"""Whole-case split retention, real service permissions and real optimizer resume."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'training'))
from book_release import build, encoded, sha
from cuda_pilot import encode_example, save_checkpoint, restore_checkpoint, torch_loss
from qimenllm.knowledge.snapshot import restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.contracts import Inquiry, GenerationError
from qimenllm.evaluation.method import MethodRequest, messages_for, check_output, score_task


class BookPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name)/'source.sqlite3'
        restore_snapshot(ROOT/'data/snapshots/current', cls.db, Path(cls.tmp.name)/'raw')
        review = json.loads((ROOT/'data/structured/shenqi/lost_method_task_review_v5.json').read_bytes())
        families = json.loads((ROOT/'data/splits/author_initial_release_v2.json').read_bytes())
        before = cls.db.read_bytes()
        cls.archives, cls.tasks, cls.report = build(cls.db, review, families)
        cls.unchanged = before == cls.db.read_bytes()
        cls.manifest = ROOT/'data/splits/lost_method_release_v5.json'
        cls.dataset = Path(cls.tmp.name)/'tasks'; cls.dataset.mkdir()
        cls.method_tasks = [t for t in cls.tasks if t['task_id'].startswith('method-')]
        cls.supplements = json.loads((ROOT/'data/structured/shenqi/book_source_limits_review_v1.json').read_bytes())
        cls.review, cls.families = review, families
        cls.archives_v2, cls.tasks_v2, cls.report_v2 = build(cls.db, review, families, cls.supplements)
        for split in ('train', 'validation', 'test', 'development'):
            (cls.dataset/(split+'.jsonl')).write_bytes(b''.join(encoded(t) for t in cls.method_tasks if t['split']==split))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_98_complete_stories_frozen_split_and_no_source_writes(self):
        self.assertTrue(self.unchanged)
        self.assertEqual(len(self.archives), 98)
        self.assertEqual(self.report['case_counts'], {'train':65, 'validation':15, 'test':15, 'development':3})
        self.assertEqual(sum(self.report['family_counts'].values()), 94)
        records, charts = set(), set()
        for a in self.archives:
            self.assertFalse(a['allowed_as_model_input'])
            self.assertTrue(a['contains_future_feedback'])
            self.assertNotIn('messages', a)
            self.assertTrue(a['original_story']['text'])
            for e in a['events']:
                self.assertEqual(e['split'], a['split'])
                self.assertEqual(e['split'], self.report['family_assignments'][e['family_id']])
                records.update(r['record_id'] for r in e['records'])
                charts.update(c['chart_id'] for c in e['charts'])
        self.assertEqual((len(records),len(charts)), (1579,104))

    def test_whole_book_frozen_bytes_and_no_label_invention(self):
        manifest = json.loads((ROOT/'data/splits/book_preparation_v1.json').read_bytes())
        self.assertEqual(len(self.tasks),125)
        self.assertEqual(len(self.report['unsupported_charts']),3)
        self.assertEqual(self.report['task_cases'],96)
        for split in ('train','validation','test','development'):
            for prefix, rows in (('cases',self.archives),('tasks',self.tasks)):
                raw = b''.join(encoded(t) for t in rows if t['split']==split)
                self.assertEqual(sha(raw),manifest['files'][prefix+'-'+split+'.jsonl']['sha256'])
        extra = [t for t in self.tasks if t['task_id'].startswith('book-table-')]
        self.assertEqual(len(extra),93)
        for task in extra:
            payload = json.loads(task['messages'][1]['content'])
            self.assertNotIn('known_information',payload)
            self.assertNotIn('original_story',payload)
            self.assertNotIn('palaces',payload['chart'])  # no ready-made JSON target in prompt
            self.assertEqual(task['input_setting'],'literal_table_exercise_not_forecasting')
            self.assertEqual(task['split'],manifest['family_assignments'][task['family_id']])
        self.assertFalse(manifest['all_case_method_reasoning_review_complete'])

    def request(self,task,**changes):
        args = dict(manifest_path=str(self.manifest),manifest_sha256=sha(self.manifest.read_bytes()),
                    data_dir=str(self.dataset),split=task['split'],task_id=task['task_id'])
        args.update(changes)
        return MethodRequest(**args)

    def test_real_ask_has_no_supervision_or_feedback_and_never_claims_professional_success(self):
        task = next(t for t in self.method_tasks if t['split']=='validation' and t['task_type']=='chart_evidence')
        gold = json.loads(task['messages'][2]['content'])
        captured = []
        class Gateway:
            def generate_method(self,messages):
                captured.extend(messages)
                return gold, {'fixture':True}
        result = QimenService(self.db,model=Gateway()).ask(Inquiry(task['task_id']),research=self.request(task))
        self.assertEqual(result['status'],'method_generated')
        self.assertFalse(result['professional_analysis_completed'])
        self.assertIsNone(result['author_method_accuracy'])
        self.assertEqual(len(captured),2)
        self.assertNotIn('supervision_sources',json.dumps(captured))
        score = score_task(task,result)
        self.assertEqual(score['literal_facts_matched'],score['literal_facts_available'])
        self.assertIsNone(score['author_method_semantic_score'])

    def test_future_hidden_context_train_scope_and_changed_split_rejected(self):
        task = next(t for t in self.method_tasks if t['split']=='validation')
        service = QimenService(self.db)
        for inquiry, request in ((Inquiry(task['task_id'],context={'later_result':'known'}),self.request(task)),
                                 (Inquiry(task['task_id']),self.request(task,split='train')),
                                 (Inquiry(task['task_id']),self.request(task,manifest_sha256='0'*64))):
            with self.assertRaises(ValueError):
                service.ask(inquiry,research=request)

    def test_baseline_arms_remove_conditions_and_gold_never_enters_messages(self):
        task = next(t for t in self.method_tasks if t.get('given_condition_sources'))
        original = copy.deepcopy(task)
        for arm in ('base','source_chart','source_chart_knowledge'):
            payload = json.loads(messages_for(task,arm)[1]['content'])
            self.assertNotIn('source_given_conditions',payload)
            self.assertFalse(any(k.startswith('condition-') for k in payload['references']))
            if arm=='base':
                self.assertNotIn('chart',payload)
        self.assertEqual(task,original)

    def test_wrong_chart_claim_and_unknown_citation_are_separate_errors(self):
        task = next(t for t in self.method_tasks if t['task_type']=='chart_evidence')
        payload = json.loads(task['messages'][1]['content'])
        output = json.loads(task['messages'][2]['content'])
        output['observations'][0]['value'] = '不存在的星'
        output['citations'] = ['future-feedback']
        self.assertEqual(set(check_output(output,payload)),{'source_table_fact_mismatch','unavailable_reference'})
        with self.assertRaises(GenerationError):
            check_output({'task_type':'chart_evidence'},payload)

    def test_v2_covers_all_98_stories_without_moving_or_rewriting_prior_tasks(self):
        self.assertEqual(len(self.tasks_v2),127)
        self.assertEqual(self.report_v2['task_cases'],98)
        self.assertEqual(self.report_v2['task_counts'],{'train':82,'validation':21,'test':20,'development':4})
        old={t['task_id']:t for t in self.tasks}
        for t in self.tasks_v2:
            if t['task_id'] in old:self.assertEqual(t,old[t['task_id']])
        self.assertEqual(self.archives_v2,self.archives)
        manifest=json.loads((ROOT/'data/splits/book_preparation_v2.json').read_bytes())
        for split in ('train','validation','test','development'):
            raw=b''.join(encoded(t) for t in self.tasks_v2 if t['split']==split)
            self.assertEqual(sha(raw),manifest['files']['tasks-'+split+'.jsonl']['sha256'])

    def test_partial_source_teaches_explicit_missing_information_without_later_commentary(self):
        task=next(t for t in self.tasks_v2 if t.get('input_setting')=='partial_source_reading')
        payload=json.loads(task['messages'][1]['content'])
        answer=json.loads(task['messages'][2]['content'])
        self.assertFalse(answer['complete_nine_palace_chart'])
        self.assertFalse(task['forecast_evaluation_eligible'])
        self.assertEqual(len(answer['reported_facts']),6)
        self.assertNotIn('palaces',payload)
        text=json.dumps(payload,ensure_ascii=False)
        self.assertNotIn('retrospective_addendum',text)
        self.assertNotIn('木克土，克不动',text)
        for fact in answer['reported_facts']:
            self.assertIn(fact['value'],fact['quote'])
            self.assertIn(fact['quote'],payload['references']['source']['text'])

    def test_user_relayout_36_literal_cells_never_upgrade_original_chart(self):
        task=next(t for t in self.tasks_v2 if t.get('input_setting')=='user_relayout_reading')
        answer=json.loads(task['messages'][2]['content'])
        cells={r['palace']:r['source_cells_as_written'] for r in answer['palaces_as_written']}
        self.assertEqual(sum(len(v) for v in cells.values()),36)
        self.assertEqual(cells[3][2],'门位：生乙')
        self.assertEqual(cells[5][2],'中宫原文：壬')
        self.assertEqual(cells[6][2],'门位：壬惊丙')
        self.assertFalse(task['original_chart_status_upgraded'])
        self.assertFalse(answer['engine_verified'])
        self.assertFalse(task['forecast_evaluation_eligible'])
        self.assertEqual(len(self.report_v2['unsupported_charts']),3)

    def test_forged_supplement_fact_source_family_or_gold_is_rejected(self):
        for change in (
            lambda s:s['rows'][0]['reported_facts'][0].update(value='不存在的干支'),
            lambda s:s['rows'][0].update(excerpt_sha256='0'*64),
            lambda s:s['rows'][0].update(family_id='another-family'),
            lambda s:s['rows'][1].update(gold_sha256='0'*64)):
            altered=copy.deepcopy(self.supplements);change(altered)
            with self.assertRaises(ValueError):build(self.db,self.review,self.families,altered)

    def test_failed_json_keeps_generation_diagnostics(self):
        task = next(t for t in self.method_tasks if t['split']=='validation')
        class Gateway:
            def generate_method(self,messages):
                return {'_generation_error':'truncated'},{'raw_output':'unfinished','finish_reason':'length'}
        result = QimenService(self.db,model=Gateway()).ask(Inquiry(task['task_id']),research=self.request(task))
        self.assertEqual(result['status'],'generation_error')
        self.assertEqual(result['telemetry']['raw_output'],'unfinished')


class AssistantMaskTests(unittest.TestCase):
    class Tokenizer:
        def apply_chat_template(self,messages,**kwargs):
            return ''.join(m['content'] for m in messages)+('ASSISTANT:' if kwargs['add_generation_prompt'] else 'END')
        def encode(self,text,**kwargs):
            return list(text.encode())

    def test_non_prefix_template_is_rejected_instead_of_training_prompt(self):
        with self.assertRaisesRegex(ValueError,'boundary'):
            encode_example(self.Tokenizer(),{'task_id':'x','messages':[
                {'role':'system','content':'s'},{'role':'user','content':'u'},
                {'role':'assistant','content':'a'}]},100)


@unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('peft'),
                     'Optional PyTorch/PEFT runtime unavailable')
class RealTorchResumeTests(unittest.TestCase):
    def test_hybrid_qwen_actual_backward_checkpoint_rng_and_next_update(self):
        import torch
        from transformers import Qwen3_5TextConfig,Qwen3_5ForCausalLM
        from peft import LoraConfig,get_peft_model
        torch.manual_seed(17)
        config = Qwen3_5TextConfig(vocab_size=32,hidden_size=32,intermediate_size=64,
            num_hidden_layers=4,num_attention_heads=2,num_key_value_heads=1,head_dim=16,
            layer_types=['linear_attention']*3+['full_attention'],
            linear_key_head_dim=8,linear_value_head_dim=8,linear_num_key_heads=2,linear_num_value_heads=4,
            max_position_embeddings=64,pad_token_id=0)
        model = get_peft_model(Qwen3_5ForCausalLM(config),LoraConfig(r=2,lora_alpha=4,
            target_modules=['q_proj','v_proj','in_proj_qkv'],lora_dropout=0.0))
        model.train()
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-3)
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer,lambda n: .9**n)
        example = {'input_ids':[1,2,3,4,5,6,7,8],'prefix':5}
        def update():
            loss,n = torch_loss(model,example)
            self.assertEqual(n,3)
            loss.backward();optimizer.step();scheduler.step();optimizer.zero_grad()
            return float(loss.detach())
        update()
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp)/'step-1'
            save_checkpoint(checkpoint,model,optimizer,scheduler,{'epoch':0,'cursor':1,'order':[0,1]},'fixture')
            expected_loss = update()
            expected = {n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad}
            state = restore_checkpoint(checkpoint,model,optimizer,scheduler,'fixture')
            self.assertEqual(state['cursor'],1)
            self.assertAlmostEqual(update(),expected_loss,places=6)
            for name,p in model.named_parameters():
                if p.requires_grad:
                    torch.testing.assert_close(p,expected[name],rtol=0,atol=1e-7)
            with self.assertRaises(ValueError):
                restore_checkpoint(checkpoint,model,optimizer,scheduler,'wrong-code')
