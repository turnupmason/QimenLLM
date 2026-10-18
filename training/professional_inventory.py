"""Prepare complete source review queues; never export unreviewed SFT messages.

This is a corpus audit, not a training release or an automatic label generator.
Record kinds locate possible evidence; they cannot establish professional task
semantics, rule applicability, or what was knowable at a historical cutoff.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3


TASK_EVIDENCE = {
    'role_selection': {'role_selection'},
    'chart_evidence': {'author_reasoning'},
    'evidence_synthesis': {'author_reasoning', 'prediction'},
    'timing_analysis': {'timing'},
    'feedback_continuation': {'continuation'},
}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(db, frozen_families):
    """Read-only source/record/chart audit, with all event-family owners retained."""
    con = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        documents = {}
        for row in con.execute('SELECT document_id,sha256,content FROM raw_documents'):
            if sha(row['content']) != row['sha256']:
                raise ValueError('Original document bytes differ from hash')
            documents[row['document_id']] = dict(row)
        references = {}
        for row in con.execute('''SELECT s.*,r.document_id FROM source_spans s
                               JOIN chapter_revisions r USING(revision_id)'''):
            doc = documents[row['document_id']]
            if not 0 <= row['byte_start'] < row['byte_end'] <= len(doc['content']):
                raise ValueError('Source span out of bounds')
            raw = doc['content'][row['byte_start']:row['byte_end']]
            references[row['source_id']] = {
                'source_id': row['source_id'], 'revision_id': row['revision_id'],
                'byte_start': row['byte_start'], 'byte_end': row['byte_end'],
                'document_sha256': doc['sha256'], 'excerpt_sha256': sha(raw),
                'text': raw.decode('utf-8'), 'locator': row['locator'],
            }
        events, queue_counts, phase_counts = [], Counter(), Counter()
        for row in con.execute('SELECT * FROM events ORDER BY family_id,event_id'):
            event = dict(row)
            if event['family_id'] not in frozen_families:
                raise ValueError('Event family absent from frozen assignment')
            records = []
            for record in con.execute('SELECT * FROM case_records WHERE event_id=? ORDER BY sequence',
                                      (event['event_id'],)):
                record = dict(record)
                ref = references[record['source_id']]
                if record['text'] != ref['text']:
                    raise ValueError('Record differs from original source span: ' + record['record_id'])
                phase_counts[(record['kind'], record['knowledge_phase'])] += 1
                # Retain original payload and phase without promoting unknown.
                record['source'] = ref
                records.append(record)
            charts = []
            for chart in con.execute('SELECT * FROM charts WHERE event_id=? ORDER BY chart_id',
                                     (event['event_id'],)):
                chart = dict(chart)
                if sha(chart['chart_json'].encode()) != chart['content_sha256']:
                    raise ValueError('Chart payload differs from hash')
                chart['source'] = references[chart['source_id']]
                charts.append(chart)
            cases = [dict(c) for c in con.execute('''SELECT c.* FROM cases c JOIN case_events ce
                       USING(case_id) WHERE ce.event_id=? ORDER BY c.case_id''', (event['event_id'],))]
            queues = {task: [r['record_id'] for r in records
                             if r['kind'] in kinds and r['explicitness'] == 'author_explicit']
                      for task, kinds in TASK_EVIDENCE.items()}
            for task, ids in queues.items():
                queue_counts[task] += len(ids)
            events.append({
                'event_id': event['event_id'], 'family_id': event['family_id'],
                'split': frozen_families[event['family_id']], 'cases': cases,
                'chronology_status': event['chronology_status'],
                'records': records, 'charts': charts, 'evidence_review_queues': queues,
                'sft_eligible': False, 'model_input': None,
                'review_requirements': [
                    'semantic task selection and cited rule applicability',
                    'task-specific known-information cutoff; no future feedback',
                    'chart fact verification and explicit author-evidence target',
                    'continuation retains prior chart unless source explicitly recasts',
                    'preserve family owner across all tasks and repeated sources',
                ],
            })
        counts = {table: con.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                  for table in ('cases', 'event_families', 'events', 'charts',
                                'knowledge_items', 'rules', 'training_tasks', 'dataset_releases')}
        version = con.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
        return events, {
            'scope': 'complete_book_professional_task_source_review_not_sft_release',
            'data_version': version, 'counts': counts,
            'source_documents_verified': len(documents), 'source_spans_verified': len(references),
            'records_verified': sum(len(e['records']) for e in events),
            'evidence_queue_counts': dict(queue_counts),
            'queue_counts_are_training_tasks': False, 'sft_eligible_tasks': 0,
            'phases_by_kind': [{'kind': kind, 'phase': phase, 'records': count}
                               for (kind, phase), count in sorted(phase_counts.items())],
            'family_assignments': frozen_families,
            'ready_for_training': False, 'database_modified': False,
        }
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--family-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Keep prior inventories; choose a new output')
    frozen = json.loads(args.family_manifest.read_bytes())
    if frozen.get('frozen') is not True:
        raise ValueError('Frozen family assignments required')
    events, report = inventory(args.db, frozen['family_assignments'])
    report['family_manifest_sha256'] = sha(args.family_manifest.read_bytes())
    raw = b''.join(encoded(e) for e in events)
    report['events_file'] = {'name': 'source-review-events.jsonl', 'bytes': len(raw),
                             'sha256': sha(raw), 'events': len(events)}
    args.output.mkdir(parents=True)
    (args.output / 'source-review-events.jsonl').write_bytes(raw)
    (args.output / 'report.json').write_bytes(encoded(report))
    print(json.dumps({k: report[k] for k in ('counts', 'records_verified',
                     'evidence_queue_counts', 'ready_for_training')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
