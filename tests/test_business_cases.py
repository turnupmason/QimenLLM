"""Regression for one confirmed, fourteen-story business chapter and its 16 real charts."""
import json
import tempfile
import unittest
from pathlib import Path

from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import BUSINESS_SHA
from qimenllm.knowledge.business import install_business
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.rules.candidates import install_candidates

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structured/shenqi'
SRC = ROOT / 'data/provenance/uploads/business_source_20261017.utf8'


class BusinessChapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / 'business.sqlite3'
        cls.raw = Path(cls.tmp.name) / 'raw'
        restore_snapshot(ROOT / 'data/snapshots/current', cls.db, cls.raw)
        cls.body = SRC.read_bytes()
        cls.curated = json.loads((DATA / 'business_curated.json').read_bytes())
        cls.cases_json = json.loads((DATA / 'business_cases.json').read_bytes())
        cls.candidates_json = json.loads((DATA / 'business_rule_candidates.json').read_bytes())
        cls.gold = json.loads((DATA / 'business_chart_gold.json').read_bytes())
        cls.source = import_chapter(
            cls.db, cls.raw, cls.body, book_key='shenqi-user-text-v1',
            book_title='神奇之门', chapter_key='business-finance',
            chapter_title='经营求财预测', sequence=12,
            origin='user-supplied-inline-business-chapter-2026-10-17; source-sha256:' + BUSINESS_SHA)
        cls.annotation = install_business(cls.db, cls.source['revision_id'], cls.curated)
        cls.case_result = import_cases(cls.db, cls.source['revision_id'], cls.cases_json)
        cls.candidate_result = install_candidates(cls.db, cls.source['revision_id'], cls.candidates_json)
        cls.service = QimenService(cls.db)
        cls.catalog = cls.service.cases('business-finance')['cases']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bytes_and_completeness(self):
        self.assertEqual(digest(self.body), BUSINESS_SHA)
        self.assertEqual((len(self.body), len(self.body.decode()), len(self.body.decode().splitlines())),
                         (56154, 22030, 1456))
        self.assertEqual(self.gold['source_sha256'], BUSINESS_SHA)
        self.assertEqual(len(self.catalog), 14)
        self.assertEqual(self.gold['count']['source_charts'], 16)
        self.assertEqual(self.gold['count']['source_nine_palace_rows'], 144)
        self.assertEqual(len(self.curated['groups']), 26)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_all_fourteen_full_stories_exact_source(self):
        lines = self.body.decode().splitlines(keepends=True)
        for index, case in enumerate(self.cases_json['cases']):
            first,last = case['source_ranges'][0]
            source_text = ''.join(lines[first-1:last])
            self.assertEqual(case['source_selectors'][0]['source_quote'], source_text)
            result = self.service.case(self.catalog[index]['case_id'])
            self.assertEqual(result['source']['text'], source_text)
            self.assertEqual(result['source_completeness'], 'confirmed_complete')
            for event in result['events']:
                for record in event['records']:
                    span = record['source']
                    self.assertEqual(record['text'].encode(), self.body[span['byte_start']:span['byte_end']])

    def test_sixteen_distinct_literal_chart_tables_and_one_nonstandard_center(self):
        ids = set()
        for index, case in enumerate(self.catalog):
            for event in case['events']:
                for chart_id in event['chart_ids']:
                    self.assertNotIn(chart_id, ids)
                    ids.add(chart_id)
                    projected = self.service.case_chart(case['case_id'], chart_id)
                    self.assertEqual(projected['status'], 'projected')
                    self.assertEqual(len(projected['palaces']), 9)
                    self.assertTrue(projected['raw_table_complete'])
                    self.assertFalse(projected['original_chart_modified'])
                    self.assertFalse(projected['engine_verified'])
                    self.assertFalse(projected['calendar_recomputed'])
        self.assertEqual(len(ids), 16)
        ninth = self.catalog[8]
        chart_id = ninth['events'][0]['chart_ids'][0]
        projected = self.service.case_chart(ninth['case_id'],chart_id)
        self.assertEqual(projected['palaces']['5']['source']['column_cells'][2], '禽己')
        self.assertEqual(projected['palaces']['5']['earth_stem'], '己')
        self.assertEqual(projected['palaces']['5']['source_center_literal_marker'], '禽')

    def test_lottery_single_story_three_provided_charts_only(self):
        lottery = self.catalog[11]
        result = self.service.case(lottery['case_id'])
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(len(result['events'][0]['chart_ids']), 3)
        raw = result['source']['text']
        for expected in ('丙午时', '丁未时', '丁巳时', '元月27日', '元月28日', '张志春按'):
            self.assertIn(expected,raw)
        before = self.service.case(lottery['case_id'], 'before_prediction')
        # Source-stage visibility is conservative: no complete case/post-hoc outcomes.
        from support import case_content_text
        content = case_content_text(before)
        self.assertNotIn('11点10分', content)
        self.assertNotIn('1997年元月28日，庚午日', content)

    def test_ten_reference_candidates_no_execution_or_training(self):
        self.assertEqual(self.candidates_json['candidate_count'], 10)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0], 43)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM charts").fetchone()[0], 45)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM training_tasks").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM dataset_releases").fetchone()[0], 0)
        result = self.service.rule_candidates(
            {'domain':'business_finance','analysis_context':'business_method_01'},
            domain='business_finance',method='shenqi_business_reference_v1')
        match = [c for c in result['candidates'] if c['candidate_key']=='business_method_01']
        self.assertEqual(len(match),1)
        self.assertEqual(match[0]['symbolic_status'],'applicable')
        self.assertEqual(match[0]['activation_status'],'reference_only')

    def test_idempotent_reimport_no_new_version(self):
        with connect(self.db) as conn:
            before = conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        other = import_chapter(
            self.db,self.raw,self.body,book_key='shenqi-user-text-v1',
            book_title='神奇之门',chapter_key='business-finance',
            chapter_title='经营求财预测',sequence=12,
            origin='same-confirmed-source-replay')
        self.assertTrue(other['duplicate'])
        self.assertTrue(import_cases(self.db,self.source['revision_id'],self.cases_json)['duplicate'])
        self.assertTrue(install_candidates(self.db,self.source['revision_id'],self.candidates_json)['duplicate'])
        install_business(self.db,self.source['revision_id'],self.curated)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],before)


if __name__ == '__main__':
    unittest.main()
