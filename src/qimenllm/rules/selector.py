"""Small explicit condition language. No learned ranking can override these gates."""
import json


def evaluate(condition: dict, context: dict) -> bool | None:
    field = condition['field']
    if field not in context or context[field] is None:
        return None
    actual = context[field]
    expected = json.loads(condition['expected_json'])
    operator = condition['operator']
    # JSON booleans and numbers must not compare equal merely because Python permits it.
    equal = type(actual) is type(expected) and actual == expected
    if operator == 'eq': return equal
    if operator == 'ne': return not equal
    if operator == 'present': return True
    if operator == 'in':
        if not isinstance(expected,list): raise ValueError('in condition requires array')
        return any(type(actual) is type(v) and actual == v for v in expected)
    raise ValueError(f'Unsupported condition operator: {operator}')


class RuleSelector:
    def select(self, candidates: list[dict], context: dict, method_id: str | None) -> list[dict]:
        results = []
        for rule in candidates:
            reasons, missing = [], []
            state = 'applicable'
            if method_id is not None and rule['method_id'] != method_id:
                state, reasons = 'excluded', ['method_mismatch']
            else:
                for condition in rule['conditions']:
                    value = evaluate(condition, context)
                    if value is None: missing.append(condition['field'])
                    elif ((condition['kind']=='require' and not value) or
                          (condition['kind']=='exclude' and value)):
                        reasons.append('condition_failed:' + condition['condition_id'])
                if reasons: state = 'excluded'
                elif missing: state = 'conditional'
                elif rule['disputed'] or rule['conflicts']: state, reasons = 'disputed', ['unresolved_method_disagreement']
                elif (rule['reference_only'] or not rule['compiled'] or not rule['structured']
                      or not rule['applicability_confirmed'] or rule['source_status']!='confirmed'):
                    state, reasons = 'reference_only', ['not_approved_executable_rule']
            results.append({**rule, 'status':state, 'reasons':reasons, 'missing':sorted(set(missing))})
        methods = {r['method_id'] for r in results if r['status']=='applicable'}
        if method_id is None and len(methods)>1:
            for rule in results:
                if rule['status']=='applicable':
                    rule['status']='disputed'; rule['reasons']=['multiple_methods_require_selection']
        return results

    def bind(self, selected: list[dict]) -> tuple[dict, ...]:
        active = [r for r in selected if r['status']=='applicable']
        roles = {}
        for rule in active:
            for role, value in rule['binding'].items():
                if role in roles and roles[role]!=value:
                    raise ValueError('Conflicting role bindings require explicit method resolution')
                roles[role]=value
        return tuple(active)
