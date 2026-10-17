#!/usr/bin/env python3
"""Replay confirmed pregnancy/childbirth source, complete stories and reference candidates."""
import argparse
import json
from pathlib import Path
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import PREGNANCY_SHA
from qimenllm.github_sync import SyncError,sync_github
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.pregnancy import install_pregnancy
from qimenllm.rules.candidates import install_candidates

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/structured/shenqi'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/snapshots/current/raw'/f'{PREGNANCY_SHA}.bin')
    parser.add_argument('--db',type=Path,default=ROOT/'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw_books')
    parser.add_argument('--local-only',action='store_true',help='Staged maintenance; synchronize before delivery')
    args=parser.parse_args();raw=args.source.read_bytes()
    if digest(raw)!=PREGNANCY_SHA:
        parser.error('Different source bytes require explicit revision workflow')
    source=import_chapter(args.db,args.raw_dir,raw,book_key='shenqi-user-text-v1',book_title='神奇之门',
        chapter_key='pregnancy-childbirth',chapter_title='怀孕分娩预测',sequence=9,
        origin='user-upload:sediment://file_00000000f65081f69216ab4e5ea91adf',confirmed=True)
    load=lambda key:json.loads((DATA/f'pregnancy_{key}.json').read_bytes())
    result={'source':source,'curation':install_pregnancy(args.db,source['revision_id'],load('curated')),
            'cases':import_cases(args.db,source['revision_id'],load('cases')),
            'candidates':install_candidates(args.db,source['revision_id'],load('rule_candidates'))}
    code=0
    if args.local_only:
        result['github_sync']={'status':'pending','reason':'Staged maintenance; synchronize before delivery'}
    else:
        try:
            result['github_sync']=sync_github(ROOT,args.db,args.raw_dir,
                'Update confirmed pregnancy chapter and complete childbirth case chronology')
        except (SyncError,ValueError) as exc:
            result['github_sync']={'status':'pending','reason':str(exc)};code=2
    print(json.dumps(result,ensure_ascii=False,indent=2));return code


if __name__=='__main__':raise SystemExit(main())
