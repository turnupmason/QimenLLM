"""The only official inquiry orchestrator. All entry points call this service."""
from __future__ import annotations
from dataclasses import asdict
from uuid import uuid4
from ..contracts import Analysis, GenerationError, Inquiry, ModelUnavailable
from ..casting.engine import UnimplementedCastingEngine
from ..casting.foundations import FoundationCalculator
from ..conversation.interpreter import ExplicitContextInterpreter
from ..models.gateway import UnconfiguredModelGateway
from ..retrieval.repository import KnowledgeRepository
from ..rules.selector import RuleSelector
from ..verification.evidence import EvidenceVerifier
from ..learning.service import LearningService


class QimenService:
    def __init__(self, db, *, casting=None, model=None, interpreter=None, verifier=None, capture_debug=False):
        self.knowledge = KnowledgeRepository(db)
        self.casting = casting or UnimplementedCastingEngine()
        self.model = model or UnconfiguredModelGateway()
        self.interpreter = interpreter or ExplicitContextInterpreter()
        self.selector = RuleSelector()
        self.verifier = verifier or EvidenceVerifier()
        self.learning = LearningService(self.knowledge)
        self.foundations = FoundationCalculator(self.knowledge)
        self.capture_debug = capture_debug  # trusted local callers only; never persisted

    def calculate(self, operation: str, args: dict) -> dict:
        return self.foundations.calculate(operation,args)

    def ask(self, inquiry: Inquiry) -> dict:
        if not isinstance(inquiry.text,str) or not inquiry.text.strip(): raise ValueError('Nonempty question required')
        trace = []
        def record(stage, status, **values): trace.append({'stage':stage,'status':status,**values})
        understanding = self.interpreter.interpret(inquiry)
        record('understanding',understanding['status'],domain=understanding['domain'])
        casting = self.casting.cast(inquiry)
        chart = casting.chart
        record('casting',casting.status,chart_id=chart.chart_id if chart else None)
        retrieval = self.knowledge.candidates(understanding['domain'])
        # Context values remain in memory, not in persisted logs or the default API trace.
        record('retrieval','queried',query=retrieval['query'],
               candidate_ids=[r['rule_id'] for r in retrieval['rules']])
        decisions = self.selector.select(retrieval['rules'], understanding['context'], inquiry.method_id)
        record('selection','evaluated',decisions=[{'rule_id':r['rule_id'],'source_id':r['source_id'],
               'status':r['status'],'reasons':r['reasons'],'missing':r['missing']} for r in decisions])
        binding_error = None
        try: active = self.selector.bind(decisions)
        except ValueError as exc: active=(); binding_error=str(exc)
        record('binding','blocked' if binding_error else 'evaluated',
               rule_ids=[r['rule_id'] for r in active],error=binding_error)
        result = {'request_id':str(uuid4()),'status':'blocked','professional_analysis_completed':False,
                  'chart_id':chart.chart_id if chart else None, 'rule_ids':[r['rule_id'] for r in active],
                  'message':'完整起盘和专业断案链路尚未验证完成，当前不能进行奇门断案。', 'trace':trace}
        if chart is None or not active or binding_error or understanding['status']=='not_implemented':
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
