"""Whole supplied satellite narrative, immutable provenance and chronology gates."""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.inspection import inspect_case
from qimenllm.cases.repository import CaseRepository
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.importer import ImportConflict, import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from support import DatabaseTest, case_content_text


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = '2022ad633e935eeca7970b74c0df7af8c980ebb2867def3a0d2593e32656ac9a'


class ApplicationCaseTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.curated = json.loads((ROOT/'data/structured/shenqi/application_overview_cases.json').read_bytes())
        path = ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHA}.bin'
        if not path.exists():
            path = ROOT/'data/raw_books'/f'{SOURCE_SHA}.utf8'
        self.content = path.read_bytes()
        self.source = self._source()

    def _source(self, *, book_key='source-case-fixture', chapter_key='application-overview'):
        return import_chapter(self.db, self.raw, self.content,
            book_key=book_key, book_title='神奇之门', chapter_key=chapter_key,
            chapter_title='奇门遁甲应用概述', sequence=6,
            origin='actual-user-supplied-case-regression', confirmed=False)

    def _install(self):
        result = import_cases(self.db, self.source['revision_id'], self.curated)
        self.case_id = result['cases'][0]['case_id']
        self.event_id = result['cases'][0]['event_ids'][0]
        return result

    def _counts(self):
        with connect(self.db) as conn:
            return {table: conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                    for table in ('data_versions', 'source_spans', 'event_families', 'cases',
                        'events', 'case_events', 'charts', 'case_records', 'evidence_links',
                        'training_tasks', 'dataset_releases', 'split_assignments')}

    def test_one_whole_case_one_event_and_partial_original_chart_without_training(self):
        result = self._install()
        counts = self._counts()
        self.assertEqual([counts[t] for t in ('cases','events','event_families','charts','case_records')],
                         [1,1,1,1,10])
        self.assertEqual([counts[t] for t in ('training_tasks','dataset_releases','split_assignments')], [0,0,0])
        self.assertEqual(result['training_tasks_added'], 0)
        full = inspect_case(self.db, self.case_id)
        self.assertEqual(full['source_completeness'], 'complete')
        self.assertFalse(full['outcome_independently_verified'])
        self.assertEqual(full['source']['source_acceptance'], 'pending')
        event = full['events'][0]
        self.assertEqual(event['chronology_status'], 'ordered')
        self.assertEqual(event['chronology_interpretation'], 'source_narrative_order')
        chart = event['charts'][0]
        self.assertEqual(chart['source_or_engine'], 'original')
        self.assertEqual(chart['validation_status'], 'original_unparsed')
        # The original import artifact supplies these facts inside the immutable
        # payload, without separately populating the SQL metadata indexes.
        self.assertIsNone(chart['input_datetime'])
        self.assertIsNone(chart['location_json'])
        self.assertEqual(chart['chart']['input_datetime'], '1995-01-26T06:40:00')
        self.assertEqual(chart['chart']['location']['name_as_written'], '我国西昌卫星发射中心')
        self.assertIsNone(chart['timezone'])
        self.assertIsNone(chart['casting_method'])
        self.assertFalse(chart['chart']['complete_nine_palace_chart'])
        self.assertFalse(chart['chart']['calendar_recomputed'])
        for field in ('palaces','heaven_plate','earth_plate','doors','stars','deities','voids','horse'):
            self.assertIsNone(chart['chart'][field])
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_exact_source_story_and_later_same_event_comment_preserved(self):
        self._install()
        full = inspect_case(self.db, self.case_id)
        lines = self.content.decode('utf-8').splitlines(keepends=True)
        event = full['events'][0]
        self.assertEqual([s['text'] for s in event['narrative_sources']],
                         [''.join(lines[51:68]), lines[203]])
        self.assertEqual(len(event['records']), 10)
        for record in event['records']:
            self.assertEqual(record['text'], record['source']['text'])
            self.assertEqual(record['source']['source_sha256'], SOURCE_SHA)
            self.assertEqual(record['text'].encode(), self.content[
                record['source']['byte_start']:record['source']['byte_end']])
        self.assertEqual(event['records'][-1]['knowledge_phase'], 'unknown')
        self.assertIn('反悔', event['records'][-1]['text'])
        self.assertEqual(len(event['evidence']), 17)
        self.assertEqual(len({r['chart_id'] for r in event['records']}), 1)
        self.assertEqual(digest(self.content), SOURCE_SHA)
        self.assertFalse(self.content.endswith(b'\n'))

    def test_pre_prediction_view_does_not_expose_targets_feedback_or_later_comment(self):
        self._install()
        view = inspect_case(self.db, self.case_id, 'before_prediction')
        event = view['events'][0]
        self.assertEqual([r['sequence'] for r in event['records']], [0,1])
        self.assertEqual(event['charts'], [])
        self.assertEqual(event['withheld_records'], 8)
        self.assertEqual(event['cutoff_sequence'], 2)
        self.assertNotIn('background', event)
        self.assertNotIn('narrative_sources', event)
        self.assertNotIn('source', view)
        self.assertNotIn('title', view)
        self.assertFalse(view['training_export'])
        self.assertFalse(event['training_eligible'])
        for record in event['records']:
            self.assertNotIn('payload', record)
            self.assertNotIn('chart_id', record)
        serialized = case_content_text(view)
        for forbidden in ('发射不成功','星箭爆炸','死6人','伤23人','1.6亿美元','天牢华盖','休囚','反悔'):
            self.assertNotIn(forbidden, serialized)

    def test_role_prediction_and_feedback_remain_distinct_and_uncertainty_preserved(self):
        self._install()
        event = inspect_case(self.db, self.case_id)['events'][0]
        role = next(r for r in event['records'] if r['kind']=='role_selection')
        prediction = next(r for r in event['records'] if r['kind']=='prediction')
        feedback = next(r for r in event['records'] if r['kind']=='feedback')
        self.assertEqual(role['payload']['selected_symbol'], '九天')
        self.assertFalse(role['payload']['generalize_to_all_space_launch_questions'])
        self.assertIn('恐怕', prediction['text'])
        self.assertIsNone(prediction['payload']['prediction_success_label'])
        self.assertEqual(feedback['knowledge_phase'], 'post_feedback')
        self.assertEqual(feedback['payload']['feedback_status'], 'author_reported')
        self.assertFalse(feedback['payload']['independent_confirmed'])
        self.assertEqual(feedback['payload']['insurance_as_written']['coverage_usd'], 160000000)
        self.assertIsNone(feedback['payload']['insurance_as_written']['payout_or_actual_loss_amount'])
        self.assertTrue(all(r['reported_at'] is None for r in event['records']))

    def test_partial_original_preserves_center_hosting_and_two_overlays_without_guessed_coordinates(self):
        self._install()
        chart = inspect_case(self.db, self.case_id)['events'][0]['charts'][0]['chart']
        self.assertEqual(chart['duty']['zhifu_landing_original_palace'], 5)
        self.assertEqual(chart['duty']['zhifu_layout_palace'], 2)
        pairs = {f['fact_key']: f for f in chart['reported_plate_facts']}
        for key, earth in (('xin_gui_overlay','癸'), ('xin_geng_overlay','庚')):
            self.assertEqual((pairs[key]['heaven_stem'], pairs[key]['earth_stem']), ('辛',earth))
            self.assertIsNone(pairs[key]['palace'])
        self.assertFalse(chart['retrospective_addendum']['before_prediction_eligible'])
        self.assertEqual(chart['retrospective_addendum']['knowledge_phase'], 'unknown')

    def test_exact_repeated_import_does_not_create_rows_or_versions(self):
        first = self._install()
        before = self._counts()
        duplicate = import_cases(self.db, self.source['revision_id'], self.curated)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['data_version'], first['data_version'])
        self.assertEqual(self._counts(), before)
        self.assertTrue(all(value==0 for value in duplicate['added'].values()))

    def test_changed_curation_is_rejected_without_mutating_existing_case(self):
        self._install()
        before = self._counts()
        original = inspect_case(self.db, self.case_id)
        changed = copy.deepcopy(self.curated)
        changed['cases'][0]['title'] += ' changed'
        with self.assertRaises(ImportConflict):
            import_cases(self.db, self.source['revision_id'], changed)
        self.assertEqual(self._counts(), before)
        self.assertEqual(inspect_case(self.db, self.case_id), original)

    def test_invalid_hash_text_source_range_or_chart_link_rolls_back_entire_import(self):
        before = self._counts()
        for mode in ('hash','text','range','chart'):
            bad = copy.deepcopy(self.curated)
            record = bad['cases'][0]['events'][0]['records'][0]
            if mode=='hash': bad['source_sha256']='0'*64
            elif mode=='text': record['text'] += ' invented'
            elif mode=='range':
                record['source_lines']=[1,1]
                record['text']=self.content.decode('utf-8').splitlines()[0]
            else: record['chart_key']='nonexistent-chart'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                import_cases(self.db, self.source['revision_id'], bad)
            self.assertEqual(self._counts(), before)

    def test_invalid_temporal_labels_and_unearned_verification_are_blocked(self):
        before = self._counts()
        for mode in ('feedback_as_pre','later_as_pre','verified_chronology','engine_verified_chart','confirmed_complete'):
            bad=copy.deepcopy(self.curated); case=bad['cases'][0]; event=case['events'][0]
            if mode=='feedback_as_pre': event['records'][-2]['knowledge_phase']='pre_prediction'
            elif mode=='later_as_pre': event['records'][-1]['knowledge_phase']='pre_prediction'
            elif mode=='verified_chronology': event['chronology_status']='verified'
            elif mode=='engine_verified_chart': event['charts'][0]['validation_status']='engine_verified'
            else: case['completeness']='confirmed_complete'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                import_cases(self.db,self.source['revision_id'],bad)
            self.assertEqual(self._counts(),before)

    def test_explicit_global_family_key_groups_same_known_event_across_sources(self):
        first=self._install()
        other=self._source(book_key='another-explicit-source')
        second=import_cases(self.db,other['revision_id'],self.curated)
        self.assertEqual(first['cases'][0]['family_id'],second['cases'][0]['family_id'])
        self.assertNotEqual(first['cases'][0]['case_id'],second['cases'][0]['case_id'])
        self.assertNotEqual(first['cases'][0]['event_ids'],second['cases'][0]['event_ids'])
        self.assertEqual(self._counts()['event_families'],1)
        self.assertEqual(self._counts()['events'],2)
        self.assertEqual(self._counts()['training_tasks'],0)
        # Same explicit family key cannot silently acquire different metadata.
        third=self._source(book_key='third-explicit-source')
        bad=copy.deepcopy(self.curated)
        bad['cases'][0]['family']['description']='different unrelated event'
        before=self._counts()
        with self.assertRaises(ImportConflict): import_cases(self.db,third['revision_id'],bad)
        self.assertEqual(self._counts(),before)

    def test_database_append_only_and_snapshot_restore_preserve_case_view(self):
        self._install()
        original=inspect_case(self.db,self.case_id)
        with connect(self.db) as conn:
            for query in ("UPDATE cases SET title='rewritten'", "UPDATE charts SET chart_json='{}'",
                          "UPDATE case_records SET knowledge_phase='pre_prediction' WHERE kind='feedback'",
                          "DELETE FROM evidence_links"):
                with self.assertRaises(sqlite3.IntegrityError): conn.execute(query)
        export_snapshot(self.db,self.raw,self.root/'snapshot')
        restored=self.root/'restored.sqlite3'; restored_raw=self.root/'restored-raw'
        restore_snapshot(self.root/'snapshot',restored,restored_raw)
        self.assertEqual(inspect_case(restored,self.case_id),original)
        self.assertTrue(audit(restored,restored_raw)['ok'])
        with self.assertRaises(KeyError): CaseRepository(self.db).project_task('not-created')

    def test_bad_view_and_unknown_case_do_not_fall_back_to_unrestricted_narrative(self):
        self._install()
        with self.assertRaises(ValueError): inspect_case(self.db,self.case_id,'anything')
        with self.assertRaises(KeyError): inspect_case(self.db,'missing','before_prediction')
