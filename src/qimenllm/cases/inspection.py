"""Source-backed whole-case learning and conservative pre-forecast inspection.

The pre-forecast view is deliberately not a training exporter.  It returns only
explicit source records before the first forecast boundary; it never injects
unrestricted event background, later commentary, or the complete narrative.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..knowledge.db import connect, digest


def list_cases(db,chapter_key=None):
    """Historical learning catalog. Titles are not evaluation inputs."""
    if chapter_key is not None and (not isinstance(chapter_key,str) or not chapter_key):
        raise ValueError('Nonempty chapter key required')
    query='''SELECT ca.case_id,ca.title,ca.completeness,ch.chapter_key,ch.title AS chapter,
        b.title AS book,ca.source_id FROM cases ca JOIN source_spans s USING(source_id)
        JOIN chapter_revisions cr USING(revision_id) JOIN chapters ch USING(chapter_id)
        JOIN books b USING(book_id)'''
    params=[]
    if chapter_key is not None: query+=' WHERE ch.chapter_key=?'; params.append(chapter_key)
    query+=' ORDER BY ch.sequence,s.byte_start,ca.case_id'
    with connect(db) as conn:
        entries=[]
        for row in conn.execute(query,params):
            item=dict(row)
            item['events']=[{'event_id':e['event_id'],'family_id':e['family_id'],
                'chart_ids':[c[0] for c in conn.execute('SELECT chart_id FROM charts WHERE event_id=? ORDER BY chart_id',(e['event_id'],))]}
                for e in conn.execute('''SELECT e.* FROM case_events ce JOIN events e USING(event_id)
                    WHERE ce.case_id=? ORDER BY ce.sequence''',(row['case_id'],))]
            entries.append(item)
    return {'status':'sources_found' if entries else 'not_found','total':len(entries),'cases':entries,
            'purpose':'historical_learning_catalog_not_prediction_input','training_export':False,
            'professional_analysis_completed':False}


def _source(conn, source_id: str) -> dict:
    row = conn.execute('''SELECT s.*,d.content,d.sha256,c.chapter_key,c.title AS chapter_title,
            b.book_key,b.title AS book_title FROM source_spans s
        JOIN chapter_revisions r USING(revision_id)
        JOIN raw_documents d USING(document_id)
        JOIN chapters c USING(chapter_id) JOIN books b USING(book_id)
        WHERE s.source_id=?''', (source_id,)).fetchone()
    if row is None:
        raise ValueError('Missing case source')
    raw = row['content']
    if digest(raw) != row['sha256']:
        raise ValueError('Case source hash mismatch')
    start, end = row['byte_start'], row['byte_end']
    review = conn.execute('''SELECT status FROM source_reviews WHERE revision_id=?
        ORDER BY rowid DESC LIMIT 1''', (row['revision_id'],)).fetchone()
    return {'source_id': row['source_id'], 'revision_id': row['revision_id'],
            'source_sha256': row['sha256'], 'byte_start': start, 'byte_end': end,
            'locator': row['locator'], 'book_key': row['book_key'],
            'book_title': row['book_title'], 'chapter_key': row['chapter_key'],
            'chapter_title': row['chapter_title'],
            'source_acceptance': review[0] if review else 'pending',
            'text': raw[start:end].decode('utf-8')}


def _covered(source: dict, allowed: list[dict]) -> bool:
    """Only expose a citation wholly contained in the selected input excerpts."""
    intervals = sorted((r['byte_start'], r['byte_end']) for r in allowed
                       if r['revision_id'] == source['revision_id'])
    cursor = source['byte_start']
    for start, end in intervals:
        if end <= cursor:
            continue
        if start > cursor:
            return False
        cursor = end
        if cursor >= source['byte_end']:
            return True
    return False


def inspect_case(db: str | Path, case_id: str, view: str = 'full') -> dict:
    """Read one intact case, or only the auditable before-prediction excerpts.

    ``full`` is a historical learning view and may include the author's outcome.
    ``before_prediction`` withholds forecast steps, targets, feedback, unknown
    chronology, payload interpretations, unrestricted background and titles that
    could encode the outcome.  Chart facts are exposed only if their entire
    source span is already present in the selected pre-prediction excerpts.
    """
    if view not in ('full', 'before_prediction'):
        raise ValueError('Case view must be full or before_prediction')
    with connect(db) as conn:
        case = conn.execute('SELECT * FROM cases WHERE case_id=?', (case_id,)).fetchone()
        if case is None:
            raise KeyError(case_id)
        full = view == 'full'
        result = {'case_id': case['case_id'], 'view': view,
                  'data_version': case['data_version'], 'events': [],
                  'training_export': False, 'professional_prediction': False,
                  'outcome_independently_verified': False,
                  'trace': [{'stage': 'case_lookup', 'tables': ['cases', 'case_events',
                    'events', 'case_records', 'charts', 'source_spans', 'raw_documents',
                    'source_reviews', 'evidence_links']}],
                  'policy': 'whole_source_learning' if full else 'explicit_pre_prediction_source_only'}
        if full:
            result.update(title=case['title'], source_completeness=case['completeness'],
                          source=_source(conn, case['source_id']))
        event_rows = conn.execute('''SELECT e.*,ce.sequence AS case_sequence FROM case_events ce
            JOIN events e USING(event_id) WHERE ce.case_id=? ORDER BY ce.sequence''',
            (case_id,)).fetchall()
        for event in event_rows:
            all_records = conn.execute('''SELECT * FROM case_records WHERE event_id=?
                ORDER BY sequence''', (event['event_id'],)).fetchall()
            boundaries = [r['sequence'] for r in all_records
                          if r['knowledge_phase'] in ('prediction', 'post_feedback')]
            boundary = min(boundaries) if boundaries else None
            records = all_records if full else [r for r in all_records
                if r['knowledge_phase'] == 'pre_prediction'
                and r['explicitness'] == 'author_explicit'
                and (boundary is None or r['sequence'] < boundary)
                and r['kind'] not in ('prediction', 'feedback', 'outcome', 'continuation')]
            sources = [_source(conn, record['source_id']) for record in records]
            event_result = {'event_id': event['event_id'], 'family_id': event['family_id'],
                            'chronology_status': event['chronology_status'],
                            'chronology_interpretation': 'source_narrative_order',
                            'records': [], 'charts': [], 'evidence': []}
            if full:
                background = json.loads(event['background_json'])
                event_result['background'] = background
                source_ids = background.get('_case_import', {}).get('case_source_ids', [])
                event_result['narrative_sources'] = [_source(conn, source_id) for source_id in source_ids]
            elif event['chronology_status'] == 'unknown':
                # A row-level phase cannot establish sequence if the event itself
                # has not passed even a narrative-order review.
                records, sources = [], []
                event_result['blocked_reason'] = 'event_chronology_unknown'
            for record, source in zip(records, sources):
                if record['text'] != source['text']:
                    raise ValueError('Case record no longer matches its authoritative source')
                item = {key: record[key] for key in ('record_id', 'sequence', 'kind',
                    'knowledge_phase', 'speaker', 'text', 'explicitness', 'reported_at')}
                item['source'] = source
                if full:
                    item['chart_id'] = record['chart_id']
                    item['payload'] = json.loads(record['payload_json'])
                event_result['records'].append(item)
            for chart in conn.execute('SELECT * FROM charts WHERE event_id=? ORDER BY chart_id',
                                      (event['event_id'],)):
                chart_source = _source(conn, chart['source_id']) if chart['source_id'] else None
                if not full and (chart_source is None or not _covered(chart_source, sources)):
                    continue
                if digest(chart['chart_json'].encode()) != chart['content_sha256']:
                    raise ValueError('Case chart hash mismatch')
                if full:
                    entry = dict(chart)
                    entry['chart'] = json.loads(entry.pop('chart_json'))
                    entry['source'] = chart_source
                else:
                    # Before-prediction inspection grants access to original
                    # excerpts, not unchecked structured chart interpretations.
                    entry = {key: chart[key] for key in ('chart_id', 'source_or_engine',
                                                        'validation_status')}
                    entry.update(source=chart_source, structured_payload_withheld=True)
                event_result['charts'].append(entry)
            for record in records:
                links = conn.execute('SELECT * FROM evidence_links WHERE record_id=? ORDER BY source_id,relation',
                                     (record['record_id'],)).fetchall()
                for link in links:
                    source = _source(conn, link['source_id'])
                    if not full and not _covered(source, sources):
                        continue
                    item = {'record_id': link['record_id'], 'source': source}
                    if full:
                        item.update(rule_id=link['rule_id'], chart_id=link['chart_id'],
                                    fact_path=link['fact_path'], relation=link['relation'])
                    else:
                        item['relation'] = 'pre_prediction_source'
                    event_result['evidence'].append(item)
            if not full:
                event_result['withheld_records'] = len(all_records) - len(records)
                event_result['cutoff_sequence'] = boundary
                event_result['withheld_background'] = True
                event_result['training_eligible'] = False
            result['events'].append(event_result)
        return result
