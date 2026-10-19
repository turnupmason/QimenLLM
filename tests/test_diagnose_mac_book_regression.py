"""Read-only, no-leak regression analysis for two whole-book generation runs."""
import importlib.util
import copy
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('diagnose', ROOT/'scripts/diagnose_mac_book_regression.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def record(tid, status, *, chapter='work-employment', split='validation', typ='role_selection',
           raw=None, finish=None, errors=()):
    r = {'status': status, 'seen_training_diagnostic': split == 'train'}
    if raw is not None or finish is not None:
        r['telemetry'] = {'raw_output': raw, 'finish_reason': finish}
    if errors:
        r['evidence_errors'] = list(errors)
    return {'task_id': tid, 'chapter': chapter, 'split': split, 'task_type': typ,
            'context_mode': 'independent_initial', 'result': r, 'score': {
                'literal_facts_available': 2, 'literal_facts_matched': int(status == 'method_generated'),
                'binding_target_available': True, 'binding_exact_match': status == 'method_generated'
            }}


def receipts(before_rows, after_rows):
    common = {
        'status': 'generation_complete_not_semantic_acceptance',
        'test_accessed': False,
        'all_chapter_model_pass': False,
        'data_manifest_sha256': 'd'*64,
        'config_sha256': 'c'*64,
        'model_manifest_sha256': 'b'*64,
        'revision': 'pinned', 'generation_settings': {'max_tokens': 1536, 'thinking': False}
    }
    def report(rows, is_baseline):
        counts = {}
        for r in rows:
            counts[r['chapter']] = counts.get(r['chapter'], 0)+1
        return {**copy.deepcopy(common), 'adapter': None if is_baseline else {'adapters.safetensors':'sha'},
                'adapter_reload_parity': None if is_baseline else {'max_delta':0.,'scales_match':True},
                'records':rows,'chapter_counts':counts}
    return report(before_rows,True),report(after_rows,False)


def compare_in_tmp(old, new):
    with tempfile.TemporaryDirectory() as td:
        p1,p2 = Path(td)/'before.json',Path(td)/'after.json'
        p1.write_text(json.dumps(old))
        p2.write_text(json.dumps(new))
        return module.compare(p1,p2)


class RegressionTriageTests(unittest.TestCase):
    def test_status_transitions_and_no_prompt_or_raw_output_in_report(self):
        old, new = receipts([
            record('a','method_generated'),
            record('b','generation_error',raw='not-json'),
            record('c','method_evidence_error',errors=('source_table_fact_mismatch',)),
            record('d','method_generated',split='train')],
            [
            record('a','generation_error',raw='{"answers":',finish='length'),
            record('b','method_generated'),
            record('c','method_evidence_error',errors=('unavailable_reference',)),
            record('d','method_generated',split='train')])
        report = compare_in_tmp(old,new)
        self.assertEqual(report['protocol_generated'],{'before':2,'after':2,'delta':0})
        self.assertEqual(report['same_task_count'],4)
        self.assertEqual(report['generation_error_causes_before']['invalid_json'],1)
        self.assertEqual(report['generation_error_causes_after']['length_truncation'],1)
        self.assertEqual(report['by_split']['train']['interpretation'],'train_is_seen_diagnostic')
        self.assertEqual(report['by_split']['validation']['protocol_success_delta'],0)
        dumped = json.dumps(report)
        for forbidden in ('not-json','{"answers":', 'prompt', 'secret user private case answer'):
            if forbidden == 'prompt':
                # The negative privacy flag includes the word prompts, not the payload itself.
                continue
            self.assertNotIn(forbidden, dumped)
        self.assertFalse(report['sealed_test_opened'])
        self.assertFalse(report['all_chapters_professionally_accepted'])

    def test_test_split_input_rejected(self):
        old,new=receipts([record('a','method_generated')],[record('a','method_generated')])
        new['records'][0]['split']='test'
        with self.assertRaisesRegex(ValueError,'sealed test split'):
            compare_in_tmp(old,new)

    def test_mismatched_settings_rejected(self):
        old,new=receipts([record('a','method_generated')],[record('a','method_generated')])
        new['generation_settings']['max_tokens']=2048
        with self.assertRaisesRegex(ValueError,'settings'):
            compare_in_tmp(old,new)

    def test_adapter_parity_rejected(self):
        old,new=receipts([record('a','method_generated')],[record('a','method_generated')])
        new['adapter_reload_parity']['max_delta']=0.1
        with self.assertRaisesRegex(ValueError,'parity'):
            compare_in_tmp(old,new)

    def test_train_not_confused_with_heldout(self):
        old,new=receipts([record('a','method_generated',split='train')],[record('a','method_generated',split='train')])
        new['records'][0]['result']['seen_training_diagnostic']=False
        with self.assertRaisesRegex(ValueError,'mislabeled'):
            compare_in_tmp(old,new)

    def test_missing_task_rejected(self):
        old,new=receipts([record('a','method_generated'),record('b','method_generated')],
                         [record('a','method_generated')])
        with self.assertRaisesRegex(ValueError,'Task set changed'):
            compare_in_tmp(old,new)

    def test_error_cause_treats_valid_json_schema_error_separately(self):
        self.assertEqual(module.generation_failure_kind({'status':'generation_error',
            'telemetry':{'raw_output':'{"bad":"schema"}','finish_reason':'stop'}}),
            'schema_rejected_or_other_generation_error')
        self.assertEqual(module.generation_failure_kind({'status':'generation_error',
            'telemetry':{'raw_output':'','finish_reason':'stop'}}),
            'empty_or_unrecorded')


if __name__=='__main__':
    unittest.main()
