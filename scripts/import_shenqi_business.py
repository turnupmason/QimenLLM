#!/usr/bin/env python3
"""Ingest the byte-confirmed Shenqi business chapter with existing append-only APIs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qimenllm.cases.ingestion import import_cases
from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.business import BUSINESS_SHA, install_business
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.rules.candidates import install_candidates

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structured/shenqi'
UPLOAD = ROOT / 'data/provenance/uploads' / (BUSINESS_SHA + '.utf8')


def ingest(db, raw_dir):
    raw = UPLOAD.read_bytes()
    if digest(raw) != BUSINESS_SHA or len(raw) != 56047 or len(raw.splitlines()) != 1366:
        raise ValueError('Source bytes differ from uploaded TXT')
    source = import_chapter(
        db, raw_dir, raw, book_key='shenqi-user-text-v1',
        book_title='神奇之门', chapter_key='business-finance',
        chapter_title='经营求财预测', sequence=12,
        origin='user-attached-TXT:经营求财预测_完整原文.txt; SHA256:' + BUSINESS_SHA)
    load = lambda key: json.loads((DATA / ('business_' + key + '.json')).read_bytes())
    curation = install_business(db, source['revision_id'], load('curated'))
    cases = import_cases(db, source['revision_id'], load('cases'))
    candidates = install_candidates(db, source['revision_id'], load('rule_candidates'))
    return {'source': source, 'curation': curation, 'cases': cases,
            'candidates': candidates, 'original_charts_expected': 16,
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
                'Ingest confirmed business methods and 14 complete historical stories')
        except (SyncError, ValueError) as exc:
            result['github_sync'] = {'status': 'pending', 'reason': str(exc)}
            code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
