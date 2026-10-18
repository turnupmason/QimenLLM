#!/usr/bin/env python3
"""Report 26-source, 15-case-chapter evaluation coverage without opening sealed test data.

A train task evaluated by a model is an explicitly *seen* diagnostic. It never
stands in for held-out generalization. No status here asserts professional pass.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ('train', 'validation', 'development', 'test')
SOURCE_ONLY = {'reference_reading', 'source_reading'}


def matrix(manifest, records=None):
    if (manifest.get('release_id') != 'shenqi-book-method-curriculum-v1'
            or manifest.get('frozen') is not True):
        raise ValueError('Only the frozen book-method curriculum may be audited')
    chapters = manifest['chapter_coverage']
    if len(chapters) != manifest['source_inputs_with_tasks']:
        raise ValueError('Not every source chapter is in the coverage table')
    if {s: sum(c['task_counts'].get(s, 0) for c in chapters.values()) for s in SPLITS} != manifest['task_counts']:
        raise ValueError('Chapter counts disagree with frozen task totals')
    by_chapter = defaultdict(list)
    if records is not None:
        seen = set()
        for r in records:
            if r['chapter'] not in chapters or r['split'] not in ('train', 'validation', 'development'):
                raise ValueError('Test or unknown chapter/split entered iterative evaluation')
            if r['task_id'] in seen:
                raise ValueError('Duplicated evaluation task')
            seen.add(r['task_id'])
            if r['split'] == 'train' and r.get('result', {}).get('seen_training_diagnostic') is not True:
                raise ValueError('Training task not visibly labeled as seen diagnostic')
            by_chapter[r['chapter']].append(r)
        if set(by_chapter) != set(chapters):
            raise ValueError('Model generation has not evaluated all 26 chapter sources')
    items = []
    for code, source in sorted(chapters.items()):
        frozen = {s: source['task_counts'].get(s, 0) for s in SPLITS}
        modes = source['modes']
        is_case = any(mode not in SOURCE_ONLY for mode in modes)
        observations = by_chapter[code]
        per_split = Counter(r['split'] for r in observations)
        if any(per_split[s] > frozen[s] for s in ('train', 'validation', 'development')):
            raise ValueError('Evaluation claims more tasks than frozen')
        entries = {
            'chapter': code,
            'title': source['title'],
            'kind': 'case_method' if is_case else 'theory_reference_or_source_reading',
            'frozen_tasks': frozen,
            'unseen_validation_families': source['unseen_validation_families'],
            'forecast_validation_tasks': source['forecast_validation_tasks'],
            'independent_sealed_test_case_gate': ('not_a_case_chapter' if not is_case else
                'missing_sealed_test_tasks' if frozen['test'] == 0 else
                'pending_unique_eligible_family_audit'),
            'training_time_validation_case_gate': ('not_a_case_chapter' if not is_case else
                'missing_validation_family' if source['unseen_validation_families'] == 0 else
                'pending_independent_case_method_review'),
            'records_evaluated': len(observations),
            'seen_train_diagnostics': per_split['train'],
            'heldout_validation_records': per_split['validation'],
            'heldout_development_records': per_split['development'],
            'completion_counts': dict(Counter(r.get('result', {}).get('status', 'unknown') for r in observations)),
            'generation_coverage': (
                'not_run' if records is None else
                'generated_diagnostics_not_semantic_acceptance'),
            'unseen_case_evidence': (
                'not_a_case_prediction_chapter' if not is_case else
                'missing_unseen_validation_family' if source['unseen_validation_families'] == 0 else
                'not_generated_yet' if records is None else
                'generated_not_semantically_accepted'),
            'professional_chapter_pass': None,
            'real_world_accuracy': None,
        }
        items.append(entries)
    summary = {
        'scope': 'all_chapter_coverage_audit_not_model_pass',
        'source_chapters': len(items),
        'case_method_chapters': sum(c['kind'] == 'case_method' for c in items),
        'theory_or_source_chapters': sum(c['kind'] != 'case_method' for c in items),
        'source_chapters_with_validation_tasks': sum(c['frozen_tasks']['validation'] > 0 for c in items),
        'source_chapters_with_development_tasks': sum(c['frozen_tasks']['development'] > 0 for c in items),
        'case_chapters_missing_any_sealed_test_tasks': [
            {'chapter': c['chapter'], 'title': c['title']} for c in items
            if c['kind'] == 'case_method' and c['frozen_tasks']['test'] == 0
        ],
        'case_chapters_with_test_tasks_but_unique_eligible_case_unverified': [
            {'chapter': c['chapter'], 'title': c['title']} for c in items
            if c['kind'] == 'case_method' and c['frozen_tasks']['test'] > 0
        ],
        'minimum_eligible_independent_final_test_cases_per_case_chapter': 1,
        'every_case_chapter_independent_final_test_verified': False,
        'case_chapters_missing_unseen_validation_families': [
            {'chapter': c['chapter'], 'title': c['title']} for c in items
            if c['kind'] == 'case_method' and c['unseen_validation_families'] == 0
        ],
        'eval_records': 0 if records is None else len(records),
        'full_source_generation_coverage': None if records is None else True,
        'frozen_test_tasks_reserved': manifest['task_counts']['test'],
        'test_file_opened': False,
        'test_inference_performed': False,
        'all_chapter_professional_pass': False,
        'independent_real_world_accuracy': None,
    }
    return {'summary': summary, 'chapters': items}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=ROOT/'data/splits/book_method_curriculum_v1.json')
    p.add_argument('--report', type=Path, help='Completed model generation report, if present')
    p.add_argument('--output', type=Path, help='Write new JSON file, never overwrite')
    args = p.parse_args()
    meta = json.loads(args.manifest.read_bytes())
    records = None
    if args.report:
        report = json.loads(args.report.read_bytes())
        if report.get('test_accessed') is not False or report.get('status') != 'generation_complete_not_semantic_acceptance':
            raise ValueError('Untrusted, incomplete or unsealed generation report')
        records = report['records']
    result = matrix(meta, records)
    body = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as f:
            f.write(body)
    print(body, end='')


if __name__ == '__main__':
    main()
