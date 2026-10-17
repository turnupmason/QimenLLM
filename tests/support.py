"""Neutral engineering fixtures only. These are not Qimen rules or historical cases."""
import tempfile
import unittest
import json
import re
from pathlib import Path
from qimenllm.knowledge.db import initialize, connect
from qimenllm.knowledge.importer import import_chapter


# Audited case-inspection metadata only. Unknown keys and malformed identities
# must remain searchable, including inside unexpected payload/background fields.
_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
_HEX = r'[0-9a-f]{64}'
_OPAQUE_CASE_FIELDS = {
    'case_id': rf'case-{_HEX}',
    'event_id': rf'event-{_HEX}',
    'family_id': rf'family-{_HEX}',
    'record_id': rf'record-{_HEX}',
    'chart_id': rf'chart-{_HEX}',
    'source_id': rf'(?:span-{_HEX}|{_UUID})',
    'revision_id': _UUID,
    'data_version': _UUID,
    'source_sha256': _HEX,
    'content_sha256': _HEX,
    'sha256': _HEX,
}


def case_content_text(value):
    """Serialize all case content without mistaking opaque IDs for evidence.

    Keep every dictionary key and all non-opaque values, including numeric
    leaves, source text/locators and unexpected nested content. This is a test
    assertion projection, not a runtime filter or a semantic leak detector.
    Structure, chronology and identity assertions remain separate.
    """
    def project(item):
        if isinstance(item, dict):
            return {key: ('<opaque identity>' if isinstance(child, str)
                    and key in _OPAQUE_CASE_FIELDS
                    and re.fullmatch(_OPAQUE_CASE_FIELDS[key], child)
                    else project(child)) for key, child in item.items()}
        if isinstance(item, list):
            return [project(child) for child in item]
        return item
    return json.dumps(project(value), ensure_ascii=False)


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=self.root/'test.sqlite3'
        self.raw=self.root/'raw'
        initialize(self.db)

    def ingest(self, content=b'Engineering fixture.\r\nContext retained.\n', **kwargs):
        defaults=dict(book_key='fixture',book_title='Engineering fixture',chapter_key='one',
                      chapter_title='Context fixture',sequence=0,origin='unit-test',confirmed=True)
        defaults.update(kwargs)
        return import_chapter(self.db,self.raw,content,**defaults)

    def seed_rule(self, *, suffix='', method='method-a', expected='peer', field='relationship',
                  operator='eq', kind='require', reference_only=0, disputed=0):
        import json
        source=self.ingest()
        rule='fixture-rule'+suffix
        with connect(self.db) as conn:
            conn.execute('INSERT OR IGNORE INTO methods VALUES (?,?,?,?,?)',
                         (method,method,'fixture-v1',source['source_id'],'{}'))
            conn.execute('''INSERT INTO knowledge_items(item_id,category,source_id,method_id,payload_json,
                structured,applicability_confirmed,compiled,reference_only,disputed,data_version)
                VALUES (?,'role',?,?,'{}',1,1,1,?,?,?)''',
                         ('item'+suffix,source['source_id'],method,reference_only,disputed,source['data_version']))
            conn.execute('INSERT INTO rules VALUES (?,?,?,?,?,?,?)',
                         (rule,'item'+suffix,method,'engineering',None,'{"fixture_role":"fixture_symbol"}',1))
            conn.execute('INSERT INTO rule_conditions VALUES (?,?,?,?,?,?,?)',
                         ('condition'+suffix,rule,field,operator,json.dumps(expected),kind,source['source_id']))
        return source,rule

    def seed_event(self):
        source=self.ingest()
        with connect(self.db) as conn:
            conn.execute("INSERT INTO event_families VALUES ('family','One synthetic engineering event')")
            conn.execute("INSERT INTO event_families VALUES ('family-other','Another synthetic engineering event')")
            conn.execute("INSERT INTO cases VALUES ('case',?,'Engineering story','complete',?)",
                         (source['source_id'],source['data_version']))
            for event,family in (('event','family'),('event-other','family-other')):
                conn.execute("INSERT INTO events VALUES (?,?,'{}','verified')",(event,family))
            conn.execute("INSERT INTO case_events VALUES ('case','event',0)")
            conn.execute("INSERT INTO case_events VALUES ('case','event-other',1)")
        return source
