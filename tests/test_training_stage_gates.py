"""Resume boundary correctness and Mac-first quality gate before GPU work."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
from train_mac_method_lora import validate_mac_cursor,validate_official_resume_name
from epoch_protocol import order_for_epoch
from cuda_pilot import require_mac_method_review,sha,train


class MacResumeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.ids=['a','b','c']

    def test_completed_last_update_can_resume_pending_epoch_validation(self):
        state={'epoch':0,'cursor':3,'optimizer_step':3,'data_order':order_for_epoch(self.ids,0)}
        before=copy.deepcopy(state)
        validate_mac_cursor(state,self.ids)
        self.assertEqual(state,before)  # validation is still pending; no silent epoch promotion

    def test_wrong_cursor_step_or_end_order_is_rejected(self):
        for state in (
            {'epoch':0,'cursor':2,'optimizer_step':1,'data_order':order_for_epoch(self.ids,0)},
            {'epoch':0,'cursor':3,'optimizer_step':3,'data_order':['wrong']},
            {'epoch':3,'cursor':3,'optimizer_step':12,'data_order':[]}):
            with self.assertRaises(ValueError):validate_mac_cursor(state,self.ids)

    def test_mid_epoch_and_final_epoch_ledgers_are_valid(self):
        validate_mac_cursor({'epoch':1,'cursor':1,'optimizer_step':4,
                             'data_order':order_for_epoch(self.ids,1)},self.ids)
        validate_mac_cursor({'epoch':3,'cursor':0,'optimizer_step':9,'data_order':[]},self.ids)

    def test_disposable_probe_is_not_an_official_resume_point(self):
        for path in ('resume-probe','arbitrary','step-wrong'):
            with self.assertRaises(ValueError):validate_official_resume_name(Path(path))
        validate_official_resume_name(Path('step-0022'))
        validate_official_resume_name(Path('epoch-01'))


class MacBeforeCudaGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'review.json'
        self.c={'mac_quality_report':str(self.path),'manifest':'data/splits/lost_method_release_v5.json',
                'systematic_training':False}
        self.report={'mac_limited_method_review_pass':True,'test_accessed':False,
            'model':'mlx-community/Qwen3.8-27B-4bit','revision':'10c35caafbb80f7dc6a7a432cdd11af10a6d4818',
            'data_manifest_sha256':sha((ROOT/self.c['manifest']).read_bytes()),'systematic_training_ready':False}

    def tearDown(self):self.tmp.cleanup()

    def write(self):self.path.write_text(json.dumps(self.report))

    def test_missing_or_failed_mac_review_blocks_before_gpu_initialization(self):
        with patch('cuda_pilot.cuda_model',side_effect=AssertionError('GPU should not initialize')):
            with self.assertRaisesRegex(ValueError,'Mac'):train(self.c,Path(self.tmp.name))
        self.report['mac_limited_method_review_pass']=False;self.write()
        with self.assertRaisesRegex(ValueError,'failed'):require_mac_method_review(self.c)

    def test_wrong_data_model_or_test_access_cannot_unlock_training(self):
        for field,value in (('data_manifest_sha256','wrong'),('model','a-smaller-model'),('test_accessed',True)):
            original=copy.deepcopy(self.report);self.report[field]=value;self.write()
            with self.assertRaises(ValueError):require_mac_method_review(self.c)
            self.report=original

    def test_local_method_pass_only_allows_bounded_pilot_not_full_system_training(self):
        self.write();approved=require_mac_method_review(self.c)
        self.assertTrue(approved['limited_method_pass'])
        self.assertFalse(approved['systematic_training_ready'])
        self.c['systematic_training']=True
        with self.assertRaisesRegex(ValueError,'Full-system'):require_mac_method_review(self.c)
