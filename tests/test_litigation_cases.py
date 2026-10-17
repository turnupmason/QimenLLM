"""Historical litigation source fidelity and chronology; no professional efficacy claim."""
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
from qimenllm.knowledge.litigation import LITIGATION_SHA
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_litigation import ingest


class LitigationCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'litigation.sqlite3';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY}
        cls.result=ingest(cls.db,cls.raw)
        d=ROOT/'data/structured/shenqi'
        cls.artifact=json.loads((d/'litigation_cases.json').read_bytes())
        cls.curated=json.loads((d/'litigation_curated.json').read_bytes())
        cls.gold=json.loads((d/'litigation_gold.json').read_bytes())['charts']
        cls.candidates=json.loads((d/'litigation_rule_candidates.json').read_bytes())
        cls.source=(ROOT/'data/provenance/uploads'/f'{LITIGATION_SHA}.utf8').read_bytes()
        cls.svc=QimenService(cls.db);cls.catalog=cls.svc.cases('litigation')['cases']

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def record(self,case,line):return next(r for r in self.artifact['cases'][case-1]['events'][0]['records'] if r['source_lines']==[line,line])

    def test_source_bytes_and_every_quote_and_statement_span(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(LITIGATION_SHA,30547,267))
        def walk(v):
            if isinstance(v,dict):
                if 'source_sha256' in v:self.assertEqual(v['source_sha256'],LITIGATION_SHA)
                if {'byte_start','byte_end'}<=v.keys():
                    t=v.get('source_quote',v.get('text'));self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),t)
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(self.artifact);walk(self.curated)
        for c in self.candidates['candidates']:
            n=c['source_lines'][0];self.assertEqual(c['source_quote'],self.source.decode().splitlines()[n-1])

    def test_all_six_whole_narratives_and_six_original_charts(self):
        self.assertEqual(len(self.catalog),6);self.assertEqual(len(self.artifact['cases']),6)
        lines=self.source.decode().splitlines()
        for i,c in enumerate(self.artifact['cases']):
            a,b=c['source_ranges'][0];self.assertEqual(c['title'],lines[a-1])
            self.assertEqual(len(c['events']),1)
            if i:self.assertEqual(self.artifact['cases'][i-1]['source_ranges'][0][1]+1,a)
        self.assertEqual([len(c['events'][0]['charts']) for c in self.artifact['cases']],[1,1,1,1,1,1])

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

    def test_case1_chronology_and_six_line_method_not_mixed(self):
        self.assertIn('六爻',self.record(1,23)['text'])
        self.assertEqual(len(self.artifact['cases'][0]['events'][0]['charts']),1)
        self.assertEqual(self.record(1,54)['kind'],'timing')
        self.assertEqual(self.record(1,58)['knowledge_phase'],'post_feedback')
        self.assertIn('己亥日',self.record(1,58)['text'])

    def test_case2_roles_money_and_bail_not_no_offense(self):
        self.assertIn('月干戊',self.record(2,83)['text'])
        self.assertIn('甲午辛',self.record(2,85)['text'])
        self.assertIn('二万或二万五千元',self.record(2,87)['text'])
        self.assertIn('两万五千元',self.record(2,91)['text'])
        self.assertIn('保释',self.record(2,91)['text'])

    def test_case3_prior_queries_and_cost_components_remain_one_event(self):
        e=self.artifact['cases'][2]['events'][0]
        self.assertEqual(len(e['charts']),1);self.assertEqual(self.record(3,95)['knowledge_phase'],'unknown')
        self.assertEqual(self.record(3,130)['knowledge_phase'],'prediction')
        self.assertIn('5点半',self.record(3,130)['text'])
        for t in ('十六万元','六千元','十七万元','搬走'):self.assertIn(t,self.record(3,132)['text'])

    def test_case4_conditional_forecast_and_civil_criminal_results_distinct(self):
        self.assertIn('就可能判缓刑',self.record(4,171)['text'])
        self.assertEqual(self.record(4,173)['kind'],'outcome')
        self.assertIn('二万元',self.record(4,173)['text'])
        for t in ('一万元','各出五千元'):self.assertIn(t,self.record(4,175)['text'])
        self.assertIn('判刑二年，缓期三年执行',self.record(4,177)['text'])

    def test_case5_initial_forecast_feedback_and_continuation_order(self):
        self.assertEqual(self.record(5,210)['knowledge_phase'],'prediction')
        f=self.record(5,212);self.assertEqual((f['kind'],f['knowledge_phase']),('feedback','post_feedback'))
        self.assertIn('二万二千',f['text']);self.assertIn('带着伤',f['text'])
        for n in (214,216):
            r=self.record(5,n);self.assertEqual(r['knowledge_phase'],'post_feedback')
            self.assertEqual(r['payload']['known_feedback_record_keys'],['litigation-case-05-line-212'])
        self.assertLess(f['sequence'],self.record(5,214)['sequence'])

    def test_case5_author_critique_never_rewrites_original_method(self):
        self.assertIn('乙奇为被告',self.record(5,214)['text'])
        for n in (220,222):
            r=self.record(5,n);self.assertEqual((r['speaker'],r['knowledge_phase']),('张志春（按语）','post_feedback'))
            self.assertTrue(r['payload']['original_method_not_rewritten'])
            self.assertTrue(r['payload']['source_opinion_not_engine_validation'])
        self.assertIn('显然不对',self.record(5,220)['text'])
        self.assertIn('地盘之星为天乙',self.record(5,222)['text'])

    def test_case6_mixed_paragraphs_keep_exact_segments_and_late_facts(self):
        for n,phases in [(228,['pre_prediction','prediction']),(232,['post_feedback','post_feedback'])]:
            r=self.record(6,n);segments=r['payload']['source_statement_segments']
            self.assertEqual([s['knowledge_phase'] for s in segments],phases)
            self.assertEqual(''.join(s['text'] for s in segments),r['text'])
        self.assertEqual(self.record(6,230)['knowledge_phase'],'post_feedback')
        self.assertIn('1996年7月24日',self.record(6,230)['text'])
        self.assertIn('见好就收',self.record(6,232)['payload']['source_statement_segments'][1]['text'])
        self.assertIn('12月27号',self.record(6,238)['text'])

    def test_case6_late_printed_chart_same_historical_inquiry(self):
        e=self.artifact['cases'][5]['events'][0];self.assertEqual(len(e['charts']),1)
        p=e['charts'][0]['payload'];self.assertEqual(p['source_presentation_stage'],'post_feedback')
        self.assertIn('阴9局',p['source_chart_metadata']['casting_description'])
        self.assertFalse(p['calendar_recomputed'])
        for n in (240,242,261,265,267):
            r=self.record(6,n);self.assertEqual(r['knowledge_phase'],'post_feedback')
            self.assertTrue(r['payload']['presentation_order_does_not_establish_prior_recording'])

    def test_literal_native_center_and_double_prefixes_preserved(self):
        c=self.catalog[4];cid=c['events'][0]['chart_ids'][0];p=self.svc.case_chart(c['case_id'],cid)
        self.assertEqual(p['palaces']['5']['earth_stem'],'戊')
        self.assertEqual(p['palaces']['2']['heaven_prefix_marker'],'戊')
        self.assertEqual(p['palaces']['2']['star_prefix_marker'],'戊')
        self.assertIn('离.9宫',self.record(1,48)['text'])
        self.assertIn('震3官',self.record(6,263)['text'])

    def test_six_candidates_require_scope_and_never_bind(self):
        for context,expected in [({},0),({'domain':'litigation','litigation_subtype':'roles','method_scope':'shenqi_litigation_roles_reference_v1'},1)]:
            r=self.svc.rule_candidates(context,domain='litigation',method='shenqi_litigation_reference_v1')
            self.assertEqual(r['candidate_count'],6);self.assertFalse(r['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),expected)
            self.assertTrue(all(c['activation_status']=='reference_only' for c in r['candidates']))

    def test_initial_view_withholds_later_feedback_and_author_comments(self):
        for c in self.catalog:
            v=self.svc.case(c['case_id'],'before_prediction');self.assertFalse(v['training_export'])
            for e in v['events']:
                for r in e.get('records',[]):self.assertEqual(r['knowledge_phase'],'pre_prediction')
        v=json.dumps(self.svc.case(self.catalog[4]['case_id'],'before_prediction'),ensure_ascii=False)
        self.assertNotIn('二万二千',v);self.assertNotIn('显然不对',v)
        v=json.dumps(self.svc.case(self.catalog[5]['case_id'],'before_prediction'),ensure_ascii=False)
        for t in ('1996年7月24日','12月27号','阴9局','厂长气得很'):self.assertNotIn(t,v)

    def test_existing_api_cli_and_append_only_replay(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        for c in call('/v1/cases',{'chapter_key':'litigation'})['cases']:
            for e in c['events']:
                for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':c['case_id'],'chart_id':cid})['chart_id'],cid)
        r=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','litigation'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(len(json.loads(r.stdout)['cases']),6)
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
