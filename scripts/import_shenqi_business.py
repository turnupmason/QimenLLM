#!/usr/bin/env python3
"""Idempotently import the user-confirmed business chapter using EXISTING QimenLLM modules.

This script intentionally never creates executable professional role rules, training
tasks, invented charts, or inferred case results. The supplied source is immutable.
"""
import argparse
import json
from pathlib import Path

from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import BUSINESS_SHA
from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.business import install_business
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.rules.candidates import install_candidates

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structured/shenqi'
DEFAULT_SOURCE = ROOT / 'data/provenance/uploads/business_source_20261017.utf8'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'data/raw_books')
    parser.add_argument('--local-only', action='store_true', help='Only for staged validation: sync before delivery')
    args = parser.parse_args()

    source = args.source.read_bytes()
    if digest(source) != BUSINESS_SHA:
        parser.error('Different supplied bytes require an explicit new chapter revision')
    load = lambda key: json.loads((DATA / f'business_{key}.json').read_bytes())
    curated, cases, candidates = (load(key) for key in ('curated', 'cases', 'rule_candidates'))
    for obj in (curated, cases, candidates):
        if obj['source_sha256'] != BUSINESS_SHA:
            parser.error('Curation, cases and candidate hashes must equal original source')
    chapter = import_chapter(
        args.db, args.raw_dir, source, book_key='shenqi-user-text-v1',
        book_title='神奇之门', chapter_key='business-finance',
        chapter_title='经营求财预测', sequence=12,
        origin='user-supplied-inline-business-chapter-2026-10-17; source-sha256:' + BUSINESS_SHA)
    result = {
        'source': chapter,
        'curation': install_business(args.db, chapter['revision_id'], curated),
        'cases': import_cases(args.db, chapter['revision_id'], cases),
        'candidates': install_candidates(args.db, chapter['revision_id'], candidates),
    }
    code = 0
    if args.local_only:
        result['github_sync'] = {'status': 'pending', 'reason': 'Staged data import only'}
    else:
        try:
            result['github_sync'] = sync_github(
                ROOT, args.db, args.raw_dir,
                'Ingest user-confirmed business methods and fourteen complete cases')
        except (SyncError, ValueError) as exc:
            result['github_sync'] = {'status': 'pending', 'reason': str(exc)}
            code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
