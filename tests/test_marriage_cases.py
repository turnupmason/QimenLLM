"""Whole marriage narratives, multiple consultations, source disagreements and scope."""
import io
import copy
import json
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
from qimenllm.api.app import create_app
from qimenllm.cli import main
from qimenllm.contracts import Inquiry
from qimenllm.cases.ingestion import import_cases
from qimenllm.cases.source_chart import MARRIAGE_SHA
from qimenllm.knowledge.db import connect,digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.chapter02 import install_chapter02
from qimenllm.knowledge.marriage import install_marriage
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot,restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.rules.candidates import install_candidates
from support import DatabaseTest
from test_runtime import request,CapturingFixtureModel

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/structured/shenqi'


class MarriageCaseTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        for n in (1,2):
            c=json.loads((DATA/f'chapter{n:02d}_curated.json').read_bytes())
            r=import_chapter(self.db,self.raw,(ROOT/'data/snapshots/current/raw'/f"{c['source_sha256']}.bin").read_bytes(),
                book_key='shenqi-user-text-v1',book_title='神奇之门',chapter_key=f'chapter-{n:02d}',
                chapter_title=c['chapter_title'],sequence=n,origin='actual-source-regression')
            (install_curated if n==1 else install_chapter02)(self.db,r['revision_id'],c)
        load=lambda name:json.loads((DATA/f'marriage_{name}.json').read_bytes())
        self.curation=load('curated');self.case_data=load('cases');self.gold=load('chart_gold')
        self.candidates=load('rule_candidates');self.selection_gold=load('selection_gold')
        self.content=(ROOT/'data/snapshots/current/raw'/f'{MARRIAGE_SHA}.bin').read_bytes()
        self.source=import_chapter(self.db,self.raw,self.content,book_key='shenqi-user-text-v1',book_title='神奇之门',
            chapter_key='marriage-prediction',chapter_title='恋爱婚姻预测',sequence=8,origin='actual-source-regression')
        self.curated_result=install_marriage(self.db,self.source['revision_id'],self.curation)
        self.case_result=import_cases(self.db,self.source['revision_id'],self.case_data)
        install_candidates(self.db,self.source['revision_id'],self.candidates)
        self.service=QimenService(self.db);self.catalog=self.service.cases('marriage-prediction')['cases']

    def case(self,number,view='full'):
        return self.service.case(self.catalog[number-1]['case_id'],view)

    def chart(self,number,method=None):
        c=self.catalog[number-1]
        ids=[i for e in c['events'] for i in e['chart_ids']]
        self.assertEqual(len(ids),1)
        return self.service.case_chart(c['case_id'],ids[0],method)

    def test_exact_original_six_cases_seven_events_and_six_actual_charts(self):
        self.assertEqual((len(self.content),len(self.content.decode()),len(self.content.splitlines())),(21490,8332,423))
        self.assertEqual(digest(self.content),MARRIAGE_SHA);self.assertFalse(self.content.endswith(b'\n'))
        self.assertEqual(len(self.catalog),6);self.assertEqual(self.curated_result['compiled_families_added'],0)
        with connect(self.db) as conn:
            for table,count in {'cases':6,'events':7,'event_families':6,'charts':6,'case_records':91,
                                'evidence_links':150,'rules':0,'training_tasks':0,'dataset_releases':0}.items():
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],count,table)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_whole_stories_and_all_source_records_preserve_bytes(self):
        lines=self.content.decode().splitlines(keepends=True)
        ranges=((21,79),(80,151),(152,215),(216,287),(288,354),(355,423))
        for number,(a,b) in enumerate(ranges,1):
            full=self.case(number);self.assertEqual(full['source_completeness'],'complete')
            self.assertEqual(full['source']['text'],''.join(lines[a-1:b]))
            for event in full['events']:
                for r in event['records']:
                    self.assertEqual(r['text'],r['source']['text'])
                    self.assertEqual(r['text'].encode(),self.content[r['source']['byte_start']:r['source']['byte_end']])
        coverage={i for g in self.curation['groups'] for i in range(g['line_start'],g['line_end']+1)}
        self.assertEqual(coverage,set(range(1,424)))

    def test_fifty_four_independently_transcribed_rows_and_prefixes(self):
        total=0
        for g in self.gold['cases']:
            projected=self.chart(g['case_number'])
            for expected in g['source_rows']:
                p=projected['palaces'][str(expected['palace'])];value=expected['interpretation']
                self.assertEqual(p['source']['text'].rstrip('\r\n'),expected['raw_line'])
                self.assertEqual(p['source']['line'],expected['line'])
                self.assertEqual(p['earth_stem'],value['earth_stem'])
                if expected['palace']!=5:
                    for actual_key,gold_key in (('door','door'),('deity','deity'),('star','primary_star'),('heaven_stem','primary_heaven_stem')):
                        self.assertEqual(p[actual_key],value[gold_key])
                    self.assertEqual(p['heaven_prefix_marker'],value['door_prefix_raw'] or None)
                    self.assertEqual(p['star_prefix_marker'],value['star_prefix_raw'] or None)
                total+=1
            self.assertFalse(projected['original_chart_modified']);self.assertFalse(projected['engine_verified'])
        self.assertEqual(total,54)

    def test_four_given_symbol_comparisons_and_two_center_door_gaps(self):
        for number in (1,2,5,6):
            p=self.chart(number,'shenqi_ch2_paper_v1');c=p['comparison']
            self.assertEqual(c['status'],'matches',c);self.assertTrue(all(x['matches'] for x in c['checks']))
            self.assertEqual(c['source_chart_id'],p['chart_id']);self.assertFalse(c['engine_verified'])
            self.assertFalse(c['calendar_recomputed']);self.assertFalse(c['source_rejected'])
        for number in (3,4):
            p=self.chart(number,'shenqi_ch2_paper_v1')
            self.assertEqual(p['comparison']['status'],'not_covered')
            self.assertFalse(p['comparison']['source_rejected'])
            self.assertIn('palace five',p['comparison']['calculation']['reason'])
        self.assertNotIn('comparison',self.chart(6))

    def test_original_duplicates_and_text_versus_table_differences_are_not_repaired(self):
        p=self.chart(3)
        self.assertEqual(p['palaces']['2']['earth_stem'],'辛')
        self.assertEqual(p['palaces']['9']['earth_stem'],'辛')
        observations=p['source_table_observations']
        self.assertEqual(observations['distinct_primary_earth_stems'],8)
        self.assertEqual(set(observations['duplicate_primary_earth_stems']['辛']),{2,9})
        original=self.case(3)
        self.assertIn('壬加癸',json.dumps(original,ensure_ascii=False))
        p=self.chart(5);self.assertEqual(p['palaces']['3']['heaven_stem'],'丁')
        self.assertIn('时干丁在5宫',json.dumps(self.case(5),ensure_ascii=False))
        self.assertEqual(self.chart(1)['palaces']['2']['star_prefix_marker'],'辛')
        self.assertIsNone(self.chart(1)['palaces']['2']['heaven_prefix_marker'])

    def test_center_original_and_hosted_chief_positions_have_separate_evidence(self):
        p=self.chart(6,'shenqi_ch2_paper_v1');c=p['comparison']
        checks={r['path']:r for r in c['checks']}
        self.assertEqual(checks['source_metadata.值符落宫.original']['source_value'],5)
        self.assertEqual(checks['source_metadata.值符落宫.hosted']['source_value'],2)
        self.assertNotEqual(c['source_chart_id'],c['computed_chart_id'])
        self.assertIn('中5宫寄坤2宫',p['source_metadata']['值符落宫'])

    def test_mother_son_first_request_does_not_know_traits_or_rejection_feedback(self):
        text=json.dumps(self.case(1,'before_prediction'),ensure_ascii=False)
        for forbidden in ('一米五六','正规大学','被动得很','一心在学习','谈了二次就吹了'):
            self.assertNotIn(forbidden,text)
        self.assertIn('刚谈了一个对象',text)

    def test_daughter_birth_years_known_but_prior_divorce_and_opposition_not_known(self):
        text=json.dumps(self.case(2,'before_prediction'),ensure_ascii=False)
        self.assertIn('1970',text);self.assertIn('1964',text)
        for forbidden in ('妻子跟他离了婚','不赞成','父母拗不过','丁壬合','美国'):
            self.assertNotIn(forbidden,text)
        full=self.case(2)['events'][0]['records']
        r=next(r for r in full if '1997年丁丑' in r['text'])
        self.assertIn(r['knowledge_phase'],('post_feedback','unknown'))

    def test_existing_divorce_reconstruction_not_future_forecast_or_preloaded_history(self):
        before=json.dumps(self.case(3,'before_prediction'),ensure_ascii=False)
        for later in ('离了婚','钢琴','九千','六千','三千九百','邮票'):
            self.assertNotIn(later,before)
        records=self.case(3)['events'][0]['records']
        self.assertTrue(any('杜新会' in (r.get('speaker') or '') for r in records))
        self.assertTrue(any('3月18日' in r['text'] and r['kind']=='feedback' for r in records))

    def test_womans_day_geng_role_does_not_get_rewritten_as_male(self):
        before=json.dumps(self.case(4,'before_prediction'),ensure_ascii=False)
        for later in ('经常夜不回家','二十年','2月27日','胳摔骨折'):
            self.assertNotIn(later,before)
        full=json.dumps(self.case(4),ensure_ascii=False)
        self.assertIn('日干庚为赵小姐',full)
        self.assertIn('时干壬为丈夫',full)
        self.assertIn('胳摔骨折',full)

    def test_unknown_initial_topic_and_forecast_year_miss_are_explicit(self):
        before=json.dumps(self.case(5,'before_prediction'),ensure_ascii=False)
        for later in ('第三者','副经理','二十六针','1998年五月'):
            self.assertNotIn(later,before)
        records=self.case(5)['events'][0]['records']
        forecast=next(r for r in records if r['source']['text'].startswith('据此，杜新会说：“时间不会'))
        feedback=next(r for r in records if r['text'].startswith('后来杜新会得知'))
        self.assertEqual(forecast['payload']['predicted_marriage_year_from_context'],1997)
        self.assertNotIn('1998',json.dumps(forecast['payload'],ensure_ascii=False))
        self.assertTrue(feedback['payload']['marriage_year_differs_from_forecast'])
        self.assertEqual(feedback['payload']['milestones'][-1]['year'],1998)

    def test_two_consultations_keep_one_missing_chart_and_one_later_chart_separate(self):
        full=self.case(6);early,later=full['events']
        self.assertEqual(early['family_id'],later['family_id'])
        self.assertEqual(early['charts'],[]);self.assertEqual(len(later['charts']),1)
        self.assertTrue(all(r['chart_id'] is None for r in early['records']))
        self.assertTrue(any('1998年1月' in r['text'] for r in early['records']))
        self.assertFalse(any('1998年1月' in r['text'] for r in later['records']))
        self.assertFalse(any(r['kind'] in ('outcome','feedback') and '不会离婚' in r['text'] for r in later['records']))
        before=self.case(6,'before_prediction')
        self.assertEqual(len(before['events']),2)
        for e in before['events']:
            self.assertNotIn('寡妇',json.dumps(e,ensure_ascii=False))

    def test_fifty_two_independent_conditional_gold_and_no_real_role_activation(self):
        self.assertEqual(len(self.selection_gold['selection_cases']),52)
        for gold in self.selection_gold['selection_cases']:
            r=self.service.rule_candidates(gold['context'],**gold['inspection_filters'])
            selected=next(c for c in r['candidates'] if c['candidate_key']==gold['expected']['candidate_key'])
            self.assertEqual(selected['symbolic_status'],gold['expected']['symbolic_status'],gold['key'])
            self.assertEqual(selected['activation_status'],'reference_only')
            self.assertEqual(r['role_bindings'],[])
            if 'missing_fields' in gold['expected']:self.assertEqual(selected['missing'],gold['expected']['missing_fields'])

    def test_actual_ask_sql_inspects_new_candidates_without_calling_model(self):
        model=CapturingFixtureModel();service=QimenService(self.db,model=model)
        g=self.selection_gold['selection_cases'][0]
        with patch.object(service,'rule_candidates',wraps=service.rule_candidates) as query:
            result=service.ask(Inquiry('研究来源条件',domain='marriage',context=g['context'],method_id=g['inspection_filters']['method']))
            query.assert_called_once()
        self.assertEqual(result['status'],'blocked');self.assertEqual(model.calls,[])
        selection=next(t for t in result['trace'] if t['stage']=='selection')
        self.assertEqual(len(selection['source_candidates']),11)
        self.assertEqual(result['rule_ids'],[])

    def test_references_idempotence_and_case_catalog_charts_through_cli_api(self):
        total=0
        for g in self.curation['groups']:
            d=g.get('dataset')
            if d:
                r=self.service.reference(d['key'],{});total+=r['total']
                self.assertEqual(r['role_bindings'],[]);self.assertFalse(r['truncated'])
        self.assertEqual(total,28)
        with connect(self.db) as conn:before=conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        self.assertEqual(install_marriage(self.db,self.source['revision_id'],self.curation)['structured_records_added'],0)
        self.assertTrue(import_cases(self.db,self.source['revision_id'],self.case_data)['duplicate'])
        self.assertEqual(install_candidates(self.db,self.source['revision_id'],self.candidates)['added'],0)
        with connect(self.db) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],before)
        status,r=request(create_app(self.service),{'chapter_key':'marriage-prediction'},'/v1/cases')
        self.assertEqual(status,'200 OK');self.assertEqual(r['total'],6)
        c=self.catalog[-1];cid=c['case_id'];chid=c['events'][-1]['chart_ids'][0]
        status,r=request(create_app(self.service),{'case_id':cid,'chart_id':chid,'comparison_method':'shenqi_ch2_paper_v1'},'/v1/case-chart')
        self.assertEqual(status,'200 OK');self.assertEqual(r,self.chart(6,'shenqi_ch2_paper_v1'))
        out=io.StringIO()
        with redirect_stdout(out):main(['--db',str(self.db),'case-chart',cid,chid,'--comparison-method','shenqi_ch2_paper_v1'])
        self.assertEqual(json.loads(out.getvalue()),r)

    def test_cross_case_no_chart_episode_cannot_steal_later_or_other_case_chart(self):
        cid=self.catalog[-1]['case_id'];foreign=self.catalog[0]['events'][0]['chart_ids'][0]
        with self.assertRaises(KeyError):self.service.case_chart(cid,foreign)
        full=self.case(6);self.assertNotEqual(full['events'][0]['event_id'],full['events'][1]['charts'][0]['event_id'])
        self.assertEqual(full['events'][0]['charts'],[])

    def test_snapshot_restores_multi_event_views_source_disagreements_and_conditions(self):
        export_snapshot(self.db,self.raw,self.root/'snapshot')
        restore_snapshot(self.root/'snapshot',self.root/'restored.sqlite3',self.root/'restored-raw')
        restored=QimenService(self.root/'restored.sqlite3')
        self.assertEqual(restored.cases(),self.service.cases())
        for c in self.catalog:
            for view in ('full','before_prediction'):self.assertEqual(restored.case(c['case_id'],view),self.service.case(c['case_id'],view))
            for e in c['events']:
                for chid in e['chart_ids']:self.assertEqual(restored.case_chart(c['case_id'],chid),self.service.case_chart(c['case_id'],chid))
        g=self.selection_gold['selection_cases'][0]
        self.assertEqual(restored.rule_candidates(g['context'],**g['inspection_filters']),self.service.rule_candidates(g['context'],**g['inspection_filters']))

    def test_temporal_payload_contract_rejects_future_values_and_references_atomically(self):
        with connect(self.db) as conn:before=conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        for kind in ('future_details','outcome_audit','future_reference'):
            bad=copy.deepcopy(self.case_data);event=bad['cases'][0]['events'][0]
            prediction=next(r for r in event['records'] if r['kind']=='prediction')
            future=next(r for r in event['records'] if r['kind']=='feedback')
            if kind=='future_details':prediction['payload']['feedback_not_available_yet']=['later source values']
            elif kind=='outcome_audit':prediction['payload']['timing_comparison']={'reported_year':1998}
            else:prediction['payload']['known_feedback_record_keys']=[future['record_key']]
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                import_cases(self.db,self.source['revision_id'],bad)
        with connect(self.db) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],before)
