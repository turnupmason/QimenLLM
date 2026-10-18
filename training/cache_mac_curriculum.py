"""Prepare exact frozen-prefix tensors for reviewed train/validation only.

Caching is not optimization. Content-addressed tensors may be reused only with
identical full token sequence and pinned base manifest. No test rows are opened.
"""
import argparse,gc,hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from cuda_pilot import encode_example
from epoch_protocol import sha
from mlx_tail import make_tail,tail_loss

def write(path,value):
 p=Path(path);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)

def selected_rows(manifest,data):
 raw=Path(manifest).read_bytes();meta=json.loads(raw)
 if meta.get('frozen') is not True or meta.get('scope')!='reviewed_book_method_curriculum':raise ValueError('Only frozen reviewed curriculum')
 result=[]
 for split in ('train','validation'):
  blob=(Path(data)/(split+'.jsonl')).read_bytes()
  if hashlib.sha256(blob).hexdigest()!=meta['files'][split+'.jsonl']['sha256']:raise ValueError('Frozen tasks changed')
  for line in blob.splitlines():
   row=json.loads(line)
   if row['split']!=split or meta['family_assignments'][row['family_id']]!=split:raise ValueError('Wrong family owner')
   result.append(row)
 return result,meta

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--model-manifest',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 if a.receipt.exists():raise FileExistsError('Completed cache receipt immutable')
 rows,release=selected_rows(a.manifest,a.data);modelmeta=json.loads(a.model_manifest.read_bytes())
 if modelmeta['revision']!='10c35caafbb80f7dc6a7a432cdd11af10a6d4818':raise ValueError('Pinned base required')
 modelpath=Path(modelmeta['local_path'])
 for name,m in modelmeta['files'].items():
  if sha(modelpath/name)!=m['sha256']:raise ValueError('Base file changed')
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
 import mlx.core as mx
 import mlx.nn as nn
 from mlx_lm import load
 from mlx_lm.models.base import create_attention_mask,create_ssm_mask
 mx.set_memory_limit(19_000_000_000);mx.set_cache_limit(64*1024**2)
 model,tok=load(str(modelpath),trust_remote_code=False);model.eval();model.freeze();mx.eval(model.parameters());base=model.language_model.model
 if len(base.layers)!=64 or base.layers[-1].is_linear:raise ValueError('Pinned final full attention architecture required')
 tail=make_tail(base.layers[-1],base.norm,model.language_model.lm_head)
 examples=[]
 for row in rows:
  e=encode_example(tok,row,8192)
  if tok.decode(e['input_ids'][e['prefix']:])!=row['messages'][2]['content']+'<|im_end|>\n':raise ValueError('Wrong assistant labels')
  key=hashlib.sha256((sha(a.model_manifest)+json.dumps(e['input_ids'])+str(e['prefix'])).encode()).hexdigest()
  examples.append({**e,'key':key,'split':row['split'],'row_sha256':row['sha256']})
 a.cache.mkdir(parents=True,exist_ok=True);a.receipt.parent.mkdir(parents=True,exist_ok=True)
 report={'scope':'frozen_prefix_preparation_no_training','model_manifest_sha256':sha(a.model_manifest),'release_sha256':sha(a.manifest),'code_sha256':sha(Path(__file__)),'test_opened':False,'optimizer_updates':0,'examples':[],'started_unix':time.time()}
 # Validate exact full versus cached loss on the longest reviewed task first.
 examples.sort(key=lambda x:len(x['input_ids']),reverse=True)
 for i,e in enumerate(examples):
  started=time.monotonic();ids=mx.array([e['input_ids'][:-1]]);labels=mx.array([e['input_ids'][1:]])
  if i==0:
   full=base(ids);logits=model.language_model.lm_head(full[:,e['prefix']-1:,:]);loss=nn.losses.cross_entropy(logits.astype(mx.float32),labels[:,e['prefix']-1:],reduction='mean');mx.eval(loss);reference=float(loss.item());del full,logits,loss;mx.clear_cache()
  file=a.cache/(e['key']+'.safetensors');identity=file.with_suffix('.json')
  if file.exists():
   old=json.loads(identity.read_bytes())
   if old['base_sha256']!=sha(a.model_manifest) or old['key']!=e['key'] or old['file_sha256']!=sha(file):raise ValueError('Unverified existing cache')
   h=mx.load(str(file))['hidden'];reused=True
  else:
   h=base.embed_tokens(ids);fa,ssm=create_attention_mask(h,None),create_ssm_mask(h,None)
   for layer in base.layers[:-1]:h=layer(h,mask=ssm if layer.is_linear else fa);mx.eval(h)
   h=mx.stop_gradient(h);mx.eval(h);stage=file.with_suffix('.partial.safetensors');mx.save_safetensors(str(stage),{'hidden':h,'labels':labels});stage.rename(file)
   write(identity,{'key':e['key'],'base_sha256':sha(a.model_manifest),'file_sha256':sha(file),'prefix':e['prefix'],'tokens':len(e['input_ids'])});reused=False
  v=tail_loss(tail,h,labels,e['prefix']);mx.eval(v);nll=float(v.item())
  if i==0:
   delta=abs(nll-reference)
   if delta>1e-5:raise ValueError('New curriculum full/cache loss differs')
   report['longest_full_cached_loss_delta']=delta;report['longest_tokens']=len(e['input_ids'])
  info={**e,'file':str(file),'file_sha256':sha(file),'unadapted_teacher_nll':nll,'seconds':time.monotonic()-started,'reused':reused}
  report['examples'].append(info);write(a.receipt.with_name(a.receipt.stem+'-progress.json'),report)
  print(json.dumps({'completed':i+1,'total':len(examples),'task':e['task_id'],'tokens':len(e['input_ids']),'seconds':info['seconds'],'reused':reused}),flush=True)
  del ids,labels,h,v;mx.clear_cache()
 report.update(status='complete',finished_unix=time.time(),peak_memory_bytes=mx.get_peak_memory());write(a.receipt,report)
if __name__=='__main__':main()
