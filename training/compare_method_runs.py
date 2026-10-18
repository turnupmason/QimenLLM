"""Same-input before/after comparison, with explicit source-based human review.

Protocol, target-field coverage and professional source fidelity are separate.
No test data are opened, and no historical/pilot score becomes real accuracy.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compare(before, after, review):
    if (before.get('test_accessed') is not False or after.get('test_accessed') is not False
            or before.get('adapter') is not None or not after.get('adapter')
            or not before.get('finished_unix') or not after.get('finished_unix')):
        raise ValueError('Complete unadapted/adapted development+validation runs required')
    for field in ('model', 'revision', 'model_manifest_sha256', 'data_manifest_sha256', 'source_data_version'):
        if before[field] != after[field]:
            raise ValueError('Comparison model/source identity differs: '+field)
    old = {r['task_id']: r for r in before['records']}
    new = {r['task_id']: r for r in after['records']}
    if len(old) != len(before['records']) or len(new) != len(after['records']) or old.keys() != new.keys():
        raise ValueError('Same distinct frozen tasks required')
    validation = {key for key, r in old.items() if r['split'] == 'validation'}
    if (review.get('split') != 'validation' or not review.get('reviewer') or not review.get('source_basis')
            or set(review.get('tasks', {})) != validation or len(validation) != 4):
        raise ValueError('All four validation tasks need source-based review')
    rows = []
    passed = 0
    for key, b in old.items():
        a = new[key]
        if b['split'] not in ('development', 'validation') or (b['split'], b['task_type']) != (a['split'], a['task_type']):
            raise ValueError('Task split/type differs')
        if b['result']['payload_sha256'] != a['result']['payload_sha256']:
            raise ValueError('Model inputs changed between runs')
        for field in ('max_tokens', 'max_context_tokens', 'temperature', 'seed', 'enable_thinking'):
            bt, at = b['result'].get('telemetry', {}), a['result'].get('telemetry', {})
            for row, telemetry in ((b, bt), (a, at)):
                if row['result']['status'] in ('method_generated', 'method_evidence_error') and field not in telemetry:
                    raise ValueError('Successful generation lacks its measured settings')
            if field in bt and field in at and bt[field] != at[field]:
                raise ValueError('Generation setting differs: '+field)
        human = review['tasks'].get(key)
        if key in validation:
            for field in ('source_fidelity_pass', 'task_completion_pass', 'no_unsupported_factual_claims'):
                if type(human.get(field)) is not bool:
                    raise ValueError('Explicit source/method judgments required')
            if not human.get('source_note'):
                raise ValueError('A protocol result cannot replace source review')
            accepted = all(human[f] for f in ('source_fidelity_pass', 'task_completion_pass',
                                             'no_unsupported_factual_claims'))
            if accepted and a['result']['status'] != 'method_generated':
                raise ValueError('Failed generation/evidence cannot be a complete pass')
            passed += accepted
        rows.append({'task_id': key, 'split': b['split'], 'task_type': b['task_type'],
            'before_status': b['result']['status'], 'after_status': a['result']['status'],
            'before_structured_score': b['score'], 'after_structured_score': a['score'],
            'source_review': human})
    return {'scope': 'same_input_source_conditioned_mac_method_pilot',
        'model': after['model'], 'revision': after['revision'],
        'data_manifest_sha256': after['data_manifest_sha256'],
        'source_data_version': after['source_data_version'], 'adapter': after['adapter'],
        'adapter_training': after.get('adapter_training'),
        'tasks_compared': len(rows), 'validation_tasks': len(validation),
        'before_completion_counts': dict(Counter(r['before_status'] for r in rows)),
        'after_completion_counts': dict(Counter(r['after_status'] for r in rows)),
        'validation_source_fidelity_and_task_passes': passed,
        'mac_limited_method_review_pass': passed == len(validation),
        'full_system_D_E_validated': False, 'systematic_training_ready': False,
        'test_accessed': False, 'author_method_population_accuracy': None,
        'reported_feedback_accuracy': None, 'independent_real_world_accuracy': None,
        'reviewer': review['reviewer'], 'source_basis': review['source_basis'], 'rows': rows,
        'limits': ['Four correlated validation subtasks from one event family; no population estimate.',
                   'Source-given conditions are not an independently computed full-system rule baseline.',
                   'Exact fields and citations do not prove narrative correctness; source review is separate.',
                   'Even a local method pass still needs all-book curation and full-system gates before systematic training.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', type=Path, required=True)
    p.add_argument('--after', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    before, after, review = [json.loads(path.read_bytes()) for path in (a.before, a.after, a.review)]
    if review.get('after_report_sha256') != sha(a.after.read_bytes()):
        raise ValueError('Review must identify the exact adapted report')
    result = compare(before, after, review)
    result['files_sha256'] = {name: sha(path.read_bytes()) for name, path in
                             (('before', a.before), ('after', a.after), ('review', a.review))}
    with a.output.open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('tasks_compared', 'validation_source_fidelity_and_task_passes',
                                            'mac_limited_method_review_pass', 'systematic_training_ready')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
