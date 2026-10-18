"""Full-book 26-source matrix stays honest about held-out and seen diagnostics."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('book_chapter_audit', ROOT/'scripts/book_chapter_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MANIFEST = json.loads((ROOT/'data/splits/book_method_curriculum_v1.json').read_bytes())


def fixture_records():
    result = []
    for key, source in MANIFEST['chapter_coverage'].items():
        split = next(s for s in ('validation','development','train') if source['task_counts'].get(s,0))
        result.append({
            'task_id': 'fixture-'+key, 'chapter': key, 'split': split,
            'result': {
                'status': 'method_generated',
                'seen_training_diagnostic': split == 'train'
            }
        })
    return result


class FullChapterCoverageAuditTests(unittest.TestCase):
    def test_all_fifteen_case_chapters_and_all_26_sources_in_matrix(self):
        report = module.matrix(MANIFEST)
        s = report['summary']
        self.assertEqual(s['source_chapters'], 26)
        self.assertEqual(s['case_method_chapters'], 15)
        self.assertEqual(s['theory_or_source_chapters'], 11)
        self.assertEqual(s['source_chapters_with_validation_tasks'], 10)
        self.assertEqual(s['source_chapters_with_development_tasks'], 3)
        self.assertEqual(s['frozen_test_tasks_reserved'], 57)
        self.assertEqual(len(s['case_chapters_missing_any_sealed_test_tasks']), 6)
        self.assertEqual(len(s['case_chapters_missing_unseen_validation_families']), 5)
        self.assertEqual(s['minimum_eligible_independent_final_test_cases_per_case_chapter'], 1)
        self.assertFalse(s['every_case_chapter_independent_final_test_verified'])
        missing = {c['chapter'] for c in s['case_chapters_missing_any_sealed_test_tasks']}
        self.assertIn('education-examinations', missing)
        self.assertIn('health-prediction', missing)
        self.assertIn('pregnancy-childbirth', missing)
        self.assertIn('weather-prediction', missing)
        self.assertIn('geography-environment', missing)
        self.assertIn('life-opportunities', missing)
        self.assertFalse(s['test_file_opened'])
        self.assertFalse(s['all_chapter_professional_pass'])
        for c in report['chapters']:
            self.assertIsNone(c['professional_chapter_pass'])

    def test_all_chapter_generation_is_diagnostics_not_certification(self):
        report = module.matrix(MANIFEST, fixture_records())
        self.assertTrue(report['summary']['full_source_generation_coverage'])
        self.assertEqual(report['summary']['eval_records'], 26)
        self.assertFalse(report['summary']['test_inference_performed'])
        by_id = {c['chapter']: c for c in report['chapters']}
        self.assertEqual(by_id['work-employment']['seen_train_diagnostics'],1)
        self.assertEqual(by_id['work-employment']['unseen_case_evidence'],'missing_unseen_validation_family')
        self.assertEqual(by_id['education-examinations']['seen_train_diagnostics'],1)
        self.assertEqual(by_id['business-finance']['heldout_validation_records'],1)
        self.assertIsNone(by_id['business-finance']['professional_chapter_pass'])

    def test_evaluation_cannot_omit_any_source(self):
        with self.assertRaisesRegex(ValueError,'all 26'):
            module.matrix(MANIFEST, fixture_records()[:-1])

    def test_sealed_test_and_seen_train_spoofing_are_rejected(self):
        rows = fixture_records()
        rows[0]['split'] = 'test'
        with self.assertRaisesRegex(ValueError,'Test or unknown'):
            module.matrix(MANIFEST, rows)
        rows = fixture_records()
        first = next(r for r in rows if r['split']=='train')
        first['result']['seen_training_diagnostic'] = False
        with self.assertRaisesRegex(ValueError,'visibly labeled'):
            module.matrix(MANIFEST, rows)

    def test_manifest_split_counts_are_immutable(self):
        m = json.loads(json.dumps(MANIFEST))
        m['chapter_coverage']['work-employment']['task_counts']['train'] = 99
        with self.assertRaisesRegex(ValueError,'counts disagree'):
            module.matrix(m)


if __name__=='__main__':
    unittest.main()
