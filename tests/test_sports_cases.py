"""Historical sports source fidelity and chronology; no professional efficacy claim."""
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
from qimenllm.knowledge.sports import SPORTS_SHA
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_sports import ingest


class SportsCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'sports.sqlite3';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY}
        cls.result=ingest(cls.db,cls.raw)
        d=ROOT/'data/structured/shenqi'
        cls.artifact=json.loads((d/'sports_cases.json').read_bytes())
        cls.curated=json.loads((d/'sports_curated.json').read_bytes())
        cls.gold=json.loads((d/'sports_gold.json').read_bytes())['charts']
        cls.candidates=json.loads((d/'sports_rule_candidates.json').read_bytes())
        cls.source=(ROOT/'data/provenance/uploads'/f'{SPORTS_SHA}.utf8').read_bytes()
        cls.svc=QimenService(cls.db);cls.catalog=cls.svc.cases('sports-competition')['cases']

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def record(self,case,line):return next(r for r in self.artifact['cases'][case-1]['events'][0]['records'] if r['source_lines']==[line,line])

    def test_source_bytes_and_every_quote_and_statement_span(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(SPORTS_SHA,26814,276))
        def walk(v):
            if isinstance(v,dict):
                if 'source_sha256' in v:self.assertEqual(v['source_sha256'],SPORTS_SHA)
                if {'byte_start','byte_end'}<=v.keys():
                    t=v.get('source_quote',v.get('text'));self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),t)
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(self.artifact);walk(self.curated)
        for c in self.candidates['candidates']:
            a,b=min(c['source_lines']),max(c['source_lines']);self.assertEqual(c['source_quote'],''.join(self.source.decode().splitlines(keepends=True)[a-1:b]).rstrip('\r\n'))

    def test_all_seven_whole_narratives_and_seven_original_charts(self):
        self.assertEqual(len(self.catalog),7);self.assertEqual(len(self.artifact['cases']),7)
        lines=self.source.decode().splitlines()
        for i,c in enumerate(self.artifact['cases']):
            a,b=c['source_ranges'][0];self.assertEqual(c['title'],lines[a-1])
            self.assertEqual(len(c['events']),1)
            if i:self.assertEqual(self.artifact['cases'][i-1]['source_ranges'][0][1]+1,a)
        self.assertEqual([len(c['events'][0]['charts']) for c in self.artifact['cases']],[1,1,1,1,1,1,1])

    def test_all_63_artifact_cells_against_independent_gold(self):
        charts={ch['chart_key']:ch for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        self.assertEqual(set(charts),set(self.gold))
        for key,ch in charts.items():self.assertEqual([r['cells'] for r in ch['payload']['source_table_rows']],self.gold[key])

    def test_service_projects_same_ids_and_all_63_literal_cells(self):
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
        self.assertEqual(n,7)

    def test_case1_explicit_team_roles_and_gold_medal_forecast(self):
        self.assertIn('地盘时干壬',self.record(1,38)['text'])
        self.assertIn('天盘时干壬',self.record(1,40)['text'])
        self.assertIn('辛为金牌',self.record(1,42)['text'])
        self.assertEqual(self.record(1,44)['knowledge_phase'],'prediction')
        self.assertIn('3:0',self.record(1,46)['text'])

    def test_case2_jiaxu_text_only_and_yihai_grid_not_conflated(self):
        e=self.artifact['cases'][1]['events'][0];self.assertEqual(len(e['charts']),1)
        for n in (54,56):
            r=self.record(2,n);self.assertIsNone(r['chart_key'])
            self.assertTrue(r['payload']['full_nine_palace_chart_not_provided'])
        self.assertIn('星、门俱伏吟',self.record(2,54)['text'])
        self.assertEqual(self.record(2,56)['kind'],'timing')
        self.assertIn('9点以前',self.record(2,56)['text'])
        self.assertIn('乙亥时',e['charts'][0]['payload']['source_chart_metadata']['casting_description'])
        self.assertEqual(self.record(2,58)['chart_key'],e['charts'][0]['chart_key'])
        for t in ('2:2','9点50分','3:2'):self.assertIn(t,self.record(2,87)['text'])

    def test_case3_sequential_number_door_star_attempts_and_rejections(self):
        self.assertIn('113',self.record(3,95)['text']);self.assertIn('114',self.record(3,95)['text'])
        for n,m in [(114,'jersey_number_earth_palaces_3_4'),(118,'jersey_number_doors_3_4'),(126,'jersey_number_stars_3_4')]:
            self.assertEqual(self.record(3,n)['payload']['method_attempt'],m)
            self.assertEqual(self.record(3,n)['knowledge_phase'],'prediction')
        self.assertIn('仍不分胜负',self.record(3,118)['text'])
        self.assertIn('胜负也不明显',self.record(3,124)['text'])
        self.assertIn('我突然想到',self.record(3,126)['text'])
        self.assertIn('孔令辉会胜',self.record(3,132)['text'])

    def test_case4_two_forecast_count_alternatives_not_retrofitted(self):
        r=self.record(4,163);self.assertEqual(r['payload']['count_alternatives_as_written'],[10,16])
        self.assertTrue(r['payload']['not_unique_point_forecast']);self.assertEqual(r['knowledge_phase'],'prediction')
        self.assertIn('十枚或十六枚',r['text']);self.assertIn('十六枚',self.record(4,165)['text'])

    def test_case5_neutral_venue_roles_and_stage_specific_score(self):
        self.assertIn('巴西为客队',self.record(5,194)['text'])
        self.assertIn('荷兰',self.record(5,194)['text'])
        self.assertEqual(self.record(5,200)['knowledge_phase'],'prediction')
        r=self.record(5,202);self.assertEqual(r['knowledge_phase'],'post_feedback')
        stages=r['payload']['reported_score_stages_as_written']
        self.assertEqual([s['score'] for s in stages],['1:1','1:1','5:3'])
        self.assertTrue(r['payload']['not_regulation_time_5_3'])

    def test_case6_wrong_winner_preserved_despite_same_score_literal(self):
        r=self.record(6,235);self.assertEqual(r['knowledge_phase'],'prediction')
        self.assertIn('克罗地亚胜',r['text']);self.assertIn('2:1',r['text'])
        later=self.record(6,237);self.assertEqual(later['knowledge_phase'],'post_feedback')
        self.assertEqual(later['payload']['winner_comparison'],{'predicted':'克罗地亚','reported':'法国','same_winner':False,'score_literal_both':'2:1'})
        self.assertTrue(later['payload']['posthoc_not_original_reasoning'])
        self.assertNotIn('没看月令',r['text'])

    def test_case6_outcome_and_posthoc_explanation_have_exact_byte_segments(self):
        r=self.record(6,237);segments=r['payload']['source_statement_segments']
        self.assertEqual(''.join(s['text'] for s in segments),r['text'])
        self.assertEqual([s['knowledge_phase'] for s in segments],['post_feedback','post_feedback'])
        self.assertIn('法国队胜',segments[0]['text']);self.assertTrue(segments[1]['text'].startswith('事后检查此局'))
        self.assertIn('没看月令',segments[1]['text'])

    def test_case7_all_six_steps_and_final_3_0(self):
        r=self.record(7,274);self.assertEqual(r['payload']['original_step_number'],'6')
        self.assertTrue(r['text'].startswith('⑥'));self.assertEqual(r['knowledge_phase'],'prediction')
        self.assertIn('3:0',self.record(7,272)['text']);self.assertIn('3:0',self.record(7,276)['text'])
        self.assertEqual(self.record(7,276)['knowledge_phase'],'post_feedback')

    def test_unmapped_source_star_literal_is_never_silently_corrected(self):
        c=self.catalog[4];p=self.svc.case_chart(c['case_id'],c['events'][0]['chart_ids'][0])
        cell=p['palaces']['9'];self.assertIsNone(cell['star']);self.assertEqual(cell['earth_stem'],'庚')
        self.assertEqual(cell['source_star_cell_as_written'],'铺庚')
        self.assertEqual(cell['unmapped_star_abbreviation'],'铺')
        self.assertFalse(p['source_symbol_mapping_complete'])
        self.assertEqual(p['unmapped_source_cells'],[{'palace':9,'field':'star','source_literal':'铺庚','canonical_star':None}])
        self.assertFalse(p['original_chart_modified']);self.assertIn('星位：铺庚',cell['source']['text'])
        c=self.catalog[5];p=self.svc.case_chart(c['case_id'],c['events'][0]['chart_ids'][0])
        self.assertTrue(p['source_symbol_mapping_complete']);self.assertEqual(p['palaces']['2']['star'],'天辅星')

    def test_source_printed_chapter_and_literal_prefixes(self):
        self.assertEqual(self.curated['printed_chapter_number'],12)
        self.assertTrue(self.source.decode().startswith('第十二章'))
        c=self.catalog[2];p=self.svc.case_chart(c['case_id'],c['events'][0]['chart_ids'][0])
        self.assertEqual(p['palaces']['2']['star_prefix_marker'],'丙')
        self.assertEqual(p['palaces']['1']['heaven_prefix_marker'],'丙')
        self.assertIn('以应地盘',self.record(6,229)['text'])

    def test_four_candidates_condition_scope_unknown_and_non_activation(self):
        for context,expected in [({},0),({'domain':'sports_competition','sports_subtype':'general_roles','method_scope':'shenqi_sports_general_roles_reference_v1'},1),({'domain':'sports_competition','sports_subtype':'same_country_jersey_methods','method_scope':'shenqi_sports_same_country_jersey_methods_reference_v1'},1)]:
            r=self.svc.rule_candidates(context,domain='sports_competition',method='shenqi_sports_reference_v1')
            self.assertEqual(r['candidate_count'],4);self.assertFalse(r['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),expected)
            self.assertTrue(all(c['activation_status']=='reference_only' for c in r['candidates']))

    def test_initial_view_withholds_outcomes_and_posthoc_month_explanation(self):
        for c in self.catalog:
            v=self.svc.case(c['case_id'],'before_prediction');self.assertFalse(v['training_export'])
            for e in v['events']:
                for r in e.get('records',[]):self.assertEqual(r['knowledge_phase'],'pre_prediction')
        v=json.dumps(self.svc.case(self.catalog[5]['case_id'],'before_prediction'),ensure_ascii=False)
        for t in ('事后检查','没看月令','比分确为2:1'):self.assertNotIn(t,v)
        v=json.dumps(self.svc.case(self.catalog[1]['case_id'],'before_prediction'),ensure_ascii=False)
        for t in ('乙亥时','9点50分','3:2'):self.assertNotIn(t,v)

    def test_existing_api_cli_and_append_only_replay(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        for c in call('/v1/cases',{'chapter_key':'sports-competition'})['cases']:
            for e in c['events']:
                for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':c['case_id'],'chart_id':cid})['chart_id'],cid)
        r=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','sports-competition'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(len(json.loads(r.stdout)['cases']),7)
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
