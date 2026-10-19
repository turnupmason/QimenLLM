#!/usr/bin/env python3
"""Matched, bounded MLX checkpoint probe on deterministic VALIDATION-only tasks.

First run --plan (no model). Then run --adapter-dir local epoch-01/02/03/04/05.
Stable 3 tasks per represented type; never opens test/dev/train JSONL. For
model choice, these are *validation diagnostics*, never independent final tests.
Reports stay local, raw answers never printed/uploaded to GitHub.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from epoch_protocol import sha
from qimenllm.evaluation.book_method import BookMethodRequest
from qimenllm.evaluation.method import score_task
from qimenllm.contracts import Inquiry

PROBE_ID = 'mac-book-checkpoint-probe-validation-v1'
SAMPLE_PER_TYPE = 3
EXPECTED_TYPES = ('chart_evidence','evidence_synthesis','feedback_continuation',
                  'role_selection','source_knowledge','timing_analysis')


def select_validation(manifest_path, data_dir):
    manifest = json.loads(Path(manifest_path).read_bytes())
    if manifest.get('frozen') is not True or manifest.get('release_id') != 'shenqi-book-method-curriculum-v1':
        raise ValueError('Only the pinned frozen book release is supported')
    p = Path(data_dir)/'validation.jsonl'
    if sha(p) != manifest['files']['validation.jsonl']['sha256']:
        raise ValueError('Validation bytes differ from the frozen release')
    groups = defaultdict(list)
    seen = set()
    for line in p.read_bytes().splitlines():
        row = json.loads(line)
        if (row['split'] != 'validation' or row['task_id'] in seen
                or manifest['family_assignments'].get(row['family_id']) != 'validation'
                or row['family_id'] in manifest['excluded_training_families']):
            raise ValueError('Duplicate task or family split leakage')
        seen.add(row['task_id'])
        groups[row['task_type']].append(row)
    if set(groups) != set(EXPECTED_TYPES):
        raise ValueError('Validation task types changed; cannot silently drop or add a domain')
    chosen = []
    for typ in EXPECTED_TYPES:
        vals = groups[typ]
        if len(vals) < SAMPLE_PER_TYPE:
            raise ValueError('Need 3 validation tasks per method type')
        vals.sort(key=lambda t: (hashlib.sha256((PROBE_ID+':'+t['task_id']).encode()).hexdigest(),t['task_id']))
        chosen.extend(vals[:SAMPLE_PER_TYPE])
    if len(chosen) != 18 or len({r['task_id'] for r in chosen}) != 18:
        raise ValueError('Probe must be exactly 18 independent task IDs, no duplicates')
    return manifest, chosen


def probe_identity(manifest_path, model_manifest_path, config_path, adapter_dir, chosen):
    base = json.loads(Path(model_manifest_path).read_bytes())
    cfg = json.loads(Path(config_path).read_bytes())
    if base['revision'] != cfg['base_revision'] or cfg['max_generation_tokens'] != 1536 or cfg['enable_thinking'] is not False:
        raise ValueError('Pinned comparison requires identical base/decoding settings')
    adapter_dir = Path(adapter_dir)
    if adapter_dir.name not in ('epoch-01','epoch-02','epoch-03','epoch-04','epoch-05'):
        raise ValueError('Only immutable first five epoch checkpoints may be evaluated')
    # Validates config/manifest/adapter hashes before evaluating any model.
    from run_mac_book_method import validate_adapter_identity
    adapter_info = validate_adapter_identity(adapter_dir,manifest_path,config_path,model_manifest_path)
    if adapter_info['epoch'] != int(adapter_dir.name.split('-')[1]):
        raise ValueError('Checkpoint epoch label differs')
    return {
        'probe_id':PROBE_ID,
        'config_sha256':sha(config_path),
        'model_manifest_sha256':sha(model_manifest_path),
        'data_manifest_sha256':sha(manifest_path),
        'base_revision':base['revision'],
        'adapter_checkpoint':adapter_dir.name,
        'adapter_state_sha256':adapter_info['state_sha256'],
        'script_sha256':sha(Path(__file__)),
        'gateway_sha256':sha(ROOT/'src/qimenllm/models/mlx_gateway.py'),
        'service_sha256':sha(ROOT/'src/qimenllm/reasoning/service.py'),
        'book_method_sha256':sha(ROOT/'src/qimenllm/evaluation/book_method.py'),
        'validation_task_ids_sha256':hashlib.sha256(json.dumps(
            [t['task_id'] for t in chosen],separators=(',',':')).encode()).hexdigest(),
        'generation_settings':{'max_tokens':1536,'thinking':False,'seed':17,'temperature':0.0},
        'split':'validation',
        'test_accessed':False,
    }, base,cfg


def _matched_old_report(path,identity,chosen):
    r=json.loads(Path(path).read_bytes())
    if (r.get('test_accessed') is not False
            or r.get('data_manifest_sha256')!=identity['data_manifest_sha256']
            or r.get('config_sha256')!=identity['config_sha256']
            or r.get('model_manifest_sha256')!=identity['model_manifest_sha256']
            or r.get('revision')!=identity['base_revision']
            or r.get('generation_settings')!={'max_tokens':1536,'thinking':False}):
        raise ValueError('Historical report is not comparable')
    data={x['task_id']:x for x in r['records']}
    result={}
    for row in chosen:
        old=data[row['task_id']]
        if (old['split']!='validation' or old['chapter']!=row['chapter']
                or old['task_type']!=row['task_type']):
            raise ValueError('Historical report task mismatch')
        result[row['task_id']]=old['result']['status']
    return result


def compare_subset(before,after,probe,chosen):
    def counter(v):return dict(sorted(Counter(v.values()).items()))
    types={}
    for typ in EXPECTED_TYPES:
        ids=[x['task_id'] for x in chosen if x['task_type']==typ]
        types[typ]={stage:sum(statuses[k]=='method_generated' for k in ids)
                    for stage,statuses in (('base',before),('epoch05',after),('probe',probe))}
    return {
        'counts':{stage:counter(statuses) for stage,statuses in
                  (('base',before),('epoch05',after),('probe',probe))},
        'success_by_task_type':types,
        'matched_validation_task_count':len(chosen),
        'scope':'unseen_validation_generated_protocol_only_not_semantic_quality',
        'test_opened':False,
        'final_professional_acceptance':False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',action='store_true',help='Verify deterministic validation subset; no MLX or model')
    p.add_argument('--manifest',type=Path,default=ROOT/'data/splits/book_method_curriculum_v1.json')
    p.add_argument('--data-dir',type=Path,default=ROOT/'work/book-method-curriculum-v1')
    p.add_argument('--config',type=Path,default=ROOT/'training/mac_book_curriculum_v1.json')
    p.add_argument('--model-manifest',type=Path,default=ROOT/'work/mac-book-model-manifest-v1.json')
    p.add_argument('--db',type=Path,default=ROOT/'work/demo.sqlite3')
    p.add_argument('--adapter-dir',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--base-report',type=Path,default=ROOT/'work/mac-book-method-before-v1/report.json')
    p.add_argument('--epoch05-report',type=Path,default=ROOT/'work/mac-book-method-after-epoch05-v1/report.json')
    args=p.parse_args()
    release,selected=select_validation(args.manifest,args.data_dir)
    if args.plan:
        print(json.dumps({'probe':PROBE_ID,'release':release['release_id'],
            'split':'validation','tasks':len(selected),
            'types':dict(sorted(Counter(r['task_type'] for r in selected).items())),
            'chapters_in_subset':len(set(r['chapter'] for r in selected)),
            'test_opened':False,'model_loaded':False},ensure_ascii=False))
        return
    if not args.adapter_dir or not args.output:
        p.error('--adapter-dir and --output are both required')
    identity,base,cfg=probe_identity(args.manifest,args.model_manifest,args.config,args.adapter_dir,selected)
    old_base=_matched_old_report(args.base_report,identity,selected)
    old_epoch05=_matched_old_report(args.epoch05_report,identity,selected)
    if args.output.exists():
        raise FileExistsError('A checkpoint probe output cannot overwrite or resume an existing experiment')
    for name,info in base['files'].items():
        f=Path(base['local_path'])/name
        if (not f.resolve().is_relative_to(Path(base['local_path']).resolve())
                or sha(f)!=info['sha256']):
            raise ValueError('Pinned local base model differs')
    args.output.mkdir(parents=True)
    # Only model inference here; no optimizer and no train/dev/test rows.
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    import mlx.core as mx
    from mlx.utils import tree_flatten
    from qimenllm.models.mlx_gateway import MLXResearchGateway
    from qimenllm.reasoning.service import QimenService
    mx.set_memory_limit(19_000_000_000)
    mx.set_cache_limit(64*1024**2)
    gateway=MLXResearchGateway(base['local_path'],revision=base['revision'],
                               max_tokens=1536,max_context_tokens=8192,
                               enable_thinking=False,adapter_path=args.adapter_dir)
    weights=mx.load(str(args.adapter_dir/'adapters.safetensors'))
    loaded=dict(tree_flatten(gateway.model.parameters()))
    if len(weights)!=2*len(cfg['target_modules']) or any(key not in loaded for key in weights):
        raise ValueError('Adapter tensor count/names incompatible')
    if max(float(mx.max(mx.abs(w-loaded[k])).item()) for k,w in weights.items())!=0:
        raise ValueError('Loaded adapter differs from exact saved weights')
    for mod in cfg['target_modules']:
        layer=gateway.model.language_model.model.layers[cfg['target_layer']]
        for part in mod.split('.'):layer=getattr(layer,part)
        if layer.scale!=cfg['scale']:raise ValueError('Loaded scale differs from frozen training')
    svc=QimenService(args.db,model=gateway)
    records=[]
    for i,t in enumerate(selected,1):
        result=svc.ask(Inquiry(t['task_id']),research=BookMethodRequest(
            str(args.manifest),sha(args.manifest),str(args.data_dir),'validation',t['task_id']))
        score=score_task(t,result)
        records.append({'task_id':t['task_id'],'chapter':t['chapter'],
                        'task_type':t['task_type'],'split':'validation',
                        'status':result['status'],'result':result,'score':score})
        print(json.dumps({'completed':i,'total':len(selected),
                          'type':t['task_type'],'status':result['status']}),flush=True)
    new={x['task_id']:x['status'] for x in records}
    comparison=compare_subset(old_base,old_epoch05,new,selected)
    report={**identity,'status':'complete_probe_not_semantic_acceptance',
            'scope':'single_checkpoint_small_validation_probe',
            'records':records,'comparison':comparison,'optimizer_updates':0,
            'final_professional_acceptance':False,'test_accessed':False,
            'all_case_chapters_independently_evaluated':False,'finished_unix':time.time()}
    # Keep private raw responses local only; do not upload work/ anywhere.
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'completed':len(records),'epoch':identity['adapter_checkpoint'],
        'comparison':comparison,'test_accessed':False},ensure_ascii=False))


if __name__=='__main__':main()
