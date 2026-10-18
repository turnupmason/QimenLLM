"""Retired author-quote pilot, retained for audit and numerical helpers.

The user's professional-task summary supersedes this pilot. Its entry point
must not allocate a model or resume the fixed-fifty-epoch reconstruction run.

Caches are possible ONLY because adapters are restricted to the final block.
The original 27B frozen prefix is evaluated on every complete sequence once.
No case truncation, repeated-example augmentation, full-model tuning, or
professional accuracy claim. Training artifacts stay outside tracked data.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import random
import time
import traceback
import importlib.metadata
import platform
import subprocess


def json_write(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)


def tokenize(tokenizer,tasks,split):
    rows=[]
    for t in tasks.values():
        if t['split']!=split:continue
        text=tokenizer.apply_chat_template(t['messages'][:-1],tokenize=False,
                                          add_generation_prompt=True,enable_thinking=False)
        prefix=tokenizer.encode(text,add_special_tokens=False)
        answer=tokenizer.encode(t['messages'][-1]['content']+'<|im_end|>',add_special_tokens=False)
        rows.append({'task_id':t['task_id'],'family_id':t['family_id'],'tokens':prefix+answer,
                     'prompt_tokens':len(prefix),'target_tokens':len(answer)})
    return rows


def _historical_pilot_main():
    from epoch_protocol import order_for_epoch, learning_rate, validate_cursor, verify_release, sha

    p=argparse.ArgumentParser();p.add_argument('--model-receipt',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--dataset-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',type=Path)
    p.add_argument('--baseline-report',type=Path,required=True)
    args=p.parse_args()
    # No MLX import/model allocation before verifying permissions, pinned release and baseline.
    if not args.baseline_report.is_file() or len(json.loads(args.baseline_report.read_bytes())['rows'])!=12:
        raise ValueError('Complete same-27B development baseline required')
    manifest,tasks=verify_release(args.manifest,args.dataset_root)
    model_receipt=json.loads(args.model_receipt.read_bytes())
    if model_receipt['revision']!='10c35caafbb80f7dc6a7a432cdd11af10a6d4818':
        raise ValueError('Unexpected 27B revision')
    baseline_report=json.loads(args.baseline_report.read_bytes())
    if baseline_report['model']['revision']!=model_receipt['revision'] or baseline_report.get('adapter') is not None:
        raise ValueError('Baseline must use same unadapted 27B')
    model_path=Path(model_receipt['local_path']).resolve()
    if not model_path.is_dir():raise FileNotFoundError(model_path)
    for name,info in model_receipt['files'].items():
        if not (model_path/name).resolve().is_relative_to(model_path) or sha(model_path/name)!=info['sha256']:
            raise ValueError('Pinned 27B file changed: '+name)
    if args.output.exists() and args.resume is None:raise FileExistsError('Keep previous experiment')
    args.output.mkdir(parents=True,exist_ok=True);root=args.output
    report_path=root/'progress.json'
    report={'scope':'initial-author-turn-27b-final-attention-qlora-research',
            'status':'starting','model_revision':model_receipt['revision'],
            'dataset_sha256':sha(args.manifest),'baseline_report_sha256':sha(args.baseline_report),
            'epochs_planned':50,'completed_epochs':0,'optimizer_steps':0,
            'rank':4,'mlx_scale':2.0,'equivalent_alpha_if_alpha_over_r':8,
            'dropout':0.0,'target_modules':['layers.63.self_attn.q_proj','layers.63.self_attn.v_proj'],
            'batch_size':1,'gradient_accumulation':1,'truncate':False,'drop_last':False,
            'seed':17,'started_unix':time.time(),'rows':[],
            'training_only_scope':True,'professional_ask_integrated':False,
            'source_commit':baseline_report['source_commit'],
            'python':platform.python_version(),'platform':platform.platform(),
            'hardware':{k:subprocess.check_output(['sysctl','-n',k],text=True).strip()
                        for k in ('hw.memsize','hw.model','machdep.cpu.brand_string')},
            'packages':{k:importlib.metadata.version(k) for k in ('mlx','mlx-lm','transformers','tokenizers','safetensors')},
            'gradient_clip_norm':1.0,'optimizer':'AdamW','weight_decay':.01,
            'loss_precision':'float32','quantization':'affine 4bit group64; frozen base',
            'independent_real_world_accuracy':None}
    def log(stage,**kw):
        row={'stage':stage,'unix':time.time(),**kw};report['rows'].append(row)
        json_write(report_path,report)
        plan_path=Path(__file__).resolve().parents[1]/'training/qwen38_27b_lora_plan.json'
        plan=json.loads(plan_path.read_bytes())
        plan['status']=report['status'];plan['training']['completed_epochs']=report['completed_epochs']
        plan['training']['optimizer_steps']=report['optimizer_steps']
        plan['actual_run_progress']=str(report_path.resolve())
        json_write(plan_path,plan)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    try:
        report['code_sha256']={name:sha(Path(__file__).parent/name) for name in ('train_mac_author_lora.py','epoch_protocol.py','author_release.py','mlx_tail.py')}
        os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
        import mlx.core as mx
        import mlx.nn as nn
        import mlx.optimizers as optim
        from mlx.utils import tree_flatten,tree_unflatten
        from mlx_lm import load
        from mlx_lm.models.base import create_attention_mask,create_ssm_mask
        from mlx_lm.tuner.lora import LoRALinear
        mx.set_memory_limit(19_000_000_000);mx.set_cache_limit(64*1024**2)
        mx.random.seed(17);random.seed(17)
        model,tok=load(str(model_path),tokenizer_config={'trust_remote_code':False},trust_remote_code=False)
        mx.eval(model.parameters());model.eval();model.freeze()
        tokenized={s:tokenize(tok,tasks,s) for s in ('train','validation','test','development')}
        lengths=[len(t['tokens']) for rows in tokenized.values() for t in rows]
        report['context_tokens_max']=max(lengths);report['split_counts']={s:len(t) for s,t in tokenized.items()}
        report['steps_per_epoch']=len(tokenized['train']);report['planned_optimizer_steps']=50*len(tokenized['train'])
        report['tokenized_data_sha256']=hashlib.sha256(json.dumps(tokenized,sort_keys=True).encode()).hexdigest()
        # Persist tokenized complete sequences and their model-specific prefix offsets.
        json_write(root/'tokens.json',tokenized)
        base=model.language_model.model;last=base.layers[-1]
        if last.is_linear or len(base.layers)!=64:raise ValueError('Unsupported adapter location')
        from mlx_tail import make_tail,masked_reference_loss,tail_loss,restore_mlx_rng
        tail=make_tail(last,base.norm,model.language_model.lm_head)
        cache=root/'frozen-prefix-cache';cache.mkdir(exist_ok=True)
        cache_index={}
        previous_cache_index=json.loads((root/'cache-index.json').read_bytes()) if args.resume else None
        all_rows=[r for s in ('train','validation','test','development') for r in tokenized[s]]
        for index,row in enumerate(all_rows):
            ids=mx.array([row['tokens'][:-1]]);labels=mx.array([row['tokens'][1:]])
            # Equivalence measured on an actual complete historical task, not neutral fixture.
            if index==0:
                full_loss=masked_reference_loss(model(ids),labels,row['prompt_tokens']);mx.eval(full_loss)
                reference=float(full_loss.item());del full_loss;mx.clear_cache()
            dest=cache/(row['task_id']+'.safetensors')
            if args.resume is None or not dest.is_file():
                t=time.perf_counter();h=base.embed_tokens(ids)
                fa=create_attention_mask(h,None);ssm=create_ssm_mask(h,None)
                for layer in base.layers[:-1]:
                    h=layer(h,mask=ssm if layer.is_linear else fa);mx.eval(h)
                h=mx.stop_gradient(h);mx.eval(h)
                mx.save_safetensors(str(dest),{'hidden':h,'labels':labels})
                log('cached_complete_frozen_prefix',task_id=row['task_id'],tokens=len(row['tokens']),
                    index=index+1,total=len(all_rows),seconds=time.perf_counter()-t,peak_bytes=mx.get_peak_memory())
            else:
                if row['task_id'] not in previous_cache_index or sha(dest)!=previous_cache_index[row['task_id']]['sha256']:
                    raise ValueError('Resume cache differs from saved index')
                h=mx.load(str(dest))['hidden']
            cache_index[row['task_id']]={'sha256':sha(dest),'tokens':len(row['tokens']),
                                        'prompt_tokens':row['prompt_tokens'],'target_tokens':row['target_tokens'],'hidden_dtype':str(h.dtype)}
            if index==0:
                reopened=mx.load(str(dest))
                if not bool(mx.all(reopened['hidden']==h).item()) or not bool(mx.all(reopened['labels']==labels).item()):
                    raise ValueError('Prefix cache roundtrip differs')
                h=reopened['hidden'];del reopened
                v=tail_loss(tail,h,labels,row['prompt_tokens']);mx.eval(v);delta=abs(float(v.item())-reference)
                if delta>1e-5:raise ValueError('Cached tail differs from full 27B model')
                log('full_27b_vs_cached_loss_equal',absolute_difference=delta,full_nll=reference)
                del v
            del h,ids,labels;mx.clear_cache()
        json_write(root/'cache-index.json',cache_index)
        # Tail owns only final block, norm and lm_head. Frozen prefix weights are
        # now freed; cached activations are exact, not quantized/approximated again.
        del layer,base,model;gc.collect();mx.clear_cache()
        log('frozen_prefix_unloaded',active_bytes=mx.get_active_memory())
        def datum(task_id):
            dest=cache/(task_id+'.safetensors')
            if sha(dest)!=cache_index[task_id]['sha256']:raise ValueError('Cached prefix changed')
            d=mx.load(str(dest));return d['hidden'],d['labels'],cache_index[task_id]['prompt_tokens']
        def evaluate(split):
            total=0.;count=0
            for row in tokenized[split]:
                h,y,prompt=datum(row['task_id']);value=tail_loss(tail,h,y,prompt);mx.eval(value)
                total+=float(value.item())*row['target_tokens'];count+=row['target_tokens']
                del h,y,value;mx.clear_cache()
            return {'target_token_nll':total/count,'target_tokens':count,'tasks':len(tokenized[split])}
        if args.resume is None:
            baseline={s:evaluate(s) for s in ('train','validation','test')}
            json_write(root/'intrinsic-baseline.json',baseline)
            log('same_27b_intrinsic_baseline_recorded',validation=baseline['validation'],
                note='Teacher-forced source reconstruction NLL is not author-judgment or predictive accuracy')
        tail.last.self_attn.update_modules({key:LoRALinear.from_base(getattr(tail.last.self_attn,key),r=4,scale=2,dropout=0) for key in ('q_proj','v_proj')})
        tail.eval();mx.eval(tail.trainable_parameters())
        report['trainable_parameters']=sum(v.size for k,v in tree_flatten(tail.trainable_parameters()))
        optimizer=optim.AdamW(learning_rate=1e-4,weight_decay=.01)
        vg=nn.value_and_grad(tail,tail_loss)
        train_ids=[t['task_id'] for t in tokenized['train']];total_steps=50*len(train_ids)
        configuration={k:report[k] for k in ('rank','mlx_scale','target_modules','batch_size','gradient_accumulation',
                     'seed','gradient_clip_norm','optimizer','weight_decay','epochs_planned','tokenized_data_sha256')}
        configuration['cache_index_sha256']=sha(root/'cache-index.json')
        configuration_sha256=hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest()
        report['configuration']=configuration;report['configuration_sha256']=configuration_sha256
        initial={k:mx.array(v) for k,v in tree_flatten(tail.trainable_parameters())};mx.eval(initial)
        def save_checkpoint(name,state):
            dest=root/name
            if dest.exists():raise FileExistsError(dest)
            dest.mkdir();mx.save_safetensors(str(dest/'tail-adapters.safetensors'),dict(tree_flatten(tail.trainable_parameters())))
            mx.savez(str(dest/'optimizer.npz'),**dict(tree_flatten(optimizer.state)))
            mx.savez(str(dest/'rng.npz'),mlx_key=mx.random.state[0])
            state=state|{'dataset_sha256':report['dataset_sha256'],'model_revision':report['model_revision'],
                         'configuration_sha256':configuration_sha256,
                         'python_rng':random.getstate(),'scheduler':{'kind':'warmup_cosine','maximum':1e-4,'minimum_ratio':.1,
                         'warmup_steps':len(train_ids),'total_steps':total_steps},
                         'files':{f:sha(dest/f) for f in ('tail-adapters.safetensors','optimizer.npz','rng.npz')}}
            json_write(dest/'state.json',state);return dest
        def restore(dest):
            state=json.loads((dest/'state.json').read_bytes())
            if (state['dataset_sha256']!=report['dataset_sha256'] or state['model_revision']!=report['model_revision']
                    or state['configuration_sha256']!=configuration_sha256):
                raise ValueError('Checkpoint release/model mismatch')
            for f,h in state['files'].items():
                if sha(dest/f)!=h:raise ValueError('Checkpoint file changed')
            tail.load_weights(str(dest/'tail-adapters.safetensors'),strict=False)
            optimizer.state=tree_unflatten(list(mx.load(str(dest/'optimizer.npz')).items()))
            restore_mlx_rng(mx.load(str(dest/'rng.npz'))['mlx_key'])
            def tuples(x):return tuple(tuples(v) for v in x) if isinstance(x,list) else x
            random.setstate(tuples(state['python_rng']));mx.eval(tail.trainable_parameters(),optimizer.state)
            if int(optimizer.step.item())!=state['optimizer_step']:raise ValueError('Optimizer step differs')
            return state
        def step(task_id,number):
            h,y,prompt=datum(task_id);t=time.perf_counter()
            loss,grad=vg(tail,h,y,prompt);grad,norm=optim.clip_grad_norm(grad,1.0)
            optimizer.learning_rate=learning_rate(number,total_steps,len(train_ids))
            optimizer.update(tail,grad);mx.eval(loss,tail.trainable_parameters(),optimizer.state)
            value=float(loss.item())
            if not __import__('math').isfinite(value) or any(not bool(mx.all(mx.isfinite(v)).item())
                 for k,v in tree_flatten(tail.trainable_parameters())):
                raise ValueError('Nonfinite training loss or adapter')
            del h,y,loss,grad;mx.clear_cache();return value,time.perf_counter()-t
        state={'epoch':0,'cursor':0,'optimizer_step':0,'data_order':order_for_epoch(train_ids,0),
               'best_validation_nll':None,'best_checkpoint':None}
        if args.resume is None:
            # Two real-domain updates are a disposable equivalence probe. Both
            # adapter and optimizer/RNG are reset before epoch 1 begins.
            step(state['data_order'][0],1)
            probe=save_checkpoint('resume-probe',state|{'cursor':1,'optimizer_step':1})
            uninterrupted_loss,_=step(state['data_order'][1],2)
            expected={k:mx.array(v) for k,v in tree_flatten(tail.trainable_parameters())};mx.eval(expected)
            restore(probe);restored_loss,_=step(state['data_order'][1],2)
            delta=max(float(mx.max(mx.abs(v-dict(tree_flatten(tail.trainable_parameters()))[k])).item()) for k,v in expected.items())
            if delta>1e-6 or abs(uninterrupted_loss-restored_loss)>1e-6:raise ValueError('Resume differs from uninterrupted update')
            log('actual_domain_resume_equivalence_passed',max_adapter_difference=delta,loss_difference=abs(uninterrupted_loss-restored_loss))
            tail.update(tree_unflatten(list(initial.items())));optimizer=optim.AdamW(learning_rate=1e-4,weight_decay=.01)
            mx.random.seed(17);random.seed(17);mx.eval(tail.trainable_parameters())
        else:state=restore(args.resume)
        report['completed_epochs']=state['epoch'];report['optimizer_steps']=state['optimizer_step']
        validate_cursor(state,train_ids,50)
        report['status']='training';json_write(report_path,report)
        while state['epoch']<50:
            epoch=state['epoch'];start_cursor=state['cursor'];losses=[];times=[]
            for cursor in range(start_cursor,len(train_ids)):
                loss,seconds=step(state['data_order'][cursor],state['optimizer_step']+1)
                state['cursor']=cursor+1;state['optimizer_step']+=1;losses.append(loss);times.append(seconds)
                report['optimizer_steps']=state['optimizer_step']
                if (cursor+1)%10==0 and cursor+1<len(train_ids):
                    save_checkpoint(f'step-{state["optimizer_step"]:05d}',state)
                log('optimizer_update',epoch=epoch+1,task_id=state['data_order'][cursor],example=cursor+1,examples=len(train_ids),
                    optimizer_step=state['optimizer_step'],loss=loss,seconds=seconds)
            validation=evaluate('validation');state['epoch']+=1;state['cursor']=0
            state['data_order']=order_for_epoch(train_ids,state['epoch']) if state['epoch']<50 else []
            improved=state['best_validation_nll'] is None or validation['target_token_nll']<state['best_validation_nll']
            name=f'epoch-{state["epoch"]:02d}'
            if improved:state['best_validation_nll']=validation['target_token_nll'];state['best_checkpoint']=name
            state['validation']=validation;checkpoint=save_checkpoint(name,state)
            report['completed_epochs']=state['epoch'];report['best_checkpoint']=state['best_checkpoint']
            log('epoch_complete',epoch=state['epoch'],examples_seen_total=state['optimizer_step'],
                validation=validation,checkpoint=name,selected_by_validation=improved)
            # Standard MLX adapter export for the SAME 27B model; no wrapper-only weights.
            weights={k.replace('last.','language_model.model.layers.63.',1):v for k,v in tree_flatten(tail.trainable_parameters())}
            mx.save_safetensors(str(checkpoint/'adapters.safetensors'),weights)
            json_write(checkpoint/'adapter_config.json',{'num_layers':1,'fine_tune_type':'lora','lora_parameters':{'rank':4,'scale':2.,'dropout':0.,'keys':['self_attn.q_proj','self_attn.v_proj']}})
        final_test=evaluate('test');restore(root/state['best_checkpoint']);best_test=evaluate('test')
        report['test_after_fifty_epochs']={'final':final_test,'best_validation':best_test,
            'selection_used_test':False,'metric_scope':'teacher_forced_source_reconstruction_not_predictive_accuracy'}
        report['status']='training_complete_50_epochs_intrinsic_validation_only';report['finished_unix']=time.time()
        json_write(report_path,report);log('fifty_complete_epochs',optimizer_steps=state['optimizer_step'])
    except BaseException as exc:
        report['status']='failed';report['error_type']=type(exc).__name__;report['error']=str(exc)
        json_write(report_path,report);traceback.print_exc();raise

def main():
    raise SystemExit(
        'Retired author-quote pilot: professional role/evidence/synthesis/timing/'
        'continuation tasks and the full-system baseline are required first. '
        'Fifty epochs is no longer a user requirement. No model was loaded.'
    )


if __name__=='__main__':main()
