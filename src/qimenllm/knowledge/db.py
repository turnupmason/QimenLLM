"""SQLite lifecycle; append-only source tables and checksum-pinned migrations."""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


APPEND_ONLY = (
    'raw_documents', 'chapter_revisions', 'source_spans', 'source_reviews',
    'data_versions', 'methods', 'concepts', 'concept_links', 'knowledge_items',
    'rules', 'rule_conditions', 'charts', 'case_records', 'evidence_links',
    'training_tasks', 'task_inputs',
    'cases', 'events', 'event_families', 'case_events', 'rule_disagreements',
)


def initialize(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sql = (Path(__file__).parent / 'migrations/001_initial.sql').read_text()
    # Include generated triggers in the migration fingerprint.
    for table in APPEND_ONLY:
        for action in ('UPDATE', 'DELETE'):
            sql += (f'\nCREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON {table}'
                    f" BEGIN SELECT RAISE(ABORT,'append-only {table}'); END;\n")
    fingerprint = digest(sql.encode())
    with connect(path) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)')
        rows = conn.execute('SELECT * FROM schema_migrations ORDER BY version').fetchall()
        if rows:
            if len(rows) != 1 or rows[0]['version'] != 1 or rows[0]['sha256'] != fingerprint:
                raise RuntimeError('Migration history mismatch; explicit migration required')
            return
        # executescript commits any open transaction; explicitly begin here for atomic DDL.
        stamp = now()
        try:
            conn.executescript('BEGIN IMMEDIATE;\n' + sql)
            conn.execute('INSERT INTO schema_migrations VALUES (1,?,?)', (fingerprint, stamp))
            conn.execute('INSERT INTO data_versions VALUES (?,?,?,?,?)',
                         ('empty-v1', None, 'initialize_empty', digest(b''), stamp))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
