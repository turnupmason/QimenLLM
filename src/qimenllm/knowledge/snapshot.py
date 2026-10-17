"""Deterministic, restorable text snapshots for the authorized private Git repository."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .db import connect, digest, initialize
from .importer import canonical
from .integrity import audit


# Foreign-key insertion order. Search is a derived index, not authoritative data.
TABLES = (
    'data_versions','books','chapters','raw_documents','chapter_revisions','source_reviews',
    'source_spans','methods','concepts','concept_links','knowledge_items','rules',
    'rule_conditions','rule_disagreements','event_families','cases','events','case_events',
    'charts','case_records','evidence_links','dataset_releases','split_assignments',
    'training_tasks','task_inputs',
)


def _rows(conn, table: str) -> list[dict]:
    columns=[r['name'] for r in conn.execute(f'PRAGMA table_info({table})') if r['pk']]
    order='rowid' if table in ('data_versions','source_reviews') else ','.join('"'+c+'"' for c in columns)
    return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}" ORDER BY {order}')]


def export_snapshot(db: str | Path, raw_dir: str | Path, destination: str | Path) -> dict:
    """Include every authoritative table and actual raw bytes, not just a count manifest."""
    report=audit(db,raw_dir)
    if not report['ok']: raise ValueError('Source integrity audit failed; export refused')
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    files={}
    counts={}
    with connect(db) as conn:
        conn.execute('BEGIN')  # one consistent database view for all tables
        schema=dict(conn.execute('SELECT version,sha256 FROM schema_migrations').fetchone())
        for table in TABLES:
            rows=_rows(conn,table)
            counts[table]=len(rows)
            if table=='raw_documents':
                for row in rows:
                    content=row.pop('content')
                    if digest(content)!=row['sha256']: raise ValueError('Raw hash mismatch')
                    relative='raw/'+row['sha256']+'.bin'
                    files[relative]=content
                    row['content_file']=relative
            files[table+'.jsonl']=''.join(canonical(row)+'\n' for row in rows).encode()
        version=conn.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
    hashes={path:digest(content) for path,content in sorted(files.items())}
    manifest={'format_version':1,'schema':schema,'data_version':version,
              'tables':list(TABLES),'counts':counts,'files':hashes}
    # No timestamp or machine-specific path: unchanged data produces unchanged Git files.
    for relative,content in files.items():
        target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists() or target.read_bytes()!=content:
            temporary=target.with_suffix(target.suffix+'.tmp')
            temporary.write_bytes(content)
            temporary.replace(target)
    (destination/'manifest.json').write_text(canonical(manifest)+'\n')
    return {'data_version':version,'snapshot':str(destination),'counts':counts,
            'manifest_sha256':digest(canonical(manifest).encode())}


def restore_snapshot(snapshot: str | Path, destination: str | Path, raw_dir: str | Path) -> dict:
    """Restore into a NEW database; never replace existing user data."""
    snapshot=Path(snapshot)
    destination=Path(destination)
    if destination.exists(): raise FileExistsError('Restore destination must be new')
    manifest=json.loads((snapshot/'manifest.json').read_bytes())
    if manifest['format_version']!=1 or manifest['tables']!=list(TABLES):
        raise ValueError('Unsupported snapshot schema')
    contents={}
    for relative,sha in manifest['files'].items():
        path=snapshot/relative
        if not path.resolve().is_relative_to(snapshot.resolve()): raise ValueError('Invalid snapshot path')
        content=path.read_bytes()
        if digest(content)!=sha: raise ValueError('Snapshot file hash mismatch: '+relative)
        contents[relative]=content
    destination.parent.mkdir(parents=True,exist_ok=True)
    raw_dir=Path(raw_dir)
    raw_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='qimen-restore-',dir=destination.parent) as directory:
        staging=Path(directory)/'restore.sqlite3'
        initialize(staging,seed_empty=False)
        releases=[]
        with connect(staging) as conn:
            conn.execute('PRAGMA defer_foreign_keys=ON')
            schema=dict(conn.execute('SELECT version,sha256 FROM schema_migrations').fetchone())
            if schema!=manifest['schema']: raise ValueError('Migration fingerprint mismatch')
            for table in TABLES:
                rows=[json.loads(line) for line in contents[table+'.jsonl'].splitlines()]
                if len(rows)!=manifest['counts'][table]: raise ValueError('Table count mismatch')
                for row in rows:
                    if table=='raw_documents':
                        row['content']=contents[row.pop('content_file')]
                        if digest(row['content'])!=row['sha256']: raise ValueError('Raw content hash mismatch')
                        mirror=raw_dir/(row['sha256']+'.utf8')
                        try:
                            with mirror.open('xb') as stream: stream.write(row['content'])
                        except FileExistsError:
                            if mirror.read_bytes()!=row['content']: raise ValueError('Existing raw mirror differs')
                    if table=='dataset_releases' and row['frozen']:
                        releases.append(row['release_id']); row['frozen']=0
                    actual_columns={r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
                    if set(row)!=actual_columns: raise ValueError('Unexpected snapshot columns')
                    columns=','.join('"'+key+'"' for key in row)
                    placeholders=','.join('?' for _ in row)
                    conn.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})',tuple(row.values()))
            for release in releases:
                conn.execute('UPDATE dataset_releases SET frozen=1 WHERE release_id=?',(release,))
            for row in conn.execute('''SELECT r.revision_id,d.content FROM chapter_revisions r
                JOIN raw_documents d USING(document_id)'''):
                conn.execute('INSERT INTO chapter_search(revision_id,body) VALUES (?,?)',
                             (row['revision_id'],row['content'].decode('utf-8')))
        report=audit(staging,raw_dir)
        if not report['ok']: raise ValueError('Restored database integrity check failed')
        # Same-filesystem exclusive hard link publishes only the fully verified DB.
        os.link(staging,destination)
    return report
