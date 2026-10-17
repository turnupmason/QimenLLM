"""Historical weather source fidelity and chronology; no professional efficacy claim."""
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
from qimenllm.knowledge.weather import WEATHER_SHA
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_weather import ingest


class WeatherCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'weather.sqlite3';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY}
        cls.result=ingest(cls.db,cls.raw)
        d=ROOT/'data/structured/shenqi'
        cls.artifact=json.loads((d/'weather_cases.json').read_bytes())
        cls.curated=json.loads((d/'weather_curated.json').read_bytes())
        cls.gold=json.loads((d/'weather_gold.json').read_bytes())['charts']
        cls.candidates=json.loads((d/'weather_rule_candidates.json').read_bytes())
        cls.source=(ROOT/'data/provenance/uploads'/f'{WEATHER_SHA}.utf8').read_bytes()
        cls.svc=QimenService(cls.db);cls.catalog=cls.svc.cases('weather-prediction')['cases']

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def record(self,case,line):return next(r for r in self.artifact['cases'][case-1]['events'][0]['records'] if r['source_lines']==[line,line])

    def test_source_bytes_and_every_quote_and_statement_span(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(WEATHER_SHA,19857,156))
        def walk(v):
            if isinstance(v,dict):
                if 'source_sha256' in v:self.assertEqual(v['source_sha256'],WEATHER_SHA)
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

    def test_case1_mixed_forecast_outcome_exact_segments(self):
        r=self.record(1,42);self.assertEqual(r['knowledge_phase'],'post_feedback')
        seg=r['payload']['source_statement_segments'];self.assertEqual(''.join(x['text'] for x in seg),r['text'])
        self.assertEqual([x['knowledge_phase'] for x in seg],['prediction','post_feedback'])
        self.assertIn('上午不会下雨',seg[0]['text']);self.assertIn('一天都是阴天',seg[1]['text'])
        self.assertIn('上午9点半',seg[1]['text']);self.assertIn('上午9点',self.record(1,19)['text'])
        self.assertTrue(r['payload']['parent_paragraph_withheld_from_initial_view'])

    def test_case2_sixyao_comparison_not_extra_qimen_charts_or_samples(self):
        r=self.record(2,46);self.assertEqual(r['knowledge_phase'],'unknown')
        self.assertTrue(r['payload']['not_three_additional_qimen_charts_or_independent_samples'])
        self.assertIn('三种方法',r['text']);self.assertIn('六爻',r['text'])
        self.assertEqual(len(self.artifact['cases'][1]['events']),1)
        self.assertEqual(len(self.artifact['cases'][1]['events'][0]['charts']),1)
        self.assertIn('问卦时间',self.record(2,47)['text'])
        self.assertIn('no separate hourly observation',self.record(2,71)['payload']['confirmation_scope'])

    def test_case3_rain_before_and_after_ceremony_window_not_all_day_dry(self):
        self.assertIn('甲辰时理应有雨',self.record(3,95)['text'])
        self.assertIn('即使有雨',self.record(3,99)['text'])
        r=self.record(3,100);self.assertEqual(r['knowledge_phase'],'post_feedback')
        self.assertEqual(r['payload']['reported_weather_sequence_as_written'],['早上一直下雨','上午9时雨停','9点15分揭牌','10点钟又下大雨'])
        self.assertTrue(r['payload']['not_all_day_dry'])
        self.assertEqual(len(self.artifact['cases'][2]['events'][0]['charts']),1)
        self.assertEqual(self.record(3,99)['speaker'],'袁炜文/原书叙述')

    def test_case4_shared_casting_existing_family_and_distinct_target_events(self):
        related=json.loads((ROOT/'data/structured/shenqi/sports_cases.json').read_bytes())['cases'][4]
        current=self.artifact['cases'][3];self.assertEqual(current['family'],related['family'])
        old=self.svc.cases('sports-competition')['cases'][4];new=self.catalog[3]
        with connect(self.db) as c:
            def ids(case):return c.execute('SELECT e.family_id,e.event_id FROM events e JOIN case_events ce USING(event_id) WHERE ce.case_id=?',(case['case_id'],)).fetchone()
            a,b=ids(old),ids(new);self.assertEqual(a['family_id'],b['family_id']);self.assertNotEqual(a['event_id'],b['event_id'])
            self.assertGreaterEqual(c.execute('SELECT COUNT(*) FROM events WHERE family_id=?',(a['family_id'],)).fetchone()[0],2)
        ref=current['events'][0]['charts'][0]['payload']['shared_casting_reference']
        self.assertEqual(ref['related_chart_key'],'sports-case-05-chart-1')
        self.assertEqual(ref['related_source_lines'],[178,190]);self.assertFalse(ref['canonical_correction_of_related_source'])
        self.assertIn('同一奇门格局',self.record(4,105)['text'])

    def test_case4_two_source_variant_cells_remain_separate(self):
        old=self.svc.cases('sports-competition')['cases'][4];new=self.catalog[3]
        a=self.svc.case_chart(old['case_id'],old['events'][0]['chart_ids'][0]);b=self.svc.case_chart(new['case_id'],new['events'][0]['chart_ids'][0])
        self.assertNotEqual(a['chart_id'],b['chart_id']);self.assertNotEqual(a['source_sha256'],b['source_sha256'])
        self.assertEqual(a['palaces']['9']['source']['column_cells'][-1],'铺庚');self.assertIsNone(a['palaces']['9']['star'])
        self.assertEqual(b['palaces']['9']['source']['column_cells'][-1],'辅庚');self.assertEqual(b['palaces']['9']['star'],'天辅星')
        for p in ('1','2','3','4','5','6','7','8'):
            self.assertEqual(a['palaces'][p]['source']['column_cells'],b['palaces'][p]['source']['column_cells'])
        self.assertFalse(a['original_chart_modified']);self.assertFalse(b['original_chart_modified'])

    def test_case4_wind_forecast_not_falsely_confirmed_by_wind_only_feedback(self):
        self.assertIn('三四级风',self.record(4,127)['text'])
        r=self.record(4,128);self.assertTrue(r['payload']['wind_force_measurement_not_supplied'])
        self.assertIn('does not separately confirm',r['payload']['confirmation_scope'])
        self.assertIn('9点20分',r['text']);self.assertIn('一天小雨',r['text']);self.assertIn('而且有风',r['text'])

    def test_case5_future_casting_time_question_window_and_result_scope(self):
        self.assertIn('7月27日下午2点',self.record(5,132)['text'])
        self.assertIn('9点半至10点半',self.record(5,132)['text'])
        self.assertIn('明天用事时间',self.record(5,133)['text'])
        p=self.artifact['cases'][4]['events'][0]['charts'][0]['payload']
        self.assertEqual(p['source_chart_metadata']['casting_basis_as_written'],'future_ceremony_time');self.assertFalse(p['calendar_recomputed'])
        self.assertIn('上午不会下雨',self.record(5,155)['text'])
        self.assertTrue(self.record(5,156)['payload']['reported_all_day_result_not_expanded_forecast'])

    def test_full_general_conditions_and_original_scientific_context_kept(self):
        source=self.source.decode()
        self.assertIn('未将天气预测列入奇门研究',source)
        c=next(c for c in self.candidates['candidates'] if c['key']=='weather_rain')
        for t in ('密云不雨','不乘壬癸','不下雨','与值符近'):self.assertIn(t,c['source_quote'])
        c=next(c for c in self.candidates['candidates'] if c['key']=='weather_river_water')
        for t in ('三奇','庚格','甲辰壬','不乘庚格','不会决堤'):self.assertIn(t,c['source_quote'])

    def test_five_candidates_scope_unknown_and_reference_only(self):
        for context,expected in [({},0),({'domain':'weather_prediction','weather_subtype':'rain','method_scope':'shenqi_weather_rain_reference_v1'},1),({'domain':'weather_prediction','weather_subtype':'winter_snow','method_scope':'shenqi_weather_winter_snow_reference_v1'},1)]:
            r=self.svc.rule_candidates(context,domain='weather_prediction',method='shenqi_weather_reference_v1')
            self.assertEqual(r['candidate_count'],5);self.assertFalse(r['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),expected)
            self.assertTrue(all(c['activation_status']=='reference_only' for c in r['candidates']))

    def test_original_center_and_carried_stem_prefixes(self):
        c=self.catalog[0];p=self.svc.case_chart(c['case_id'],c['events'][0]['chart_ids'][0])
        self.assertEqual(p['palaces']['5']['earth_stem'],'癸')
        self.assertEqual(p['palaces']['8']['heaven_prefix_marker'],'癸')
        self.assertIn('原盘单字：癸',p['palaces']['5']['source']['text'])
        self.assertIsNone(self.curated['printed_chapter_number'])

    def test_initial_view_withholds_mixed_outcome_and_prior_sixyao_forecasts(self):
        for c in self.catalog:
            v=self.svc.case(c['case_id'],'before_prediction');self.assertFalse(v['training_export'])
            for e in v['events']:
                for r in e.get('records',[]):self.assertEqual(r['knowledge_phase'],'pre_prediction')
        v=json.dumps(self.svc.case(self.catalog[0]['case_id'],'before_prediction'),ensure_ascii=False)
        for t in ('一天都是阴天','9点半举行','一点雨也未下'):self.assertNotIn(t,v)
        v=json.dumps(self.svc.case(self.catalog[1]['case_id'],'before_prediction'),ensure_ascii=False)
        for t in ('三个卦都表明','完全证实','其他时间为晴天'):self.assertNotIn(t,v)

    def test_existing_api_cli_and_append_only_replay(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        for c in call('/v1/cases',{'chapter_key':'weather-prediction'})['cases']:
            for e in c['events']:
                for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':c['case_id'],'chart_id':cid})['chart_id'],cid)
        r=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','weather-prediction'],cwd=ROOT,capture_output=True,text=True,check=True)
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
