"""Real source boundaries, task-specific targets and event-family permissions."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from qimenllm.knowledge.snapshot import restore_snapshot

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('method_release', ROOT / 'training/method_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class MethodReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / 'source.sqlite3'
        restore_snapshot(ROOT / 'data/snapshots/current', cls.db, Path(cls.tmp.name) / 'raw')
        cls.review = json.loads((ROOT / 'data/structured/shenqi/lost_method_task_review_v5.json').read_bytes())
        cls.families = json.loads((ROOT / 'data/splits/author_initial_release_v2.json').read_bytes())
        before = cls.db.read_bytes()
        cls.tasks, cls.report = release.build(cls.db, cls.review, cls.families)
        cls.db_unchanged = before == cls.db.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def build_changed(self, change):
        review = copy.deepcopy(self.review)
        change(review)
        return release.build(self.db, review, self.families)

    def test_frozen_release_rebuilds_all_actual_task_bytes(self):
        manifest = json.loads((ROOT / 'data/splits/lost_method_release_v5.json').read_bytes())
        for split in ('train', 'validation', 'test', 'development'):
            raw = b''.join(release.encoded(t) for t in self.tasks if t['split'] == split)
            self.assertEqual(release.sha(raw), manifest['files'][split + '.jsonl']['sha256'])
        self.assertEqual(self.report['counts_by_split'], {'test': 4, 'train': 22, 'development': 2, 'validation': 4})
        self.assertEqual(self.report['counts_by_task_type'], {'role_selection': 6, 'chart_evidence': 8,
            'evidence_synthesis': 6, 'timing_analysis': 6, 'feedback_continuation': 6})

    def test_full_eight_cases_stay_in_original_families_and_database_is_read_only(self):
        self.assertTrue(self.db_unchanged)
        owners = {}
        for task in self.tasks:
            self.assertEqual(owners.setdefault(task['family_id'], task['split']), task['split'])
            self.assertEqual(self.families['family_assignments'][task['family_id']], task['split'])
        self.assertEqual(len(owners), 8)
        self.assertFalse(self.report['database_modified'])
        self.assertFalse(self.report['formal_sft_launch_authorized'])
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM events WHERE chronology_status='verified'").fetchone()[0], 0)

    def test_initial_inputs_are_known_dialogue_without_targets_or_feedback(self):
        with sqlite3.connect(self.db) as con:
            con.row_factory = sqlite3.Row
            for task in self.tasks:
                payload = json.loads(task['messages'][1]['content'])
                self.assertNotIn('case_title_for_review_only', payload)
                self.assertNotIn('supervision_sources', payload)
                for permission in task['input_permissions']:
                    record = con.execute('SELECT * FROM case_records WHERE record_id=?', (permission['record_id'],)).fetchone()
                    self.assertLess(record['sequence'], task['cutoff_sequence'])
                    if task['context_mode'] == 'initial':
                        self.assertEqual(record['kind'], 'dialogue')
                        self.assertIn(record['knowledge_phase'], ('pre_prediction', 'unknown'))
                for target in task['supervision_sources']:
                    self.assertNotIn(target['text'], task['messages'][1]['content'])

    def test_semantic_targets_are_paraphrases_and_timing_condition_difference_survives(self):
        for task in self.tasks:
            target = json.loads(task['messages'][-1]['content'])
            self.assertNotIn('author_steps', target)
            self.assertTrue(target['explanation'])
            self.assertTrue(target['citations'])
        cash = next(t for t in self.tasks if t['event_id'].startswith('event-36d690ee')
                    and t['task_type'] == 'timing_analysis')
        self.assertIn('阳日', cash['messages'][-1]['content'])
        self.assertIn('阴干阳干', cash['messages'][-1]['content'])

    def test_continuation_keeps_old_chart_and_excludes_each_next_feedback(self):
        for task in self.tasks:
            if task['task_type'] == 'feedback_continuation':
                answer = json.loads(task['messages'][-1]['content'])
                self.assertEqual(answer['chart_action'], 'reuse_original')
                self.assertEqual(json.loads(task['messages'][1]['content'])['chart']['chart_id'], task['chart_id'])
        after_negative = next(t for t in self.tasks if t['event_id'].startswith('event-9192e1ff')
                              and t['cutoff_sequence'] == 16)
        self.assertIn('办公室和汽车里都找遍了', after_negative['messages'][1]['content'])
        for text in ('坐垫', '1点28分', '小宋'):
            self.assertNotIn(text, after_negative['messages'][1]['content'])
            self.assertNotIn(text, after_negative['messages'][-1]['content'])

    def test_wrong_chart_fact_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'contradicts original chart'):
            self.build_changed(lambda r: r['cases'][0]['stages'][0]['facts'][0].update(value='invented'))

    def test_future_feedback_cannot_be_smuggled_into_initial_context(self):
        def change(review):
            stage = review['cases'][0]['stages'][0]
            with sqlite3.connect(self.db) as con:
                row = con.execute("SELECT record_id,text FROM case_records WHERE event_id=? AND kind='outcome'",
                                  (review['cases'][0]['event_id'],)).fetchone()
            stage['input_permissions'].append({'record_id': row[0], 'text_sha256': release.sha(row[1].encode()),
                'grant': 'pre_prediction_dialogue'})
        with self.assertRaisesRegex(ValueError, 'Future record'):
            self.build_changed(change)

    def test_initial_target_may_not_cross_later_feedback(self):
        def change(review):
            case = review['cases'][0]
            with sqlite3.connect(self.db) as con:
                row = con.execute("SELECT record_id,text FROM case_records WHERE event_id=? AND kind='outcome'",
                                  (case['event_id'],)).fetchone()
            case['stages'][0]['tasks'][0]['target_permissions'].append(
                {'record_id': row[0], 'text_sha256': release.sha(row[1].encode())})
        with self.assertRaisesRegex(ValueError, 'later feedback boundary'):
            self.build_changed(change)

    def test_negative_reminder_of_later_hiding_place_is_still_a_leak(self):
        def change(review):
            cash = next(c for c in review['cases'] if c['event_id'].startswith('event-36d690ee'))
            cash['stages'][0]['tasks'][0]['answer']['explanation'] += '不要说床单。'
        with self.assertRaisesRegex(ValueError, 'future information'):
            self.build_changed(change)

    def test_non_time_unknown_dialogue_cannot_be_marked_as_time_metadata(self):
        def change(review):
            case = review['cases'][0]
            stage = case['stages'][0]
            # A genuine initial dialogue lacks the required source-time fields.
            stage['input_permissions'][0]['grant'] = 'source_given_time_metadata'
        with self.assertRaisesRegex(ValueError, 'time-only metadata'):
            self.build_changed(change)

    def test_knowledge_retrieval_rejects_a_whole_case_even_with_matching_hash(self):
        def change(review):
            case = review['cases'][0]
            with sqlite3.connect(self.db) as con:
                con.row_factory = sqlite3.Row
                source_id = con.execute('SELECT source_id FROM cases WHERE case_id=?', (case['case_id'],)).fetchone()[0]
                ref = release.source(con, source_id)
            case['stages'][0]['rule_references'].append({'id': 'leaky', 'source_id': source_id,
                'excerpt_sha256': ref['excerpt_sha256']})
        with self.assertRaisesRegex(ValueError, 'Case narrative'):
            self.build_changed(change)

    def test_unknown_citation_and_unreviewed_legacy_v1_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unavailable evidence'):
            self.build_changed(lambda r: r['cases'][0]['stages'][0]['tasks'][0]['answer'].update(citations=['invented']))
        old = json.loads((ROOT / 'data/structured/shenqi/lost_method_task_review_v1.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'semantic review'):
            release.build(self.db, old, self.families)

    def test_generic_reference_cannot_overwrite_chart_citation(self):
        def change(review):
            review['cases'][0]['stages'][0]['rule_references'][0]['id'] = 'chart'
        with self.assertRaisesRegex(ValueError, 'reserved evidence reference'):
            self.build_changed(change)

    def test_author_given_conditions_are_explicit_and_owned_by_each_task(self):
        for task in self.tasks:
            case = next(c for c in self.review['cases'] if c['event_id'] == task['event_id'])
            stage = next(s for s in case['stages'] if s['cutoff_sequence'] == task['cutoff_sequence'])
            item = next(t for t in stage['tasks'] if t['type'] == task['task_type'])
            payload = json.loads(task['messages'][1]['content'])
            expected = item.get('source_given_conditions', [])
            self.assertEqual(len([k for k in payload['references'] if k.startswith('condition-')]), len(expected))
            self.assertEqual([v['text'] for v in payload.get('source_given_conditions', [])],
                             [v['quote'] for v in expected])
            self.assertFalse(payload['chart']['engine_verified'])
            if task['task_type'] in ('role_selection', 'chart_evidence'):
                self.assertNotIn('source_given_conditions', payload)
            for value in payload.get('source_given_conditions', []):
                self.assertEqual(value['verification'], 'author_given_condition_not_engine_recomputed')

    def test_given_condition_may_not_supply_the_recovery_judgment(self):
        def change(review):
            case = review['cases'][0]
            item = next(t for t in case['stages'][0]['tasks'] if t['type'] == 'evidence_synthesis')
            item['source_given_conditions'][0]['quote'] = '失物可以找回'
        with self.assertRaisesRegex(ValueError, 'contains a judgment'):
            self.build_changed(change)

    def test_book_coverage_counts_only_cases_with_actual_reviewed_tasks(self):
        coverage = json.loads((ROOT / 'data/provenance/method_task_coverage_v1.json').read_bytes())
        self.assertEqual(coverage['book_cases'], len(coverage['case_rows']))
        reviewed = [r for r in coverage['case_rows'] if r['source_reviewed_method_tasks'] > 0]
        self.assertEqual(coverage['source_reviewed_cases'], len(reviewed))
        self.assertEqual(coverage['pending_cases'], 90)
        self.assertEqual(coverage['source_reviewed_tasks'], sum(r['source_reviewed_method_tasks'] for r in reviewed))
        self.assertEqual({r['case_id'] for r in reviewed}, {t['case_id'] for t in self.tasks})
