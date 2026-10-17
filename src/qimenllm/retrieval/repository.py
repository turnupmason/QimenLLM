"""Parameterized runtime SQL retrieval; semantic similarity never activates a rule."""
import json
from ..knowledge.db import connect


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
                r.revision,d.sha256 FROM source_spans s JOIN chapter_revisions r USING(revision_id)
                JOIN raw_documents d USING(document_id) JOIN chapters c USING(chapter_id)
                JOIN books b USING(book_id) WHERE s.source_id=?''', (source_id,)).fetchone()
            if row is None: raise KeyError(source_id)
            result = dict(row)
            raw = result.pop('content')
            result['excerpt'] = raw[result['byte_start']:result['byte_end']].decode('utf-8')
            return result

    def search(self, term: str, limit: int = 20) -> list[dict]:
        # Bound literal substring search handles Chinese without tokenization assumptions.
        # FTS5 is maintained for later token-aware ranking; neither path is an applicability test.
        if not term.strip(): return []
        limit = min(max(limit,1),100)
        with connect(self.db) as conn:
            return [dict(r) for r in conn.execute('''SELECT revision_id,body FROM chapter_search
                WHERE instr(body,?)>0 ORDER BY revision_id LIMIT ?''', (term,limit))]
