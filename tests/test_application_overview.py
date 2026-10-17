"""Exact supplied examples and public entry points; no forecast accuracy claims."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.cli import main
from qimenllm.cases.ingestion import import_cases
from qimenllm.contracts import Inquiry
from qimenllm.knowledge.application_overview import SOURCE_SHA, install_application
from qimenllm.knowledge.chapter02 import install_chapter02
from qimenllm.knowledge.chapters0405 import install_chapter
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.importer import import_chapter
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
from qimenllm.rules.candidates import install_candidates
from support import DatabaseTest
from test_runtime import request, CapturingFixtureModel

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/structured/shenqi'


class ApplicationOverviewTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        for n in (1,2,4,5):
            c=json.loads((DATA/f'chapter{n:02d}_curated.json').read_bytes())
            r=import_chapter(self.db,self.raw,(ROOT/'data/snapshots/current/raw'/f"{c['source_sha256']}.bin").read_bytes(),
                book_key='shenqi-user-text-v1',book_title='神奇之门',chapter_key=f'chapter-{n:02d}',
                chapter_title=c['chapter_title'],sequence=n,origin='supplied-source-regression')
            if n==1: install_curated(self.db,r['revision_id'],c)
            elif n==2: install_chapter02(self.db,r['revision_id'],c)
            else: install_chapter(self.db,r['revision_id'],c,n)
        self.curation=json.loads((DATA/'application_overview_curated.json').read_bytes())
        self.content=(ROOT/'data/snapshots/current/raw'/f'{SOURCE_SHA}.bin').read_bytes()
        self.source=import_chapter(self.db,self.raw,self.content,book_key='shenqi-user-text-v1',book_title='神奇之门',
            chapter_key='application-overview',chapter_title='奇门遁甲应用概述',sequence=6,origin='supplied-source-regression')
        install_application(self.db,self.source['revision_id'],self.curation)
        install_candidates(self.db,self.source['revision_id'],json.loads((DATA/'application_overview_rule_candidates.json').read_bytes()))
        self.service=QimenService(self.db)

    def result(self,op,**args):
        r=self.service.calculate(op,args)
        self.assertEqual(r['status'],'computed',r)
        self.assertTrue(r['evidence']); self.assertFalse(r['professional_analysis_completed'])
        self.assertFalse(r['calendar_recomputed']); return r['result']

    def test_original_exact_coverage_and_idempotence(self):
        self.assertEqual(digest(self.content),SOURCE_SHA)
        self.assertEqual((len(self.content),len(self.content.decode()),len(self.content.splitlines())),(32020,11062,479))
        self.assertFalse(self.content.endswith(b'\n'))
        covered={n for g in self.curation['groups'] for n in range(g['line_start'],g['line_end']+1)}
        self.assertTrue({n for n,l in enumerate(self.content.splitlines(),1) if l.strip()}<=covered)
        r=install_application(self.db,self.source['revision_id'],self.curation)
        for k in ('structured_records_added','compiled_families_added','methods_added','concept_entries_added'):
            self.assertEqual(r[k],0)
        bad=copy.deepcopy(self.curation); bad['source_sha256']='0'*64
        with self.assertRaises(ValueError): install_application(self.db,self.source['revision_id'],bad)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_sixteen_inner_outer_source_classifications_and_no_center_inference(self):
        for dun,inner,outer in (('阳遁',(1,8,3,4),(9,2,7,6)),('阴遁',(9,2,7,6),(1,8,3,4))):
            for palaces,classification in ((inner,'内'),(outer,'外')):
                for palace in palaces:
                    r=self.result('inner_outer',dun=dun,palace=palace)
                    self.assertEqual(r['classification'],classification)
                    self.assertIsNone(r['exact_duration']); self.assertIsNone(r['exact_distance'])
        self.assertEqual(self.service.calculate('inner_outer',{'dun':'阳遁','palace':5})['status'],'not_covered')
        self.assertEqual(self.service.calculate('inner_outer',{'palace':1})['status'],'conditional')
        with self.assertRaises(ValueError): self.service.calculate('inner_outer',{'dun':'阳遁','palace':True})

    def test_horizontal_uses_actual_palaces_and_vertical_fixed_symbol_elements(self):
        r=self.result('horizontal_palace_relation',first_palace=9,second_palace=6)
        self.assertEqual((r['first_palace_element'],r['second_palace_element'],r['relation_kind']),('火','金','controls'))
        self.assertFalse(r['fixed_symbol_elements_used']); self.assertEqual(r['role_bindings'],[])
        self.assertEqual(self.result('horizontal_palace_relation',first_palace=6,second_palace=9)['relation_kind'],'controlled_by')
        self.assertEqual(self.result('horizontal_palace_relation',first_palace=3,second_palace=4)['relation_kind'],'same_element')
        for kind,name in (('star','天心星'),('door','开门')):
            self.assertEqual(self.result('vertical_symbol_relation',kind=kind,name=name,palace=3)['relation_kind'],'controls')
        r=self.result('vertical_symbol_relation',kind='deity',name='白虎',palace=3)
        self.assertEqual(r['status'],'reference_only'); self.assertIsNone(r['relation_kind'])
        self.assertEqual(self.service.calculate('horizontal_palace_relation',{'first_palace':5,'second_palace':2})['status'],'not_covered')

    def test_nine_exact_chief_timing_examples_no_calendar_extrapolation(self):
        # Source lines405 and409; expectations transcribed independently of compiler rows.
        gold=(('甲子',9,'冲','丑'),('甲午',1,'冲','未'),('甲寅',2,'冲','亥'),
              ('甲申',8,'冲','巳'),('甲戌',4,'冲','卯'),('甲辰',6,'冲','酉'),
              ('甲戌',2,'刑','卯'),('甲子',3,'刑','丑'),('甲寅',4,'刑','亥'))
        for xun,palace,trigger,branch in gold:
            r=self.result('timing_chief_example',xun_head=xun,palace=palace,trigger=trigger)
            self.assertEqual(r['branch'],branch); self.assertIsNone(r['calendar_date'])
            self.assertFalse(r['timing_prediction_completed'])
        self.assertEqual(self.service.calculate('timing_chief_example',{'xun_head':'甲子','palace':2,'trigger':'冲'})['status'],'not_covered')

    def test_service_api_cli_and_actual_ask_share_conditional_database_inspection(self):
        artifact=json.loads((DATA/'application_overview_regression_cases.json').read_bytes())
        context=next(c['context'] for c in artifact['selection_cases'] if c['expected']['symbolic_status']=='applicable')
        expected=self.service.rule_candidates(context,context['domain'])
        status,result=request(create_app(self.service),{'context':context,'domain':context['domain']},'/v1/rule-candidates')
        self.assertEqual(status,'200 OK'); self.assertEqual(result,expected)
        output=io.StringIO()
        with redirect_stdout(output):
            code=main(['--db',str(self.db),'rule-candidates','--context',json.dumps(context),'--domain',context['domain']])
        self.assertEqual(code,0); self.assertEqual(json.loads(output.getvalue()),expected)
        model=CapturingFixtureModel(); service=QimenService(self.db,model=model)
        with patch.object(service,'rule_candidates',wraps=service.rule_candidates) as query:
            answer=service.ask(Inquiry('研究已给条件',domain=context['domain'],context=context))
            query.assert_called_once()
        self.assertEqual(answer['status'],'blocked'); self.assertEqual(model.calls,[])
        self.assertTrue(next(t for t in answer['trace'] if t['stage']=='selection')['source_candidates'])
        self.assertEqual(request(create_app(service),{'context':[]},'/v1/rule-candidates')[0],'400 Bad Request')

    def test_snapshot_restores_same_actual_application_results(self):
        expected=self.service.calculate('inner_outer',{'dun':'阴遁','palace':2})
        export_snapshot(self.db,self.raw,self.root/'snapshot')
        restore_snapshot(self.root/'snapshot',self.root/'restored.sqlite3',self.root/'restored-raw')
        self.assertEqual(QimenService(self.root/'restored.sqlite3').calculate('inner_outer',{'dun':'阴遁','palace':2}),expected)

    def test_given_satellite_symbols_reproduce_reported_partial_positions_only(self):
        # Original case lines58–64 supply these symbols. This is an explicit
        # comparison under chapter-two paper conventions, not calendar validation.
        chart=self.service.calculate('symbolic_chart',{'dun':'阳遁','bureau':9,
            'hour_ganzhi':'癸卯','method':'shenqi_ch2_paper_v1'})['result']
        facts=chart['derived_facts']
        self.assertEqual((facts['zhifu_star'],facts['zhishi_door']),('天冲星','伤门'))
        self.assertEqual((facts['zhifu_landing_original_palace'],facts['zhifu_layout_palace']),(5,2))
        self.assertEqual(facts['zhishi_landing_palace'],3)
        self.assertEqual(chart['deities']['9'],'九天')
        self.assertEqual(chart['earth_plate']['9'],'戊')
        self.assertEqual(chart['heaven_plate']['9'][0]['carried_stem'],'乙')
        self.assertEqual((chart['earth_plate']['5'],chart['earth_plate']['2']),('癸','庚'))
        self.assertEqual(chart['heaven_plate']['2'][0]['carried_stem'],'辛')
        self.assertIsNone(chart['four_pillars']['day']); self.assertFalse(chart['calendar_recomputed'])
        self.assertTrue(self.service.calculate('five_missed_hour',{'day_stem':'丁','hour_ganzhi':'癸卯'})['result']['listed_hour_match'])

    def test_full_and_before_prediction_case_views_reach_same_cli_api_service(self):
        imported=import_cases(self.db,self.source['revision_id'],json.loads((DATA/'application_overview_cases.json').read_bytes()))
        case_id=imported['cases'][0]['case_id']
        for view in ('full','before_prediction'):
            expected=self.service.case(case_id,view)
            with patch.object(self.service,'case',wraps=self.service.case) as query:
                status,r=request(create_app(self.service),{'case_id':case_id,'view':view},'/v1/case')
                query.assert_called_once_with(case_id,view)
            self.assertEqual(status,'200 OK'); self.assertEqual(r,expected)
            output=io.StringIO()
            with redirect_stdout(output): code=main(['--db',str(self.db),'case',case_id,'--view',view])
            self.assertEqual(code,0); self.assertEqual(json.loads(output.getvalue()),expected)
        self.assertEqual(request(create_app(self.service),{'case_id':'missing'},'/v1/case')[0],'404 Not Found')
        self.assertEqual(request(create_app(self.service),{'case_id':case_id,'view':'unknown'},'/v1/case')[0],'400 Bad Request')
