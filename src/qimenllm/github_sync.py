"""Explicit authorized-repository synchronization; failures are never success."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
from .knowledge.snapshot import export_snapshot


class SyncError(RuntimeError):
    pass


def _run(args,root):
    try:
        env=os.environ.copy()
        env['PYTHONPATH']=str(root/'src')
        result=subprocess.run(args,cwd=root,env=env,capture_output=True,text=True,timeout=600)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise SyncError('Command unavailable or timed out: '+args[0]) from exc
    if result.returncode:
        # Do not echo command stderr: credential helpers or remotes may contain secrets.
        raise SyncError('Command failed: '+' '.join(args[:3])+f' (exit {result.returncode})')
    return result.stdout.strip()


def sync_github(root: str | Path, db: str | Path, raw_dir: str | Path, message: str) -> dict:
    root=Path(root).resolve()
    try: config=json.loads((root/'configs/github.json').read_bytes())
    except (OSError,ValueError) as exc: raise SyncError('Missing or invalid configs/github.json') from exc
    if Path(_run(['git','rev-parse','--show-toplevel'],root)).resolve()!=root:
        raise SyncError('Project must be the actual Git checkout root')
    export=export_snapshot(db,raw_dir,root/'data/snapshots/current')
    repository=config['repository']
    expected='https://github.com/'+repository+'.git'
    actual=_run(['git','remote','get-url','origin'],root)
    if actual!=expected: raise SyncError('Unexpected Git origin; refusing to publish data')
    # Check repository visibility before even staging a data export.
    metadata=json.loads(_run(['gh','api','repos/'+repository,'--jq','{private: .private, full_name: .full_name}'],root))
    visibility=config.get('visibility','private')
    if visibility not in ('private','public'):
        raise SyncError('Explicit supported visibility required')
    if visibility=='public':
        authorization=config.get('public_sync_user_authorization')
        instruction=root/'docs/user_instructions/all_cases_pilot_github_2026-10-17.txt'
        try:
            manifest=json.loads((root/'docs/user_instructions/manifest.json').read_bytes())
        except (OSError,ValueError) as exc:
            raise SyncError('Public synchronization authorization unavailable') from exc
        from hashlib import sha256
        registered=[r for r in manifest['files'] if r['path']==instruction.name]
        if (repository!='turnupmason/QimenLLM' or authorization!=str(instruction.relative_to(root))
                or not instruction.is_file() or len(registered)!=1
                or sha256(instruction.read_bytes()).hexdigest()!=registered[0]['sha256']):
            raise SyncError('Public synchronization requires the recorded user authorization')
    if metadata!={'private':visibility=='private','full_name':repository}:
        raise SyncError('Verified target visibility differs from authorized configuration')
    _run([sys.executable,'-m','unittest','discover','-s','tests','-q'],root)
    # Only tracked changes plus approved project paths; no arbitrary `git add .`.
    _run(['git','add','-u'],root)
    _run(['git','add','AGENTS.md','README.md','pyproject.toml','Makefile','.gitignore','.gitattributes',
          'configs','docs','src','scripts','tests','.github','frontend','training',
          'data/snapshots','data/structured','data/provenance','data/rules','data/cases','data/splits'],root)
    staged=_run(['git','diff','--cached','--name-only'],root)
    if staged:
        _run(['git','diff','--cached','--check'],root)
        _run(['git','commit','-m',message],root)
    local=_run(['git','rev-parse','HEAD'],root)
    _run(['git','push','--set-upstream','origin','HEAD:refs/heads/main'],root)
    remote=_run(['git','ls-remote','origin','refs/heads/main'],root).split()
    if not remote or remote[0]!=local: raise SyncError('Remote HEAD does not match local commit')
    receipt={'status':'synced','repository':repository,'commit':local,'data_version':export['data_version'],
             'snapshot_manifest_sha256':export['manifest_sha256']}
    work=root/'work'; work.mkdir(exist_ok=True)
    (work/'github-sync.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return receipt
