#!/usr/bin/env python3
"""Replay the confirmed inline employment source, whole narratives and references."""
import argparse
import json
from pathlib import Path
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import EMPLOYMENT_SHA
from qimenllm.github_sync import SyncError,sync_github
from qimenllm.knowledge.db import digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.employment import install_employment
from qimenllm.rules.candidates import install_candidates

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/structured/shenqi'
MESSAGE_SHA='f29974870ede762aa4fd3370bb7554f031d45d6b79f993d5e673ad1cd453af67'


def source_from_inline_message():
    """Verify the preserved chat serialization and its explicit body slice."""
    pointer=json.loads((ROOT/'data/provenance/employment_inline_input.json').read_bytes())
    path=(ROOT/pointer['message_path']).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Input provenance must stay inside the project')
    message=path.read_bytes()
    if digest(message)!=MESSAGE_SHA or pointer['message_sha256']!=MESSAGE_SHA:
        raise ValueError('Inline message fingerprint mismatch')
    prefix='下一个： '.encode('utf-8')
    if (not message.startswith(prefix) or pointer['source_byte_start']!=len(prefix)
            or pointer['source_byte_end']!=len(message)):
        raise ValueError('Unexpected inline instruction/body boundary')
    body=message[pointer['source_byte_start']:pointer['source_byte_end']]
    if digest(body)!=EMPLOYMENT_SHA or pointer['source_sha256']!=EMPLOYMENT_SHA:
        raise ValueError('Employment body fingerprint mismatch')
    return body


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/snapshots/current/raw'/f'{EMPLOYMENT_SHA}.bin')
    parser.add_argument('--db',type=Path,default=ROOT/'data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw_books')
    parser.add_argument('--local-only',action='store_true',help='Staged maintenance; synchronize before delivery')
    args=parser.parse_args();raw=args.source.read_bytes()
    if digest(raw)!=EMPLOYMENT_SHA or raw!=source_from_inline_message():
        parser.error('Different source bytes require an explicit revision workflow')
    source=import_chapter(args.db,args.raw_dir,raw,book_key='shenqi-user-text-v1',book_title='神奇之门',
        chapter_key='work-employment',chapter_title='工作就业预测',sequence=11,
        origin='user-inline-chat:employment; message-sha256:'+MESSAGE_SHA+'; bytes 13:22434')
    load=lambda key:json.loads((DATA/f'employment_{key}.json').read_bytes())
    result={'source':source,'curation':install_employment(args.db,source['revision_id'],load('curated')),
            'cases':import_cases(args.db,source['revision_id'],load('cases')),
            'candidates':install_candidates(args.db,source['revision_id'],load('rule_candidates'))}
    code=0
    if args.local_only:
        result['github_sync']={'status':'pending','reason':'Staged maintenance; synchronize before delivery'}
    else:
        try:
            result['github_sync']=sync_github(ROOT,args.db,args.raw_dir,
                'Update confirmed employment methods and full multi-round historical cases')
        except (SyncError,ValueError) as exc:
            result['github_sync']={'status':'pending','reason':str(exc)};code=2
    print(json.dumps(result,ensure_ascii=False,indent=2));return code


if __name__=='__main__':raise SystemExit(main())
