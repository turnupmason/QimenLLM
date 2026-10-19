"""Only local/frozen metadata are used to diagnose generation loops or target shapes."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('repetition',ROOT/'scripts/audit_mac_book_repetition_targets.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp):
    root=Path(tmp);data=root/'frozen';data.mkdir()
    b=[];a=[];cache=[];family={}
    for split,n in (('train',265),('validation',60)):
        rows=[]
        for i in range(n):
            tid=split+str(i)
            name='feedback_continuation' if i==0 else 'role_selection'
            fid='family-'+tid
            family[fid]=split
            rows.append({'task_id':tid,'split':split,'family_id':fid,
                         'task_type':name,'messages':[{}, {}, {'content':json.dumps({
                             'chart_action':'reuse_original' if name=='feedback_continuation' else None})}]})
            cache.append({'task_id':tid,'split':split,'input_ids':list(range(17)),
                          'prefix':8})
            if i==0:
                base={'task_id':tid,'chapter':'work-employment','split':split,'task_type':name,
                      'context_mode':'independent_initial','result':{'status':'generation_error',
                        'seen_training_diagnostic':split=='train',
                        'telemetry':{'raw_output':'{"incorrect":'+ 'x'*80,'finish_reason':'length','generation_tokens':1536}}}
                tuned=json.loads(json.dumps(base));tuned['result']['telemetry']['raw_output']='{"x":"'+ 'a'*100 + '"}'
                b.append(base);a.append(tuned)
        (data/(split+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    manifest={'release_id':'shenqi-book-method-curriculum-v1','frozen':True,'family_assignments':family,
              'excluded_training_families':[], 'files':{
                  split+'.jsonl':{'sha256':sha(data/(split+'.jsonl'))} for split in ('train','validation')}}
    manifest_path=root/'manifest.json';manifest_path.write_text(json.dumps(manifest))
    def report(rows,baseline):
        return {'status':'generation_complete_not_semantic_acceptance','test_accessed':False,
               'all_chapter_model_pass':False,'adapter':None if baseline else {'a':'b'},
               'adapter_reload_parity':None if baseline else {'max_delta':0,'scales_match':True},
               'data_manifest_sha256':sha(manifest_path),'config_sha256':'abc',
               'model_manifest_sha256':'mm','revision':'pinned',
               'generation_settings':{'max_tokens':1536,'thinking':False},
               'records':rows,'chapter_counts':{'work-employment':2}}
    before=root/'before.json';after=root/'after.json'
    before.write_text(json.dumps(report(b,True)));after.write_text(json.dumps(report(a,False)))
    receipt=root/'receipt.json';receipt.write_text(json.dumps({
        'status':'complete','test_opened':False,'optimizer_updates':0,'examples':cache,
        'release_sha256':sha(manifest_path),'model_manifest_sha256':'mm'}))
    return before,after,manifest_path,data,receipt


class RepetitionAuditTests(unittest.TestCase):
    def test_suffix_loop_is_only_heuristic(self):
        self.assertGreaterEqual(mod.loop_signals('prefix'+ 'abcde'*45)['tail40_occurrences'],3)
        self.assertTrue(mod.loop_signals('X'+ 'abcde'*45)['exact_periodic_suffix'])
        self.assertFalse(mod.loop_signals('single occurrence')['exact_periodic_suffix'])
        self.assertFalse(mod.loop_signals(None)['raw_available'])

    def test_length_distribution(self):
        self.assertEqual(mod.dist([10,20,30])['median'],20)
        self.assertEqual(mod.dist([1536,1537])['above_1536'],1)

    def test_only_nonsealed_frozen_data_enter_and_no_raw_text_output(self):
        with tempfile.TemporaryDirectory() as td:
            args=fixture(td)
            result=mod.audit(*args)
            self.assertEqual(result['supervised_answer_token_lengths']['all_train_and_validation']['count'],325)
            self.assertEqual(result['feedback_continuation_train_validation_target_field']['explicit_reuse_original'],2)
            self.assertFalse(result['sealed_test_file_opened'])
            self.assertFalse(result['complete_full_book_professional_pass'])
            self.assertEqual(result['truncation_generation_tokens']['after']['max'],1536)
            self.assertNotIn('incorrect',json.dumps(result))

    def test_manifest_mismatch_rejected_before_review(self):
        with tempfile.TemporaryDirectory() as td:
            args=fixture(td)
            args[2].write_text(args[2].read_text()+' ')
            with self.assertRaisesRegex(ValueError,'identity mismatch'):
                mod.audit(*args)

    def test_wrong_feedback_target_is_reported_not_marked_correct(self):
        with tempfile.TemporaryDirectory() as td:
            args=fixture(td);data=args[3];p=data/'train.jsonl'
            rows=[json.loads(s) for s in p.read_text().splitlines()]
            rows[0]['messages'][2]['content']='{}'
            p.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
            manifest=json.loads(args[2].read_text())
            manifest['files']['train.jsonl']['sha256']=sha(p)
            args[2].write_text(json.dumps(manifest))
            cache=json.loads(args[4].read_text());cache['release_sha256']=sha(args[2]);args[4].write_text(json.dumps(cache))
            for p in args[:2]:
                report=json.loads(p.read_text());report['data_manifest_sha256']=sha(args[2]);p.write_text(json.dumps(report))
            result=mod.audit(*args)
            self.assertEqual(result['feedback_continuation_train_validation_target_field']['missing_or_wrong_reuse_original'],1)


if __name__=='__main__':unittest.main()
