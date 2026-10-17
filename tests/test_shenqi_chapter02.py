"""Source-transcribed chapter-two regressions; no synthetic divination outcomes."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.casting.paper import PAPER_METHOD
from qimenllm.contracts import Inquiry
from qimenllm.knowledge.chapter02 import SOURCE_SHA, install_chapter02
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
from support import DatabaseTest
from test_runtime import request, CapturingFixtureModel


ROOT=Path(__file__).resolve().parents[1]
CURATED=json.loads((ROOT/'data/structured/shenqi/chapter02_curated.json').read_bytes())
EXPECTED=json.loads((ROOT/'data/structured/shenqi/chapter02_regression_cases.json').read_bytes())
C1=json.loads((ROOT/'data/structured/shenqi/chapter01_curated.json').read_bytes())


class ChapterTwoTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        for seq,title,curation in ((1,'时家奇门演局的规律',C1),(2,'时家奇门的起局方法',CURATED)):
            self.source=import_chapter(self.db,self.raw,
                (ROOT/'data/snapshots/current/raw'/f"{curation['source_sha256']}.bin").read_bytes(),
                book_key='shenqi-user-text-v1',book_title='神奇之门',chapter_key=f'chapter-0{seq}',
                chapter_title=title,sequence=seq,origin='actual-supplied-text-regression',confirmed=False)
            if seq==1: install_curated(self.db,self.source['revision_id'],curation)
            else: self.install=install_chapter02(self.db,self.source['revision_id'],curation)
        self.service=QimenService(self.db)

    def calculate(self,operation,**args):
        result=self.service.calculate(operation,args)
        self.assertEqual(result['status'],'computed',result)
        self.assertTrue(result['evidence'])
        self.assertFalse(result['calendar_recomputed'])
        self.assertFalse(result['professional_analysis_completed'])
        return result

    def chart(self,dun,bureau,hour):
        return self.calculate('symbolic_chart',dun=dun,bureau=bureau,hour_ganzhi=hour,method=PAPER_METHOD)

    def test_whole_source_hash_spans_and_no_invented_cases(self):
        raw=(ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHA}.bin').read_bytes()
        self.assertEqual(digest(raw),SOURCE_SHA)
        self.assertEqual(len(raw),22354)
        self.assertEqual(len(raw.decode().splitlines()),416)
        self.assertFalse(raw.endswith(b'\n'))
        covered=set()
        for g in CURATED['groups']: covered.update(range(g['line_start'],g['line_end']+1))
        self.assertEqual(covered,set(range(1,417)))
        self.assertTrue(audit(self.db,self.raw)['ok'])
        with connect(self.db) as conn:
            for table in ('cases','events','charts','training_tasks','rules'):
                self.assertEqual(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)

    def test_replay_keeps_data_version_and_compilation_profile_isolated(self):
        again=install_chapter02(self.db,self.source['revision_id'],CURATED)
        self.assertEqual(again['data_version'],self.install['data_version'])
        for field in ('structured_records_added','compiled_families_added','methods_added','concept_entries_added'):
            self.assertEqual(again[field],0)
        self.assertEqual(len(self.service.knowledge.compiled_datasets('shenqi_ch1_foundation_v1')),12)
        self.assertEqual(len(self.service.knowledge.compiled_datasets('shenqi_ch2_foundation_v1')),8)
        invalid=copy.deepcopy(CURATED); invalid['source_sha256']='0'*64
        with self.assertRaises(ValueError): install_chapter02(self.db,self.source['revision_id'],invalid)

    def test_two_complete_source_plates_every_palace_star_stem_door_deity(self):
        for case in EXPECTED['chart_expectations']:
            given=case['given_inputs']
            with self.subTest(case=case['key']):
                result=self.chart(given['dun'],given['bureau'],given['four_pillars']['hour'])
                chart=result['result']
                for palace,expected in case['palaces'].items():
                    with self.subTest(palace=palace):
                        actual=chart['palaces'][palace]
                        for key in ('earth_stem','door','deity'): self.assertEqual(actual[key],expected[key])
                        self.assertEqual({s['name']:s['carried_stem'] for s in actual['heaven_stars']},
                                         {s['name']:s['carried_stem'] for s in expected['heaven_stars']})
                facts=chart['derived_facts']; expected=case['duty']
                for key in ('xun_head','hidden_stem','zhifu_star','zhifu_landing_original_palace',
                            'zhifu_layout_palace','zhishi_door'):
                    self.assertEqual(facts[key],expected[key])
                self.assertEqual(facts['zhishi_counting_origin_palace'],expected['zhishi_count_origin_palace'])
                self.assertEqual(facts['zhishi_landing_palace'],expected['zhishi_landing_original_palace'])
                self.assertTrue(chart['plate_layout_complete'])
                self.assertEqual(chart['validation_status'],'symbolic_verified')
                self.assertEqual(chart['four_pillars']['day'],None)
                self.assertEqual(chart['input_datetime'],None)
                self.assertEqual(chart['voids'],None); self.assertEqual(chart['horse'],None)
                self.assertFalse(chart['complete_chart'])
                self.assertEqual({e['sha256'] for e in result['evidence']},{C1['source_sha256'],SOURCE_SHA})

    def test_source_hour_tables_all_ten_days_and_twelve_hours(self):
        for group in EXPECTED['hour_pillar_groups']:
            for stem in group['day_stems']:
                for hour in group['hours']:
                    with self.subTest(stem=stem,hour=hour):
                        result=self.calculate('hour_ganzhi',day_stem=stem,hour_branch=hour[1])['result']
                        self.assertEqual(result['hour_ganzhi'],hour)
                        self.assertEqual(result['midnight_day_convention'],'not_inferred')

    def test_source_example_inputs_compose_bureau_hour_and_layout(self):
        for case in EXPECTED['chart_expectations']:
            given=case['given_inputs']; day=given['four_pillars']['day']; hour=given['four_pillars']['hour']
            bureau=self.service.calculate('bureau',{'solar_term':given['solar_term'],'day_ganzhi':day,'method':'chaibu'})['result']
            self.assertEqual((bureau['dun'],bureau['bureau'],bureau['fu_head'],bureau['yuan']),
                             (given['dun'],given['bureau'],given['fu_head'],given['yuan']))
            calculated=self.calculate('hour_ganzhi',day_stem=day[0],hour_branch=hour[1])['result']
            self.assertEqual(calculated['hour_ganzhi'],hour)
            self.chart(bureau['dun'],bureau['bureau'],calculated['hour_ganzhi'])
        palm=EXPECTED['additional_symbolic_examples'][0]
        chart=self.chart(palm['given_inputs']['dun'],palm['given_inputs']['bureau'],palm['given_inputs']['hour_pillar'])['result']
        for key in ('xun_head','hidden_stem','zhifu_star','zhifu_landing_original_palace','zhifu_layout_palace','zhishi_door'):
            self.assertEqual(chart['derived_facts'][key],palm['expected'][key])
        self.assertEqual(chart['derived_facts']['zhishi_landing_palace'],palm['expected']['zhishi_landing_original_palace'])

    def test_source_clock_ranges_and_explicit_boundary_policy(self):
        for row in EXPECTED['clock_branch_expectations']:
            hour,minute=map(int,row['representative_clock_time'].split(':'))
            self.assertEqual(self.calculate('hour_branch',clock_hour=hour,clock_minute=minute)['result']['hour_branch'],row['branch'])
        for hour,branch in ((0,'子'),(1,'丑'),(3,'寅'),(22,'亥'),(23,'子')):
            r=self.calculate('hour_branch',clock_hour=hour,clock_minute=0)['result']
            self.assertEqual(r['hour_branch'],branch)
            self.assertEqual(r['day_assignment'],'not_determined')
            self.assertEqual(r['boundary_convention'],'start_inclusive_end_exclusive')
        for args in ({'clock_hour':24,'clock_minute':0},{'clock_hour':True,'clock_minute':0},
                     {'clock_hour':9,'clock_minute':60}):
            with self.assertRaises(ValueError): self.service.calculate('hour_branch',args)

    def test_five_combinations_are_correspondences_not_actual_transformation(self):
        for row in EXPECTED['stem_combination_expectations']:
            for stem in row['stems']:
                value=self.calculate('stem_combination',stem=stem)['result']
                self.assertEqual(set(value['stems']),set(row['stems']))
                self.assertEqual(value['element'],row['transformation_element'])
        self.assertEqual(self.service.calculate('stem_attribute',{'stem':'甲'})['result']['element'],'木')
        self.assertEqual(self.service.calculate('operational_hour_half',{'stem':'乙'})['result']['half'],'yang')

    def test_only_explicit_palace_elements_and_directed_relations(self):
        for row in EXPECTED['palace_element_expectations']:
            self.assertEqual(self.calculate('documented_palace_element',palace=row['palace'])['result']['element'],row['element'])
        for palace in (1,3,4,5,6,8):
            self.assertEqual(self.service.calculate('documented_palace_element',{'palace':palace})['status'],'not_covered')
        for row in EXPECTED['element_relation_expectations']:
            value=self.calculate('documented_element_relation',source=row['source'],target=row['target'])['result']
            self.assertEqual(value['relations'],[row['relation']])
        self.assertEqual(self.service.calculate('documented_element_relation',{'source':'火','target':'水'})['status'],'not_covered')

    def test_center_origin_counts_from_five_not_host_two(self):
        chart=self.chart('阴遁',8,'戊戌')['result']; facts=chart['derived_facts']
        self.assertEqual(facts['zhifu_native_palace'],5)
        self.assertEqual(facts['zhishi_native_palace'],2)
        self.assertEqual(facts['zhishi_counting_origin_palace'],5)
        self.assertEqual(facts['zhishi_landing_palace'],1)
        self.assertEqual(chart['palaces']['5']['heaven_stars'],[])
        self.assertEqual({s['name'] for s in chart['palaces']['8']['heaven_stars']},{'天禽星','天芮星'})

    def test_center_star_landing_retains_five_and_layout_two(self):
        chart=self.chart('阳遁',1,'壬寅')['result']; facts=chart['derived_facts']
        self.assertEqual(facts['zhifu_landing_original_palace'],5)
        self.assertEqual(facts['zhifu_layout_palace'],2)
        self.assertIn('天辅星',[s['name'] for s in chart['palaces']['2']['heaven_stars']])
        self.assertEqual(chart['palaces']['5']['heaven_stars'],[])

    def test_unprovided_final_center_door_is_not_silently_hosted(self):
        result=self.service.calculate('symbolic_chart',{'dun':'阳遁','bureau':1,'hour_ganzhi':'乙未','method':PAPER_METHOD})
        self.assertEqual(result['status'],'not_covered')
        self.assertNotIn('result',result)
        missing=self.service.calculate('symbolic_chart',{'dun':'阳遁','bureau':3,'hour_ganzhi':'丁巳'})
        self.assertEqual(missing['status'],'conditional'); self.assertEqual(missing['missing'],['method'])
        other=self.service.calculate('symbolic_chart',{'dun':'阳遁','bureau':3,'hour_ganzhi':'丁巳','method':'per_xun'})
        self.assertEqual(other['status'],'not_covered')

    def test_api_and_official_ask_use_same_immutable_chart_and_no_model(self):
        args={'dun':'阳遁','bureau':3,'hour_ganzhi':'丁巳','method':PAPER_METHOD}
        with patch.object(self.service.knowledge,'compiled_datasets',wraps=self.service.knowledge.compiled_datasets) as query:
            status,response=request(create_app(self.service),{'operation':'symbolic_chart','args':args},path='/v1/calculate')
            self.assertEqual(status,'200 OK'); self.assertGreaterEqual(query.call_count,2)
        model=CapturingFixtureModel(); service=QimenService(self.db,model=model)
        answer=service.ask(Inquiry('原文起局演示',casting_method=PAPER_METHOD,
            context={k:v for k,v in args.items() if k!='method'}))
        self.assertEqual(answer['status'],'blocked'); self.assertEqual(model.calls,[])
        self.assertEqual(answer['chart_id'],response['result']['chart_id'])
        self.assertEqual(json.loads(answer['chart']['payload_json']),response['result'])
        chart=service.casting.cast(Inquiry('演示',casting_method=PAPER_METHOD,context={'dun':'阳遁','bureau':3,'hour_ganzhi':'丁巳'})).chart
        changed=chart.facts(); changed['palaces']['9']['door']='改动'
        self.assertEqual(chart.facts()['palaces']['9']['door'],'休门')
        self.assertEqual(answer['trace'][1]['status'],'symbolic_verified')
        self.assertEqual(service.ask(Inquiry('只给真实日期',input_datetime='1995-06-11T09:30:00'))['chart_id'],None)

    def test_learning_retains_original_chart_and_explanation_labels(self):
        value=self.service.learning.learn('五鼠遁')
        self.assertEqual(value['status'],'sources_found')
        self.assertTrue(any('1995年8月13日' in hit['body'] for hit in value['original_sources']))
        self.assertTrue(value['knowledge_blocks'])
        self.assertTrue(all(e['kind']=='curated_explanation_not_original' for e in value['system_explanation']))
        self.assertIsNone(value['model_analysis'])

    def test_snapshot_restores_same_plate_and_per_request_evidence(self):
        expected=self.chart('阴遁',8,'戊戌')
        export_snapshot(self.db,self.raw,self.root/'snapshot')
        restore_snapshot(self.root/'snapshot',self.root/'restored.sqlite3',self.root/'restored-raw')
        restored=QimenService(self.root/'restored.sqlite3')
        self.assertEqual(restored.calculate('symbolic_chart',expected['inputs']),expected)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda x:self.service.calculate(*x),[
                ('symbolic_chart',expected['inputs']),('hour_branch',{'clock_hour':9,'clock_minute':30})]*4))
        for i,result in enumerate(results):
            self.assertEqual(result['operation'],'symbolic_chart' if i%2==0 else 'hour_branch')
            if i%2: self.assertEqual({e['dataset'] for e in result['evidence']},{'hour_windows'})

    def test_empty_database_never_synthesizes_second_chapter(self):
        from qimenllm.knowledge.db import initialize
        empty=self.root/'empty.sqlite3'; initialize(empty)
        value=QimenService(empty).calculate('symbolic_chart',{'dun':'阳遁','bureau':3,'hour_ganzhi':'丁巳','method':PAPER_METHOD})
        self.assertEqual(value['status'],'not_covered')
