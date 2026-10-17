"""Incremental UTF-8 imports. The supplied bytes, not normalized text, are authoritative."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from .db import connect, digest, now


class ImportConflict(ValueError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def new_version(conn, operation: str, manifest: object) -> str:
    parent = conn.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
    version = str(uuid4())
    conn.execute('INSERT INTO data_versions VALUES (?,?,?,?,?)',
                 (version, parent, operation, digest(canonical(manifest).encode()), now()))
    return version


def import_chapter(db: str | Path, raw_dir: str | Path, content: bytes, *,
                   book_key: str, book_title: str, chapter_key: str, chapter_title: str,
                   sequence: int, origin: str, author: str | None = None,
                   edition: str | None = None, revision: int | None = None,
                   confirmed: bool = False) -> dict:
    text = content.decode('utf-8')  # no BOM removal, whitespace cleanup, newline conversion
    if not text.strip() or not all((book_key.strip(), book_title.strip(), chapter_key.strip(), chapter_title.strip(), origin.strip())):
        raise ValueError('Nonempty text and source identity required')
    if sequence < 0 or (revision is not None and revision < 1):
        raise ValueError('Invalid sequence or revision')
    sha = digest(content)
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    mirror = raw_dir / f'{sha}.utf8'
    # Exclusive create protects against replacing an existing immutable mirror.
    try:
        with mirror.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if mirror.read_bytes() != content:
            raise ImportConflict('Raw mirror hash collision or corruption')
    with connect(db) as conn:
        conn.execute('BEGIN IMMEDIATE')
        book = conn.execute('SELECT * FROM books WHERE book_key=?', (book_key,)).fetchone()
        if book:
            if (book['title'], book['author'], book['edition']) != (book_title, author, edition):
                raise ImportConflict('Book metadata changed; use a separate edition key')
            book_id = book['book_id']
        else:
            book_id = str(uuid4())
            conn.execute('INSERT INTO books(book_id,book_key,title,author,edition) VALUES (?,?,?,?,?)',
                         (book_id, book_key, book_title, author, edition))
        chapter = conn.execute('SELECT * FROM chapters WHERE book_id=? AND chapter_key=?',
                               (book_id, chapter_key)).fetchone()
        if chapter:
            if (chapter['title'], chapter['sequence']) != (chapter_title, sequence):
                raise ImportConflict('Chapter metadata changed; explicit editorial migration required')
            chapter_id = chapter['chapter_id']
        else:
            chapter_id = str(uuid4())
            conn.execute('INSERT INTO chapters VALUES (?,?,?,?,?)',
                         (chapter_id, book_id, chapter_key, chapter_title, sequence))
        existing = conn.execute('''SELECT r.* FROM chapter_revisions r JOIN raw_documents d USING(document_id)
            WHERE r.chapter_id=? AND d.sha256=?''', (chapter_id, sha)).fetchone()
        if existing:
            if revision is not None and revision != existing['revision']:
                raise ImportConflict('Same bytes already imported at a different revision')
            result = dict(existing)
            result['source_id']=conn.execute('''SELECT source_id FROM source_spans WHERE revision_id=?
                AND byte_start=0 AND byte_end=? AND locator='full chapter' ''',
                (existing['revision_id'],len(content))).fetchone()[0]
            latest_review=conn.execute('SELECT status FROM source_reviews WHERE revision_id=? ORDER BY rowid DESC LIMIT 1',
                                      (existing['revision_id'],)).fetchone()
            if confirmed and (latest_review is None or latest_review[0]!='confirmed'):
                new_version(conn,'confirm_source',{'revision_id':existing['revision_id']})
                conn.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?,?)',
                    (str(uuid4()),existing['revision_id'],'confirmed','user','Explicit confirmation at repeated import',now()))
            result.update(duplicate=True, sha256=sha)
            return result
        latest = conn.execute('SELECT MAX(revision) FROM chapter_revisions WHERE chapter_id=?', (chapter_id,)).fetchone()[0]
        expected = (latest or 0) + 1
        if latest is not None and revision is None:
            raise ImportConflict('Chapter content differs; explicit next revision required')
        if revision is not None and revision != expected:
            raise ImportConflict(f'Expected revision {expected}')
        document_id = 'doc-' + sha
        conn.execute('INSERT OR IGNORE INTO raw_documents VALUES (?,?,?,?,?,?)',
                     (document_id, sha, content, len(content), 'text/plain; charset=utf-8', now()))
        version = new_version(conn, 'import_chapter', {'book':book_key,'chapter':chapter_key,'revision':expected,'sha256':sha})
        revision_id, source_id = str(uuid4()), str(uuid4())
        conn.execute('INSERT INTO chapter_revisions VALUES (?,?,?,?,?,?,?)',
                     (revision_id, chapter_id, expected, document_id, version, origin, now()))
        conn.execute('INSERT INTO source_spans VALUES (?,?,?,?,?)',
                     (source_id, revision_id, 0, len(content), 'full chapter'))
        conn.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?,?)',
                     (str(uuid4()), revision_id, 'confirmed' if confirmed else 'pending',
                      'user' if confirmed else 'importer', 'Explicit confirmation at import' if confirmed else 'Awaiting source acceptance', now()))
        conn.execute('INSERT INTO chapter_search(revision_id,body) VALUES (?,?)', (revision_id, text))
        return {'revision_id':revision_id, 'source_id':source_id, 'data_version':version,
                'revision':expected, 'sha256':sha, 'duplicate':False}


def add_annotations(db: str | Path, revision_id: str, annotations: list[dict]) -> dict:
    """Import reviewed context-complete annotations; never infer rules from individual sentences.

    Each entry: category, byte_start/end, locator, payload, optional method_id.
    Applicability/compilation stay false until separately implemented and audited.
    """
    if not annotations:
        raise ValueError('No annotations supplied')
    with connect(db) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('''SELECT d.content FROM chapter_revisions r JOIN raw_documents d USING(document_id)
            WHERE revision_id=?''', (revision_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown revision')
        raw = row[0]
        entries = []
        for entry in annotations:
            start, end = entry['byte_start'], entry['byte_end']
            if not (0 <= start < end <= len(raw)):
                raise ValueError('Source bounds invalid')
            raw[:start].decode('utf-8'); raw[start:end].decode('utf-8'); raw[end:].decode('utf-8')
            payload = canonical(entry['payload'])
            if not isinstance(entry['payload'], dict) or not entry['locator'].strip():
                raise ValueError('Payload object and locator required')
            item_id = 'item-' + digest(canonical([revision_id,entry]).encode())
            if conn.execute('SELECT 1 FROM knowledge_items WHERE item_id=?', (item_id,)).fetchone():
                continue
            entries.append((entry,start,end,payload,item_id))
        if not entries:
            return {'added':0, 'duplicate':True}
        version = new_version(conn, 'annotate', annotations)
        for entry,start,end,payload,item_id in entries:
            source_id = 'span-' + digest(canonical([revision_id,start,end,entry['locator']]).encode())
            conn.execute('INSERT OR IGNORE INTO source_spans VALUES (?,?,?,?,?)',
                         (source_id,revision_id,start,end,entry['locator']))
            conn.execute('''INSERT INTO knowledge_items(item_id,category,source_id,method_id,payload_json,structured,data_version)
                VALUES (?,?,?,?,?,1,?)''', (item_id,entry['category'],source_id,entry.get('method_id'),payload,version))
        return {'added':len(entries), 'duplicate':False, 'data_version':version}
