"""Missing-person chapter fidelity, chronology, conditions and whole-case service paths."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qimenllm.api.app import create_app
from qimenllm.cases.ingestion import import_cases
from qimenllm.knowledge.db import connect,digest
from qimenllm.knowledge.importer import ImportConflict
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.missing import MISSING_SHA
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_missing import ingest


class MissingCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'missing.sqlite3';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:
            cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in
                ['cases','events','charts','case_records','source_spans','raw_documents','source_reviews','rules','training_tasks']}
        cls.result=ingest(cls.db,cls.raw)
        cls.artifact=json.loads((ROOT/'data/structured/shenqi/missing_cases.json').read_bytes())
        cls.gold=json.loads((ROOT/'data/structured/shenqi/missing_gold.json').read_bytes())['charts']
        cls.source=(ROOT/'data/provenance/uploads'/f'{MISSING_SHA}.utf8').read_bytes()
        cls.svc=QimenService(cls.db)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def record(self,case,line):
        return next(r for r in self.artifact['cases'][case-1]['events'][0]['records'] if r['source_lines']==[line,line])

    def test_original_bytes_line_counts_and_all_quotes(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(MISSING_SHA,49372,477))
        for c in self.artifact['cases']:
            for s in c['source_selectors']:
                self.assertEqual(self.source[s['byte_start']:s['byte_end']].decode(),s['source_quote'])
            for e in c['events']:
                for r in e['records']:
                    s=r['payload']['source_selector']
                    self.assertEqual(self.source[s['byte_start']:s['byte_end']].decode(),r['text'])
                    for seg in r['payload'].get('source_statement_segments',[]):
                        self.assertEqual(self.source[seg['byte_start']:seg['byte_end']].decode(),seg['text'])

    def test_narrative_ranges_do_not_overlap_or_omit_titles(self):
        lines=self.source.decode().splitlines()
        self.assertEqual(len(self.artifact['cases']),10)
        for i,c in enumerate(self.artifact['cases']):
            a,b=c['source_ranges'][0];self.assertEqual(lines[a-1],c['title'])
            if i:self.assertEqual(self.artifact['cases'][i-1]['source_ranges'][0][1]+1,a)
        self.assertEqual(self.artifact['cases'][-1]['source_ranges'][0][1],477)

    def test_all_99_literal_palaces_match_independent_source_gold(self):
        found={ch['chart_key']:ch for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        self.assertEqual(set(found),set(self.gold))
        for key,ch in found.items():
            self.assertEqual([r['cells'] for r in ch['payload']['source_table_rows']],self.gold[key],key)
            for r in ch['payload']['source_table_rows']:
                s=r['source_selector'];self.assertEqual(self.source[s['byte_start']:s['byte_end']].decode(),s['source_quote'])
                self.assertEqual(s['line_end']-s['line_start'],3)

    def test_all_charts_project_same_id_through_service(self):
        expected_by_line={ch['source_lines'][0]+2:self.gold[ch['chart_key']]
            for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        n=0
        for c in self.svc.cases('missing-person')['cases']:
            for e in c['events']:
                for cid in e['chart_ids']:
                    p=self.svc.case_chart(c['case_id'],cid)
                    self.assertEqual((p['status'],p['chart_id']),('projected',cid))
                    self.assertEqual(set(p['palaces']),set(map(str,range(1,10))))
                    self.assertFalse(p['engine_verified'])
                    self.assertFalse(p['original_chart_modified'])
                    first_line=min(v['source']['line'] for v in p['palaces'].values())
                    expected=expected_by_line[first_line]
                    for palace,cells in zip((4,9,2,3,5,7,8,1,6),expected):
                        self.assertEqual(p['palaces'][str(palace)]['source']['column_cells'],cells)
                    for palace in p['palaces'].values():self.assertIn('│',palace['source']['text'])
                    n+=1
        self.assertEqual(n,11)

    def test_case2_dual_basis_and_six_unprovided_charts_not_invented(self):
        c=self.artifact['cases'][1];self.assertEqual(len(c['events']),1)
        charts=c['events'][0]['charts'];self.assertEqual(len(charts),2)
        self.assertEqual([ch['payload']['source_chart_metadata']['casting_time_basis_as_written'] for ch in charts],['inquiry_time','disappearance_time'])
        self.assertEqual(self.record(2,131)['payload']['record_role'],'six_later_consultations_summary_no_charts')
        self.assertEqual(self.record(2,133)['kind'],'outcome')

    def test_case3_retrospective_opening_and_analysis_are_withheld(self):
        records=self.artifact['cases'][2]['events'][0]['records']
        self.assertTrue(all(r['knowledge_phase']=='post_feedback' for r in records))
        self.assertIn('5月20日',self.record(3,137)['text'])
        self.assertEqual([s['knowledge_phase'] for s in self.record(3,137)['payload']['source_statement_segments']],['unknown','prediction','post_feedback'])

    def test_wrong_forecasts_are_preserved_without_hindsight_relabeling(self):
        for case,line,post in [(5,239,241),(9,401,403)]:
            r=self.record(case,line)
            self.assertEqual(r['knowledge_phase'],'post_feedback')
            a,b=r['payload']['source_statement_segments']
            self.assertEqual(a['knowledge_phase'],'prediction');self.assertEqual(b['knowledge_phase'],'post_feedback')
            self.assertIn('凶多吉少',a['text']);self.assertIn('断错',b['text'])
            self.assertEqual(self.record(case,post)['knowledge_phase'],'post_feedback')

    def test_case10_initial_failed_deadline_reply_and_seminar_are_separate(self):
        self.assertEqual(self.record(10,453)['knowledge_phase'],'prediction')
        self.assertEqual(self.record(10,455)['kind'],'feedback')
        self.assertEqual(self.record(10,459)['knowledge_phase'],'post_feedback')
        self.assertEqual(len(self.record(10,459)['payload']['source_statement_segments']),2)
        self.assertEqual(self.record(10,473)['payload']['death_date_status'],'author_retrospective_estimate_not_confirmed_death_date')
        self.assertEqual(len(self.artifact['cases'][9]['events'][0]['charts']),1)

    def test_actual_reported_outcomes_not_upgraded_to_other_claims(self):
        self.assertIn('商场警卫',self.record(8,369)['text'])
        self.assertIn('公安',self.record(8,367)['text'])
        self.assertEqual(self.record(8,367)['kind'],'prediction')
        self.assertEqual(self.record(8,369)['kind'],'outcome')
        self.assertIn('六十六天',self.record(9,415)['text'])

    def test_native_center_and_star_prefix_literal_are_retained(self):
        c=self.svc.cases('missing-person')['cases'][9];cid=c['events'][0]['chart_ids'][0]
        p=self.svc.case_chart(c['case_id'],cid)
        self.assertEqual(p['palaces']['5']['earth_stem'],'庚')
        self.assertEqual(p['palaces']['2']['star_prefix_marker'],'庚')
        self.assertEqual(p['palaces']['7']['heaven_prefix_marker'],'庚')

    def test_case7_explicit_hour_role_does_not_rewrite_general_rule(self):
        c=self.artifact['cases'][6]['events'][0]
        self.assertEqual(c['charts'][0]['payload']['source_chart_metadata']['casting_time_basis_as_written'],'disappearance_time')
        self.assertIn('时干',self.record(7,315)['text'])
        self.assertIn('do not rewrite',self.record(7,315)['payload']['method_exception_scope'])

    def test_conditions_require_basis_and_relationship_not_age(self):
        contexts=[({},0),({'domain':'missing_person','casting_time_basis':'inquiry_time','age':14,'method_scope':'shenqi_missing_roles_reference_v1'},0),({'domain':'missing_person','casting_time_basis':'inquiry_time','target_relationship':'parent_to_child','method_scope':'shenqi_missing_roles_reference_v1'},1),({'domain':'missing_person','casting_time_basis':'disappearance_time','method_scope':'shenqi_missing_roles_reference_v1'},1)]
        for context,expected in contexts:
            v=self.svc.rule_candidates(context,domain='missing_person',method='shenqi_missing_reference_v1')
            self.assertEqual(v['candidate_count'],9);self.assertFalse(v['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in v['candidates']),expected)
            self.assertTrue(all(c['activation_status']=='reference_only' for c in v['candidates']))

    def test_before_prediction_views_never_contain_known_outcomes(self):
        cases=self.svc.cases('missing-person')['cases']
        for c in cases:
            v=self.svc.case(c['case_id'],'before_prediction')
            self.assertFalse(v['training_export'])
            for e in v['events']:
                for r in e.get('records',[]):self.assertEqual(r['knowledge_phase'],'pre_prediction')
        self.assertNotIn('5月20日',json.dumps(self.svc.case(cases[2]['case_id'],'before_prediction'),ensure_ascii=False))
        self.assertNotIn('尸首',json.dumps(self.svc.case(cases[9]['case_id'],'before_prediction'),ensure_ascii=False))

    def test_full_case_api_and_cli_use_same_catalog_and_chart_objects(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        cases=call('/v1/cases',{'chapter_key':'missing-person'})['cases'];self.assertEqual(len(cases),10)
        for c in cases:
            for e in c['events']:
                for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':c['case_id'],'chart_id':cid})['chart_id'],cid)
        result=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','missing-person'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(len(json.loads(result.stdout)['cases']),10)

    def test_old_rows_and_raw_bytes_preserved_audit_and_idempotence(self):
        with connect(self.db) as c:
            for t,rows in self.before.items():
                now=[tuple(r) for r in c.execute('SELECT * FROM '+t)]
                self.assertTrue(all(r in now for r in rows),t)
            versions=c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        v=ingest(self.db,self.raw)
        self.assertTrue(v['cases']['duplicate']);self.assertTrue(v['candidates']['duplicate'])
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],versions)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rules').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0],0)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_rewrite_rejected_and_snapshot_roundtrip_exact(self):
        changed=copy.deepcopy(self.artifact);changed['cases'][0]['title']='changed'
        with self.assertRaises(ImportConflict):import_cases(self.db,self.result['source']['revision_id'],changed)
        first=self.path/'snapshot';again=self.path/'again';db=self.path/'roundtrip.sqlite3';raw=self.path/'roundtrip_raw'
        export_snapshot(self.db,self.raw,first);restore_snapshot(first,db,raw);export_snapshot(db,raw,again)
        self.assertEqual({str(p.relative_to(first)):p.read_bytes() for p in first.rglob('*') if p.is_file()},
            {str(p.relative_to(again)):p.read_bytes() for p in again.rglob('*') if p.is_file()})
