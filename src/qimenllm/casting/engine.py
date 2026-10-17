from ..contracts import CastingResult, Inquiry


class UnimplementedCastingEngine:
    def cast(self, inquiry: Inquiry) -> CastingResult:
        return CastingResult('not_implemented', None, '尚未提供并验证原书起盘算法，未生成盘面。')
