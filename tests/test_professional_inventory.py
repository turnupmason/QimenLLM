"""Complete source retention and refusal to promote a review queue to SFT."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from qimenllm.knowledge.snapshot import restore_snapshot


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'professional_inventory', ROOT / 'training/professional_inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class ProfessionalInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / 'source.sqlite3'
        restore_snapshot(ROOT / 'data/snapshots/current', cls.db, Path(cls.tmp.name) / 'raw')
        cls.assignments = json.loads((ROOT / 'data/splits/author_initial_release_v2.json').read_bytes())['family_assignments']
        before = cls.db.read_bytes()
        cls.events, cls.report = inventory.inventory(cls.db, cls.assignments)
        cls.unchanged = before == cls.db.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_book_records_and_charts_retained_without_database_writes(self):
        self.assertTrue(self.unchanged)
        self.assertEqual(len(self.events), 106)
        self.assertEqual(sum(len(e['records']) for e in self.events), 1579)
        self.assertEqual(sum(len(e['charts']) for e in self.events), 104)
        self.assertEqual(self.report['source_documents_verified'], 26)
        self.assertEqual(self.report['source_spans_verified'], 3275)
        self.assertEqual(len({e['family_id'] for e in self.events}), 94)
        self.assertTrue(all(e['split'] == self.assignments[e['family_id']] for e in self.events))

    def test_future_and_unknown_records_are_retained_but_never_exported_as_input(self):
        records = [r for e in self.events for r in e['records']]
        self.assertTrue(any(r['knowledge_phase'] == 'unknown' for r in records))
        self.assertTrue(any(r['kind'] == 'feedback' for r in records))
        for event in self.events:
            self.assertIsNone(event['model_input'])
            self.assertIs(event['sft_eligible'], False)
            self.assertNotIn('messages', event)
        self.assertFalse(self.report['ready_for_training'])
        self.assertEqual(self.report['sft_eligible_tasks'], 0)
        self.assertFalse(self.report['queue_counts_are_training_tasks'])

    def test_missing_frozen_family_is_rejected_instead_of_resplitting(self):
        missing = dict(self.assignments)
        del missing[self.events[0]['family_id']]
        with self.assertRaisesRegex(ValueError, 'absent from frozen'):
            inventory.inventory(self.db, missing)

    def test_record_not_equal_to_source_is_rejected(self):
        altered = Path(self.tmp.name) / 'altered.sqlite3'
        with sqlite3.connect(self.db) as source, sqlite3.connect(altered) as dest:
            source.backup(dest)
            dest.execute('DROP TRIGGER immutable_case_records_update')
            dest.execute("UPDATE case_records SET text='fabricated' WHERE rowid=(SELECT MIN(rowid) FROM case_records)")
        with self.assertRaisesRegex(ValueError, 'Record differs from original source'):
            inventory.inventory(altered, self.assignments)
