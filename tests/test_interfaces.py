from dataclasses import FrozenInstanceError
import io
import json
from contextlib import redirect_stdout
from qimenllm.calendar.interface import TimeContext, UnimplementedCalendar
from qimenllm.casting.engine import UnimplementedCastingEngine
from qimenllm.cli import main
from qimenllm.contracts import Chart, Inquiry
from qimenllm.evaluation.metrics import summarize
from qimenllm.models.gateway import UnconfiguredModelGateway
from qimenllm.reasoning.service import QimenService
from support import DatabaseTest
from test_runtime import FixtureCasting


class InterfaceTests(DatabaseTest):
    def test_chart_object_and_returned_facts_cannot_mutate_shared_chart(self):
        chart=Chart('fixture','fixture','v1','{"nested":{"value":1}}','engine_unverified')
        with self.assertRaises(FrozenInstanceError): chart.chart_id='changed'
        facts=chart.facts(); facts['nested']['value']=999
        self.assertEqual(chart.facts()['nested']['value'],1)

    def test_calendar_and_casting_report_unimplemented(self):
        context=TimeContext('original',None,None,None,None,None)
        with self.assertRaises(NotImplementedError): UnimplementedCalendar().normalize(context,'unknown')
        self.assertIsNone(UnimplementedCastingEngine().cast(Inquiry('fixture')).chart)

    def test_model_unavailable_is_not_a_knowledge_failure(self):
        self.seed_rule()
        service=QimenService(self.db,casting=FixtureCasting(),model=UnconfiguredModelGateway())
        result=service.ask(Inquiry('fixture',domain='engineering',context={'relationship':'peer'}))
        self.assertEqual(result['status'],'model_unavailable')

    def test_cli_init_ask_and_backup_use_current_code(self):
        for args in (['init'],['ask','fixture'],['backup',str(self.root/'backup.sqlite3')]):
            output=io.StringIO()
            with redirect_stdout(output):
                code=main(['--db',str(self.db),'--raw-dir',str(self.raw),*args])
            self.assertEqual(code,0)
            result=json.loads(output.getvalue())
            if args[0]=='ask': self.assertEqual(result['status'],'blocked')
        self.assertTrue((self.root/'backup.sqlite3').exists())

    def test_refusals_and_format_errors_are_not_counted_as_professional_success(self):
        result=summarize([{'status':'blocked','professional_analysis_completed':False},
                          {'status':'generation_error'}, {'status':'structurally_verified'}])
        self.assertEqual(result['professional_completions'],0)
        self.assertEqual(result['generation_failures'],1)
        self.assertIsNone(result['professional_correctness'])
