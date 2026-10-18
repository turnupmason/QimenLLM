#!/usr/bin/env python3
"""Ingest the byte-confirmed Shenqi learning chapter with existing append-only APIs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter, add_annotations
from qimenllm.knowledge.snapshot import restore_snapshot

LEARNING_SHA = '10db674c708186c6408c9d38228b066456ed71adb6e5939e2e1102e2a2df15ef'

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structured/shenqi'
UPLOAD = ROOT / 'data/provenance/uploads' / (LEARNING_SHA + '.utf8')


def ingest(db, raw_dir):
    raw = UPLOAD.read_bytes()
    if digest(raw) != LEARNING_SHA or len(raw) != 11761 or len(raw.splitlines()) != 51:
        raise ValueError('Source bytes differ from uploaded TXT')
    curated = json.loads((DATA / 'learning_curated.json').read_bytes())
    if curated['source_sha256'] != LEARNING_SHA:
        raise ValueError('Curation fingerprint differs from source')
    relation = curated['source_relationship']
    previous = relation['existing_source_selector']
    old = (ROOT / 'data/provenance/uploads' / (previous['source_sha256'] + '.utf8')).read_bytes()
    if digest(old) != previous['source_sha256'] or old[previous['byte_start']:previous['byte_end']].decode() != previous['source_quote']:
        raise ValueError('Linked previous source changed')
    old_lines = old.decode().splitlines(keepends=True)
    comparison = ''.join(old_lines[n-1] for n in range(previous['line_start'], previous['line_end']+1)
                         if n not in relation['comparison']['excluded_old_source_lines'])
    if re.sub(r'\s+', '', comparison) != re.sub(r'\s+', '', raw.decode()):
        raise ValueError('Source relationship no longer matches')
    source = import_chapter(
        db, raw_dir, raw, book_key='shenqi-user-text-v1',
        book_title='神奇之门', chapter_key='appendix-learning-clean',
        chapter_title='一、学习奇门遁甲并不难（精校独立来源）', sequence=26,
        origin='user-attached-TXT:神奇之门_附录一_学习奇门遁甲并不难_精校完整版.txt; SHA256:' + LEARNING_SHA)
    curation = add_annotations(db, source['revision_id'], curated['annotations'])
    return {'source': source, 'curation': curation,
            'historical_cases_added': 0, 'charts_added': 0,
            'empirical_evaluation_runs_added': 0, 'project_empirical_accuracy': None,
            'no_formal_roles': True, 'no_training_tasks': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'data/raw_books')
    parser.add_argument('--restore-base', action='store_true',
                        help='Restore existing committed snapshot into a new database first')
    parser.add_argument('--local-only', action='store_true',
                        help='Skip auto-sync in staging CI; final delivery must push and verify')
    args = parser.parse_args()
    if args.restore_base:
        restore_snapshot(ROOT / 'data/snapshots/current', args.db, args.raw_dir)
    result = ingest(args.db, args.raw_dir)
    code = 0
    if args.local_only:
        result['github_sync'] = {'status': 'pending',
                                 'reason': 'Staged maintenance; remote acceptance outstanding'}
    else:
        try:
            result['github_sync'] = sync_github(
                ROOT, args.db, args.raw_dir,
                'Preserve alternate learning source and link existing appendix without duplicating knowledge')
        except (SyncError, ValueError) as exc:
            result['github_sync'] = {'status': 'pending', 'reason': str(exc)}
            code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
