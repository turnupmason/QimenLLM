"""Explicit local development run; no downloads, network service or training."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import time

from qimenllm.contracts import Inquiry
from qimenllm.evaluation.research import ARMS, ResearchRequest, score, summarize_runs
from qimenllm.knowledge.db import digest
from qimenllm.models.mlx_gateway import MLXResearchGateway
from qimenllm.reasoning.service import QimenService


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--suite-sha256', required=True)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--model-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--disable-thinking', action='store_true')
    parser.add_argument('--adapter-path', type=Path)
    parser.add_argument('--arm', action='append', choices=ARMS)
    parser.add_argument('--memory-limit-bytes', type=int)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError('Keep previous experiment intact; select a new output path')
    if digest(args.suite.read_bytes()) != args.suite_sha256:
        raise ValueError('Suite hash mismatch')
    manifest = json.loads(args.model_manifest.read_bytes())
    for name, info in manifest['files'].items():
        path = args.model_path / name
        if not path.resolve().is_relative_to(args.model_path.resolve()):
            raise ValueError('Unsafe model manifest path')
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                h.update(block)
        if h.hexdigest() != info['sha256'] or path.stat().st_size != info['bytes']:
            raise ValueError('Local model file differs from pinned manifest: ' + name)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    suite = json.loads(args.suite.read_bytes())
    if args.memory_limit_bytes:
        import mlx.core as mx
        mx.set_memory_limit(args.memory_limit_bytes)
        mx.set_cache_limit(64*1024**2)
    model = MLXResearchGateway(args.model_path, revision=manifest['revision'],
                               enable_thinking=False if args.disable_thinking else None, adapter_path=args.adapter_path)
    service = QimenService(args.db, model=model)
    report = {'scope': suite['scope'], 'suite_sha256': args.suite_sha256,
              'data_version': suite['data_version'], 'source_commit': suite['source_commit'],
              'model': manifest, 'model_load_seconds': model.load_seconds,
              'python': platform.python_version(), 'platform': platform.platform(),
              'packages': {name: importlib.metadata.version(name) for name in
                           ('mlx', 'mlx-lm', 'transformers', 'tokenizers', 'safetensors')},
              'hardware': {key: subprocess.check_output(['sysctl', '-n', key], text=True).strip()
                           for key in ('hw.memsize', 'hw.model', 'machdep.cpu.brand_string')},
              'started_unix': time.time(), 'rows': [], 'training_performed': False,
              'network_inference': False, 'reserved_families_evaluated': 0}
    report['adapter'] = None if args.adapter_path is None else {
        'files': {name: digest((args.adapter_path / name).read_bytes())
                  for name in ('adapters.safetensors', 'adapter_config.json')}}
    root = Path(__file__).resolve().parents[1]
    report['code_sha256'] = {name: digest((root / name).read_bytes()) for name in (
        'scripts/run_mac_baseline.py', 'src/qimenllm/models/mlx_gateway.py',
        'src/qimenllm/evaluation/research.py', 'src/qimenllm/reasoning/service.py')}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive run directory prevents overwriting any previous run/checkpoint.
    args.output.mkdir()
    for task in suite['tasks']:
        for arm in (args.arm or ARMS):
            request = ResearchRequest(str(args.suite), args.suite_sha256, task['task_id'], arm)
            result = service.ask(Inquiry(task['question']), research=request)
            row = {'task_id': task['task_id'], 'family_id': task['family_id'], 'arm': arm,
                   'result': result, 'score': score(args.db, task, result)}
            report['rows'].append(row)
            (args.output / (task['task_id'] + '-' + arm + '.json')).write_text(
                json.dumps(row, ensure_ascii=False, indent=2) + '\n')
            print(task['task_id'], arm, result['status'], flush=True)
    report['summary'] = summarize_runs(report['rows'])
    if args.adapter_path is not None:
        report['summary']['finetuned_baseline']='measured_local_adapter_only'
    report['finished_unix'] = time.time()
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
