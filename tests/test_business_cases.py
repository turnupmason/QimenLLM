"""Regression for the user-confirmed full Shenqi business chapter."""
import json
import tempfile
from pathlib import Path
import unittest

from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import BUSINESS_SHA, project_chart
from qimenllm.knowledge.business import install_business
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.rules.candidates import install_candidates


ROOT = Path(__file__).resolve().parents[1]


class BusinessCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db, self.raw = root / 'business.sqlite3', root / 'raw'
        restore_snapshot(ROOT / 'data/snapshots/current', self.db, self.raw)
        self.content = (ROOT / 'data/provenance/uploads' / (BUSINESS_SHA + '.utf8')).read_bytes()
        source = import_chapter(self.db, self.raw, self.content,
            book_key='shenqi-user-text-v1', book_title='神奇之门',
            chapter_key='business-finance', chapter_title='经营求财预测',
            sequence=12, origin='user-attached-TXT:经营求财预测_完整原文.txt; SHA256:' + BUSINESS_SHA)
        self.revision = source['revision_id']
        datadir = ROOT / 'data/structured/shenqi'
        self.curated = json.loads((datadir / 'business_curated.json').read_bytes())
        self.cases = json.loads((datadir / 'business_cases.json').read_bytes())
        self.candidates = json.loads((datadir / 'business_rule_candidates.json').read_bytes())
        install_business(self.db, self.revision, self.curated)
        import_cases(self.db, self.revision, self.cases)
        install_candidates(self.db, self.revision, self.candidates)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_original_and_all_source_tables(self):
        self.assertEqual(digest(self.content), BUSINESS_SHA)
        self.assertEqual(len(self.content), 56047)
        self.assertEqual(len(self.content.splitlines()), 1366)
        self.assertEqual(len(self.cases['cases']), 14)
        charts = [ch for c in self.cases['cases'] for ev in c['events'] for ch in ev['charts']]
        self.assertEqual(len(charts), 16)
        self.assertTrue(all(len(ch['payload']['source_table_rows']) == 9 for ch in charts))
        self.assertEqual(sum(len(c['events']) for c in self.cases['cases']), 18)

    def test_database_linkage_and_condition_status(self):
        s = QimenService(self.db)
        result = s.cases('business-finance')
        self.assertEqual(len(result['cases']), 14)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM charts').fetchone()[0], 45)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0], 43)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM rules').fetchone()[0], 0)
        self.assertEqual(len(self.candidates['candidates']), 10)
        self.assertTrue(audit(self.db, self.raw)['ok'])

    def test_narrative_families_and_missing_charts(self):
        c = self.cases['cases']
        self.assertEqual(c[1]['family']['family_key'], c[2]['family']['family_key'])
        self.assertEqual(c[2]['family']['family_key'], c[3]['family']['family_key'])
        self.assertEqual([len(e['charts']) for e in c[11]['events']], [1, 1, 1, 0, 0])
        self.assertFalse(any(r['knowledge_phase'] == 'pre_prediction'
                             for case in c for e in case['events'] for r in e['records']))

    def test_all_sixteen_original_charts_project_without_modifying_source(self):
        svc = QimenService(self.db)
        count = 0
        literal_centre_found = False
        for c in svc.cases('business-finance')['cases']:
            for event in c['events']:
                for chart_id in event['chart_ids']:
                    result = svc.case_chart(c['case_id'], chart_id)
                    self.assertEqual(result['status'], 'projected')
                    self.assertEqual(len(result['palaces']), 9)
                    self.assertFalse(result['engine_verified'])
                    self.assertEqual(result['chart_id'], chart_id)
                    if result['palaces']['5'].get('native_center_prefix_marker') == '禽':
                        literal_centre_found = True
                        self.assertEqual(result['palaces']['5']['earth_stem'], '己')
                        self.assertEqual(result['palaces']['5']['source_cell_as_written'], '禽己')
                    count += 1
        self.assertEqual(count, 16)
        self.assertTrue(literal_centre_found)

    def test_real_sql_reference_conditions_are_never_role_bindings(self):
        svc = QimenService(self.db)
        context = {'domain': 'business_finance', 'business_subtype': 'borrowing',
                   'method_scope': 'shenqi_business_borrowing_reference_v1'}
        result = svc.rule_candidates(context, domain='business_finance',
                                     method='shenqi_business_reference_v1')
        self.assertEqual(result['candidate_count'], 10)
        self.assertEqual(len([c for c in result['candidates']
                              if c['symbolic_status']=='applicable']), 1)
        self.assertFalse(result['role_bindings'])
        self.assertFalse(result['professional_analysis_completed'])
        self.assertTrue(all(c['activation_status']=='reference_only'
                            for c in result['candidates']))

    def test_idempotent_complete_reimport(self):
        curated = install_business(self.db, self.revision, self.curated)
        reimport = import_cases(self.db, self.revision, self.cases)
        candidates = install_candidates(self.db, self.revision, self.candidates)
        self.assertTrue(reimport['duplicate'])
        self.assertTrue(candidates['duplicate'])
        self.assertEqual(reimport['training_tasks_added'], 0)


if __name__ == '__main__':
    unittest.main()
