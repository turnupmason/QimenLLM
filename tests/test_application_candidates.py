"""Independent supplied-source gold for candidate applicability, not predictions."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from qimenllm.knowledge.db import connect, digest, initialize, now
from qimenllm.knowledge.importer import import_chapter
from qimenllm.rules.candidates import install_candidates, inspect_candidates
from qimenllm.rules.selector import RuleSelector
from qimenllm.retrieval.repository import KnowledgeRepository
from support import DatabaseTest


ROOT = Path(__file__).resolve().parents[1]
SHA = '2022ad633e935eeca7970b74c0df7af8c980ebb2867def3a0d2593e32656ac9a'


def artifact(name):
    choices = [ROOT / 'data/structured/shenqi' / name, ROOT / 'work' / name]
    return json.loads(next(path for path in choices if path.exists()).read_bytes())


class ApplicationCandidateTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.curated = artifact('application_overview_rule_candidates.json')
        self.gold = artifact('application_overview_regression_cases.json')
        choices = [ROOT / 'data/snapshots/current/raw' / f'{SHA}.bin',
                   ROOT / 'data/raw_books' / f'{SHA}.utf8']
        self.content = next(path for path in choices if path.exists()).read_bytes()
        self.source = import_chapter(self.db, self.raw, self.content,
            book_key='shenqi-user-text-v1', book_title='神奇之门', chapter_key='application-overview',
            chapter_title='奇门遁甲应用概述', sequence=6, origin='actual-supplied-text-regression')
        self.installed = install_candidates(self.db, self.source['revision_id'], self.curated)

    def decisions(self, context, **kwargs):
        result = inspect_candidates(self.db, context, **kwargs)
        self.assertEqual(result['status'], 'inspected')
        self.assertEqual(result['role_bindings'], [])
        self.assertFalse(result['professional_analysis_completed'])
        self.assertIsNone(result['model_analysis'])
        return {r['candidate_key']: r for r in result['candidates']}

    def test_all_independent_source_condition_gold(self):
        self.assertEqual(self.gold['selection_case_count'], 72)
        for example in self.gold['selection_cases']:
            with self.subTest(example['key']):
                expected = example['expected']
                actual = self.decisions(example['context'])[expected['candidate_key']]
                self.assertEqual(actual['symbolic_status'], expected['symbolic_status'])
                self.assertEqual(actual['role_bindings'], [])
                self.assertEqual(actual['activation_status'], 'reference_only')
                self.assertEqual(actual['source_acceptance'], 'confirmed')
                if 'missing_fields' in expected:
                    self.assertEqual(actual['missing'], sorted(expected['missing_fields']))
                if 'reference_side' in expected:
                    self.assertEqual(actual['hypothetical_role_recommendation']['symbols'], [expected['reference_side']])
                if 'record_revision' in expected:
                    self.assertEqual(actual['record_revision'], expected['record_revision'])

    def test_source_quotes_and_original_bytes_are_exact(self):
        self.assertEqual(digest(self.content), SHA)
        self.assertEqual(self.installed['added'], 61)
        lines = self.content.decode().splitlines()
        actual = self.decisions({})
        for candidate in self.curated['candidates']:
            row = actual[candidate['key']]
            selected = candidate['source_lines']
            quote = '\n'.join(lines[min(selected)-1:max(selected)])
            self.assertEqual(row['source']['quote'], quote)
            self.assertEqual(row['source']['sha256'], SHA)
            self.assertTrue(row['source']['source_id'])
            self.assertEqual(row['source']['excerpt'].rstrip('\r\n'), quote)

    def test_multiple_methods_stay_disputed_without_implicit_default(self):
        for example in self.gold['multi_method_conflict_gold']:
            with self.subTest(example['key']):
                actual = self.decisions(example['context'])
                keys = example['expected'].get('candidate_keys', [example['expected'].get('source_candidate')])
                for key in keys:
                    self.assertEqual(actual[key]['symbolic_status'], 'disputed')
                    self.assertIsNone(actual[key]['hypothetical_role_recommendation'])
        context = self.gold['multi_method_conflict_gold'][0]['context']
        selected = self.decisions(context, method='timing_geng_day_polarity')
        self.assertEqual(selected['timing_geng_day_polarity']['symbolic_status'], 'applicable')
        self.assertEqual(selected['timing_geng_hour_star_polarity']['symbolic_status'], 'excluded')
        self.assertIn('method_mismatch', selected['timing_geng_hour_star_polarity']['reasons'])

    def test_database_query_filters_but_keeps_rejection_reasons(self):
        result = inspect_candidates(self.db, {'target_relationship': 'elder_brother', 'age_difference': 50}, domain='health')
        self.assertEqual(result['query']['parameters'], ['source_selection_candidate', 'health'])
        self.assertTrue(result['candidates'])
        self.assertTrue(all(r['domain'] == 'health' for r in result['candidates']))
        by_key = {r['candidate_key']: r for r in result['candidates']}
        self.assertEqual(by_key['health_sibling_patient']['symbolic_status'], 'applicable')
        self.assertEqual(by_key['health_elder_generation_patient']['symbolic_status'], 'excluded')
        self.assertTrue(by_key['health_elder_generation_patient']['reasons'])
        proposal = by_key['health_sibling_patient']['hypothetical_role_recommendation']
        self.assertEqual(proposal['symbols'], ['month_stem'])
        self.assertTrue(proposal['hypothetical'])
        self.assertFalse(proposal['automatic_activation'])

    def test_missing_false_null_boolean_and_numeric_types_are_distinct(self):
        context = {'domain': 'timing', 'timing_task': 'candidate_selection',
                   'chief_relation': 'none', 'heaven_instrument_branch_relation': 'combine'}
        key = 'timing_instrument_combine_use_clash'
        self.assertEqual(self.decisions(context)[key]['symbolic_status'], 'conditional')
        self.assertEqual(self.decisions({**context, 'chief_in_void': None})[key]['symbolic_status'], 'conditional')
        self.assertEqual(self.decisions({**context, 'chief_in_void': False})[key]['symbolic_status'], 'applicable')
        self.assertEqual(self.decisions({**context, 'chief_in_void': 0})[key]['symbolic_status'], 'excluded')
        self.assertEqual(self.decisions({**context, 'chief_in_void': True})[key]['symbolic_status'], 'excluded')

    def test_reinstall_is_idempotent_and_changed_candidate_is_not_silent(self):
        with connect(self.db) as conn:
            count = conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        repeated = install_candidates(self.db, self.source['revision_id'], self.curated)
        self.assertEqual(repeated['added'], 0)
        changed = deepcopy(self.curated)
        changed['candidates'][0]['notes'].append('changed annotation needs another version')
        with self.assertRaisesRegex(ValueError, 'explicit version'):
            install_candidates(self.db, self.source['revision_id'], changed)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0], count)

    def test_append_only_revision_upgrade_preserves_old_records_and_selects_latest(self):
        older = deepcopy(self.curated)
        history = {c['key']: c for c in older.pop('historical_candidates')}
        older['candidates'] = [history.get(c['key'], c) for c in older['candidates']]
        older['candidate_record_count'] = 58
        db = self.root / 'revision-upgrade.sqlite3'; initialize(db)
        source = import_chapter(db, self.root / 'revision-raw', self.content,
            book_key='shenqi-user-text-v1', book_title='神奇之门', chapter_key='application-overview',
            chapter_title='奇门遁甲应用概述', sequence=6, origin='actual-supplied-text-regression')
        self.assertEqual(install_candidates(db, source['revision_id'], older)['added'], 58)
        with connect(db) as conn:
            original = {r['item_id']: tuple(r) for r in conn.execute('SELECT * FROM knowledge_items')}
        self.assertEqual(install_candidates(db, source['revision_id'], self.curated)['added'], 3)
        result = inspect_candidates(db, {'domain': 'timing', 'timing_task': 'candidate_selection',
            'chief_relation': 'clash', 'chief_in_void': False,
            'heaven_instrument_branch_relation': 'neither_combine_nor_clash'})
        self.assertEqual(result['candidate_count'], 58)
        selected = {r['candidate_key']: r for r in result['candidates']}
        self.assertEqual(selected['timing_star_door_fallback']['record_revision'], 2)
        self.assertEqual(selected['timing_star_door_fallback']['symbolic_status'], 'excluded')
        self.assertIn('如果既不冲，又不刑，又不空', selected['timing_star_door_fallback']['source']['quote'])
        with connect(db) as conn:
            after = {r['item_id']: tuple(r) for r in conn.execute('SELECT * FROM knowledge_items')}
            self.assertEqual(len(after), 61)
            for key, value in original.items(): self.assertEqual(after[key], value)
        skipped = deepcopy(self.curated)
        skipped['candidates'] = [deepcopy(next(c for c in skipped['candidates'] if c.get('record_revision') == 2))]
        skipped['candidates'][0]['record_revision'] = 4
        skipped['historical_candidates'] = []; skipped['candidate_count'] = 1; skipped['candidate_record_count'] = 1
        with self.assertRaisesRegex(ValueError, 'contiguous prior'):
            install_candidates(db, source['revision_id'], skipped)
        self.assertEqual(install_candidates(db, source['revision_id'], self.curated)['added'], 0)

    def test_invalid_artifact_rejects_before_any_new_record(self):
        with connect(self.db) as conn:
            before = {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                      for t in ('knowledge_items', 'source_spans', 'data_versions')}
        changed = deepcopy(self.curated)
        extra = deepcopy(changed['candidates'][0]); extra['key'] = 'new_key_not_written'
        changed['candidates'].insert(0, extra); changed['candidate_count'] += 1; changed['candidate_record_count'] += 1
        changed['candidates'][-1]['source_quote'] += 'not in supplied original'
        with self.assertRaisesRegex(ValueError, 'quote differs'):
            install_candidates(self.db, self.source['revision_id'], changed)
        changed = deepcopy(self.curated); changed['candidates'][-1]['require'][0]['op'] = 'matches'
        with self.assertRaisesRegex(ValueError, 'protocol'):
            install_candidates(self.db, self.source['revision_id'], changed)
        with connect(self.db) as conn:
            for table, count in before.items():
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], count)

    def test_original_confirmation_alone_cannot_promote_executable_rules(self):
        context = {'domain': 'health', 'target_relationship': 'self', 'source_confirmed': True, 'compiled': True}
        before = self.decisions(context)['health_self_patient']
        self.assertEqual(before['status'], 'reference_only')
        with connect(self.db) as conn:
            conn.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?,?)',
                (str(uuid4()), self.source['revision_id'], 'confirmed', 'test fixture',
                 'Original accepted independently of executable compilation', now()))
        after = self.decisions(context)['health_self_patient']
        self.assertEqual(after['source_acceptance'], 'confirmed')
        self.assertEqual(after['status'], 'reference_only')
        self.assertEqual(after['role_bindings'], [])
        professional = KnowledgeRepository(self.db).candidates('health')
        self.assertEqual(professional['rules'], [])
        self.assertEqual(RuleSelector().bind(professional['rules']), ())
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM rules').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM knowledge_items WHERE compiled=1').fetchone()[0], 0)

    def test_disputed_source_preserves_text_and_blocks_recommendations(self):
        with connect(self.db) as conn:
            conn.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?,?)',
                (str(uuid4()), self.source['revision_id'], 'disputed', 'test fixture', 'Technical source review', now()))
        row = self.decisions({'domain': 'health', 'target_relationship': 'self'})['health_self_patient']
        self.assertEqual(row['symbolic_status'], 'applicable')
        self.assertEqual(row['status'], 'disputed')
        self.assertIsNone(row['hypothetical_role_recommendation'])
        self.assertIn('如果是患者自己求测，则日干为他本人', row['source']['quote'])

    def test_invalid_context_and_conflicting_domain_are_explicit(self):
        with self.assertRaises(ValueError): inspect_candidates(self.db, [])
        with self.assertRaises(ValueError): inspect_candidates(self.db, {}, domain='')
        with self.assertRaises(ValueError): inspect_candidates(self.db, {}, method=1)
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            inspect_candidates(self.db, {'domain': 'health'}, domain='crime')
