"""Append a whole-book reviewed curriculum, preserving older sources and splits.

The cross-chapter duplicate is quarantined, not moved into another frozen split.
Reference-reading groups are not independent event families or forecasts.
"""
from collections import Counter
import argparse,copy,json,sqlite3
from pathlib import Path
from method_release import build as lost_build,encoded,sha
from book_method_release import build as chapter_build,SYSTEM,INSTRUCTIONS
from book_release import source_limit_tasks
SPLITS=('train','validation','test','development')

def reference_tasks(con,review,version):
 if review.get('schema')!='book-foundation-semantic-review-v1' or review.get('source_data_version')!=version or review.get('reviewed_by')!='Codex source-grounded semantic curation':raise ValueError('Unreviewed foundation')
 result=[]
 for item in review['rows']:
  row=con.execute('select d.content,d.sha256,ch.chapter_key from raw_documents d join chapter_revisions r using(document_id) join chapters ch using(chapter_id) where r.revision_id=?',(item['revision_id'],)).fetchone()
  if row is None or row['chapter_key']!=item['chapter'] or sha(row['content'])!=item['document_sha256'] or row['sha256']!=item['document_sha256']:raise ValueError('Reference document changed')
  a,b=item['byte_start'],item['byte_end'];raw=row['content'][a:b]
  if not 0<=a<b<=len(row['content']) or sha(raw)!=item['excerpt_sha256']:raise ValueError('Reference selector changed')
  if con.execute('select 1 from cases ca join source_spans s on s.source_id=ca.source_id where s.revision_id=? and s.byte_start<? and s.byte_end>?',(item['revision_id'],b,a)).fetchone():raise ValueError('Foundation selected a case narrative')
  # The clean learning appendix quotes validation lottery in a new revision;
  # those duplicate case quotations must stay archived, never train as prose.
  if item['chapter']=='appendix-learning-clean':
   boundary=row['content'].decode().index('为说明一用就灵')
   if b>len(row['content'].decode()[:boundary].encode()):raise ValueError('Learning appendix quoted outcomes forbidden')
  if item.get('split')!='train' or item.get('mode')!='reference_reading' or not item.get('review_note'):raise ValueError('Reference-reading scope')
  ref={k:item[k] for k in ('revision_id','document_sha256','byte_start','byte_end','excerpt_sha256')};ref.update(text=raw.decode(),selection_kind='manually_reviewed_reference_subspan')
  answer=item['answer']
  if answer.get('task_type')!='source_knowledge' or answer.get('citations')!=['source'] or not answer.get('explanation') or not isinstance(answer.get('uncertainties'),list):raise ValueError('Reference answer invalid')
  payload={'task_type':'source_knowledge','instruction':item['question']+' 输出task_type、explanation、citations、uncertainties。','references':{'source':{'text':ref['text'],'scope':'supplied_source_reading_not_predictive_outcome'}},'scope':'reference_reading_not_forecasting','context_mode':'reference_reading'}
  task={'task_id':'bookknowledge-'+sha(item['key'].encode())[:24],'task_type':'source_knowledge','chapter':item['chapter'],'case_id':None,'event_id':None,'chart_id':None,'family_id':'reference-document-'+item['document_sha256'],'split':'train','context_mode':'reference_reading','source_data_version':version,'input_sources':[ref],'supervision_sources':[ref],'forecast_evaluation_eligible':False,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False)},{'role':'assistant','content':json.dumps(answer,ensure_ascii=False)}]}
  task['sha256']=sha(encoded(task));result.append(task)
 return result

def isolate(tasks,ledger,con,assignments):
 if ledger.get('original_database_or_frozen_assignments_modified') is not False or len(ledger.get('source_rows',[]))!=2:raise ValueError('Duplicate source review missing')
 for row in ledger['source_rows']:
  actual=con.execute('select * from case_records where record_id=? and event_id=?',(row['record_id'],row['event_id'])).fetchone()
  event=con.execute('select family_id from events where event_id=?',(row['event_id'],)).fetchone()
  if actual is None or actual['source_id']!=row['source_id'] or actual['text']!=row['text'] or sha(actual['text'].encode())!=row['text_sha256'] or event['family_id']!=row['family_id']:raise ValueError('Duplicate review source changed')
 excluded=set(ledger['excluded_training_families'])
 if any(assignments.get(f)!='train' for f in excluded) or assignments.get(ledger['retained_validation_family'])!='validation':raise ValueError('Duplicate isolation owner changed')
 retained=[];quarantine=[]
 for task in tasks:
  if task['family_id'] in excluded:
   if task['split']!='train':raise ValueError('Unexpected duplicate split')
   quarantine.append({**task,'allowed_for_training':False,'quarantine_reason':'same_underlying_event_as_frozen_validation_family'})
  else:retained.append(task)
 if not quarantine:raise ValueError('Required duplicate exclusion not exercised')
 return retained,quarantine

def build(db,chapter_files,lost_review,families,foundation,limits,isolation):
 tasks,report=chapter_build(db,chapter_files,families);version=report['source_data_version']
 old,_=lost_build(db,lost_review,families)
 for original in old:
  t=copy.deepcopy(original);t['task_id']='booklost-'+original['task_id'];t['derived_from_task_id']=original['task_id'];t['chapter']='lost-property'
  u=json.loads(t['messages'][1]['content']);u['chart'].pop('raw_text',None);u['chart'].pop('chart_id',None);u['scope']='source_conditioned_historical_method_exercise';u['context_mode']=t['context_mode'];u['instruction']=INSTRUCTIONS[t['task_type']]
  a=json.loads(t['messages'][2]['content']);answer={'task_type':a.pop('task_type'),**a}
  t['messages']=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(u,ensure_ascii=False)},{'role':'assistant','content':json.dumps(answer,ensure_ascii=False)}];tasks.append(t)
 c=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 try:
  extra=source_limit_tasks(c,limits,families['family_assignments'],version)
  for t in extra:
   t['task_id']='curriculum-'+t['task_id'];t['context_mode']='source_reading';t['chapter']='application-overview' if t['input_setting']=='partial_source_reading' else 'appendix-demo-clean'
  tasks.extend(extra);tasks.extend(reference_tasks(c,foundation,version))
  reviewed_cases={t['case_id'] for t in tasks if t['case_id']};actual_cases={r[0] for r in c.execute('select case_id from cases')}
  if reviewed_cases!=actual_cases:raise ValueError('Unreviewed case stories remain')
  tasks,quarantine=isolate(tasks,isolation,c,families['family_assignments'])
  chapters={r['chapter_key']:{'title':r['title'],'task_counts':{},'modes':{},'unseen_validation_families':0,'model_pass':None} for r in c.execute('select * from chapters')}
 finally:c.close()
 assignments=dict(families['family_assignments']);reference_groups={t['family_id']:'train' for t in tasks if t['event_id'] is None};assignments.update(reference_groups)
 for t in tasks:
  t.pop('sha256',None);t['chapter']=t['chapter'][3:] if t['chapter'][:2].isdigit() and t['chapter'][2:3]=='-' else t['chapter']
  if t['event_id'] is not None:t['forecast_evaluation_eligible']=t['context_mode'] in ('initial','source_conditioned')
  t['sha256']=sha(encoded(t))
 if len({t['task_id'] for t in tasks})!=len(tasks):raise ValueError('Duplicate task IDs')
 for ch,data in chapters.items():
  rows=[t for t in tasks if t['chapter']==ch];data.update(task_counts=dict(Counter(t['split'] for t in rows)),modes=dict(Counter(t['context_mode'] for t in rows)),unseen_validation_families=len({t['family_id'] for t in rows if t['split']=='validation' and t['event_id'] is not None}),forecast_validation_tasks=sum(t['split']=='validation' and t['forecast_evaluation_eligible'] for t in rows))
  if not rows:raise ValueError('Chapter input missing '+ch)
 report={'release_id':'shenqi-book-method-curriculum-v1','scope':'reviewed_book_method_curriculum','frozen':True,'source_data_version':version,'family_assignments':assignments,'original_event_family_assignments':families['family_assignments'],'reference_document_groups':reference_groups,'excluded_training_families':isolation['excluded_training_families'],'quarantined_tasks':len(quarantine),'case_stories_source_reviewed':len(reviewed_cases),'case_stories_in_retained_tasks':len({t['case_id'] for t in tasks if t['case_id']}),'source_inputs_with_tasks':len(chapters),'task_count':len(tasks),'task_counts':dict(Counter(t['split'] for t in tasks)),'task_types':dict(Counter(t['task_type'] for t in tasks)),'context_modes':dict(Counter(t['context_mode'] for t in tasks)),'chapter_coverage':chapters,'all_book_professional_ready':False,'formal_system_validated':False,'all_chapter_model_pass':False,'test_inference_accessed':False,'independent_real_world_accuracy':None,'notes':['All98 stories have source review; mixed source critique and literal reading are not independent forecasts.','Reference knowledge train diagnostics do not establish unseen family generalization.','All older source bytes and split assignments are preserved; cross-split duplicate is quarantined only in this new curriculum.']}
 return tasks,quarantine,report

def export(db,chapter_files,lost,families,foundation,limits,isolation,output,manifest):
 if output.exists() or manifest.exists():raise FileExistsError('Append new release version')
 paths=[*chapter_files,lost,families,foundation,limits,isolation];values=[json.loads(Path(p).read_bytes()) for p in (lost,families,foundation,limits,isolation)]
 tasks,quarantine,report=build(db,chapter_files,*values);report['review_files']={str(p):sha(Path(p).read_bytes()) for p in paths};report['export_code_sha256']=sha(Path(__file__).read_bytes());report['files']={};output.mkdir(parents=True)
 for split in SPLITS:
  raw=b''.join(encoded(t) for t in tasks if t['split']==split);name=split+'.jsonl';(output/name).write_bytes(raw);report['files'][name]={'sha256':sha(raw),'bytes':len(raw),'tasks':sum(t['split']==split for t in tasks)}
 raw=b''.join(encoded(t) for t in quarantine);(output/'quarantine.jsonl').write_bytes(raw);report['quarantine_file']={'sha256':sha(raw),'tasks':len(quarantine),'allowed_as_model_input':False};manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_bytes(encoded(report));return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--reviews',type=Path,nargs='+',required=True);p.add_argument('--lost',type=Path,required=True);p.add_argument('--families',type=Path,required=True);p.add_argument('--foundation',type=Path,required=True);p.add_argument('--limits',type=Path,required=True);p.add_argument('--isolation',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();r=export(a.db,a.reviews,a.lost,a.families,a.foundation,a.limits,a.isolation,a.output,a.manifest);print(json.dumps({k:r[k] for k in ('release_id','task_count','task_counts','quarantined_tasks','source_inputs_with_tasks','case_stories_source_reviewed')},ensure_ascii=False))
