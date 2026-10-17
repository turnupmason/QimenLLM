#!/usr/bin/env python3
"""Replay only the user-supplied first chapter; no OCR, external sources or inferred metadata."""
import argparse
import json
from pathlib import Path

from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = 'b70a7ab71b428a39f262d3df2ff41058af9273bb561419371d5e1b979e095718'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?',
                        default=ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHA}.bin')
    parser.add_argument('--db', type=Path, default=ROOT/'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir', type=Path, default=ROOT/'data/raw_books')
    parser.add_argument('--local-only', action='store_true',
                        help='Trusted staged maintenance only; GitHub synchronization remains outstanding')
    args = parser.parse_args()
    raw = args.source.read_bytes()
    if digest(raw) != SOURCE_SHA:
        parser.error('Source differs from the preserved upload; use an explicit new revision workflow')
    curated = json.loads((ROOT/'data/structured/shenqi/chapter01_curated.json').read_bytes())
    result = {'source': import_chapter(
        args.db, args.raw_dir, raw, book_key='shenqi-user-text-v1', book_title='神奇之门',
        chapter_key='chapter-01', chapter_title='时家奇门演局的规律', sequence=1,
        origin='user-upload:file_000000002c9081f6bfe1eb22da47d4d0', confirmed=False)}
    result['curation'] = install_curated(args.db, result['source']['revision_id'], curated)
    status = 0
    if args.local_only:
        result['github_sync'] = {'status': 'pending', 'reason': 'Explicit staged maintenance; synchronize before delivery'}
    else:
        try:
            result['github_sync'] = sync_github(ROOT, args.db, args.raw_dir, 'Import supplied Shenqi chapter 1')
        except (SyncError, ValueError) as exc:
            result['github_sync'] = {'status': 'pending', 'reason': str(exc)}
            status = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
