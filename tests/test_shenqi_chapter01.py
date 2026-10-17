"""Professional-source regressions from the newly supplied chapter, not synthetic Qimen facts."""
import copy
import io
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cli import main
from qimenllm.contracts import Inquiry
from qimenllm.knowledge.curation import install_curated, COMPILED_DATASETS
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
from support import DatabaseTest
from test_runtime import request


ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='b70a7ab71b428a39f262d3df2ff41058af9273bb561419371d5e1b979e095718'
RAW=ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHA}.bin'
CURATED=json.loads((ROOT/'data/structured/shenqi/chapter01_curated.json').read_bytes())
CASES=json.loads((ROOT/'data/structured/shenqi/chapter01_regression_cases.json').read_bytes())


class ShenqiChapterTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.source=import_chapter(self.db,self.raw,RAW.read_bytes(),book_key='shenqi-user-text-v1',
            book_title='神奇之门',chapter_key='chapter-01',chapter_title='时家奇门演局的规律',
            sequence=1,origin='actual_user_chapter_regression',confirmed=False)
        self.installed=install_curated(self.db,self.source['revision_id'],CURATED)
        self.service=QimenService(self.db)

    def compute(self,op,**args):
        result=self.service.calculate(op,args)
        self.assertEqual(result['status'],'computed',result)
        return result

    def test_original_exact_hash_full_context_and_anomalies_preserved(self):
        raw=RAW.read_bytes()
        self.assertEqual(digest(raw),SOURCE_SHA)
        self.assertEqual(len(raw),63691)
        self.assertEqual(len(raw.decode().splitlines()),447)
        self.assertFalse(raw.endswith(b'\n'))
        self.assertIn('太合',raw.decode())
        self.assertEqual(raw.decode().count('____'),3)
        self.assertTrue(audit(self.db,self.raw)['ok'])
        covered=set()
        for group in CURATED['groups']: covered.update(range(group['line_start'],group['line_end']+1))
        self.assertEqual(covered,set(range(1,448)))

    def test_install_is_idempotent_without_extra_data_version(self):
        again=install_curated(self.db,self.source['revision_id'],CURATED)
        self.assertEqual(again['structured_records_added'],0)
        self.assertEqual(again['compiled_families_added'],0)
        self.assertEqual(again['concept_entries_added'],0)
        self.assertEqual(again['data_version'],self.installed['data_version'])

    def test_invalid_curation_references_are_rejected_before_any_annotation_write(self):
        bad=copy.deepcopy(CURATED)
        target=next(g for g in bad['groups'] if (g.get('dataset') or {}).get('key')=='earth_sequence')
        target['summary']='Changed summary that must never partially commit'
        target['dataset']['supporting_group_keys']=['nonexistent_group']
        with connect(self.db) as conn:
            before=[conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('knowledge_items','data_versions')]
        with self.assertRaises(ValueError): install_curated(self.db,self.source['revision_id'],bad)
        with connect(self.db) as conn:
            after=[conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('knowledge_items','data_versions')]
        self.assertEqual(before,after)

    def test_independent_203_source_expectations(self):
        self.assertEqual(len(CASES),203)
        for case in CASES:
            with self.subTest(source_case=case['key']):
                result=self.compute(case['operation'],**case['args'])
                for key,value in case['expected'].items(): self.assertEqual(result['result'].get(key),value,key)
                self.assertFalse(result['calendar_recomputed'])
                self.assertFalse(result['complete_chart'])
                self.assertTrue(result['evidence'])
                self.assertTrue(all(e['sha256']==SOURCE_SHA for e in result['evidence']))

    def test_all_18_earth_layouts_keep_nine_unique_stems_and_center(self):
        for dun in ('阳遁','阴遁'):
            for bureau in range(1,10):
                with self.subTest(dun=dun,bureau=bureau):
                    value=self.compute('earth_plate',dun=dun,bureau=bureau)['result']
                    self.assertEqual(len(value['palaces']),9)
                    self.assertEqual(len(set(value['palaces'].values())),9)
                    self.assertEqual(value['palaces'][str(bureau)],'戊')
                    self.assertEqual(value['center']['stem'],value['palaces']['5'])
                    self.assertEqual(value['center']['host_palace'],2)
                    self.assertNotEqual(value['palaces']['2'],value['palaces']['5'])

    def test_hour_halves_do_not_overwrite_stem_polarity_or_trigram_scope(self):
        self.assertEqual(self.compute('stem_attribute',stem='乙')['result']['polarity'],'yin')
        self.assertEqual(self.compute('operational_hour_half',stem='乙')['result']['half'],'yang')
        self.assertEqual(self.compute('stem_attribute',stem='庚')['result']['polarity'],'yang')
        self.assertEqual(self.compute('operational_hour_half',stem='庚')['result']['half'],'yin')
        familial=self.compute('trigram_classification',classification='familial_trigram_yinyang')['result']
        dun=self.compute('trigram_classification',classification='dun_half_year_trigram_yinyang')['result']
        self.assertIn('乾',familial['yang']); self.assertIn('乾',dun['yin'])

    def test_all_compiled_fixed_stem_star_door_and_deity_attributes(self):
        # Expected values are independently transcribed from input lines 12/14 and 383–440.
        stems=[('甲','yang','木'),('乙','yin','木'),('丙','yang','火'),('丁','yin','火'),
               ('戊','yang','土'),('己','yin','土'),('庚','yang','金'),('辛','yin','金'),('壬','yang','水'),('癸','yin','水')]
        for stem,polarity,element in stems:
            row=self.compute('stem_attribute',stem=stem)['result']
            self.assertEqual((row['polarity'],row['element']),(polarity,element))
        correspondence=[(1,'天蓬星','贪狼星','水','休门'),(2,'天芮星','巨门星','土','死门'),
            (3,'天冲星','禄存星','木','伤门'),(4,'天辅星','文曲星','木','杜门'),
            (5,'天禽星','廉贞星','土',None),(6,'天心星','武曲星','金','开门'),
            (7,'天柱星','破军星','金','惊门'),(8,'天任星','左辅星','土','生门'),(9,'天英星','右弼星','火','景门')]
        for palace,star,alias,element,door in correspondence:
            row=self.compute('star_attribute',star=star)['result']
            self.assertEqual((row['home_palace'],row['element']),(palace,element)); self.assertIn(alias,row['aliases'])
            if door:
                row=self.compute('door_attribute',door=door)['result']
                self.assertEqual((row['home_palace'],row['element']),(palace,element))
        self.assertTrue(self.compute('door_attribute',door='死门')['result']['includes_central_palace'])
        deities=[('值符','木',False),('螣蛇','火',False),('太阴','金',True),('六合','木',True),
                 ('白虎','金',False),('玄武','水',False),('九地','土',True),('九天','金',True)]
        for deity,element,good in deities:
            row=self.compute('deity_attribute',deity=deity)['result']
            self.assertEqual((row['element'],row['listed_among_four_good']),(element,good))

    def test_only_three_directed_element_edges_and_unknown_is_not_false(self):
        for source,target,relation in (('木','火','生'),('金','木','克'),('火','金','克')):
            self.assertEqual(self.compute('element_relation',source=source,target=target)['result']['relations'],[relation])
        for source,target in (('水','木'),('火','木'),('木','金')):
            self.assertEqual(self.service.calculate('element_relation',{'source':source,'target':target})['status'],'not_covered')

    def test_yuan_uses_full_day_table_not_day_branch_alone(self):
        value=self.compute('day_yuan',day_ganzhi='壬辰')['result']
        self.assertEqual((value['fu_head'],value['yuan'],value['day_in_yuan']),('己丑','下元',4))
        value=self.compute('day_yuan',day_ganzhi='乙酉')['result']
        self.assertFalse(value['is_fu_head']); self.assertEqual(value['yuan'],'中元')

    def test_method_not_silently_selected_and_calendar_not_invented(self):
        response=self.service.calculate('bureau',{'solar_term':'冬至','day_ganzhi':'壬辰'})
        self.assertEqual(response['status'],'conditional'); self.assertIn('method',response['missing'])
        self.assertEqual(self.service.calculate('bureau',{'solar_term':'冬至','day_ganzhi':'壬辰','method':'zhirun'})['status'],'not_covered')
        with self.assertRaises(ValueError): self.service.calculate('bureau',{'solar_term':'冬至','day_ganzhi':'壬辰','method':'chaibu','datetime':'1995-01-01'})
        with self.assertRaises(ValueError): self.service.calculate('full_chart',{'datetime':'1995-01-01'})

    def test_native_palace_not_actual_landing_and_no_palace_element_invention(self):
        star=self.compute('star_attribute',star='天心星')['result']
        self.assertEqual(star['home_palace'],6)
        self.assertNotIn('landing_palace',star)
        palace=self.compute('palace_attribute',palace=6)['result']
        self.assertEqual(palace['trigram'],'乾'); self.assertEqual(palace['home_star_element'],'金')
        self.assertIsNone(palace['palace_element'])

    def test_deity_imagery_and_underlying_names_are_not_unconditional_aliases(self):
        earth=self.compute('deity_attribute',deity='九地')['result']
        self.assertEqual(earth['element_basis'],'element_imagery')
        self.assertEqual(self.service.calculate('deity_attribute',{'deity':'勾陈'})['status'],'not_covered')
        self.assertEqual(self.service.calculate('deity_attribute',{'deity':'太合'})['status'],'not_covered')
        with self.assertRaises(ValueError): self.service.calculate('deity_placement',{'method':'any'})

    def test_unprovided_chief_center_conventions_are_not_silently_guessed(self):
        # In provided yang-1 earth layout, 壬 hides 甲辰 at central palace.
        result=self.service.calculate('duty',{'dun':'阳遁','bureau':1,'hour_ganzhi':'甲辰'})
        self.assertEqual(result['status'],'not_covered')
        # 杜门's arithmetic landing may be 5; hosting has not been supplied.
        result=self.compute('duty',dun='阳遁',bureau=1,hour_ganzhi='乙未')['result']
        self.assertEqual(result['zhishi_landing_palace'],5)
        self.assertIsNone(result['zhishi_hosted_palace'])

    def test_actual_database_retrieval_and_learning_api_share_service(self):
        with patch.object(self.service.knowledge,'compiled_datasets',wraps=self.service.knowledge.compiled_datasets) as query:
            status,result=request(create_app(self.service),{'operation':'earth_plate','args':{'dun':'阳遁','bureau':3}},'/v1/calculate')
            self.assertEqual(status,'200 OK'); self.assertEqual(result['status'],'computed')
            query.assert_called_once()
        status,result=request(create_app(self.service),{'term':'太合'},'/v1/learn')
        self.assertEqual(status,'200 OK'); self.assertTrue(result['knowledge_blocks'])
        self.assertIsNone(result['model_analysis'])
        self.assertTrue(any('太合' in b['payload']['summary'] for b in result['knowledge_blocks']))
        self.assertEqual(self.service.ask(Inquiry('这次考试会成功吗'))['status'],'blocked')
        self.assertEqual(request(create_app(self.service),{},'/health','GET')[1]['phase'],1)

    def test_curated_only_search_hit_has_original_citation_and_correct_status(self):
        result=self.service.learning.learn('军事来源')
        self.assertEqual(result['status'],'sources_found')
        self.assertEqual(result['original_sources'],[])
        self.assertTrue(result['knowledge_blocks'])
        source=result['knowledge_blocks'][0]['source']
        self.assertEqual(source['sha256'],SOURCE_SHA)
        self.assertTrue(source['excerpt']); self.assertEqual(source['source_acceptance'],'pending')

    def test_cli_calculation_reaches_same_database_backed_result(self):
        output=io.StringIO()
        with redirect_stdout(output):
            code=main(['--db',str(self.db),'calculate','bureau','--args',json.dumps({'solar_term':'冬至','day_ganzhi':'壬辰','method':'chaibu'})])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())['result']['bureau'],4)

    def test_source_review_and_case_counts_are_separate_from_compilation(self):
        result=self.compute('earth_plate',dun='阳遁',bureau=3)
        self.assertTrue(all(e['source_acceptance']=='pending' for e in result['evidence']))
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM knowledge_items WHERE compiled=1').fetchone()[0],12)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM rules').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0],0)
        self.assertFalse(result['professional_analysis_completed'])

    def test_calculations_without_database_knowledge_cannot_use_model_memory(self):
        empty=self.root/'empty.sqlite3'
        from qimenllm.knowledge.db import initialize
        initialize(empty)
        response=QimenService(empty).calculate('earth_plate',{'dun':'阳遁','bureau':3})
        self.assertEqual(response['status'],'not_covered')

    def test_snapshot_roundtrip_reproduces_teaching_calculations(self):
        destination=self.root/'snapshot'; export_snapshot(self.db,self.raw,destination)
        restored=self.root/'restored.sqlite3'; restore_snapshot(destination,restored,self.root/'restored-raw')
        after=QimenService(restored).calculate('duty',{'dun':'阳遁','bureau':1,'hour_ganzhi':'戊戌'})
        before=self.compute('duty',dun='阳遁',bureau=1,hour_ganzhi='戊戌')
        self.assertEqual(after,before)

    def test_per_request_evidence_does_not_leak_between_concurrent_operations(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.service.calculate,'stem_attribute',{'stem':'甲'})
            b=pool.submit(self.service.calculate,'element_relation',{'source':'木','target':'火'})
            self.assertEqual({e['dataset'] for e in a.result()['evidence']},{'stem_attributes'})
            self.assertEqual({e['dataset'] for e in b.result()['evidence']},{'explicit_element_relations'})
