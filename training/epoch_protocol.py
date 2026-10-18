"""Small dependency-free training ledger: epochs count examples, never iterations."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def order_for_epoch(task_ids, epoch, seed=17):
    if len(set(task_ids))!=len(task_ids) or epoch<0:
        raise ValueError('Duplicate examples or invalid epoch')
    return sorted(task_ids,key=lambda t:hashlib.sha256(f'{seed}:{epoch}:{t}'.encode()).hexdigest())


def learning_rate(step, total, warmup, maximum=1e-4):
    if not 1<=step<=total or not 0<=warmup<total:
        raise ValueError('Invalid scheduler position')
    if step<=warmup:
        return maximum*step/max(1,warmup)
    progress=(step-warmup)/(total-warmup)
    return maximum*(.1+.9*.5*(1+math.cos(math.pi*progress)))


def validate_cursor(state, task_ids, epochs, seed=17):
    epoch,cursor,step=state['epoch'],state['cursor'],state['optimizer_step']
    if not 0<=epoch<=epochs or not 0<=cursor<len(task_ids):
        raise ValueError('Invalid epoch cursor')
    if epoch==epochs and cursor!=0:
        raise ValueError('Cursor after final epoch')
    if step!=epoch*len(task_ids)+cursor:
        raise ValueError('Step does not match complete passes and cursor')
    expected=order_for_epoch(task_ids,epoch,seed) if epoch<epochs else []
    if state['data_order']!=expected:
        raise ValueError('Shuffled order differs from deterministic release')


def verify_release(manifest_path, root):
    manifest=json.loads(Path(manifest_path).read_bytes());root=Path(root)
    if manifest.get('frozen') is not True:
        raise ValueError('Unfrozen dataset')
    owners={};tasks={}
    for split in ('train','validation','test','development'):
        name=split+'.jsonl';info=manifest['files'][name]
        if sha(root/name)!=info['sha256'] or (root/name).stat().st_size!=info['bytes']:
            raise ValueError('Dataset file changed')
        rows=[json.loads(line) for line in (root/name).read_text().splitlines()]
        if len(rows)!=info['tasks']:
            raise ValueError('Task count mismatch')
        for row in rows:
            family=row['family_id'];task=row['task_id']
            if task in tasks or row['split']!=split or manifest['family_assignments'][family]!=split:
                raise ValueError('Duplicate task or wrong split')
            if family in owners and owners[family]!=split:
                raise ValueError('Family leakage')
            owners[family]=split;tasks[task]=row
    if not any(r['split']=='train' for r in tasks.values()) or not any(r['split']=='validation' for r in tasks.values()):
        raise ValueError('Training and validation must be nonempty')
    return manifest,tasks
