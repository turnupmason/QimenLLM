"""The author's afterword is source knowledge, not extra cases or proven capability."""
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
from qimenllm.knowledge.afterword import AFTERWORD_SHA, install_afterword
from qimenllm.knowledge.db import APPEND_ONLY, connect, digest
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_shenqi_afterword as importer


class AfterwordKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.path = Path(cls.tmp.name)
        cls.db, cls.raw = cls.path / 'afterword.sqlite3', cls.path / 'raw'
        restore_snapshot(ROOT / 'data/snapshots/current', cls.db, cls.raw)
        with connect(cls.db) as c:
            cls.before = {t: [tuple(r) for r in c.execute('SELECT * FROM ' + t)]
                          for t in APPEND_ONLY + ('books', 'chapters', 'dataset_releases')}
        cls.chart_args = {'dun': '阳遁', 'bureau': 2, 'hour_ganzhi': '辛卯', 'method': 'shenqi_ch2_paper_v1'}
        cls.before_chart = QimenService(cls.db).calculate('symbolic_chart', cls.chart_args)
        cls.result = importer.ingest(cls.db, cls.raw)
        cls.curated = json.loads((ROOT / 'data/structured/shenqi/afterword_curated.json').read_bytes())
        cls.source = importer.UPLOAD.read_bytes()
        cls.groups = {g['key']: g for g in cls.curated['groups']}
        cls.svc = QimenService(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def assessment(self, key):
        return self.groups['afterword_' + key]['assessment']

    def test_source_bytes_all_quotes_and_line_coverage(self):
        self.assertEqual((digest(self.source), len(self.source), len(self.source.splitlines())),
                         (AFTERWORD_SHA, 5285, 21))
        def walk(v):
            if isinstance(v, dict):
                if 'source_sha256' in v:
                    self.assertEqual(v['source_sha256'], AFTERWORD_SHA)
                if {'byte_start', 'byte_end'} <= v.keys():
                    self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),
                                     v.get('source_quote', v.get('text')))
                for child in v.values(): walk(child)
            elif isinstance(v, list):
                for child in v: walk(child)
        walk(self.curated)
        covered = []; lines = self.source.decode().splitlines(keepends=True)
        for g in self.groups.values():
            covered.extend(range(g['line_start'], g['line_end'] + 1))
            for row in g['dataset']['rows']:
                a, b = row['source_lines']
                self.assertEqual(row['source_quote'], ''.join(lines[a-1:b]))
                self.assertEqual(row['applicability_status'], 'reference_only')
        self.assertEqual(covered, list(range(1, 22)))

    def test_previous_book_date_not_current_book_or_signature_date(self):
        a = self.assessment('earlier_book')
        self.assertEqual((a['publication_time_as_written'], a['publisher_as_written'], a['book_title_as_written']),
                         ('1993年6月', '作家出版社', '未知之门'))
        self.assertEqual(a['date_role'], 'earlier_book_publication_not_current_book_or_afterword_date')
        self.assertFalse(a['new_book_imported'])
        a = self.assessment('signature')
        self.assertEqual((a['name_as_written'], a['location_as_written']), ('张志春', '石家庄'))
        self.assertIsNone(a['date_as_written'])
        self.assertFalse(a['current_book_edition_or_publication_date_inferred'])
        self.assertFalse(a['entire_book_completeness_asserted'])

    def test_research_programme_and_explicit_immaturity_remain_together(self):
        g = self.groups['afterword_research_limits']
        self.assertEqual((g['line_start'], g['line_end']), (15, 16))
        text = g['dataset']['rows'][0]['source_quote']
        for phrase in ('思维科学', '技术特征', '极其初步的', '幼稚的', '不成熟的', '批评指正'):
            self.assertIn(phrase, text)
        a = g['assessment']; self.assertTrue(a['programme_and_limit_kept_together'])
        self.assertIsNone(a['project_empirical_accuracy'])
        self.assertFalse(a['professional_analysis_completed'])
        self.assertFalse(a['training_authorized_by_author_invitation'])
        self.assertEqual(a['related_purpose_group_key'], 'afterword_purpose')
        self.assertFalse(self.assessment('purpose')['automatic_mastery_guarantee'])

    def test_three_demystification_reasons_are_attributed_not_casting_rules(self):
        g = self.groups['afterword_demystification']; text = g['dataset']['rows'][0]['source_quote']
        for phrase in ('一是封建统治者', '二是操其术者', '三是中国人本来没有宗教'):
            self.assertIn(phrase, text)
        a = g['assessment']
        self.assertFalse(a['historical_or_religious_claims_independently_verified_by_project'])
        self.assertFalse(a['deterministic_casting_or_role_rule'])

    def test_science_and_technology_argument_retains_secondary_citation_chain(self):
        g = self.groups['afterword_science_technology']
        self.assertEqual((g['line_start'], g['line_end']), (9, 14))
        a = g['assessment']; self.assertEqual([p['source_selector']['line_start'] for p in a['source_positions']], [9, 11, 13])
        c = a['secondary_citation']
        self.assertEqual((c['quoted_person_as_written'], c['publication_as_written'], c['date_as_written'], c['article_title_as_written']),
                         ('吴大猷', '光明日报', '1998年3月20日', '如何面对“李约瑟难题”'))
        self.assertIn('转引自', c['source_selector']['source_quote'])
        self.assertFalse(c['independently_checked'])
        self.assertFalse(a['new_external_sources_imported'])
        text = ''.join(r['source_quote'] for r in g['dataset']['rows'])
        for phrase in ('自然哲学', '社会制度问题', '技术与科学不能混为一谈', '理论与实际脱离', '我不赞成'):
            self.assertIn(phrase, text)

    def test_acknowledgements_not_inferred_case_contributors_or_current_titles(self):
        a = self.assessment('acknowledgements')
        self.assertEqual(a['names_as_written'], ['王修义','张岩客','杜新会','王建国','王瑞民','刘成云','张顺良','张粤','高海东','王庆丰'])
        self.assertFalse(a['specific_case_contributor_mapping_supplied'])
        self.assertFalse(a['inferred_links_to_existing_case_people'])
        self.assertFalse(a['new_cases_or_person_identities_created'])
        a = self.assessment('prefaces')
        self.assertEqual(a['named_people_as_written'], ['唐明邦', '叶梓铨'])
        self.assertFalse(a['current_titles_independently_verified'])
        self.assertFalse(a['endorsement_of_project_or_models'])
        self.assertFalse(a['new_preface_texts_imported'])

    def test_literal_wording_and_undated_signature_not_corrected(self):
        text = self.source.decode()
        self.assertIn('该书则是我对易学预测原理', text)
        self.assertIn('特别是我会的王修义师傅', text)
        self.assertTrue(text.endswith('张志春于石家庄\n'))
        self.assertIsNone(self.curated['printed_chapter_number'])

    def test_no_new_cases_books_charts_rules_or_training(self):
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
        self.assertEqual(self.svc.cases('afterword')['cases'], [])

    def test_learning_returns_full_caution_and_confirmed_reference_provenance(self):
        r = self.svc.learning.learn('极其初步的')
        self.assertEqual(r['status'], 'sources_found')
        block = next(b for b in r['knowledge_blocks'] if b['payload'].get('key') == 'afterword_research_limits')
        self.assertEqual(block['payload']['assessment'], self.assessment('research_limits'))
        self.assertIsNone(r['model_analysis'])
        ref = self.svc.reference('afterword_research_limits_reference', {})
        self.assertEqual((ref['status'], ref['total']), ('sources_found', 1))
        self.assertFalse(ref['professional_analysis_completed']); self.assertEqual(ref['role_bindings'], [])
        for s in ref['sources'].values():
            self.assertEqual(s['sha256'], AFTERWORD_SHA)
            self.assertEqual(s['source_acceptance'], 'confirmed')
        with connect(self.db) as c:
            rows = c.execute('SELECT compiled,reference_only,applicability_confirmed FROM knowledge_items JOIN source_spans USING(source_id) WHERE revision_id=?', (self.result['source']['revision_id'],)).fetchall()
            self.assertEqual(len(rows), 16)
            self.assertTrue(all(tuple(r) == (0, 1, 0) for r in rows))

    def test_existing_cli_and_wsgi_retrieve_whole_arguments(self):
        app = create_app(self.svc)
        def call(path, payload):
            body = json.dumps(payload).encode(); status = []
            out = b''.join(app({'PATH_INFO': path, 'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(body)),
                'wsgi.input': io.BytesIO(body)}, lambda s, h: status.append(s)))
            self.assertEqual(status, ['200 OK']); return json.loads(out)
        r = call('/v1/reference', {'family': 'afterword_science_technology_reference', 'filters': {}})
        self.assertEqual(r['total'], 3)
        self.assertIn('转引自《光明日报》', json.dumps(r, ensure_ascii=False))
        r = call('/v1/learn', {'term': '极其初步的'})
        self.assertTrue(any(b['payload'].get('key') == 'afterword_research_limits' for b in r['knowledge_blocks']))
        r = subprocess.run([sys.executable, '-m', 'qimenllm', '--db', str(self.db),
                            'reference', 'afterword_research_limits_reference', '--filters', '{}'],
                           cwd=ROOT, capture_output=True, text=True, check=True)
        result = json.loads(r.stdout); self.assertEqual(result['total'], 1)
        self.assertIn('不成熟的', result['entries'][0]['record']['source_quote'])
        self.assertFalse(result['professional_analysis_completed'])

    def test_existing_calculation_and_empirical_metrics_remain_unchanged(self):
        self.assertEqual(self.before_chart['status'], 'computed')
        self.assertEqual(self.svc.calculate('symbolic_chart', self.chart_args), self.before_chart)
        metrics = summarize([{'status': 'blocked', 'professional_analysis_completed': False}])
        self.assertEqual(metrics['professional_completions'], 0)
        self.assertIsNone(metrics['professional_correctness'])
        self.assertIsNone(metrics['real_world_predictive_accuracy'])

    def test_all_old_rows_retained_and_replay_idempotent(self):
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

    def test_source_change_and_wrong_fingerprint_rejected_and_snapshot_roundtrip(self):
        bad = self.path / 'bad.txt'; bad.write_bytes(self.source + b'changed')
        with patch.object(importer, 'UPLOAD', bad), self.assertRaises(ValueError):
            importer.ingest(self.db, self.raw)
        curated = copy.deepcopy(self.curated); curated['source_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            install_afterword(self.db, self.result['source']['revision_id'], curated)
        first, again = self.path / 'snapshot', self.path / 'again'
        db, raw = self.path / 'roundtrip.sqlite3', self.path / 'roundtrip-raw'
        export_snapshot(self.db, self.raw, first); restore_snapshot(first, db, raw)
        export_snapshot(db, raw, again)
        self.assertEqual({str(p.relative_to(first)): p.read_bytes() for p in first.rglob('*') if p.is_file()},
                         {str(p.relative_to(again)): p.read_bytes() for p in again.rglob('*') if p.is_file()})
        self.assertEqual((first / 'raw' / (AFTERWORD_SHA + '.bin')).read_bytes(), self.source)
