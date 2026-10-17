#!/usr/bin/env python3
"""Replay exactly this supplied application overview, its whole case and source candidates."""
import argparse
import json
from pathlib import Path

from qimenllm.cases.ingestion import import_cases
from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.application_overview import SOURCE_SHA, install_application
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.rules.candidates import install_candidates

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/structured/shenqi'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHA}.bin')
    parser.add_argument('--db',type=Path,default=ROOT/'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw_books')
    parser.add_argument('--local-only',action='store_true',help='Staged maintenance; synchronize before delivery')
    args=parser.parse_args(); raw=args.source.read_bytes()
    if digest(raw)!=SOURCE_SHA: parser.error('Different source bytes require an explicit revision workflow')
    source=import_chapter(args.db,args.raw_dir,raw,book_key='shenqi-user-text-v1',book_title='神奇之门',
        chapter_key='application-overview',chapter_title='奇门遁甲应用概述',sequence=6,
        origin='user-upload:sediment://file_000000003d1081f6b048e2ee4b4b1253',confirmed=False)
    load=lambda key:json.loads((DATA/f'application_overview_{key}.json').read_bytes())
    result={'source':source,'curation':install_application(args.db,source['revision_id'],load('curated')),
            'candidates':install_candidates(args.db,source['revision_id'],load('rule_candidates')),
            'cases':import_cases(args.db,source['revision_id'],load('cases'))}
    code=0
    if args.local_only:
        result['github_sync']={'status':'pending','reason':'Explicit staged maintenance; synchronize before delivery'}
    else:
        try: result['github_sync']=sync_github(ROOT,args.db,args.raw_dir,'Update supplied application overview and whole case')
        except (SyncError,ValueError) as exc:
            result['github_sync']={'status':'pending','reason':str(exc)}; code=2
    print(json.dumps(result,ensure_ascii=False,indent=2)); return code

if __name__=='__main__': raise SystemExit(main())
