"""Historical life source fidelity and chronology; no professional efficacy claim."""
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
from qimenllm.knowledge.life import LIFE_SHA
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_life import ingest


class LifeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'life.sqlite3';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY}
        cls.result=ingest(cls.db,cls.raw)
        d=ROOT/'data/structured/shenqi'
        cls.artifact=json.loads((d/'life_cases.json').read_bytes())
        cls.curated=json.loads((d/'life_curated.json').read_bytes())
        cls.gold=json.loads((d/'life_gold.json').read_bytes())['charts']
        cls.candidates=json.loads((d/'life_rule_candidates.json').read_bytes())
        cls.source=(ROOT/'data/provenance/uploads'/f'{LIFE_SHA}.utf8').read_bytes()
        cls.svc=QimenService(cls.db);cls.catalog=cls.svc.cases('life-opportunities')['cases']

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def record(self,case,line):return next(r for r in self.artifact['cases'][case-1]['events'][0]['records'] if r['source_lines']==[line,line])

    def test_source_bytes_and_every_quote_and_statement_span(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(LIFE_SHA,37761,273))
        def walk(v):
            if isinstance(v,dict):
                if 'source_sha256' in v:self.assertEqual(v['source_sha256'],LIFE_SHA)
                if {'byte_start','byte_end'}<=v.keys():
                    t=v.get('source_quote',v.get('text'));self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),t)
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(self.artifact);walk(self.curated)
        for c in self.candidates['candidates']:
            a,b=min(c['source_lines']),max(c['source_lines']);self.assertEqual(c['source_quote'],''.join(self.source.decode().splitlines(keepends=True)[a-1:b]).rstrip('\r\n'))

    def test_all_five_whole_narratives_and_five_original_charts(self):
        self.assertEqual(len(self.catalog),5);self.assertEqual(len(self.artifact['cases']),5)
        lines=self.source.decode().splitlines()
        for i,c in enumerate(self.artifact['cases']):
            a,b=c['source_ranges'][0];self.assertEqual(c['title'],lines[a-1])
            self.assertEqual(len(c['events']),1)
            if i:self.assertEqual(self.artifact['cases'][i-1]['source_ranges'][0][1]+1,a)
        self.assertEqual([len(c['events'][0]['charts']) for c in self.artifact['cases']],[1,1,1,1,1])

    def test_all_45_artifact_cells_against_independent_gold(self):
        charts={ch['chart_key']:ch for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        self.assertEqual(set(charts),set(self.gold))
        for key,ch in charts.items():self.assertEqual([r['cells'] for r in ch['payload']['source_table_rows']],self.gold[key])

    def test_service_projects_same_ids_and_all_45_literal_cells(self):
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
        self.assertEqual(n,5)

    def test_birth_and_inquiry_chart_bases_and_relation_scopes(self):
        charts=[c['events'][0]['charts'][0]['payload'] for c in self.artifact['cases']]
        self.assertEqual([p['source_chart_metadata']['casting_basis_as_written'] for p in charts],['inquiry_time']*3+['birth_time']*2)
        self.assertIn('1986年十一月十五日',charts[3]['source_chart_metadata']['birth_time_as_written'])
        self.assertIn('阳历时间：1942年1月13日早晨5点多',charts[4]['source_chart_metadata']['birth_time_as_written'])
        self.assertTrue(all(not p['calendar_recomputed'] for p in charts))
        self.assertEqual(self.curated['printed_chapter_number'],16)

    def test_quoted_verse_preserved_whole_with_authors_caution(self):
        c=next(c for c in self.candidates['candidates'] if c['key']=='life_quoted_verse_with_caution')
        for t in ('奇门遁甲秘笈大全','只可参考，不能拘泥','片面性、绝对性很大','全盘分析'):self.assertIn(t,c['source_quote'])
        g=next(g for g in self.curated['groups'] if g['key']=='life_quoted_verse_with_caution')
        self.assertEqual((g['line_start'],g['line_end']),(12,25))
        with connect(self.db) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM books').fetchone()[0],1)

    def test_case1_feedback_revealed_in_rounds_not_initial_input(self):
        self.assertEqual(self.record(1,54)['knowledge_phase'],'prediction')
        self.assertEqual(self.record(1,55)['kind'],'feedback');self.assertIn('宣传部副部长',self.record(1,55)['text'])
        for forecast,known in [(57,55),(60,58),(66,64),(79,77)]:
            r=self.record(1,forecast);self.assertEqual(r['knowledge_phase'],'post_feedback')
            self.assertIn(f'life-case-01-line-{known}',r['payload']['known_feedback_record_keys'])
        self.assertIn('县委书记已上党校一年',self.record(1,80)['text'])
        self.assertIn('future reassignment',self.record(1,80)['payload']['confirmation_scope'])

    def test_case1_sibling_approximation_and_actual_counts_not_rewritten(self):
        self.assertIn('6个左右',self.record(1,68)['text'])
        self.assertIn('七个，伤了二人，现在还有五个',self.record(1,69)['text'])
        self.assertIn('结合计划生育政策和洪先生年龄',self.record(1,73)['text'])
        self.assertIn('有一个女孩有病',self.record(1,74)['text'])

    def test_case2_principal_already_recovered_and_party_role_first_revealed(self):
        self.assertEqual(self.record(2,118)['payload']['party_role_first_revealed_here'],'原告')
        self.assertIn('life-case-02-line-118',self.record(2,120)['payload']['known_feedback_record_keys'])
        self.assertIn('本钱可能能追回',self.record(2,125)['text'])
        r=self.record(2,126);self.assertEqual(r['kind'],'feedback')
        self.assertEqual(r['payload']['money_as_written'],{'principal_recovered':90000,'interest_not_recovered':'二十多万元','recovery_status':'already_recovered_when_revealed_not_new_future_event'})
        self.assertIn('九万元本钱已追回',r['text'])
        self.assertIn('life-case-02-line-126',self.record(2,128)['payload']['known_feedback_record_keys'])

    def test_case2_planned_travel_and_unconfirmed_future_are_not_outcomes(self):
        self.assertIn('亥月、日',self.record(2,138)['text'])
        self.assertEqual(self.record(2,139)['payload']['departure_status'],'plan_only_as_revealed_not_actual_departure_confirmation')
        for n in (140,156):self.assertEqual(self.record(2,n)['kind'],'prediction')
        self.assertTrue(self.record(2,154)['payload']['new_question_not_confirmation_of_previous_target'])
        self.assertIn('no year-end survival',self.record(2,110)['payload']['confirmation_scope'])
        self.assertIn('戌、亥月',self.record(2,156)['text'])
        self.assertEqual(len(self.artifact['cases'][1]['events']),1)

    def test_case2_literal_verse_chart_and_analysis_discrepancies_not_fixed(self):
        self.assertIn('临天禽吉星',self.record(2,108)['text']);self.assertIn('年干癸',self.record(2,150)['text'])
        c=self.catalog[1];p=self.svc.case_chart(c['case_id'],c['events'][0]['chart_ids'][0])
        self.assertEqual(p['palaces']['1']['source']['column_cells'][-1],'芮丙')
        self.assertEqual(p['palaces']['1']['star'],'天芮星');self.assertEqual(p['palaces']['1']['heaven_prefix_marker'],'辛')

    def test_case3_month_windows_and_posthoc_day_explanation_separate(self):
        r=self.record(3,188);self.assertEqual(r['payload']['timing_windows_as_written'],['农历正月','农历七月'])
        self.assertEqual(r['knowledge_phase'],'prediction');self.assertNotIn('初五',r['text'])
        self.assertEqual(self.record(3,189)['kind'],'outcome');self.assertIn('正月初五',self.record(3,189)['text'])
        for n in (190,191):self.assertEqual(self.record(3,n)['knowledge_phase'],'post_feedback')
        self.assertTrue(self.record(3,190)['payload']['not_original_day_level_forecast'])
        self.assertTrue(self.record(3,191)['payload']['counterfactual_not_observed_prevention'])

    def test_case4_entire_known_death_verification_not_prospective_prediction(self):
        c=self.artifact['cases'][3];e=c['events'][0]
        self.assertTrue(all(r['knowledge_phase']=='post_feedback' for r in e['records']))
        self.assertTrue(all(r['payload']['outcome_known_before_analysis'] for r in e['records']))
        self.assertEqual(e['charts'][0]['payload']['source_presentation_stage'],'post_feedback')
        self.assertIn('落水溺死',self.record(4,195)['text']);self.assertIn('绝不可能都在这一年被水淹死',self.record(4,221)['text'])
        v=self.svc.case(self.catalog[3]['case_id'],'before_prediction')
        self.assertTrue(all(not e.get('records') and not e.get('charts') for e in v['events']))

    def test_case5_revealed_death_wrong_year_and_posthoc_reanalysis(self):
        self.assertIn('已不幸去世',self.record(5,256)['text'])
        r=self.record(5,257);self.assertEqual(r['payload']['death_year_alternatives_as_written'],[1994,1995])
        self.assertIn('life-case-05-line-256',r['payload']['known_feedback_record_keys'])
        self.assertNotIn('life-case-05-line-258',r['payload']['known_feedback_record_keys'])
        r=self.record(5,258);self.assertEqual(r['payload']['timing_comparison'],{'predicted_years':[1994,1995],'reported_year':1996,'year_prediction_correct':False})
        self.assertIn('时间不太对',r['text'])
        self.assertTrue(self.record(5,259)['payload']['not_prior_spouse_death_reasoning'])
        self.assertIn('life-case-05-line-258',self.record(5,259)['payload']['known_feedback_record_keys'])
        self.assertTrue(self.record(5,267)['payload']['contains_previously_revealed_1996_husband_death'])

    def test_case5_marriage_alternatives_and_partial_spouse_confirmation(self):
        self.assertEqual(self.record(5,250)['payload']['marriage_year_alternatives_as_written'],[1967,1968])
        self.assertIn('1967年来中国',self.record(5,251)['text']);self.assertIn('1968年结的婚',self.record(5,251)['text'])
        self.assertIn('no explicit confirmation',self.record(5,249)['payload']['confirmation_scope'])

    def test_case5_children_alternatives_and_student_branch_not_illness_confirmation(self):
        self.assertIn('三个',self.record(5,261)['text']);self.assertIn('也可能是两个',self.record(5,261)['text'])
        self.assertIn('miscarriage not confirmed',self.record(5,262)['payload']['confirmation_scope'])
        self.assertIn('身体倒没病',self.record(5,264)['text']);self.assertIn('Eldest son not ill',self.record(5,264)['payload']['confirmation_scope'])
        self.assertEqual(self.record(5,265)['kind'],'prediction')

    def test_mixed_turns_keep_exact_byte_segments_and_roles(self):
        for case,n,roles in [(2,126,['preexisting_principal_recovery_and_unrecovered_interest','new_marriage_question']),(5,255,['client_question','author_separation_alternatives']),(5,259,['posthoc_explanation_using_revealed_birth_and_death_years','new_mother_father_comparison'])]:
            r=self.record(case,n);seg=r['payload']['source_statement_segments']
            self.assertEqual(''.join(s['text'] for s in seg),r['text'])
            self.assertEqual([s['record_role'] for s in seg],roles)
            self.assertTrue(all(s['knowledge_phase']=='post_feedback' for s in seg))

    def test_case5_future_career_and_reactions_not_outcome_confirmation(self):
        self.assertEqual(self.record(5,271)['kind'],'prediction')
        for t in ('今后5年','1999年'):self.assertIn(t,self.record(5,271)['text'])
        self.assertTrue(self.record(5,270)['payload']['reaction_not_individual_confirmation_of_prior_help_claim'])
        self.assertTrue(self.record(5,272)['payload']['learning_interest_not_future_outcome_validation'])

    def test_four_candidates_require_explicit_family_social_method_scopes(self):
        contexts=[({},0),({'domain':'life_opportunities','life_subtype':'birth_family','method_scope':'shenqi_life_birth_family_reference_v1'},0),({'domain':'life_opportunities','life_subtype':'birth_family','method_scope':'shenqi_life_birth_family_reference_v1','relationship_scope':'family'},1),({'domain':'life_opportunities','life_subtype':'birth_family','method_scope':'shenqi_life_birth_family_reference_v1','relationship_scope':'social_group'},0)]
        for context,expected in contexts:
            r=self.svc.rule_candidates(context,domain='life_opportunities',method='shenqi_life_reference_v1')
            self.assertEqual(r['candidate_count'],4);self.assertFalse(r['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),expected)
            self.assertTrue(all(c['activation_status']=='reference_only' for c in r['candidates']))

    def test_initial_view_withholds_revealed_facts_and_retrospective_analysis(self):
        for c in self.catalog:
            v=self.svc.case(c['case_id'],'before_prediction');self.assertFalse(v['training_export'])
            for e in v['events']:
                for r in e.get('records',[]):self.assertEqual(r['knowledge_phase'],'pre_prediction')
        for i,words in [(0,['宣传部副部长','已上党校一年']),(1,['九万元本钱已追回','1949年己丑年生','7月31日甲戌日']),(2,['正月初五','五天之数']),(3,['落水溺死','早夭命象']),(4,['1996年病故','医院误治','1968年结的婚'])]:
            v=json.dumps(self.svc.case(self.catalog[i]['case_id'],'before_prediction'),ensure_ascii=False)
            for word in words:self.assertNotIn(word,v)

    def test_existing_api_cli_and_append_only_replay(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        for c in call('/v1/cases',{'chapter_key':'life-opportunities'})['cases']:
            for e in c['events']:
                for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':c['case_id'],'chart_id':cid})['chart_id'],cid)
        r=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','life-opportunities'],cwd=ROOT,capture_output=True,text=True,check=True)
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
