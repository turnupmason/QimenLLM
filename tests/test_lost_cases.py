"""Lost-property source fidelity, staged feedback, and existing service paths."""
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
from qimenllm.knowledge.db import APPEND_ONLY, connect, digest
from qimenllm.knowledge.importer import ImportConflict
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.lost import LOST_SHA
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from import_shenqi_lost import ingest


class LostCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name)
        cls.db = cls.path / 'lost.sqlite3'
        cls.raw = cls.path / 'raw'
        restore_snapshot(ROOT / 'data/snapshots/current', cls.db, cls.raw)
        with connect(cls.db) as conn:
            cls.before = {table: [tuple(row) for row in conn.execute('SELECT * FROM ' + table)]
                          for table in APPEND_ONLY}
        cls.result = ingest(cls.db, cls.raw)
        data = ROOT / 'data/structured/shenqi'
        cls.artifact = json.loads((data / 'lost_cases.json').read_bytes())
        cls.curated = json.loads((data / 'lost_curated.json').read_bytes())
        cls.candidates = json.loads((data / 'lost_rule_candidates.json').read_bytes())
        cls.gold_artifact = json.loads((data / 'lost_gold.json').read_bytes())
        cls.gold = cls.gold_artifact['charts']
        cls.source = (ROOT / 'data/provenance/uploads' / f'{LOST_SHA}.utf8').read_bytes()
        cls.svc = QimenService(cls.db)
        cls.catalog = cls.svc.cases('lost-property')['cases']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def record(self, case, line):
        return next(record for record in self.artifact['cases'][case - 1]['events'][0]['records']
                    if record['source_lines'] == [line, line])

    def projection(self, case):
        entry = self.catalog[case - 1]
        chart_id = entry['events'][0]['chart_ids'][0]
        return self.svc.case_chart(entry['case_id'], chart_id)

    def test_original_bytes_all_source_quotes_and_statement_hashes(self):
        self.assertEqual((digest(self.source), len(self.source), len(self.source.splitlines())),
                         (LOST_SHA, 34197, 362))
        selector_count = 0

        def check(value):
            nonlocal selector_count
            if isinstance(value, dict):
                if 'source_sha256' in value:
                    self.assertEqual(value['source_sha256'], LOST_SHA)
                if {'byte_start', 'byte_end'} <= value.keys():
                    text = value.get('source_quote', value.get('text'))
                    self.assertIsInstance(text, str)
                    raw = self.source[value['byte_start']:value['byte_end']]
                    self.assertEqual(raw.decode(), text)
                    self.assertEqual(digest(raw), digest(text.encode()))
                    selector_count += 1
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)

        for artifact in (self.artifact, self.curated):
            check(artifact)
        self.assertGreater(selector_count, 72)
        lines = self.source.decode().splitlines(keepends=True)
        for candidate in self.candidates['candidates']:
            expected = ''.join(lines[line - 1] for line in candidate['source_lines']).rstrip('\r\n')
            self.assertEqual(candidate['source_quote'], expected)
        with connect(self.db) as conn:
            raw = conn.execute('SELECT content,sha256 FROM raw_documents WHERE sha256=?',
                               (LOST_SHA,)).fetchone()
            self.assertEqual((raw['content'], digest(raw['content'])), (self.source, raw['sha256']))
            for chart in conn.execute('''SELECT chart_json,content_sha256 FROM charts
                    JOIN source_spans USING(source_id) WHERE revision_id=?''',
                                      (self.result['source']['revision_id'],)):
                self.assertEqual(digest(chart['chart_json'].encode()), chart['content_sha256'])

    def test_eight_complete_narrative_ranges_end_before_editorial_appendix(self):
        lines = self.source.decode().splitlines()
        self.assertEqual(len(self.artifact['cases']), 8)
        self.assertEqual(len(self.catalog), 8)
        for index, case in enumerate(self.artifact['cases']):
            start, end = case['source_ranges'][0]
            self.assertEqual(lines[start - 1], case['title'])
            self.assertEqual(case['completeness'], 'confirmed_complete')
            self.assertEqual(len(case['events']), 1)
            self.assertEqual(len(case['events'][0]['charts']), 1)
            if index:
                self.assertEqual(self.artifact['cases'][index - 1]['source_ranges'][0][1] + 1, start)
            for record in case['events'][0]['records']:
                self.assertLessEqual(start, record['source_lines'][0])
                self.assertLessEqual(record['source_lines'][1], end)
        self.assertEqual(self.artifact['cases'][0]['source_ranges'][0][0], 16)
        self.assertEqual(self.artifact['cases'][-1]['source_ranges'][0][1], 355)

    def test_all_72_literal_palaces_match_independent_source_gold(self):
        self.assertEqual(self.gold_artifact['source_sha256'], LOST_SHA)
        self.assertIn('independent literal transcription', self.gold_artifact['basis'])
        found = {chart['chart_key']: chart for case in self.artifact['cases']
                 for event in case['events'] for chart in event['charts']}
        self.assertEqual(set(found), {f'lost-case-{index:02d}-chart-1' for index in range(1, 9)})
        self.assertEqual(set(found), set(self.gold))
        self.assertEqual(sum(len(cells) for cells in self.gold.values()), 72)
        for key, chart in found.items():
            self.assertEqual([row['cells'] for row in chart['payload']['source_table_rows']],
                             self.gold[key], key)
            for row in chart['payload']['source_table_rows']:
                selector = row['source_selector']
                self.assertEqual(self.source[selector['byte_start']:selector['byte_end']].decode(),
                                 selector['source_quote'])
                self.assertEqual(selector['line_end'] - selector['line_start'], 2)

    def test_all_charts_project_same_ids_and_source_cells_through_service(self):
        expected_by_line = {chart['source_lines'][0] + 2: self.gold[chart['chart_key']]
                            for case in self.artifact['cases'] for event in case['events']
                            for chart in event['charts']}
        count = 0
        for case in self.catalog:
            for event in case['events']:
                for chart_id in event['chart_ids']:
                    projected = self.svc.case_chart(case['case_id'], chart_id)
                    self.assertEqual((projected['status'], projected['chart_id']), ('projected', chart_id))
                    self.assertEqual(set(projected['palaces']), set(map(str, range(1, 10))))
                    self.assertFalse(projected['engine_verified'])
                    self.assertFalse(projected['original_chart_modified'])
                    first_line = min(palace['source']['line'] for palace in projected['palaces'].values())
                    for number, cells in zip((4, 9, 2, 3, 5, 7, 8, 1, 6), expected_by_line[first_line]):
                        palace = projected['palaces'][str(number)]
                        self.assertEqual(palace['source']['column_cells'], cells)
                        self.assertIn('│', palace['source']['text'])
                    count += 1
        self.assertEqual(count, 8)

    def test_native_centers_and_door_and_star_prefixes_are_literal(self):
        for case, center in enumerate(('壬', '庚', '乙', '己', '乙', '戊', '辛', '丁'), 1):
            self.assertEqual(self.projection(case)['palaces']['5']['earth_stem'], center)
        for case, palace, field, value in [
                (1, '3', 'heaven_prefix_marker', '壬'),
                (2, '9', 'heaven_prefix_marker', '庚'),
                (2, '2', 'star_prefix_marker', '庚'),
                (3, '2', 'star_prefix_marker', '乙'),
                (3, '7', 'heaven_prefix_marker', '乙'),
                (4, '8', 'heaven_prefix_marker', '己'),
                (5, '6', 'heaven_prefix_marker', '乙'),
                (7, '8', 'heaven_prefix_marker', '辛')]:
            self.assertEqual(self.projection(case)['palaces'][palace][field], value)
        self.assertEqual(self.projection(3)['palaces']['7']['source']['column_cells'][2], '乙休庚')

    def test_case3_blind_forecast_precedes_revealed_question_and_followup(self):
        self.assertIn('又不说预测何事', self.record(3, 92)['text'])
        initial = self.record(3, 113)
        self.assertEqual((initial['kind'], initial['knowledge_phase']), ('prediction', 'prediction'))
        feedback = self.record(3, 115)
        self.assertEqual((feedback['kind'], feedback['knowledge_phase'], feedback['speaker']),
                         ('feedback', 'post_feedback', '李云霞'))
        self.assertEqual(feedback['payload']['record_role'], 'revealed_question')
        for line in (117, 119):
            later = self.record(3, line)
            self.assertEqual(later['knowledge_phase'], 'post_feedback')
            self.assertEqual(later['payload']['record_role'], 'forecast_after_question_revealed')
            self.assertLess(initial['sequence'], feedback['sequence'])
            self.assertLess(feedback['sequence'], later['sequence'])
        self.assertEqual(self.record(3, 121)['kind'], 'outcome')

    def test_case6_incremental_confirmations_and_timing_preserve_known_feedback(self):
        for line in (227, 229):
            self.assertEqual(self.record(6, line)['knowledge_phase'], 'prediction')
        for line in (231, 235, 239, 247):
            record = self.record(6, line)
            self.assertEqual((record['kind'], record['knowledge_phase']), ('feedback', 'post_feedback'))
        for line in (231, 235, 239):
            self.assertEqual(self.record(6, line)['speaker'], '张局长')
        self.assertEqual(self.record(6, 241)['speaker'], '王建国')
        expected = [f'lost-case-06-line-{line}' for line in (231, 235, 239)]
        for line in (243, 245):
            record = self.record(6, line)
            self.assertEqual(record['knowledge_phase'], 'post_feedback')
            self.assertEqual(record['payload']['known_feedback_record_keys'], expected)
            self.assertLess(record['sequence'], self.record(6, 247)['sequence'])
        self.assertIn('下午一点以后', self.record(6, 245)['text'])
        self.assertEqual(self.record(6, 249)['payload']['known_feedback_record_keys'],
                         expected + ['lost-case-06-line-247'])
        self.assertIn('杜新会', self.record(6, 249)['speaker'])

    def test_case6_found_location_and_explicit_miss_are_not_initial_forecasts(self):
        outcome = self.record(6, 251)
        self.assertEqual((outcome['kind'], outcome['knowledge_phase']), ('outcome', 'post_feedback'))
        self.assertIn('司机', outcome['speaker'])
        self.assertIn('下午1点28分', outcome['text'])
        self.assertIn('坐垫下面', outcome['text'])
        after = self.record(6, 253)
        self.assertEqual(after['knowledge_phase'], 'post_feedback')
        self.assertEqual(after['payload']['record_role'], 'posthoc_vehicle_location_not_predicted')
        self.assertIn('这一点事先没有断出', after['text'])
        self.assertLess(outcome['sequence'], after['sequence'])

    def test_case7_travel_then_identity_and_zhang_posthoc_note_remain_separate(self):
        travel = self.record(7, 287)
        identity = self.record(7, 293)
        self.assertEqual(travel['knowledge_phase'], 'prediction')
        self.assertEqual(travel['speaker'], '赵国葆')
        self.assertIn('去海口', travel['text'])
        self.assertNotIn('身份证', travel['text'])
        self.assertEqual((identity['kind'], identity['knowledge_phase'], identity['speaker']),
                         ('feedback', 'post_feedback', '梁工'))
        self.assertEqual(identity['payload']['record_role'], 'identity_revealed')
        self.assertLess(travel['sequence'], identity['sequence'])
        note = self.record(7, 307)
        self.assertEqual((note['kind'], note['knowledge_phase']), ('author_reasoning', 'post_feedback'))
        self.assertEqual(note['speaker'], '张志春（后置按语）')
        self.assertEqual(note['payload']['record_role'], 'posthoc_author_note')
        self.assertTrue(note['payload']['not_original_analyst_reasoning'])
        self.assertLess(self.record(7, 305)['sequence'], note['sequence'])

    def test_case8_dialogue_segments_and_outcome_are_narrow_source_claims(self):
        segments = self.record(8, 343)['payload']['source_statement_segments']
        self.assertEqual([segment['speaker'] for segment in segments],
                         ['张志春', '对方', '张志春', '对方', '张志春'])
        self.assertEqual(segments[-1]['record_role'], 'author_theft_judgment_not_external_confirmation')
        self.assertEqual(self.record(8, 347)['speaker'], '对方')
        outcome = self.record(8, 353)
        self.assertEqual((outcome['kind'], outcome['knowledge_phase']), ('outcome', 'post_feedback'))
        self.assertEqual(outcome['text'], '结果：这辆丢失的汽车，至今也未找回。\n')
        self.assertEqual(outcome['payload']['outcome_time_scope'],
                         'as_of_original_narration_only; no later result provided')

    def test_editorial_appendix_is_preserved_without_ninth_case_or_agent_correction(self):
        group = next(group for group in self.curated['groups'] if group['key'] == 'lost_editorial_appendix')
        self.assertEqual((group['line_start'], group['line_end'], group['category']),
                         (356, 362, 'commentary'))
        self.assertFalse(group['dataset']['rows'])
        chart = self.artifact['cases'][2]['events'][0]['charts'][0]['payload']
        appendix = chart['source_editorial_appendix']
        self.assertEqual((appendix['line_start'], appendix['line_end']), (356, 362))
        self.assertEqual(self.source[appendix['byte_start']:appendix['byte_end']].decode(),
                         appendix['source_quote'])
        self.assertIn('乙体庚', appendix['source_quote'])
        self.assertIn('乙休庚', appendix['source_quote'])
        self.assertEqual(chart['source_version_policy'],
                         'Received edited upload is authoritative; no scan provided, no agent correction')
        self.assertTrue(all(record['source_lines'][1] < 356 for case in self.artifact['cases']
                            for event in case['events'] for record in event['records']))

    def test_five_conditional_candidates_never_activate_roles_or_unknown_conditions(self):
        contexts = [({}, 0), ({'domain': 'lost_property'}, 0),
                    ({'domain': 'lost_property', 'lost_subtype': 'theft'}, 0)]
        for subtype in ('owner_property', 'recoverability', 'location', 'theft', 'timing'):
            contexts.append(({'domain': 'lost_property', 'lost_subtype': subtype,
                              'method_scope': f'shenqi_lost_{subtype}_reference_v1'}, 1))
        for context, count in contexts:
            result = self.svc.rule_candidates(context, domain='lost_property', method='shenqi_lost_reference_v1')
            self.assertEqual(result['candidate_count'], 5)
            self.assertFalse(result['role_bindings'])
            self.assertEqual(sum(candidate['symbolic_status'] == 'applicable'
                                 for candidate in result['candidates']), count)
            self.assertTrue(all(candidate['activation_status'] == 'reference_only'
                                for candidate in result['candidates']))
        for candidate in self.candidates['candidates']:
            self.assertEqual(candidate['unknown_policy'], 'conditional_never_true_by_default')
            self.assertFalse(candidate['formal_role_activation_allowed'])
            self.assertFalse(candidate['role_binding']['automatic_activation'])

    def test_before_prediction_views_withhold_feedback_followups_and_outcomes(self):
        for case in self.catalog:
            view = self.svc.case(case['case_id'], 'before_prediction')
            self.assertFalse(view['training_export'])
            for event in view['events']:
                for record in event['records']:
                    self.assertEqual(record['knowledge_phase'], 'pre_prediction')
        for case, forbidden in [(3, ('皮衣', '货主')),
                                (6, ('下午一点以后', '1点28分', '坐垫下面', '这一点事先没有断出')),
                                (7, ('身份证', '张志春按')),
                                (8, ('至今也未找回',))]:
            view = self.svc.case(self.catalog[case - 1]['case_id'], 'before_prediction')
            encoded = json.dumps(view, ensure_ascii=False)
            for phrase in forbidden:
                self.assertNotIn(phrase, encoded)

    def test_full_case_wsgi_and_cli_use_existing_catalog_and_chart_objects(self):
        app = create_app(self.svc)

        def call(path, payload):
            body = json.dumps(payload).encode()
            statuses = []
            output = b''.join(app({'PATH_INFO': path, 'REQUEST_METHOD': 'POST',
                                  'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(body)),
                                  'wsgi.input': io.BytesIO(body)}, lambda status, headers: statuses.append(status)))
            self.assertEqual(statuses, ['200 OK'])
            return json.loads(output)

        cases = call('/v1/cases', {'chapter_key': 'lost-property'})['cases']
        self.assertEqual([case['case_id'] for case in cases], [case['case_id'] for case in self.catalog])
        for case in cases:
            full = call('/v1/case', {'case_id': case['case_id']})
            self.assertEqual(full['case_id'], case['case_id'])
            for event in case['events']:
                for chart_id in event['chart_ids']:
                    projected = call('/v1/case-chart', {'case_id': case['case_id'], 'chart_id': chart_id})
                    self.assertEqual(projected, self.svc.case_chart(case['case_id'], chart_id))
        result = subprocess.run([sys.executable, '-m', 'qimenllm', '--db', str(self.db),
                                 'cases', '--chapter-key', 'lost-property'],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual([case['case_id'] for case in json.loads(result.stdout)['cases']],
                         [case['case_id'] for case in self.catalog])

    def test_old_rows_preserved_audit_and_idempotence_without_training(self):
        with connect(self.db) as conn:
            for table, rows in self.before.items():
                current = [tuple(row) for row in conn.execute('SELECT * FROM ' + table)]
                self.assertTrue(all(row in current for row in rows), table)
            versions = conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        result = ingest(self.db, self.raw)
        self.assertTrue(result['cases']['duplicate'])
        self.assertTrue(result['candidates']['duplicate'])
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0], versions)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM rules').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0], 0)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_existing_case_rewrite_rejected_and_snapshot_roundtrip_exact(self):
        changed = copy.deepcopy(self.artifact)
        changed['cases'][0]['title'] = 'changed'
        with self.assertRaises(ImportConflict):
            import_cases(self.db, self.result['source']['revision_id'], changed)
        first = self.path / 'snapshot'
        again = self.path / 'again'
        db = self.path / 'roundtrip.sqlite3'
        raw = self.path / 'roundtrip_raw'
        export_snapshot(self.db, self.raw, first)
        restore_snapshot(first, db, raw)
        export_snapshot(db, raw, again)
        self.assertEqual({str(path.relative_to(first)): path.read_bytes() for path in first.rglob('*') if path.is_file()},
                         {str(path.relative_to(again)): path.read_bytes() for path in again.rglob('*') if path.is_file()})
