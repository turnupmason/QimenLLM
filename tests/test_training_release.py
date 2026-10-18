"""Release chronology and complete-epoch invariants; no large-model dependency."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'training'/(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
release=module('author_release');protocol=module('epoch_protocol')

class EpochProtocolTests(unittest.TestCase):
    def test_fifty_complete_passes_with_odd_example_count(self):
        ids=['task-'+str(i) for i in range(33)]
        seen=[]
        for epoch in range(50):
            order=protocol.order_for_epoch(ids,epoch);self.assertEqual(set(order),set(ids))
            self.assertEqual(len(order),33);seen+=order
        self.assertEqual(len(seen),1650)
        self.assertTrue(all(seen.count(t)==50 for t in ids))
    def test_resume_cursor_and_order_both_checked(self):
        ids=['a','b','c'];s={'epoch':4,'cursor':2,'optimizer_step':14,'data_order':protocol.order_for_epoch(ids,4)}
        protocol.validate_cursor(s,ids,50)
        with self.assertRaises(ValueError):protocol.validate_cursor(s|{'optimizer_step':15},ids,50)
        with self.assertRaises(ValueError):protocol.validate_cursor(s|{'data_order':list(reversed(s['data_order']))},ids,50)
    def test_completed_epoch_boundary_and_final_cursor(self):
        protocol.validate_cursor({'epoch':50,'cursor':0,'optimizer_step':150,'data_order':[]},['a','b','c'],50)
        with self.assertRaises(ValueError):protocol.validate_cursor({'epoch':50,'cursor':1,'optimizer_step':151,'data_order':[]},['a','b','c'],50)
    def test_scheduler_uses_updates_and_complete_epoch_warmup(self):
        self.assertAlmostEqual(protocol.learning_rate(33,1650,33),1e-4)
        self.assertAlmostEqual(protocol.learning_rate(1650,1650,33),1e-5)
        self.assertLess(protocol.learning_rate(1,1650,33),1e-4)
        with self.assertRaises(ValueError):protocol.learning_rate(1651,1650,33)
    def test_duplicate_examples_rejected(self):
        with self.assertRaises(ValueError):protocol.order_for_epoch(['a','a'],0)

class SourceReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review=json.loads((ROOT/'data/provenance/author_initial_turn_review_v1.json').read_bytes())
        cls.dev=json.loads((ROOT/'data/structured/shenqi/baseline_development_v3.json').read_bytes())
        # Test from committed snapshot in a temporary DB, independent of work/.
        from qimenllm.knowledge.snapshot import restore_snapshot
        cls.tmp=tempfile.TemporaryDirectory();cls.db=Path(cls.tmp.name)/'test.sqlite3'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,Path(cls.tmp.name)/'raw')
        cls.tasks,cls.manifest=release.build(cls.db,cls.review,cls.dev)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_actual_release_has_reviewed_initial_subtasks_and_all_families(self):
        self.assertEqual(len(self.tasks),49)
        self.assertEqual(len(self.manifest['family_assignments']),94)
        self.assertEqual(self.manifest['split_counts'],{'train':33,'validation':9,'test':6,'development':1})
    def test_source_bytes_and_db_chronology_unchanged(self):
        c=sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM events WHERE chronology_status='verified'").fetchone()[0],0)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0],0)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM dataset_releases').fetchone()[0],0)
        self.assertFalse(self.manifest['full_cases_modified'])
    def test_no_case_title_target_or_feedback_in_prompt(self):
        for task in self.tasks:
            payload=json.loads(task['messages'][1]['content'])
            self.assertEqual(set(payload),{'scope','known_information','source_chart'})
            self.assertTrue(set(task['input_record_ids']).isdisjoint(task['target_record_ids']))
            prompt=task['messages'][1]['content']
            for target in task['target_sources']:
                self.assertNotIn(target['text'],prompt)
            self.assertLessEqual(task['input_sources'][-1]['byte_end'],min(s['byte_start'] for s in task['target_sources']))
    def test_family_split_and_development_exclusion(self):
        dev={t['family_id'] for t in self.dev['tasks']};owners={}
        for task in self.tasks:
            self.assertEqual(owners.setdefault(task['family_id'],task['split']),task['split'])
            if task['family_id'] in dev:self.assertEqual(task['split'],'development')
    def test_no_unknown_phase_input_and_every_quote_is_literal(self):
        c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row
        for task in self.tasks:
            for rid in task['input_record_ids']:
                r=c.execute('SELECT * FROM case_records WHERE record_id=?',(rid,)).fetchone()
                self.assertEqual(r['knowledge_phase'],'pre_prediction');self.assertLess(r['sequence'],task['cutoff_sequence'])
            answer=json.loads(task['messages'][-1]['content'])
            self.assertEqual([x['text'] for x in answer['author_steps']],[x['text'] for x in task['target_sources']])
    def test_feedback_injected_as_input_rejected(self):
        review=copy.deepcopy(self.review);chosen=next(r for r in review['rows'] if r['disposition']=='include_initial_turn')
        c=sqlite3.connect(self.db)
        rid=c.execute("SELECT record_id FROM case_records WHERE event_id=? AND knowledge_phase='post_feedback' LIMIT 1",(chosen['event_id'],)).fetchone()[0]
        chosen['input_record_ids'].append(rid)
        with self.assertRaises(ValueError):release.build(self.db,review,self.dev)
    def test_target_injected_as_input_rejected(self):
        review=copy.deepcopy(self.review);chosen=next(r for r in review['rows'] if r['disposition']=='include_initial_turn')
        chosen['input_record_ids'].append(chosen['target_record_ids'][0])
        with self.assertRaises(ValueError):release.build(self.db,review,self.dev)
    def test_wrong_family_and_data_version_rejected(self):
        review=copy.deepcopy(self.review);review['source_data_version']='other'
        with self.assertRaises(ValueError):release.build(self.db,review,self.dev)
        review=copy.deepcopy(self.review);chosen=next(r for r in review['rows'] if r['disposition']=='include_initial_turn');chosen['family_id']='other'
        with self.assertRaises(ValueError):release.build(self.db,review,self.dev)
        review=copy.deepcopy(self.review);chosen=next(r for r in review['rows'] if r['disposition']=='include_initial_turn');chosen['case_id']='wrong-case'
        with self.assertRaises(ValueError):release.build(self.db,review,self.dev)

    def test_frozen_v1_and_v2_rebuild_hashes_and_metadata_permissions(self):
        import hashlib
        for version in (1,2):
            review=json.loads((ROOT/f'data/provenance/author_initial_turn_review_v{version}.json').read_bytes())
            tasks,manifest=release.build(self.db,review,self.dev)
            frozen=json.loads((ROOT/f'data/splits/author_initial_release_v{version}.json').read_bytes())
            for split in ('train','validation','test','development'):
                raw=b''.join(release.encoded(t) for t in tasks if t['split']==split)
                self.assertEqual(hashlib.sha256(raw).hexdigest(),frozen['files'][split+'.jsonl']['sha256'])
            if version==2:
                self.assertEqual(sum(len(t['metadata_permissions']) for t in tasks),31)
                for task in tasks:
                    for p in task['metadata_permissions']:
                        self.assertEqual(p['permission'],'source_given_symbolic_time_metadata_only')
                        self.assertEqual(p['text_sha256'],hashlib.sha256(next(s['text'] for s in task['input_sources'] if self._source_for_record(p['record_id'])==s['source_id']).encode()).hexdigest())
    def _source_for_record(self,rid):
        with sqlite3.connect(self.db) as c:return c.execute('SELECT source_id FROM case_records WHERE record_id=?',(rid,)).fetchone()[0]

if __name__=='__main__':unittest.main()
