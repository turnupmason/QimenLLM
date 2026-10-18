"""Small, real 27B method LoRA pilot on Apple Silicon, separate from retired quote run.

Only train/validation are opened. Frozen layers 0..62 are cached exactly; LoRA is
restricted to q/v in full-attention layer 63. Cache/full-forward and resumed-next-
update equivalence must pass before any official training update. This is not
full-system training or a claim of professional prediction capability.
"""
import argparse
import gc
import json
import math
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from cuda_pilot import encode_example, rows, load_config
from epoch_protocol import order_for_epoch, learning_rate, sha


def json_write(path, value):
    path = Path(path)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    tmp.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-manifest', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--resume', type=Path)
    a = p.parse_args()
    c = load_config(ROOT/'training/lost_4090_pilot.json')
    baseline = json.loads(a.baseline.read_bytes())
    model_info = json.loads(a.model_manifest.read_bytes())
    if (baseline['data_manifest_sha256'] != sha(ROOT/c['manifest'])
            or baseline['revision'] != model_info['revision'] or baseline.get('adapter')
            or {r['task_id'] for r in baseline['records'] if r['split']=='validation'} !=
               {r['task_id'] for r in rows(c, 'validation')}
            or baseline['training_updates'] != 0 or baseline['test_accessed']):
        raise ValueError('Complete matching unadapted validation baseline required')
    if a.output.exists() and a.resume is None:
        raise FileExistsError('Keep completed/partial runs; resume explicitly')
    if a.resume and not a.resume.resolve().is_relative_to(a.output.resolve()):
        raise ValueError('Only local checkpoints from this run may be resumed')
    a.output.mkdir(parents=True, exist_ok=True)
    model_path = Path(model_info['local_path'])
    if model_info['revision'] != '10c35caafbb80f7dc6a7a432cdd11af10a6d4818':
        raise ValueError('Unexpected model revision')
    for name, meta in model_info['files'].items():
        path = model_path/name
        if not path.resolve().is_relative_to(model_path.resolve()) or sha(path) != meta['sha256']:
            raise ValueError('Pinned local model changed')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten, tree_unflatten
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask, create_ssm_mask
    from mlx_lm.tuner.lora import LoRALinear
    from mlx_tail import make_tail, tail_loss, restore_mlx_rng
    mx.set_memory_limit(19_000_000_000); mx.set_cache_limit(64*1024**2)
    mx.random.seed(17); random.seed(17)
    report = {'scope': 'source_conditioned_method_lora_mac_pilot', 'status': 'loading',
        'release_id': 'shenqi-lost-method-tasks-v5', 'release_sha256': sha(ROOT/c['manifest']),
        'model': model_info['repo'], 'model_revision': model_info['revision'],
        'baseline_sha256': sha(a.baseline), 'epochs_cap': 3, 'validation_patience': 1,
        'learning_rate': 1e-4, 'rank': 4, 'scale': 2, 'dropout': 0,
        'target_modules': ['layers.63.self_attn.q_proj', 'layers.63.self_attn.v_proj'],
        'batch_size': 1, 'completed_epochs': 0, 'optimizer_steps': 0,
        'truncate': False, 'drop_last': False, 'test_accessed': False,
        'author_method_accuracy': None, 'reported_feedback_accuracy': None,
        'independent_real_world_accuracy': None,
        'code_sha256': {str(path.relative_to(ROOT)): sha(path) for path in
            (Path(__file__), ROOT/'training/mlx_tail.py', ROOT/'training/cuda_pilot.py')},
        'started_unix': time.time(), 'log': []}
    def log(stage, **kw):
        report['log'].append({'stage': stage, 'unix': time.time(), **kw})
        json_write(a.output/'progress.json', report)
        print(json.dumps({'stage': stage, **kw}, ensure_ascii=False), flush=True)
    try:
        model, tok = load(str(model_path), trust_remote_code=False, tokenizer_config={'trust_remote_code': False})
        model.eval(); model.freeze(); mx.eval(model.parameters())
        tokenized = {s: [encode_example(tok, t, 8192) for t in rows(c, s)] for s in ('train', 'validation')}
        json_write(a.output/'tokens.json', tokenized)
        report['tokenized_sha256'] = sha(a.output/'tokens.json')
        base = model.language_model.model
        if len(base.layers) != 64 or base.layers[-1].is_linear:
            raise ValueError('Expected 64-layer hybrid with final full attention')
        tail = make_tail(base.layers[-1], base.norm, model.language_model.lm_head)
        cache = a.output/'frozen-prefix-cache'; cache.mkdir(exist_ok=True)
        index = {}
        old = json.loads((a.output/'cache-index.json').read_bytes()) if a.resume else {}
        longest = max(tokenized['train'], key=lambda r: len(r['input_ids']))
        ordered = [longest]+[r for r in tokenized['train']+tokenized['validation']
                             if r['task_id'] != longest['task_id']]
        for i, row in enumerate(ordered):
            ids = mx.array([row['input_ids'][:-1]]); labels = mx.array([row['input_ids'][1:]])
            if i == 0:
                # Full original 64-layer forward, then slice only the tokenwise
                # head. Identical target logits without allocating prompt logits.
                full_hidden = base(ids)
                full_logits = model.language_model.lm_head(full_hidden[:, row['prefix']-1:, :])
                loss = nn.losses.cross_entropy(full_logits.astype(mx.float32),
                                               labels[:, row['prefix']-1:], reduction='mean')
                mx.eval(loss); reference = float(loss.item())
                del full_hidden, full_logits, loss; mx.clear_cache()
            path = cache/(row['task_id']+'.safetensors')
            started = time.monotonic()
            if not path.exists():
                h = base.embed_tokens(ids)
                fa, ssm = create_attention_mask(h, None), create_ssm_mask(h, None)
                for layer in base.layers[:-1]:
                    h = layer(h, mask=ssm if layer.is_linear else fa); mx.eval(h)
                h = mx.stop_gradient(h); mx.eval(h)
                mx.save_safetensors(str(path), {'hidden': h, 'labels': labels})
            elif a.resume and row['task_id'] in old and sha(path) == old[row['task_id']]['sha256']:
                h = mx.load(str(path))['hidden']
            else:
                raise ValueError('Unverified existing prefix cache')
            index[row['task_id']] = {'sha256': sha(path), 'prefix': row['prefix'],
                'target_tokens': len(row['input_ids'])-row['prefix'], 'tokens': len(row['input_ids'])}
            if i == 0:
                v = tail_loss(tail, h, labels, row['prefix']); mx.eval(v)
                delta = abs(float(v.item())-reference)
                if delta > 1e-5:
                    raise ValueError('Real method sample full/cached forward differs')
                report['full_cached_loss_delta'] = delta
                log('full_27b_method_cache_equivalence_passed', loss_delta=delta, reference_nll=reference)
                del v
            log('cached_task', completed=i+1, total=len(ordered), task_id=row['task_id'],
                tokens=len(row['input_ids']), seconds=time.monotonic()-started)
            del h, ids, labels; mx.clear_cache()
        json_write(a.output/'cache-index.json', index)
        del layer, base, model; gc.collect(); mx.clear_cache()
        log('frozen_prefix_unloaded', active_bytes=mx.get_active_memory())
        def datum(task_id):
            path = cache/(task_id+'.safetensors')
            if sha(path) != index[task_id]['sha256']:
                raise ValueError('Cache changed')
            data = mx.load(str(path))
            return data['hidden'], data['labels'], index[task_id]['prefix']
        def evaluate(split):
            numerator, denominator = 0.0, 0
            for row in tokenized[split]:
                h, labels, prompt = datum(row['task_id'])
                loss = tail_loss(tail, h, labels, prompt); mx.eval(loss)
                n = index[row['task_id']]['target_tokens']
                numerator += float(loss.item())*n; denominator += n
                del h, labels, loss; mx.clear_cache()
            return numerator/denominator
        intrinsic = {s: evaluate(s) for s in ('train', 'validation')}
        json_write(a.output/'intrinsic-baseline.json', intrinsic)
        tail.last.self_attn.update_modules({key: LoRALinear.from_base(getattr(tail.last.self_attn, key),
            r=4, scale=2, dropout=0) for key in ('q_proj', 'v_proj')})
        tail.eval(); mx.eval(tail.trainable_parameters())
        report['trainable_parameters'] = sum(v.size for _, v in tree_flatten(tail.trainable_parameters()))
        initial = {k: mx.array(v) for k, v in tree_flatten(tail.trainable_parameters())}; mx.eval(initial)
        optimizer = optim.AdamW(learning_rate=1e-4, weight_decay=.01)
        value_grad = nn.value_and_grad(tail, tail_loss)
        train_ids = [r['task_id'] for r in tokenized['train']]
        total_steps = 3*len(train_ids)
        identity = sha(a.output/'tokens.json')+sha(a.output/'cache-index.json')+report['release_sha256']
        identity += json.dumps(report['code_sha256'], sort_keys=True)
        def save(name, state):
            dest = a.output/name
            if dest.exists():
                raise FileExistsError('Immutable checkpoint')
            stage = dest.with_name(dest.name+'.partial'); stage.mkdir()
            mx.save_safetensors(str(stage/'tail-adapters.safetensors'), dict(tree_flatten(tail.trainable_parameters())))
            weights = {k.replace('last.', 'language_model.model.layers.63.', 1): v
                       for k, v in tree_flatten(tail.trainable_parameters())}
            mx.save_safetensors(str(stage/'adapters.safetensors'), weights)
            json_write(stage/'adapter_config.json', {'num_layers': 1, 'fine_tune_type': 'lora',
                'lora_parameters': {'rank': 4, 'scale': 2.0, 'dropout': 0.0,
                                    'keys': ['self_attn.q_proj', 'self_attn.v_proj']}})
            mx.savez(str(stage/'optimizer.npz'), **dict(tree_flatten(optimizer.state)))
            mx.savez(str(stage/'rng.npz'), mlx_key=mx.random.state[0])
            json_write(stage/'state.json', {**state, 'identity': identity, 'python_rng': random.getstate(),
                'scheduler': {'kind': 'warmup_cosine', 'total': total_steps, 'warmup': len(train_ids)},
                'files': {f.name: sha(f) for f in stage.iterdir() if f.is_file()}})
            stage.rename(dest)
            return dest
        def restore(dest):
            state = json.loads((dest/'state.json').read_bytes())
            if state['identity'] != identity:
                raise ValueError('Model/data/code identity differs')
            for name, digest in state['files'].items():
                if sha(dest/name) != digest:
                    raise ValueError('Checkpoint changed')
            tail.load_weights(str(dest/'tail-adapters.safetensors'), strict=False)
            optimizer.state = tree_unflatten(list(mx.load(str(dest/'optimizer.npz')).items()))
            restore_mlx_rng(mx.load(str(dest/'rng.npz'))['mlx_key'])
            def tuples(v):
                return tuple(tuples(x) for x in v) if isinstance(v, list) else v
            random.setstate(tuples(state['python_rng']))
            mx.eval(tail.trainable_parameters(), optimizer.state)
            if int(optimizer.step.item()) != state['optimizer_step']:
                raise ValueError('Optimizer cursor differs')
            return state
        def step(task_id, number):
            h, labels, prompt = datum(task_id)
            loss, grads = value_grad(tail, h, labels, prompt)
            grads, _ = optim.clip_grad_norm(grads, 1.0)
            optimizer.learning_rate = learning_rate(number, total_steps, len(train_ids))
            optimizer.update(tail, grads); mx.eval(loss, tail.trainable_parameters(), optimizer.state)
            value = float(loss.item())
            if not math.isfinite(value) or any(not bool(mx.all(mx.isfinite(v)).item())
                    for _, v in tree_flatten(tail.trainable_parameters())):
                raise ValueError('Nonfinite update')
            del h, labels, loss, grads; mx.clear_cache()
            return value
        state = {'epoch': 0, 'cursor': 0, 'optimizer_step': 0, 'data_order': order_for_epoch(train_ids, 0),
                 'best_validation_nll': intrinsic['validation'], 'best_checkpoint': None, 'bad_epochs': 0}
        if a.resume:
            state = restore(a.resume)
        else:
            probe_ids = [r['task_id'] for r in sorted(tokenized['train'],
                         key=lambda r: len(r['input_ids']), reverse=True)[:2]]
            step(probe_ids[0], 1)
            probe = save('resume-probe', {**state, 'cursor': 1, 'optimizer_step': 1})
            reference_loss = step(probe_ids[1], 2)
            expected = {k: mx.array(v) for k, v in tree_flatten(tail.trainable_parameters())}; mx.eval(expected)
            restore(probe)
            resumed_loss = step(probe_ids[1], 2)
            actual = dict(tree_flatten(tail.trainable_parameters()))
            delta = max(float(mx.max(mx.abs(v-actual[k])).item()) for k, v in expected.items())
            if abs(reference_loss-resumed_loss) > 1e-6 or delta > 1e-6:
                raise ValueError('Actual method-task save/resume next update differs')
            report['resume_adapter_delta'] = delta
            report['resume_loss_delta'] = abs(reference_loss-resumed_loss)
            log('real_method_resume_equivalence_passed', adapter_delta=delta, loss_delta=abs(reference_loss-resumed_loss))
            tail.update(tree_unflatten(list(initial.items())))
            optimizer = optim.AdamW(learning_rate=1e-4, weight_decay=.01)
            mx.random.seed(17); random.seed(17); mx.eval(tail.trainable_parameters())
        report['status'] = 'training'
        while state['epoch'] < 3:
            for cursor in range(state['cursor'], len(train_ids)):
                task_id = state['data_order'][cursor]
                loss = step(task_id, state['optimizer_step']+1)
                state['cursor'] = cursor+1; state['optimizer_step'] += 1
                report['optimizer_steps'] = state['optimizer_step']
                save(f'step-{state["optimizer_step"]:04d}', state)
                log('optimizer_update', epoch=state['epoch']+1, cursor=cursor+1,
                    optimizer_step=state['optimizer_step'], task_id=task_id, loss=loss)
            validation = evaluate('validation')
            improved = validation < state['best_validation_nll']-.001
            state['epoch'] += 1; state['cursor'] = 0
            name = f'epoch-{state["epoch"]:02d}'
            if improved:
                state['best_validation_nll'] = validation; state['best_checkpoint'] = name
            state['bad_epochs'] = 0 if improved else state['bad_epochs']+1
            state['data_order'] = order_for_epoch(train_ids, state['epoch']) if state['epoch'] < 3 else []
            save(name, state)
            report['completed_epochs'] = state['epoch']; report['best_checkpoint'] = state['best_checkpoint']
            log('epoch_complete', epoch=state['epoch'], validation_nll=validation,
                improved=improved, checkpoint=name)
            if state['bad_epochs'] >= 1:
                break
        report.update(status='pilot_training_complete', final_state=state, finished_unix=time.time(),
            peak_memory_bytes=mx.get_peak_memory(), semantic_selection_complete=False,
            note='Validation NLL chooses a candidate only; compare generated methods before scaling to GPU.')
        json_write(a.output/'report.json', report)
        log('pilot_complete', epochs=state['epoch'], optimizer_steps=state['optimizer_step'],
            candidate=state['best_checkpoint'])
    except BaseException as exc:
        report.update(status='failed', error_type=type(exc).__name__)
        json_write(a.output/'progress.json', report)
        raise


if __name__ == '__main__':
    main()
