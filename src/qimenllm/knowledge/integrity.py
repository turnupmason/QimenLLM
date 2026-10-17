"""Detect source, index and relational corruption without altering accepted originals."""
from pathlib import Path
from .db import connect, digest


def audit(db: str | Path, raw_dir: str | Path) -> dict:
    errors = []
    with connect(db) as conn:
        for row in conn.execute('PRAGMA integrity_check'):
            if row[0] != 'ok': errors.append(f'sqlite:{row[0]}')
        errors.extend(f'foreign_key:{tuple(row)}' for row in conn.execute('PRAGMA foreign_key_check'))
        for row in conn.execute('SELECT * FROM raw_documents'):
            if digest(row['content']) != row['sha256'] or len(row['content']) != row['byte_length']:
                errors.append(f"raw_hash:{row['document_id']}")
            path = Path(raw_dir) / f"{row['sha256']}.utf8"
            if not path.exists() or path.read_bytes() != row['content']:
                errors.append(f"mirror:{row['document_id']}")
        for row in conn.execute('''SELECT r.revision_id,d.content FROM chapter_revisions r JOIN raw_documents d USING(document_id)'''):
            indexed = conn.execute('SELECT body FROM chapter_search WHERE revision_id=?', (row['revision_id'],)).fetchall()
            if len(indexed) != 1 or indexed[0][0] != row['content'].decode('utf-8'):
                errors.append(f"index:{row['revision_id']}")
        for row in conn.execute('''SELECT s.*,d.content FROM source_spans s JOIN chapter_revisions r USING(revision_id)
            JOIN raw_documents d USING(document_id)'''):
            try:
                raw = row['content']
                if row['byte_end'] > len(raw): raise ValueError('bounds')
                raw[:row['byte_start']].decode('utf-8')
                raw[row['byte_start']:row['byte_end']].decode('utf-8')
                raw[row['byte_end']:].decode('utf-8')
            except (ValueError, UnicodeError): errors.append(f"span:{row['source_id']}")
        for row in conn.execute('SELECT chart_id,chart_json,content_sha256 FROM charts'):
            if digest(row['chart_json'].encode()) != row['content_sha256']:
                errors.append(f"chart_hash:{row['chart_id']}")
        counts = {table:conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                  for table in ('books','chapters','raw_documents','knowledge_items','rules','cases','events','charts','training_tasks')}
        version = conn.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
    return {'ok':not errors, 'errors':errors, 'counts':counts, 'data_version':version}
