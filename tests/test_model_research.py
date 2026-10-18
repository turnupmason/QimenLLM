import copy
import json
from pathlib import Path
import tempfile
import unittest

from qimenllm.api.app import create_app
from qimenllm.contracts import GenerationError, Inquiry
from qimenllm.evaluation.research import (
    ARMS, ResearchRequest, prepare, score, validate_output)
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.reasoning.service import QimenService
from test_runtime import request as http_request


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / 'data/structured/shenqi/baseline_development_v3.json'
PINNED_SHA = '6c43228e83db2e71eb658ef2a385088cb93a007fbaea4006d93eb0d0e37b5a78'


class ModelResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.db = Path(cls.temporary.name) / 'db.sqlite3'
        restore_snapshot(ROOT / 'data/snapshots/current', cls.db, Path(cls.temporary.name) / 'raw')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.suite = json.loads(SUITE.read_bytes())
        self.service = QimenService(self.db)

    def req(self, task=0, arm='base', path=SUITE, sha=PINNED_SHA):
        return ResearchRequest(str(path), sha, self.suite['tasks'][task]['task_id'], arm)

    def question(self, task=0):
        return Inquiry(self.suite['tasks'][task]['question'])

    def modified(self, mutate):
        suite = copy.deepcopy(self.suite)
        mutate(suite)
        path = Path(self.temporary.name) / 'modified.json'
        path.write_text(json.dumps(suite, ensure_ascii=False))
        return path, digest(path.read_bytes())

    def test_development_suite_pinned_and_families_reserved(self):
        self.assertEqual(digest(SUITE.read_bytes()), PINNED_SHA)
        self.assertEqual(len(self.suite['family_assignments']), 94)
        self.assertEqual(list(self.suite['family_assignments'].values()).count('development'), 3)
        self.assertEqual(list(self.suite['family_assignments'].values()).count('reserved_unreviewed'), 91)

    def test_all_arms_run_real_service_preparation_and_keep_truth_out(self):
        for index, task in enumerate(self.suite['tasks']):
            for arm in ARMS:
                payload, diagnostics = prepare(self.service, self.req(index, arm), self.question(index))
                body = json.dumps(payload, ensure_ascii=False)
                self.assertNotIn('gold', payload)
                self.assertNotIn('case_id', payload)
                for target in task['gold']['author'].values():
                    self.assertNotIn(target['record_id'], body)
                    # A short role phrase can also occur legitimately in a
                    # released general rule. Check the held case record itself.
                    from qimenllm.knowledge.db import connect
                    with connect(self.db) as conn:
                        text = conn.execute('SELECT text FROM case_records WHERE record_id=?',
                                            (target['record_id'],)).fetchone()[0]
                    self.assertNotIn(text, [s['text'] for s in payload['known_information']])
                self.assertEqual(diagnostics['formal_rule_count'], 0)
                if payload['chart']:
                    self.assertFalse(payload['chart']['engine_verified'])
                    self.assertFalse(payload['chart']['calendar_recomputed'])

    def test_all_arms_share_identical_known_inputs_not_answer_dependent(self):
        for index in range(3):
            common = []
            for arm in ARMS:
                payload, _ = prepare(self.service, self.req(index, arm), self.question(index))
                common.append({k: payload[k] for k in ('question', 'answer_fields', 'known_information',
                                                      'given_symbolic_inputs', 'declared_condition_context')})
            self.assertTrue(all(item == common[0] for item in common))

    def test_source_candidate_context_mapping_is_not_false_exclusion(self):
        payload, _ = prepare(self.service, self.req(0, 'candidate_conditions'), self.question(0))
        car = next(r for r in payload['candidate_conditions'] if r['candidate_key'] == 'travel_car')
        # A matched local subtype still needs an explicit method selection.
        # Preserving that dispute is correct; do not force activation for a test.
        self.assertEqual(car['symbolic_status'], 'disputed')
        self.assertEqual(car['activation_status'], 'reference_only')
        self.assertEqual(car['role_bindings'], [])
        payload, _ = prepare(self.service, self.req(2, 'candidate_conditions'), self.question(2))
        self.assertTrue(all(r['symbolic_status'] == 'conditional' for r in payload['candidate_conditions']))

    def test_duplicate_nonfinite_json_and_oversize_citation_rejected(self):
        from qimenllm.models.mlx_gateway import parse_research_json
        for value in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                parse_research_json(value)
        payload, _ = prepare(self.service, self.req(), self.question())
        output = {'answers': {k: None for k in payload['answer_fields']},
                  'evidence': [{'source_id': 'x', 'quote': 'x'*81}], 'fact_claims': []}
        with self.assertRaises(GenerationError):
            validate_output(output, payload)

    def test_first_concealed_question_never_receives_lost_property_domain_hint(self):
        payload, _ = prepare(self.service, self.req(1, 'candidate_conditions'), self.question(1))
        self.assertEqual(payload['knowledge'], [])
        self.assertEqual(payload['candidate_conditions'], [])
        self.assertNotIn('测失皮衣', json.dumps(payload, ensure_ascii=False))
        self.assertNotIn('少的那件皮衣仍在辛集货主那里', json.dumps(payload, ensure_ascii=False))

    def test_later_turn_receives_only_feedback_before_this_target(self):
        payload, _ = prepare(self.service, self.req(2, 'chart_knowledge'), self.question(2))
        body = json.dumps(payload, ensure_ascii=False)
        self.assertIn('他老婆是一家商场的会计', body)
        self.assertNotIn('1998年五月同这个青年女子结了婚', body)
        self.assertNotIn('用酒瓶打伤丈夫右脸', body)

    def test_modified_suite_without_new_pin_rejected(self):
        with self.assertRaises(ValueError):
            prepare(self.service, self.req(sha='0'*64), self.question())

    def test_reserved_family_cannot_run(self):
        path, sha = self.modified(lambda s: s['family_assignments'].update(
            {s['tasks'][0]['family_id']: 'reserved_unreviewed'}))
        with self.assertRaises(ValueError):
            prepare(self.service, self.req(path=path, sha=sha), self.question())

    def test_stale_data_version_rejected(self):
        path, sha = self.modified(lambda s: s.update(data_version='stale'))
        with self.assertRaises(ValueError):
            prepare(self.service, self.req(path=path, sha=sha), self.question())

    def test_after_cutoff_record_and_changed_source_rejected(self):
        for mutate in (
            lambda s: s['tasks'][0].update(cutoff_sequence=0),
            lambda s: s['tasks'][0]['input_records'][0].update(excerpt_sha256='0'*64)):
            path, sha = self.modified(mutate)
            with self.assertRaises(ValueError):
                prepare(self.service, self.req(path=path, sha=sha), self.question())

    def test_whole_case_cannot_enter_retrieval(self):
        from qimenllm.knowledge.db import connect
        with connect(self.db) as conn:
            sid = conn.execute('SELECT source_id FROM cases WHERE case_id=?',
                               (self.suite['tasks'][0]['case_id'],)).fetchone()[0]
        source = self.service.knowledge.source(sid)
        path, sha = self.modified(lambda s: s['tasks'][0].update(knowledge_sources=[
            {'source_id': sid, 'excerpt_sha256': digest(source['excerpt'].encode())}]))
        with self.assertRaises(ValueError):
            prepare(self.service, self.req(arm='chart_knowledge', path=path, sha=sha), self.question())

    def test_hidden_inquiry_context_and_wrong_task_rejected(self):
        with self.assertRaises(ValueError):
            prepare(self.service, self.req(), Inquiry(self.question().text, context={'answer': True}))
        with self.assertRaises(ValueError):
            prepare(self.service, self.req(), Inquiry('different'))

    def test_actual_ask_calls_research_model_and_never_claims_professional_success(self):
        calls = []
        class Model:
            def generate_research(inner, payload):
                calls.append(payload)
                return {'answers': {k: None for k in payload['answer_fields']},
                        'evidence': [], 'fact_claims': []}, {'generation_tokens': 12}
        self.service.model = Model()
        result = self.service.ask(self.question(), research=self.req())
        self.assertEqual(result['status'], 'research_generated')
        self.assertFalse(result['professional_analysis_completed'])
        self.assertEqual(len(calls), 1)
        self.assertNotIn('gold', calls[0])

    def test_generation_error_preserves_telemetry_and_cannot_score_as_success(self):
        class Model:
            def generate_research(inner, payload):
                return {'bad': True}, {'raw_output': 'not json', 'finish_reason': 'length'}
        self.service.model = Model()
        result = self.service.ask(self.question(), research=self.req())
        self.assertEqual(result['status'], 'generation_error')
        self.assertEqual(result['telemetry']['raw_output'], 'not json')
        self.assertNotIn('output', result)
        self.assertEqual(score(self.db, self.suite['tasks'][0], result)['author']['matches'], 0)

    def test_invalid_citation_and_wrong_chart_fact_classified(self):
        payload, _ = prepare(self.service, self.req(arm='symbolic_chart'), self.question())
        output = {'answers': {k: None for k in payload['answer_fields']},
                  'evidence': [{'source_id': 'future', 'quote': 'future'}],
                  'fact_claims': [{'key': 'does_not_exist', 'value': 1}]}
        self.assertEqual(validate_output(output, payload),
                         ['citation_not_in_released_source', 'chart_fact_mismatch'])
        output['answers']['people_safe'] = 1
        with self.assertRaises(GenerationError):
            validate_output(output, payload)

    def test_author_reproduction_and_actual_reported_year_are_different_targets(self):
        task = self.suite['tasks'][2]
        result = {'output': {'answers': {'marriage_year': 1997, 'male_role': '庚', 'wife_role': '乙'}}}
        scores = score(self.db, task, result)
        self.assertEqual(scores['author']['matches'], 3)
        self.assertEqual(scores['reported_outcome']['matches'], 0)
        self.assertIsNone(scores['real_world_predictive_accuracy'])

    def test_http_cannot_enable_research_and_production_gate_remains(self):
        status, _ = http_request(create_app(self.service), {'text': 'test', 'research': True})
        self.assertEqual(status, '400 Bad Request')
        self.assertEqual(self.service.ask(Inquiry('正常问事'))['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
