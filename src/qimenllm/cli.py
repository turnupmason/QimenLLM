from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server
from .api.app import create_app
from .contracts import Inquiry
from .knowledge.db import connect, digest, initialize
from .knowledge.importer import add_annotations, import_chapter
from .knowledge.integrity import audit
from .knowledge.snapshot import export_snapshot, restore_snapshot
from .github_sync import sync_github, SyncError
from .reasoning.service import QimenService


class PrivateRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass  # no URL/query/user text access log in the research server


def main(argv=None):
    parser = argparse.ArgumentParser(description='QimenLLM Phase 0 research tools')
    parser.add_argument('--db',default='data/qimenllm.sqlite3')
    parser.add_argument('--raw-dir',default='data/raw_books')
    subs = parser.add_subparsers(dest='command',required=True)
    for name in ('init','audit'): subs.add_parser(name)
    importer = subs.add_parser('import-chapter')
    importer.add_argument('file',type=Path)
    for name in ('book-key','book-title','chapter-key','chapter-title','origin'):
        importer.add_argument('--'+name,required=True)
    importer.add_argument('--sequence',type=int,required=True)
    importer.add_argument('--author'); importer.add_argument('--edition')
    importer.add_argument('--revision',type=int)
    importer.add_argument('--confirmed',action='store_true',help='Only when user explicitly confirmed the original')
    annotate = subs.add_parser('annotate')
    annotate.add_argument('revision_id'); annotate.add_argument('file',type=Path)
    ask = subs.add_parser('ask'); ask.add_argument('text')
    learn = subs.add_parser('learn'); learn.add_argument('term')
    serve = subs.add_parser('serve'); serve.add_argument('--port',type=int,default=8765)
    backup = subs.add_parser('backup'); backup.add_argument('destination',type=Path)
    snapshot = subs.add_parser('export-snapshot'); snapshot.add_argument('destination',type=Path,nargs='?',default=Path('data/snapshots/current'))
    restore = subs.add_parser('restore-snapshot'); restore.add_argument('snapshot',type=Path); restore.add_argument('destination',type=Path)
    sync = subs.add_parser('sync'); sync.add_argument('--message',required=True)
    args = parser.parse_args(argv)
    if args.command=='init':
        initialize(args.db); result={'status':'initialized','db':args.db,'knowledge_seeded':False}
    elif args.command=='import-chapter':
        fields = {name:getattr(args,name) for name in ('book_key','book_title','chapter_key','chapter_title','sequence','origin','author','edition','revision','confirmed')}
        result=import_chapter(args.db,args.raw_dir,args.file.read_bytes(),**fields)
    elif args.command=='annotate':
        result=add_annotations(args.db,args.revision_id,json.loads(args.file.read_bytes()))
    elif args.command=='audit': result=audit(args.db,args.raw_dir)
    elif args.command=='export-snapshot': result=export_snapshot(args.db,args.raw_dir,args.destination)
    elif args.command=='restore-snapshot': result=restore_snapshot(args.snapshot,args.destination,args.raw_dir)
    elif args.command=='sync':
        try: result=sync_github(Path.cwd(),args.db,args.raw_dir,args.message)
        except (SyncError,ValueError) as exc:
            print(json.dumps({'github_sync':'pending','reason':str(exc)},ensure_ascii=False,indent=2))
            return 2
    elif args.command=='backup':
        if args.destination.exists(): parser.error('Backup destination must be new')
        args.destination.parent.mkdir(parents=True,exist_ok=True)
        with connect(args.db) as source:
            with sqlite3.connect(args.destination) as destination: source.backup(destination)
        result={'backup':str(args.destination),'sha256':digest(args.destination.read_bytes()),
                'note':'Copy raw_books mirrors and record Git commit together; database includes authoritative raw bytes.'}
    elif args.command=='serve':
        # No host flag: external listening requires a separate reviewed deployment design.
        with make_server('127.0.0.1',args.port,create_app(QimenService(args.db)),handler_class=PrivateRequestHandler) as server:
            print(f'Research API: http://127.0.0.1:{args.port} (not for public use)',flush=True)
            server.serve_forever()
        return 0
    else:
        service=QimenService(args.db)
        result=service.ask(Inquiry(args.text)) if args.command=='ask' else service.learning.learn(args.term)
    if args.command in ('import-chapter','annotate'):
        try:
            result['github_sync']=sync_github(Path.cwd(),args.db,args.raw_dir,
                                            f'Update source data: {args.command}')
        except (SyncError,ValueError) as exc:
            result['github_sync']={'status':'pending','reason':str(exc)}
            result['note']='本地资料已保存，GitHub 尚未同步成功；修复连接后运行 sync 重试。'
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if args.command=='audit' and not result['ok'] else 0


if __name__=='__main__': raise SystemExit(main())
