from ..contracts import CastingResult, Inquiry
from .paper import PAPER_METHOD, PaperCalculator


class UnimplementedCastingEngine:
    def cast(self, inquiry: Inquiry) -> CastingResult:
        return CastingResult('not_implemented', None, '完整历法与全盘算法尚未实现并验证，未生成完整盘面。')


class SourceCastingEngine:
    """Official entry for explicit symbolic casting; no implicit calendar defaults."""
    def __init__(self, paper: PaperCalculator):
        self.paper=paper

    def cast(self, inquiry: Inquiry) -> CastingResult:
        if inquiry.casting_method is None:
            return UnimplementedCastingEngine().cast(inquiry)
        if inquiry.casting_method!=PAPER_METHOD:
            return CastingResult('not_covered',None,'尚未实现所指定的起局方法。')
        args={k:inquiry.context[k] for k in ('dun','bureau','hour_ganzhi') if k in inquiry.context}
        result=self.paper.calculate('symbolic_chart',{'method':PAPER_METHOD,**args})
        if result['status']!='computed':
            return CastingResult(result['status'],None,result.get('reason','起局符号条件不足。'))
        return CastingResult('symbolic_verified',self.paper.immutable_chart(result),
                             '仅验证已知遁局及时干支的转盘；历法、空亡马星与专业角色未完成。')
