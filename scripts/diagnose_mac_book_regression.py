#!/usr/bin/env python3
"""Offline regression triage for two immutable full-book generation receipts.

No inference, test.jsonl access, source text, prompts, model output text,
case IDs, or answer targets are written into the diagnostic report.
Diagnostics assess generation *protocol*, not professional prediction quality.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


STATUSES = frozenset({'method_generated', 'method_evidence_error', 'generation_error', 'model_unavailable'})
SPLITS = frozenset({'train', 'validation', 'development'})


def generation_failure_kind(result):
    if result.get('status') != 'generation_error':
        return None
    telemetry = result.get('telemetry') or {}
    if telemetry.get('finish_reason') == 'length':
        return 'length_truncation'
    raw = telemetry.get('raw_output')
    if not isinstance(raw, str) or not raw.strip():
        return 'empty_or_unrecorded'
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError):
        return 'invalid_json'
    if isinstance(obj, dict) and obj.get('_generation_error') == 'truncated':
        return 'length_truncation'
    if isinstance(obj, dict) and obj.get('_generation_error') == 'invalid_json':
        return 'invalid_json'
    return 'schema_rejected_or_other_generation_error'


def _load_receipt(path, *, baseline):
    r = json.loads(Path(path).read_bytes())
    if r.get('status') != 'generation_complete_not_semantic_acceptance':
        raise ValueError('Incomplete generation receipt')
    if r.get('test_accessed') is not False or r.get('all_chapter_model_pass') is not False:
        raise ValueError('Sealed test or professional pass boundary inconsistent')
    if (r.get('adapter') is None) != baseline:
        raise ValueError('Expected unadapted baseline / actual trained adapter')
    if not baseline:
        parity = r.get('adapter_reload_parity') or {}
        if parity.get('max_delta') != 0 or parity.get('scales_match') is not True:
            raise ValueError('Adapter model reload parity is not proven')
    records = r.get('records')
    if not isinstance(records, list) or not records:
        raise ValueError('No evaluation records')
    index = {}
    for x in records:
        tid = x.get('task_id')
        if not isinstance(tid, str) or not tid or tid in index:
            raise ValueError('Missing/duplicate task identity')
        if x.get('split') not in SPLITS:
            raise ValueError('Unknown or sealed test split in iterative evaluation')
        result = x.get('result') or {}
        if result.get('status') not in STATUSES:
            raise ValueError('Unknown generation status')
        if result.get('seen_training_diagnostic') is not (x['split'] == 'train'):
            raise ValueError('Train diagnostics mislabeled as held-out')
        index[tid] = x
    counts = dict(Counter(x['chapter'] for x in records))
    if counts != r.get('chapter_counts'):
        raise ValueError('Chapter counts do not match actual records')
    return r, index


def compare(before_report, after_report):
    before, b = _load_receipt(before_report, baseline=True)
    after, a = _load_receipt(after_report, baseline=False)
    for field in ('data_manifest_sha256', 'config_sha256', 'model_manifest_sha256',
                  'revision', 'generation_settings'):
        if before.get(field) is None or before[field] != after.get(field):
            raise ValueError('Mismatched identity/settings: ' + field)
    if set(b) != set(a):
        raise ValueError('Task set changed; cannot make paired comparison')
    if set(before['chapter_counts']) != set(after['chapter_counts']):
        raise ValueError('Chapter coverage differs')
    transitions = Counter()
    kinds = [Counter(), Counter()]
    evidence = [Counter(), Counter()]
    by_chapter = defaultdict(lambda: [Counter(), Counter()])
    by_split = defaultdict(lambda: [Counter(), Counter()])
    by_type = defaultdict(lambda: [Counter(), Counter()])
    matches = [Counter(), Counter()]
    for tid, old in b.items():
        new = a[tid]
        for key in ('chapter', 'split', 'task_type', 'context_mode'):
            if old.get(key) != new.get(key):
                raise ValueError('Task metadata changed: ' + key)
        os, ns = old['result']['status'], new['result']['status']
        transitions[(os, ns)] += 1
        for i, row in enumerate((old, new)):
            status = row['result']['status']
            by_chapter[row['chapter']][i][status] += 1
            by_split[row['split']][i][status] += 1
            by_type[row['task_type']][i][status] += 1
            kind = generation_failure_kind(row['result'])
            if kind:
                kinds[i][kind] += 1
            for error in row['result'].get('evidence_errors', []):
                if isinstance(error, str):
                    evidence[i][error] += 1
            score = row.get('score') or {}
            # Mechanical target comparisons only. Not source-method correctness.
            matches[i]['literal_facts_available'] += int(score.get('literal_facts_available') or 0)
            matches[i]['literal_facts_matched'] += int(score.get('literal_facts_matched') or 0)
            matches[i]['binding_target_available'] += int(score.get('binding_target_available') is True)
            matches[i]['binding_exact_match'] += int(score.get('binding_exact_match') is True)
    def statuses(counter):
        return {s: counter[s] for s in sorted(STATUSES) if counter[s]}
    def group(d):
        return {key: {
            'before': statuses(pairs[0]),
            'after': statuses(pairs[1]),
            'protocol_success_delta': pairs[1]['method_generated'] - pairs[0]['method_generated'],
            'interpretation': 'train_is_seen_diagnostic' if key == 'train' else 'not_professional_semantic_pass',
        } for key, pairs in sorted(d.items())}
    successes_before = sum(old['result']['status'] == 'method_generated' for old in b.values())
    successes_after = sum(new['result']['status'] == 'method_generated' for new in a.values())
    out = {
        'scope': 'paired_full_book_generation_regression_diagnostic',
        'status': 'diagnosed_not_professionally_accepted',
        'source_prompts_or_raw_model_responses_included': False,
        'sealed_test_opened': False,
        'independent_test_accuracy': None,
        'all_chapters_professionally_accepted': False,
        'same_task_count': len(b),
        'chapter_count': len(before['chapter_counts']),
        'comparison_same_revision_data_config_generation_settings': True,
        'adapter_reload_parity_confirmed': True,
        'protocol_generated': {'before': successes_before, 'after': successes_after,
                               'delta': successes_after - successes_before},
        'counts_before': statuses(Counter(x['result']['status'] for x in b.values())),
        'counts_after': statuses(Counter(x['result']['status'] for x in a.values())),
        'transitions': [
            {'before': old, 'after': new, 'count': n}
            for (old, new), n in sorted(transitions.items())
        ],
        'generation_error_causes_before': dict(sorted(kinds[0].items())),
        'generation_error_causes_after': dict(sorted(kinds[1].items())),
        'evidence_error_types_before': dict(sorted(evidence[0].items())),
        'evidence_error_types_after': dict(sorted(evidence[1].items())),
        'mechanical_task_target_comparison_before': dict(matches[0]),
        'mechanical_task_target_comparison_after': dict(matches[1]),
        'by_split': group(by_split),
        'by_task_type': group(by_type),
        'by_chapter': group(by_chapter),
        'next_gate': 'Review failure modes, source-specific answer quality, and a new preregistered candidate; do not extend epoch-05 blindly or open sealed test.',
    }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.before, args.after)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({
        'output': str(args.output), 'task_count': result['same_task_count'],
        'chapters': result['chapter_count'],
        'protocol_generated': result['protocol_generated'],
        'failure_causes_before': result['generation_error_causes_before'],
        'failure_causes_after': result['generation_error_causes_after'],
        'sealed_test_opened': False,
        'professionally_accepted': False,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
