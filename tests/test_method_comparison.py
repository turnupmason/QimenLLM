"""Refuse misleading before/after or protocol-only improvement claims."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'training'))
from compare_method_runs import compare


class MethodComparisonTests(unittest.TestCase):
    def setUp(self):
        telemetry = {'max_tokens':768,'max_context_tokens':8192,'temperature':0.0,'seed':17,'enable_thinking':False}
        self.before = {'test_accessed':False,'adapter':None,'finished_unix':10,
            'model':'pinned27B','revision':'revision','model_manifest_sha256':'weights',
            'data_manifest_sha256':'data','source_data_version':'source',
            'records':[{'task_id':str(i),'split':'validation','task_type':'chart_evidence',
                'result':{'payload_sha256':'input'+str(i),'status':'method_generated','telemetry':dict(telemetry)},
                'score':{'literal_facts_available':7,'literal_facts_matched':7}} for i in range(4)]}
        self.after = copy.deepcopy(self.before);self.after['adapter']={'sha256':'adapter'}
        self.review = {'split':'validation','reviewer':'fixture source reviewer','source_basis':'frozen source',
            'tasks':{str(i):{'source_fidelity_pass':False,'task_completion_pass':True,
                            'no_unsupported_factual_claims':False,'source_note':'Typed facts right; narrative assigns wrong role.'}
                     for i in range(4)}}

    def test_perfect_structured_and_protocol_scores_do_not_prove_method_pass(self):
        r = compare(self.before,self.after,self.review)
        self.assertEqual(r['validation_source_fidelity_and_task_passes'],0)
        self.assertFalse(r['mac_limited_method_review_pass'])
        self.assertIsNone(r['independent_real_world_accuracy'])

    def test_changed_input_model_data_or_generation_settings_are_not_comparable(self):
        changes = [lambda a:a.update(revision='other'),lambda a:a.update(data_manifest_sha256='other'),
                   lambda a:a['records'][0]['result'].update(payload_sha256='changed'),
                   lambda a:a['records'][0]['result']['telemetry'].update(max_tokens=4096)]
        for change in changes:
            a=copy.deepcopy(self.after);change(a)
            with self.assertRaises(ValueError):compare(self.before,a,self.review)

    def test_test_access_missing_settings_or_incomplete_source_review_is_rejected(self):
        a=copy.deepcopy(self.after);a['test_accessed']=True
        with self.assertRaises(ValueError):compare(self.before,a,self.review)
        a=copy.deepcopy(self.after);del a['records'][0]['result']['telemetry']['seed']
        with self.assertRaises(ValueError):compare(self.before,a,self.review)
        r=copy.deepcopy(self.review);del r['tasks']['0']
        with self.assertRaises(ValueError):compare(self.before,self.after,r)

    def test_source_method_pass_still_cannot_claim_full_system_or_real_prediction(self):
        for task in self.review['tasks'].values():
            task.update(source_fidelity_pass=True,no_unsupported_factual_claims=True,
                        source_note='All factual claims and method conditions compared with released source.')
        r=compare(self.before,self.after,self.review)
        self.assertTrue(r['mac_limited_method_review_pass'])
        self.assertFalse(r['systematic_training_ready'])
        self.assertFalse(r['full_system_D_E_validated'])
        self.assertIsNone(r['author_method_population_accuracy'])
