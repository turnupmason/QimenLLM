"""Read-only full-book gate audit; no rule promotion or source corrections."""
import argparse
from collections import Counter
import json
from pathlib import Path

from qimenllm.casting.paper import PAPER_METHOD
from qimenllm.knowledge.db import connect, digest
from qimenllm.knowledge.integrity import audit
from qimenllm.reasoning.service import QimenService


def audit_readiness(db, raw_dir):
    service = QimenService(db)
    report = {'integrity': audit(db, raw_dir), 'charts': []}
    with connect(db) as conn:
        report['data_version'] = conn.execute(
            'SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
        report['counts'] = {table: conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                            for table in ('books', 'chapters', 'cases', 'event_families', 'events',
                                          'charts', 'rules', 'training_tasks', 'dataset_releases')}
        rows = conn.execute('''SELECT ce.case_id,ch.chart_id,ch.event_id FROM charts ch
            JOIN case_events ce USING(event_id) ORDER BY ch.chart_id''').fetchall()
    seen = set()
    for row in rows:
        if row['chart_id'] in seen:
            continue
        seen.add(row['chart_id'])
        projection = service.case_chart(row['case_id'], row['chart_id'], PAPER_METHOD)
        comparison = projection.get('comparison', {})
        report['charts'].append({**dict(row), 'projection_status': projection['status'],
                                  'comparison_status': comparison.get('status', 'not_run'),
                                  'comparison': comparison})
    candidates = service.rule_candidates({})
    report['candidate_conditions_with_no_context'] = {
        'count': candidates['candidate_count'], 'statuses': candidates['symbolic_status_counts'],
        'formal_bindings': candidates['role_bindings']}
    report['chart_projection_counts'] = dict(Counter(r['projection_status'] for r in report['charts']))
    report['chart_comparison_counts'] = dict(Counter(r['comparison_status'] for r in report['charts']))
    report['interpretation'] = {
        'matches': '只比较所给符号及受支持字段，不是公历复算或完整全盘认证',
        'mismatch': '指定比较方法下存在差异；不改来源，不推断原书错误',
        'conditional': '现有投影缺少可执行比较所需的结构化元数据；不代表原文缺失',
        'not_covered': '现有算法或投影未覆盖，不计正确或错误预测',
        'rules': '来源条件候选不等于正式可执行角色规则',
        'source_acceptance': 'user_attestation与软件独立外查、模型表现分开'}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--raw-dir', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError('Keep previous gate audit intact')
    result = audit_readiness(args.db, args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ('charts', 'integrity')}, ensure_ascii=False, indent=2))
    return 0 if result['integrity']['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
