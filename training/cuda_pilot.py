"""User-operated RTX4090 research pilot. No model imports before explicit GPU work.

prepare/audit are CPU-only. Training reads train+validation ONLY. Test generation
requires a previously frozen selection receipt. Every evaluation uses ask().
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from method_release import build as method_build, encoded, sha
from book_release import export as book_export
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.evaluation.method import ARMS, MethodRequest, messages_for, score_task
from qimenllm.reasoning.service import QimenService
from qimenllm.contracts import Inquiry, GenerationError


def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(encoded(data))


def load_config(path):
    c = json.loads(Path(path).read_bytes())
    if (c['model'] != 'Qwen/Qwen3.8-27B' or c['revision'] != '1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'
            or c['license'] != 'apache-2.0' or c['rank'] <= 0 or c['max_epochs'] <= 0
            or c['gradient_accumulation'] <= 0 or c['max_context'] <= 0):
        raise ValueError('Unsupported or invalid pinned pilot configuration')
    return c


def fingerprint(c):
    # Source code, config and dataset are checkpoint compatibility boundaries.
    paths = [Path(__file__), ROOT/'src/qimenllm/evaluation/method.py',
             ROOT/'src/qimenllm/reasoning/service.py', ROOT/c['manifest']]
    return sha(encoded({'config': c, 'files': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}}))


def require_mac_method_review(c):
    name = c.get('mac_quality_report')
    path = ROOT/name if name else None
    if path is None or not path.is_file():
        raise ValueError('Mac source-based method review must pass before CUDA training')
    report = json.loads(path.read_bytes())
    if (report.get('mac_limited_method_review_pass') is not True or report.get('test_accessed') is not False
            or report.get('model') != 'mlx-community/Qwen3.8-27B-4bit'
            or report.get('revision') != '10c35caafbb80f7dc6a7a432cdd11af10a6d4818'
            or report.get('data_manifest_sha256') != sha((ROOT/c['manifest']).read_bytes())):
        raise ValueError('Mac method/source review is incomplete or failed; no CUDA training started')
    if c.get('systematic_training') and report.get('systematic_training_ready') is not True:
        raise ValueError('Full-system training gates remain incomplete')
    return {'path': str(name), 'sha256': sha(path.read_bytes()), 'limited_method_pass': True,
            'systematic_training_ready': report.get('systematic_training_ready', False)}


def rows(c, split):
    m = json.loads((ROOT/c['manifest']).read_bytes())
    name = split + '.jsonl'
    raw = (ROOT/c['data_dir']/name).read_bytes()
    if sha(raw) != m['files'][name]['sha256']:
        raise ValueError('Frozen split bytes changed')
    result = [json.loads(line) for line in raw.splitlines()]
    for r in result:
        if r['split'] != split or m['family_assignments'][r['family_id']] != split:
            raise ValueError('Cross-family leakage')
    return result


def prepare(c):
    db = ROOT/c['db']
    if not db.exists():
        restore_snapshot(ROOT/'data/snapshots/current', db, ROOT/'work/restored-raw')
    tasks, _ = method_build(db,
        json.loads((ROOT/'data/structured/shenqi/lost_method_task_review_v5.json').read_bytes()),
        json.loads((ROOT/'data/splits/author_initial_release_v2.json').read_bytes()))
    release = json.loads((ROOT/c['manifest']).read_bytes())
    output = ROOT/c['data_dir']
    output.mkdir(parents=True, exist_ok=True)
    for split in ('train', 'validation', 'test', 'development'):
        raw = b''.join(encoded(t) for t in tasks if t['split'] == split)
        if sha(raw) != release['files'][split+'.jsonl']['sha256']:
            raise ValueError('Rebuild differs from frozen chapter release')
        path = output/(split+'.jsonl')
        if path.exists() and path.read_bytes() != raw:
            raise ValueError('Refuse to overwrite changed local tasks')
        if not path.exists():
            path.write_bytes(raw)
    # Rebuild all 98 complete story archives and safe chart tasks; compare every byte.
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp:
        tmp = Path(tmp)
        report = book_export(db, ROOT/'data/structured/shenqi/lost_method_task_review_v5.json',
            ROOT/'data/splits/author_initial_release_v2.json', tmp/'book', tmp/'manifest.json')
        if (tmp/'manifest.json').read_bytes() != (ROOT/'data/splits/book_preparation_v1.json').read_bytes():
            raise ValueError('Whole-book rebuild differs from frozen manifest')
        dest = ROOT/'work/book-preparation-v1'
        if dest.exists():
            for name, meta in report['files'].items():
                if sha((dest/name).read_bytes()) != meta['sha256']:
                    raise ValueError('Whole-book output changed')
        else:
            shutil.copytree(tmp/'book', dest)
    return {'status': 'data_rebuilt_and_hash_verified', 'all_cases': 98,
            'pilot_tasks': len(tasks), 'split_counts': dict(Counter(t['split'] for t in tasks)),
            'whole_book_tasks': sum(report['task_counts'].values()), 'fingerprint': fingerprint(c)}


def encode_example(tokenizer, task, maximum):
    messages = task['messages']
    prefix = tokenizer.apply_chat_template(messages[:2], tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False)
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False,
                                         enable_thinking=False)
    pids = tokenizer.encode(prefix, add_special_tokens=False)
    ids = tokenizer.encode(text, add_special_tokens=False)
    if ids[:len(pids)] != pids or len(ids) <= len(pids):
        raise ValueError('Assistant token boundary is not an exact prefix')
    if len(ids) > maximum:
        raise ValueError('Full task exceeds context; truncation is forbidden')
    return {'input_ids': ids, 'prefix': len(pids), 'task_id': task['task_id']}


def torch_loss(model, example):
    import torch
    ids = torch.tensor([example['input_ids']], device=next(model.parameters()).device)
    positions = torch.arange(example['prefix']-1, ids.shape[1]-1, device=ids.device)
    # Avoid allocating vocabulary logits for masked prompt tokens. All response
    # tokens, including the exact template terminator, contribute to the loss.
    output = model(input_ids=ids, use_cache=False, logits_to_keep=positions)
    target = ids[:, example['prefix']:]
    return torch.nn.functional.cross_entropy(output.logits.float().reshape(-1, output.logits.shape[-1]),
                                             target.reshape(-1)), target.numel()


def cuda_model(c, adapter=None, trainable=True):
    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError('One actual CUDA GPU required; no CPU/Mac fallback')
    props = torch.cuda.get_device_properties(0)
    if '4090' not in props.name or not torch.cuda.is_bf16_supported():
        raise RuntimeError('This configuration requires the user-reported RTX4090 with BF16')
    from transformers import AutoConfig, AutoTokenizer, AutoModelForImageTextToText, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
    cfg = AutoConfig.from_pretrained(c['model'], revision=c['revision'], trust_remote_code=False)
    if cfg.model_type != 'qwen3_5' or cfg.text_config.num_hidden_layers != 64:
        raise ValueError('Pinned model architecture differs from reviewed hybrid model')
    tok = AutoTokenizer.from_pretrained(c['model'], revision=c['revision'], trust_remote_code=False)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForImageTextToText.from_pretrained(c['model'], revision=c['revision'],
        trust_remote_code=False, dtype=torch.bfloat16, attn_implementation='sdpa', device_map={'': 0},
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
    if trainable:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                    gradient_checkpointing_kwargs={'use_reentrant': False})
        # k-bit preparation upcasts frozen large embeddings/output heads. Return
        # these to BF16 while keeping small normalization/state parameters FP32.
        for module in (model.get_input_embeddings(), model.get_output_embeddings()):
            module.to(dtype=torch.bfloat16)
    matches = [name for name, _ in model.named_modules() if re.fullmatch(c['target_modules'], name)]
    if not matches or any('visual' in name for name in matches):
        raise ValueError('No reviewed text-only adapter sites')
    if adapter:
        model = PeftModel.from_pretrained(model, str(adapter), is_trainable=trainable)
    else:
        model = get_peft_model(model, LoraConfig(r=c['rank'], lora_alpha=c['alpha'],
            lora_dropout=c['dropout'], target_modules=c['target_modules'], bias='none'))
    model.config.use_cache = False
    return model, tok, {'gpu': props.name, 'vram_bytes': props.total_memory,
        'cuda': torch.version.cuda, 'adapter_sites': matches,
        'trainable_parameters': sum(p.numel() for p in model.parameters() if p.requires_grad),
        'packages': {p: importlib.metadata.version(p) for p in
                     ('torch', 'transformers', 'peft', 'accelerate', 'bitsandbytes', 'safetensors')}}


def save_checkpoint(path, model, optimizer, scheduler, state, identity):
    import torch
    path = Path(path)
    if path.exists():
        raise FileExistsError('Checkpoint is immutable')
    stage = path.with_name(path.name+'.partial')
    stage.mkdir(parents=True)
    model.save_pretrained(stage/'adapter', safe_serialization=True)
    torch.save({'optimizer': optimizer.state_dict(), 'scheduler': scheduler.state_dict(),
                'rng_python': random.getstate(), 'rng_torch': torch.get_rng_state(),
                'rng_cuda': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                'state': state, 'fingerprint': identity}, stage/'state.pt')
    files = {str(p.relative_to(stage)): sha(p.read_bytes()) for p in stage.rglob('*') if p.is_file()}
    (stage/'receipt.json').write_bytes(encoded({'fingerprint': identity, 'state': state, 'files': files}))
    stage.rename(path)


def checkpoint_receipt(path, identity):
    path = Path(path)
    receipt = json.loads((path/'receipt.json').read_bytes())
    if receipt['fingerprint'] != identity:
        raise ValueError('Checkpoint config/code/data changed')
    for name, digest in receipt['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or sha((path/name).read_bytes()) != digest:
            raise ValueError('Checkpoint content changed')
    return receipt


def restore_checkpoint(path, model, optimizer, scheduler, identity):
    import torch
    from peft import set_peft_model_state_dict
    from safetensors.torch import load_file
    checkpoint_receipt(path, identity)
    # Only this locally generated, integrity-checked checkpoint is trusted for
    # optimizer/RNG deserialization. Never use downloaded arbitrary .pt files.
    saved = torch.load(Path(path)/'state.pt', map_location='cpu', weights_only=False)
    set_peft_model_state_dict(model, load_file(str(Path(path)/'adapter/adapter_model.safetensors')))
    optimizer.load_state_dict(saved['optimizer'])
    scheduler.load_state_dict(saved['scheduler'])
    random.setstate(saved['rng_python'])
    torch.set_rng_state(saved['rng_torch'])
    if saved['rng_cuda']:
        torch.cuda.set_rng_state_all(saved['rng_cuda'])
    return saved['state']


def preflight(c, run):
    import torch
    random.seed(c['seed']); torch.manual_seed(c['seed']); torch.cuda.manual_seed_all(c['seed'])
    model, tok, hardware = cuda_model(c)
    examples = [encode_example(tok, t, c['max_context']) for t in rows(c, 'train')]
    val = [encode_example(tok, t, c['max_context']) for t in rows(c, 'validation')]
    longest = max(examples, key=lambda e: len(e['input_ids']))
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=c['learning_rate'])
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.0)
    model.train()
    loss, _ = torch_loss(model, longest)
    loss.backward(); optimizer.step(); optimizer.zero_grad(); scheduler.step()
    identity = fingerprint(c)
    save_checkpoint(run/'preflight-checkpoint', model, optimizer, scheduler,
                    {'epoch': 0, 'cursor': 1, 'order': [longest['task_id']], 'optimizer_steps': 1}, identity)
    def next_update():
        loss, _ = torch_loss(model, longest)
        loss.backward(); optimizer.step(); optimizer.zero_grad(); scheduler.step()
        return float(loss.detach()), {n: p.detach().cpu().clone() for n, p in model.named_parameters() if p.requires_grad}
    before, expected = next_update()
    restore_checkpoint(run/'preflight-checkpoint', model, optimizer, scheduler, identity)
    after, actual = next_update()
    max_delta = max(float((actual[n]-expected[n]).abs().max()) for n in expected)
    if abs(before-after) > 1e-5 or max_delta > 1e-5:
        raise RuntimeError('Actual-context optimizer/RNG resume equivalence failed')
    report = {'status': 'passed', 'scope': 'real_cuda_full_training_context_and_resume',
        'fingerprint': identity, 'hardware': hardware, 'loss_before_resume': before,
        'loss_after_resume': after, 'maximum_adapter_delta': max_delta,
        'max_train_tokens': max(len(e['input_ids']) for e in examples),
        'max_validation_tokens': max(len(e['input_ids']) for e in val),
        'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
        'peak_reserved_bytes': torch.cuda.max_memory_reserved(), 'official_training_updates': 0}
    write_new(run/'preflight.json', report)
    return report


class Gateway:
    def __init__(self, model, tokenizer, c, base=False):
        self.model, self.tokenizer, self.c, self.base = model, tokenizer, c, base

    def generate_method(self, messages):
        import torch
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                  enable_thinking=False)
        batch = self.tokenizer(text, add_special_tokens=False, return_tensors='pt').to('cuda')
        if batch['input_ids'].shape[1] + self.c['max_new_tokens'] > self.c['max_context']:
            raise GenerationError('Full prompt and response budget exceed context')
        start = time.monotonic()
        self.model.eval()
        from contextlib import nullcontext
        with torch.inference_mode(), (self.model.disable_adapter() if self.base else nullcontext()):
            output = self.model.generate(**batch, do_sample=False, max_new_tokens=self.c['max_new_tokens'],
                                         pad_token_id=self.tokenizer.pad_token_id, use_cache=True)
        tail = output[0, batch['input_ids'].shape[1]:]
        raw = self.tokenizer.decode(tail, skip_special_tokens=True)
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise GenerationError('Response is not complete JSON') from exc
        return parsed, {'seconds': time.monotonic()-start, 'generated_tokens': len(tail)}


def evaluate(c, run, model, tok, split, name, base=False, arms=('source_chart_conditions',)):
    data = rows(c, split)
    output = run/(name+'.json')
    if output.exists():
        raise FileExistsError('Evaluation is immutable; do not repeat blind test')
    # Mark access before generation. A crash never silently grants a new test.
    write_new(run/(name+'.access.json'), {'split': split, 'fingerprint': fingerprint(c)})
    service = QimenService(ROOT/c['db'], model=Gateway(model, tok, c, base))
    records = []
    for arm in arms:
        for task in data:
            result = service.ask(Inquiry(task['task_id']), research=MethodRequest(
                str(ROOT/c['manifest']), sha((ROOT/c['manifest']).read_bytes()),
                str(ROOT/c['data_dir']), split, task['task_id'], arm))
            records.append({'arm': arm, 'task_id': task['task_id'], 'result': result,
                            'score': score_task(task, result)})
    report = {'fingerprint': fingerprint(c), 'split': split, 'base_adapter_disabled': base,
        'model': c['model'], 'revision': c['revision'], 'records': records,
        'completion_counts': dict(Counter(r['result']['status'] for r in records)),
        'author_method_accuracy': None, 'reported_feedback_accuracy': None,
        'independent_real_world_accuracy': None,
        'formal_D_full_system_arm': 'blocked', 'semantic_source_review_required': True}
    write_new(output, report)
    return report


def train(c, run, resume=None):
    mac_review = require_mac_method_review(c)
    import torch
    identity = fingerprint(c)
    for prerequisite in ('preflight.json', 'baseline-validation.json'):
        record = json.loads((run/prerequisite).read_bytes())
        if record['fingerprint'] != identity or prerequisite == 'preflight.json' and record['status'] != 'passed':
            raise ValueError('Matching actual preflight and baseline required')
    if (run/'selected.json').exists() or (run/'blind-test.access.json').exists() or (run/'training-complete.json').exists():
        raise ValueError('Selected/tested run cannot be trained again')
    if not resume and (run/'training-started.json').exists():
        raise ValueError('Use an explicit local checkpoint to resume')
    random.seed(c['seed']); torch.manual_seed(c['seed']); torch.cuda.manual_seed_all(c['seed'])
    model, tok, hardware = cuda_model(c)
    data = [encode_example(tok, t, c['max_context']) for t in rows(c, 'train')]
    val = [encode_example(tok, t, c['max_context']) for t in rows(c, 'validation')]
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=c['learning_rate'])
    total = math.ceil(len(data)/c['gradient_accumulation'])*c['max_epochs']
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda step: max(0.0, 1-step/total))
    state = {'epoch': 0, 'cursor': 0, 'order': [], 'optimizer_steps': 0,
             'best_validation_loss': None, 'epochs_without_improvement': 0, 'history': []}
    if resume:
        started = json.loads((run/'training-started.json').read_bytes())
        if started.get('mac_method_review') != mac_review:
            raise ValueError('Mac review changed since this CUDA run started')
        resume = Path(resume).resolve()
        if not resume.is_relative_to(run.resolve()):
            raise ValueError('Resume only checkpoints generated inside this run')
        state = restore_checkpoint(resume, model, optimizer, scheduler, identity)
        # Resuming a superseded checkpoint forks history; require a new run
        # rather than overwrite/repeat already committed optimizer updates.
        existing = sorted(run.glob('step-*'))
        if existing and int(existing[-1].name.split('-')[1]) > state['optimizer_steps']:
            raise ValueError('Resume the latest completed checkpoint, not an older branch')
    else:
        write_new(run/'training-started.json', {'fingerprint': identity, 'hardware': hardware, 'config': c,
                                              'mac_method_review': mac_review})
    for epoch in range(state['epoch'], c['max_epochs']):
        if not state['order']:
            state['order'] = list(range(len(data)))
            random.Random(c['seed']+epoch).shuffle(state['order'])
        model.train()
        while state['cursor'] < len(data):
            window = state['order'][state['cursor']:state['cursor']+c['gradient_accumulation']]
            for i in window:
                loss, _ = torch_loss(model, data[i])
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite training loss; no checkpoint promoted')
                (loss/len(window)).backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], c['gradient_clip'])
            optimizer.step(); scheduler.step(); optimizer.zero_grad()
            state['optimizer_steps'] += 1
            state['cursor'] += len(window)
            save_checkpoint(run/f"step-{state['optimizer_steps']:06d}", model, optimizer, scheduler, state, identity)
            print(json.dumps({'epoch': epoch+1, 'examples_seen': state['cursor'],
                              'optimizer_steps': state['optimizer_steps']}, ensure_ascii=False), flush=True)
        model.eval()
        with torch.no_grad():
            weighted = [torch_loss(model, e) for e in val]
        value = sum(float(loss)*n for loss, n in weighted)/sum(n for _, n in weighted)
        del weighted
        if not math.isfinite(value):
            raise RuntimeError('Nonfinite validation loss')
        improved = state['best_validation_loss'] is None or value < state['best_validation_loss']-c['min_validation_improvement']
        state['best_validation_loss'] = value if improved else state['best_validation_loss']
        state['epochs_without_improvement'] = 0 if improved else state['epochs_without_improvement']+1
        state['history'].append({'epoch': epoch+1, 'validation_loss': value,
                                 'candidate_only_not_professional_score': True})
        state.update(epoch=epoch+1, cursor=0, order=[])
        checkpoint = run/f'epoch-{epoch+1:03d}'
        save_checkpoint(checkpoint, model, optimizer, scheduler, state, identity)
        evaluate(c, run, model, tok, 'validation', checkpoint.name+'-validation')
        if state['epochs_without_improvement'] >= c['validation_loss_patience']:
            break
    report = {'fingerprint': identity, 'state': state, 'hardware': hardware,
              'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
              'professional_checkpoint_selected': False, 'blind_test_used': False,
              'required_next': 'Review generated validation analyses against sources, then select'}
    write_new(run/'training-complete.json', report)
    return report


def select(c, run, checkpoint, review_path):
    if (run/'blind-test.access.json').exists():
        raise ValueError('Blind test has already been opened')
    checkpoint = Path(checkpoint).resolve()
    if checkpoint.parent != run.resolve() or not checkpoint.name.startswith('epoch-'):
        raise ValueError('Select one complete epoch checkpoint in this run')
    checkpoint_receipt(checkpoint, fingerprint(c))
    evaluation = run/(checkpoint.name+'-validation.json')
    report = json.loads(evaluation.read_bytes())
    review = json.loads(Path(review_path).read_bytes())
    ids = {r['task_id'] for r in report['records']}
    if (review.get('split') != 'validation' or review.get('evaluation_sha256') != sha(evaluation.read_bytes())
            or not review.get('reviewer') or not review.get('selection_reason')
            or set(review.get('tasks', {})) != ids):
        raise ValueError('Complete source-based validation review required')
    for item in review['tasks'].values():
        if (type(item.get('method_correct')) is not bool or type(item.get('evidence_supported')) is not bool
                or not item.get('source_note')):
            raise ValueError('Explicit method/evidence judgments and source notes required')
    record = {'fingerprint': fingerprint(c), 'checkpoint': checkpoint.name,
              'checkpoint_receipt_sha256': sha((checkpoint/'receipt.json').read_bytes()),
              'validation_evaluation_sha256': sha(evaluation.read_bytes()),
              'validation_review_sha256': sha(Path(review_path).read_bytes()),
              'validation_review': review, 'selected_before_test': True}
    write_new(run/'selected.json', record)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'audit', 'preflight', 'baseline', 'train', 'select', 'test'))
    p.add_argument('--config', type=Path, default=ROOT/'training/lost_4090_pilot.json')
    p.add_argument('--run', type=Path, default=ROOT/'work/lost-4090-run001')
    p.add_argument('--resume', type=Path)
    p.add_argument('--checkpoint', type=Path)
    p.add_argument('--review', type=Path)
    a = p.parse_args()
    c = load_config(a.config)
    if a.command == 'prepare':
        result = prepare(c)
    elif a.command == 'audit':
        result = {'fingerprint': fingerprint(c), 'split_counts': {s: len(rows(c, s)) for s in
                  ('train', 'validation', 'test', 'development')}, 'model_loaded': False}
    elif a.command == 'preflight':
        result = preflight(c, a.run)
    elif a.command == 'baseline':
        model, tok, _ = cuda_model(c, trainable=False)
        result = evaluate(c, a.run, model, tok, 'validation', 'baseline-validation', base=True, arms=ARMS)
    elif a.command == 'train':
        result = train(c, a.run, a.resume)
    elif a.command == 'select':
        if not a.checkpoint or not a.review:
            p.error('select requires --checkpoint and --review')
        result = select(c, a.run, a.checkpoint, a.review)
    else:
        selected = json.loads((a.run/'selected.json').read_bytes())
        checkpoint = a.run/selected['checkpoint']
        checkpoint_receipt(checkpoint, fingerprint(c))
        if (selected['fingerprint'] != fingerprint(c)
                or selected['checkpoint_receipt_sha256'] != sha((checkpoint/'receipt.json').read_bytes())):
            raise ValueError('Selected model changed')
        # Baseline and adapted model use identical test inputs only AFTER selection.
        model, tok, _ = cuda_model(c, checkpoint/'adapter', trainable=False)
        evaluate(c, a.run, model, tok, 'test', 'blind-test-base', base=True)
        result = evaluate(c, a.run, model, tok, 'test', 'blind-test')
    print(json.dumps({k: v for k, v in result.items() if k not in ('records',)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
