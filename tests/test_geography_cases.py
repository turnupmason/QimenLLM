"""Historical geography source fidelity and chronology; no professional efficacy claim."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qimenllm.api.app import create_app
from qimenllm.cases.ingestion import import_cases
from qimenllm.knowledge.db import APPEND_ONLY,connect,digest
from qimenllm.knowledge.importer import ImportConflict
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.geography import GEOGRAPHY_SHA
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_shenqi_geography import ingest


class GeographyCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'geography.sqlite3';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY}
        cls.result=ingest(cls.db,cls.raw)
        d=ROOT/'data/structured/shenqi'
        cls.artifact=json.loads((d/'geography_cases.json').read_bytes())
        cls.curated=json.loads((d/'geography_curated.json').read_bytes())
        cls.gold=json.loads((d/'geography_gold.json').read_bytes())['charts']
        cls.candidates=json.loads((d/'geography_rule_candidates.json').read_bytes())
        cls.source=(ROOT/'data/provenance/uploads'/f'{GEOGRAPHY_SHA}.utf8').read_bytes()
        cls.svc=QimenService(cls.db);cls.catalog=cls.svc.cases('geography-environment')['cases']

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def record(self,case,line):return next(r for e in self.artifact['cases'][case-1]['events'] for r in e['records'] if r['source_lines']==[line,line])

    def test_source_bytes_and_every_quote_and_statement_span(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(GEOGRAPHY_SHA,10912,81))
        def walk(v):
            if isinstance(v,dict):
                if 'source_sha256' in v:self.assertEqual(v['source_sha256'],GEOGRAPHY_SHA)
                if {'byte_start','byte_end'}<=v.keys():
                    t=v.get('source_quote',v.get('text'));self.assertEqual(self.source[v['byte_start']:v['byte_end']].decode(),t)
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(self.artifact);walk(self.curated)
        for c in self.candidates['candidates']:
            a,b=min(c['source_lines']),max(c['source_lines']);self.assertEqual(c['source_quote'],''.join(self.source.decode().splitlines(keepends=True)[a-1:b]).rstrip('\r\n'))

    def test_all_two_whole_narratives_and_two_original_charts(self):
        self.assertEqual(len(self.catalog),2);self.assertEqual(len(self.artifact['cases']),2)
        lines=self.source.decode().splitlines()
        for i,c in enumerate(self.artifact['cases']):
            a,b=c['source_ranges'][0];self.assertEqual(c['title'],lines[a-1])
            self.assertEqual(len(c['events']),1 if i==0 else 2)
            if i:self.assertEqual(self.artifact['cases'][i-1]['source_ranges'][0][1]+1,a)
        self.assertEqual([[len(e['charts']) for e in c['events']] for c in self.artifact['cases']],[[1],[0,1]])

    def test_all_18_artifact_cells_against_independent_gold(self):
        charts={ch['chart_key']:ch for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        self.assertEqual(set(charts),set(self.gold))
        for key,ch in charts.items():self.assertEqual([r['cells'] for r in ch['payload']['source_table_rows']],self.gold[key])

    def test_service_projects_same_ids_and_all_18_literal_cells(self):
        expected={ch['source_lines'][0]+1:self.gold[ch['chart_key']] for c in self.artifact['cases'] for e in c['events'] for ch in e['charts']}
        n=0
        for c in self.catalog:
            for e in c['events']:
                for cid in e['chart_ids']:
                    p=self.svc.case_chart(c['case_id'],cid);self.assertEqual((p['status'],p['chart_id']),('projected',cid))
                    self.assertFalse(p['engine_verified']);self.assertFalse(p['original_chart_modified'])
                    first=min(v['source']['line'] for v in p['palaces'].values())
                    for palace,cells in zip((4,9,2,3,5,7,8,1,6),expected[first]):
                        self.assertEqual(p['palaces'][str(palace)]['source']['column_cells'],cells)
                    n+=1
        self.assertEqual(n,2)

    def test_case1_prior_expert_consensus_is_known_before_qimen_comparison(self):
        r=self.record(1,19);self.assertEqual(r['knowledge_phase'],'pre_prediction')
        self.assertIn('第三种方案',r['text']);self.assertIn('东北艮位',r['text'])
        self.assertTrue(r['payload']['already_known_expert_consensus']);self.assertTrue(r['payload']['not_blind_qimen_validation'])
        self.assertLess(r['sequence'],self.record(1,41)['sequence'])
        self.assertIn('完全一致',self.record(1,41)['text'])

    def test_case1_named_author_prepared_chart_and_field_claim_attribution(self):
        self.assertIn('张志春先生',self.record(1,20)['text'])
        self.assertEqual(self.record(1,41)['speaker'],'张志春/原书叙述')
        self.assertIn('姜国胜',self.record(1,22)['text'])
        self.assertIn('事先已经起好',self.record(1,22)['text'])
        self.assertTrue(self.record(1,40)['payload']['author_claim_not_instrument_measurement'])
        self.assertIn('地磁场',self.record(1,40)['text'])

    def test_case1_dates_and_costs_are_original_claims_not_completed_outcomes(self):
        self.assertEqual(self.record(1,45)['kind'],'timing')
        for t in ('1995年','2001年'):self.assertIn(t,self.record(1,45)['text'])
        for t in ('八个亿','十四个亿','资金不到位'):self.assertIn(t,self.record(1,46)['text'])
        f=self.record(1,47);self.assertEqual((f['kind'],f['knowledge_phase']),('feedback','post_feedback'))
        self.assertEqual(f['payload']['confirmation_scope'],['reported_budget_8yi','funding_not_in_place'])
        self.assertIn('opening_2001_or_later',f['payload']['not_individually_confirmed'])
        self.assertIn('possible_total_14yi',f['payload']['not_individually_confirmed'])
        for n in (48,49):self.assertEqual(self.record(1,n)['kind'],'continuation')
        self.assertEqual(len(self.artifact['cases'][0]['events']),1)

    def test_case2_two_burial_targets_one_family_only_second_has_chart(self):
        c=self.artifact['cases'][1];a,b=c['events'];self.assertEqual(a['charts'],[]);self.assertEqual(len(b['charts']),1)
        self.assertTrue(a['background']['casting_method_not_explicit'])
        self.assertEqual(b['background']['preceding_event_key'],a['event_key'])
        for r in a['records']:self.assertIsNone(r['chart_key'])
        for r in b['records']:self.assertEqual(r['chart_key'],b['charts'][0]['chart_key'])
        self.assertIn('癸山丁向',self.record(2,54)['text']);self.assertIn('辛山乙向',self.record(2,56)['text'])
        with connect(self.db) as db:
            rows=list(db.execute('SELECT e.event_id,e.family_id FROM events e JOIN case_events ce USING(event_id) WHERE ce.case_id=?',(self.catalog[1]['case_id'],)))
            self.assertEqual(len(rows),2);self.assertEqual(len({r['family_id'] for r in rows}),1)

    def test_case2_first_question_and_prediction_keep_exact_segments(self):
        r=self.record(2,54);seg=r['payload']['source_statement_segments']
        self.assertEqual(''.join(x['text'] for x in seg),r['text'])
        self.assertEqual([x['knowledge_phase'] for x in seg],['pre_prediction','prediction'])
        self.assertIn('画了墓地的形势图',seg[0]['text']);self.assertIn('如果不在银行工作',seg[1]['text'])
        self.assertTrue(r['payload']['method_not_explicitly_stated_as_qimen'])
        self.assertTrue(r['payload']['full_chart_and_topographic_diagram_not_provided'])
        self.assertIn('not proof the family personally owns',self.record(2,55)['payload']['confirmation_scope'])

    def test_case2_ellipsis_and_reactions_do_not_invent_burial_outcome(self):
        r=self.record(2,78);self.assertIn('前辈高人……你得不到',r['text'])
        self.assertTrue(r['payload']['ellipsis_preserved_without_completion'])
        self.assertTrue(r['payload']['internal_reasoning_not_explicit_in_source'])
        for n in (79,81):
            f=self.record(2,n);self.assertEqual(f['knowledge_phase'],'post_feedback')
            self.assertTrue(f['payload']['reaction_only_not_explicit_grave_possession_or_eventual_use_confirmation'])
        self.assertIn('这上边都有呢',self.record(2,80)['text'])
        self.assertFalse(any(r['kind']=='author_reasoning' for e in self.artifact['cases'][1]['events'] for r in e['records']))

    def test_same_named_actor_does_not_merge_unrelated_missing_person_family(self):
        with connect(self.db) as c:
            current={r[0] for r in c.execute('SELECT e.family_id FROM events e JOIN case_events ce USING(event_id) WHERE ce.case_id=?',(self.catalog[1]['case_id'],))}
            unrelated={r[0] for r in c.execute("SELECT DISTINCT e.family_id FROM events e JOIN case_records cr USING(event_id) WHERE cr.text LIKE '%王庆丰%' AND cr.text LIKE '%外甥女%'")}
            self.assertTrue(unrelated);self.assertTrue(current.isdisjoint(unrelated))

    def test_three_source_contexts_and_conditions_remain_separate(self):
        self.assertEqual(self.curated['printed_chapter_number'],15)
        self.assertTrue(self.source.decode().startswith('第十五章'))
        a,b,c=self.candidates['candidates']
        for t in ('日干为人','时干为住宅','三奇','吉凶','来克日干宫'):self.assertIn(t,a['source_quote'])
        for t in ('生门为房屋','死门为地皮','值符为新宅','值使为旧宅'):self.assertIn(t,b['source_quote'])
        for t in ('地盘为死者','天盘为生者','天盘克地盘','地盘克天盘','一、三、四宫不吉'):self.assertIn(t,c['source_quote'])

    def test_three_candidates_scope_unknown_and_reference_only(self):
        for context,expected in [({},0),({'domain':'geography_environment','geography_subtype':'burial_site','method_scope':'shenqi_geography_burial_site_reference_v1'},1),({'domain':'geography_environment','geography_subtype':'living_residence','method_scope':'shenqi_geography_living_residence_reference_v1'},1)]:
            r=self.svc.rule_candidates(context,domain='geography_environment',method='shenqi_geography_reference_v1')
            self.assertEqual(r['candidate_count'],3);self.assertFalse(r['role_bindings'])
            self.assertEqual(sum(c['symbolic_status']=='applicable' for c in r['candidates']),expected)
            self.assertTrue(all(c['activation_status']=='reference_only' for c in r['candidates']))

    def test_original_center_and_literal_prefix(self):
        c=self.catalog[1];cid=next(cid for e in c['events'] for cid in e['chart_ids']);p=self.svc.case_chart(c['case_id'],cid)
        self.assertEqual(p['palaces']['5']['earth_stem'],'壬')
        self.assertEqual(p['palaces']['3']['heaven_prefix_marker'],'壬')
        self.assertIn('原盘单字：壬',p['palaces']['5']['source']['text'])
        self.assertFalse(p['engine_verified']);self.assertFalse(p['original_chart_modified'])

    def test_initial_view_preserves_known_consensus_and_withholds_feedback(self):
        for c in self.catalog:
            v=self.svc.case(c['case_id'],'before_prediction');self.assertFalse(v['training_export'])
            for e in v['events']:
                for r in e.get('records',[]):self.assertEqual(r['knowledge_phase'],'pre_prediction')
        v=json.dumps(self.svc.case(self.catalog[0]['case_id'],'before_prediction'),ensure_ascii=False)
        self.assertIn('第三种方案',v)
        for t in ('投资八个亿','十四个亿','2001年才能'):self.assertNotIn(t,v)
        v=json.dumps(self.svc.case(self.catalog[1]['case_id'],'before_prediction'),ensure_ascii=False)
        for t in ('三儿子是本地工商银行行长','前辈高人','佩服得五体投地'):self.assertNotIn(t,v)

    def test_existing_api_cli_and_append_only_replay(self):
        app=create_app(self.svc)
        def call(path,payload):
            b=json.dumps(payload).encode();status=[]
            out=b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
            self.assertEqual(status,['200 OK']);return json.loads(out)
        for c in call('/v1/cases',{'chapter_key':'geography-environment'})['cases']:
            for e in c['events']:
                for cid in e['chart_ids']:self.assertEqual(call('/v1/case-chart',{'case_id':c['case_id'],'chart_id':cid})['chart_id'],cid)
        r=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'cases','--chapter-key','geography-environment'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(len(json.loads(r.stdout)['cases']),2)
        with connect(self.db) as c:
            for t,old in self.before.items():
                current=[tuple(r) for r in c.execute('SELECT * FROM '+t)]
                self.assertTrue(all(row in current for row in old),t)
            n=c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        r=ingest(self.db,self.raw);self.assertTrue(r['cases']['duplicate']);self.assertTrue(r['candidates']['duplicate'])
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],n)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rules').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM training_tasks').fetchone()[0],0)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_immutable_rewrite_rejected_and_snapshot_restores_exactly(self):
        bad=copy.deepcopy(self.artifact);bad['cases'][0]['title']='changed'
        with self.assertRaises(ImportConflict):import_cases(self.db,self.result['source']['revision_id'],bad)
        first=self.path/'snapshot';again=self.path/'again';db=self.path/'roundtrip.sqlite3';raw=self.path/'roundtrip_raw'
        export_snapshot(self.db,self.raw,first);restore_snapshot(first,db,raw);export_snapshot(db,raw,again)
        self.assertEqual({str(p.relative_to(first)):p.read_bytes() for p in first.rglob('*') if p.is_file()},
            {str(p.relative_to(again)):p.read_bytes() for p in again.rglob('*') if p.is_file()})
