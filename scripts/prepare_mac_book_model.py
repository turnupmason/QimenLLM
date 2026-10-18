#!/usr/bin/env python3
"""Locate already-downloaded SHA-pinned MLX 27B weights; never downloads/trains.

Hugging Face snapshot entries are often symlinks into ../../blobs. Existing
training requires resolved model files to remain inside one model directory.
After validating each source file's SHA256 against pinned provenance, create
hardlinks (not 16 GB copies) under ignored work/ if needed, without overwrites.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = 'mlx-community/Qwen3.8-27B-4bit'
REVISION = '10c35caafbb80f7dc6a7a432cdd11af10a6d4818'
MODEL_NAME = 'models--mlx-community--Qwen3.8-27B-4bit'


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_dir(path, files):
    """Verify actual bytes/lengths; external symlinks allowed at source only."""
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError('No model directory: ' + str(path))
    for name, info in files.items():
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or len(rel.parts) != 1:
            raise ValueError('Unsafe provenance file name: ' + name)
        f = path / name
        if not f.is_file():
            raise ValueError('Missing pinned model file: ' + str(f))
        if f.stat().st_size != info['bytes']:
            raise ValueError('Pinned model size mismatch: ' + str(f))
        if sha_file(f) != info['sha256']:
            raise ValueError('Pinned model SHA256 mismatch: ' + str(f))
    return path


def contained_without_symlinks(path, files):
    return all((path / name).resolve().is_relative_to(path) for name in files)


def candidate_directories(root=ROOT, environ=None, home=None, explicit=None):
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if explicit:
        return [Path(explicit).expanduser()]
    candidates = []
    for name in ('QIMEN_27B_MODEL_DIR', 'QIMEN_MLX_MODEL_PATH'):
        if environ.get(name):
            candidates.append(Path(environ[name]).expanduser())
    hubs = [home/'.cache/huggingface/hub', home/'Library/Caches/huggingface/hub']
    for key in ('HUGGINGFACE_HUB_CACHE', 'HF_HUB_CACHE'):
        if environ.get(key):
            hubs.insert(0, Path(environ[key]).expanduser())
    if environ.get('HF_HOME'):
        hubs.insert(0, Path(environ['HF_HOME']).expanduser()/'hub')
    if environ.get('XDG_CACHE_HOME'):
        hubs.append(Path(environ['XDG_CACHE_HOME']).expanduser()/'huggingface/hub')
    for hub in hubs:
        snapshots = hub/MODEL_NAME/'snapshots'
        candidates.append(snapshots/REVISION)
        if snapshots.is_dir():
            candidates.extend(sorted(p for p in snapshots.iterdir() if p.is_dir()))
    work = root/'work'
    candidates.append(work/'qwen38-27b-pinned-v1')
    if work.is_dir():
        for parent in (work, work/'models', work/'model'):
            if parent.is_dir():
                candidates.extend(sorted(p for p in parent.iterdir()
                                         if p.is_dir() and ('27b' in p.name.lower() or 'qwen' in p.name.lower())))
    result, seen = [], set()
    for candidate in candidates:
        candidate = candidate.expanduser()
        if candidate not in seen:
            seen.add(candidate)
            if candidate.is_dir():
                result.append(candidate)
    return result


def materialize_verified_links(source, target, files):
    """Hardlink identical already-verified inodes; never replace a user file."""
    source = Path(source).resolve()
    target = Path(target).expanduser().absolute()
    if target == source:
        return source
    if target.is_symlink():
        raise ValueError('Refusing model target symlink: ' + str(target))
    if target.exists():
        if not target.is_dir():
            raise ValueError('Model target occupied: ' + str(target))
        verified = verify_dir(target, files)
        if not contained_without_symlinks(verified, files):
            raise ValueError('Existing target contains external symlinks: ' + str(target))
        return verified
    stage = target.with_name(target.name + '.partial')
    stage.mkdir(parents=True, exist_ok=True)
    if stage.is_symlink():
        raise ValueError('Refusing staging symlink')
    for name, info in files.items():
        existing = stage / name
        src = (source / name).resolve()
        if existing.exists() or existing.is_symlink():
            if (not existing.is_file() or existing.stat().st_size != info['bytes']
                    or sha_file(existing) != info['sha256']):
                raise ValueError('Existing staged file differs: ' + str(existing))
            continue
        try:
            os.link(src, existing)
        except OSError as exc:
            raise RuntimeError('Cannot hardlink model files on this volume; no weights copied. '
                               'Use a model directory with real files. Cause: ' + str(exc)) from exc
        if not os.path.samefile(src, existing):
            raise ValueError('Hardlink did not preserve inode: ' + name)
    if target.exists():
        raise FileExistsError('Model target created concurrently: ' + str(target))
    stage.rename(target)
    return target


def prepare(root=ROOT, explicit=None, output=None):
    root = Path(root).resolve()
    provenance = json.loads((root/'data/provenance/qwen38_27b_download_v1.json').read_text(encoding='utf-8'))
    if (provenance.get('repo') != REPO or provenance.get('revision') != REVISION
            or len(provenance.get('files', {})) < 15):
        raise ValueError('Unrecognized pinned base provenance')
    files = provenance['files']
    manifest = Path(output) if output else root/'work/mac-book-model-manifest-v1.json'
    if manifest.exists():
        recorded = json.loads(manifest.read_text(encoding='utf-8'))
        if (recorded.get('repo') != REPO or recorded.get('revision') != REVISION
                or recorded.get('files') != files):
            raise ValueError('Existing manifest identity differs; refusing overwrite: ' + str(manifest))
        directory = verify_dir(recorded['local_path'], files)
        if not contained_without_symlinks(directory, files):
            raise ValueError('Existing manifest points outside directory: ' + str(manifest))
        return {'status': 'existing_verified', 'manifest': str(manifest), 'model': str(directory), 'files': len(files)}
    options = candidate_directories(root=root, explicit=explicit)
    if not options:
        raise FileNotFoundError('Pinned 27B model not found in standard local directories. '
                                'Use --model-dir PATH pointing to your existing snapshot; no download made.')
    errors = []
    for candidate in options:
        try:
            source = verify_dir(candidate, files)
            break
        except (ValueError, OSError) as exc:
            errors.append({'directory': str(candidate), 'error': str(exc)[:300]})
    else:
        raise FileNotFoundError('No complete SHA-verified 27B model found. '
                                'Use --model-dir PATH if stored elsewhere. Checked: '
                                + json.dumps(errors[-8:]))
    directory = (source if contained_without_symlinks(source, files)
                 else materialize_verified_links(source, root/'work/qwen38-27b-pinned-v1', files))
    manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = {'repo': REPO, 'revision': REVISION, 'local_path': str(directory), 'files': files}
    try:
        with manifest.open('x', encoding='utf-8') as out:
            json.dump(payload, out, indent=2, ensure_ascii=False)
            out.write('\n')
    except FileExistsError:
        raise FileExistsError('Manifest appeared concurrently; rerun to verify')
    return {'status': 'created_verified', 'manifest': str(manifest), 'model': str(directory),
            'files': len(files), 'base_source': str(source), 'hardlinked': directory != source}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir', type=Path, help='Existing local MLX model directory if outside standard cache')
    p.add_argument('--manifest', type=Path, help='Private output; default work/mac-book-model-manifest-v1.json')
    args = p.parse_args()
    try:
        print(json.dumps(prepare(explicit=args.model_dir, output=args.manifest),
                         ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Model preparation BLOCKED (nothing downloaded or overwritten): {exc}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
