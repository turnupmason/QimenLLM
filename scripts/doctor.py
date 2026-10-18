#!/usr/bin/env python3
"""Read-only host and pinned-model preflight; no weight loading or network access."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from importlib import metadata

ROOT = Path(__file__).resolve().parents[1]
PINNED = '10c35caafbb80f7dc6a7a432cdd11af10a6d4818'


def command(args, timeout=15):
    if not shutil.which(args[0]):
        return {'available': False}
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {'available': True, 'returncode': p.returncode, 'stdout': p.stdout.strip()[:2048]}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {'available': True, 'error': type(e).__name__}


def version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def memory_bytes():
    if platform.system() == 'Darwin':
        r = command(['sysctl', '-n', 'hw.memsize'])
        return int(r['stdout']) if r.get('returncode') == 0 and r.get('stdout', '').isdigit() else None
    if Path('/proc/meminfo').exists():
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):
                return int(line.split()[1]) * 1024
    if platform.system() == 'Windows':
        try:
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('memory_load', ctypes.c_ulong),
                            ('total_phys', ctypes.c_ulonglong), ('avail_phys', ctypes.c_ulonglong),
                            ('total_page', ctypes.c_ulonglong), ('avail_page', ctypes.c_ulonglong),
                            ('total_virtual', ctypes.c_ulonglong), ('avail_virtual', ctypes.c_ulonglong),
                            ('avail_extended', ctypes.c_ulonglong)]
            m = MemoryStatus(); m.length = ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return int(m.total_phys)
        except (AttributeError, OSError):
            pass
    return None


def model_report(manifest_path, verify_hashes=False):
    if not manifest_path:
        return {'status': 'manifest_not_supplied', 'verified': False}
    p = Path(manifest_path).resolve()
    if not p.is_file():
        return {'status': 'manifest_not_found', 'verified': False}
    manifest = json.loads(p.read_text(encoding='utf-8'))
    path = Path(manifest.get('local_path', '')).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    files = manifest.get('files', {})
    checked = 0; missing = []; mismatch = []
    for name, expected in files.items():
        file = (path / name).resolve()
        if not file.is_relative_to(path) or not file.is_file():
            missing.append(name)
            continue
        checked += 1
        if verify_hashes:
            h = hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                    h.update(chunk)
            if h.hexdigest() != expected.get('sha256'):
                mismatch.append(name)
    revision_ok = manifest.get('revision') == PINNED
    repo_ok = manifest.get('repo') == 'mlx-community/Qwen3.8-27B-4bit'
    return {'status': 'ok' if revision_ok and repo_ok and files and not missing and not mismatch else 'blocked',
            'revision': manifest.get('revision'), 'expected_revision': PINNED,
            'revision_match': revision_ok, 'repo_match': repo_ok, 'declared_files': len(files), 'present_files': checked,
            'missing_files': missing, 'hash_mismatches': mismatch,
            'verified': bool(revision_ok and repo_ok and files and not missing and not mismatch and verify_hashes),
            'hash_check_performed': verify_hashes}


def current_book_state():
    work = ROOT / 'work'
    def read_status(rel, *keys):
        file = work / rel
        if not file.is_file():
            return {'exists': False}
        try:
            value = json.loads(file.read_text(encoding='utf-8'))
            return {'exists': True, **{key: value.get(key) for key in keys}}
        except (OSError, ValueError):
            return {'exists': True, 'unreadable': True}
    data = work / 'book-method-curriculum-v1'
    return {'pipeline': read_status('book-iteration-v1/pipeline.json', 'stage', 'pid', 'error_type'),
            'stage_a_receipt': read_status('book-method-stage-a-cache.json', 'status', 'optimizer_updates'),
            'whole_book_cache': read_status('book-method-curriculum-cache.json', 'status', 'optimizer_updates'),
            'baseline': read_status('mac-book-method-before-v1/report.json', 'status', 'test_accessed'),
            'training': read_status('mac-book-method-lora-v1/progress.json', 'status', 'completed_epochs', 'optimizer_steps'),
            'training_receipt': read_status('mac-book-method-lora-v1/report.json', 'status', 'completed_epochs', 'optimizer_steps'),
            'release_files_present': {split: (data / (split + '.jsonl')).is_file()
                                      for split in ('train', 'validation', 'development', 'test')}}


def report(manifest_path=None, verify_hashes=False):
    mem = memory_bytes()
    disk = shutil.disk_usage(ROOT)
    packages = {p: version(p) for p in ('torch', 'mlx', 'mlx-lm', 'transformers', 'peft', 'bitsandbytes')}
    git_head = command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'])
    status = command(['git', '-C', str(ROOT), 'status', '--porcelain'])
    gpu = command(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv,noheader,nounits'])
    torch_probe = command([sys.executable, '-c', 'import json,torch;print(json.dumps({"cuda":torch.cuda.is_available(),"mps":torch.backends.mps.is_available()}))'], timeout=25) if packages['torch'] else {'available': False}
    mlx_probe = command([sys.executable, '-c', 'import json,mlx.core as mx;print(json.dumps({"metal":bool(mx.metal.is_available())}))'], timeout=25) if packages['mlx'] else {'available': False}
    probe = {'operating_system': platform.system(), 'os_release': platform.release(),
             'architecture': platform.machine(), 'python': platform.python_version(),
             'cpu_count': os.cpu_count(), 'memory_total_bytes': mem,
             'memory_headroom_after_19gb_mlx_limit_bytes': None if mem is None else mem - 19_000_000_000,
             'disk_free_bytes': disk.free, 'git': command(['git', '--version']),
             'git_lfs': command(['git', 'lfs', 'version']),
             'git_head': git_head.get('stdout') if git_head.get('returncode') == 0 else None,
             'git_worktree_clean': status.get('returncode') == 0 and not status.get('stdout'),
             'packages': packages, 'nvidia_smi': gpu, 'torch_accelerator': torch_probe, 'mlx_metal': mlx_probe,
             'metal_capable_host': platform.system() == 'Darwin' and platform.machine() == 'arm64',
             'mlx_installed': importlib.util.find_spec('mlx') is not None,
             'torch_installed': importlib.util.find_spec('torch') is not None,
             'model': model_report(manifest_path, verify_hashes),
             'book_iteration': current_book_state(),
             'machine_training_verified': False,
             'note': 'This checks availability and files, not a real GPU load or training step.'}
    latest = ROOT / 'work/mac-book-method-lora-v1/latest.json'
    probe['latest_checkpoint'] = json.loads(latest.read_text(encoding='utf-8')) if latest.is_file() else None
    return probe


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-manifest', type=Path, help='Existing pinned 27B local model manifest JSON')
    p.add_argument('--verify-model', action='store_true', help='SHA256 all listed model files; can take time')
    p.add_argument('--output', type=Path, help='Write private JSON report to work/ or another local path')
    a = p.parse_args()
    value = report(a.model_manifest, a.verify_model)
    content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        if a.output.exists():
            p.error('Will not overwrite an existing diagnostic: choose another filename')
        a.output.write_text(content, encoding='utf-8')
    print(content, end='')


if __name__ == '__main__':
    main()
