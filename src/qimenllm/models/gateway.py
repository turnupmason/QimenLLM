from ..contracts import ModelUnavailable


class UnconfiguredModelGateway:
    def analyze(self, inquiry, chart, rules):
        raise ModelUnavailable('No model configured; no model request was made')
