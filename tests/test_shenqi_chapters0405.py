"""Independent source transcriptions and real runtime regressions for chapters 4 and 5."""
import io
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cli import main
from qimenllm.contracts import Inquiry
from qimenllm.knowledge.chapters0405 import SOURCE_SHAS, install_chapter
from qimenllm.knowledge.chapter02 import install_chapter02
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.db import connect, digest, initialize
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
from support import DatabaseTest
from test_runtime import request, CapturingFixtureModel


ROOT=Path(__file__).resolve().parents[1]
CURATIONS={n:json.loads((ROOT/f'data/structured/shenqi/chapter{n:02d}_curated.json').read_bytes()) for n in (1,2,4,5)}
GOLD=json.loads((ROOT/'data/structured/shenqi/chapter0405_regression_cases.json').read_bytes())
UPLOAD_SHA='8b8d7f57fa539785f5613cb6f8fdbdc27090da559d6d2fe5ce0ffd03953c9147'


class NewSourceTests(DatabaseTest):
    def setUp(self):
        super().setUp(); self.revisions={}
        for number,c in CURATIONS.items():
            source=import_chapter(self.db,self.raw,
                (ROOT/'data/snapshots/current/raw'/f"{c['source_sha256']}.bin").read_bytes(),
                book_key='shenqi-user-text-v1',book_title='神奇之门',chapter_key=f'chapter-{number:02d}',
                chapter_title=c['chapter_title'],sequence=number,origin='actual-supplied-text-regression',confirmed=False)
            self.revisions[number]=source['revision_id']
            if number==1: install_curated(self.db,source['revision_id'],c)
            elif number==2: install_chapter02(self.db,source['revision_id'],c)
            else: install_chapter(self.db,source['revision_id'],c,number)
        self.service=QimenService(self.db)

    def calc(self,operation,**args):
        r=self.service.calculate(operation,args)
        self.assertEqual(r['status'],'computed',r)
        self.assertTrue(r['evidence'])
        self.assertFalse(r['professional_analysis_completed'])
        self.assertFalse(r['calendar_recomputed'])
        return r['result']

    def test_parent_upload_and_exact_slices_reconstruct_without_renumbering(self):
        whole=(ROOT/'data/provenance/uploads'/f'{UPLOAD_SHA}.utf8').read_bytes()
        self.assertEqual(digest(whole),UPLOAD_SHA); self.assertEqual(len(whole),86324)
        parts=[(ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHAS[n]}.bin').read_bytes() for n in (4,5)]
        self.assertEqual(b''.join(parts),whole)
        self.assertEqual([len(p.splitlines()) for p in parts],[500,761])
        with connect(self.db) as conn:
            self.assertEqual([r[0] for r in conn.execute('SELECT chapter_key FROM chapters ORDER BY sequence')],
                             ['chapter-01','chapter-02','chapter-04','chapter-05'])
            for table in ('rules','cases','events','charts','training_tasks'):
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_all_curated_context_and_independent_source_quotes_preserved(self):
        whole=(ROOT/'data/provenance/uploads'/f'{UPLOAD_SHA}.utf8').read_text().splitlines(keepends=True)
        count=0
        def visit(node):
            nonlocal count
            if isinstance(node,dict):
                if 'source_quote' in node:
                    expected=''.join(whole[node['line_start']-1:node['line_end']])
                    self.assertEqual(node['source_quote'],expected); count+=1
                for value in node.values(): visit(value)
            elif isinstance(node,list):
                for value in node: visit(value)
        visit(GOLD); self.assertGreater(count,1000)
        for number in (4,5):
            c=CURATIONS[number]; covered=set()
            for g in c['groups']: covered.update(range(g['line_start'],g['line_end']+1))
            self.assertEqual(covered,set(range(1,c['source_line_count']+1)))

    def test_both_installers_idempotent_without_new_versions(self):
        with connect(self.db) as conn: before=conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        for number in (4,5):
            r=install_chapter(self.db,self.revisions[number],CURATIONS[number],number)
            for k in ('structured_records_added','compiled_families_added','methods_added','concept_entries_added'):
                self.assertEqual(r[k],0)
        with connect(self.db) as conn: self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],before)
        bad=copy.deepcopy(CURATIONS[5]); bad['groups'][0]['category']='unsupported_category'
        with self.assertRaises(ValueError): install_chapter(self.db,self.revisions[5],bad,5)
        with connect(self.db) as conn: self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],before)

    def test_branch_attributes_stem_stages_and_fixed_home_attributes(self):
        for row in GOLD['branch_native_attributes']:
            actual=self.calc('branch_attribute',branch=row['branch'])
            self.assertEqual((actual['polarity'],actual['element']),(row['polarity'],row['element']))
            self.assertIsNone(actual['hidden_stems'])
        for row in GOLD['stem_life_stage_facts']:
            for stage,branch in row['stages'].items():
                self.assertEqual(self.calc('stem_life_stage',stem=row['stem'],stage=stage)['branch'],branch)
        self.assertEqual(self.service.calculate('stem_life_stage',{'stem':'甲','stage':'沐浴'})['status'],'not_covered')
        for row in GOLD['door_native_attributes']:
            result=self.calc('door_attribute',door=row['door'])
            self.assertEqual((result['home_palace'],result['element']),(row['home_palace'],row['element']))
        for row in GOLD['star_native_attributes']:
            result=self.calc('star_attribute',star=row['star'])
            self.assertEqual((result['home_palace'],result['element']),(row['home_palace'],row['element']))
        # Chapter-four line 251: independent explicit source pairs, not a generated complement.
        for first,second in (('甲','庚'),('乙','辛'),('壬','丙'),('癸','丁')):
            self.assertTrue(self.calc('stem_clash',first=first,second=second)['listed_pair_match'])
            self.assertTrue(self.calc('stem_clash',first=second,second=first)['listed_pair_match'])
        self.assertFalse(self.calc('stem_clash',first='戊',second='己')['listed_pair_match'])

    def test_all_ten_directed_element_edges_now_have_actual_sources(self):
        self.assertEqual(len(GOLD['explicit_element_relations']),10)
        for row in GOLD['explicit_element_relations']:
            value=self.calc('sourced_element_relation',source=row['source'],target=row['target'])
            self.assertEqual(value['relation_kind'],'generates' if row['relation']=='生' else 'controls')
            opposite=self.calc('sourced_element_relation',source=row['target'],target=row['source'])
            self.assertEqual(opposite['relation_kind'],'generated_by' if row['relation']=='生' else 'controlled_by')

    def test_108_star_month_expectations_use_the_selected_month_method(self):
        self.assertEqual(len(GOLD['star_month_strength_expectations']),108)
        for row in GOLD['star_month_strength_expectations']:
            with self.subTest(case=row['key']):
                result=self.calc('star_month_strength',star=row['star'],month_branch=row['month_branch'],method='shenqi_ch4_star_month_v1')
                self.assertEqual(result['state'],row['expected_state'])
                self.assertFalse(result['landing_palace_used_as_month'])
        missing=self.service.calculate('star_month_strength',{'star':'天蓬星','month_branch':'寅'})
        self.assertEqual(missing['status'],'conditional'); self.assertEqual(missing['missing'],['method'])
        wrong=self.service.calculate('star_month_strength',{'star':'天蓬星','month_branch':'寅','method':'ordinary_season_strength'})
        self.assertEqual(wrong['status'],'not_covered')

    def test_door_general_seasons_preserve_special_month_scope_and_omission(self):
        for row in GOLD['door_seasonal_strength']:
            for state,season in row['states_as_written'].items():
                if season is None: continue
                with self.subTest(door=row['door'],season=season):
                    result=self.calc('door_season_strength',door=row['door'],season=season)
                    self.assertIn(state,[s['state'] for s in result['states']])
                    self.assertEqual(result['special_month_priority'],'not_assumed')
        dead=self.calc('door_season_strength',door='死门',season='秋')
        self.assertEqual(dead['states'][0]['state'],'旺'); self.assertIn('休',dead['missing_states'])
        self.assertEqual(self.service.calculate('door_season_strength',{'door':'死门','season':'四季末月'})['status'],'not_covered')

    def test_door_palace_direction_and_thirteen_explicit_pressure_pairs(self):
        for row in GOLD['explicit_door_poe_pairs']:
            value=self.calc('door_palace_relation',door=row['door'],palace=row['landing_palace'])
            self.assertEqual(value['classification'],'迫')
            self.assertEqual((value['door_element'],value['palace_element']),(row['door_element'],row['palace_element']))
        for door,palace,name in (('休门',2,'制'),('开门',1,'和'),('休门',6,'义')):
            self.assertEqual(self.calc('door_palace_relation',door=door,palace=palace)['classification'],name)
        self.assertEqual(self.service.calculate('door_palace_relation',{'door':'开门','palace':5})['status'],'not_covered')

    def test_branch_punishment_directions_do_not_replace_instrument_table(self):
        # Exact fourth-chapter line 315 directed graph, including the contrary local fifth-chapter example.
        for pair in ('子卯','卯子','寅巳','巳申','申寅','丑未','未戌','戌丑'):
            self.assertTrue(self.calc('branch_group',relation='刑',branches=pair)['listed_group_match'])
        for pair in ('辰辰','午午','酉酉','亥亥'):
            self.assertTrue(self.calc('branch_group',relation='自刑',branches=pair)['listed_group_match'])
        for relation,groups in (('冲',('子午','卯酉','辰戌','巳亥','丑未','寅申')),
                                ('害',('子未','丑午','寅巳','卯辰','申亥','酉戌')),
                                ('六合',('子丑','寅亥','卯戌','辰酉','巳申','午未')),
                                ('三会',('寅卯辰','巳午未','申酉戌','亥子丑')),
                                ('三合',('申子辰','亥卯未','寅午戌','巳酉丑'))):
            for group in groups:
                self.assertTrue(self.calc('branch_group',relation=relation,branches=group)['listed_group_match'])
                self.assertTrue(self.calc('branch_group',relation=relation,branches=group[::-1])['listed_group_match'])
        self.assertTrue(self.calc('branch_group',relation='刑',branches='未戌')['listed_group_match'])
        self.assertFalse(self.calc('branch_group',relation='刑',branches='戌未')['listed_group_match'])
        self.assertTrue(self.calc('branch_group',relation='冲',branches='午子')['listed_group_match'])
        self.assertTrue(self.calc('branch_group',relation='自刑',branches='午午')['listed_group_match'])
        self.assertTrue(self.calc('branch_group',relation='三合',branches='辰申子')['listed_group_match'])
        self.assertFalse(self.calc('branch_group',relation='三合',branches='辰申午')['listed_group_match'])
        for row in GOLD['six_instrument_punishments']:
            r=self.calc('instrument_punishment_pair',instrument=row['heaven_instrument'],palace=row['landing_palace'])
            self.assertTrue(r['listed_pair_match']); self.assertEqual(r['professional_applicability'],'reference_only')
        self.assertTrue(self.calc('instrument_punishment_pair',instrument='己',palace=2)['listed_pair_match'])

    def test_wonder_tombs_require_explicit_convention_keep_both_yi_methods(self):
        for row in GOLD['three_qi_tombs']:
            convention='general_wood' if row['heaven_stem']=='乙' and row['landing_palace']==2 else 'stem_life_stage'
            self.assertTrue(self.calc('wonder_tomb',stem=row['heaven_stem'],palace=row['landing_palace'],convention=convention)['listed_pair_match'])
        self.assertFalse(self.calc('wonder_tomb',stem='乙',palace=2,convention='stem_life_stage')['listed_pair_match'])
        missing=self.service.calculate('wonder_tomb',{'stem':'乙','palace':2})
        self.assertEqual(missing['status'],'conditional')
        # Door tomb and stem tomb remain separate source dimensions.
        self.assertEqual(self.calc('stem_life_stage',stem='乙',stage='墓')['branch'],'戌')
        self.assertEqual(self.calc('door_source_profile',door='杜门',palace=2)['source_profiles'][0]['label_as_written'],'入墓')
        for row in GOLD['door_tombs']:
            profiles=self.calc('door_source_profile',door=row['door'],palace=row['landing_palace'])['source_profiles']
            self.assertTrue(any('入墓' in p['label_as_written'] for p in profiles))

    def test_wonder_restraints_do_not_require_both_alternative_conditions(self):
        # Fifth-chapter line 679 gives these OR branches explicitly.
        for stem,palaces,earth_stems in (('丙',(1,),('壬','癸')),('丁',(1,),('壬','癸')),('乙',(6,7),('庚','辛'))):
            for palace in palaces:
                self.assertTrue(self.calc('wonder_restraint_palace',stem=stem,palace=palace)['listed_pair_match'])
            for earth_stem in earth_stems:
                self.assertTrue(self.calc('wonder_restraint_stem',heaven_stem=stem,earth_stem=earth_stem)['listed_pair_match'])
        self.assertTrue(self.calc('wonder_restraint_palace',stem='丙',palace=1)['listed_pair_match'])
        self.assertTrue(self.calc('wonder_restraint_stem',heaven_stem='丙',earth_stem='壬')['listed_pair_match'])
        self.assertFalse(self.calc('wonder_restraint_stem',heaven_stem='丙',earth_stem='庚')['listed_pair_match'])
        self.assertTrue(self.calc('wonder_restraint_palace',stem='乙',palace=7)['listed_pair_match'])

    def test_five_missed_hours_verify_day_hour_consistency_not_outcome(self):
        for row in GOLD['five_not_meeting_hour_expectations']:
            value=self.calc('five_missed_hour',day_stem=row['day_stem'],hour_ganzhi=row['hour_ganzhi'])
            self.assertTrue(value['listed_hour_match']); self.assertIsNone(value['prediction'])
        self.assertFalse(self.calc('five_missed_hour',day_stem='甲',hour_ganzhi='甲子')['listed_hour_match'])
        with self.assertRaises(ValueError): self.service.calculate('five_missed_hour',{'day_stem':'甲','hour_ganzhi':'辛巳'})
        self.assertTrue(self.calc('heavenly_manifest_hour',day_stem='甲',hour_ganzhi='甲子')['listed_hour_match'])
        self.assertFalse(self.calc('heavenly_manifest_hour',day_stem='甲',hour_ganzhi='甲子')['automatic_fuyin_judgment_override'])
        # Fifth-chapter line 543, independently transcribed complete list.
        for stems,hours in (('甲己',('甲子','甲戌')),('乙庚',('甲申',)),('丙辛',('甲午',)),
                            ('丁壬',('甲辰',)),('戊癸',('甲寅',))):
            for stem in stems:
                for hour in hours:
                    self.assertTrue(self.calc('heavenly_manifest_hour',day_stem=stem,hour_ganzhi=hour)['listed_hour_match'])

    def test_all_217_ordered_references_keep_complete_original_conditions(self):
        definitions=(('stem_overlay_expectations','stem_responses',('heaven_stem','earth_stem')),
                     ('door_door_expectations','door_door_responses',('first_door','second_door')),
                     ('door_stem_expectations','door_stem_responses',('door','stem')))
        total=0
        for gold_key,family,keys in definitions:
            for row in GOLD[gold_key]:
                with self.subTest(case=row['key']):
                    result=self.service.reference(family,{k:row[k] for k in keys})
                    self.assertEqual(result['status'],'sources_found'); self.assertEqual(result['total'],1)
                    entry=result['entries'][0]
                    self.assertEqual(entry['record']['source_text'].strip(),row['source_quote'].strip())
                    self.assertEqual(entry['applicability_status'],'reference_only')
                    self.assertEqual(result['role_bindings'],[]); self.assertFalse(result['truncated'])
                    if family=='door_stem_responses':
                        self.assertEqual(entry['record']['stem_plate'],'not_explicitly_identified')
                    if family=='door_door_responses':
                        self.assertEqual(entry['record']['second_door_plate'],'not_explicitly_identified')
                    self.assertTrue(all(s['sha256']==SOURCE_SHAS[5] for s in result['sources'].values()))
                    total+=1
        self.assertEqual(total,217)

    def test_reference_direction_source_condition_disputes_and_missing_fields(self):
        a=self.service.reference('stem_responses',{'heaven_stem':'乙','earth_stem':'辛'})
        b=self.service.reference('stem_responses',{'heaven_stem':'辛','earth_stem':'乙'})
        self.assertNotEqual(a['entries'][0]['record']['source_text'],b['entries'][0]['record']['source_text'])
        r=self.service.reference('wonder_service_pairs',{'heaven_stem':'乙','earth_stem':'辛'})
        row=r['entries'][0]['record']; self.assertTrue(row['disputed'])
        self.assertIn('实践',row['source_text']); self.assertIn('值使',row['author_provisional_requirement'])
        pattern=self.service.reference('auspicious_patterns',{'key':'dragon_return'})['entries'][0]['record']
        self.assertTrue(pattern['exceptions']); self.assertIn('门克宫',pattern['source_text'])
        self.assertEqual(self.service.reference('stem_responses',{'heaven_stem':'甲','earth_stem':'戊'})['status'],'not_found')
        with self.assertRaises(ValueError): self.service.reference('stem_responses',{'invented_plate':'天盘'})

    def test_api_cli_and_actual_sql_reference_entry_share_service(self):
        app=create_app(self.service)
        with patch.object(self.service.knowledge,'reference_dataset',wraps=self.service.knowledge.reference_dataset) as query:
            status,r=request(app,{'family':'stem_responses','filters':{'heaven_stem':'戊','earth_stem':'丙'}},'/v1/reference')
            self.assertEqual(status,'200 OK'); query.assert_called_once_with('stem_responses')
            self.assertEqual(r['mode'],'source_reference_not_prediction')
        output=io.StringIO()
        with redirect_stdout(output): code=main(['--db',str(self.db),'reference','stem_responses','--filters','{"heaven_stem":"戊","earth_stem":"丙"}'])
        self.assertEqual(code,0); self.assertEqual(json.loads(output.getvalue()),r)
        self.assertEqual(request(app,{'family':'stem_responses','filters':[]},'/v1/reference')[0],'400 Bad Request')

    def test_chart_observations_share_same_chart_without_mutating_or_predicting(self):
        args={'dun':'阳遁','bureau':3,'hour_ganzhi':'丁巳','method':'shenqi_ch2_paper_v1'}
        chart=self.service.calculate('symbolic_chart',args)
        status,result=request(create_app(self.service),{'operation':'chart_observations','args':args},'/v1/calculate')
        self.assertEqual(status,'200 OK'); self.assertEqual(result['status'],'computed')
        self.assertEqual(result['chart'],chart['result']); self.assertEqual(result['chart_id'],chart['result']['chart_id'])
        self.assertEqual(len(result['door_palace_observations']),8)
        self.assertEqual(result['door_palace_observations']['9']['result']['classification'],'迫')
        self.assertFalse(result['professional_analysis_completed'])
        model=CapturingFixtureModel(); service=QimenService(self.db,model=model)
        answer=service.ask(Inquiry('我今天考试',casting_method='shenqi_ch2_paper_v1',context={k:v for k,v in args.items() if k!='method'}))
        self.assertEqual(answer['status'],'blocked'); self.assertEqual(model.calls,[])
        self.assertEqual(answer['chart_id'],result['chart_id'])

    def test_snapshot_restore_and_concurrent_evidence_remain_source_scoped(self):
        args={'star':'天蓬星','month_branch':'寅','method':'shenqi_ch4_star_month_v1'}
        expected=self.service.calculate('star_month_strength',args)
        export_snapshot(self.db,self.raw,self.root/'snapshot')
        restore_snapshot(self.root/'snapshot',self.root/'restored.sqlite3',self.root/'restored-raw')
        self.assertEqual(QimenService(self.root/'restored.sqlite3').calculate('star_month_strength',args),expected)
        with ThreadPoolExecutor(max_workers=4) as pool:
            values=list(pool.map(lambda n:self.service.calculate('star_month_strength',args) if n%2==0 else
                self.service.calculate('branch_attribute',{'branch':'子'}),range(8)))
        for n,value in enumerate(values):
            self.assertEqual(value['status'],'computed')
            if n%2: self.assertEqual({e['dataset'] for e in value['evidence']},{'branch_attributes'})

    def test_empty_database_cannot_supply_facts_or_original_reference(self):
        db=self.root/'empty.sqlite3'; initialize(db); service=QimenService(db)
        self.assertEqual(service.calculate('star_month_strength',{'star':'天蓬星','month_branch':'寅','method':'shenqi_ch4_star_month_v1'})['status'],'not_covered')
        self.assertEqual(service.reference('stem_responses',{'heaven_stem':'戊'})['status'],'not_found')
