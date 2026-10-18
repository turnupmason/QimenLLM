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


def source_limit_tasks(con, supplements, assignments, version):
    """Two specifically reviewed teaching uses; neither upgrades original charts."""
    if (supplements['source_data_version'] != version
            or supplements['reviewed_by'] != 'Codex source-grounded semantic and literal review'
            or supplements['release_id'] != 'shenqi-book-preparation-v2'):
        raise ValueError('Pinned source-limit review required')
    result = []
    for item in supplements['rows']:
        event = con.execute('SELECT family_id FROM events WHERE event_id=?', (item['event_id'],)).fetchone()
        if (event is None or event['family_id'] != item['family_id']
                or not con.execute('SELECT 1 FROM case_events WHERE case_id=? AND event_id=?',
                                   (item['case_id'], item['event_id'])).fetchone()
                or not item['review_note']):
            raise ValueError('Source-limit task event/family mismatch')
        chart = con.execute('SELECT * FROM charts WHERE chart_id=? AND event_id=?',
                            (item['chart_id'], item['event_id'])).fetchone()
        if chart is None or chart['source_or_engine'] != 'original':
            raise ValueError('Existing original chart identity required')
        ref = source(con, item['source_id'])
        if ref['excerpt_sha256'] != item['excerpt_sha256']:
            raise ValueError('Reviewed source-limit bytes changed')
        answer = {'task_type': 'chart_evidence', 'citations': ['source'], 'engine_verified': False}
        if item['kind'] == 'partial_source_reading':
            data = json.loads(chart['chart_json'])
            if chart['source_id'] != ref['source_id'] or data.get('complete_nine_palace_chart') is not False:
                raise ValueError('Expected the reviewed partial original source')
            for fact in item['reported_facts']:
                if (not fact['value'] or fact['value'] not in fact['quote'] or fact['quote'] not in ref['text']
                        or any(word in fact['quote'] for word in ('凶', '利阴害阳', '反馈'))):
                    raise ValueError('Partial fact must be a literal, non-judgment source clause')
            answer.update(reported_facts=item['reported_facts'], complete_nine_palace_chart=False,
                explanation='此段只报出了若干局部盘面信息。带凶断的格局解释属于作者判断，不构成完整九宫或独立复算；只能摘录明确报出的字段。',
                uncertainties=['完整九宫的天地盘、门星神分布未提供。', '旬首、空亡、马星等缺项保持未知，不根据后文结果补盘。'])
            instruction = ('只做所引局部资料的完整性检查与字面摘录。输出reported_facts（key/value/quote）、'
                           'complete_nine_palace_chart、explanation、citations、uncertainties；保留未知项，不作发射结果预测。')
        elif item['kind'] == 'user_relayout_reading':
            project_root = Path(__file__).resolve().parents[1]
            gold_path = project_root/item['gold_path']
            if sha(gold_path.read_bytes()) != item['gold_sha256']:
                raise ValueError('Original independent relayout gold changed')
            gold = json.loads(gold_path.read_bytes())
            record = con.execute('SELECT payload_json FROM knowledge_items WHERE item_id=? AND source_id=?',
                                 (item['reference_item_id'], item['source_id'])).fetchone()
            if record is None:
                raise ValueError('Reviewed reference table absent')
            table = json.loads(record['payload_json'])
            if (table['existing_case_id'] != item['case_id'] or table['new_independent_chart'] is not False
                    or table['engine_verified'] is not False or gold['source_sha256'] != ref['document_sha256']
                    or len(table['dataset']['rows']) != 9):
                raise ValueError('Relayout must retain its reference-only identity')
            rows = {r['palace']: r for r in table['dataset']['rows']}
            cells = []
            for palace, expected in zip(gold['palace_order'], gold['cells']):
                row = rows[palace]
                quote = row['source_selector']['source_quote']
                col = row['source_grid_column']
                lines = quote.splitlines()
                if quote not in ref['text'] or len(lines) != 4 or col not in (1, 2, 3):
                    raise ValueError('Relayout source selector changed')
                actual = [line.split('│')[col].strip() for line in lines]
                if actual != expected or row['source_cells_as_written'] != expected:
                    raise ValueError('Relayout source cells differ from independent gold')
                cells.append({'palace': palace, 'source_cells_as_written': expected})
            answer.update(palaces_as_written=cells, representation='user_supplied_relayout_not_original_scan',
                explanation='逐宫保留所供重排表的原字单元；震三生乙、中宫壬、乾六壬惊丙均照录。该资料是同一历史盘的重排表示，两个旧事件原盘的技术状态保持。',
                uncertainties=['未独立核验纸本原图、历法或完整排盘算法。', '本题不是当年现场首次预测，也不从表格读取案情结果。'])
            instruction = ('逐宫读取这份明确标注的用户重排表。输出palaces_as_written（palace及四个source_cells_as_written）、'
                           'representation、explanation、citations、uncertainties；所有字面前缀和中宫字保留。')
        else:
            raise ValueError('Unreviewed source-limit task kind')
        payload = {'task_type': 'chart_evidence', 'instruction': instruction,
                   'references': {'source': {'source_id': ref['source_id'], 'text': ref['text']}},
                   'representation_scope': item['kind'], 'engine_verified': False,
                   'scope': 'source_reading_only_not_a_historical_first_forecast'}
        task = {'task_id': 'book-source-limits-'+item['chart_id'], 'task_type': 'chart_evidence',
                'case_id': item['case_id'], 'event_id': item['event_id'], 'family_id': item['family_id'],
                'chart_id': item['chart_id'], 'split': assignments[item['family_id']],
                'source_data_version': version, 'input_setting': item['kind'],
                'validation_status': 'explicit_source_scope_review_and_literal_check',
                'semantic_review_note': item['review_note'], 'input_sources': [ref], 'supervision_sources': [ref],
                'original_chart_status_upgraded': False, 'forecast_evaluation_eligible': False,
                'target_kind': 'source_literal_fields_and_explicit_information_limits',
                'independent_real_world_accuracy': None,
                'messages': [{'role': 'system', 'content': SYSTEM},
                             {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, sort_keys=True)},
                             {'role': 'assistant', 'content': json.dumps(answer, ensure_ascii=False, sort_keys=True)}]}
        task['sha256'] = sha(encoded(task))
        result.append(task)
    if len(result) != 2 or len({t['case_id'] for t in result}) != 2:
        raise ValueError('This review covers exactly two distinct source-limit stories')
    return result


def build(db, review, families, supplements=None):
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
        if supplements:
            tasks.extend(source_limit_tasks(con, supplements, families['family_assignments'], audit['data_version']))
    finally:
        con.close()
    if len(archives) != audit['counts']['cases'] or len({t['task_id'] for t in tasks}) != len(tasks):
        raise ValueError('Incomplete corpus or duplicate task')
    return archives, tasks, {
        'release_id': supplements['release_id'] if supplements else 'shenqi-book-preparation-v1', 'frozen': True,
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


def export(db, review_path, families_path, output, manifest, supplement_path=None):
    if output.exists() or manifest.exists():
        raise FileExistsError('Frozen outputs cannot be overwritten')
    archives, tasks, report = build(db, json.loads(review_path.read_bytes()), json.loads(families_path.read_bytes()),
                                   json.loads(supplement_path.read_bytes()) if supplement_path else None)
    report['review_sha256'] = sha(review_path.read_bytes())
    report['family_manifest_sha256'] = sha(families_path.read_bytes())
    if supplement_path:
        report['source_limit_review_sha256'] = sha(supplement_path.read_bytes())
        report['source_limit_reading_tasks'] = 2
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
    p.add_argument('--supplement-review', type=Path)
    a = p.parse_args()
    report = export(a.db, a.review, a.family_manifest, a.output, a.manifest, a.supplement_review)
    print(json.dumps({k: report[k] for k in ('all_cases_archived', 'case_counts', 'task_counts',
                                          'method_tasks', 'additional_literal_tasks', 'task_cases')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
