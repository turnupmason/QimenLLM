from ..contracts import CastingResult, Inquiry


class UnimplementedCastingEngine:
    def cast(self, inquiry: Inquiry) -> CastingResult:
        return CastingResult('not_implemented', None, '完整历法与全盘算法尚未实现并验证，未生成完整盘面。')
