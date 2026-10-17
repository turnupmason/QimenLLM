"""Append-only import of reviewed, whole historical narratives.

The supplied chapter bytes remain authoritative.  This importer records a source
narrative and its explicitly curated chronology; it neither recomputes a chart
nor asserts that the reported outcome was independently verified.
"""
from __future__ import annotations

from pathlib import Path

from ..knowledge.db import connect, digest
from ..knowledge.importer import ImportConflict, canonical, new_version


KINDS = frozenset(('dialogue', 'author_reasoning', 'role_selection', 'prediction',
                   'timing', 'feedback', 'continuation', 'outcome'))
PHASES = frozenset(('pre_prediction', 'prediction', 'post_feedback', 'unknown'))
EXPLICITNESS = frozenset(('author_explicit', 'not_explicit', 'agent_hypothesis'))


def _identity(kind: str, revision_id: str, key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f'Nonempty {kind} key required')
    return kind + '-' + digest(canonical([revision_id, key]).encode())


def _range(value: object, line_count: int) -> tuple[int, int]:
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(i) is not int for i in value)):
        raise ValueError('source_lines must contain two integer line numbers')
    start, end = value
    if not 1 <= start <= end <= line_count:
        raise ValueError('Source line range out of bounds')
    return start, end


def _put(conn, table: str, row: dict) -> bool:
    """Compare every authoritative field before treating a row as a duplicate."""
    keys = {'source_spans': ('source_id',), 'event_families': ('family_id',),
            'cases': ('case_id',), 'events': ('event_id',),
            'case_events': ('case_id', 'event_id'), 'charts': ('chart_id',),
            'case_records': ('record_id',),
            'evidence_links': ('record_id', 'source_id', 'relation')}[table]
    where = ' AND '.join(f'{key}=?' for key in keys)
    existing = conn.execute(f'SELECT * FROM {table} WHERE {where}',
                            tuple(row[key] for key in keys)).fetchone()
    if existing is not None:
        if any(existing[key] != value for key, value in row.items()):
            raise ImportConflict(f'Existing immutable {table} row differs')
        return False
    columns = ','.join(row)
    conn.execute(f'INSERT INTO {table} ({columns}) VALUES ({",".join("?" for _ in row)})',
                 tuple(row.values()))
    return True


def import_cases(db: str | Path, revision_id: str, curated: dict) -> dict:
    """Install complete source narratives, with stable IDs and atomic idempotence.

    Input is a reviewed JSON object with ``source_sha256`` and ``cases``.  Cases
    contain source_ranges, a family, and ordered events with charts and records.
    No tasks, splits, engine charts, or source-confirmation records are created.
    A changed curation for an existing ID is rejected rather than silently updated.
    """
    if not isinstance(curated, dict) or not isinstance(curated.get('cases'), list):
        raise ValueError('Reviewed cases object required')
    if not curated['cases']:
        raise ValueError('At least one case required')
    manifest_hash = digest(canonical(curated).encode())
    with connect(db) as conn:
        conn.execute('BEGIN IMMEDIATE')
        revision = conn.execute('''SELECT d.content,d.sha256 FROM chapter_revisions r
            JOIN raw_documents d USING(document_id) WHERE r.revision_id=?''',
            (revision_id,)).fetchone()
        if revision is None:
            raise ValueError('Unknown revision')
        raw = revision['content']
        if digest(raw) != revision['sha256'] or curated.get('source_sha256') != revision['sha256']:
            raise ValueError('Source hash mismatch')
        lines = raw.decode('utf-8').splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line.encode('utf-8')))
        if offsets[-1] != len(raw):
            raise ValueError('Cannot locate source lines without altering bytes')

        planned: list[tuple[str, dict]] = []
        seen_keys: set[tuple[str, str]] = set()
        result_cases = []
        existing_versions = set()

        def unique(kind: str, key: str) -> str:
            marker = (kind, key)
            if marker in seen_keys:
                raise ValueError(f'Duplicate {kind} key')
            seen_keys.add(marker)
            return _identity(kind, revision_id, key)

        def span(source_lines: object, locator: str) -> tuple[str, str]:
            start, end = _range(source_lines, len(lines))
            left, right = offsets[start - 1], offsets[end]
            source_id = 'span-' + digest(canonical([revision_id, left, right, locator]).encode())
            planned.append(('source_spans', dict(source_id=source_id, revision_id=revision_id,
                byte_start=left, byte_end=right, locator=locator)))
            return source_id, raw[left:right].decode('utf-8')

        for case in curated['cases']:
            case_key = case['case_key']
            case_id = unique('case', case_key)
            if case.get('completeness') not in ('partial', 'complete', 'confirmed_complete'):
                raise ValueError('Explicit source narrative completeness required')
            # Confirmation belongs to the source review workflow, never to this importer.
            if case['completeness'] == 'confirmed_complete':
                review = conn.execute('''SELECT status FROM source_reviews WHERE revision_id=?
                    ORDER BY rowid DESC LIMIT 1''', (revision_id,)).fetchone()
                if review is None or review[0] != 'confirmed':
                    raise ValueError('Source not confirmed; confirmed_complete forbidden')
            ranges = case.get('source_ranges')
            if not isinstance(ranges, list) or not ranges:
                raise ValueError('Whole case source_ranges required')
            case_ranges = [_range(source_lines, len(lines)) for source_lines in ranges]
            def case_range(source_lines: object) -> None:
                start, end = _range(source_lines, len(lines))
                if not any(left <= start <= end <= right for left, right in case_ranges):
                    raise ValueError('Case record/chart/evidence outside whole narrative ranges')
            case_spans = []
            for index, source_lines in enumerate(ranges):
                _range(source_lines, len(lines))
                source_id, _ = span(source_lines, f'case:{case_key}:narrative:{index}')
                case_spans.append(source_id)
            family = case['family']
            # Explicit event-family keys are global across books and revisions.
            # This is curated identity, never a fuzzy guess from similar stories.
            family_key = family['family_key']
            if not isinstance(family_key, str) or not family_key.strip():
                raise ValueError('Nonempty explicit event family key required')
            family_id = 'family-' + digest(canonical(family_key).encode())
            planned.append(('event_families', dict(family_id=family_id, description=family['description'])))
            old_case = conn.execute('SELECT data_version FROM cases WHERE case_id=?', (case_id,)).fetchone()
            if old_case:
                existing_versions.add(old_case['data_version'])
            case_row = dict(case_id=case_id, source_id=case_spans[0], title=case['title'],
                            completeness=case['completeness'], data_version=None)
            planned.append(('cases', case_row))
            events = case.get('events')
            if not isinstance(events, list) or not events:
                raise ValueError('Historical case requires events')
            event_ids = []
            for event_sequence, event in enumerate(events):
                event_key = event['event_key']
                event_id = unique('event', event_key)
                event_ids.append(event_id)
                if event.get('chronology_status') not in ('unknown', 'ordered'):
                    raise ValueError('Narrative import cannot assert independently verified chronology')
                background = dict(event.get('background', {}))
                if '_case_import' in background:
                    raise ValueError('Reserved background field')
                background['_case_import'] = {
                    'case_key': case_key, 'event_key': event_key,
                    'case_source_ids': case_spans, 'source_ranges': ranges,
                    'source_sha256': revision['sha256'], 'manifest_sha256': manifest_hash,
                    'prediction_input_policy': event.get('prediction_input_policy'),
                    'independently_verified': False,
                    'full_curated_case': case,
                }
                planned.append(('events', dict(event_id=event_id, family_id=family_id,
                    background_json=canonical(background), chronology_status=event['chronology_status'])))
                planned.append(('case_events', dict(case_id=case_id, event_id=event_id,
                    sequence=event_sequence)))
                chart_ids = {}
                for chart in event.get('charts', []):
                    chart_key = chart['chart_key']
                    chart_id = unique('chart', chart_key)
                    chart_ids[chart_key] = chart_id
                    case_range(chart['source_lines'])
                    source_id, _ = span(chart['source_lines'], f'case:{case_key}:chart:{chart_key}')
                    payload = chart.get('payload')
                    if not isinstance(payload, dict):
                        raise ValueError('Original chart payload must be an object')
                    if chart.get('source_or_engine', 'original') != 'original':
                        raise ValueError('Case import only stores original charts')
                    status = chart.get('validation_status', 'original_parsed')
                    if status not in ('original_unparsed', 'original_parsed'):
                        raise ValueError('Source narrative cannot establish engine validation')
                    chart_body = canonical(payload)
                    planned.append(('charts', dict(chart_id=chart_id, event_id=event_id,
                        source_id=source_id, source_or_engine='original',
                        casting_method=chart.get('casting_method'), method_version=chart.get('method_version'),
                        # SQL metadata indexes contain only explicit top-level
                        # fields in this import artifact.  Source facts supplied
                        # inside payload remain intact there; missing indexes do
                        # not authorize modifying an existing original chart.
                        input_datetime=chart.get('input_datetime'), timezone=chart.get('timezone'),
                        location_json=canonical(chart['location']) if chart.get('location') is not None else None,
                        chart_json=chart_body, content_sha256=digest(chart_body.encode()),
                        validation_status=status)))
                records = event.get('records')
                if not isinstance(records, list) or not records:
                    raise ValueError('Historical event requires ordered source records')
                record_ids, record_sources = {}, {}
                sequences = set()
                for record in records:
                    key = record['record_key']
                    record_id = unique('record', key)
                    record_ids[key] = record_id
                    seq = record['sequence']
                    if type(seq) is not int or seq < 0 or seq in sequences:
                        raise ValueError('Unique nonnegative record sequence required')
                    sequences.add(seq)
                    if record['kind'] not in KINDS or record['knowledge_phase'] not in PHASES:
                        raise ValueError('Invalid record kind or knowledge phase')
                    if record.get('explicitness') not in EXPLICITNESS:
                        raise ValueError('Record explicitness required')
                    if record['kind'] in ('feedback', 'outcome', 'continuation') and record['knowledge_phase'] == 'pre_prediction':
                        raise ValueError('Post-event material cannot be pre-prediction input')
                    case_range(record['source_lines'])
                    source_id, text = span(record['source_lines'], f'case:{case_key}:record:{key}')
                    if record.get('text') not in (text, text.rstrip('\r\n')):
                        raise ValueError('Record text differs from exact source range')
                    record_sources[key] = source_id
                    chart_key = record.get('chart_key')
                    if chart_key is not None and chart_key not in chart_ids:
                        raise ValueError('Record references unknown chart')
                    planned.append(('case_records', dict(record_id=record_id, event_id=event_id,
                        chart_id=chart_ids.get(chart_key), sequence=seq, kind=record['kind'],
                        knowledge_phase=record['knowledge_phase'], source_id=source_id,
                        speaker=record.get('speaker'), text=text,
                        payload_json=canonical(record.get('payload', {})),
                        explicitness=record['explicitness'], reported_at=record.get('reported_at'))))
                    planned.append(('evidence_links', dict(record_id=record_id, source_id=source_id,
                        rule_id=None, chart_id=chart_ids.get(chart_key), fact_path=None,
                        relation='exact_source_record')))
                # A pre-forecast label after a source prediction/feedback is suspect,
                # unless unknown chronology is retained instead of granting input access.
                boundary = min((r['sequence'] for r in records if r['knowledge_phase'] in
                                ('prediction', 'post_feedback')), default=None)
                if boundary is not None and any(r['knowledge_phase'] == 'pre_prediction' and
                                               r['sequence'] >= boundary for r in records):
                    raise ValueError('Pre-prediction record occurs after forecast boundary')
                for evidence in event.get('evidence_links', []):
                    record_key = evidence['record_key']
                    if record_key not in record_ids:
                        raise ValueError('Evidence references unknown record')
                    case_range(evidence['source_lines'])
                    source_id, _ = span(evidence['source_lines'],
                        f'case:{case_key}:evidence:{record_key}:{evidence["relation"]}')
                    chart_key = evidence.get('chart_key')
                    if chart_key is not None and chart_key not in chart_ids:
                        raise ValueError('Evidence references unknown chart')
                    planned.append(('evidence_links', dict(record_id=record_ids[record_key],
                        source_id=source_id, rule_id=None, chart_id=chart_ids.get(chart_key),
                        fact_path=evidence.get('fact_path'), relation=evidence['relation'])))
            result_cases.append({'case_key': case_key, 'case_id': case_id,
                                 'family_id': family_id, 'event_ids': event_ids})
        if len(existing_versions) > 1:
            raise ImportConflict('Case manifest spans multiple existing imports')
        # A fully existing manifest must compare identically without adding a version.
        existing_count = sum(conn.execute('SELECT 1 FROM cases WHERE case_id=?',
                                         (c['case_id'],)).fetchone() is not None for c in result_cases)
        if existing_count not in (0, len(result_cases)):
            raise ImportConflict('Partial manifest already exists; explicit new import required')
        duplicate = existing_count == len(result_cases)
        version = next(iter(existing_versions)) if duplicate else new_version(conn, 'import_cases', {
            'revision_id': revision_id, 'manifest_sha256': manifest_hash,
            'case_ids': [case['case_id'] for case in result_cases]})
        counts = {}
        for table, row in planned:
            if table == 'cases':
                row['data_version'] = version
            added = _put(conn, table, row)
            counts[table] = counts.get(table, 0) + int(added)
            if duplicate and added:
                raise ImportConflict('Existing case import is incomplete')
        return {'duplicate': duplicate, 'data_version': version,
                'source_sha256': revision['sha256'], 'manifest_sha256': manifest_hash,
                'cases': result_cases, 'added': counts, 'training_tasks_added': 0}
