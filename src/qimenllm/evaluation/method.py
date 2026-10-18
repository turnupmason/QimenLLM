"""Source-reviewed method pilot through the sole QimenService.ask entry.

These are controlled, source-table exercises. No production chart/rule gate is
relaxed, and protocol/fact checks are never called professional prediction success.
"""
from dataclasses import dataclass
import copy
import hashlib
import json
from pathlib import Path

from ..contracts import GenerationError, ModelUnavailable
from ..knowledge.db import connect


ARMS = ('base', 'source_chart', 'source_chart_knowledge', 'source_chart_conditions')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class MethodRequest:
    manifest_path: str
    manifest_sha256: str
    data_dir: str
    split: str
    task_id: str
    arm: str = 'source_chart_conditions'


def load_task(request, db):
    raw = Path(request.manifest_path).read_bytes()
    if sha(raw) != request.manifest_sha256:
        raise ValueError('Frozen method manifest changed')
    release = json.loads(raw)
    if (release.get('frozen') is not True or request.split not in ('validation', 'test', 'development')
            or request.arm not in ARMS or release['release_id'] != 'shenqi-lost-method-tasks-v5'):
        raise ValueError('Unsupported method evaluation scope')
    name = request.split + '.jsonl'
    data = (Path(request.data_dir) / name).read_bytes()
    if sha(data) != release['files'][name]['sha256']:
        raise ValueError('Frozen method tasks changed')
    rows = [json.loads(line) for line in data.splitlines()]
    matches = [t for t in rows if t['task_id'] == request.task_id]
    if len(matches) != 1:
        raise ValueError('Task absent or duplicated')
    task = matches[0]
    if task['split'] != request.split or release['family_assignments'][task['family_id']] != request.split:
        raise ValueError('Task moved across frozen families')
    with connect(db) as con:
        version = con.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
        event = con.execute('SELECT family_id FROM events WHERE event_id=?', (task['event_id'],)).fetchone()
        if version != release['source_data_version'] or event is None or event['family_id'] != task['family_id']:
            raise ValueError('Task/source database mismatch')
    return task


def messages_for(task, arm):
    if arm not in ARMS:
        raise ValueError('Unknown pilot arm')
    messages = copy.deepcopy(task['messages'][:2])
    payload = json.loads(messages[1]['content'])
    if arm != 'source_chart_conditions':
        payload.pop('source_given_conditions', None)
        payload['references'] = {k: v for k, v in payload['references'].items()
                                 if not k.startswith('condition-')}
    if arm in ('base', 'source_chart'):
        payload['references'] = {k: v for k, v in payload['references'].items() if k == 'chart'}
    if arm == 'base':
        payload.pop('chart', None)
        payload.pop('provided_roles', None)
        payload['references'] = {}
    messages[1]['content'] = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return messages


def check_output(output, payload):
    if (not isinstance(output, dict) or output.get('task_type') != payload['task_type']
            or not isinstance(output.get('explanation'), str) or not output['explanation'].strip()
            or not isinstance(output.get('citations'), list)
            or not isinstance(output.get('uncertainties'), list)):
        raise GenerationError('Invalid method output schema')
    errors = []
    if not output['citations'] or any(not isinstance(c, str) or c not in payload['references']
                                       for c in output['citations']):
        errors.append('unavailable_reference')
    observations = output.get('observations', [])
    if not isinstance(observations, list):
        raise GenerationError('Invalid observation list')
    palaces = payload.get('chart', {}).get('palaces', {})
    for fact in observations:
        if not isinstance(fact, dict):
            raise GenerationError('Invalid fact schema')
        palace, field = str(fact.get('palace')), fact.get('field')
        if (not isinstance(field, str) or palace not in palaces or field not in palaces[palace]
                or fact.get('value') is None or fact.get('value') != palaces[palace][field]):
            errors.append('source_table_fact_mismatch')
    return errors


def method_ask(service, inquiry, request):
    task = load_task(request, service.knowledge.db)
    if inquiry.text != task['task_id'] or inquiry.context or inquiry.domain is not None:
        raise ValueError('Pilot inquiry must identify only the frozen task')
    messages = messages_for(task, request.arm)
    payload = json.loads(messages[1]['content'])
    result = {'status': 'model_unavailable', 'scope': 'source_reviewed_method_pilot',
              'professional_analysis_completed': False,
              'formal_conditional_rule_arm': 'blocked_not_equivalent_to_source_given_conditions',
              'payload_sha256': sha(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()),
              'author_method_accuracy': None, 'reported_feedback_accuracy': None,
              'independent_real_world_accuracy': None}
    try:
        output, telemetry = service.model.generate_method(messages)
        result['telemetry'] = telemetry
        errors = check_output(output, payload)
        result.update(status='method_generated' if not errors else 'method_evidence_error',
                      output=output, telemetry=telemetry, evidence_errors=errors)
    except (ModelUnavailable, AttributeError):
        pass
    except GenerationError:
        result['status'] = 'generation_error'
    return result


def score_task(task, result):
    """Independent literal/role targets; narrative quality requires source review."""
    expected = json.loads(task['messages'][2]['content'])
    actual = result.get('output', {})
    facts = expected.get('observations', [])
    proposed = actual.get('observations', [])
    if not isinstance(proposed, list):
        proposed = []
    matched = sum(any(isinstance(p, dict) and all(type(p.get(k)) is type(f.get(k))
                      and p.get(k) == f.get(k) for k in ('palace', 'field', 'value')) for p in proposed) for f in facts)
    bindings = expected.get('bindings')
    return {'task_id': task['task_id'], 'task_type': task['task_type'],
            'literal_facts_available': len(facts), 'literal_facts_matched': matched,
            'literal_facts_claimed': len(proposed),
            'binding_target_available': bindings is not None,
            'binding_exact_match': bindings is not None and actual.get('bindings') == bindings,
            'protocol_and_citations_pass': result['status'] == 'method_generated',
            'author_method_semantic_score': None, 'reported_feedback_score': None,
            'independent_real_world_score': None,
            'human_review_required': ['方法条件与角色是否正确', '证据支持、反证与不确定性',
                                     '应期方法和续断是否符合本轮来源', '作者断语与书中结局分开核对']}
