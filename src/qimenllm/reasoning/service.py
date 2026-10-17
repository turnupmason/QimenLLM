"""The only official inquiry orchestrator. All entry points call this service."""
from __future__ import annotations
from dataclasses import asdict
from uuid import uuid4
from ..contracts import Analysis, GenerationError, Inquiry, ModelUnavailable
from ..casting.engine import SourceCastingEngine
from ..casting.foundations import FoundationCalculator
from ..casting.paper import PaperCalculator
from ..casting.judgment_facts import JudgmentFactsCalculator
from ..casting.application_facts import ApplicationFactsCalculator
from ..conversation.interpreter import ExplicitContextInterpreter
from ..models.gateway import UnconfiguredModelGateway
from ..retrieval.repository import KnowledgeRepository
from ..rules.selector import RuleSelector
from ..verification.evidence import EvidenceVerifier
from ..learning.service import LearningService


class QimenService:
    def __init__(self, db, *, casting=None, model=None, interpreter=None, verifier=None, capture_debug=False):
        self.knowledge = KnowledgeRepository(db)
        self.paper = PaperCalculator(self.knowledge)
        self.judgment_facts = JudgmentFactsCalculator(self.knowledge)
        self.application_facts = ApplicationFactsCalculator(self.knowledge)
        self.casting = casting or SourceCastingEngine(self.paper)
        self.model = model or UnconfiguredModelGateway()
        self.interpreter = interpreter or ExplicitContextInterpreter()
        self.selector = RuleSelector()
        self.verifier = verifier or EvidenceVerifier()
        self.learning = LearningService(self.knowledge)
        self.foundations = FoundationCalculator(self.knowledge)
        self.capture_debug = capture_debug  # trusted local callers only; never persisted

    def calculate(self, operation: str, args: dict) -> dict:
        if operation=='chart_observations':
            layout=self.paper.calculate('symbolic_chart',args)
            if layout['status']!='computed': return {**layout,'operation':operation}
            immutable=self.paper.immutable_chart(layout)
            chart=immutable.facts(); observations={}
            for palace,door in chart['doors'].items():
                if door is not None:
                    observations[palace]=self.judgment_facts.calculate('door_palace_relation',
                        {'door':door,'palace':int(palace)})
            return {'status':'computed' if all(v['status']=='computed' for v in observations.values()) else 'partial',
                    'operation':operation,'chart_id':chart['chart_id'],'chart':chart,
                    'layout_evidence':layout['evidence'],'door_palace_observations':observations,
                    'professional_analysis_completed':False,'complete_chart':False,
                    'calendar_recomputed':False,'model_analysis':None,
                    'scope':'same_symbolic_chart_directional_facts_only_not_event_prediction'}
        if operation in self.application_facts.OPERATIONS:
            return self.application_facts.calculate(operation,args)
        if operation in self.judgment_facts.OPERATIONS:
            return self.judgment_facts.calculate(operation,args)
        if operation in self.paper.OPERATIONS:
            return self.paper.calculate(operation,args)
        return self.foundations.calculate(operation,args)

    def reference(self, family: str, filters: dict) -> dict:
        return self.learning.reference(family,filters)

    def rule_candidates(self,context: dict,domain=None,method=None) -> dict:
        from ..rules.candidates import inspect_candidates
        return inspect_candidates(self.knowledge.db,context,domain=domain,method=method)

    def case(self,case_id: str,view: str='full') -> dict:
        from ..cases.inspection import inspect_case
        return inspect_case(self.knowledge.db,case_id,view=view)

    def cases(self,chapter_key=None) -> dict:
        from ..cases.inspection import list_cases
        return list_cases(self.knowledge.db,chapter_key)

    def case_chart(self,case_id,chart_id,comparison_method=None) -> dict:
        from ..cases.source_chart import project_chart,compare_chart
        if comparison_method is not None and (not isinstance(comparison_method,str) or not comparison_method):
            raise ValueError('Explicit comparison method required')
        result=project_chart(self.knowledge.db,case_id,chart_id)
        if comparison_method is not None:
            result['comparison']=compare_chart(result,self.paper,comparison_method)
        return result

    def ask(self, inquiry: Inquiry) -> dict:
        if not isinstance(inquiry.text,str) or not inquiry.text.strip(): raise ValueError('Nonempty question required')
        trace = []
        def record(stage, status, **values): trace.append({'stage':stage,'status':status,**values})
        understanding = self.interpreter.interpret(inquiry)
        record('understanding',understanding['status'],domain=understanding['domain'])
        casting = self.casting.cast(inquiry)
        chart = casting.chart
        record('casting',casting.status,chart_id=chart.chart_id if chart else None,reason=casting.reason)
        retrieval = self.knowledge.candidates(understanding['domain'])
        candidate_inspection = (self.rule_candidates(understanding['context'],domain=understanding['domain'],
                                method=inquiry.method_id) if understanding['domain'] else None)
        # Context values remain in memory, not in persisted logs or the default API trace.
        record('retrieval','queried',query=retrieval['query'],
               candidate_ids=[r['rule_id'] for r in retrieval['rules']],
               source_candidate_query=candidate_inspection['query'] if candidate_inspection else None)
        decisions = self.selector.select(retrieval['rules'], understanding['context'], inquiry.method_id)
        record('selection','evaluated',decisions=[{'rule_id':r['rule_id'],'source_id':r['source_id'],
               'status':r['status'],'reasons':r['reasons'],'missing':r['missing']} for r in decisions],
               source_candidates=[{'candidate_key':r['candidate_key'],'source_id':r['source']['source_id'],
                   'symbolic_status':r['symbolic_status'],'activation_status':r['activation_status'],
                   'reasons':r['reasons'],'missing':r['missing']} for r in
                   candidate_inspection['candidates']] if candidate_inspection else [])
        binding_error = None
        try: active = self.selector.bind(decisions)
        except ValueError as exc: active=(); binding_error=str(exc)
        record('binding','blocked' if binding_error else 'evaluated',
               rule_ids=[r['rule_id'] for r in active],error=binding_error)
        result = {'request_id':str(uuid4()),'status':'blocked','professional_analysis_completed':False,
                  'chart_id':chart.chart_id if chart else None, 'rule_ids':[r['rule_id'] for r in active],
                  'chart':asdict(chart) if chart else None,
                  'message':'完整起盘和专业断案链路尚未验证完成，当前不能进行奇门断案。', 'trace':trace}
        if chart is None or chart.validation_status!='engine_verified' or not active or binding_error or understanding['status']=='not_implemented':
            record('model','skipped',reason='prerequisites_missing')
            record('verification','not_run',reason='no_generated_analysis')
            record('rendering','status_message_only')
            record('final_check','status_message_only')
            return result
        try:
            if self.capture_debug:
                record('model_request','prepared',inquiry=asdict(inquiry),chart=asdict(chart),
                       active_rules=list(active))
            analysis = self.model.analyze(inquiry,chart,active)
            if not isinstance(analysis,Analysis): raise GenerationError('Invalid structured output contract')
            details = {'raw_output':asdict(analysis)} if self.capture_debug else {}
            record('model','generated',claim_count=len(analysis.claims),**details)
        except ModelUnavailable:
            result.update(status='model_unavailable',message='模型尚未配置，未生成分析。')
            record('model','unavailable'); return result
        except GenerationError:
            result.update(status='generation_error',message='结构化生成失败，未形成专业分析。')
            record('model','generation_error'); return result
        verification = self.verifier.verify(analysis,chart,active)
        record('verification','passed' if verification['ok'] else 'failed',**verification)
        if not verification['ok']:
            result.update(status='verification_failed',message='证据校验未通过，未输出分析。')
            return result
        rendered = self.verifier.render(analysis)
        record('rendering','rendered_verified_values')
        if not self.verifier.verify_rendered(rendered,analysis):
            record('final_check','failed')
            result.update(status='final_verification_failed',message='最终文字校验未通过。')
            return result
        record('final_check','passed')
        result.update(status='structurally_verified',message=rendered,
                      limitation='仅验证结构化事实引用；专业推断与自然语言解释层尚未实现。')
        # Structural success is never counted as a professional diagnosis/prediction.
        return result
