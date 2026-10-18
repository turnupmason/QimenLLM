#!/usr/bin/env python3
"""Ingest the byte-confirmed Shenqi accuracy chapter with existing append-only APIs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.accuracy import ACCURACY_SHA, install_accuracy
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.snapshot import restore_snapshot

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structured/shenqi'
UPLOAD = ROOT / 'data/provenance/uploads' / (ACCURACY_SHA + '.utf8')


def ingest(db, raw_dir):
    raw = UPLOAD.read_bytes()
    if digest(raw) != ACCURACY_SHA or len(raw) != 9177 or len(raw.splitlines()) != 37:
        raise ValueError('Source bytes differ from uploaded TXT')
    source = import_chapter(
        db, raw_dir, raw, book_key='shenqi-user-text-v1',
        book_title='神奇之门', chapter_key='accuracy-assessment',
        chapter_title='奇门预测准确率评估', sequence=22,
        origin='user-attached-TXT:神奇之门_奇门预测准确率评估_精校完整版.txt; SHA256:' + ACCURACY_SHA)
    load = lambda key: json.loads((DATA / ('accuracy_' + key + '.json')).read_bytes())
    curation = install_accuracy(db, source['revision_id'], load('curated'))
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
                'Ingest confirmed accuracy-assessment methodology without inventing cases or scores')
        except (SyncError, ValueError) as exc:
            result['github_sync'] = {'status': 'pending', 'reason': str(exc)}
            code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
