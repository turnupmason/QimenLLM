from ..contracts import Inquiry


class ExplicitContextInterpreter:
    """Phase 0 adapter: preserves supplied context; natural-language extraction is pending."""
    def interpret(self, inquiry: Inquiry) -> dict:
        return {'domain':inquiry.domain, 'context':dict(inquiry.context),
                'status':'explicit_context' if inquiry.domain else 'not_implemented',
                'missing':[] if inquiry.domain else ['question_understanding']}
