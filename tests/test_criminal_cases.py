"""Historical criminal-case source fidelity; no investigative or predictive efficacy claim."""
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
from qimenllm.knowledge.db import APPEND_ONLY,connect,digest
from qimenllm.knowledge.importer import ImportConflict
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.criminal import CRIMINAL_SHA
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_criminal import ingest


class CriminalCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'criminal.sqlite3';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY}
        cls.result=ingest(cls.db,cls.raw)
        d=ROOT/'data/structured/shenqi'
        cls.artifact=json.loads((d/'criminal_cases.json').read_bytes())
        cls.curated=json.loads((d/'criminal_curated.json').read_bytes())
        cls.gold=json.loads((d/'criminal_gold.json').read_bytes())['charts']
        cls.candidates=json.loads((d/'criminal_rule_candidates.json').read_bytes())
        cls.source=(ROOT/'data/provenance/uploads'/f'{CRIMINAL_SHA}.utf8').read_bytes()
        cls.svc=QimenService(cls.db);cls.catalog=cls.svc.cases('criminal-cases')['cases']

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def record(self,case,line):return next(r for r in self.artifact['cases'][case-1]['events'][0]['records'] if r['source_lines']==[line,line])

    def test_source_bytes_and_every_quote_and_statement_span(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(CRIMINAL_SHA,37260,261))
        def walk(v):
            if isinstance(v,dict):
                if 'source_sha256' in v:self.assertEqual(v['source_sha256'],CRIMINAL_SHA)
                if {'byte_start','byte_end'}<=v.keys():
                    t=v.get('source_quote',v.get('text'));self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),t)
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(self.artifact);walk(self.curated)
        for c in self.candidates['candidates']:
            n=c['source_lines'][0];self.assertEqual(c['source_quote'],self.source.decode().splitlines()[n-1])

    def test_all_five_whole_narratives_and_six_original_charts(self):
        self.assertEqual(len(self.catalog),5);self.assertEqual(len(self.artifact['cases']),5)
        lines=self.source.decode().splitlines()
        for i,c in enumerate(self.artifact['cases']):
            a,b=c['source_ranges'][0];self.assertEqual(c['title'],lines[a-1])
            self.assertEqual(len(c['events']),1)
            if i:self.assertEqual(self.artifact['cases'][i-1]['source_ranges'][0][1]+1,a)
        self.assertEqual([len(c['events'][0]['charts']) for c in self.artifact['cases']],[1,1,1,2,1])

    def test_all_54_artifact_cells_against_independent_gold(self):
        charts={ch['chart_key']:ch for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        self.assertEqual(set(charts),set(self.gold))
        for key,ch in charts.items():self.assertEqual([r['cells'] for r in ch['payload']['source_table_rows']],self.gold[key])

    def test_service_projects_same_ids_and_all_54_literal_cells(self):
        expected={ch['source_lines'][0]+1:self.gold[ch['chart_key']] for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        n=0
        for c in self.catalog:
            for e in c['events']:
                for cid in e['chart_ids']:
                    p=self.svc.case_chart(c['case_id'],cid);self.assertEqual((p['status'],p['chart_id']),('projected',cid))
                    self.assertFalse(p['engine_verified']);self.assertFalse(p['original_chart_modified'])
                    first=min(v['source']['line'] for v in p['palaces'].values())
                    for palace,cells in zip((4,9,2,3,5,7,8,1,6),expected[first]):
                        self.assertEqual(p['palaces'][str(palace)]['source']['column_cells'],cells)
                    n+=1
        self.assertEqual(n,6)

    def test_bank_zhirun_original_and_chaibu_posthoc_methods_do_not_merge(self):
        e=self.artifact['cases'][3]['events'][0];a,b=e['charts']
        self.assertEqual(a['payload']['source_chart_metadata']['method_as_written'],'置闰法')
        self.assertEqual(b['payload']['source_chart_metadata']['method_as_written'],'拆补法')
        self.assertIn('阳3局',a['payload']['source_chart_metadata']['casting_description'])
        self.assertIn('阳2局',b['payload']['source_chart_metadata']['casting_description'])
        self.assertEqual(b['payload']['source_presentation_stage'],'post_feedback')
        self.assertFalse(b['payload']['calendar_recomputed'])
        self.assertNotEqual(a['chart_key'],b['chart_key'])

    def test_bank_missed_initial_dates_and_retrospective_september_explanation(self):
        initial=self.record(4,183);later=self.record(4,187)
        self.assertEqual(initial['knowledge_phase'],'prediction');self.assertIn('6月24日',initial['text']);self.assertIn('7月4日',initial['text'])
        self.assertEqual(later['knowledge_phase'],'post_feedback');self.assertTrue(later['payload']['not_predicted_at_time'])
        self.assertIn('当时没有看出',later['text']);self.assertIn('9月9日',self.record(4,185)['text'])
        for line in (189,191,209,211,213,215,217,219,223):self.assertEqual(self.record(4,line)['knowledge_phase'],'post_feedback')

    def test_serial_crimes_remain_one_family_without_fabricated_charts(self):
        e=self.artifact['cases'][3]['events'][0]
        self.assertEqual(len(e['charts']),2)
        t=self.record(4,185)['text']
        for date in ('2月8日','6月3日','8月27日','9月2日'):self.assertIn(date,t)
        self.assertIn('no invented',self.record(4,185)['payload']['serial_case_grouping'])
        self.assertTrue(all(r['chart_key'] in {c['chart_key'] for c in e['charts']} for r in e['records']))

    def test_posthoc_method_opinion_has_both_source_charts_and_no_validation_claim(self):
        e=self.artifact['cases'][3]['events'][0];r=self.record(4,223)
        self.assertEqual(set(r['payload']['related_chart_keys']),{ch['chart_key'] for ch in e['charts']})
        self.assertTrue(r['payload']['source_opinion_not_engine_validation'])
        self.assertEqual(r['speaker'],'张志春（按语）')
        self.assertEqual(len(e['evidence_links']),2)

    def test_clothing_loss_amount_and_preexisting_arrests_revealed_in_order(self):
        self.assertEqual(self.record(2,101)['knowledge_phase'],'prediction')
        self.assertEqual(self.record(2,103)['speaker'],'女老板');self.assertIn('一万七千',self.record(2,103)['text'])
        self.assertEqual(self.record(2,105)['knowledge_phase'],'post_feedback')
        self.assertEqual(self.record(2,107)['kind'],'feedback');self.assertIn('现在是抓住两个',self.record(2,107)['text'])
        out=self.record(2,111);self.assertEqual(out['kind'],'outcome');self.assertTrue(out['payload']['not_original_stolen_amount'])
        self.assertIn('近八千',out['text'])

    def test_capture_forecast_and_reported_shooting_are_distinct(self):
        self.assertIn('可望抓获',self.record(3,144)['text'])
        out=self.record(3,146);self.assertEqual(out['knowledge_phase'],'post_feedback')
        self.assertEqual(out['payload']['resolution_as_written'],'shot_dead_not_live_capture')
        self.assertEqual([s['record_role'] for s in out['payload']['source_statement_segments']],['reported_shooting_outcome','retrospective_timing_explanation'])

    def test_unresolved_case_is_as_of_source_not_all_claims_confirmed(self):
        r=self.record(5,259);self.assertEqual(r['kind'],'outcome')
        self.assertIn('not confirmation of every',r['payload']['confirmation_scope'])
        self.assertEqual(r['payload']['outcome_time_scope'],'Unresolved as of original narration only')
        self.assertEqual(self.record(5,261)['speaker'],'张志春（按语）')
        self.assertIn('更不能作为破案的依据和证据',self.source.decode())

    def test_native_center_star_and_prefixes_and_source_typos_unchanged(self):
        c=self.catalog[3]
        projections=[self.svc.case_chart(c['case_id'],cid) for cid in c['events'][0]['chart_ids']]
        p=next(p for p in projections if p['palaces']['5']['earth_stem']=='庚')
        self.assertEqual(p['palaces']['7']['star'],'天禽星')
        self.assertEqual(p['palaces']['7']['source']['column_cells'][-1],'禽壬')
        self.assertEqual(p['palaces']['2']['star_prefix_marker'],'庚')
        self.assertEqual(p['palaces']['7']['heaven_prefix_marker'],'乙')
        self.assertIn('己已',self.record(4,189)['text']);self.assertIn('妍头',self.record(4,215)['text'])

    def test_eleven_candidates_require_scope_and_never_bind(self):
        for context,expected in [({},0),({'domain':'criminal_cases','offense_scope':'theft_sexual_assault_or_minor_economic','method_scope':'shenqi_criminal_roles_reference_v1'},1),({'domain':'criminal_cases','offense_scope':'violent_robbery_homicide_or_major_economic','method_scope':'shenqi_criminal_roles_reference_v1'},1)]:
            r=self.svc.rule_candidates(context,domain='criminal_cases',method='shenqi_criminal_reference_v1')
            self.assertEqual(r['candidate_count'],11);self.assertFalse(r['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),expected)
            self.assertTrue(all(c['activation_status']=='reference_only' for c in r['candidates']))

    def test_initial_view_withholds_posthoc_method_and_final_outcomes(self):
        for c in self.catalog:
            v=self.svc.case(c['case_id'],'before_prediction');self.assertFalse(v['training_export'])
            for e in v['events']:
                for r in e.get('records',[]):self.assertEqual(r['knowledge_phase'],'pre_prediction')
        v=json.dumps(self.svc.case(self.catalog[3]['case_id'],'before_prediction'),ensure_ascii=False)
        self.assertNotIn('9月9日',v);self.assertNotIn('拆补',v);self.assertNotIn('阳2局',v)

    def test_existing_api_cli_and_append_only_replay(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        for c in call('/v1/cases',{'chapter_key':'criminal-cases'})['cases']:
            for e in c['events']:
                for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':c['case_id'],'chart_id':cid})['chart_id'],cid)
        r=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','criminal-cases'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(len(json.loads(r.stdout)['cases']),5)
        with connect(self.db) as c:
            for t,old in self.before.items():
                current=[tuple(r) for r in c.execute('SELECT * FROM '+t)]
                self.assertTrue(all(row in current for row in old),t)
            n=c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        r=ingest(self.db,self.raw);self.assertTrue(r['cases']['duplicate']);self.assertTrue(r['candidates']['duplicate'])
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],n)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rules').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0],0)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_immutable_rewrite_rejected_and_snapshot_restores_exactly(self):
        bad=copy.deepcopy(self.artifact);bad['cases'][0]['title']='changed'
        with self.assertRaises(ImportConflict):import_cases(self.db,self.result['source']['revision_id'],bad)
        first=self.path/'snapshot';again=self.path/'again';db=self.path/'roundtrip.sqlite3';raw=self.path/'roundtrip_raw'
        export_snapshot(self.db,self.raw,first);restore_snapshot(first,db,raw);export_snapshot(db,raw,again)
        self.assertEqual({str(p.relative_to(first)):p.read_bytes() for p in first.rglob('*') if p.is_file()},
            {str(p.relative_to(again)):p.read_bytes() for p in again.rglob('*') if p.is_file()})
