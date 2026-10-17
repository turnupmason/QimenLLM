#!/usr/bin/env python3
"""Replay only this authorized second-chapter upload and its reviewed curation."""
import argparse
import json
from pathlib import Path

from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.chapter02 import SOURCE_SHA, install_chapter02
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter


ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path,nargs='?',
                        default=ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHA}.bin')
    parser.add_argument('--db',type=Path,default=ROOT/'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw_books')
    parser.add_argument('--local-only',action='store_true',
                        help='Staged maintenance only; synchronize GitHub before delivery')
    args=parser.parse_args(); raw=args.source.read_bytes()
    if digest(raw)!=SOURCE_SHA: parser.error('Different bytes require an explicit new revision workflow')
    curated=json.loads((ROOT/'data/structured/shenqi/chapter02_curated.json').read_bytes())
    result={'source':import_chapter(args.db,args.raw_dir,raw,book_key='shenqi-user-text-v1',
        book_title='神奇之门',chapter_key='chapter-02',chapter_title='时家奇门的起局方法',
        sequence=2,origin='user-upload:file_00000000e23881f6a5483db6435220e3',confirmed=True)}
    result['curation']=install_chapter02(args.db,result['source']['revision_id'],curated)
    code=0
    if args.local_only:
        result['github_sync']={'status':'pending','reason':'Explicit staged maintenance; synchronize before delivery'}
    else:
        try: result['github_sync']=sync_github(ROOT,args.db,args.raw_dir,'Import supplied Shenqi chapter 2')
        except (SyncError,ValueError) as exc:
            result['github_sync']={'status':'pending','reason':str(exc)}; code=2
    print(json.dumps(result,ensure_ascii=False,indent=2)); return code


if __name__=='__main__': raise SystemExit(main())
