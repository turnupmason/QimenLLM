"""Owner attestations, append-only acceptance and separate engineering states."""
import json
import io
from contextlib import redirect_stdout
from unittest.mock import patch

from qimenllm.cases.inspection import inspect_case
from qimenllm.cli import main
from qimenllm.knowledge.db import APPEND_ONLY, connect
from qimenllm.knowledge.importer import add_annotations, import_chapter
from qimenllm.knowledge.source_confirmation import (
    DECLARATION_SOURCE, accept_user_supplied_sources, source_confirmation,
)
from support import DatabaseTest


class SourceConfirmationTests(DatabaseTest):
    def test_cli_maintenance_import_uses_standing_confirmation_without_confirmation_flag(self):
        source_file=self.root/'source.txt'
        source_file.write_bytes(b'Neutral source for maintainer CLI confirmation.')
        output=io.StringIO()
        with patch('qimenllm.cli.sync_github',return_value={'status':'synced'}),redirect_stdout(output):
            code=main(['--db',str(self.db),'--raw-dir',str(self.raw),'import-chapter',str(source_file),
                '--book-key','fixture','--book-title','Fixture','--chapter-key','one',
                '--chapter-title','One','--sequence','1','--origin','unit-test'])
        self.assertEqual(code,0)
        result=json.loads(output.getvalue())
        self.assertEqual(result['source_confirmation']['source_acceptance'],'confirmed')
        self.assertTrue(result['source_confirmation']['user_declares_independent_verification'])

    def _rows(self):
        with connect(self.db) as conn:
            return {table: [tuple(row) for row in conn.execute('SELECT * FROM '+table+' ORDER BY rowid')]
                    for table in APPEND_ONLY}

    def _review(self, revision_id):
        with connect(self.db) as conn:
            return source_confirmation(conn, revision_id)

    def _case_record(self, source, kind='outcome', phase='post_feedback'):
        with connect(self.db) as conn:
            raw = conn.execute('SELECT content FROM raw_documents').fetchone()[0].decode()
            conn.execute('''INSERT INTO case_records VALUES
                ('record','event',NULL,0,?,?,?,'author',?,?,'author_explicit',NULL)''',
                (kind, phase, source['source_id'], raw,
                 json.dumps({'independent_confirmed':False})))

    def test_maintainer_import_defaults_to_owner_attestation_with_explicit_basis(self):
        result = import_chapter(self.db, self.raw, b'Neutral engineering source.',
            book_key='fixture', book_title='Fixture', chapter_key='one', chapter_title='One',
            sequence=1, origin='unit-test')
        confirmation = result['source_confirmation']
        self.assertEqual(confirmation['source_acceptance'], 'confirmed')
        self.assertTrue(confirmation['source_facts_user_confirmed'])
        self.assertTrue(confirmation['user_declares_independent_verification'])
        self.assertEqual(confirmation['verification_basis'], 'user_attestation')
        self.assertEqual(confirmation['declaration_source'], DECLARATION_SOURCE)
        self.assertFalse(confirmation['system_performed_independent_verification'])

    def test_explicit_pending_opt_out_is_preserved_until_owner_policy_applied(self):
        source = self.ingest(confirmed=False)
        self.assertEqual(self._review(source['revision_id'])['source_acceptance'], 'pending')
        report = accept_user_supplied_sources(self.db)
        self.assertEqual(report['appended_reviews'], 1)
        self.assertTrue(self._review(source['revision_id'])['source_facts_user_confirmed'])

    def test_bulk_acceptance_appends_audit_and_preserves_every_existing_authoritative_row(self):
        first = self.ingest(confirmed=False)
        second = self.ingest(b'Second neutral source.', chapter_key='two', chapter_title='Two', sequence=2)
        # A legacy review may be confirmed without recording the newer independent-confirmation declaration.
        with connect(self.db) as conn:
            conn.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?,?)',
                ('legacy-review', second['revision_id'], 'confirmed', 'user', 'Earlier explicit approval', 'legacy'))
        before = self._rows()
        report = accept_user_supplied_sources(self.db)
        after = self._rows()
        self.assertEqual(report['appended_reviews'], 2)
        self.assertEqual(len(after['data_versions']), len(before['data_versions'])+1)
        for table in APPEND_ONLY:
            self.assertEqual(after[table][:len(before[table])], before[table], table)
            if table not in ('data_versions', 'source_reviews'):
                self.assertEqual(after[table], before[table], table)
        self.assertEqual(after['data_versions'][-1][2], 'accept_user_supplied_sources')
        for source in (first, second):
            confirmation = self._review(source['revision_id'])
            self.assertTrue(confirmation['user_declares_independent_verification'])
            self.assertFalse(confirmation['system_performed_independent_verification'])

    def test_same_declaration_reapplication_is_fully_idempotent(self):
        self.ingest(confirmed=False)
        first = accept_user_supplied_sources(self.db)
        before = self._rows()
        again = accept_user_supplied_sources(self.db)
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['appended_reviews'], 0)
        self.assertEqual(again['data_version'], first['data_version'])
        self.assertEqual(self._rows(), before)

    def test_unknown_selected_revision_rejects_the_entire_confirmation(self):
        source = self.ingest(confirmed=False)
        before = self._rows()
        with self.assertRaises(ValueError):
            accept_user_supplied_sources(self.db, revision_ids=[source['revision_id'], 'unknown'])
        self.assertEqual(self._rows(), before)

    def test_restricted_revision_scope_does_not_accept_other_sources(self):
        first = self.ingest(confirmed=False)
        second = self.ingest(b'Second neutral source.', chapter_key='two', chapter_title='Two', sequence=2,
                             confirmed=False)
        report = accept_user_supplied_sources(self.db, revision_ids=[first['revision_id']])
        self.assertEqual(report['reviewed_revisions'], 1)
        self.assertEqual(self._review(second['revision_id'])['source_acceptance'], 'pending')

    def test_duplicate_import_accepts_without_replacing_original_or_reconfirming_twice(self):
        first = self.ingest(confirmed=False)
        accepted = self.ingest()
        self.assertTrue(accepted['duplicate'])
        self.assertEqual(accepted['revision_id'], first['revision_id'])
        self.assertNotEqual(accepted['data_version'], first['data_version'])
        before = self._rows()
        self.ingest()
        self.assertEqual(self._rows(), before)

    def test_acceptance_does_not_compile_rules_or_authorize_training(self):
        source = self.ingest(confirmed=False)
        add_annotations(self.db, source['revision_id'], [{'byte_start':0, 'byte_end':19,
            'locator':'neutral context', 'category':'commentary', 'payload':{'note':'engineering fixture'}}])
        accept_user_supplied_sources(self.db)
        with connect(self.db) as conn:
            row = conn.execute('SELECT * FROM knowledge_items').fetchone()
            self.assertEqual((row['compiled'], row['applicability_confirmed'], row['training_allowed']), (0,0,0))
            for table in ('rules', 'training_tasks', 'dataset_releases'):
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)

    def test_reported_outcome_is_confirmed_by_user_without_claiming_software_verification(self):
        source = self.seed_event()
        self._case_record(source)
        full = inspect_case(self.db, 'case')
        self.assertTrue(full['outcome_independently_verified'])
        confirmation = full['outcome_confirmation']
        self.assertEqual(confirmation['recorded_outcome_count'], 1)
        self.assertEqual(confirmation['verification_basis'], 'user_attestation')
        self.assertFalse(confirmation['system_performed_independent_verification'])
        self.assertFalse(confirmation['prediction_accuracy_evaluated'])
        record = full['events'][0]['records'][0]
        self.assertFalse(record['payload']['independent_confirmed'])
        self.assertTrue(record['source_confirmation'][
            'historical_annotation_superseded_by_current_user_attestation'])

    def test_missing_outcome_and_author_forecast_never_become_verified_outcomes(self):
        source = self.seed_event()
        self._case_record(source, 'prediction', 'prediction')
        full = inspect_case(self.db, 'case')
        self.assertFalse(full['outcome_independently_verified'])
        self.assertEqual(full['outcome_confirmation']['status'], 'no_normalized_outcome_record')

    def test_feedback_alone_does_not_invent_a_final_outcome(self):
        source = self.seed_event()
        self._case_record(source, 'feedback', 'post_feedback')
        full = inspect_case(self.db, 'case')
        self.assertFalse(full['outcome_independently_verified'])
        self.assertTrue(full['events'][0]['records'][0]['source_confirmation']['source_facts_user_confirmed'])

    def test_explicit_source_result_annotation_confirms_only_its_recorded_scope(self):
        source=self.seed_event()
        with connect(self.db) as conn:
            text=conn.execute('SELECT content FROM raw_documents').fetchone()[0].decode()
            for sequence,role in enumerate(('reported_first_lunar_month_conception','reported_delivery_result')):
                conn.execute('''INSERT INTO case_records VALUES
                    (?, 'event', NULL, ?, 'feedback', 'post_feedback', ?, 'author', ?, ?, 'author_explicit', NULL)''',
                    ('result-'+str(sequence),sequence,source['source_id'],text,json.dumps({'record_role':role})))
        full=inspect_case(self.db,'case')
        self.assertTrue(full['outcome_independently_verified'])
        self.assertEqual(full['outcome_confirmation']['recorded_outcome_roles'],
                         ['reported_delivery_result','reported_first_lunar_month_conception'])
        self.assertTrue(full['outcome_confirmation']['unreported_outcomes_not_inferred'])

    def test_pending_outcome_requires_user_attestation_and_never_defaults_to_verified(self):
        source = self.seed_event()
        self._case_record(source)
        with connect(self.db) as conn:
            conn.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?,?)',
                ('pending-fixture', source['revision_id'], 'pending', 'importer',
                 'Explicit neutral pending fixture', 'fixture'))
        full = inspect_case(self.db, 'case')
        self.assertFalse(full['outcome_independently_verified'])
        self.assertEqual(full['outcome_confirmation']['status'], 'not_user_confirmed')
        self.assertEqual(full['outcome_confirmation']['recorded_outcome_count'], 1)

    def test_pre_prediction_view_does_not_reveal_whether_outcome_was_recorded_or_confirmed(self):
        source = self.seed_event()
        self._case_record(source)
        before = inspect_case(self.db, 'case', 'before_prediction')
        self.assertFalse(before['outcome_independently_verified'])
        self.assertNotIn('outcome_confirmation', before)
        self.assertTrue(before['source_confirmation']['source_facts_user_confirmed'])
        for event in before['events']:
            self.assertNotIn('outcome_confirmation', event)
