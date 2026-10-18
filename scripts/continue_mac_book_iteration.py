"""Serialize full-model jobs; stop for source review, never auto-declare all-pass.

The thread heartbeat continues the next reviewed iteration. File receipts retain
all transitions and errors. Existing active cache is allowed to finish first.
"""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'training'))
from epoch_protocol import sha
from cache_mac_curriculum import write

def main():
 p=argparse.ArgumentParser();p.add_argument('--existing-cache-pid',type=int,required=True);p.add_argument('--model-manifest',type=Path,required=True);p.add_argument('--verification-receipt',type=Path,required=True);a=p.parse_args();output=ROOT/'work/book-iteration-v1';output.mkdir(exist_ok=True);state=output/'pipeline.json'
 if state.exists():raise FileExistsError('Do not duplicate an existing pipeline; inspect its live pid and receipts')
 def status(stage,**kw):write(state,{'pid':os.getpid(),'stage':stage,'unix':time.time(),'all_chapter_model_pass':False,'test_opened':False,**kw});print(stage,flush=True)
 status('waiting_for_existing_stage_a_cache')
 stage_a=ROOT/'work/book-method-stage-a-cache.json'
 while not stage_a.exists():
  try:os.kill(a.existing_cache_pid,0)
  except ProcessLookupError:raise RuntimeError('Existing cache exited without completion receipt')
  time.sleep(20)
 if not a.verification_receipt.exists():raise ValueError('Full regression/remote verification receipt missing')
 verified=json.loads(a.verification_receipt.read_bytes())
 if not verified.get('regression_passed') or not verified.get('four_ci_passed') or verified.get('curriculum_sha256')!=sha(ROOT/'data/splits/book_method_curriculum_v1.json'):raise ValueError('Current full release verification missing')
 for name,digest in verified['execution_files'].items():
  if sha(ROOT/name)!=digest:raise ValueError('Verified execution code changed: '+name)
 env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
 def run(stage,script,args):
  status(stage,verification_commit=verified['commit'])
  with (output/(stage+'.log')).open('ab') as log:subprocess.run([sys.executable,str(ROOT/script),*map(str,args)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 cache=ROOT/'work/book-method-curriculum-cache.json';baseline=ROOT/'work/mac-book-method-before-v1';training=ROOT/'work/mac-book-method-lora-v1';after=ROOT/'work/mac-book-method-after-epoch05-v1';cfg=ROOT/'training/mac_book_curriculum_v1.json'
 run('full_curriculum_prefix_cache','training/cache_mac_curriculum.py',['--manifest',ROOT/'data/splits/book_method_curriculum_v1.json','--data',ROOT/'work/book-method-curriculum-v1','--model-manifest',a.model_manifest,'--cache',ROOT/'work/book-method-prefix-cache','--receipt',cache])
 run('unadapted_whole_book_generation','scripts/run_mac_book_method.py',['--config',cfg,'--model-manifest',a.model_manifest,'--output',baseline])
 run('expanded_rank16_training_first_boundary','training/train_mac_book_lora.py',['--config',cfg,'--model-manifest',a.model_manifest,'--cache-receipt',cache,'--baseline',baseline/'report.json','--output',training])
 receipt=training/('report.json' if (training/'report.json').exists() else 'evaluation-boundary.json');report=json.loads(receipt.read_bytes());checkpoint=report['final_state']['best_checkpoint'] or f'epoch-{report["completed_epochs"]:02d}'
 run('package_checkpoint_for_github_release','scripts/package_book_checkpoint.py',['--run',training,'--receipt',receipt])
 run('adapted_whole_book_generation','scripts/run_mac_book_method.py',['--config',cfg,'--model-manifest',a.model_manifest,'--output',after,'--adapter',training/checkpoint])
 status('awaiting_agent_source_review_and_github_model_asset_sync',checkpoint=checkpoint,baseline=str(baseline/'report.json'),adapted=str(after/'report.json'),training_receipt=str(receipt),next_action='Source-audit every response by chapter, publish real checkpoint and records, then resume a new verified iteration or same preregistered run if appropriate. Never use test to tune.')
if __name__=='__main__':
 try:main()
 except BaseException as exc:
  p=ROOT/'work/book-iteration-v1/pipeline.json'
  if p.exists():
   s=json.loads(p.read_bytes());write(p,{**s,'stage':'failed','error_type':type(exc).__name__,'unix':time.time()})
  raise
