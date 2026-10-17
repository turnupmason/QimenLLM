"""Parameterized runtime SQL retrieval; semantic similarity never activates a rule."""
import json
from ..knowledge.db import connect, digest
from ..knowledge.source_confirmation import source_confirmation


class KnowledgeRepository:
    def __init__(self, db): self.db = db

    def candidates(self, domain: str | None) -> dict:
        query = '''SELECT r.*, k.source_id,k.structured,k.applicability_confirmed,k.compiled,
            k.reference_only,k.disputed,
            (SELECT status FROM source_reviews sr WHERE sr.revision_id=s.revision_id
             ORDER BY sr.rowid DESC LIMIT 1) AS source_status
            FROM rules r JOIN knowledge_items k USING(item_id)
            JOIN source_spans s USING(source_id)
            WHERE r.domain=? ORDER BY r.rule_id'''
        with connect(self.db) as conn:
            rules = []
            for row in conn.execute(query, (domain,)):
                item = dict(row)
                item['binding'] = json.loads(item.pop('binding_json'))
                item['conditions'] = [dict(c) for c in conn.execute(
                    'SELECT * FROM rule_conditions WHERE rule_id=? ORDER BY condition_id', (item['rule_id'],))]
                item['conflicts'] = [tuple(r) for r in conn.execute('''SELECT rule_a,rule_b FROM rule_disagreements
                    WHERE resolved=0 AND (rule_a=? OR rule_b=?)''', (item['rule_id'],item['rule_id']))]
                rules.append(item)
        return {'query':query, 'parameters':{'domain':domain}, 'rules':rules}

    def source(self, source_id: str) -> dict:
        with connect(self.db) as conn:
            row = conn.execute('''SELECT s.*,d.content,b.title AS book,c.title AS chapter,
                r.revision,d.sha256,
                (SELECT status FROM source_reviews sr WHERE sr.revision_id=r.revision_id
                 ORDER BY sr.rowid DESC LIMIT 1) AS source_acceptance
                FROM source_spans s JOIN chapter_revisions r USING(revision_id)
                JOIN raw_documents d USING(document_id) JOIN chapters c USING(chapter_id)
                JOIN books b USING(book_id) WHERE s.source_id=?''', (source_id,)).fetchone()
            if row is None: raise KeyError(source_id)
            result = dict(row)
            raw = result.pop('content')
            if digest(raw)!=result['sha256']: raise ValueError('Source bytes do not match their recorded hash')
            result['excerpt'] = raw[result['byte_start']:result['byte_end']].decode('utf-8')
            result['source_confirmation'] = source_confirmation(conn,result['revision_id'])
            return result

    def search(self, term: str, limit: int = 20) -> list[dict]:
        # Bound literal substring search handles Chinese without tokenization assumptions.
        # FTS5 is maintained for later token-aware ranking; neither path is an applicability test.
        if not term.strip(): return []
        limit = min(max(limit,1),100)
        with connect(self.db) as conn:
            return [dict(r) for r in conn.execute('''SELECT revision_id,body FROM chapter_search
                WHERE instr(body,?)>0 ORDER BY revision_id LIMIT ?''', (term,limit))]

    def compiled_datasets(self, method_id: str = 'shenqi_ch1_foundation_v1') -> list[dict]:
        with connect(self.db) as conn:
            rows=conn.execute('''SELECT k.item_id,k.source_id,k.payload_json,
                (SELECT status FROM source_reviews sr WHERE sr.revision_id=s.revision_id
                 ORDER BY sr.rowid DESC LIMIT 1) AS source_acceptance
                FROM knowledge_items k JOIN source_spans s USING(source_id)
                WHERE k.method_id=? AND k.compiled=1 AND k.structured=1 AND k.disputed=0
                AND k.reference_only=0 ORDER BY k.item_id''',(method_id,)).fetchall()
            return [{**dict(row),'payload':json.loads(row['payload_json'])} for row in rows
                    if row['source_acceptance']!='disputed']

    def context_groups(self, term: str, limit: int = 30) -> list[dict]:
        if not term.strip(): return []
        with connect(self.db) as conn:
            rows=conn.execute('''SELECT k.item_id,k.source_id,k.payload_json,k.compiled,k.disputed
                FROM knowledge_items k WHERE json_extract(k.payload_json,'$.kind')='context_group'
                AND instr(k.payload_json,?)>0 ORDER BY k.rowid LIMIT ?''',(term,min(max(limit,1),100))).fetchall()
            return [{**dict(row),'payload':json.loads(row['payload_json'])} for row in rows]

    def reference_dataset(self, family: str) -> list[dict]:
        """Retrieve whole curated context, including reference-only and disputed material.

        This is a learning query, never an applicability decision or role binding.
        """
        with connect(self.db) as conn:
            rows=conn.execute('''SELECT k.item_id,k.source_id,k.payload_json,k.data_version
                FROM knowledge_items k WHERE json_extract(k.payload_json,'$.kind')='context_group'
                AND json_extract(k.payload_json,'$.dataset.key')=? ORDER BY k.rowid''',(family,)).fetchall()
            return [{**dict(row),'payload':json.loads(row['payload_json'])} for row in rows]

    def coverage(self) -> dict:
        with connect(self.db) as conn:
            return {table:conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    for table in ('books','chapters','knowledge_items','cases','rules')}
