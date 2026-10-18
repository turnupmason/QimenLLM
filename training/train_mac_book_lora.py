"""Larger, validation-driven whole-book Mac LoRA with exact cached prefix.

Only final block changes: cached layers0..62 remain exactly frozen. Source-method
acceptance is decided after generated outputs, not by lowering teacher NLL.
"""
import argparse,gc,json,math,os,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from cache_mac_curriculum import selected_rows,write
from epoch_protocol import sha,order_for_epoch,learning_rate
from train_mac_method_lora import validate_mac_cursor,validate_official_resume_name

def preflight(config,cache,baseline,manifest,data,model_manifest):
 rows,release=selected_rows(manifest,data);base=json.loads(Path(model_manifest).read_bytes());train=[t for t in rows if t['split']=='train'];val=[t for t in rows if t['split']=='validation']
 if release.get('release_id')!='shenqi-book-method-curriculum-v1' or release['quarantined_tasks']!=3 or release['source_inputs_with_tasks']!=26 or release['case_stories_source_reviewed']!=98:raise ValueError('Full reviewed and isolated curriculum required')
 if any(t['family_id'] in release['excluded_training_families'] for t in rows):raise ValueError('Quarantined family in training/validation')
 if config['target_layer']!=63 or config['target_modules']!=['self_attn.q_proj','self_attn.k_proj','self_attn.v_proj','self_attn.o_proj','mlp.gate_proj','mlp.up_proj','mlp.down_proj'] or config['dropout']!=0 or config['rank']!=16:raise ValueError('Only preregistered final-block run')
 if base['revision']!=config['base_revision'] or cache.get('status')!='complete' or cache['release_sha256']!=sha(manifest) or cache['model_manifest_sha256']!=sha(model_manifest) or cache['test_opened'] is not False or cache['optimizer_updates']!=0 or cache['longest_full_cached_loss_delta']>1e-5:raise ValueError('Exact full/cache preflight missing')
 if baseline.get('status')!='generation_complete_not_semantic_acceptance' or baseline.get('adapter') is not None or baseline.get('training_updates')!=0 or baseline.get('test_accessed') is not False or baseline['data_manifest_sha256']!=sha(manifest) or baseline['model_manifest_sha256']!=sha(model_manifest) or baseline['revision']!=config['base_revision']:raise ValueError('Same-base whole-book unadapted generation baseline missing')
 if {r['task_id'] for r in baseline['records'] if r['split']=='validation'}!={t['task_id'] for t in val} or len(baseline['chapter_counts'])!=26:raise ValueError('Baseline lacks full validation/chapter diagnostics')
 entries={r['task_id']:r for r in cache['examples']}
 if len(entries)!=len(rows) or set(entries)!={t['task_id'] for t in rows}:raise ValueError('Cache task coverage differs')
 for t in rows:
  e=entries[t['task_id']]
  if e['row_sha256']!=t['sha256'] or e['split']!=t['split'] or sha(e['file'])!=e['file_sha256']:raise ValueError('Cache identity/file differs')
 return rows,release,base,entries

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'training/mac_book_curriculum_v1.json');p.add_argument('--cache-receipt',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--model-manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',type=Path);a=p.parse_args();cfg=json.loads(a.config.read_bytes());manifest=ROOT/cfg['data_manifest'];cache=json.loads(a.cache_receipt.read_bytes());baseline=json.loads(a.baseline.read_bytes());rows,release,baseinfo,entries=preflight(cfg,cache,baseline,manifest,ROOT/cfg['data_dir'],a.model_manifest)
 if baseline['config_sha256']!=sha(a.config):raise ValueError('Baseline generation config differs')
 if cache['code_sha256']!=sha(ROOT/'training/cache_mac_curriculum.py'):raise ValueError('Cache preparation code changed')
 if a.output.exists() and not a.resume:raise FileExistsError('New run or explicit latest checkpoint resume')
 if (a.output/'report.json').exists():raise ValueError('Completed run immutable')
 if a.resume:
  validate_official_resume_name(a.resume)
  if not a.resume.resolve().is_relative_to(a.output.resolve()):raise ValueError('Checkpoint belongs to another run')
 for n,m in baseinfo['files'].items():
  f=Path(baseinfo['local_path'])/n
  if not f.resolve().is_relative_to(Path(baseinfo['local_path']).resolve()) or sha(f)!=m['sha256']:raise ValueError('Pinned base changed')
 a.output.mkdir(parents=True,exist_ok=True);identity={'config_sha256':sha(a.config),'cache_receipt_sha256':sha(a.cache_receipt),'baseline_sha256':sha(a.baseline),'release_sha256':sha(manifest),'model_manifest_sha256':sha(a.model_manifest),'code_sha256':{n:sha(ROOT/n) for n in ('training/train_mac_book_lora.py','training/mlx_tail.py','training/epoch_protocol.py')}}
 if (a.output/'identity.json').exists():
  if json.loads((a.output/'identity.json').read_bytes())!=identity:raise ValueError('Run identity differs')
 else:write(a.output/'identity.json',identity)
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1');import mlx.core as mx;import mlx.nn as nn;import mlx.optimizers as optim
 from mlx.utils import tree_flatten,tree_unflatten
 from mlx_lm import load
 from mlx_lm.tuner.lora import LoRALinear
 from mlx_tail import make_tail,tail_loss,restore_mlx_rng
 mx.set_memory_limit(19_000_000_000);mx.set_cache_limit(64*1024**2);mx.random.seed(17);random.seed(17)
 report={**identity,'scope':'whole_book_source_conditioned_method_lora','status':'preflight','epochs_cap':cfg['epochs_cap'],'validation_patience':cfg['validation_patience'],'rank':cfg['rank'],'scale':cfg['scale'],'target_modules':cfg['target_modules'],'model_revision':baseinfo['revision'],'source_data_version':release['source_data_version'],'optimizer_steps':0,'completed_epochs':0,'test_accessed':False,'all_chapter_model_pass':False,'semantic_source_review_complete':False,'log':[],'started_unix':time.time()}
 def log(stage,**kw):
  item={'stage':stage,'unix':time.time(),**kw};report['log'].append(item);write(a.output/'progress.json',report);print(json.dumps(item),flush=True)
 try:
  model,_=load(baseinfo['local_path'],trust_remote_code=False);model.eval();model.freeze();mx.eval(model.parameters());base=model.language_model.model
  if len(base.layers)!=64 or base.layers[-1].is_linear:raise ValueError('Final full-attention architecture required')
  tail=make_tail(base.layers[-1],base.norm,model.language_model.lm_head);del base,model;gc.collect();mx.clear_cache()
  train=[t['task_id'] for t in rows if t['split']=='train'];validation=[t['task_id'] for t in rows if t['split']=='validation'];total=cfg['epochs_cap']*len(train)
  def datum(tid):
   e=entries[tid]
   if sha(e['file'])!=e['file_sha256']:raise ValueError('Cache mutated')
   d=mx.load(e['file']);return d['hidden'],d['labels'],e['prefix']
  def evaluate():
   weighted=0.;tokens=0
   for tid in validation:
    h,y,prefix=datum(tid);v=tail_loss(tail,h,y,prefix);mx.eval(v);n=len(entries[tid]['input_ids'])-prefix;weighted+=float(v.item())*n;tokens+=n;del h,y,v;mx.clear_cache()
   return weighted/tokens
  intrinsic=evaluate();expected=sum(entries[t]['unadapted_teacher_nll']*(len(entries[t]['input_ids'])-entries[t]['prefix']) for t in validation)/sum(len(entries[t]['input_ids'])-entries[t]['prefix'] for t in validation)
  if abs(intrinsic-expected)>1e-5:raise ValueError('Tail unadapted validation differs from cache receipt')
  for parent in ('self_attn','mlp'):
   obj=getattr(tail.last,parent);keys=[k.split('.')[1] for k in cfg['target_modules'] if k.startswith(parent+'.')];obj.update_modules({key:LoRALinear.from_base(getattr(obj,key),r=cfg['rank'],scale=cfg['scale'],dropout=0) for key in keys})
  tail.eval();mx.eval(tail.trainable_parameters());initial={k:mx.array(v) for k,v in tree_flatten(tail.trainable_parameters())};mx.eval(initial);report['trainable_parameters']=sum(v.size for v in initial.values());report['initial_validation_nll']=intrinsic
  optimizer=optim.AdamW(learning_rate=cfg['learning_rate'],weight_decay=cfg['weight_decay']);value_grad=nn.value_and_grad(tail,tail_loss)
  def save(name,state):
   dest=a.output/name;stage=dest.with_name(dest.name+'.partial')
   if dest.exists() or stage.exists():raise FileExistsError('Immutable checkpoint')
   stage.mkdir();weights=dict(tree_flatten(tail.trainable_parameters()));mx.save_safetensors(str(stage/'tail-adapters.safetensors'),weights);mx.save_safetensors(str(stage/'adapters.safetensors'),{k.replace('last.','language_model.model.layers.63.',1):v for k,v in weights.items()});write(stage/'adapter_config.json',{'num_layers':1,'fine_tune_type':'lora','lora_parameters':{'rank':cfg['rank'],'scale':cfg['scale'],'dropout':0.,'keys':cfg['target_modules']}});mx.savez(str(stage/'optimizer.npz'),**dict(tree_flatten(optimizer.state)));mx.savez(str(stage/'rng.npz'),mlx_key=mx.random.state[0]);write(stage/'state.json',{**state,'identity':identity,'python_rng':random.getstate(),'files':{f.name:sha(f) for f in stage.iterdir() if f.is_file()}});stage.rename(dest);return dest
  def restore(dest):
   s=json.loads((dest/'state.json').read_bytes())
   if s['identity']!=identity:raise ValueError('Checkpoint identity differs')
   for n,h in s['files'].items():
    if sha(dest/n)!=h:raise ValueError('Checkpoint bytes differ')
   tail.load_weights(str(dest/'tail-adapters.safetensors'),strict=False);optimizer.state=tree_unflatten(list(mx.load(str(dest/'optimizer.npz')).items()));restore_mlx_rng(mx.load(str(dest/'rng.npz'))['mlx_key'])
   def tup(v):return tuple(tup(x) for x in v) if isinstance(v,list) else v
   random.setstate(tup(s['python_rng']));mx.eval(tail.trainable_parameters(),optimizer.state)
   if int(optimizer.step.item())!=s['optimizer_step']:raise ValueError('Optimizer step differs')
   return s
  def step(tid,number):
   h,y,prefix=datum(tid);loss,grads=value_grad(tail,h,y,prefix);grads,_=optim.clip_grad_norm(grads,cfg['gradient_clip']);optimizer.learning_rate=learning_rate(number,total,len(train),maximum=cfg['learning_rate']);optimizer.update(tail,grads);mx.eval(loss,tail.trainable_parameters(),optimizer.state);value=float(loss.item())
   if not math.isfinite(value) or any(not bool(mx.all(mx.isfinite(v)).item()) for _,v in tree_flatten(tail.trainable_parameters())):raise ValueError('Nonfinite update')
   del h,y,loss,grads;mx.clear_cache();return value
  state={'epoch':0,'cursor':0,'optimizer_step':0,'data_order':order_for_epoch(train,0),'best_validation_nll':intrinsic,'best_checkpoint':None,'bad_epochs':0}
  if a.resume:
   state=restore(a.resume);latest=json.loads((a.output/'latest.json').read_bytes())
   if latest['checkpoint']!=a.resume.name:raise ValueError('Resume latest completed checkpoint only')
  else:
   probes=sorted(train,key=lambda t:len(entries[t]['input_ids']),reverse=True)[:2];step(probes[0],1);probe=save('resume-probe',{**state,'optimizer_step':1,'cursor':1});reference=step(probes[1],2);expected={k:mx.array(v) for k,v in tree_flatten(tail.trainable_parameters())};mx.eval(expected);restore(probe);resumed=step(probes[1],2);actual=dict(tree_flatten(tail.trainable_parameters()));delta=max(float(mx.max(mx.abs(v-actual[k])).item()) for k,v in expected.items())
   if abs(reference-resumed)>1e-6 or delta>1e-6:raise ValueError('Real task next-update resume differs')
   report['resume_loss_delta']=abs(reference-resumed);report['resume_adapter_delta']=delta;tail.update(tree_unflatten(list(initial.items())));optimizer=optim.AdamW(learning_rate=cfg['learning_rate'],weight_decay=cfg['weight_decay']);mx.random.seed(17);random.seed(17);mx.eval(tail.trainable_parameters());log('expanded_adapter_real_resume_probe_passed',parameters=report['trainable_parameters'],loss_delta=abs(reference-resumed),adapter_delta=delta)
  validate_mac_cursor(state,train,cfg['epochs_cap'])
  while state['epoch']<cfg['epochs_cap']:
   for cursor in range(state['cursor'],len(train)):
    tid=state['data_order'][cursor];loss=step(tid,state['optimizer_step']+1);state['cursor']=cursor+1;state['optimizer_step']+=1;report['optimizer_steps']=state['optimizer_step']
    if state['optimizer_step']%cfg['checkpoint_every_updates']==0:
     checkpoint=save(f'step-{state["optimizer_step"]:05d}',state);write(a.output/'latest.json',{'checkpoint':checkpoint.name,'optimizer_step':state['optimizer_step']})
    log('optimizer_update',epoch=state['epoch']+1,cursor=cursor+1,optimizer_step=state['optimizer_step'],task_id=tid,loss=loss)
   validation_nll=evaluate();improved=validation_nll<state['best_validation_nll']-cfg['validation_min_nll_improvement'];state['epoch']+=1;state['cursor']=0;name=f'epoch-{state["epoch"]:02d}'
   if improved:state.update(best_validation_nll=validation_nll,best_checkpoint=name)
   state['bad_epochs']=0 if improved else state['bad_epochs']+1;state['data_order']=order_for_epoch(train,state['epoch']) if state['epoch']<cfg['epochs_cap'] else [];checkpoint=save(name,state);write(a.output/'latest.json',{'checkpoint':name,'optimizer_step':state['optimizer_step']});report.update(completed_epochs=state['epoch'],best_checkpoint=state['best_checkpoint']);log('epoch_complete',epoch=state['epoch'],validation_nll=validation_nll,improved=improved,checkpoint=name)
   # Generation is a separate full-model process after this process exits;
   # cap each invocation at an evaluation boundary without marking acceptance.
   if state['bad_epochs']>=cfg['validation_patience'] or state['epoch']%cfg['generation_evaluation_every_epochs']==0:break
  finished=state['epoch']>=cfg['epochs_cap'] or state['bad_epochs']>=cfg['validation_patience'];report.update(status='candidate_training_complete' if finished else 'awaiting_generated_source_review',final_state=state,peak_memory_bytes=mx.get_peak_memory(),finished_unix=time.time());write(a.output/('report.json' if finished else 'evaluation-boundary.json'),report);log('candidate_saved_for_generation',epochs=state['epoch'],optimizer_steps=state['optimizer_step'],checkpoint=state['best_checkpoint'],professional_pass=False)
 except BaseException as exc:
  report.update(status='failed',error_type=type(exc).__name__);write(a.output/'progress.json',report);raise
if __name__=='__main__':main()
