"""Local development experiments. Never promote a research answer to professional success.

Only explicitly reviewed source slices are released. Full chapters, case titles,
author targets, feedback after the cutoff and unrestricted background are withheld.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path

from ..contracts import GenerationError, ModelUnavailable
from ..knowledge.db import connect, digest
from ..knowledge.importer import canonical


ARMS = ('base', 'symbolic_chart', 'chart_knowledge', 'candidate_conditions')


@dataclass(frozen=True)
class ResearchRequest:
    suite_path: str
    suite_sha256: str
    task_id: str
    arm: str


def load_suite(request: ResearchRequest, db) -> tuple[dict, dict]:
    raw = Path(request.suite_path).read_bytes()
    if digest(raw) != request.suite_sha256:
        raise ValueError('Frozen development suite hash mismatch')
    suite = json.loads(raw)
    if request.arm not in ARMS or suite['scope'] not in ('development_only_not_blind_test','frozen_initial_turn_test'):
        raise ValueError('Unsupported research scope or arm')
    tasks = [t for t in suite['tasks'] if t['task_id'] == request.task_id]
    if len(tasks) != 1:
        raise ValueError('Unknown or repeated task')
    task = tasks[0]
    with connect(db) as conn:
        version = conn.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
        if version != suite['data_version']:
            raise ValueError('Database version differs from frozen suite')
        event = conn.execute('SELECT family_id FROM events WHERE event_id=?', (task['event_id'],)).fetchone()
        if event is None or event['family_id'] != task['family_id']:
            raise ValueError('Event family mismatch')
        expected_split='test' if suite['scope']=='frozen_initial_turn_test' else 'development'
        if suite['family_assignments'].get(task['family_id']) != expected_split:
            raise ValueError('Family outside authorized research split')
        if expected_split=='test':
            frozen_path=Path(__file__).resolve().parents[3]/suite['frozen_release_path']
            frozen_raw=frozen_path.read_bytes()
            if digest(frozen_raw)!=suite['frozen_release_sha256']:
                raise ValueError('Frozen release changed')
            release=json.loads(frozen_raw)
            if not release['frozen'] or release['family_assignments'].get(task['family_id'])!='test':
                raise ValueError('Family was not frozen as test')
            if request.arm!='symbolic_chart':
                raise ValueError('Held-out task released for fixed symbolic_chart condition only')
        if not conn.execute('SELECT 1 FROM case_events WHERE case_id=? AND event_id=?',
                            (task['case_id'], task['event_id'])).fetchone():
            raise ValueError('Case event mismatch')
    return suite, task


def _record(db, record_id, event_id):
    with connect(db) as conn:
        row = conn.execute('SELECT * FROM case_records WHERE record_id=? AND event_id=?',
                           (record_id, event_id)).fetchone()
    if row is None:
        raise ValueError('Record outside task event')
    return dict(row)


def _source(service, selector):
    source = service.knowledge.source(selector['source_id'])
    if digest(source['excerpt'].encode()) != selector['excerpt_sha256']:
        raise ValueError('Reviewed source slice changed')
    return {'id': selector['source_id'], 'text': source['excerpt'],
            'document_sha256': source['sha256'], 'byte_start': source['byte_start'],
            'byte_end': source['byte_end']}


def _safe_knowledge(service, selector):
    """Only a reviewed theory slice wholly outside EVERY historical case span."""
    source = service.knowledge.source(selector['source_id'])
    with connect(service.knowledge.db) as conn:
        overlap = conn.execute('''SELECT 1 FROM cases c JOIN source_spans s USING(source_id)
            WHERE s.revision_id=? AND s.byte_start<? AND s.byte_end>? LIMIT 1''',
            (source['revision_id'], source['byte_end'], source['byte_start'])).fetchone()
    if overlap:
        raise ValueError('Case narrative is forbidden in evaluation retrieval')
    return _source(service, selector)


def prepare(service, request: ResearchRequest, inquiry) -> tuple[dict, dict]:
    suite, task = load_suite(request, service.knowledge.db)
    if inquiry.text != task['question'] or inquiry.context or inquiry.domain is not None:
        raise ValueError('Research inquiry must equal frozen question without hidden context')
    expected_review=('source_chronology_reviewed_for_frozen_test' if suite['scope']=='frozen_initial_turn_test'
                     else 'source_chronology_reviewed_for_development')
    if task['review']['status'] != expected_review:
        raise ValueError('Unreviewed task')
    records = []
    for selected in task['input_records']:
        record = _record(service.knowledge.db, selected['record_id'], task['event_id'])
        if record['sequence'] >= task['cutoff_sequence']:
            raise ValueError('Input is at or after forecast cutoff')
        # Later-turn feedback requires explicit, per-record review; it is NEVER
        # permission to export the first-forecast view or future feedback.
        if (record['kind'] not in ('dialogue', 'feedback', 'author_reasoning')
                or record['knowledge_phase'] != selected['reviewed_phase']):
            raise ValueError('Unexpected input kind or chronology')
        if record['kind'] == 'author_reasoning' and selected.get('reviewed_content_type') != 'source_given_time_metadata_only':
            raise ValueError('Author interpretation cannot enter input as metadata')
        if not selected['review_note']:
            raise ValueError('Explicit input chronology review required')
        source = _source(service, selected)
        if source['text'] != record['text']:
            raise ValueError('Record is not its exact source slice')
        records.append(source)
    # Gold is validated in the scorer, never serialized into this payload.
    payload = {'protocol': 'qimen-research-v1', 'question': task['question'],
               'answer_fields': task['answer_fields'], 'known_information': records,
               'given_symbolic_inputs': task['symbolic_inputs'],
               'declared_condition_context': task['condition_context'],
               'chart': None, 'knowledge': [], 'candidate_conditions': [],
               'scope': 'research_only_no_professional_completion'}
    diagnostics = {'arm': request.arm, 'evaluation_scope': suite['scope'], 'casting_status': 'not_requested',
                   'knowledge_count': 0, 'formal_rule_count': 0,
                   'full_condition_rule_arm': 'blocked_no_compiled_professional_rules'}
    if request.arm != 'base':
        from ..contracts import Inquiry
        from ..casting.paper import PAPER_METHOD
        # Supplied symbolic inputs are reviewed source facts, never calendar inference.
        casting = service.casting.cast(Inquiry(task['question'], casting_method=PAPER_METHOD,
                                              context=task['symbolic_inputs']))
        diagnostics['casting_status'] = casting.status
        chart_sources = [_source(service, item) for item in task['chart_sources']]
        payload['chart'] = {'sources': chart_sources,
                            'given_symbolic_inputs': task['symbolic_inputs'],
                            'calculation_status': casting.status,
                            'calculated': casting.chart.facts() if casting.chart else None,
                            'calendar_recomputed': False, 'engine_verified': False}
    if request.arm in ('chart_knowledge', 'candidate_conditions'):
        payload['knowledge'] = [_safe_knowledge(service, item) for item in task['knowledge_sources']]
        diagnostics['knowledge_count'] = len(payload['knowledge'])
    if request.arm == 'candidate_conditions':
        allowed = {s['id'] for s in payload['knowledge']}
        # Inputs are manually reviewed as knowable at this turn. Missing keys
        # stay unknown; the inspector cannot create a formal binding.
        inspected = service.rule_candidates(task['condition_context'], domain=task['domain'])
        payload['candidate_conditions'] = [
            {key: entry[key] for key in ('candidate_key', 'symbolic_status', 'missing',
                                         'condition_checks', 'activation_status', 'role_bindings')}
            for entry in inspected['candidates'] if entry['source']['source_id'] in allowed]
        diagnostics['candidate_count'] = len(payload['candidate_conditions'])
    return payload, diagnostics


def validate_output(output, payload):
    try:
        canonical(output)
    except (ValueError, TypeError) as exc:
        raise GenerationError('Nonfinite or invalid JSON output') from exc
    if not isinstance(output, dict) or set(output) != {'answers', 'evidence', 'fact_claims'}:
        raise GenerationError('Output keys do not match protocol')
    answers = output['answers']
    if not isinstance(answers, dict) or set(answers) != set(payload['answer_fields']):
        raise GenerationError('Answer fields differ from task')
    for key, value in answers.items():
        if value is not None and not any(type(value) is type(v) and value == v
                                         for v in payload['answer_fields'][key]['values']):
            raise GenerationError('Answer value outside declared schema')
    if not isinstance(output['evidence'], list) or not isinstance(output['fact_claims'], list):
        raise GenerationError('Evidence and fact claims must be arrays')
    if len(output['evidence']) > 2 or len(output['fact_claims']) > 1:
        raise GenerationError('Evidence/claim count exceeds declared protocol')
    sources = {s['id']: s['text'] for s in payload['known_information'] + payload['knowledge']}
    if payload['chart']:
        sources.update({s['id']: s['text'] for s in payload['chart']['sources']})
    errors = []
    for evidence in output['evidence']:
        if not isinstance(evidence, dict) or set(evidence) != {'source_id', 'quote'}:
            raise GenerationError('Invalid citation schema')
        if isinstance(evidence['quote'], str) and len(evidence['quote']) > 80:
            raise GenerationError('Citation exceeds declared protocol budget')
        if (not isinstance(evidence['source_id'], str) or evidence['source_id'] not in sources or not isinstance(evidence['quote'], str)
                or not evidence['quote'].strip() or evidence['quote'] not in sources[evidence['source_id']]):
            errors.append('citation_not_in_released_source')
    facts = payload['chart']['calculated'] if payload['chart'] else None
    for claim in output['fact_claims']:
        if not isinstance(claim, dict) or set(claim) != {'key', 'value'} or not isinstance(claim['key'], str):
            raise GenerationError('Invalid chart fact schema')
        if facts is None or claim['key'] not in facts or canonical(claim['value']) != canonical(facts[claim['key']]):
            errors.append('chart_fact_mismatch')
    return errors


def research_ask(service, inquiry, request):
    payload, diagnostics = prepare(service, request, inquiry)
    result = {'status': 'model_unavailable', 'scope': ('frozen_family_held_out_research'
              if diagnostics['evaluation_scope']=='frozen_initial_turn_test' else 'development_research_only'),
              'professional_analysis_completed': False, 'diagnostics': diagnostics,
              'payload_sha256': digest(canonical(payload).encode())}
    try:
        output, telemetry = service.model.generate_research(payload)
        result['telemetry'] = telemetry
        errors = validate_output(output, payload)
        result.update(status='research_generated' if not errors else 'research_evidence_error',
                      output=output, telemetry=telemetry, evidence_errors=errors)
    except (ModelUnavailable, AttributeError):
        result['status'] = 'model_unavailable'
    except GenerationError:
        result['status'] = 'generation_error'
    return result


def score(db, task, result):
    """Source fidelity and historical feedback agreement are separate denominators."""
    answers = result.get('output', {}).get('answers', {})
    scores = {}
    for axis in ('author', 'reported_outcome'):
        checked = []
        for key, target in task['gold'][axis].items():
            record = _record(db, target['record_id'], task['event_id'])
            if target['quote'] not in record['text']:
                raise ValueError('Gold quote is absent from source record')
            checked.append({'field': key, 'expected': target['value'],
                            'answered': key in answers and answers[key] is not None,
                            'abstained': key in answers and answers[key] is None,
                            'match': key in answers and type(answers[key]) is type(target['value'])
                                     and answers[key] == target['value'],
                            'record_id': target['record_id']})
        scores[axis] = {'available': len(checked), 'matches': sum(x['match'] for x in checked),
                        'details': checked}
    scores['real_world_predictive_accuracy'] = None
    scores['professional_correctness'] = None
    scores['limitations'] = [('family_held_out_historical_test_not_prospective'
        if task['review']['status']=='source_chronology_reviewed_for_frozen_test' else 'development_cases_not_blind'), 'selected_published_cases',
                            'pretraining_contamination_unknown',
                            'reported_feedback_not_prospective_validation',
                            'citation_substring_match_does_not_verify_inference']
    return scores


def summarize_runs(rows):
    return {'requests': len(rows), 'statuses': dict(Counter(r['result']['status'] for r in rows)),
            'by_arm': {arm: {
                'requests': sum(r['arm'] == arm for r in rows),
                'statuses': dict(Counter(r['result']['status'] for r in rows if r['arm'] == arm)),
                'author_fields_available': sum(r['score']['author']['available'] for r in rows if r['arm'] == arm),
                'author_fields_matched': sum(r['score']['author']['matches'] for r in rows if r['arm'] == arm),
                'author_fields_matched_protocol_accepted': sum(r['score']['author']['matches'] for r in rows
                    if r['arm']==arm and r['result']['status']=='research_generated'),
                'reported_outcome_fields_available': sum(r['score']['reported_outcome']['available'] for r in rows if r['arm'] == arm),
                'reported_outcome_fields_matched': sum(r['score']['reported_outcome']['matches'] for r in rows if r['arm'] == arm),
                'reported_outcome_fields_matched_protocol_accepted': sum(r['score']['reported_outcome']['matches'] for r in rows
                    if r['arm']==arm and r['result']['status']=='research_generated')
            } for arm in ARMS},
            'professional_correctness': None, 'real_world_predictive_accuracy': None,
            'full_condition_rule_baseline': 'blocked', 'finetuned_baseline': 'not_run'}
