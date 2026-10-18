"""Source methodology remains retrievable without becoming empirical scores."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.evaluation.metrics import summarize
from qimenllm.knowledge.accuracy import ACCURACY_SHA, install_accuracy
from qimenllm.knowledge.db import APPEND_ONLY, connect, digest
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_shenqi_accuracy as importer


class AccuracyKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name)
        cls.db, cls.raw = cls.path / 'accuracy.sqlite3', cls.path / 'raw'
        restore_snapshot(ROOT / 'data/snapshots/current', cls.db, cls.raw)
        with connect(cls.db) as c:
            cls.before = {t: [tuple(r) for r in c.execute('SELECT * FROM ' + t)]
                          for t in APPEND_ONLY + ('books', 'chapters', 'dataset_releases')}
        cls.chart_args = {'dun': '阳遁', 'bureau': 2, 'hour_ganzhi': '辛卯', 'method': 'shenqi_ch2_paper_v1'}
        cls.before_chart = QimenService(cls.db).calculate('symbolic_chart', cls.chart_args)
        cls.result = importer.ingest(cls.db, cls.raw)
        cls.curated = json.loads((ROOT / 'data/structured/shenqi/accuracy_curated.json').read_bytes())
        cls.source = importer.UPLOAD.read_bytes()
        cls.groups = {g['key']: g for g in cls.curated['groups']}
        cls.svc = QimenService(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def assessment(self, key):
        return self.groups['accuracy_' + key]['assessment']

    def test_exact_bytes_and_all_byte_selectors(self):
        self.assertEqual((digest(self.source), len(self.source), len(self.source.splitlines())),
                         (ACCURACY_SHA, 9177, 37))
        def walk(v):
            if isinstance(v, dict):
                if 'source_sha256' in v:
                    self.assertEqual(v['source_sha256'], ACCURACY_SHA)
                if {'byte_start', 'byte_end'} <= v.keys():
                    self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),
                                     v.get('source_quote', v.get('text')))
                for child in v.values():
                    walk(child)
            elif isinstance(v, list):
                for child in v:
                    walk(child)
        walk(self.curated)

    def test_full_paragraph_coverage_and_literal_rows(self):
        lines = self.source.decode().splitlines(keepends=True)
        covered = []
        for g in self.groups.values():
            covered.extend(range(g['line_start'], g['line_end'] + 1))
            for row in g['dataset']['rows']:
                p = row['source_pointer']
                self.assertEqual(row['source_quote'], ''.join(lines[p['line_start']-1:p['line_end']]))
                self.assertEqual(row['applicability_status'], 'reference_only')
        self.assertEqual(covered, list(range(1, 38)))
        self.assertEqual(len(self.curated['quality_issues']), 9)

    def test_two_meanings_do_not_create_observed_hundred_or_single_probability(self):
        a = self.assessment('rate_meanings')
        self.assertEqual(len(a['interpretations']), 2)
        self.assertIn('测一百人或一百件事', a['interpretations'][0]['source_selector']['source_quote'])
        self.assertIn('一件事在百分之七八十程度', a['interpretations'][1]['source_selector']['source_quote'])
        for key in ('observed_sample_size', 'observed_correct_count', 'project_empirical_accuracy'):
            self.assertIsNone(a[key])
        self.assertTrue(a['hypothetical_hundred_not_observed_cohort'])
        self.assertTrue(a['do_not_merge_denominators'])
        self.assertFalse(a['scoring_protocol_supplied'])
        self.assertFalse(a['normalize_to_single_calibrated_probability'])

    def test_publication_positions_preserved_together_without_dropping_failures(self):
        g = self.groups['accuracy_publication_policy']
        self.assertEqual((g['line_start'], g['line_end']), (19, 24))
        a = g['assessment']
        self.assertEqual([p['source_selector']['line_start'] for p in a['source_positions']], [19, 21, 23])
        self.assertTrue(a['source_tension_preserved'])
        self.assertTrue(a['published_examples_not_complete_success_failure_population'])
        self.assertFalse(a['project_may_drop_failed_predictions_on_this_basis'])
        self.assertFalse(a['project_success_rate_computed_from_book_examples'])

    def test_five_method_families_have_no_selected_default_or_compilation(self):
        a = self.assessment('method_disagreements')
        self.assertEqual([f['key'] for f in a['families']],
                         ['bureau_choice', 'deity_reference_frame', 'star_strength', 'center_hosting', 'patterns_and_selection'])
        for f in a['families']:
            self.assertIsNone(f['selected_default'])
            self.assertEqual(f['execution_status'], 'reference_only_not_compiled')
        center = a['families'][3]['alternatives_as_written']
        self.assertEqual(len(center), 3)
        for phrase in ('永远寄坤2宫', '阳遁寄艮8宫', '立春寄艮', '立夏寄巽', '立秋寄坤', '立冬寄乾'):
            self.assertIn(phrase, json.dumps(center, ensure_ascii=False))
        self.assertFalse(a['default_method_changed'])
        self.assertFalse(a['algorithm_validation_completed'])

    def test_analogies_and_scientific_limit_remain_attributed(self):
        a = self.assessment('three_reasons')
        self.assertIn('是否科学，尚待研究', a['analogy_caution_selector']['source_quote'])
        self.assertFalse(a['scientific_comparison_independently_verified'])
        self.assertTrue(a['no_birth_time_description_not_override_of_previous_birth_chart_scope'])
        self.assertFalse(self.assessment('scientific_limits')['theory_scientifically_validated_by_project'])
        self.assertFalse(self.assessment('closing_argument')['quotation_independently_checked_against_external_edition'])

    def test_proposed_error_and_question_factors_do_not_excuse_or_exclude_results(self):
        self.assertFalse(self.assessment('operator_factors')['automatically_excuse_wrong_prediction_or_remove_from_denominator'])
        a = self.assessment('question_context')
        self.assertIsNone(a['project_empirical_subgroup_scores'])
        self.assertFalse(a['automatically_refuse_curious_unrelated_or_proxy_questioners'])
        self.assertFalse(a['post_outcome_case_exclusion_allowed'])
        self.assertFalse(self.assessment('timing_relationship')['automatic_timestamp_or_probability_selection'])

    def test_no_fabricated_cases_charts_rules_tasks_or_new_books(self):
        for key in ('historical_cases_added', 'charts_added', 'empirical_evaluation_runs_added'):
            self.assertEqual(self.result[key], 0)
        self.assertIsNone(self.result['project_empirical_accuracy'])
        self.assertEqual(self.curated['worked_examples'], [])
        unchanged = ('books', 'cases', 'events', 'event_families', 'case_events', 'charts',
                     'case_records', 'evidence_links', 'rules', 'rule_conditions', 'training_tasks',
                     'task_inputs', 'dataset_releases', 'rule_disagreements')
        with connect(self.db) as c:
            for t in unchanged:
                self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM ' + t)], self.before[t], t)
        self.assertEqual(self.svc.cases('accuracy-assessment')['cases'], [])

    def test_stored_assessments_are_reference_only_with_confirmed_provenance(self):
        r = self.svc.learning.learn('百分之七八十')
        self.assertEqual(r['status'], 'sources_found')
        block = next(b for b in r['knowledge_blocks'] if b['payload'].get('key') == 'accuracy_rate_meanings')
        self.assertEqual(block['payload']['assessment'], self.assessment('rate_meanings'))
        self.assertIsNone(r['model_analysis'])
        ref = self.svc.reference('accuracy_rate_meanings_reference', {})
        self.assertEqual((ref['status'], ref['total']), ('sources_found', 1))
        self.assertFalse(ref['professional_analysis_completed'])
        self.assertEqual(ref['role_bindings'], [])
        for s in ref['sources'].values():
            self.assertEqual(s['sha256'], ACCURACY_SHA)
            self.assertEqual(s['source_acceptance'], 'confirmed')
        with connect(self.db) as c:
            rows = c.execute("SELECT compiled,reference_only,applicability_confirmed FROM knowledge_items JOIN source_spans USING(source_id) WHERE revision_id=?", (self.result['source']['revision_id'],)).fetchall()
            self.assertEqual(len(rows), 22)
            self.assertTrue(all(tuple(r) == (0, 1, 0) for r in rows))

    def test_existing_wsgi_reads_complete_method_context(self):
        app = create_app(self.svc)
        def call(path, payload):
            body = json.dumps(payload).encode(); status = []
            out = b''.join(app({'PATH_INFO': path, 'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(body)),
                'wsgi.input': io.BytesIO(body)}, lambda s, h: status.append(s)))
            self.assertEqual(status, ['200 OK'])
            return json.loads(out)
        r = call('/v1/reference', {'family': 'accuracy_method_disagreements_reference', 'filters': {}})
        self.assertEqual(r['total'], 1)
        text = json.dumps(r, ensure_ascii=False)
        for phrase in ('拆补法', '十个时辰', '锡孟樨', '旺相休囚'):
            self.assertIn(phrase, text)
        r = call('/v1/learn', {'term': '百分之七八十'})
        self.assertTrue(any(b['payload'].get('key') == 'accuracy_rate_meanings' for b in r['knowledge_blocks']))

    def test_actual_cli_reference(self):
        r = subprocess.run([sys.executable, '-m', 'qimenllm', '--db', str(self.db),
                            'reference', 'accuracy_rate_meanings_reference', '--filters', '{}'],
                           cwd=ROOT, capture_output=True, text=True, check=True)
        result = json.loads(r.stdout)
        self.assertEqual(result['total'], 1)
        self.assertIn('测一百人或一百件事', result['entries'][0]['record']['source_quote'])
        self.assertFalse(result['professional_analysis_completed'])

    def test_existing_calculation_and_metrics_do_not_take_author_percentage(self):
        self.assertEqual(self.before_chart['status'], 'computed')
        self.assertEqual(self.svc.calculate('symbolic_chart', self.chart_args), self.before_chart)
        with connect(self.db) as c:
            methods = [tuple(r) for r in c.execute('SELECT * FROM methods')]
            self.assertTrue(all(r in methods for r in self.before['methods']))
        metrics = summarize([{'status': 'blocked', 'professional_analysis_completed': False},
                             {'status': 'structurally_verified', 'professional_analysis_completed': False}])
        self.assertEqual(metrics['professional_completions'], 0)
        self.assertIsNone(metrics['professional_correctness'])
        self.assertIsNone(metrics['real_world_predictive_accuracy'])

    def test_old_rows_retained_and_replay_does_not_add_versions(self):
        with connect(self.db) as c:
            for t, old in self.before.items():
                current = [tuple(r) for r in c.execute('SELECT * FROM ' + t)]
                self.assertTrue(all(row in current for row in old), t)
            n = c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        result = importer.ingest(self.db, self.raw)
        self.assertEqual(result['curation']['structured_records_added'], 0)
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0], n)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_changed_source_or_wrong_fingerprint_is_rejected(self):
        bad = self.path / 'bad-source.txt'; bad.write_bytes(self.source + b'changed')
        with patch.object(importer, 'UPLOAD', bad), self.assertRaises(ValueError):
            importer.ingest(self.db, self.raw)
        curated = copy.deepcopy(self.curated); curated['source_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            install_accuracy(self.db, self.result['source']['revision_id'], curated)

    def test_snapshot_roundtrip_keeps_exact_source_and_all_tables(self):
        first, again = self.path / 'snapshot', self.path / 'again'
        db, raw = self.path / 'roundtrip.sqlite3', self.path / 'roundtrip-raw'
        export_snapshot(self.db, self.raw, first)
        restore_snapshot(first, db, raw)
        export_snapshot(db, raw, again)
        self.assertEqual({str(p.relative_to(first)): p.read_bytes() for p in first.rglob('*') if p.is_file()},
                         {str(p.relative_to(again)): p.read_bytes() for p in again.rglob('*') if p.is_file()})
        self.assertEqual((first / 'raw' / (ACCURACY_SHA + '.bin')).read_bytes(), self.source)
