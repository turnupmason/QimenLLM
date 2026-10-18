import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.cli import main
from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.db import connect
from qimenllm.knowledge.importer import add_annotations
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot, TABLES
from support import DatabaseTest


class SnapshotTests(DatabaseTest):
    def test_complete_source_snapshot_roundtrip_and_idempotence(self):
        original='完整工程输入\r\n保持排版。'.encode()
        source=self.ingest(original,confirmed=False)
        self.ingest('修订工程输入。'.encode(),revision=2)
        self.ingest(original,confirmed=True)  # original revision exists; confirmation remains independent
        annotation={'byte_start':0,'byte_end':18,'locator':'工程整体','category':'commentary','payload':{'type':'fixture'}}
        add_annotations(self.db,source['revision_id'],[annotation])
        snapshot=self.root/'snapshot'
        first=export_snapshot(self.db,self.raw,snapshot)
        before={str(p.relative_to(snapshot)):p.read_bytes() for p in snapshot.rglob('*') if p.is_file()}
        second=export_snapshot(self.db,self.raw,snapshot)
        self.assertEqual(first,second)
        self.assertEqual(before,{str(p.relative_to(snapshot)):p.read_bytes() for p in snapshot.rglob('*') if p.is_file()})
        restored=self.root/'restored.sqlite3'
        report=restore_snapshot(snapshot,restored,self.root/'restored-raw')
        self.assertTrue(report['ok'])
        again=self.root/'again'
        export_snapshot(restored,self.root/'restored-raw',again)
        self.assertEqual((snapshot/'manifest.json').read_bytes(),(again/'manifest.json').read_bytes())
        for table in TABLES:
            self.assertEqual((snapshot/(table+'.jsonl')).read_bytes(),(again/(table+'.jsonl')).read_bytes())

    def test_empty_snapshot_restores_real_application(self):
        snapshot=self.root/'snapshot'
        export_snapshot(self.db,self.raw,snapshot)
        report=restore_snapshot(snapshot,self.root/'new.sqlite3',self.root/'new-raw')
        self.assertTrue(report['ok']); self.assertEqual(report['data_version'],'empty-v1')
        with self.assertRaises(FileExistsError): restore_snapshot(snapshot,self.db,self.raw)

    def test_hash_corruption_is_rejected_before_restore(self):
        self.ingest()
        snapshot=self.root/'snapshot'; export_snapshot(self.db,self.raw,snapshot)
        (snapshot/'books.jsonl').write_bytes(b'corrupted')
        target=self.root/'new.sqlite3'
        with self.assertRaises(ValueError): restore_snapshot(snapshot,target,self.root/'new-raw')
        self.assertFalse(target.exists())

    def test_frozen_family_splits_survive_restore(self):
        source=self.seed_event()
        with connect(self.db) as conn:
            conn.execute("INSERT INTO dataset_releases VALUES ('release',?,0,?)",(source['data_version'],'0'*64))
            conn.execute("INSERT INTO split_assignments VALUES ('release','family','test')")
            conn.execute("UPDATE dataset_releases SET frozen=1")
        snapshot=self.root/'snapshot'; export_snapshot(self.db,self.raw,snapshot)
        target=self.root/'new.sqlite3'; restore_snapshot(snapshot,target,self.root/'new-raw')
        with connect(target) as conn:
            self.assertEqual(conn.execute('SELECT frozen FROM dataset_releases').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT split FROM split_assignments').fetchone()[0],'test')


class SyncTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        (self.root/'configs').mkdir()
        (self.root/'configs/github.json').write_text(json.dumps({'repository':'owner/QimenLLM'}))

    def runner(self,private=True,remote_head='fixture-commit'):
        def run(args,root):
            if args[:3]==['git','remote','get-url']: return 'https://github.com/owner/QimenLLM.git'
            if args[:2]==['gh','api']: return json.dumps({'private':private,'full_name':'owner/QimenLLM'})
            if args[:3]==['git','diff','--cached']: return ''
            if args[:2]==['git','rev-parse']: return 'fixture-commit'
            if args[:2]==['git','ls-remote']: return remote_head+'\trefs/heads/main'
            return ''
        return run

    def test_remote_verified_before_success_receipt(self):
        with patch('qimenllm.github_sync._run',side_effect=self.runner()) as run:
            result=sync_github(self.root,self.db,self.raw,'fixture update')
        self.assertEqual(result['status'],'synced')
        self.assertTrue(any(call.args[0][:2]==['git','push'] for call in run.call_args_list))
        staged_paths={path for call in run.call_args_list if call.args[0][:2]==['git','add']
                      for path in call.args[0][2:]}
        self.assertTrue({'data/snapshots','data/structured','data/provenance'}<=staged_paths)
        self.assertIn('.gitattributes',staged_paths)
        self.assertNotIn('data/raw_books',staged_paths)
        self.assertTrue((self.root/'work/github-sync.json').exists())

    def test_public_repo_does_not_stage_or_push_data(self):
        with patch('qimenllm.github_sync._run',side_effect=self.runner(private=False)) as run:
            with self.assertRaises(SyncError): sync_github(self.root,self.db,self.raw,'fixture')
        self.assertFalse(any(call.args[0][:2] in (['git','add'],['git','push']) for call in run.call_args_list))

    def test_wrong_remote_head_never_claims_synced(self):
        with patch('qimenllm.github_sync._run',side_effect=self.runner(remote_head='different')):
            with self.assertRaises(SyncError): sync_github(self.root,self.db,self.raw,'fixture')
        self.assertFalse((self.root/'work/github-sync.json').exists())

    def public_fixture(self):
        from hashlib import sha256
        folder=self.root/'docs/user_instructions';folder.mkdir(parents=True)
        instruction=folder/'all_cases_pilot_github_2026-10-17.txt'
        instruction.write_text('Fixture: user explicitly authorizes public synchronization')
        (folder/'manifest.json').write_text(json.dumps({'files':[{'path':instruction.name,
            'sha256':sha256(instruction.read_bytes()).hexdigest()}]}))
        (self.root/'configs/github.json').write_text(json.dumps({'repository':'turnupmason/QimenLLM',
            'visibility':'public','public_sync_user_authorization':str(instruction.relative_to(self.root))}))
        default=self.runner()
        def run(args,root):
            if args[:3]==['git','remote','get-url']:return 'https://github.com/turnupmason/QimenLLM.git'
            if args[:2]==['gh','api']:return json.dumps({'private':False,'full_name':'turnupmason/QimenLLM'})
            return default(args,root)
        return instruction,run

    def test_explicit_recorded_public_target_may_sync(self):
        _,runner=self.public_fixture()
        with patch('qimenllm.github_sync._run',side_effect=runner):
            result=sync_github(self.root,self.db,self.raw,'fixture')
        self.assertEqual(result['status'],'synced')

    def test_altered_public_authorization_cannot_stage_or_push(self):
        instruction,runner=self.public_fixture()
        instruction.write_text('Changed bytes')
        with patch('qimenllm.github_sync._run',side_effect=runner) as run:
            with self.assertRaises(SyncError):sync_github(self.root,self.db,self.raw,'fixture')
        self.assertFalse(any(c.args[0][:2] in (['git','add'],['git','push']) for c in run.call_args_list))

    def test_cli_import_saves_content_and_reports_pending_on_network_failure(self):
        path=self.root/'chapter.txt'; path.write_bytes(b'Neutral engineering fixture')
        args=['--db',str(self.db),'--raw-dir',str(self.raw),'import-chapter',str(path),
              '--book-key','fixture','--book-title','fixture','--chapter-key','one',
              '--chapter-title','fixture','--sequence','1','--origin','test']
        out=io.StringIO()
        with patch('qimenllm.cli.sync_github',side_effect=SyncError('Network unavailable')) as sync:
            with redirect_stdout(out): code=main(args)
        self.assertEqual(code,2); sync.assert_called_once()
        self.assertEqual(json.loads(out.getvalue())['github_sync']['status'],'pending')
        with connect(self.db) as conn: self.assertEqual(conn.execute('SELECT COUNT(*) FROM raw_documents').fetchone()[0],1)
