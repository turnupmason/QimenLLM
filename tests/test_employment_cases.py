"""User-confirmed employment narratives, chronology and real runtime integration."""
import copy
import io
import json
import sqlite3
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import EMPLOYMENT_SHA
from qimenllm.cli import main
from qimenllm.contracts import Inquiry
from qimenllm.knowledge.chapter02 import install_chapter02
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.employment import install_employment
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.rules.candidates import install_candidates
from support import DatabaseTest, case_content_text
from test_runtime import CapturingFixtureModel, request


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structured/shenqi'


class EmploymentCaseTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        for number in (1, 2):
            curated = json.loads((DATA / f'chapter{number:02d}_curated.json').read_bytes())
            source = import_chapter(self.db, self.raw,
                (ROOT / 'data/snapshots/current/raw' / f"{curated['source_sha256']}.bin").read_bytes(),
                book_key='shenqi-user-text-v1', book_title='神奇之门',
                chapter_key=f'chapter-{number:02d}', chapter_title=curated['chapter_title'],
                sequence=number, origin='actual-source-regression')
            (install_curated if number == 1 else install_chapter02)(
                self.db, source['revision_id'], curated)
        load = lambda name: json.loads((DATA / f'employment_{name}.json').read_bytes())
        self.curated = load('curated')
        self.case_data = load('cases')
        self.gold = load('chart_gold')
        self.candidates = load('rule_candidates')
        self.selection_gold = load('selection_gold')
        self.provenance = json.loads((ROOT / 'data/provenance/employment_inline_input.json').read_bytes())
        self.message = (ROOT / self.provenance['message_path']).read_bytes()
        self.content = self.message[self.provenance['source_byte_start']:self.provenance['source_byte_end']]
        self.source = import_chapter(self.db, self.raw, self.content,
            book_key='shenqi-user-text-v1', book_title='神奇之门',
            chapter_key='work-employment', chapter_title='工作就业预测',
            sequence=11, origin='actual-user-supplied-inline-chat-regression')
        self.curated_result = install_employment(self.db, self.source['revision_id'], self.curated)
        self.case_result = import_cases(self.db, self.source['revision_id'], self.case_data)
        install_candidates(self.db, self.source['revision_id'], self.candidates)
        self.service = QimenService(self.db)
        self.catalog = self.service.cases('work-employment')['cases']

    def case(self, number, view='full'):
        return self.service.case(self.catalog[number - 1]['case_id'], view)

    def records(self, number):
        return [record for event in self.case(number)['events'] for record in event['records']]

    def record_containing(self, number, text):
        matches = [record for record in self.records(number) if text in record['text']]
        self.assertEqual(len(matches), 1, text)
        return matches[0]

    def chart(self, number, method=None):
        case = self.catalog[number - 1]
        chart_ids = [chart for event in case['events'] for chart in event['chart_ids']]
        self.assertEqual(len(chart_ids), 1)
        return self.service.case_chart(case['case_id'], chart_ids[0], method)

    def test_inline_message_prefix_and_authoritative_chapter_bytes_are_auditable(self):
        self.assertEqual(digest(self.message), self.provenance['message_sha256'])
        self.assertEqual(len(self.message), 22434)
        self.assertEqual(self.message[:13].decode(), '下一个： ')
        self.assertEqual(self.provenance['input_kind'], 'inline_chat_text')
        self.assertFalse(self.provenance['external_uploaded_file_hash_claimed'])
        self.assertEqual((len(self.content), len(self.content.decode()), len(self.content.splitlines())),
                         (22421, 8573, 550))
        self.assertEqual(digest(self.content), EMPLOYMENT_SHA)
        self.assertFalse(self.content.endswith(b'\n'))
        self.assertEqual(self.content, (ROOT / 'data/snapshots/current/raw' / f'{EMPLOYMENT_SHA}.bin').read_bytes())

    def test_five_whole_stories_six_events_five_source_charts_and_no_training(self):
        self.assertEqual(len(self.catalog), 5)
        self.assertEqual(self.curated_result['compiled_families_added'], 0)
        with connect(self.db) as conn:
            for table, count in {'cases': 5, 'events': 6, 'event_families': 5, 'charts': 5,
                                 'case_records': 101, 'evidence_links': 163,
                                 'rules': 0, 'training_tasks': 0, 'dataset_releases': 0}.items():
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], count, table)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_whole_story_ranges_and_all_record_bytes_preserve_the_supplied_source(self):
        lines = self.content.decode().splitlines(keepends=True)
        ranges = ((39, 106), (107, 199), (200, 266), (267, 374), (375, 550))
        for number, (first, last) in enumerate(ranges, 1):
            full = self.case(number)
            self.assertEqual(full['source']['text'], ''.join(lines[first - 1:last]))
            self.assertEqual(full['source_completeness'], 'confirmed_complete')
            for record in self.records(number):
                source = record['source']
                self.assertEqual(record['text'], source['text'])
                self.assertEqual(record['text'].encode(),
                    self.content[source['byte_start']:source['byte_end']])
        covered = {line for group in self.curated['groups']
                   for line in range(group['line_start'], group['line_end'] + 1)}
        self.assertEqual(covered, set(range(1, 551)))

    def test_all_forty_five_source_rows_match_independent_transcription_gold(self):
        total = 0
        citations = 0
        lines = self.content.decode().splitlines(keepends=True)

        def verify_citations(value):
            nonlocal citations
            if isinstance(value, dict):
                if 'source_quote' in value:
                    quote = value['source_quote']
                    self.assertTrue(quote.strip())
                    if 'byte_start' in value and 'byte_end' in value:
                        self.assertEqual(self.content[value['byte_start']:value['byte_end']].decode()
                                         .rstrip('\r\n'), quote.rstrip('\r\n'))
                    if 'line' in value:
                        self.assertEqual(lines[value['line'] - 1].rstrip('\r\n'), quote.rstrip('\r\n'))
                    citations += 1
                if 'source_quotes' in value:
                    self.assertEqual(len(value['source_lines']), len(value['source_quotes']))
                    for line, quote in zip(value['source_lines'], value['source_quotes']):
                        self.assertTrue(quote.strip())
                        self.assertEqual(lines[line - 1].rstrip('\r\n'), quote)
                if 'source_pointer' in value:
                    pointer = value['source_pointer']
                    excerpt = ''.join(lines[pointer['line_start'] - 1:pointer['line_end']])
                    self.assertTrue(excerpt.strip())
                    self.assertEqual(self.content[pointer['byte_start']:pointer['byte_end']].decode()
                                     .rstrip('\r\n'), excerpt.rstrip('\r\n'))
                for child in value.values():
                    verify_citations(child)
            elif isinstance(value, list):
                for child in value:
                    verify_citations(child)

        for artifact in (self.gold, self.curated, self.candidates):
            verify_citations(artifact)
        self.assertGreater(citations, 100)
        self.assertEqual(len(self.gold['cases']), 5)
        for gold in self.gold['cases']:
            chart = self.chart(gold['case_number'])
            self.assertEqual(chart['status'], 'projected')
            self.assertEqual(len(chart['palaces']), 9)
            self.assertEqual(len(gold['source_rows']), 9)
            for row in gold['source_rows']:
                palace = chart['palaces'][str(row['palace'])]
                expected = row['interpretation']
                self.assertEqual(palace['source']['line'], row['line'])
                self.assertEqual(palace['source']['text'].rstrip('\r\n'), row['raw_line'])
                self.assertEqual(palace['earth_stem'], expected['earth_stem'])
                if row['palace'] != 5:
                    for actual_key, gold_key in (('door', 'door'), ('star', 'primary_star'),
                                                 ('deity', 'deity'), ('heaven_stem', 'primary_heaven_stem')):
                        self.assertEqual(palace[actual_key], expected[gold_key])
                    self.assertEqual(palace['heaven_prefix_marker'], expected['door_prefix_raw'] or None)
                    self.assertEqual(palace['star_prefix_marker'], expected['star_prefix_raw'] or None)
                total += 1
            self.assertFalse(chart['original_chart_modified'])
            self.assertFalse(chart['engine_verified'])
            self.assertFalse(chart['calendar_recomputed'])
        self.assertEqual(total, 45)

    def test_explicit_paper_comparison_reports_its_two_uncovered_carried_stem_conventions(self):
        for number in range(1, 6):
            original = self.chart(number)
            compared = self.chart(number, 'shenqi_ch2_paper_v1')
            comparison = compared['comparison']
            self.assertEqual(comparison['checked_field_count'], 47)
            self.assertEqual(comparison['source_chart_id'], original['chart_id'])
            self.assertNotEqual(comparison['computed_chart_id'], original['chart_id'])
            self.assertEqual(compared['palaces'], original['palaces'])
            self.assertEqual(compared['source_metadata'], original['source_metadata'])
            self.assertFalse(comparison['source_rejected'])
            self.assertFalse(comparison['original_chart_modified'])
            self.assertFalse(comparison['engine_verified'])
            self.assertFalse(comparison['calendar_recomputed'])
            mismatches = {check['path']: (check['source_value'], check['computed_value'])
                          for check in comparison['checks'] if not check['matches']}
            if number == 4:
                self.assertEqual(comparison['status'], 'mismatch')
                # Literal source gold was transcribed before calling the engine.
                # This test freezes the currently incomplete carried-stem convention.
                self.assertEqual(mismatches, {'palaces.9.heaven_stem': ('己', '壬'),
                                             'palaces.9.heaven_prefix_marker': ('壬', '己')})
                self.assertEqual(original['palaces']['9']['star'], '天禽星')
                self.assertEqual(original['palaces']['9']['heaven_stem'], '己')
                self.assertEqual(original['palaces']['9']['heaven_prefix_marker'], '壬')
            else:
                self.assertEqual(comparison['status'], 'matches')
                self.assertEqual(mismatches, {})
            self.assertNotIn('comparison', self.chart(number))

    def test_chart_identity_and_cross_case_access_do_not_mix_the_originals(self):
        ids = [self.chart(number)['chart_id'] for number in range(1, 6)]
        self.assertEqual(len(set(ids)), 5)
        for index, case in enumerate(self.catalog):
            with self.assertRaises(KeyError):
                self.service.case_chart(case['case_id'], ids[(index + 1) % 5])
        self.assertEqual(self.chart(1)['source_metadata']['值符'], '天禽星')
        self.assertEqual(self.chart(4)['source_metadata']['值符'], '天禽星')
        self.assertEqual(self.chart(4)['source_metadata']['值符落宫'], '离9宫')
        self.assertEqual(self.chart(4)['palaces']['2']['earth_stem'], '己')
        self.assertEqual(self.chart(4)['palaces']['9']['earth_stem'], '乙')
        for number in range(1, 6):
            self.assertNotIn('comparison', self.chart(number))

    def test_case_one_keeps_du_zhang_review_and_timing_prediction_distinct_from_actual_signing(self):
        before = case_content_text(self.case(1, 'before_prediction'))
        for known in ('南京上大学', '今年暑期毕业', '寒假期间能否签订就业合同'):
            self.assertIn(known, before)
        for later in ('以巽4宫断', '省广播电视厅', '初九甲午日', '己巳时', '当年8月'):
            self.assertNotIn(later, before)
        preliminary = self.record_containing(1, '就以巽4宫逢开门大致断了一下')
        author = self.record_containing(1, '饭后，杜、张二人又到另一雅间')
        timing = self.record_containing(1, '应该以本月辰日或巳日为应期')
        signing = self.record_containing(1, '初九甲午日，己巳时')
        result = self.record_containing(1, '当年8月，顺利分配')
        self.assertLess(preliminary['sequence'], author['sequence'])
        self.assertEqual(preliminary['chart_id'], author['chart_id'])
        self.assertEqual(timing['kind'], 'timing')
        self.assertIn('辰日或巳日', timing['text'])
        self.assertEqual(signing['kind'], 'outcome')
        self.assertEqual(result['kind'], 'outcome')
        self.assertLess(timing['sequence'], signing['sequence'])
        self.assertNotIn('甲午日', case_content_text(timing['payload']))
        self.assertNotIn('己巳时', case_content_text(timing['payload']))

    def test_case_two_mother_son_birth_year_is_known_but_competitive_interference_is_later(self):
        before = case_content_text(self.case(2, 'before_prediction'))
        for known in ('1974', '北京经贸大学', '外经部', '外交部'):
            self.assertIn(known, before)
        for later in ('排在第三名', '排到了第八名', '二班班长', '找学校领导',
                      '及时扭转了被动局面', '1997年暑期'):
            self.assertNotIn(later, before)
        role = self.record_containing(2, '以时干庚代表她儿子')
        self.assertEqual(role['payload']['role_selection_as_written'], {'时干庚': '她儿子', '年命甲寅癸': '她儿子'})
        self.assertNotEqual(role['knowledge_phase'], 'pre_prediction')
        self.assertNotIn(role['text'], before)

    def test_case_two_november_continuation_reuses_original_chart_without_fabricating_a_new_one(self):
        case = self.case(2)
        self.assertEqual(len(case['events']), 1)
        self.assertEqual(len(case['events'][0]['charts']), 1)
        report = self.record_containing(2, '他儿子应排在第三名')
        reuse = self.record_containing(2, '我把11月4日的奇门格局找出来一看')
        advice = self.record_containing(2, '惟一的办法就是找学校领导')
        response = self.record_containing(2, '二班班长把二班的人排了前4名')
        outcome = self.record_containing(2, '1997年暑期毕业后')
        self.assertEqual(report['kind'], 'feedback')
        self.assertEqual(response['speaker'], '范荣')
        self.assertEqual(advice['kind'], 'continuation')
        self.assertEqual(outcome['kind'], 'outcome')
        self.assertLess(report['sequence'], reuse['sequence'])
        self.assertLess(reuse['sequence'], response['sequence'])
        self.assertLess(response['sequence'], advice['sequence'])
        self.assertLess(advice['sequence'], outcome['sequence'])
        chart_id = self.chart(2)['chart_id']
        for record in (reuse, advice):
            self.assertEqual(record['chart_id'], chart_id)

    def test_case_three_attributes_zhang_and_keeps_removal_prediction_separate_from_report(self):
        before = case_content_text(self.case(3, 'before_prediction'))
        self.assertIn('某部一团级军官', before)
        self.assertIn('张顺良按干支历起局', before)
        for later in ('必然被降职', '还有1～2人', '副主任和一个处长', '免去该军官主任职务'):
            self.assertNotIn(later, before)
        forecast = self.record_containing(3, '被降职者不止你一人')
        outcome = self.record_containing(3, '免去该军官主任职务')
        self.assertEqual(forecast['knowledge_phase'], 'prediction')
        self.assertIn('1～2人', forecast['text'])
        self.assertEqual(outcome['kind'], 'outcome')
        self.assertIn('副主任和一个处长', outcome['text'])
        self.assertLess(forecast['sequence'], outcome['sequence'])
        self.assertNotIn('副主任', case_content_text(forecast['payload']))
        self.assertTrue(any('张顺良' in (record['speaker'] or '')
                            for record in self.records(3) if record['kind'] in ('prediction', 'author_reasoning')))

    def test_case_four_two_events_share_one_family_and_only_the_supplied_first_chart(self):
        case = self.case(4)
        self.assertEqual(len(case['events']), 2)
        first, later = case['events']
        self.assertEqual(first['family_id'], later['family_id'])
        self.assertNotEqual(first['event_id'], later['event_id'])
        self.assertEqual(len(first['charts']), 1)
        self.assertEqual(later['charts'], [])
        self.assertIn('这次调动我共预测了五次', case['source']['text'])
        self.assertEqual(len([c for event in case['events'] for c in event['charts']]), 1)
        with connect(self.db) as conn:
            conn.execute("INSERT INTO dataset_releases VALUES ('engineering-group-guard',?,0,?)",
                         (self.source['data_version'], '0' * 64))
            conn.execute("INSERT INTO split_assignments VALUES ('engineering-group-guard',?,'train')",
                         (first['family_id'],))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO split_assignments VALUES ('engineering-group-guard',?,'test')",
                             (later['family_id'],))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("""INSERT INTO case_records VALUES ('engineering-cross-event',?,?,999,
                    'dialogue','unknown',?,NULL,'engineering relation fixture','{}','not_explicit',NULL)""",
                             (later['event_id'], first['charts'][0]['chart_id'], case['source']['source_id']))
        first_input = case_content_text(self.case(4, 'before_prediction')['events'][0])
        for later_text in ('4月21日', '4月27日', '联通河北分公司', '7月28日', '副部长',
                           '事实证明这一判断是正确的', '时干主工作任务'):
            self.assertNotIn(later_text, first_input)

    def test_case_four_june_recast_does_not_expose_july_outcome_or_invent_a_chart(self):
        full = self.case(4)
        later = full['events'][1]
        before = self.case(4, 'before_prediction')['events'][1]
        self.assertEqual(before['charts'], [])
        initial = case_content_text(before)
        self.assertIn('6月1日', initial)
        self.assertIn('人员调动暂时冻结', initial)
        for later_text in ('7月28日', '辛未日', '副部长', '事实证明'):
            self.assertNotIn(later_text, initial)
        prediction = next(record for record in later['records'] if '能调成，只不过是时间长点' in record['text'])
        self.assertEqual(prediction['knowledge_phase'], 'prediction')
        self.assertIsNone(prediction['chart_id'])
        outcome = self.record_containing(4, '阳历7月28日')
        appointment = self.record_containing(4, '一个月后我被任命')
        self.assertEqual((outcome['kind'], appointment['kind']), ('outcome', 'outcome'))
        self.assertEqual((outcome['knowledge_phase'], appointment['knowledge_phase']),
                         ('post_feedback', 'post_feedback'))

    def test_case_four_retrospective_analysis_and_du_voice_are_never_initial_inputs(self):
        retrospective = self.record_containing(4, '时干主工作任务，克日干主工作任务重')
        self.assertNotEqual(retrospective['knowledge_phase'], 'pre_prediction')
        self.assertIn('事实证明这一判断是正确的', retrospective['text'])
        for record in self.records(4):
            if record['kind'] in ('prediction', 'author_reasoning', 'timing'):
                self.assertIn('杜新会', record['speaker'] or '')
        self.assertNotIn('事实证明这一判断是正确的',
                         case_content_text(self.case(4, 'before_prediction')))

    def test_case_five_explicit_home_positions_are_known_without_exposing_role_analysis_payload(self):
        role = self.record_containing(5, '尚明吉写入坤2宫')
        for name, palace in (('尚明吉', '坤2宫'), ('尚耀坤', '乾6宫'), ('尚文才', '巽4宫'),
                             ('张相如', '震3宫'), ('尚用成', '坎1宫')):
            self.assertIn(name, role['text'])
            self.assertIn(palace, role['text'])
        self.assertEqual(role['payload']['bindings_as_written'], [
            {'person_as_written': '尚明吉', 'palace': 2}, {'person_as_written': '尚耀坤', 'palace': 6},
            {'person_as_written': '尚文才', 'palace': 4}, {'person_as_written': '张相如', 'palace': 3},
            {'person_as_written': '尚用成', 'palace': 1}])
        initial = self.case(5, 'before_prediction')
        before = case_content_text(initial)
        self.assertIn('尚明吉写入坤2宫', before)
        self.assertNotIn('bindings_as_written', before)
        for later in ('尚耀坤第一', '尚明吉第二', '张相如第三', '尚文才第四', '尚用成第五',
                      '只比较各宫旺相休囚就行了'):
            self.assertNotIn(later, before)

    def test_case_five_only_two_places_were_forecast_and_full_ranking_arrives_as_result(self):
        forecast = self.record_containing(5, '只求第一、二名即可')
        self.assertEqual(forecast['kind'], 'prediction')
        self.assertIn('尚耀坤第一', forecast['text'])
        self.assertIn('尚明吉第二', forecast['text'])
        for later in ('张相如第三', '尚文才第四', '尚用成第五'):
            self.assertNotIn(later, forecast['text'])
            self.assertNotIn(later, case_content_text(forecast['payload']))
            outcomes = [record for record in self.records(5) if later in record['text'] and record['kind'] == 'outcome']
            self.assertEqual(len(outcomes), 1)
            outcome = outcomes[0]
            self.assertEqual(outcome['kind'], 'outcome')
            self.assertEqual(outcome['knowledge_phase'], 'post_feedback')
            self.assertGreater(outcome['sequence'], forecast['sequence'])

    def test_case_five_student_scientific_claim_and_zhang_commentary_keep_source_attribution(self):
        claim = self.record_containing(5, '她是真正的高级预测术')
        self.assertIn('尚瓴吉', claim['speaker'])
        self.assertNotEqual(claim['knowledge_phase'], 'pre_prediction')
        commentary = self.record_containing(5, '只比较各宫旺相休囚就行了')
        self.assertIn('张志春', commentary['speaker'])
        self.assertEqual(commentary['knowledge_phase'], 'post_feedback')
        self.assertNotEqual(commentary['kind'], 'prediction')
        self.assertEqual(self.record_containing(5, '3宫张相如第三，4宫尚文才第四')['knowledge_phase'],
                         'post_feedback')

    def test_confirmation_is_user_attestation_and_not_new_program_verification(self):
        for number in range(1, 6):
            for view in ('full', 'before_prediction'):
                case = self.case(number, view)
                confirmation = case['source_confirmation']
                self.assertTrue(confirmation['source_facts_user_confirmed'])
                self.assertTrue(confirmation['user_declares_independent_verification'])
                self.assertEqual(confirmation['verification_basis'], 'user_attestation')
                self.assertFalse(confirmation['system_performed_independent_verification'])
                if view == 'before_prediction':
                    self.assertFalse(case['outcome_independently_verified'])
                    self.assertNotIn('outcome_confirmation', case)
            self.assertTrue(self.case(number)['outcome_independently_verified'])
            self.assertFalse(self.case(number)['outcome_confirmation']['prediction_accuracy_evaluated'])

    def test_condition_gold_executes_actual_sql_without_enabling_professional_roles(self):
        self.assertEqual(len(self.candidates['candidates']), 27)
        self.assertEqual(len(self.selection_gold['selection_cases']), 256)
        statuses = set()
        for gold in self.selection_gold['selection_cases']:
            result = self.service.rule_candidates(gold['context'], **gold['inspection_filters'])
            matches = [candidate for candidate in result['candidates']
                       if candidate['candidate_key'] == gold['expected']['candidate_key']]
            self.assertEqual(len(matches), 1, gold['key'])
            selected = matches[0]
            self.assertEqual(selected['symbolic_status'], gold['expected']['symbolic_status'], gold['key'])
            self.assertEqual(selected['activation_status'], 'reference_only')
            self.assertEqual(selected['source_acceptance'], 'confirmed')
            self.assertEqual(result['role_bindings'], [])
            statuses.add(selected['symbolic_status'])
            if 'missing_fields' in gold['expected']:
                self.assertEqual(selected['missing'], gold['expected']['missing_fields'])
        self.assertIn('applicable', statuses)
        self.assertIn('conditional', statuses)
        self.assertIn('excluded', statuses)

    def test_official_ask_retrieves_real_candidates_and_explicitly_skips_model_and_prediction(self):
        gold = self.selection_gold['selection_cases'][0]
        model = CapturingFixtureModel()
        service = QimenService(self.db, model=model)
        filters = gold['inspection_filters']
        with patch.object(service, 'rule_candidates', wraps=service.rule_candidates) as query:
            result = service.ask(Inquiry('研究古籍工作就业方法的条件',
                domain=filters['domain'], context=gold['context'], method_id=filters.get('method')))
            query.assert_called_once()
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['rule_ids'], [])
        self.assertEqual(model.calls, [])
        selection = next(stage for stage in result['trace'] if stage['stage'] == 'selection')
        self.assertTrue(selection['source_candidates'])
        self.assertEqual({candidate['candidate_key'] for candidate in selection['source_candidates']},
                         {candidate['key'] for candidate in self.candidates['candidates']})

    def test_reference_learning_api_and_cli_share_the_original_source_chart(self):
        total = 0
        for group in self.curated['groups']:
            if group.get('dataset'):
                result = self.service.reference(group['dataset']['key'], {})
                self.assertFalse(result['truncated'])
                self.assertEqual(result['role_bindings'], [])
                total += result['total']
        self.assertEqual(total, 42)
        status, result = request(create_app(self.service), {'chapter_key': 'work-employment'}, '/v1/cases')
        self.assertEqual(status, '200 OK')
        self.assertEqual(result, self.service.cases('work-employment'))
        case = self.catalog[3]
        chart_id = case['events'][0]['chart_ids'][0]
        status, result = request(create_app(self.service),
            {'case_id': case['case_id'], 'chart_id': chart_id}, '/v1/case-chart')
        self.assertEqual(status, '200 OK')
        self.assertEqual(result, self.chart(4))
        output = io.StringIO()
        with redirect_stdout(output):
            main(['--db', str(self.db), 'case-chart', case['case_id'], chart_id])
        self.assertEqual(json.loads(output.getvalue()), result)

    def test_reimport_is_idempotent_and_tampering_or_future_payload_fails_atomically(self):
        with connect(self.db) as conn:
            before = conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        self.assertEqual(install_employment(self.db, self.source['revision_id'], self.curated)['structured_records_added'], 0)
        self.assertTrue(import_cases(self.db, self.source['revision_id'], self.case_data)['duplicate'])
        self.assertEqual(install_candidates(self.db, self.source['revision_id'], self.candidates)['added'], 0)
        for mode in ('source_hash', 'record_text', 'future_payload'):
            bad = copy.deepcopy(self.case_data)
            if mode == 'source_hash':
                bad['source_sha256'] = '0' * 64
            elif mode == 'record_text':
                bad['cases'][0]['events'][0]['records'][0]['text'] += ' changed'
            else:
                prediction = next(record for record in bad['cases'][0]['events'][0]['records']
                                  if record['kind'] == 'prediction')
                prediction['payload']['feedback_not_available_yet'] = ['future result']
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                import_cases(self.db, self.source['revision_id'], bad)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0], before)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_snapshot_restores_two_event_family_original_charts_confirmations_and_real_queries(self):
        export_snapshot(self.db, self.raw, self.root / 'snapshot')
        restore_snapshot(self.root / 'snapshot', self.root / 'restored.sqlite3', self.root / 'restored-raw')
        restored = QimenService(self.root / 'restored.sqlite3')
        self.assertEqual(restored.cases(), self.service.cases())
        for case in self.catalog:
            for view in ('full', 'before_prediction'):
                self.assertEqual(restored.case(case['case_id'], view), self.service.case(case['case_id'], view))
            for event in case['events']:
                for chart in event['chart_ids']:
                    self.assertEqual(restored.case_chart(case['case_id'], chart),
                                     self.service.case_chart(case['case_id'], chart))
        gold = self.selection_gold['selection_cases'][0]
        self.assertEqual(restored.rule_candidates(gold['context'], **gold['inspection_filters']),
                         self.service.rule_candidates(gold['context'], **gold['inspection_filters']))

    def test_all_initial_views_withhold_unrestricted_background_targets_roles_and_later_records(self):
        for number in range(1, 6):
            before = self.case(number, 'before_prediction')
            self.assertFalse(before['training_export'])
            self.assertNotIn('source', before)
            self.assertNotIn('title', before)
            for event in before['events']:
                self.assertTrue(event['withheld_background'])
                self.assertNotIn('background', event)
                self.assertNotIn('narrative_sources', event)
                for record in event['records']:
                    self.assertEqual(record['knowledge_phase'], 'pre_prediction')
                    self.assertNotIn(record['kind'], ('prediction', 'feedback', 'outcome', 'continuation', 'role_selection'))
                    self.assertNotIn('payload', record)
                    self.assertNotIn('chart_id', record)
                    self.assertLess(record['sequence'], event['cutoff_sequence'])
