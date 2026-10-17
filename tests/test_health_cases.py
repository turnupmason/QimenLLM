"""Complete supplied medical narratives; facts, chronology and computation separated."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cli import main
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import HEALTH_SHA
from qimenllm.knowledge.db import connect,digest
from qimenllm.knowledge.importer import import_chapter,ImportConflict
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.chapter02 import install_chapter02
from qimenllm.knowledge.health import install_health
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
from support import DatabaseTest,case_content_text
from test_runtime import request

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/structured/shenqi'


class HealthCaseTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        for n in (1,2):
            c=json.loads((DATA/f'chapter{n:02d}_curated.json').read_bytes())
            r=import_chapter(self.db,self.raw,(ROOT/'data/snapshots/current/raw'/f"{c['source_sha256']}.bin").read_bytes(),
                book_key='shenqi-user-text-v1',book_title='神奇之门',chapter_key=f'chapter-{n:02d}',
                chapter_title=c['chapter_title'],sequence=n,origin='actual-source-regression')
            (install_curated if n==1 else install_chapter02)(self.db,r['revision_id'],c)
        self.raw_text=(ROOT/'data/snapshots/current/raw'/f'{HEALTH_SHA}.bin').read_bytes()
        self.curation=json.loads((DATA/'health_curated.json').read_bytes())
        self.case_data=json.loads((DATA/'health_cases.json').read_bytes())
        self.gold=json.loads((DATA/'health_chart_gold.json').read_bytes())
        self.source=import_chapter(self.db,self.raw,self.raw_text,book_key='shenqi-user-text-v1',book_title='神奇之门',
            chapter_key='health-prediction',chapter_title='人体疾病预测',sequence=7,origin='actual-source-regression')
        self.curation_result=install_health(self.db,self.source['revision_id'],self.curation)
        self.installed=import_cases(self.db,self.source['revision_id'],self.case_data)
        self.service=QimenService(self.db)
        self.catalog=self.service.cases('health-prediction')['cases']

    def original(self,index,view='full'):
        return self.service.case(self.catalog[index-1]['case_id'],view)

    def chart(self,index,method=None):
        c=self.catalog[index-1]
        return self.service.case_chart(c['case_id'],c['events'][0]['chart_ids'][0],method)

    def test_exact_source_six_complete_stories_and_reference_only_compilation(self):
        self.assertEqual(digest(self.raw_text),HEALTH_SHA)
        self.assertEqual((len(self.raw_text),len(self.raw_text.decode()),len(self.raw_text.splitlines())),(20031,7839,431))
        self.assertFalse(self.raw_text.endswith(b'\n'))
        self.assertEqual(self.curation_result['compiled_families_added'],0)
        self.assertEqual(self.curation_result['worked_examples'],0)
        self.assertEqual(len(self.catalog),6)
        with connect(self.db) as conn:
            expected={'cases':6,'events':6,'event_families':6,'charts':6,'case_records':81,
                      'rules':0,'training_tasks':0,'dataset_releases':0,'split_assignments':0}
            for table,count in expected.items(): self.assertEqual(conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],count,table)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_all_records_whole_source_and_nine_raw_rows_are_lossless(self):
        lines=self.raw_text.decode().splitlines(keepends=True)
        ranges=((33,105),(106,164),(165,232),(233,289),(290,364),(365,431))
        for number,(first,last) in enumerate(ranges,1):
            view=self.original(number);self.assertEqual(view['source_completeness'],'complete')
            self.assertEqual(view['events'][0]['narrative_sources'][0]['text'],''.join(lines[first-1:last]))
            self.assertEqual(len(view['events'][0]['charts']),1)
            for record in view['events'][0]['records']:
                self.assertEqual(record['text'],record['source']['text'])
                self.assertEqual(record['text'].encode(),self.raw_text[record['source']['byte_start']:record['source']['byte_end']])
                self.assertEqual(record['source']['source_sha256'],HEALTH_SHA)
            for p in self.chart(number)['palaces'].values():
                self.assertEqual(p['source']['text'],lines[p['source']['line']-1])

    def test_all_fifty_four_rows_match_independently_transcribed_gold(self):
        count=0
        for g in self.gold['cases']:
            result=self.chart(g['case_number']);self.assertEqual(result['status'],'projected')
            self.assertEqual(len(result['palaces']),9)
            for source in g['source_rows']:
                actual=result['palaces'][str(source['palace'])]; expected=source['interpretation']
                self.assertEqual(actual['source']['text'].rstrip('\r\n'),source['raw_line'])
                self.assertEqual(actual['earth_stem'],expected['earth_stem'])
                if source['palace']!=5:
                    self.assertEqual(actual['door'],expected['door'])
                    self.assertEqual(actual['star'],expected['primary_star'])
                    self.assertEqual(actual['deity'],expected['deity'])
                    self.assertEqual(actual['heaven_stem'],expected['primary_heaven_stem'])
                    self.assertEqual(actual['heaven_prefix_marker'],expected['door_prefix_raw'] or None)
                    self.assertEqual(actual['star_prefix_marker'],expected['star_prefix_raw'] or None)
                count+=1
            self.assertFalse(result['engine_verified']);self.assertFalse(result['calendar_recomputed'])
            self.assertFalse(result['original_chart_modified']);self.assertIsNone(result['medical_inference'])
        self.assertEqual(count,54)

    def test_five_symbolic_comparisons_match_and_center_door_gap_stays_not_covered(self):
        for number in (1,3,4,5,6):
            result=self.chart(number,'shenqi_ch2_paper_v1');comparison=result['comparison']
            self.assertEqual(comparison['status'],'matches',comparison)
            self.assertGreaterEqual(len(comparison['checks']),41)
            self.assertTrue(all(c['matches'] for c in comparison['checks']))
            self.assertEqual(result['chart_id'],comparison['source_chart_id'])
            self.assertNotEqual(comparison['source_chart_id'],comparison['computed_chart_id'])
            self.assertFalse(comparison['engine_verified']);self.assertFalse(comparison['source_rejected'])
        gap=self.chart(2,'shenqi_ch2_paper_v1')['comparison']
        self.assertEqual(gap['status'],'not_covered');self.assertFalse(gap['source_rejected'])
        self.assertIn('palace five',gap['calculation']['reason'])
        # No default algorithm is silently selected, and original chart remains intact.
        self.assertNotIn('comparison',self.chart(2))
        self.assertEqual(self.chart(2)['palaces']['2']['door'],'死门')

    def test_first_diagnosis_cannot_see_later_birth_year_confirmation_or_survival_target(self):
        before=self.original(1,'before_prediction');text=case_content_text(before)
        self.assertEqual(len(before['events'][0]['records']),4)
        for forbidden in ('结肠癌','1991','1943','1997','再活五年','reasoning-2'):
            self.assertNotIn(forbidden,text)
        full=self.original(1)['events'][0]
        for record in full['records']:
            if '1943' in record['text'] or '1991年12' in record['text']:
                self.assertIn(record['knowledge_phase'],('post_feedback','unknown'))
        self.assertFalse(any(r['kind']=='outcome' for r in full['records']))

    def test_father_disease_hospital_and_death_reports_are_after_prediction(self):
        before=self.original(2,'before_prediction');text=case_content_text(before)
        self.assertIn('1921',text)
        for forbidden in ('食道癌','八厘米','9月13日','9月7日','梅核气','丁未日'):
            self.assertNotIn(forbidden,text)
        full=self.original(2)['events'][0]
        for record in full['records']:
            if record['kind'] in ('feedback','outcome'):
                self.assertEqual(record['knowledge_phase'],'post_feedback')
        self.assertFalse(self.original(2)['outcome_independently_verified'])

    def test_nephew_initial_accident_known_but_later_feedback_and_discharge_hidden(self):
        text=case_content_text(self.original(3,'before_prediction'))
        for known in ('电工','摔伤','手术','1975'):self.assertIn(known,text)
        for later in ('尾椎骨','大小便失禁','拆线','5月20日','丙辰'):self.assertNotIn(later,text)
        records=self.original(3)['events'][0]['records']
        feedback=next(r for r in records if r['kind']=='feedback')
        for record in records:
            if record['sequence']>feedback['sequence']:
                self.assertEqual(record['knowledge_phase'],'post_feedback')
        self.assertEqual(sum(r['kind']=='outcome' for r in records),1)

    def test_aunt_predictor_and_postmortem_feedback_do_not_become_initial_input(self):
        before=self.original(4,'before_prediction');text=case_content_text(before)
        self.assertIn('王建国',text)
        for later in ('脑溢血','昏迷不醒','5月26日','癸亥日壬子时'):self.assertNotIn(later,text)
        background=self.original(4)['events'][0]['background']
        self.assertEqual(background['predictor_as_written'],'王建国')
        self.assertTrue(background['predictor_distinct_from_narrator'])

    def test_live_diagnosis_and_travel_feedback_not_prospective_medical_proof(self):
        before=case_content_text(self.original(5,'before_prediction'))
        for later in ('糖尿病','脂肪肝','1989','脑囊肿'):self.assertNotIn(later,before)
        fifth=self.original(5)['events'][0]['background']
        self.assertTrue(fifth['not_a_prospective_prediction_of_future_disease_outcome'])
        before=case_content_text(self.original(6,'before_prediction'))
        self.assertIn('肾炎',before)
        for later in ('1998年3月','已经稳定了','心脏病'):self.assertNotIn(later,before)
        full=self.original(6);self.assertFalse(full['outcome_independently_verified'])
        final=full['events'][0]['records'][-1]
        self.assertEqual(final['knowledge_phase'],'post_feedback')
        self.assertIn('已经稳定了',final['text'])

    def test_pre_prediction_assertion_handles_original_ci_source_id_collision(self):
        before=self.original(1,'before_prediction')
        # The exact opaque ID from macOS/Python 3.11 run 39046797275.
        collision='span-43a2315a84b68c425eb3e38ab559e78fe2eac199155022a22e4ca78404c805b2'
        before['events'][0]['records'][0]['source']['source_id']=collision
        self.assertIn('1991',json.dumps(before,ensure_ascii=False))
        self.assertNotIn('1991',case_content_text(before))
        self.assertEqual([r['sequence'] for r in before['events'][0]['records']],[0,1,2,3])
        # A real future year under an unexpected content path must still fail
        # the same content-absence check; do not whitelist whole subtrees.
        before['events'][0]['background']={'unexpected_feedback_year':1991}
        self.assertIn('1991',case_content_text(before))

    def test_prefix_markers_are_retained_without_fabricated_stars_or_times(self):
        for number,palace,prefix in ((1,8,'庚'),(2,2,'庚'),(3,3,'丙'),(4,9,'丁'),(5,3,'辛'),(6,2,'丙')):
            result=self.chart(number)
            self.assertEqual(result['palaces'][str(palace)]['heaven_prefix_marker'],prefix)
            self.assertEqual(result['palaces']['5']['earth_stem'],prefix)
            self.assertIsNone(result['palaces']['5']['star'])
        for number,prefix in ((2,'庚'),(6,'丙')):
            self.assertEqual(self.chart(number)['palaces']['2']['star_prefix_marker'],prefix)
        for number in range(1,7):
            chart=self.original(number)['events'][0]['charts'][0]
            if number==3:self.assertEqual(chart['input_datetime'],'1996-05-09T16:20:00')
            else:self.assertIsNone(chart['input_datetime'])
            self.assertIsNone(chart['timezone'])
            self.assertEqual(chart['validation_status'],'original_unparsed')

    def test_reference_learning_preserves_all_author_steps_without_role_binding(self):
        total=0
        for g in self.curation['groups']:
            d=g.get('dataset')
            if not d:continue
            r=self.service.reference(d['key'],{})
            self.assertEqual(r['total'],len(d['rows']))
            self.assertEqual(r['role_bindings'],[]);self.assertFalse(r['truncated'])
            self.assertTrue(all(s['sha256']==HEALTH_SHA for s in r['sources'].values()))
            total+=r['total']
        self.assertEqual(total,39)

    def test_replay_is_idempotent_and_changes_to_same_case_are_rejected(self):
        with connect(self.db) as conn:before=conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        r=install_health(self.db,self.source['revision_id'],self.curation)
        self.assertEqual(r['structured_records_added'],0);self.assertEqual(r['methods_added'],0)
        repeated=import_cases(self.db,self.source['revision_id'],self.case_data)
        self.assertTrue(repeated['duplicate']);self.assertTrue(all(n==0 for n in repeated['added'].values()))
        changed=copy.deepcopy(self.case_data);changed['cases'][0]['events'][0]['records'][0]['text']+='invented'
        with self.assertRaises(ValueError):import_cases(self.db,self.source['revision_id'],changed)
        with connect(self.db) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],before)

    def test_case_catalog_chart_api_and_cli_use_same_actual_service(self):
        app=create_app(self.service)
        status,r=request(app,{'chapter_key':'health-prediction'},'/v1/cases')
        self.assertEqual(status,'200 OK');self.assertEqual(r,self.service.cases('health-prediction'))
        output=io.StringIO()
        with redirect_stdout(output):main(['--db',str(self.db),'cases','--chapter-key','health-prediction'])
        self.assertEqual(json.loads(output.getvalue()),r)
        c=self.catalog[0];cid=c['case_id'];chid=c['events'][0]['chart_ids'][0]
        with patch.object(self.service,'case_chart',wraps=self.service.case_chart) as called:
            status,r=request(app,{'case_id':cid,'chart_id':chid,'comparison_method':'shenqi_ch2_paper_v1'},'/v1/case-chart')
            called.assert_called_once_with(cid,chid,'shenqi_ch2_paper_v1')
        self.assertEqual(status,'200 OK');self.assertEqual(r,self.chart(1,'shenqi_ch2_paper_v1'))
        output=io.StringIO()
        with redirect_stdout(output):main(['--db',str(self.db),'case-chart',cid,chid,'--comparison-method','shenqi_ch2_paper_v1'])
        self.assertEqual(json.loads(output.getvalue()),r)

    def test_cross_case_chart_cannot_be_rebound_or_api_parameter_bypassed(self):
        cid=self.catalog[0]['case_id'];other=self.catalog[1]['events'][0]['chart_ids'][0]
        with self.assertRaises(KeyError):self.service.case_chart(cid,other)
        app=create_app(self.service)
        self.assertEqual(request(app,{'case_id':cid,'chart_id':other},'/v1/case-chart')[0],'404 Not Found')
        self.assertEqual(request(app,{'case_id':cid,'chart_id':other,'comparison_method':{}},'/v1/case-chart')[0],'400 Bad Request')
        self.assertEqual(request(app,{'chapter_key':[]},'/v1/cases')[0],'400 Bad Request')

    def test_snapshot_recovery_preserves_all_case_views_and_same_source_chart_ids(self):
        export_snapshot(self.db,self.raw,self.root/'snapshot')
        restore_snapshot(self.root/'snapshot',self.root/'restored.sqlite3',self.root/'restored-raw')
        restored=QimenService(self.root/'restored.sqlite3')
        self.assertEqual(restored.cases('health-prediction'),self.service.cases('health-prediction'))
        for case in self.catalog:
            cid=case['case_id'];chid=case['events'][0]['chart_ids'][0]
            for view in ('full','before_prediction'):self.assertEqual(restored.case(cid,view),self.service.case(cid,view))
            self.assertEqual(restored.case_chart(cid,chid),self.service.case_chart(cid,chid))
