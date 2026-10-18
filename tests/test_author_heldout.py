"""Frozen family holdout permissions and independent source-label axes."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from qimenllm.contracts import Inquiry
from qimenllm.evaluation.research import ResearchRequest,prepare,score
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.reasoning.service import QimenService

ROOT=Path(__file__).resolve().parents[1]
SUITE=ROOT/'data/structured/shenqi/author_initial_heldout_v2.json'
class HeldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.db=Path(cls.tmp.name)/'data.sqlite3'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,Path(cls.tmp.name)/'raw')
        cls.service=QimenService(cls.db);cls.suite=json.loads(SUITE.read_bytes())
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def req(self,t,path=SUITE,arm='symbolic_chart'):
        return ResearchRequest(str(path),hashlib.sha256(path.read_bytes()).hexdigest(),t['task_id'],arm)
    def test_six_held_out_initial_inputs_and_all_gold_quotes_resolve(self):
        self.assertEqual(len(self.suite['tasks']),6)
        for t in self.suite['tasks']:
            payload,diag=prepare(self.service,self.req(t),Inquiry(t['question']))
            self.assertEqual(diag['evaluation_scope'],'frozen_initial_turn_test')
            self.assertEqual(payload['knowledge'],[]);self.assertEqual(payload['candidate_conditions'],[])
            for axis in ('author','reported_outcome'):
                for target in t['gold'][axis].values():
                    for source in payload['known_information']:
                        self.assertNotEqual(source['id'],self._record_source(target['record_id']))
            scored=score(self.db,t,{'output':{'answers':{}}})
            self.assertIsNone(scored['real_world_predictive_accuracy'])
            self.assertIn('family_held_out_historical_test_not_prospective',scored['limitations'])
    def _record_source(self,rid):
        import sqlite3
        with sqlite3.connect(self.db) as conn:return conn.execute('SELECT source_id FROM case_records WHERE record_id=?',(rid,)).fetchone()[0]
    def test_heldout_other_arms_are_not_implicitly_authorized(self):
        t=self.suite['tasks'][0]
        with self.assertRaises(ValueError):prepare(self.service,self.req(t,arm='base'),Inquiry(t['question']))
    def test_forged_family_assignment_cannot_promote_train_into_test(self):
        suite=copy.deepcopy(self.suite);t=suite['tasks'][0];suite['family_assignments'][t['family_id']]='train'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text(json.dumps(suite))
            with self.assertRaises(ValueError):prepare(self.service,self.req(t,path),Inquiry(t['question']))
    def test_release_hash_must_match(self):
        suite=copy.deepcopy(self.suite);suite['frozen_release_sha256']='0'*64;t=suite['tasks'][0]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text(json.dumps(suite))
            with self.assertRaises(ValueError):prepare(self.service,self.req(t,path),Inquiry(t['question']))

if __name__=='__main__':unittest.main()
