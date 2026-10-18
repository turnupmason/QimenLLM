"""Composite appendix source fidelity, duplicate grouping and demonstration chronology."""
import copy
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cases.ingestion import import_cases
from qimenllm.evaluation.metrics import summarize
from qimenllm.knowledge.db import APPEND_ONLY, connect, digest
from qimenllm.knowledge.importer import ImportConflict
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.knowledge.appendix import APPENDIX_SHA
from qimenllm.reasoning.service import QimenService
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_shenqi_appendix as importer


class AppendixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.path = Path(cls.tmp.name)
        cls.db, cls.raw = cls.path/'appendix.sqlite3', cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current', cls.db, cls.raw)
        with connect(cls.db) as c:
            cls.before = {t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY+('books','chapters','dataset_releases')}
        cls.args = {'dun':'阳遁','bureau':2,'hour_ganzhi':'辛卯','method':'shenqi_ch2_paper_v1'}
        cls.before_chart = QimenService(cls.db).calculate('symbolic_chart', cls.args)
        cls.result = importer.ingest(cls.db, cls.raw)
        d = ROOT/'data/structured/shenqi'
        for name in ('curated','cases','gold','source_links','rule_candidates'):
            setattr(cls,name,json.loads((d/f'appendix_{name}.json').read_bytes()))
        cls.source = importer.UPLOAD.read_bytes(); cls.svc = QimenService(cls.db)
        cls.catalog = cls.svc.cases('appendix-bundle')['cases']

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def record(self,event,line):
        return next(r for r in self.cases['cases'][0]['events'][event]['records'] if r['source_lines'][0] == line)

    def group(self,key): return next(g for g in self.curated['groups'] if g['key']=='appendix_'+key)

    def test_exact_source_crlf_tabs_and_all_source_selectors(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(APPENDIX_SHA,48021,276))
        self.assertEqual(self.source.count(b'\r\n'),276)
        self.assertEqual(self.source.count(b'\n'),276)
        def walk(v):
            if isinstance(v,dict):
                if 'source_sha256' in v: self.assertEqual(v['source_sha256'],APPENDIX_SHA)
                if {'byte_start','byte_end'} <= v.keys():
                    self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),v.get('source_quote',v.get('text')))
                for child in v.values(): walk(child)
            elif isinstance(v,list):
                for child in v: walk(child)
        for v in (self.curated,self.cases,self.source_links):walk(v)

    def test_contexts_cover_complete_input_and_three_article_authors(self):
        covered=[]
        for g in self.curated['groups']:
            covered.extend(range(g['line_start'],g['line_end']+1))
            a,b=g['line_start'],g['line_end']
            self.assertEqual(g['dataset']['rows'][0]['source_quote'],b''.join(self.source.splitlines(keepends=True)[a-1:b]).decode())
        self.assertEqual(covered,list(range(1,277)))
        self.assertIn('张志春',self.group('teaching_heading')['dataset']['rows'][0]['source_quote'])
        self.assertIn('宛北布衣',self.group('biography_heading')['dataset']['rows'][0]['source_quote'])
        self.assertIn('杜新会',self.group('demo_heading')['dataset']['rows'][0]['source_quote'])

    def test_overlapping_accuracy_and_afterword_are_only_layout_variants(self):
        lines=self.source.decode().splitlines(keepends=True)
        for link in self.source_links['links'][:2]:
            old=(ROOT/'data/provenance/uploads'/(link['existing_source_sha256']+'.utf8')).read_bytes().decode()
            p=link['new_source_selector'];exclude=link['derivative_comparison']['excluded_new_source_lines']
            new=''.join(lines[n-1] for n in range(p['line_start'],p['line_end']+1) if n not in exclude)
            self.assertEqual(re.sub(r'\s+','',old),re.sub(r'\s+','',new))
            self.assertFalse(link['existing_source_modified'])
            self.assertEqual(link['derivative_comparison']['lexical_differences'],[])

    def test_three_existing_case_summaries_resolve_to_real_unchanged_families(self):
        links=self.source_links['links'][2:]
        self.assertEqual([l['existing_case_key'] for l in links],['business-case-12','employment-election19961027','lost-case-07'])
        with connect(self.db) as c:
            for link in links:
                family='family-'+digest(json.dumps(link['existing_family']['family_key'],ensure_ascii=False,separators=(',',':')).encode())
                row=c.execute('SELECT description FROM event_families WHERE family_id=?',(family,)).fetchone()
                self.assertEqual(row[0],link['existing_family']['description'])
                self.assertFalse(link['new_case_created']);self.assertFalse(link['new_event_created'])
        self.assertEqual(len(self.catalog),1)
        self.assertIn('张××',self.group('election_occurrence')['dataset']['rows'][0]['source_quote'])

    def test_four_barriers_three_principles_and_explicit_conventions(self):
        text=self.group('four_barriers')['dataset']['rows'][0]['source_quote']
        for phrase in ('定局难','起局难','断卦难','定应期更难'): self.assertIn(phrase,text)
        text=self.group('teaching_principles')['dataset']['rows'][0]['source_quote']
        for phrase in ('化繁为简','去伪存真','规范统一','头脑清醒','有章可循','一学就懂'): self.assertIn(phrase,text)
        self.assertFalse(self.group('bureau_convention')['assessment']['existing_method_defaults_changed'])
        a=self.group('casting_convention')['assessment']
        self.assertEqual(a['author_method_tuple'],['时家奇门','排宫法','中五宫一律寄坤二宫','天盘八神'])
        self.assertTrue(a['demo_casting_method_not_inferred_from_general_preference'])

    def test_learning_time_claim_keeps_prior_knowledge_condition(self):
        text=self.group('casting_convention')['dataset']['rows'][0]['source_quote']
        for phrase in ('五十分钟','已有奇门其他方面的基础知识','五个小时'):self.assertIn(phrase,text)
        self.assertIn('已有',self.group('casting_convention')['assessment']['learning_time_scope']['fifty_minutes'])

    def test_biography_six_theses_and_incomplete_tail_preserved(self):
        a=self.group('six_theses')['assessment']
        self.assertEqual(a['theses_as_written'],['天人合一论','太极阴阳论','五行关系论','时空统一论','宇宙全息论','穷通分合论'])
        self.assertFalse(a['compiled_as_physical_science'])
        self.assertIn('代表人物之\r\n',self.group('biography_background')['dataset']['rows'][0]['source_quote'])
        for name in ('碧波','东方碧珠','东君','慈圣'):self.assertIn(name,self.group('biography_ending')['dataset']['rows'][0]['source_quote'])

    def test_complete_joint_story_two_events_one_family_one_unique_source_diagram(self):
        c=self.cases['cases'][0];self.assertEqual(c['source_ranges'],[[172,276]])
        self.assertEqual(len(c['events']),2);self.assertEqual(len(self.catalog[0]['events']),2)
        with connect(self.db) as db:
            ids=[e['event_id'] for e in self.catalog[0]['events']]
            families=[db.execute('SELECT family_id FROM events WHERE event_id=?',(eid,)).fetchone()[0] for eid in ids]
        self.assertEqual(len(set(families)),1)
        charts=[e['charts'][0] for e in c['events']]
        self.assertEqual(len({ch['payload']['shared_source_diagram_id'] for ch in charts}),1)
        self.assertEqual(len({ch['chart_key'] for ch in charts}),2)

    def test_literal_chart_gold_and_same_id_storage_do_not_infer_nine_palaces(self):
        expected=''.join(self.gold['literal_lines'])
        self.assertEqual(expected,b''.join(self.source.splitlines(keepends=True)[240:254]).decode())
        self.assertIn('壬\t合  死戊\r\n',expected)
        full=self.svc.case(self.catalog[0]['case_id'],'full')
        for e in full['events']:
            for ch in e['charts']:
                p=ch['chart'];self.assertEqual(p['raw_chart_text'],expected)
                self.assertIsNone(p['palaces']);self.assertFalse(p['engine_verified'])
                r=self.svc.case_chart(self.catalog[0]['case_id'],ch['chart_id'])
                self.assertEqual((r['status'],r['chart_id']),('not_covered',ch['chart_id']))

    def test_publication_first_quantity_then_titles_and_existing_opinion(self):
        self.assertEqual(self.record(0,194)['knowledge_phase'],'prediction')
        self.assertNotIn('中国方术大师传奇',self.record(0,194)['text'])
        self.assertIn('中国方术大师传奇',self.record(0,195)['text'])
        self.assertIn('根本没听清',self.record(0,197)['text'])
        self.assertEqual(self.record(0,200)['kind'],'feedback')
        self.assertIn('already existed',self.record(0,200)['payload']['confirmation_scope'])

    def test_letter_direction_differs_from_original_suggestion_and_2000_note_is_later(self):
        self.assertEqual(self.record(0,199)['payload']['directions_as_written'],['北方','东北方','南方要钱'])
        letter=self.record(0,222)
        self.assertEqual(letter['payload']['letter_date_as_written'],'1998年9月18日')
        self.assertTrue(letter['payload']['does_not_overwrite_live_north_or_northeast_suggestion'])
        later=self.record(0,276);self.assertEqual((later['kind'],later['knowledge_phase']),('outcome','post_feedback'))
        self.assertEqual(later['payload']['published_title_as_written'],'中国异人传奇')
        self.assertEqual(later['payload']['publication_date_as_written'],'2000年2月')
        self.assertIn('first manuscript publication only',later['payload']['confirmation_scope'])

    def test_initial_court_rejection_not_erased_by_car_accident_continuation(self):
        first=self.record(1,210);self.assertEqual(first['knowledge_phase'],'prediction')
        self.assertIn('官讼',first['text'])
        denied=self.record(1,211);self.assertTrue(denied['payload']['initial_forecast_rejected_as_written'])
        next_forecast=self.record(1,213)
        self.assertEqual((next_forecast['kind'],next_forecast['knowledge_phase']),('continuation','post_feedback'))
        self.assertEqual(next_forecast['payload']['known_feedback_record_keys'],[denied['record_key']])
        feedback=self.record(1,214);self.assertIn('第八根肋条骨折',feedback['text'])
        self.assertEqual(feedback['payload']['occurrence_time_as_written'],'今年二月初四')

    def test_partial_money_feedback_and_postsession_deaths_are_separate(self):
        r=self.record(1,236)
        self.assertEqual(r['payload']['reported_financial_loss_as_written'],'三千元左右')
        self.assertFalse(r['payload']['initial_litigation_and_junior_cause_confirmed'])
        self.assertEqual(self.record(1,237)['knowledge_phase'],'post_feedback')
        self.assertNotIn('死了两个人',self.record(1,213)['text'])
        self.assertEqual(self.record(1,238)['payload']['deaths_as_written'],2)
        self.assertEqual(self.record(1,238)['payload']['injuries_as_written'],3)

    def test_retrospective_numbered_reasoning_never_enters_initial_view(self):
        for event,starts in [(0,[258,263,265]),(1,[270,274])]:
            for n in starts:self.assertEqual(self.record(event,n)['knowledge_phase'],'post_feedback')
        v=self.svc.case(self.catalog[0]['case_id'],'before_prediction')
        self.assertFalse(v['training_export'])
        for e in v['events']:
            self.assertFalse(e['charts'])
            self.assertTrue(all(r['knowledge_phase']=='pre_prediction' for r in e['records']))
        s=json.dumps(v,ensure_ascii=False)
        for term in ('张贵河','王成周','三千元','第八根肋条','2000年2月','中国异人传奇','死俩伤仨','天盘癸'):
            self.assertNotIn(term,s)

    def test_candidates_use_real_sql_conditions_without_formal_activation(self):
        for gold in self.gold['condition_cases']:
            r=self.svc.rule_candidates(gold['context'],domain='live_demo',method='shenqi_appendix_reference_v1')
            self.assertEqual(r['candidate_count'],2)
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),gold['applicable'])
            self.assertEqual(r['role_bindings'],[])
            self.assertTrue(all(c['activation_status']=='reference_only' for c in r['candidates']))

    def test_existing_cli_wsgi_case_chart_and_learning_routes(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        self.assertEqual(len(call('/v1/cases',{'chapter_key':'appendix-bundle'})['cases']),1)
        for e in self.catalog[0]['events']:
            for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':self.catalog[0]['case_id'],'chart_id':cid})['status'],'not_covered')
        r=call('/v1/reference',{'family':'appendix_casting_convention_reference','filters':{}})
        self.assertEqual(r['total'],1);self.assertIn('已有奇门其他方面的基础知识',r['entries'][0]['record']['source_quote'])
        r=call('/v1/learn',{'term':'五十分钟'})
        self.assertTrue(any(b['payload'].get('key')=='appendix_casting_convention' for b in r['knowledge_blocks']))
        out=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','appendix-bundle'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(len(json.loads(out.stdout)['cases']),1)

    def test_old_rows_replay_source_guard_immutable_manifest_and_calculator(self):
        with connect(self.db) as c:
            for t,old in self.before.items():
                current=[tuple(r) for r in c.execute('SELECT * FROM '+t)]
                self.assertTrue(all(row in current for row in old),t)
            n=c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rules').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0],0)
        result=importer.ingest(self.db,self.raw);self.assertTrue(result['cases']['duplicate']);self.assertTrue(result['candidates']['duplicate'])
        with connect(self.db) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],n)
        bad=copy.deepcopy(self.cases);bad['cases'][0]['title']='changed'
        with self.assertRaises(ImportConflict):import_cases(self.db,self.result['source']['revision_id'],bad)
        p=self.path/'bad.txt';p.write_bytes(self.source.replace(b'\r\n',b'\n'))
        with patch.object(importer,'UPLOAD',p),self.assertRaises(ValueError):importer.ingest(self.db,self.raw)
        self.assertEqual(self.before_chart['status'],'computed')
        self.assertEqual(self.svc.calculate('symbolic_chart',self.args),self.before_chart)
        self.assertIsNone(summarize([{'status':'blocked'}])['real_world_predictive_accuracy'])
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_snapshot_roundtrip_keeps_all_tables_and_exact_pasted_crlf_bytes(self):
        first,again=self.path/'snapshot',self.path/'again';db,raw=self.path/'roundtrip.db',self.path/'roundtrip-raw'
        export_snapshot(self.db,self.raw,first);restore_snapshot(first,db,raw);export_snapshot(db,raw,again)
        self.assertEqual({str(p.relative_to(first)):p.read_bytes() for p in first.rglob('*') if p.is_file()},
                         {str(p.relative_to(again)):p.read_bytes() for p in again.rglob('*') if p.is_file()})
        self.assertEqual((first/'raw'/(APPENDIX_SHA+'.bin')).read_bytes(),self.source)
