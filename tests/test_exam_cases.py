"""Supplied examination narratives: immutable source, chronology and real integration."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import EXAM_SHA
from qimenllm.cli import main
from qimenllm.contracts import Inquiry
from qimenllm.knowledge.chapter02 import install_chapter02
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.exam import install_exam
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.rules.candidates import install_candidates
from support import DatabaseTest, case_content_text
from test_runtime import CapturingFixtureModel, request


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structured/shenqi'


class ExamCaseTests(DatabaseTest):
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
        load = lambda name: json.loads((DATA / f'exam_{name}.json').read_bytes())
        self.curated = load('curated')
        self.case_data = load('cases')
        self.gold = load('chart_gold')
        self.candidates = load('rule_candidates')
        self.selection_gold = load('selection_gold')
        self.content = (ROOT / 'data/snapshots/current/raw' / f'{EXAM_SHA}.bin').read_bytes()
        self.source = import_chapter(self.db, self.raw, self.content,
            book_key='shenqi-user-text-v1', book_title='神奇之门',
            chapter_key='education-examinations', chapter_title='求学考试预测',
            sequence=10, origin='actual-user-supplied-source-regression')
        self.curated_result = install_exam(self.db, self.source['revision_id'], self.curated)
        self.case_result = import_cases(self.db, self.source['revision_id'], self.case_data)
        install_candidates(self.db, self.source['revision_id'], self.candidates)
        self.service = QimenService(self.db)
        self.catalog = self.service.cases('education-examinations')['cases']

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

    def test_exact_supplied_bytes_five_stories_original_charts_and_no_training(self):
        self.assertEqual((len(self.content), len(self.content.decode()), len(self.content.splitlines())),
                         (18832, 7326, 446))
        self.assertEqual(digest(self.content), EXAM_SHA)
        self.assertFalse(self.content.endswith(b'\n'))
        self.assertEqual(len(self.catalog), 5)
        self.assertEqual(self.curated_result['compiled_families_added'], 0)
        with connect(self.db) as conn:
            for table, count in {'cases': 5, 'events': 5, 'event_families': 5, 'charts': 5,
                                 'case_records': 93, 'evidence_links': 165,
                                 'rules': 0, 'training_tasks': 0, 'dataset_releases': 0}.items():
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], count, table)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_whole_story_ranges_and_each_record_preserve_authoritative_bytes(self):
        lines = self.content.decode().splitlines(keepends=True)
        ranges = ((55, 120), (121, 180), (181, 250), (251, 308), (309, 446))
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
        self.assertEqual(covered, set(range(1, 447)))

    def test_all_forty_five_rows_match_independently_transcribed_source_gold(self):
        total = 0
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

    def test_chart_identities_are_distinct_and_cross_case_access_is_rejected(self):
        ids = [self.chart(number)['chart_id'] for number in range(1, 6)]
        self.assertEqual(len(set(ids)), 5)
        for index, case in enumerate(self.catalog):
            with self.assertRaises(KeyError):
                self.service.case_chart(case['case_id'], ids[(index + 1) % 5])
        fifth = self.chart(5)
        self.assertEqual(fifth['source_metadata']['值符落宫'], '中5宫寄坤2宫')
        self.assertEqual(fifth['source_metadata']['原书说明'], '值使惊门伏吟')
        self.assertEqual(fifth['palaces']['5']['earth_stem'], '癸')
        self.assertEqual(fifth['palaces']['9']['heaven_prefix_marker'], '癸')
        self.assertNotIn('comparison', fifth)

    def test_explicit_paper_method_comparison_preserves_source_identity_and_limited_scope(self):
        for number in range(1, 6):
            chart = self.chart(number, 'shenqi_ch2_paper_v1')
            comparison = chart['comparison']
            self.assertEqual(comparison['status'], 'matches', comparison)
            self.assertEqual(comparison['checked_field_count'], 48 if number == 5 else 47)
            self.assertTrue(all(check['matches'] for check in comparison['checks']))
            self.assertEqual(comparison['source_chart_id'], chart['chart_id'])
            self.assertNotEqual(comparison['computed_chart_id'], chart['chart_id'])
            self.assertFalse(comparison['source_rejected'])
            self.assertFalse(comparison['original_chart_modified'])
            self.assertFalse(comparison['engine_verified'])
            self.assertFalse(comparison['calendar_recomputed'])
            self.assertNotIn('comparison', self.chart(number))
        fifth = self.chart(5, 'shenqi_ch2_paper_v1')['comparison']
        paths = {check['path'] for check in fifth['checks']}
        self.assertIn('source_metadata.值符落宫.original', paths)
        self.assertIn('source_metadata.值符落宫.hosted', paths)

    def test_dai_estimate_birth_year_health_and_admission_are_not_initial_evidence(self):
        before = case_content_text(self.case(1, 'before_prediction'))
        self.assertIn('高考刚结束', before)
        for later in ('六百分以上', '六百二十分', '1977', '年命丁在兑7宫', '眼睛近视',
                      '清华大学', '应用物理系', '西安交通大学'):
            self.assertNotIn(later, before)
        estimate = self.record_containing(1, '自己估分六百二十分')
        birth = self.record_containing(1, '1977年（丁巳年）出生')
        continuation = self.record_containing(1, '你儿子考上重点大学不成问题')
        outcome = self.record_containing(1, '顺利被清华大学应用物理系录取')
        self.assertEqual((estimate['kind'], birth['kind']), ('feedback', 'feedback'))
        self.assertEqual(continuation['kind'], 'continuation')
        self.assertEqual(outcome['kind'], 'outcome')
        self.assertLess(estimate['sequence'], birth['sequence'])
        self.assertLess(birth['sequence'], continuation['sequence'])
        self.assertLess(continuation['sequence'], outcome['sequence'])

    def test_editor_birth_year_and_self_funded_result_follow_the_initial_judgment(self):
        before = case_content_text(self.case(2, 'before_prediction'))
        self.assertIn('出版社女编辑', before)
        for later in ('1975', '先天不足', '从小就多病', '四百多分', '自费学校', '准备自费上学'):
            self.assertNotIn(later, before)
        first = self.record_containing(2, '你儿子先天不足')
        birth = self.record_containing(2, '他是1975年')
        revised = self.record_containing(2, '准备自费上学吧')
        outcome = self.record_containing(2, '儿子仅考了四百多分')
        self.assertEqual(first['kind'], 'prediction')
        self.assertEqual((birth['kind'], birth['knowledge_phase']), ('feedback', 'post_feedback'))
        self.assertEqual(revised['kind'], 'continuation')
        self.assertEqual(outcome['kind'], 'outcome')
        self.assertLess(first['sequence'], birth['sequence'])
        self.assertLess(birth['sequence'], revised['sequence'])
        self.assertLess(revised['sequence'], outcome['sequence'])

    def test_direct_dialogue_keeps_dai_editor_and_student_attribution(self):
        for phrase in ('自己估分六百二十分', '1977年（丁巳年）出生', '现在眼睛近视'):
            self.assertEqual(self.record_containing(1, phrase)['speaker'], '戴金来')
        for phrase in ('他从小就多病', '他是1975年'):
            self.assertEqual(self.record_containing(2, phrase)['speaker'], '女编辑')
        self.assertEqual(self.record_containing(4, '我明年准备报考')['speaker'], '金美含')
        for phrase in ('日干甲辰壬和时干壬', '丁奇为考生文章', '年干丙为学校'):
            self.assertIn('学员', self.record_containing(4, phrase)['speaker'])

    def test_initial_known_1977_birth_does_not_expose_420_forecast_or_427_result(self):
        before = case_content_text(self.case(3, 'before_prediction'))
        self.assertIn('1977', before)
        self.assertIn('家长好早做准备', before)
        for later in ('四百二十分', '四百二十七分', '418', '7月27日', '9月13日',
                      '计算机专业', '靠其父找找人'):
            self.assertNotIn(later, before)
        forecast = self.record_containing(3, '四百二十分左右')
        july = self.record_containing(3, '四百二十七分')
        september = self.record_containing(3, '计算机专业录取')
        self.assertEqual(forecast['knowledge_phase'], 'prediction')
        self.assertEqual(july['knowledge_phase'], 'post_feedback')
        self.assertEqual(september['knowledge_phase'], 'post_feedback')
        self.assertEqual(september['kind'], 'outcome')
        self.assertIn('418', july['text'])
        self.assertLess(forecast['sequence'], july['sequence'])
        self.assertLess(july['sequence'], september['sequence'])
        self.assertNotIn('四百二十七分', case_content_text(forecast['payload']))

    def test_doctoral_self_inquiry_group_judgment_and_two_result_years_remain_separate(self):
        before = case_content_text(self.case(4, 'before_prediction'))
        self.assertIn('我明年准备报考北京大学心理学博士生', before)
        for later in ('考不上的信息', '1997年她的考博愿望未能实现', '1998年她终于考取'):
            self.assertNotIn(later, before)
        for phrase in ('日干甲辰壬和时干壬', '丁奇为考生文章', '年干丙为学校'):
            judgment = self.record_containing(4, phrase)
            self.assertIn('学员', judgment['speaker'])
        self.assertIn('日干壬所在6宫', self.record_containing(4, '年干丙为学校')['text'])
        failed = self.record_containing(4, '1997年她的考博愿望未能实现')
        later = self.record_containing(4, '1998年她终于考取')
        self.assertEqual(failed['knowledge_phase'], 'post_feedback')
        self.assertEqual(later['knowledge_phase'], 'post_feedback')
        self.assertEqual((failed['kind'], later['kind']), ('outcome', 'outcome'))
        self.assertLess(failed['sequence'], later['sequence'])
        self.assertNotEqual(failed['record_id'], later['record_id'])

    def test_du_phone_inquiry_withholds_late_chart_birth_and_litigation_advice(self):
        before = self.case(5, 'before_prediction')
        text = case_content_text(before)
        for known in ('怀疑成绩不真实', '9月16日', '打官司能胜吗', '过二十分钟您再来电话'):
            self.assertIn(known, text)
        for later in ('1969', '不宜打官司', '阴历九月份', '10月7号以后', '八磅重',
                      '10月9日', '年干为太岁', '太岁生景门'):
            self.assertNotIn(later, text)
        self.assertEqual(before['events'][0]['charts'], [])
        original = self.record_containing(5, '起局时间：1997年8月23日凌晨5时30分')
        self.assertEqual(original['knowledge_phase'], 'unknown')
        caveat = self.record_containing(5, '我对美国的法律不了解')
        self.assertIn('杜', caveat['speaker'])
        self.assertNotEqual(caveat['knowledge_phase'], 'pre_prediction')
        full = self.case(5)
        self.assertEqual(len(full['events']), 1)
        self.assertEqual(len(full['events'][0]['charts']), 1)
        self.assertIn('不一会儿，叶教授又打来电话', full['source']['text'])

    def test_du_october_prediction_followup_and_notification_are_separate_source_stages(self):
        forecast = self.record_containing(5, '具体说10月7号以后才能收到录取通知书')
        followup = self.record_containing(5, '今天刚进入寒露')
        outcome = self.record_containing(5, '第二天，10月9日其女儿果然收到了通知书')
        self.assertEqual(forecast['knowledge_phase'], 'prediction')
        self.assertEqual((followup['kind'], followup['knowledge_phase']), ('continuation', 'post_feedback'))
        self.assertEqual(outcome['knowledge_phase'], 'post_feedback')
        self.assertLess(forecast['sequence'], followup['sequence'])
        self.assertLess(followup['sequence'], outcome['sequence'])
        self.assertNotIn('10月9日', case_content_text(forecast['payload']))
        self.assertNotIn('八磅重', case_content_text(forecast['payload']))

    def test_confirmed_source_keeps_user_attestation_separate_from_program_verification(self):
        for number in range(1, 6):
            for view in ('full', 'before_prediction'):
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
        self.assertTrue(self.case(5)['outcome_independently_verified'])
        self.assertFalse(self.case(5)['outcome_confirmation']['prediction_accuracy_evaluated'])

    def test_selection_gold_executes_real_sql_and_never_creates_formal_role_bindings(self):
        self.assertEqual(len(self.selection_gold['selection_cases']), 116)
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
        self.assertEqual(statuses, {'applicable', 'conditional', 'excluded', 'disputed'})

    def test_official_ask_retrieves_actual_candidates_but_skips_model_and_prediction(self):
        gold = self.selection_gold['selection_cases'][0]
        model = CapturingFixtureModel()
        service = QimenService(self.db, model=model)
        filters = gold['inspection_filters']
        with patch.object(service, 'rule_candidates', wraps=service.rule_candidates) as query:
            result = service.ask(Inquiry('研究古籍求学考试方法的适用条件',
                domain=filters['domain'], context=gold['context'], method_id=filters.get('method')))
            query.assert_called_once()
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['rule_ids'], [])
        self.assertEqual(model.calls, [])
        selection = next(stage for stage in result['trace'] if stage['stage'] == 'selection')
        self.assertTrue(selection['source_candidates'])
        self.assertEqual(len(self.candidates['candidates']), 19)
        self.assertEqual({candidate['candidate_key'] for candidate in selection['source_candidates']},
                         {candidate['key'] for candidate in self.candidates['candidates']})

    def test_reference_and_identical_source_chart_share_service_api_and_cli(self):
        total = 0
        for group in self.curated['groups']:
            if group.get('dataset'):
                result = self.service.reference(group['dataset']['key'], {})
                self.assertFalse(result['truncated'])
                self.assertEqual(result['role_bindings'], [])
                total += result['total']
        self.assertEqual(total, 37)
        status, result = request(create_app(self.service),
            {'chapter_key': 'education-examinations'}, '/v1/cases')
        self.assertEqual(status, '200 OK')
        self.assertEqual(result, self.service.cases('education-examinations'))
        case = self.catalog[4]
        chart_id = case['events'][0]['chart_ids'][0]
        status, result = request(create_app(self.service),
            {'case_id': case['case_id'], 'chart_id': chart_id}, '/v1/case-chart')
        self.assertEqual(status, '200 OK')
        self.assertEqual(result, self.chart(5))
        output = io.StringIO()
        with redirect_stdout(output):
            main(['--db', str(self.db), 'case-chart', case['case_id'], chart_id])
        self.assertEqual(json.loads(output.getvalue()), result)

    def test_reimport_is_idempotent_and_tampered_source_or_future_payload_is_atomic(self):
        with connect(self.db) as conn:
            before = conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        self.assertEqual(install_exam(self.db, self.source['revision_id'], self.curated)['structured_records_added'], 0)
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

    def test_snapshot_recovers_views_original_charts_confirmations_and_condition_queries(self):
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

    def test_every_initial_view_excludes_background_payload_targets_and_later_records(self):
        for number in range(1, 6):
            before = self.case(number, 'before_prediction')
            self.assertFalse(before['training_export'])
            self.assertTrue(before['events'])
            for event in before['events']:
                self.assertTrue(event['withheld_background'])
                self.assertNotIn('background', event)
                self.assertTrue(event['records'])
                for record in event['records']:
                    self.assertEqual(record['knowledge_phase'], 'pre_prediction')
                    self.assertNotIn(record['kind'], ('prediction', 'feedback', 'outcome', 'continuation'))
                    self.assertNotIn('payload', record)
                    self.assertLess(record['sequence'], event['cutoff_sequence'])
