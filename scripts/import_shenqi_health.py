#!/usr/bin/env python3
"""Replay exactly the supplied health chapter and its six whole narratives."""
import argparse
import json
from pathlib import Path
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import HEALTH_SHA
from qimenllm.github_sync import SyncError,sync_github
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.health import install_health
from qimenllm.knowledge.importer import import_chapter

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/structured/shenqi'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/snapshots/current/raw'/f'{HEALTH_SHA}.bin')
    parser.add_argument('--db',type=Path,default=ROOT/'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw_books')
    parser.add_argument('--local-only',action='store_true',help='Staged maintenance; synchronize before delivery')
    args=parser.parse_args();raw=args.source.read_bytes()
    if digest(raw)!=HEALTH_SHA:parser.error('Different source bytes require explicit revision workflow')
    source=import_chapter(args.db,args.raw_dir,raw,book_key='shenqi-user-text-v1',book_title='神奇之门',
        chapter_key='health-prediction',chapter_title='人体疾病预测',sequence=7,
        origin='user-upload:sediment://file_00000000126481f6ab7b7bec77ac66b1',confirmed=True)
    result={'source':source,'curation':install_health(args.db,source['revision_id'],json.loads((DATA/'health_curated.json').read_bytes())),
            'cases':import_cases(args.db,source['revision_id'],json.loads((DATA/'health_cases.json').read_bytes()))}
    code=0
    if args.local_only:result['github_sync']={'status':'pending','reason':'Staged maintenance; synchronize before delivery'}
    else:
        try:result['github_sync']=sync_github(ROOT,args.db,args.raw_dir,'Update supplied health chapter and six whole cases')
        except (SyncError,ValueError) as exc:result['github_sync']={'status':'pending','reason':str(exc)};code=2
    print(json.dumps(result,ensure_ascii=False,indent=2));return code

if __name__=='__main__':raise SystemExit(main())
