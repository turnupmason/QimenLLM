"""Generate all validation/dev and coverage diagnostics via the shared ask entry.

A run can resume only uncompleted requests with identical code/model/data config.
Never opens test. Seen train tasks are diagnostics, not unseen validation.
"""
import argparse,hashlib,importlib.metadata,json,os,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'training'))
from epoch_protocol import sha
from method_release import encoded
from qimenllm.contracts import Inquiry
from qimenllm.evaluation.book_method import BookMethodRequest
from qimenllm.evaluation.method import score_task
from qimenllm.models.mlx_gateway import MLXResearchGateway
from qimenllm.reasoning.service import QimenService

def select_tasks(manifest,data):
 meta=json.loads(Path(manifest).read_bytes());out=[]
 if meta.get('release_id')!='shenqi-book-method-curriculum-v1' or not meta.get('frozen'):raise ValueError('Frozen full curriculum required')
 for split in ('validation','development','train'):
  raw=(Path(data)/(split+'.jsonl')).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=meta['files'][split+'.jsonl']['sha256']:raise ValueError('Task bytes differ')
  rows=[json.loads(line) for line in raw.splitlines()]
  for t in rows:
   if t['split']!=split or meta['family_assignments'].get(t['family_id'])!=split or t['family_id'] in meta['excluded_training_families']:raise ValueError('Group ownership or duplicate isolation')
  if split!='train':out.extend(rows)
  else:
   # Read train diagnostics only where chapter/type has no unseen example.
   covered={(t['chapter'],t['task_type']) for t in out}
   for t in rows:
    key=(t['chapter'],t['task_type'])
    if key not in covered:out.append(t);covered.add(key)
 return out

def validate_adapter_identity(adapter,manifest,config,model_manifest):
 state=json.loads((Path(adapter)/'state.json').read_bytes());identity=state['identity']
 if identity.get('release_sha256')!=sha(manifest) or identity.get('config_sha256')!=sha(config) or identity.get('model_manifest_sha256')!=sha(model_manifest):raise ValueError('Adapter belongs to different model/data/config')
 for name in ('adapters.safetensors','adapter_config.json'):
  if state['files'].get(name)!=sha(Path(adapter)/name):raise ValueError('Saved adapter checkpoint changed')
 return {'optimizer_step':state['optimizer_step'],'epoch':state['epoch'],'state_sha256':sha(Path(adapter)/'state.json')}

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'training/mac_book_curriculum_v1.json');p.add_argument('--model-manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--db',type=Path,default=ROOT/'work/demo.sqlite3');p.add_argument('--adapter',type=Path);p.add_argument('--resume',action='store_true');a=p.parse_args();cfg=json.loads(a.config.read_bytes());manifest=ROOT/cfg['data_manifest'];data=ROOT/cfg['data_dir'];todo=select_tasks(manifest,data);base=json.loads(a.model_manifest.read_bytes())
 if base['revision']!=cfg['base_revision']:raise ValueError('Pinned base mismatch')
 adapter_training=None if a.adapter is None else validate_adapter_identity(a.adapter,manifest,a.config,a.model_manifest)
 for n,m in base['files'].items():
  f=Path(base['local_path'])/n
  if not f.resolve().is_relative_to(Path(base['local_path']).resolve()) or sha(f)!=m['sha256']:raise ValueError('Model file changed')
 identity={'data_manifest_sha256':sha(manifest),'config_sha256':sha(a.config),'model_manifest_sha256':sha(a.model_manifest),'script_sha256':sha(Path(__file__)),'runtime_sha256':{n:sha(ROOT/n) for n in ('src/qimenllm/evaluation/book_method.py','src/qimenllm/reasoning/service.py','src/qimenllm/models/mlx_gateway.py')},'adapter_files':None if a.adapter is None else {n:sha(a.adapter/n) for n in ('adapters.safetensors','adapter_config.json')}}
 if a.output.exists() and not a.resume:raise FileExistsError('Resume explicit or new generation run')
 if (a.output/'report.json').exists():raise ValueError('Completed generation immutable')
 a.output.mkdir(parents=True,exist_ok=True)
 if (a.output/'identity.json').exists():
  if json.loads((a.output/'identity.json').read_bytes())!=identity:raise ValueError('Resume identity changed')
 else:(a.output/'identity.json').write_bytes(encoded(identity))
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1');import mlx.core as mx
 mx.set_memory_limit(19_000_000_000);mx.set_cache_limit(64*1024**2)
 gateway=MLXResearchGateway(base['local_path'],revision=base['revision'],max_tokens=cfg['max_generation_tokens'],max_context_tokens=8192,enable_thinking=False,adapter_path=a.adapter)
 adapter_parity=None
 if a.adapter:
  from mlx.utils import tree_flatten
  saved=mx.load(str(a.adapter/'adapters.safetensors'));loaded=dict(tree_flatten(gateway.model.parameters()))
  if len(saved)!=2*len(cfg['target_modules']) or any(n not in loaded for n in saved):raise ValueError('Wrong adapter tensor names/count')
  delta=max(float(mx.max(mx.abs(v-loaded[n])).item()) for n,v in saved.items())
  if delta!=0:raise ValueError('Full model adapter reload mismatch')
  for mod in cfg['target_modules']:
   layer=gateway.model.language_model.model.layers[cfg['target_layer']]
   for part in mod.split('.'):layer=getattr(layer,part)
   if layer.scale!=cfg['scale']:raise ValueError('Reloaded LoRA scale differs')
  adapter_parity={'tensors_compared':len(saved),'max_delta':delta,'scales_match':True}
 service=QimenService(a.db,model=gateway);records=[];started=time.time()
 for t in todo:
  dest=a.output/(t['task_id']+'.json')
  if dest.exists():record=json.loads(dest.read_bytes())
  else:
   result=service.ask(Inquiry(t['task_id']),research=BookMethodRequest(str(manifest),sha(manifest),str(data),t['split'],t['task_id'],seen_training_diagnostic=t['split']=='train'))
   score=score_task(t,result)
   if t.get('input_setting') in ('partial_source_reading','user_relayout_reading'):
    expected=json.loads(t['messages'][2]['content']);actual=result.get('output',{});key='reported_facts' if t['input_setting']=='partial_source_reading' else 'palaces_as_written';score['source_limit_literal_exact_match']=actual.get(key)==expected[key]
   record={'task_id':t['task_id'],'chapter':t['chapter'],'split':t['split'],'context_mode':t['context_mode'],'task_type':t['task_type'],'result':result,'score':score};dest.write_bytes(encoded(record))
  records.append(record);progress={'completed':len(records),'total':len(todo),'last_task':t['task_id'],'last_status':record['result']['status']};(a.output/'progress.json').write_bytes(encoded(progress));print(json.dumps(progress),flush=True)
 report={**identity,'status':'generation_complete_not_semantic_acceptance','scope':'whole_book_source_conditioned_method_research','records':records,'adapter':identity['adapter_files'],'adapter_reload_parity':adapter_parity,'adapter_training':adapter_training,'training_updates':0,'generation_settings':{'max_tokens':cfg['max_generation_tokens'],'thinking':False},'revision':base['revision'],'test_accessed':False,'chapter_counts':dict(Counter(r['chapter'] for r in records)),'completion_counts':dict(Counter(r['result']['status'] for r in records)),'semantic_source_review_complete':False,'all_chapter_model_pass':False,'independent_real_world_accuracy':None,'started_unix':started,'finished_unix':time.time()};(a.output/'report.json').write_bytes(encoded(report))
if __name__=='__main__':main()
