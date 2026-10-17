"""Strict structural fact/citation checks. Professional inference validation is not implemented."""
import json
from ..contracts import Analysis, Chart
from ..knowledge.importer import canonical


class EvidenceVerifier:
    def verify(self, analysis: Analysis, chart: Chart | None, rules: tuple[dict,...]) -> dict:
        errors = []
        if chart is None: return {'ok':False,'errors':['chart_unavailable'],'scope':'structural_only'}
        if chart.validation_status != 'engine_verified': errors.append('chart_not_verified')
        if not isinstance(analysis,Analysis):
            return {'ok':False,'errors':['analysis_protocol_invalid'],'scope':'structural_only'}
        if not analysis.claims: errors.append('empty_analysis')
        rule_index = {r['rule_id']:r for r in rules if r['status']=='applicable'}
        facts = chart.facts()
        for claim in analysis.claims:
            if claim.kind=='chart_fact':
                if claim.reference!=chart.chart_id or claim.key not in facts:
                    errors.append('unknown_chart_fact'); continue
                expected = facts[claim.key]
            elif claim.kind=='rule_binding':
                rule = rule_index.get(claim.reference)
                if rule is None or claim.key not in rule['binding']:
                    errors.append('unavailable_rule'); continue
                expected = rule['binding'][claim.key]
            else:
                errors.append('unsupported_claim_kind'); continue
            try:
                if canonical(json.loads(claim.value_json)) != canonical(expected): errors.append('fact_mismatch')
            except (ValueError,TypeError): errors.append('invalid_claim_json')
        return {'ok':not errors, 'errors':errors, 'scope':'structural_only'}

    def render(self, analysis: Analysis) -> str:
        # Copy verified values literally; no unconstrained second generation pass.
        return '\n'.join(f'{c.reference} / {c.key} = {c.value_json}' for c in analysis.claims)

    def verify_rendered(self, text: str, analysis: Analysis) -> bool:
        # Phase 0 renderer accepts only the exact verified rendering.
        return text == self.render(analysis)
