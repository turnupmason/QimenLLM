"""Source-level adversarial boundaries and whole-book research service checks."""
import copy,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'training'))
from book_curriculum_release import build,reference_tasks,isolate
from book_method_release import build as chapter_build
from method_release import encoded,sha
from cache_mac_curriculum import selected_rows
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.evaluation.book_method import BookMethodRequest,check_book_output,load_task
from qimenllm.reasoning.service import QimenService
from qimenllm.contracts import Inquiry,GenerationError

class BookCurriculumTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.db=Path(cls.tmp.name)/'db.sqlite3';restore_snapshot(ROOT/'data/snapshots/current',cls.db,Path(cls.tmp.name)/'raw')
  cls.files=sorted(Path('data/structured/shenqi').glob('book_method_review_*_v1.json'))
  cls.paths=[Path('data/structured/shenqi/lost_method_task_review_v5.json'),Path('data/splits/lost_method_release_v5.json'),Path('data/structured/shenqi/book_foundation_review_v1.json'),Path('data/structured/shenqi/book_source_limits_review_v1.json'),Path('data/provenance/book_method_duplicate_isolation_v1.json')]
  cls.values=[json.loads(p.read_bytes()) for p in cls.paths];before=cls.db.read_bytes();cls.tasks,cls.quarantine,cls.report=build(cls.db,cls.files,*cls.values);cls.unchanged=before==cls.db.read_bytes();cls.manifest=ROOT/'data/splits/book_method_curriculum_v1.json';cls.data=Path(cls.tmp.name)/'data';cls.data.mkdir()
  for split in ('train','validation','development','test'):(cls.data/(split+'.jsonl')).write_bytes(b''.join(encoded(t) for t in cls.tasks if t['split']==split))
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def request(self,t,**changes):
  d=dict(manifest_path=str(self.manifest),manifest_sha256=sha(self.manifest.read_bytes()),data_dir=str(self.data),task_id=t['task_id'],split=t['split']);d.update(changes);return BookMethodRequest(**d)
 def test_all_stories_inputs_and_frozen_bytes_with_read_only_db(self):
  self.assertTrue(self.unchanged);self.assertEqual((self.report['case_stories_source_reviewed'],self.report['source_inputs_with_tasks'],len(self.tasks)),(98,26,391));self.assertEqual(len(self.quarantine),3)
  meta=json.loads(self.manifest.read_bytes())
  for split in ('train','validation','development','test'):self.assertEqual(sha((self.data/(split+'.jsonl')).read_bytes()),meta['files'][split+'.jsonl']['sha256'])
  self.assertFalse(meta['all_chapter_model_pass']);self.assertFalse(meta['formal_system_validated']);self.assertEqual(len(meta['original_event_family_assignments']),94)
 def test_duplicate_isolation_not_cross_split_reassignment(self):
  old=self.values[1]['family_assignments'];bad=set(self.values[4]['excluded_training_families'])
  self.assertFalse(any(t['family_id'] in bad for t in self.tasks));self.assertTrue(all(t['split']=='train' and not t['allowed_for_training'] for t in self.quarantine))
  for t in self.tasks:
   if t['event_id']:self.assertEqual(t['split'],old[t['family_id']])
  self.assertEqual(self.report['case_stories_in_retained_tasks'],97)
 def test_source_reading_and_no_unseen_families_are_not_forecast_pass(self):
  self.assertTrue(all(not t['forecast_evaluation_eligible'] for t in self.tasks if t['context_mode'] in ('retrospective','source_reading','reference_reading')))
  self.assertEqual(self.report['chapter_coverage']['education-examinations']['unseen_validation_families'],0)
  self.assertTrue(all(c['model_pass'] is None for c in self.report['chapter_coverage'].values()))
 def test_all_curated_outputs_have_required_schema_and_literal_facts(self):
  for t in self.tasks:
   p=json.loads(t['messages'][1]['content']);a=json.loads(t['messages'][2]['content']);self.assertEqual(check_book_output(a,p),[],t['task_id']);self.assertNotIn('supervision_sources',p)
 def test_service_only_receives_two_messages_and_no_success_claim(self):
  t=next(t for t in self.tasks if t['split']=='validation' and t['task_type']=='chart_evidence');captured=[]
  class Gateway:
   def generate_method(self,m):captured.extend(m);return json.loads(t['messages'][2]['content']),{}
  result=QimenService(self.db,model=Gateway()).ask(Inquiry(t['task_id']),research=self.request(t));self.assertEqual(len(captured),2);self.assertEqual(result['status'],'method_generated');self.assertFalse(result['professional_analysis_completed']);self.assertIsNone(result['independent_real_world_accuracy'])
 def test_train_and_test_scope_and_inquiry_future_context_rejected(self):
  for split in ('train','test'):
   t=next(t for t in self.tasks if t['split']==split)
   with self.assertRaises(ValueError):load_task(self.request(t),self.db)
  t=next(t for t in self.tasks if t['split']=='train' and t['event_id'] is None);self.assertEqual(load_task(self.request(t,seen_training_diagnostic=True),self.db)['task_id'],t['task_id'])
  t=next(t for t in self.tasks if t['split']=='validation')
  with self.assertRaises(ValueError):QimenService(self.db).ask(Inquiry(t['task_id'],context={'future':'result'}),research=self.request(t))
 def test_missing_specialized_fields_and_wrong_prefix_are_rejected(self):
  for kind,field in [('role_selection','bindings'),('chart_evidence','observations'),('timing_analysis','methods')]:
   t=next(t for t in self.tasks if t['task_type']==kind);p=json.loads(t['messages'][1]['content']);a=json.loads(t['messages'][2]['content']);a.pop(field)
   with self.assertRaises(GenerationError):check_book_output(a,p)
  t=next(t for t in self.tasks if t['task_type']=='chart_evidence' and 'palaces' in json.loads(t['messages'][1]['content']).get('chart',{}));p=json.loads(t['messages'][1]['content']);a=json.loads(t['messages'][2]['content']);a['observations'][0]['value']='虚构';a['observations'][0]['citation']='future';errors=check_book_output(a,p);self.assertIn('source_table_fact_mismatch',errors);self.assertIn('literal_field_or_citation_invalid',errors)
 def changed_chapter(self,change):
  review=json.loads(self.files[1].read_bytes());change(review)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'changed.json';p.write_bytes(encoded(review));return chapter_build(self.db,[p],self.values[1])
 def test_future_input_cannot_be_granted_by_unknown_phase_note(self):
  def change(r):r['rows'][0]['known'][0]['sequence']=r['rows'][0]['cutoff']
  with self.assertRaises(ValueError):self.changed_chapter(change)
 def test_wrong_event_chart_and_tampered_source_permission_rejected(self):
  with self.assertRaises(ValueError):self.changed_chapter(lambda r:r['rows'][0].update(chart_id='other-case-chart'))
  with self.assertRaises(ValueError):self.changed_chapter(lambda r:r['rows'][0]['known'][0].update(sha256='0'*64))
 def test_foundation_cannot_repackage_clean_appendix_validation_story(self):
  review=copy.deepcopy(self.values[2]);row=next(r for r in review['rows'] if r['chapter']=='appendix-learning-clean')
  with sqlite3.connect(self.db) as c:
   c.row_factory=sqlite3.Row;raw=c.execute('select d.content from raw_documents d join chapter_revisions r using(document_id) where r.revision_id=?',(row['revision_id'],)).fetchone()[0];row.update(byte_end=len(raw),excerpt_sha256=sha(raw[row['byte_start']:]))
   with self.assertRaisesRegex(ValueError,'quoted outcomes'):reference_tasks(c,review,self.report['source_data_version'])
 def test_cache_preparation_never_opens_test_or_quarantine(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   for split in ('train','validation'):(p/(split+'.jsonl')).write_bytes((self.data/(split+'.jsonl')).read_bytes())
   rows,_=selected_rows(self.manifest,p);self.assertEqual(len(rows),325);self.assertTrue(all(t['split'] in ('train','validation') for t in rows));self.assertFalse(any(t['family_id'] in self.report['excluded_training_families'] for t in rows))
 def test_known_weather_subspan_excludes_external_divination_answer(self):
  weather=[t for t in self.tasks if t['chapter']=='weather-prediction' and any(r.get('selection_kind')=='reviewed_subspan' for r in t['input_sources'])];self.assertTrue(weather)
  for t in weather:
   q=[r for r in t['input_sources'] if r.get('selection_kind')=='reviewed_subspan'][0];self.assertIn('提前8天',q['text']);self.assertNotIn('在课上',q['text']);self.assertEqual(sha(q['text'].encode()),q['excerpt_sha256'])
 def test_whole_book_evaluation_selector_never_opens_test(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('wholebook_run',ROOT/'scripts/run_mac_book_method.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   for split in ('train','validation','development'):(p/(split+'.jsonl')).write_bytes((self.data/(split+'.jsonl')).read_bytes())
   rows=mod.select_tasks(self.manifest,p);self.assertEqual(len({t['chapter'] for t in rows}),26);self.assertFalse(any(t['split']=='test' for t in rows));self.assertEqual(sum(t['split']=='validation' for t in rows),60)
 def test_actual_future_feedback_cannot_be_reclassified_as_known_source(self):
  def change(review):
   row=next(r for r in review['rows'] if r['mode'] in ('initial','source_conditioned'))
   with sqlite3.connect(self.db) as c:
    c.row_factory=sqlite3.Row;r=c.execute("select * from case_records where event_id=? and kind in ('feedback','outcome') order by sequence limit 1",(row['event_id'],)).fetchone()
   row['known'].append({'record_id':r['record_id'],'source_id':r['source_id'],'sequence':r['sequence'],'sha256':sha(r['text'].encode())});row['known']=sorted(row['known'],key=lambda r:r['sequence']);row['cutoff']=r['sequence']+1;row['known_source_window_review']='不能用说明文字将真实反馈冒充初断信息。'
  with self.assertRaisesRegex(ValueError,'Initial context phase'):self.changed_chapter(change)
 def test_train_preflight_rejects_missing_baseline_before_loading_mlx(self):
  from train_mac_book_lora import preflight
  c=json.loads((ROOT/'training/mac_book_curriculum_v1.json').read_bytes())
  with tempfile.TemporaryDirectory() as d:
   base=Path(d)/'base.json';base.write_text(json.dumps({'revision':c['base_revision']}))
   with self.assertRaisesRegex(ValueError,'preflight'):preflight(c,{}, {},self.manifest,self.data,base)
 def test_model_package_roundtrips_all_epochs_and_latest_resume_state(self):
  import importlib.util,zipfile
  spec=importlib.util.spec_from_file_location('book_package',ROOT/'scripts/package_book_checkpoint.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'fixture';run.mkdir();names=('adapters.safetensors','adapter_config.json','tail-adapters.safetensors','optimizer.npz','rng.npz')
   for epoch in (1,2):
    folder=run/f'epoch-{epoch:02d}';folder.mkdir()
    for name in names:(folder/name).write_bytes(f'fixture-{epoch}-{name}'.encode())
    (folder/'state.json').write_bytes(encoded({'files':{n:sha((folder/n).read_bytes()) for n in names}}))
   (run/'identity.json').write_bytes(encoded({'fixture':True}));(run/'latest.json').write_bytes(encoded({'checkpoint':'epoch-02'}));receipt=run/'evaluation-boundary.json';receipt.write_bytes(encoded({'completed_epochs':2,'optimizer_steps':4}));record=mod.package(run,receipt)
   self.assertIn('epoch-01/adapters.safetensors',record['files']);self.assertIn('epoch-02/optimizer.npz',record['files']);self.assertNotIn('epoch-01/optimizer.npz',record['files']);self.assertEqual(record['scope'],'local_model_package_not_upload');self.assertTrue(record['github_upload_status'].startswith('pending'))
   with zipfile.ZipFile(record['archive']) as z:self.assertEqual(z.read('epoch-02/optimizer.npz'),(run/'epoch-02/optimizer.npz').read_bytes())
   with self.assertRaises(FileExistsError):mod.package(run,receipt)
 def test_model_package_rejects_corrupted_checkpoint(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('book_package_bad',ROOT/'scripts/package_book_checkpoint.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  with tempfile.TemporaryDirectory() as d:
   run=Path(d);folder=run/'epoch-01';folder.mkdir();(folder/'adapters.safetensors').write_bytes(b'changed');(folder/'state.json').write_bytes(encoded({'files':{'adapters.safetensors':'0'*64}}));(run/'latest.json').write_bytes(encoded({'checkpoint':'epoch-01'}));receipt=run/'report.json';receipt.write_bytes(encoded({}))
   with self.assertRaisesRegex(ValueError,'Checkpoint changed'):mod.package(run,receipt)
if __name__=='__main__':unittest.main()
