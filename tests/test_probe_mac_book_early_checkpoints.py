"""The early checkpoint probe must never substitute seen cases for heldout validation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('early_probe',ROOT/'scripts/probe_mac_book_early_checkpoints.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


def fixture(tmp):
    root=Path(tmp)
    data=root/'data'
    data.mkdir()
    rows=[]
    families={}
    for typ in mod.EXPECTED_TYPES:
        for n in range(4):
            tid=typ+'-'+str(n)
            fid='family-'+tid
            families[fid]='validation'
            rows.append({'task_id':tid,'family_id':fid,
                         'split':'validation','chapter':'chapter-'+typ,'task_type':typ})
    val=data/'validation.jsonl'
    val.write_text('\n'.join(json.dumps(x) for x in rows)+'\n',encoding='utf-8')
    digest=hashlib.sha256(val.read_bytes()).hexdigest()
    manifest={'release_id':'shenqi-book-method-curriculum-v1','frozen':True,
              'family_assignments':families,'excluded_training_families':[],
              'files':{'validation.jsonl':{'sha256':digest}}}
    m=root/'manifest.json'
    m.write_text(json.dumps(manifest),encoding='utf-8')
    return m,data


class CheckpointProbeTests(unittest.TestCase):
    def test_frozen_validation_only_exact_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,data=fixture(tmp)
            meta,rows=mod.select_validation(m,data)
            self.assertEqual(len(rows),15)
            self.assertEqual(len({r['task_id'] for r in rows}),15)
            self.assertEqual(set(r['split'] for r in rows),{'validation'})
            self.assertEqual([r['task_id'] for r in rows],
                             [r['task_id'] for r in mod.select_validation(m,data)[1]])
            self.assertNotIn('source_knowledge', {r['task_type'] for r in rows})
            self.assertEqual(set(r['task_type'] for r in rows),set(mod.EXPECTED_TYPES))

    def test_duplicate_or_wrong_family_never_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,data=fixture(tmp)
            records=(data/'validation.jsonl').read_text().splitlines()
            source=json.loads(records[0])
            old=json.loads(m.read_text())
            old['family_assignments'][source['family_id']]='train'
            m.write_text(json.dumps(old))
            with self.assertRaisesRegex(ValueError,'family split leakage'):
                mod.select_validation(m,data)

    def test_validation_manifest_sha_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,data=fixture(tmp)
            with (data/'validation.jsonl').open('a') as f:f.write('\n')
            with self.assertRaisesRegex(ValueError,'bytes differ'):
                mod.select_validation(m,data)

    def test_missing_task_type_is_not_silently_included_from_train(self):
        with tempfile.TemporaryDirectory() as tmp:
            m,data=fixture(tmp)
            rows=[json.loads(x) for x in (data/'validation.jsonl').read_text().splitlines()]
            rows=[r for r in rows if r['task_type']!='feedback_continuation']
            p=data/'validation.jsonl'
            p.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
            meta=json.loads(m.read_text())
            meta['files']['validation.jsonl']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
            m.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'task types changed'):
                mod.select_validation(m,data)

    def test_comparison_never_claims_prediction_success(self):
        chosen=[{'task_id':t,'task_type':'role_selection'} for t in ('a','b','c')]
        before={'a':'method_generated','b':'method_generated','c':'generation_error'}
        after={'a':'generation_error','b':'method_generated','c':'generation_error'}
        early={'a':'method_generated','b':'method_generated','c':'method_generated'}
        comp=mod.compare_subset(before,after,early,chosen)
        self.assertFalse(comp['final_professional_acceptance'])
        self.assertFalse(comp['test_opened'])
        self.assertEqual(comp['success_by_task_type']['role_selection'],
                         {'base':2,'epoch05':1,'probe':3})
        self.assertEqual(comp['matched_validation_task_count'],3)


if __name__=='__main__':
    unittest.main()
