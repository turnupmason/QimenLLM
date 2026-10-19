#!/usr/bin/env python3
"""Private, no-inference audit of QimenLLM epoch-05 loop symptoms and SFT targets.

Read only verified train/validation, cached training token lengths, and existing
paired generation reports. Never opens test.jsonl, prints historical text,
returns any task IDs, or changes training/config/checkpoint files.
The source-target audit does NOT prove model quality; semantic review remains.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import median
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from diagnose_mac_book_regression import compare, _load_receipt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dist(seq):
    vals=sorted(v for v in seq if isinstance(v,int))
    if not vals:return {'count':0}
    return {'count':len(vals),'min':vals[0],'median':median(vals),'max':vals[-1],
            'above_1536':sum(v>1536 for v in vals),
            'at_or_below_1536':sum(v<=1536 for v in vals)}


def loop_signals(raw):
    """Heuristic repeated text, does not assert that output is semantically a loop."""
    if not isinstance(raw,str):return {'raw_available':False,'tail40_occurrences':0,'exact_periodic_suffix':False}
    last40=raw[-40:] if len(raw)>=40 else ''
    tail40=raw.count(last40) if last40 else 0
    periodic=any(raw[-p:]==raw[-2*p:-p]==raw[-3*p:-2*p]
                 for p in range(4,min(160,len(raw)//3)+1))
    # Count repeated 40-char windows only inside the final 320 characters.
    window=raw[-320:]; pieces=[window[i:i+40] for i in range(max(0,len(window)-39))]
    most_common=max(Counter(pieces).values(),default=0)
    return {'raw_available':True,'tail40_occurrences':tail40,
            'exact_periodic_suffix':periodic,'max_tail_window_repeats':most_common}


def audit(before_path,after_path,manifest_path,data_dir,cache_path):
    # Reuse strict paired report identity/splits/adapter checks without touching models.
    paired=compare(before_path,after_path)
    before,b=_load_receipt(before_path,baseline=True)
    after,a=_load_receipt(after_path,baseline=False)
    manifest=json.loads(Path(manifest_path).read_bytes())
    receipt=json.loads(Path(cache_path).read_bytes())
    if (manifest.get('release_id')!='shenqi-book-method-curriculum-v1'
            or manifest.get('frozen') is not True
            or receipt.get('status')!='complete'
            or receipt.get('test_opened') is not False
            or receipt.get('optimizer_updates') != 0
            or sha(manifest_path)!=receipt.get('release_sha256')
            or receipt.get('release_sha256')!=after.get('data_manifest_sha256')
            or receipt.get('model_manifest_sha256')!=after.get('model_manifest_sha256')):
        raise ValueError('Frozen manifest/cache/paired report identity mismatch')
    meta={}
    for split in ('train','validation'):
        p=Path(data_dir)/(split+'.jsonl')
        if sha(p)!=manifest['files'][split+'.jsonl']['sha256']:
            raise ValueError('Frozen train/validation source bytes mismatch')
        for line in p.read_text(encoding='utf-8').splitlines():
            r=json.loads(line)
            if (r['split']!=split or r['task_id'] in meta
                    or manifest['family_assignments'].get(r['family_id'])!=split
                    or r['family_id'] in manifest['excluded_training_families']):
                raise ValueError('Split family mismatch')
            meta[r['task_id']]={'split':split,'type':r['task_type'],
                                'target':r['messages'][2]['content']}
    example_rows=receipt['examples']
    if len(example_rows)!=325 or len({x['task_id'] for x in example_rows})!=325 or set(meta)!={x['task_id'] for x in example_rows}:
        raise ValueError('Training cache not exactly 325 unique frozen tasks')
    target_all=defaultdict(list)
    feedback_targets=Counter()
    for e in example_rows:
        tid=e['task_id']
        t=meta[tid]
        if e['split']!=t['split']:
            raise ValueError('Cached split mismatch')
        length=len(e['input_ids'])-e['prefix']
        if length<1 or length>8192:
            raise ValueError('Invalid supervised answer token count')
        target_all[t['type']].append(length)
        if t['type']=='feedback_continuation':
            try:
                chart_action=json.loads(t['target']).get('chart_action')
            except (TypeError,ValueError,AttributeError):
                feedback_targets['invalid_target_json']+=1
            else:
                feedback_targets['explicit_reuse_original' if chart_action=='reuse_original' else 'missing_or_wrong_reuse_original']+=1
    causes={'before':Counter(),'after':Counter()}
    repet={'before':Counter(),'after':Counter()}
    token_lengths={'before':[],'after':[]}
    truncated_by_type=Counter()
    for stage,records in (('before',b),('after',a)):
        for row in records.values():
            if row['result']['status']!='generation_error':
                continue
            t=row['result'].get('telemetry') or {}
            if t.get('finish_reason')!='length':
                continue
            raw=t.get('raw_output')
            signals=loop_signals(raw)
            causes[stage]['truncations']+=1
            if signals['raw_available']:
                repet[stage]['raw_available']+=1
                repet[stage]['tail40_occurs_at_least_three']+=int(signals['tail40_occurrences']>=3)
                repet[stage]['exact_periodic_suffix']+=int(signals['exact_periodic_suffix'])
                repet[stage]['max_tail40_windows_at_least_three']+=int(signals.get('max_tail_window_repeats',0)>=3)
            if stage=='after':
                truncated_by_type[row['task_type']]+=1
            if isinstance(t.get('generation_tokens'),int):
                token_lengths[stage].append(t['generation_tokens'])
    return {
        'scope':'read_only_frozen_train_val_target_and_two_unsealed_generation_reports',
        'status':'diagnosed_not_model_acceptance',
        'sealed_test_file_opened':False,'model_loaded_or_training_run':False,
        'raw_user_case_text_or_generated_text_in_report':False,
        'complete_full_book_professional_pass':False,
        'protocol_success':paired['protocol_generated'],
        'truncation_generation_tokens':{stage:dist(token_lengths[stage]) for stage in ('before','after')},
        'truncation_repetition_heuristics':{stage:dict(repet[stage]) for stage in ('before','after')},
        'truncated_after_by_task_type':dict(sorted(truncated_by_type.items())),
        'supervised_answer_token_lengths':{
            'all_train_and_validation':dist(v for group in target_all.values() for v in group),
            'by_task_type':{k:dist(v) for k,v in sorted(target_all.items())},
        },
        'feedback_continuation_train_validation_target_field':dict(sorted(feedback_targets.items())),
        'caveats':[
            'Repeating a 40-character suffix is a heuristic and can be valid source quotations or JSON list formatting.',
            'Target length is from verified teacher-forced cache, not proof of successful autoregressive termination.',
            'Output cap increase or training hyperparameter changes require a new controlled experiment.',
            'Do not select a model using sealed test or training-set-only scores.',
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path,required=True)
    p.add_argument('--after',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=ROOT/'data/splits/book_method_curriculum_v1.json')
    p.add_argument('--data-dir',type=Path,default=ROOT/'work/book-method-curriculum-v1')
    p.add_argument('--cache-receipt',type=Path,default=ROOT/'work/book-method-curriculum-cache.json')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=audit(a.before,a.after,a.manifest,a.data_dir,a.cache_receipt)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'report':str(a.output),'training_target_lengths':result['supervised_answer_token_lengths'],
        'feedback_target_field':result['feedback_continuation_train_validation_target_field'],
        'truncation_repetition':result['truncation_repetition_heuristics'],
        'test_opened':False},ensure_ascii=False))


if __name__=='__main__':main()
