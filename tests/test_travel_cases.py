"""Travel source fidelity, shared service projection, chronology and append-only replay."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import restore_snapshot, export_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.knowledge.travel import TRAVEL_SHA
from qimenllm.cases.ingestion import import_cases
from qimenllm.knowledge.importer import ImportConflict
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_travel import ingest


class TravelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'travel.sqlite3'; cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:
            cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in
                ['cases','events','charts','case_records','raw_documents','source_reviews','rules','training_tasks']}
        cls.result=ingest(cls.db,cls.raw)
        cls.artifact=json.loads((ROOT/'data/structured/shenqi/travel_cases.json').read_bytes())
        cls.bytes=(ROOT/'data/provenance/uploads'/f'{TRAVEL_SHA}.utf8').read_bytes()
        cls.lines=cls.bytes.decode().splitlines(keepends=True)
        cls.svc=QimenService(cls.db)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_original_bytes_and_every_selector(self):
        self.assertEqual((len(self.bytes),len(self.lines),digest(self.bytes)),(31026,350,TRAVEL_SHA))
        self.assertTrue(self.bytes.endswith('只是对这一点当时没有细看\n'.encode()))
        for case in self.artifact['cases']:
            for ev in case['events']:
                for record in ev['records']:
                    s=record['payload']['source_selector']
                    self.assertEqual(self.bytes[s['byte_start']:s['byte_end']].decode(),record['text'])
                for ch in ev['charts']:
                    a,b=ch['source_lines'];self.assertEqual(''.join(self.lines[a-1:b]),ch['payload']['raw_chart_text'])
                    for row in ch['payload']['source_table_rows']:
                        s=row['source_selector'];self.assertEqual(self.bytes[s['byte_start']:s['byte_end']].decode(),s['source_quote'])

    def test_all_narratives_and_grid_cells_through_shared_service(self):
        cases=self.svc.cases('travel-abroad')['cases'];self.assertEqual(len(cases),6)
        total=0
        for case in cases:
            for ev in case['events']:
                for cid in ev['chart_ids']:
                    p=self.svc.case_chart(case['case_id'],cid)
                    self.assertEqual((p['status'],p['chart_id']),('projected',cid))
                    self.assertEqual(set(p['palaces']),set(map(str,range(1,10))))
                    self.assertFalse(p['engine_verified'])
                    for palace in p['palaces'].values():
                        self.assertIn('│',palace['source']['text'])
                        self.assertIn(palace['source']['grid_column'],[1,2,3])
                    total+=1
        self.assertEqual(total,7)

    def test_companion_and_original_duplicate_stems_are_not_silently_fixed(self):
        case=self.svc.cases('travel-abroad')['cases'][5]
        projections=[self.svc.case_chart(case['case_id'],cid) for cid in case['events'][0]['chart_ids']]
        p=next(p for p in projections if p['palaces']['7'].get('source_star_cell_as_written')=='芮禽己')
        self.assertEqual(p['palaces']['7']['source_star_cell_as_written'],'芮禽己')
        self.assertEqual(p['palaces']['7']['additional_star_as_written'],'禽')
        self.assertIsNone(p['palaces']['7']['additional_star_carried_stem'])
        self.assertEqual(p['palaces']['5']['earth_stem'],'己')
        self.assertEqual(p['palaces']['7']['earth_stem'],'己')

    def test_october_review_uses_same_chart_and_withholds_later_diagnoses(self):
        e=self.artifact['cases'][3]['events'][0]
        self.assertEqual(len(e['charts']),1)
        initial={r['chart_key'] for r in e['records'] if r['source_lines'][0]<193}
        later=[r for r in e['records'] if r['source_lines'][0]>=193]
        self.assertEqual(initial,{r['chart_key'] for r in later})
        self.assertTrue(all(r['knowledge_phase']=='post_feedback' for r in later))
        self.assertEqual(next(r for r in later if r['source_lines']==[243,243])['kind'],'feedback')

    def test_two_times_one_trip_and_posthoc_rain_explanation(self):
        e=self.artifact['cases'][5]['events'][0]
        self.assertEqual(len(e['charts']),2)
        get=lambda n:next(r for r in e['records'] if r['source_lines']==[n,n])
        self.assertNotEqual(get(309)['chart_key'],get(340)['chart_key'])
        self.assertEqual(get(348)['kind'],'feedback')
        self.assertEqual(get(350)['knowledge_phase'],'post_feedback')
        self.assertFalse(any(r['knowledge_phase']=='pre_prediction' for r in e['records']))

    def test_reference_conditions_unknown_and_matching_still_do_not_bind(self):
        for context in [{},{'domain':'travel','travel_subtype':'air','method_scope':'shenqi_travel_air_reference_v1'}]:
            r=self.svc.rule_candidates(context,domain='travel',method='shenqi_travel_reference_v1')
            self.assertEqual(r['candidate_count'],8)
            self.assertFalse(r['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),int(bool(context)))

    def test_old_rows_unchanged_and_full_audit(self):
        with connect(self.db) as c:
            for t,rows in self.before.items():
                now=[tuple(r) for r in c.execute('SELECT * FROM '+t)]
                self.assertTrue(all(row in now for row in rows),t)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rules').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0],0)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_exact_replay_adds_no_rows_or_versions(self):
        with connect(self.db) as c:n=c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        r=ingest(self.db,self.raw)
        self.assertTrue(r['cases']['duplicate']);self.assertTrue(r['candidates']['duplicate'])
        with connect(self.db) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],n)

    def test_immutable_case_manifest_rejects_rewrite(self):
        bad=copy.deepcopy(self.artifact);bad['cases'][0]['title']='changed'
        with self.assertRaises(ImportConflict):import_cases(self.db,self.result['source']['revision_id'],bad)

    def test_snapshot_roundtrip_exact(self):
        first=self.path/'snapshot';again=self.path/'again';db=self.path/'roundtrip.sqlite3';raw=self.path/'roundtrip_raw'
        export_snapshot(self.db,self.raw,first);restore_snapshot(first,db,raw);export_snapshot(db,raw,again)
        self.assertEqual({str(p.relative_to(first)):p.read_bytes() for p in first.rglob('*') if p.is_file()},
                         {str(p.relative_to(again)):p.read_bytes() for p in again.rglob('*') if p.is_file()})
