#!/usr/bin/env python3
"""Replay the exact combined upload, retaining byte-identical parent and chapter slices."""
import argparse
import json
from pathlib import Path

from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.chapters0405 import SOURCE_SHAS, install_chapter
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter


ROOT=Path(__file__).resolve().parents[1]
UPLOAD_SHA='8b8d7f57fa539785f5613cb6f8fdbdc27090da559d6d2fe5ce0ffd03953c9147'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/provenance/uploads'/f'{UPLOAD_SHA}.utf8')
    parser.add_argument('--db',type=Path,default=ROOT/'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw_books')
    parser.add_argument('--local-only',action='store_true',help='Staged maintenance; sync before delivery')
    args=parser.parse_args(); raw=args.source.read_bytes()
    if digest(raw)!=UPLOAD_SHA: parser.error('Different upload bytes require an explicit revision workflow')
    lines=raw.splitlines(keepends=True); boundary=sum(map(len,lines[:500]))
    results=[]
    for number,title,start,end in ((4,'奇门预测符号的象数理含义',0,boundary),
                                   (5,'奇门预测的判断依据',boundary,len(raw))):
        content=raw[start:end]
        if digest(content)!=SOURCE_SHAS[number]: parser.error('Chapter slice fingerprint mismatch')
        curated=json.loads((ROOT/f'data/structured/shenqi/chapter{number:02d}_curated.json').read_bytes())
        source=import_chapter(args.db,args.raw_dir,content,book_key='shenqi-user-text-v1',book_title='神奇之门',
            chapter_key=f'chapter-0{number}',chapter_title=title,sequence=number,
            origin=f'user-upload:file_00000000a94481f6bc6b14739af71694; byte slice {start}:{end}',confirmed=True)
        results.append({'chapter':number,'source':source,
                        'curation':install_chapter(args.db,source['revision_id'],curated,number)})
    result={'upload_sha256':UPLOAD_SHA,'chapters':results}; code=0
    if args.local_only:
        result['github_sync']={'status':'pending','reason':'Explicit staged maintenance; synchronize before delivery'}
    else:
        try: result['github_sync']=sync_github(ROOT,args.db,args.raw_dir,'Update supplied Shenqi chapters 4 and 5')
        except (SyncError,ValueError) as exc:
            result['github_sync']={'status':'pending','reason':str(exc)}; code=2
    print(json.dumps(result,ensure_ascii=False,indent=2)); return code


if __name__=='__main__': raise SystemExit(main())
