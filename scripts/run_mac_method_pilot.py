"""Explicit local 27B method baseline, validation/development only; no training."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qimenllm.contracts import Inquiry
from qimenllm.evaluation.method import MethodRequest, score_task
from qimenllm.models.mlx_gateway import MLXResearchGateway
from qimenllm.reasoning.service import QimenService


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-path', type=Path, required=True)
    p.add_argument('--model-manifest', type=Path, required=True)
    p.add_argument('--data-dir', type=Path, default=ROOT/'work/lost-method-release-v5')
    p.add_argument('--manifest', type=Path, default=ROOT/'data/splits/lost_method_release_v5.json')
    p.add_argument('--db', type=Path, default=ROOT/'work/demo.sqlite3')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--adapter-path', type=Path)
    p.add_argument('--split', action='append', choices=('development', 'validation'))
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError('Keep prior runs immutable')
    metadata = json.loads(a.model_manifest.read_bytes())
    if (metadata['repo'] != 'mlx-community/Qwen3.8-27B-4bit'
            or metadata['revision'] != '10c35caafbb80f7dc6a7a432cdd11af10a6d4818'):
        raise ValueError('Only the pinned user-selected local 27B')
    for name, info in metadata['files'].items():
        path = a.model_path/name
        if not path.resolve().is_relative_to(a.model_path.resolve()):
            raise ValueError('Unsafe model file path')
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024*1024), b''):
                h.update(block)
        if h.hexdigest() != info['sha256'] or path.stat().st_size != info['bytes']:
            raise ValueError('Local model bytes changed: '+name)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    import mlx.core as mx
    mx.set_memory_limit(19_000_000_000)
    mx.set_cache_limit(64*1024**2)
    release_raw = a.manifest.read_bytes()
    release = json.loads(release_raw)
    todo = []
    for split in a.split or ('development', 'validation'):
        raw = (a.data_dir/(split+'.jsonl')).read_bytes()
        if sha(raw) != release['files'][split+'.jsonl']['sha256']:
            raise ValueError('Frozen method split changed')
        todo.extend((split, json.loads(line)) for line in raw.splitlines())
    a.output.mkdir(parents=True)
    gateway = MLXResearchGateway(a.model_path, revision=metadata['revision'], max_tokens=768,
                                 max_context_tokens=8192, enable_thinking=False, adapter_path=a.adapter_path)
    service = QimenService(a.db, model=gateway)
    report = {'scope': 'source_conditioned_27b_method_baseline_not_full_system_D',
        'model': metadata['repo'], 'revision': metadata['revision'],
        'model_manifest_sha256': sha(a.model_manifest.read_bytes()),
        'data_manifest_sha256': sha(release_raw), 'source_data_version': release['source_data_version'],
        'code_sha256': {name: sha((ROOT/name).read_bytes()) for name in
             ('scripts/run_mac_method_pilot.py', 'src/qimenllm/models/mlx_gateway.py',
              'src/qimenllm/evaluation/method.py', 'src/qimenllm/reasoning/service.py')},
        'packages': {name: importlib.metadata.version(name) for name in ('mlx', 'mlx-lm', 'transformers')},
        'model_load_seconds': gateway.load_seconds, 'started_unix': time.time(), 'records': [],
        'training_updates': 0, 'test_accessed': False, 'network_inference': False,
        'adapter': None if a.adapter_path is None else {
            name: sha((a.adapter_path/name).read_bytes()) for name in ('adapters.safetensors', 'adapter_config.json')},
        'author_method_accuracy': None, 'reported_feedback_accuracy': None,
        'independent_real_world_accuracy': None}
    for split, task in todo:
        print(json.dumps({'task': task['task_id'], 'type': task['task_type'], 'split': split, 'status': 'running'}), flush=True)
        result = service.ask(Inquiry(task['task_id']), research=MethodRequest(str(a.manifest),
            sha(release_raw), str(a.data_dir), split, task['task_id']))
        record = {'split': split, 'task_id': task['task_id'], 'task_type': task['task_type'],
                  'result': result, 'score': score_task(task, result)}
        (a.output/(task['task_id']+'.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
        report['records'].append(record)
        (a.output/'progress.json').write_text(json.dumps({'completed': len(report['records']), 'total': len(todo),
            'last_task': task['task_id'], 'last_status': result['status']}, ensure_ascii=False)+'\n')
        print(json.dumps({'completed': len(report['records']), 'status': result['status'],
                          'seconds': result.get('telemetry', {}).get('seconds')}, ensure_ascii=False), flush=True)
    report['completion_counts'] = dict(Counter(r['result']['status'] for r in report['records']))
    report['finished_unix'] = time.time()
    (a.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report['completion_counts'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
