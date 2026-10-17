"""Supplied pregnancy narratives, source chronology and research-only integration."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import PREGNANCY_SHA
from qimenllm.cli import main
from qimenllm.contracts import Inquiry
from qimenllm.knowledge.chapter02 import install_chapter02
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.pregnancy import install_pregnancy
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.rules.candidates import install_candidates
from support import DatabaseTest, case_content_text
from test_runtime import CapturingFixtureModel, request


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/structured/shenqi'


class PregnancyCaseTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        for number in (1, 2):
            curated = json.loads((DATA/f'chapter{number:02d}_curated.json').read_bytes())
            source = import_chapter(self.db, self.raw,
                (ROOT/'data/snapshots/current/raw'/f"{curated['source_sha256']}.bin").read_bytes(),
                book_key='shenqi-user-text-v1', book_title='神奇之门',
                chapter_key=f'chapter-{number:02d}', chapter_title=curated['chapter_title'],
                sequence=number, origin='actual-source-regression')
            (install_curated if number == 1 else install_chapter02)(
                self.db, source['revision_id'], curated)
        load = lambda name: json.loads((DATA/f'pregnancy_{name}.json').read_bytes())
        self.curated = load('curated')
        self.case_data = load('cases')
        self.gold = load('chart_gold')
        self.candidates = load('rule_candidates')
        self.selection_gold = load('selection_gold')
        source_path = ROOT/'data/snapshots/current/raw'/f'{PREGNANCY_SHA}.bin'
        if not source_path.exists():
            source_path = ROOT/'data/raw_books'/f'{PREGNANCY_SHA}.utf8'
        self.content = source_path.read_bytes()
        self.source = import_chapter(self.db, self.raw, self.content,
            book_key='shenqi-user-text-v1', book_title='神奇之门',
            chapter_key='pregnancy-childbirth', chapter_title='怀孕分娩预测',
            sequence=9, origin='actual-user-supplied-source-regression')
        self.curated_result = install_pregnancy(self.db, self.source['revision_id'], self.curated)
        self.case_result = import_cases(self.db, self.source['revision_id'], self.case_data)
        install_candidates(self.db, self.source['revision_id'], self.candidates)
        self.service = QimenService(self.db)
        self.catalog = self.service.cases('pregnancy-childbirth')['cases']

    def case(self, number, view='full'):
        return self.service.case(self.catalog[number-1]['case_id'], view)

    def chart(self, number, method=None):
        case = self.catalog[number-1]
        chart_ids = [chart for event in case['events'] for chart in event['chart_ids']]
        self.assertEqual(len(chart_ids), 1)
        return self.service.case_chart(case['case_id'], chart_ids[0], method)

    def test_exact_supplied_bytes_six_stories_five_families_and_no_training(self):
        self.assertEqual((len(self.content), len(self.content.decode()), len(self.content.splitlines())),
                         (17843, 7147, 505))
        self.assertEqual(digest(self.content), PREGNANCY_SHA)
        self.assertFalse(self.content.endswith(b'\n'))
        self.assertEqual(len(self.catalog), 6)
        self.assertEqual(self.curated_result['compiled_families_added'], 0)
        with connect(self.db) as conn:
            for table, count in {'cases':6, 'events':6, 'event_families':5, 'charts':6,
                                 'case_records':99, 'evidence_links':180,
                                 'rules':0, 'training_tasks':0, 'dataset_releases':0}.items():
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], count, table)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_complete_story_ranges_and_every_record_preserve_authoritative_bytes(self):
        lines = self.content.decode().splitlines(keepends=True)
        ranges = ((60,127), (128,203), (204,265), (266,333), (334,416), (417,505))
        for number, (first,last) in enumerate(ranges, 1):
            full = self.case(number)
            self.assertEqual(full['source']['text'], ''.join(lines[first-1:last]))
            self.assertEqual(full['source_completeness'], 'confirmed_complete')
            for event in full['events']:
                for record in event['records']:
                    source = record['source']
                    self.assertEqual(record['text'], source['text'])
                    self.assertEqual(record['text'].encode(),
                        self.content[source['byte_start']:source['byte_end']])
        covered = {line for group in self.curated['groups']
                   for line in range(group['line_start'], group['line_end']+1)}
        self.assertEqual(covered, set(range(1,506)))

    def test_all_fifty_four_rows_match_independently_transcribed_source_gold(self):
        total = 0
        for gold in self.gold['cases']:
            chart = self.chart(gold['case_number'])
            self.assertEqual(chart['status'], 'projected')
            self.assertEqual(len(chart['palaces']), 9)
            for row in gold['source_rows']:
                palace = chart['palaces'][str(row['palace'])]
                expected = row['interpretation']
                self.assertEqual(palace['source']['line'], row['line'])
                self.assertEqual(palace['source']['text'].rstrip('\r\n'), row['raw_line'])
                self.assertEqual(palace['earth_stem'], expected['earth_stem'])
                if row['palace'] != 5:
                    for actual_key, gold_key in (('door','door'), ('star','primary_star'),
                                                 ('deity','deity'), ('heaven_stem','primary_heaven_stem')):
                        self.assertEqual(palace[actual_key], expected[gold_key])
                    self.assertEqual(palace['heaven_prefix_marker'], expected['door_prefix_raw'] or None)
                    self.assertEqual(palace['star_prefix_marker'], expected['star_prefix_raw'] or None)
                total += 1
            self.assertFalse(chart['original_chart_modified'])
            self.assertFalse(chart['engine_verified'])
            self.assertFalse(chart['calendar_recomputed'])
        self.assertEqual(total, 54)

    def test_first_two_consultations_share_event_family_without_sharing_events_or_charts(self):
        first, second = self.case(1)['events'][0], self.case(2)['events'][0]
        self.assertEqual(first['family_id'], second['family_id'])
        self.assertNotEqual(first['event_id'], second['event_id'])
        self.assertNotEqual(first['charts'][0]['chart_id'], second['charts'][0]['chart_id'])
        self.assertNotIn('11月21日', case_content_text(self.case(1)))
        with self.assertRaises(KeyError):
            self.service.case_chart(self.catalog[0]['case_id'], second['charts'][0]['chart_id'])

    def test_symbol_comparison_matches_listed_fields_but_preserves_case_three_difference(self):
        for number in (1,2,4,5,6):
            chart = self.chart(number, 'shenqi_ch2_paper_v1')
            comparison = chart['comparison']
            self.assertEqual(comparison['status'], 'matches', comparison)
            self.assertTrue(all(row['matches'] for row in comparison['checks']))
            self.assertEqual(comparison['source_chart_id'], chart['chart_id'])
            self.assertNotEqual(comparison['computed_chart_id'], chart['chart_id'])
            self.assertFalse(comparison['engine_verified'])
            self.assertFalse(comparison['calendar_recomputed'])
            self.assertFalse(comparison['source_rejected'])
        third = self.chart(3, 'shenqi_ch2_paper_v1')
        self.assertEqual(third['comparison']['status'], 'mismatch')
        self.assertFalse(third['comparison']['source_rejected'])
        self.assertEqual(third['palaces']['4']['source']['column_cells'], ['巽四宫','虎','杜庚','辅辛'])
        self.assertEqual(third['palaces']['4']['earth_stem'], '辛')
        self.assertEqual(third['palaces']['4']['heaven_stem'], '庚')
        self.assertEqual(third['palaces']['5']['earth_stem'], '庚')
        self.assertNotIn('comparison', self.chart(3))

    def test_conception_background_is_known_but_conception_forecast_and_feedback_are_withheld(self):
        before = case_content_text(self.case(1, 'before_prediction'))
        for known in ('1971', '1995年夏天结婚', '1996年生育指标', '什么时候怀孕'):
            self.assertIn(known, before)
        for later in ('到1996年正月怀孕', '寅月填实', '头胎怀男孩之象', '果然到'):
            self.assertNotIn(later, before)
        records = self.case(1)['events'][0]['records']
        feedback = next(record for record in records if record['text'].startswith('他们听从'))
        self.assertEqual(feedback['kind'], 'feedback')
        self.assertEqual(feedback['knowledge_phase'], 'post_feedback')

    def test_hospital_due_date_is_new_information_before_a_distinct_continuation(self):
        before = case_content_text(self.case(2, 'before_prediction'))
        for later in ('医院给定的预产期', '11月21日', '庚申日', '凌晨3点零5分', '顺利生下一男孩'):
            self.assertNotIn(later, before)
        records = self.case(2)['events'][0]['records']
        initial = next(record for record in records if '应断11月19日庚申日' in record['text'])
        hospital = next(record for record in records if record['text'].startswith('但听老伴讲'))
        revised = next(record for record in records if record['text'].startswith('据此，我又按阴日'))
        self.assertEqual((initial['kind'], initial['knowledge_phase']), ('timing','prediction'))
        self.assertEqual((hospital['kind'], hospital['knowledge_phase']), ('feedback','post_feedback'))
        self.assertEqual((revised['kind'], revised['knowledge_phase']), ('continuation','post_feedback'))
        self.assertLess(initial['sequence'], hospital['sequence'])
        self.assertLess(hospital['sequence'], revised['sequence'])
        self.assertIn('到底是男是女，我也拿不准了', case_content_text(self.case(2)))

    def test_teacher_initial_view_excludes_forecast_later_chart_and_birth_report(self):
        before = self.case(3, 'before_prediction')
        text = case_content_text(before)
        self.assertIn('忧闷', text)
        for later in ('明天上午7至9点', '女孩', '辰时生了', '全盘伏吟', '乙丑日辰时'):
            self.assertNotIn(later, text)
        self.assertEqual(len(before['events'][0]['records']), 2)
        self.assertEqual(before['events'][0]['charts'], [])
        records = self.case(3)['events'][0]['records']
        original = next(record for record in records if record['text'].startswith('干支历为'))
        self.assertEqual(original['knowledge_phase'], 'unknown')

    def test_prematurity_request_does_not_preload_cause_operation_or_actual_birth(self):
        before = case_content_text(self.case(4, 'before_prediction'))
        self.assertIn('要早产', before)
        for later in ('冲击造成早产', '戊戌时', '剖腹产', '母子均平安健康', '我进行了修改加工'):
            self.assertNotIn(later, before)
        full = self.case(4)
        editorial = next(record for record in full['events'][0]['records']
                         if record['text'].startswith('张志春按：'))
        self.assertEqual(editorial['speaker'], '张志春')
        self.assertIn('我进行了修改加工', editorial['text'])

    def test_wang_haiyan_feedback_and_editorial_lessons_are_not_initial_evidence(self):
        before = case_content_text(self.case(5, 'before_prediction'))
        for later in ('2月9日', '壬午日壬寅时', '三天内出生', '我进行了修改加工', '并不十分准确'):
            self.assertNotIn(later, before)
        records = self.case(5)['events'][0]['records']
        editorial = next(record for record in records if record['text'].startswith('张志春按：'))
        self.assertEqual(editorial['speaker'], '张志春')
        self.assertEqual(editorial['knowledge_phase'], 'post_feedback')
        self.assertTrue(any('不能一见五不遇时' in record['text'] for record in records))
        self.assertTrue(any('并不十分准确' in record['text'] for record in records))

    def test_prior_ultrasound_suspicion_is_available_but_normal_result_and_birth_are_not(self):
        before = case_content_text(self.case(6, 'before_prediction'))
        for known in ('B超检查', '羊水过多', '怀疑胎儿有畸形', '是保留还是做流产'):
            self.assertIn(known, before)
        for later in ('以时干为胎儿', '丙下又临丁奇', '胎儿正常', '胎儿一切正常',
                      '6.6斤', '6月19日', '安心保胎', '检查的不认真不仔细'):
            self.assertNotIn(later, before)
        full = self.case(6)
        records = full['events'][0]['records']
        forecast = next(record for record in records if '胎儿体重6斤左右' in record['text'])
        outcome = next(record for record in records if '体重6.6斤' in record['text'])
        self.assertEqual((forecast['kind'], forecast['knowledge_phase']), ('prediction','prediction'))
        self.assertEqual((outcome['kind'], outcome['knowledge_phase']), ('outcome','post_feedback'))
        self.assertNotIn('6.6斤', case_content_text(forecast['payload']))
        self.assertNotIn('6月19日', case_content_text(forecast['payload']))

    def test_source_confirmation_honors_user_attestation_without_claiming_system_external_verification(self):
        for number in range(1,7):
            for view in ('full','before_prediction'):
                full = self.case(number, view)
                confirmation = full['source_confirmation']
                self.assertTrue(confirmation['source_facts_user_confirmed'])
                self.assertTrue(confirmation['user_declares_independent_verification'])
                self.assertEqual(confirmation['verification_basis'], 'user_attestation')
                self.assertFalse(confirmation['system_performed_independent_verification'])
                if view == 'before_prediction':
                    self.assertFalse(full['outcome_independently_verified'])
                    self.assertNotIn('outcome_confirmation', full)
        self.assertTrue(self.case(1)['outcome_independently_verified'])
        self.assertEqual(self.case(1)['outcome_confirmation']['recorded_outcome_roles'],
                         ['reported_first_lunar_month_conception'])
        self.assertTrue(self.case(3)['outcome_independently_verified'])
        self.assertTrue(self.case(6)['outcome_independently_verified'])
        self.assertFalse(self.case(6)['outcome_confirmation']['prediction_accuracy_evaluated'])

    def test_conditional_selection_gold_runs_through_real_database_without_formal_bindings(self):
        self.assertEqual(len(self.selection_gold['selection_cases']), 68)
        for gold in self.selection_gold['selection_cases']:
            result = self.service.rule_candidates(gold['context'], **gold['inspection_filters'])
            selected = next(candidate for candidate in result['candidates']
                            if candidate['candidate_key'] == gold['expected']['candidate_key'])
            self.assertEqual(selected['symbolic_status'], gold['expected']['symbolic_status'], gold['key'])
            self.assertEqual(selected['activation_status'], 'reference_only')
            self.assertEqual(selected['source_acceptance'], 'confirmed')
            self.assertEqual(result['role_bindings'], [])
            if 'missing_fields' in gold['expected']:
                self.assertEqual(selected['missing'], gold['expected']['missing_fields'])

    def test_actual_ask_retrieves_candidates_while_skipping_model_and_formal_prediction(self):
        model = CapturingFixtureModel()
        service = QimenService(self.db, model=model)
        gold = self.selection_gold['selection_cases'][0]
        with patch.object(service, 'rule_candidates', wraps=service.rule_candidates) as query:
            result = service.ask(Inquiry('研究古籍孕产方法的适用条件',
                domain='pregnancy_childbirth', context=gold['context'],
                method_id=gold['inspection_filters']['method']))
            query.assert_called_once()
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(model.calls, [])
        self.assertEqual(result['rule_ids'], [])
        selection = next(stage for stage in result['trace'] if stage['stage'] == 'selection')
        self.assertTrue(selection['source_candidates'])
        expected_keys = {candidate['key'] for candidate in self.candidates['candidates']}
        self.assertEqual(len(expected_keys), 14)
        self.assertEqual({candidate['candidate_key'] for candidate in selection['source_candidates']}, expected_keys)

    def test_reference_case_catalog_and_same_chart_identity_through_api_and_cli(self):
        total = 0
        for group in self.curated['groups']:
            if group.get('dataset'):
                reference = self.service.reference(group['dataset']['key'], {})
                total += reference['total']
                self.assertFalse(reference['truncated'])
                self.assertEqual(reference['role_bindings'], [])
        self.assertEqual(total, 34)
        status, result = request(create_app(self.service),
            {'chapter_key':'pregnancy-childbirth'}, '/v1/cases')
        self.assertEqual(status, '200 OK')
        self.assertEqual(result, self.service.cases('pregnancy-childbirth'))
        case = self.catalog[5]
        chart_id = case['events'][0]['chart_ids'][0]
        status, result = request(create_app(self.service), {'case_id':case['case_id'],
            'chart_id':chart_id, 'comparison_method':'shenqi_ch2_paper_v1'}, '/v1/case-chart')
        self.assertEqual(status, '200 OK')
        self.assertEqual(result, self.chart(6, 'shenqi_ch2_paper_v1'))
        output = io.StringIO()
        with redirect_stdout(output):
            main(['--db',str(self.db),'case-chart',case['case_id'],chart_id,
                  '--comparison-method','shenqi_ch2_paper_v1'])
        self.assertEqual(json.loads(output.getvalue()), result)

    def test_reimport_is_idempotent_and_tampered_cases_fail_without_database_mutation(self):
        with connect(self.db) as conn:
            before = conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        self.assertEqual(install_pregnancy(self.db,self.source['revision_id'],self.curated)['structured_records_added'],0)
        self.assertTrue(import_cases(self.db,self.source['revision_id'],self.case_data)['duplicate'])
        self.assertEqual(install_candidates(self.db,self.source['revision_id'],self.candidates)['added'],0)
        for mode in ('source_hash','future_payload'):
            bad = copy.deepcopy(self.case_data)
            if mode == 'source_hash':
                bad['source_sha256'] = '0'*64
            else:
                prediction = next(record for record in bad['cases'][0]['events'][0]['records']
                                  if record['kind'] == 'prediction')
                prediction['payload']['feedback_not_available_yet'] = ['future result']
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                import_cases(self.db,self.source['revision_id'],bad)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0], before)

    def test_snapshot_recovers_original_views_confirmations_families_and_condition_queries(self):
        export_snapshot(self.db, self.raw, self.root/'snapshot')
        restore_snapshot(self.root/'snapshot', self.root/'restored.sqlite3', self.root/'restored-raw')
        restored = QimenService(self.root/'restored.sqlite3')
        self.assertEqual(restored.cases(), self.service.cases())
        for case in self.catalog:
            for view in ('full','before_prediction'):
                self.assertEqual(restored.case(case['case_id'],view), self.service.case(case['case_id'],view))
            for event in case['events']:
                for chart in event['chart_ids']:
                    self.assertEqual(restored.case_chart(case['case_id'],chart),
                                     self.service.case_chart(case['case_id'],chart))
        gold = self.selection_gold['selection_cases'][0]
        self.assertEqual(restored.rule_candidates(gold['context'],**gold['inspection_filters']),
                         self.service.rule_candidates(gold['context'],**gold['inspection_filters']))

    def test_every_before_prediction_view_excludes_payload_targets_and_feedback(self):
        self.assertEqual([len(self.case(number,'before_prediction')['events'][0]['records'])
                          for number in range(1,7)], [4,2,2,2,2,4])
        for number in range(1,7):
            before = self.case(number,'before_prediction')
            self.assertFalse(before['training_export'])
            for event in before['events']:
                self.assertTrue(event['withheld_background'])
                self.assertNotIn('background',event)
                for record in event['records']:
                    self.assertEqual(record['knowledge_phase'],'pre_prediction')
                    self.assertNotIn(record['kind'],('prediction','feedback','outcome','continuation'))
                    self.assertNotIn('payload',record)
                    self.assertLess(record['sequence'],event['cutoff_sequence'])

    def test_canonical_symbol_revision_keeps_history_and_queries_only_latest_conditions(self):
        key='pregnancy_kun_star_mother_fetus'
        with connect(self.db) as conn:
            revisions=[row[0] for row in conn.execute('''SELECT COALESCE(json_extract(payload_json,'$.record_revision'),1)
                FROM knowledge_items WHERE json_extract(payload_json,'$.candidate.key')=?
                ORDER BY json_extract(payload_json,'$.record_revision')''',(key,))]
        self.assertEqual(revisions,[1,2])
        for star,status in (('天心星','applicable'),('天心','excluded'),(False,'excluded')):
            result=self.service.rule_candidates({'analysis_context':'maternal_fetal_role_reference',
                'kun_heaven_star':star},'pregnancy_childbirth','shenqi_pregnancy_kun_star_v1')
            selected=[candidate for candidate in result['candidates'] if candidate['candidate_key']==key]
            self.assertEqual(len(selected),1)
            self.assertEqual(selected[0]['record_revision'],2)
            self.assertEqual(selected[0]['symbolic_status'],status)
            self.assertEqual(result['role_bindings'],[])
