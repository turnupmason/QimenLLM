"""Freeze ALL complete case archives and safe chart-reading tasks, without editing DB.

Case archives contain outcomes and are NEVER model inputs. Additional SFT tasks
are literal table reading only: no role/forecast labels inferred from record kinds.
The separately reviewed lost-property method tasks are included byte-for-byte.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from method_release import build as method_build, encoded, sha, source, SYSTEM
from professional_inventory import inventory
from qimenllm.cases.source_chart import project_chart


SPLITS = ('train', 'validation', 'test', 'development')


def build(db, review, families):
    events, audit = inventory(db, families['family_assignments'])
    methods, _ = method_build(db, review, families)
    tasks = list(methods)
    method_charts = {t['chart_id'] for t in methods if t['task_type'] == 'chart_evidence'}
    con = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    archives, unsupported, seen = [], [], set()
    try:
        for row in con.execute('SELECT * FROM cases ORDER BY case_id'):
            case = dict(row)
            own_events = [e for e in events if any(c['case_id'] == case['case_id'] for c in e['cases'])]
            owners = {e['split'] for e in own_events}
            if len(owners) != 1:
                raise ValueError('Missing event or cross-split story')
            split = owners.pop()
            archive = {'case': case, 'original_story': source(con, case['source_id']),
                       'split': split, 'events': own_events,
                       'contains_future_feedback': True, 'allowed_as_model_input': False,
                       'use': 'complete_source_archive_and_scoring_only'}
            archives.append(archive)
            for event in own_events:
                for chart in event['charts']:
                    chart_id = chart['chart_id']
                    if chart_id in seen or chart_id in method_charts:
                        continue
                    seen.add(chart_id)
                    p = project_chart(db, case['case_id'], chart_id)
                    if p['status'] != 'projected' or not p.get('raw_table_complete'):
                        unsupported.append({'case_id': case['case_id'], 'event_id': event['event_id'],
                                            'chart_id': chart_id, 'reason': p.get('reason', p['status']),
                                            'source_preserved': True, 'sft_eligible': False})
                        continue
                    # No narrative/title/date/author interpretation is supplied. A table
                    # reading exercise has no claim to be an historical first forecast.
                    palaces = {n: {k: v for k, v in palace.items() if k != 'source'}
                               for n, palace in p['palaces'].items()}
                    facts = [{'palace': int(n), 'field': field, 'value': value, 'citation': 'chart',
                              'verification': 'source_table_literal_not_recalculation'}
                             for n, palace in palaces.items() for field, value in palace.items()
                             if field != 'palace' and value is not None]
                    payload = {'task_type': 'chart_evidence', 'instruction':
                        '逐宫读取原表中明确给出的门、星、神、天干和原字标记。保留未知字，不作预测、用神绑定、历法或格局推算。',
                        'chart': {'chart_id': chart_id, 'raw_text': chart['source']['text'],
                                  'engine_verified': False, 'calendar_recomputed': False},
                        'references': {'chart': {'source_id': chart['source_id'],
                                                'scope': 'original_source_table_not_computed'}},
                        'scope': 'literal_source_table_reading_only'}
                    answer = {'task_type': 'chart_evidence', 'observations': facts, 'citations': ['chart'],
                              'explanation': '按原表逐宫读取；字面转写不等于独立排盘或断案。',
                              'uncertainties': ['空亡、马星、历法和格局未在本题独立复算。']}
                    task = {'task_id': 'book-table-' + chart_id, 'task_type': 'chart_evidence',
                            'case_id': case['case_id'], 'event_id': event['event_id'],
                            'family_id': event['family_id'], 'chart_id': chart_id, 'split': split,
                            'source_data_version': audit['data_version'],
                            'input_setting': 'literal_table_exercise_not_forecasting',
                            'validation_status': 'deterministic_literal_projection',
                            'input_sources': [chart['source']], 'supervision_sources': [chart['source']],
                            'target_kind': 'literal_source_table_fields',
                            'independent_real_world_accuracy': None,
                            'messages': [{'role': 'system', 'content': SYSTEM},
                                         {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, sort_keys=True)},
                                         {'role': 'assistant', 'content': json.dumps(answer, ensure_ascii=False, sort_keys=True)}]}
                    task['sha256'] = sha(encoded(task))
                    tasks.append(task)
    finally:
        con.close()
    if len(archives) != audit['counts']['cases'] or len({t['task_id'] for t in tasks}) != len(tasks):
        raise ValueError('Incomplete corpus or duplicate task')
    return archives, tasks, {
        'release_id': 'shenqi-book-preparation-v1', 'frozen': True,
        'source_data_version': audit['data_version'], 'family_assignments': families['family_assignments'],
        'family_counts': dict(Counter(families['family_assignments'].values())),
        'case_counts': dict(Counter(c['split'] for c in archives)),
        'task_counts': dict(Counter(t['split'] for t in tasks)),
        'task_types': dict(Counter(t['task_type'] for t in tasks)),
        'all_cases_archived': len(archives), 'events': len(events),
        'method_reviewed_cases': len({t['case_id'] for t in methods}),
        'method_tasks': len(methods), 'additional_literal_tasks': len(tasks) - len(methods),
        'task_cases': len({t['case_id'] for t in tasks}), 'unsupported_charts': unsupported,
        'archive_is_training_input': False, 'all_case_method_reasoning_review_complete': False,
        'source_audit': audit, 'database_modified': False,
        'professional_accuracy': None, 'independent_real_world_accuracy': None,
    }


def export(db, review_path, families_path, output, manifest):
    if output.exists() or manifest.exists():
        raise FileExistsError('Frozen outputs cannot be overwritten')
    archives, tasks, report = build(db, json.loads(review_path.read_bytes()), json.loads(families_path.read_bytes()))
    report['review_sha256'] = sha(review_path.read_bytes())
    report['family_manifest_sha256'] = sha(families_path.read_bytes())
    report['files'] = {}
    output.mkdir(parents=True)
    for split in SPLITS:
        for prefix, rows in (('cases', archives), ('tasks', tasks)):
            raw = b''.join(encoded(r) for r in rows if r['split'] == split)
            name = prefix + '-' + split + '.jsonl'
            (output / name).write_bytes(raw)
            report['files'][name] = {'sha256': sha(raw), 'bytes': len(raw),
                                    'rows': sum(r['split'] == split for r in rows)}
    manifest.write_bytes(encoded(report))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--review', type=Path, default=Path('data/structured/shenqi/lost_method_task_review_v5.json'))
    p.add_argument('--family-manifest', type=Path, default=Path('data/splits/author_initial_release_v2.json'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    a = p.parse_args()
    report = export(a.db, a.review, a.family_manifest, a.output, a.manifest)
    print(json.dumps({k: report[k] for k in ('all_cases_archived', 'case_counts', 'task_counts',
                                          'method_tasks', 'additional_literal_tasks', 'task_cases')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
