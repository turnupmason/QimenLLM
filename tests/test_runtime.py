import io
import json
from unittest.mock import patch
from qimenllm.api.app import create_app
from qimenllm.contracts import Analysis, CastingResult, Chart, Claim, GenerationError, Inquiry
from qimenllm.knowledge.db import connect
from qimenllm.reasoning.service import QimenService
from qimenllm.retrieval.repository import KnowledgeRepository
from qimenllm.rules.selector import RuleSelector, evaluate
from qimenllm.verification.evidence import EvidenceVerifier
from support import DatabaseTest


class FixtureCasting:
    """Neutral engineering object; not a real chart engine."""
    def cast(self,inquiry):
        return CastingResult('fixture_only',Chart('fixture-chart','fixture','test-v1',
                            '{"fixture_fact":"fixture_value"}','engine_verified'),'test double')


class CapturingFixtureModel:
    def __init__(self): self.calls=[]
    def analyze(self,inquiry,chart,rules):
        self.calls.append((chart,rules))
        return Analysis((Claim('chart_fact',chart.chart_id,'fixture_fact','"fixture_value"'),
                         Claim('rule_binding',rules[0]['rule_id'],'fixture_role','"fixture_symbol"')))


def request(app,payload,path='/v1/ask',method='POST',content_type='application/json'):
    body=json.dumps(payload).encode()
    statuses=[]
    environ={'PATH_INFO':path,'REQUEST_METHOD':method,'CONTENT_TYPE':content_type,
             'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
    result=b''.join(app(environ,lambda status,headers:statuses.append(status)))
    return statuses[0],json.loads(result)


class RuleTests(DatabaseTest):
    def decisions(self,context,method=None):
        rules=KnowledgeRepository(self.db).candidates('engineering')['rules']
        return RuleSelector().select(rules,context,method)

    def test_missing_is_conditional_not_true(self):
        self.seed_rule()
        for context in ({},{'relationship':None}):
            self.assertEqual(self.decisions(context)[0]['status'],'conditional')
        self.assertEqual(self.decisions({'relationship':'peer'})[0]['status'],'applicable')

    def test_relation_is_not_derived_from_age_or_semantics(self):
        self.seed_rule(expected='explicit_category')
        self.assertEqual(self.decisions({'age':80})[0]['status'],'conditional')
        self.assertEqual(self.decisions({'relationship':'other_category','age':80})[0]['status'],'excluded')

    def test_method_isolation_and_multiple_methods(self):
        self.seed_rule()
        self.seed_rule(suffix='b',method='method-b')
        self.assertEqual({r['status'] for r in self.decisions({'relationship':'peer'})},{'disputed'})
        selected=self.decisions({'relationship':'peer'},'method-a')
        self.assertEqual([r['status'] for r in selected],['applicable','excluded'])

    def test_reference_and_disagreement_cannot_bind(self):
        self.seed_rule(reference_only=1)
        self.assertEqual(self.decisions({'relationship':'peer'})[0]['status'],'reference_only')
        self.assertEqual(RuleSelector().bind(self.decisions({'relationship':'peer'})),())

    def test_unconfirmed_original_does_not_make_executable_rule(self):
        source,_=self.seed_rule()
        with connect(self.db) as conn:
            conn.execute("INSERT INTO source_reviews VALUES ('dispute',?,'disputed','fixture','fixture','now')",(source['revision_id'],))
        self.assertEqual(self.decisions({'relationship':'peer'})[0]['status'],'reference_only')

    def test_exclusion_and_strict_json_types(self):
        self.seed_rule(kind='exclude',expected='blocked')
        self.assertEqual(self.decisions({'relationship':'blocked'})[0]['status'],'excluded')
        self.assertEqual(self.decisions({'relationship':'allowed'})[0]['status'],'applicable')
        condition={'field':'x','operator':'eq','expected_json':'true'}
        self.assertFalse(evaluate(condition,{'x':1}))
        condition.update(operator='in',expected_json='[true,"yes"]')
        self.assertFalse(evaluate(condition,{'x':1}))

    def test_conflicting_role_bindings_blocked(self):
        selector=RuleSelector()
        with self.assertRaises(ValueError):
            selector.bind([{'status':'applicable','binding':{'x':'a'}},
                           {'status':'applicable','binding':{'x':'b'}}])


class RuntimeTests(DatabaseTest):
    def fixture_service(self,model=None,verifier=None):
        self.seed_rule()
        return QimenService(self.db,casting=FixtureCasting(),model=model or CapturingFixtureModel(),verifier=verifier)

    def inquiry(self): return Inquiry('Engineering fixture question',domain='engineering',context={'relationship':'peer'})

    def test_empty_official_flow_queries_database_and_does_not_call_model(self):
        model=CapturingFixtureModel()
        service=QimenService(self.db,model=model)
        with patch.object(service.knowledge,'candidates',wraps=service.knowledge.candidates) as query:
            result=service.ask(Inquiry('普通问题'))
            query.assert_called_once_with(None)
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(result['professional_analysis_completed'])
        self.assertEqual(model.calls,[])
        self.assertEqual([t['stage'] for t in result['trace']],
                         ['understanding','casting','retrieval','selection','binding','model','verification','rendering','final_check'])

    def test_real_database_rules_reach_model_via_official_service(self):
        model=CapturingFixtureModel()
        service=self.fixture_service(model=model)
        result=service.ask(self.inquiry())
        self.assertEqual(result['status'],'structurally_verified')
        self.assertFalse(result['professional_analysis_completed'])
        self.assertEqual(model.calls[0][1][0]['rule_id'],'fixture-rule')
        self.assertEqual(model.calls[0][0].chart_id,result['chart_id'])
        self.assertEqual(result['trace'][-1]['status'],'passed')
        # Counterfactual: a rule from another domain cannot reach this same model.
        result=service.ask(Inquiry('Fixture',domain='other',context={'relationship':'peer'}))
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(len(model.calls),1)

    def test_missing_condition_blocks_model_even_with_chart(self):
        model=CapturingFixtureModel(); service=self.fixture_service(model=model)
        result=service.ask(Inquiry('Fixture',domain='engineering'))
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(model.calls,[])

    def test_generation_protocol_errors_separate_from_evidence_errors(self):
        class BadProtocol:
            def analyze(self,*args): return {'claims':'not the protocol'}
        result=self.fixture_service(model=BadProtocol()).ask(self.inquiry())
        self.assertEqual(result['status'],'generation_error')
        self.assertFalse(any(t['stage']=='verification' for t in result['trace']))

    def test_model_failure_classified(self):
        class Truncated:
            def analyze(self,*args): raise GenerationError('fixture truncation')
        result=self.fixture_service(model=Truncated()).ask(self.inquiry())
        self.assertEqual(result['status'],'generation_error')

    def test_hallucinated_or_wrong_facts_cannot_render(self):
        class Wrong:
            def analyze(self,*args): return Analysis((Claim('chart_fact','fixture-chart','fixture_fact','"WRONG"'),))
        result=self.fixture_service(model=Wrong()).ask(self.inquiry())
        self.assertEqual(result['status'],'verification_failed')
        self.assertNotIn('WRONG',result['message'])
        self.assertFalse(any(t['stage']=='rendering' for t in result['trace']))

    def test_final_text_cannot_change_validated_values(self):
        class BadRenderer(EvidenceVerifier):
            def verify_rendered(self,text,analysis): return False
        result=self.fixture_service(verifier=BadRenderer()).ask(self.inquiry())
        self.assertEqual(result['status'],'final_verification_failed')

    def test_empty_analysis_is_not_success(self):
        class Empty:
            def analyze(self,*args): return Analysis(())
        result=self.fixture_service(model=Empty()).ask(self.inquiry())
        self.assertEqual(result['status'],'verification_failed')

    def test_unknown_rule_unverified_chart_rejected(self):
        verifier=EvidenceVerifier()
        analysis=Analysis((Claim('rule_binding','nonexistent','x','1'),))
        chart=Chart('x','fixture','v1','{}','engine_unverified')
        report=verifier.verify(analysis,chart,())
        self.assertEqual(set(report['errors']),{'chart_not_verified','unavailable_rule'})

    def test_api_uses_same_service_and_no_write_routes(self):
        service=QimenService(self.db)
        app=create_app(service)
        with patch.object(service,'ask',wraps=service.ask) as entry:
            status,result=request(app,{'text':'普通问题'})
            self.assertEqual(status,'200 OK'); entry.assert_called_once()
            self.assertEqual(result['status'],'blocked')
        status,_=request(app,{},'/v1/import')
        self.assertEqual(status,'404 Not Found')

    def test_api_fixture_runs_full_database_model_verification_path(self):
        model=CapturingFixtureModel(); service=self.fixture_service(model=model)
        status,result=request(create_app(service),{'text':'fixture','domain':'engineering','context':{'relationship':'peer'}})
        self.assertEqual(status,'200 OK')
        self.assertEqual(result['status'],'structurally_verified')
        self.assertEqual(len(model.calls),1)

    def test_api_rejects_invalid_types_and_oversize(self):
        app=create_app(QimenService(self.db))
        for payload in ([], {'text':12}, {'text':'x','context':[]}, {'text':'x','override_rules':True}, {'text':'x'*70000}):
            self.assertEqual(request(app,payload)[0],'400 Bad Request')
        self.assertEqual(request(app,{'text':'x'},content_type='text/plain')[0],'400 Bad Request')
        self.assertEqual(request(app,{'text':'x','context':{'bad':float('inf')}})[0],'400 Bad Request')

    def test_learning_empty_then_reads_actual_new_source(self):
        service=QimenService(self.db)
        self.assertEqual(service.learning.learn('工程')['status'],'awaiting_sources')
        self.ingest('工程学习样本，保持原文。'.encode())
        status,result=request(create_app(service),{'term':'工程'},'/v1/learn')
        self.assertEqual(status,'200 OK')
        self.assertEqual(result['original_sources'][0]['body'],'工程学习样本，保持原文。')
        self.assertIsNone(result['model_analysis'])

    def test_trace_does_not_include_question_or_private_context(self):
        secret='private-name-example'
        service=QimenService(self.db)
        result=service.ask(Inquiry(secret,context={'name':secret}))
        self.assertNotIn(secret,json.dumps(result,ensure_ascii=False))

    def test_opt_in_local_debug_captures_actual_model_request_and_output(self):
        self.seed_rule()
        service=QimenService(self.db,casting=FixtureCasting(),model=CapturingFixtureModel(),capture_debug=True)
        result=service.ask(self.inquiry())
        request_trace=next(t for t in result['trace'] if t['stage']=='model_request')
        output_trace=next(t for t in result['trace'] if t['stage']=='model')
        self.assertEqual(request_trace['active_rules'][0]['rule_id'],'fixture-rule')
        self.assertEqual(output_trace['raw_output']['claims'][0]['reference'],'fixture-chart')
