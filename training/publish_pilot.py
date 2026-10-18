"""Publish each selected, tested pilot adapter as a GitHub Release, with verified hashes.

Run on the user's training clone after gh auth login. No tokens are printed or
stored. Base weights, optimizer state and arbitrary run files are never uploaded.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from cuda_pilot import ROOT, checkpoint_receipt, fingerprint, load_config, sha, encoded, write_new


def command(args, cwd=ROOT):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Required Git/GitHub command unavailable or timed out') from exc
    if r.returncode:
        raise RuntimeError('Git/GitHub operation failed; no verified success recorded')
    return r.stdout.strip()


def publish(c, run):
    run = run.resolve()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,60}', run.name):
        raise ValueError('Use a simple versioned experiment name')
    config = json.loads((ROOT/'configs/github.json').read_bytes())
    repo = 'turnupmason/QimenLLM'
    if config['repository'] != repo or config['visibility'] != 'public' or not config.get('public_sync_user_authorization'):
        raise ValueError('Recorded user authorization and exact repository required')
    if command(['git', 'remote', 'get-url', 'origin']) != 'https://github.com/'+repo+'.git':
        raise ValueError('Unexpected origin')
    metadata = json.loads(command(['gh', 'api', 'repos/'+repo]))
    if metadata['full_name'] != repo or metadata['private'] or not metadata['permissions']['push']:
        raise ValueError('Repository visibility or push permission changed')
    if command(['git', 'branch', '--show-current']) != 'main' or command(['git', 'status', '--porcelain']):
        raise ValueError('Publish from a clean main checkout')
    code_sha = command(['git', 'rev-parse', 'HEAD'])
    if command(['git', 'ls-remote', 'origin', 'refs/heads/main']).split()[0] != code_sha:
        raise ValueError('Local main differs from remote; update clean checkout first')
    selected = json.loads((run/'selected.json').read_bytes())
    if selected['fingerprint'] != fingerprint(c):
        raise ValueError('Selected code/config/data changed')
    checkpoint = run/selected['checkpoint']
    receipt = checkpoint_receipt(checkpoint, fingerprint(c))
    if sha((checkpoint/'receipt.json').read_bytes()) != selected['checkpoint_receipt_sha256']:
        raise ValueError('Selected checkpoint receipt changed')
    names = ['preflight.json', 'baseline-validation.json', 'training-started.json',
             'training-complete.json', 'selected.json', 'blind-test-base.json', 'blind-test.json',
             selected['checkpoint']+'-validation.json']
    for name in names:
        if json.loads((run/name).read_bytes())['fingerprint'] != fingerprint(c):
            raise ValueError('Experiment record differs from selected data/code')
    adapter = checkpoint/'adapter'
    allowed = {'adapter_config.json', 'adapter_model.safetensors', 'README.md'}
    if {p.name for p in adapter.iterdir()} - allowed:
        raise ValueError('Unexpected adapter files; do not upload arbitrary artifacts')
    digest = sha((adapter/'adapter_model.safetensors').read_bytes())
    tag = 'qimenllm-'+run.name+'-'+digest[:12]
    archive = run/(tag+'.zip')
    if archive.exists():
        raise FileExistsError('Publication artifacts immutable; inspect prior receipt before retrying')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(adapter.iterdir()):
            z.write(p, 'adapter/'+p.name)
        for name in names:
            z.write(run/name, 'experiment/'+name)
        z.writestr('experiment/config.json', encoded(c))
        z.writestr('experiment/checkpoint-receipt.json', encoded(receipt))
    notes = run/(tag+'-notes.txt')
    notes.write_text('QimenLLM 钱物丢失章节研究试验。基座 '+c['model']+' @ '+c['revision']+
        '\n源码 '+code_sha+'\n适配器 SHA256 '+digest+'\n附件 SHA256 '+sha(archive.read_bytes())+
        '\n作者方法语义评分、书中反馈一致率及独立现实预测准确率分开；自动协议检查不代表断案成功。\n')
    command(['gh', 'release', 'create', tag, str(archive), '--repo', repo, '--target', code_sha,
             '--title', tag, '--notes-file', str(notes)])
    with tempfile.TemporaryDirectory() as tmp:
        command(['gh', 'release', 'download', tag, '--repo', repo, '--pattern', archive.name, '--dir', tmp])
        if sha((Path(tmp)/archive.name).read_bytes()) != sha(archive.read_bytes()):
            raise RuntimeError('Downloaded release asset hash differs')
    record = {'experiment_id': run.name, 'release_tag': tag, 'code_sha': code_sha,
              'release_url': 'https://github.com/'+repo+'/releases/tag/'+tag,
              'model': c['model'], 'model_revision': c['revision'], 'fingerprint': fingerprint(c),
              'adapter_sha256': digest, 'archive_sha256': sha(archive.read_bytes()),
              'records_sha256': {name: sha((run/name).read_bytes()) for name in names},
              'author_method_accuracy': None, 'reported_feedback_accuracy': None,
              'independent_real_world_accuracy': None, 'release_asset_reopened_and_verified': True}
    path = ROOT/'data/provenance'/(tag+'.json')
    write_new(path, record)
    command(['git', 'add', '--', str(path.relative_to(ROOT))])
    user = json.loads(command(['gh', 'api', 'user']))
    command(['git', '-c', 'user.name='+user['login'], '-c',
             'user.email='+str(user['id'])+'+'+user['login']+'@users.noreply.github.com',
             'commit', '-m', 'Record verified model experiment '+tag])
    local = command(['git', 'rev-parse', 'HEAD'])
    command(['git', 'push', 'origin', 'HEAD:refs/heads/main'])
    if command(['git', 'ls-remote', 'origin', 'refs/heads/main']).split()[0] != local:
        raise RuntimeError('Experiment manifest remote SHA mismatch')
    result = {'status': 'release_and_main_verified', 'commit': local, **record}
    write_new(run/'github-publication.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=ROOT/'training/lost_4090_pilot.json')
    p.add_argument('--run', type=Path, default=ROOT/'work/lost-4090-run001')
    a = p.parse_args()
    print(json.dumps(publish(load_config(a.config), a.run), ensure_ascii=False, indent=2))
