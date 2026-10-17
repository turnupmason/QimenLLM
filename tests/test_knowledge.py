import sqlite3
from qimenllm.knowledge.db import connect, initialize, digest
from qimenllm.knowledge.importer import ImportConflict, add_annotations
from qimenllm.knowledge.integrity import audit
from qimenllm.retrieval.repository import KnowledgeRepository
from support import DatabaseTest


class KnowledgeTests(DatabaseTest):
    def test_empty_schema_no_domain_data(self):
        report=audit(self.db,self.raw)
        self.assertTrue(report['ok'])
        self.assertTrue(all(count==0 for count in report['counts'].values()))

    def test_initialize_idempotent_and_checksum_guard(self):
        initialize(self.db)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],1)
            conn.execute("UPDATE schema_migrations SET sha256='corrupted'")
        with self.assertRaises(RuntimeError): initialize(self.db)

    def test_text_primary_key_cannot_be_null(self):
        with connect(self.db) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO event_families VALUES (NULL,'invalid')")

    def test_utf8_crlf_and_layout_preserved(self):
        content='工程样本\r\n  A│B  \n\n尾段'.encode()
        result=self.ingest(content)
        self.assertEqual((self.raw/(result['sha256']+'.utf8')).read_bytes(),content)
        self.assertEqual(result['sha256'],digest(content))
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT content FROM raw_documents').fetchone()[0],content)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_long_complete_input_is_not_truncated(self):
        content=('完整工程上下文，非古籍资料。\n'*10000).encode()
        self.ingest(content)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT content FROM raw_documents').fetchone()[0],content)
            self.assertEqual(conn.execute('SELECT body FROM chapter_search').fetchone()[0].encode(),content)

    def test_duplicate_no_extra_version_or_document(self):
        first=self.ingest(); second=self.ingest()
        self.assertTrue(second['duplicate'])
        self.assertEqual(first['revision_id'],second['revision_id'])
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM raw_documents').fetchone()[0],1)

    def test_explicit_confirmation_is_separate_from_content(self):
        first=self.ingest(confirmed=False)
        self.ingest(confirmed=True)
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT status FROM source_reviews ORDER BY rowid DESC LIMIT 1').fetchone()[0],'confirmed')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM chapter_revisions').fetchone()[0],1)

    def test_different_bytes_require_explicit_revision(self):
        self.ingest()
        with self.assertRaises(ImportConflict): self.ingest(b'Changed engineering fixture')
        second=self.ingest(b'Changed engineering fixture',revision=2)
        self.assertEqual(second['revision'],2)
        with self.assertRaises(ImportConflict): self.ingest(b'Another change',revision=4)

    def test_metadata_conflicts_are_not_silent(self):
        self.ingest()
        with self.assertRaises(ImportConflict): self.ingest(book_title='Changed title')
        with self.assertRaises(ImportConflict): self.ingest(chapter_title='Changed chapter')

    def test_raw_source_and_chart_revision_are_append_only(self):
        self.ingest()
        with connect(self.db) as conn:
            for table in ('raw_documents','chapter_revisions','source_spans','source_reviews','data_versions'):
                with self.assertRaises(sqlite3.IntegrityError): conn.execute(f'DELETE FROM {table}')
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE raw_documents SET content=X'61',byte_length=1")

    def test_annotations_trace_to_whole_context_and_are_idempotent(self):
        source=self.ingest()
        entry={'byte_start':0,'byte_end':19,'locator':'context block','category':'commentary',
               'payload':{'note':'Engineering annotation; not a domain fact'}}
        self.assertEqual(add_annotations(self.db,source['revision_id'],[entry])['added'],1)
        self.assertTrue(add_annotations(self.db,source['revision_id'],[entry])['duplicate'])
        with connect(self.db) as conn:
            item=conn.execute('SELECT * FROM knowledge_items').fetchone()
            self.assertEqual(item['compiled'],0)
            self.assertEqual(item['reference_only'],1)
            citation=KnowledgeRepository(self.db).source(item['source_id'])
            self.assertEqual(citation['excerpt'],'Engineering fixture')

    def test_invalid_source_or_annotation_rolls_back_batch(self):
        source=self.ingest('中工程'.encode())
        with self.assertRaises(UnicodeDecodeError):
            add_annotations(self.db,source['revision_id'],[{'byte_start':1,'byte_end':4,'category':'commentary','locator':'bad','payload':{}}])
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM knowledge_items').fetchone()[0],0)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('INSERT INTO source_spans VALUES (?,?,?,?,?)',('bad',source['revision_id'],0,9999,'bad'))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO concepts VALUES ('bad','x','x','missing','x')")

    def test_audit_detects_mirror_and_index_corruption(self):
        result=self.ingest()
        (self.raw/(result['sha256']+'.utf8')).write_bytes(b'corrupted')
        with connect(self.db) as conn: conn.execute("UPDATE chapter_search SET body='wrong'")
        report=audit(self.db,self.raw)
        self.assertFalse(report['ok'])
        self.assertEqual(len(report['errors']),2)

    def test_chinese_search_literal_and_sql_injection_safe(self):
        self.ingest('完整工程上下文。'.encode())
        repo=KnowledgeRepository(self.db)
        self.assertEqual(len(repo.search('工程')),1)
        self.assertEqual(repo.search("' OR 1=1 --"),[])
        self.assertEqual(repo.candidates("' OR 1=1 --")['rules'],[])

    def test_empty_or_invalid_input_rejected(self):
        for content in (b'',b'  \n',b'\xff'):
            with self.assertRaises((ValueError,UnicodeError)): self.ingest(content)
