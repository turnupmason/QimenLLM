"""Source-scoped condition inspection, deliberately separate from official rule activation.

Candidates describe the supplied text. They are not ``rules`` records and cannot
be passed to RuleSelector.bind or the professional model gateway. A symbolic
condition match and approval to execute a professional rule are separate states.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from ..knowledge.db import connect, digest
from ..knowledge.importer import canonical, new_version
from .selector import evaluate


SCHEMA_VERSION = 'source_selection_candidates_v1'
KIND = 'source_selection_candidate'


def _validate_condition(condition: dict) -> None:
    if not isinstance(condition, dict) or not isinstance(condition.get('field'), str) or not condition['field']:
        raise ValueError('A candidate condition requires an explicit field')
    if condition.get('op') not in {'eq', 'in', 'present'} or 'value' not in condition:
        raise ValueError('Unsupported candidate condition protocol')
    if condition['op'] == 'in' and not isinstance(condition['value'], list):
        raise ValueError('Candidate membership requires an array')


def install_candidates(db: str | Path, revision_id: str, artifact: dict) -> dict:
    """Append validated annotations atomically; reinstallation cannot change a key.

    Exact quotes are checked against their supplied line range before any write.
    The DB's executable/approval flags remain false even after a condition match.
    No training tasks, formal rules, method defaults or predictions are created.
    """
    canonical(artifact)
    if artifact.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported candidate artifact schema')
    candidates = artifact.get('candidates')
    if not isinstance(candidates, list) or len(candidates) != artifact.get('candidate_count'):
        raise ValueError('Candidate count mismatch')
    historical = artifact.get('historical_candidates', [])
    if not isinstance(historical, list):
        raise ValueError('Historical candidate records must be an array')
    if artifact.get('candidate_record_count', len(candidates) + len(historical)) != len(candidates) + len(historical):
        raise ValueError('Candidate record count mismatch')
    latest_keys = [candidate.get('key') for candidate in candidates if isinstance(candidate, dict)]
    if len(latest_keys) != len(candidates) or len(set(latest_keys)) != len(latest_keys):
        raise ValueError('Duplicate or missing current candidate key')
    keys = set()
    with connect(db) as conn:
        conn.execute('BEGIN IMMEDIATE')
        source = conn.execute('''SELECT d.content,d.sha256 FROM chapter_revisions r
            JOIN raw_documents d USING(document_id) WHERE revision_id=?''', (revision_id,)).fetchone()
        if source is None:
            raise ValueError('Unknown candidate source revision')
        raw = source['content']; lines = raw.splitlines(keepends=True)
        if digest(raw) != source['sha256'] or source['sha256'] != artifact.get('source_sha256'):
            raise ValueError('Candidate source hash mismatch')
        if len(raw) != artifact.get('source_byte_count') or len(lines) != artifact.get('source_line_count'):
            raise ValueError('Candidate source dimensions mismatch')
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        pending = []; versions = {}
        for row in conn.execute('''SELECT k.payload_json FROM knowledge_items k
                JOIN source_spans s USING(source_id) WHERE s.revision_id=?
                AND json_extract(k.payload_json,'$.kind')=?''', (revision_id, KIND)):
            prior = json.loads(row['payload_json'])
            versions.setdefault(prior['candidate']['key'], set()).add(prior.get('record_revision', 1))
        for candidate in historical + candidates:
            if not isinstance(candidate, dict):
                raise ValueError('Candidate must be an object')
            key = candidate.get('key')
            record_revision = candidate.get('record_revision', 1)
            if type(record_revision) is not int or record_revision < 1:
                raise ValueError('Invalid candidate record revision')
            if not isinstance(key, str) or not key or (key, record_revision) in keys:
                raise ValueError('Duplicate or missing candidate key')
            if key not in latest_keys:
                raise ValueError('Historical candidate must retain a current record')
            keys.add((key, record_revision))
            if not isinstance(candidate.get('domain'), str) or not candidate['domain']:
                raise ValueError('Candidate domain required')
            for collection in ('require', 'exclude'):
                if not isinstance(candidate.get(collection), list):
                    raise ValueError('Explicit candidate conditions required')
                for condition in candidate[collection]:
                    _validate_condition(condition)
            choice = candidate.get('method_choice')
            if not isinstance(choice, dict) or not isinstance(choice.get('method_id'), str) or not choice['method_id']:
                raise ValueError('Explicit candidate method required')
            if (candidate.get('formal_role_activation_allowed') is not False or
                    candidate.get('professional_prediction_completed') is not False):
                raise ValueError('Source candidates cannot authorize professional inference')
            numbers = candidate.get('source_lines')
            if (not isinstance(numbers, list) or not numbers or
                    any(type(n) is not int or n < 1 or n > len(lines) for n in numbers) or
                    numbers != sorted(set(numbers))):
                raise ValueError('Invalid candidate source lines')
            start, end = min(numbers), max(numbers)
            excerpt = b''.join(lines[start-1:end]).decode('utf-8')
            # Candidate quotes omit only the final line terminator; blanks inside
            # the range are retained. The source bytes themselves never change.
            if candidate.get('source_quote') != excerpt.rstrip('\r\n'):
                raise ValueError('Candidate quote differs from original source: ' + key)
            payload = {'kind': KIND, 'schema_version': SCHEMA_VERSION,
                       'source_sha256': source['sha256'], 'candidate': candidate}
            if record_revision > 1:
                payload['record_revision'] = record_revision
            encoded = canonical(payload)
            identity = [revision_id, SCHEMA_VERSION, key]
            if record_revision > 1:
                identity.append(record_revision)
            item_id = 'candidate-' + digest(canonical(identity).encode())
            existing = conn.execute('SELECT payload_json FROM knowledge_items WHERE item_id=?', (item_id,)).fetchone()
            if existing is not None:
                if existing['payload_json'] != encoded:
                    raise ValueError('Changed candidate requires an explicit version: ' + key)
                continue
            prior_versions = versions.setdefault(key, set())
            if prior_versions != set(range(1, record_revision)):
                raise ValueError('Candidate revisions require contiguous prior records: ' + key)
            prior_versions.add(record_revision)
            category = ('timing' if candidate['domain'] == 'timing' else
                        'casting' if candidate['domain'] == 'case_reproduction' else
                        'analysis' if candidate['domain'] in {'host_guest_classification', 'method_selection'} else 'role')
            locator = f"来源条件候选 {key}；输入行 {start}–{end}"
            if record_revision > 1:
                locator += f'；候选修订 {record_revision}'
            source_id = 'span-' + digest(canonical([revision_id, offsets[start-1], offsets[end], locator]).encode())
            pending.append((item_id, category, source_id, encoded, offsets[start-1], offsets[end], locator))
        for candidate in candidates:
            if candidate.get('record_revision', 1) != max(revision for key, revision in keys if key == candidate['key']):
                raise ValueError('Current candidate must be its latest supplied record revision')
        if not pending:
            return {'added': 0, 'duplicate': True, 'formal_rules_added': 0,
                    'data_version': conn.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]}
        version = new_version(conn, 'annotate_source_selection_candidates', {
            'source_sha256': source['sha256'], 'schema_version': SCHEMA_VERSION,
            'candidate_ids': [row[0] for row in pending]})
        for item_id, category, source_id, encoded, start, end, locator in pending:
            conn.execute('INSERT OR IGNORE INTO source_spans VALUES (?,?,?,?,?)',
                         (source_id, revision_id, start, end, locator))
            conn.execute('''INSERT INTO knowledge_items(item_id,category,source_id,payload_json,
                structured,applicability_confirmed,compiled,reference_only,data_version)
                VALUES (?,?,?,?,1,0,0,1,?)''', (item_id, category, source_id, encoded, version))
        return {'added': len(pending), 'duplicate': False, 'formal_rules_added': 0, 'data_version': version}


def _inspect_conditions(candidate: dict, context: dict, method: str | None) -> dict:
    reasons, missing, checks = [], [], []
    for kind in ('exclude', 'require'):
        for index, condition in enumerate(candidate[kind]):
            value = evaluate({'field': condition['field'], 'operator': condition['op'],
                              'expected_json': canonical(condition['value'])}, context)
            checks.append({'kind': kind, 'field': condition['field'], 'operator': condition['op'],
                           'result': 'unknown' if value is None else 'matched' if value else 'not_matched'})
            if value is None:
                missing.append(condition['field'])
            elif (kind == 'exclude' and value) or (kind == 'require' and not value):
                reasons.append(f'{kind}_condition_failed:{index}:{condition["field"]}')
    choice = candidate['method_choice']
    if method is not None and method != choice['method_id']:
        reasons.append('method_mismatch')
    status = 'excluded' if reasons else 'conditional' if missing else 'applicable'
    if status == 'applicable' and choice.get('status') == 'explicit_choice_required' and method is None:
        # The four concrete geng-side candidates explicitly require a named
        # perspective in their context. That satisfies their local method choice.
        explicitly_conditioned = any(c['field'] == 'geng_polarity_method' and c['op'] == 'eq'
                                     for c in candidate['require'])
        if not explicitly_conditioned:
            status = 'disputed'; reasons.append('multiple_methods_require_selection')
    return {'symbolic_status': status, 'reasons': reasons, 'missing': sorted(set(missing)),
            'condition_checks': checks}


def inspect_candidates(db: str | Path, context: dict, domain: str | None = None,
                       method: str | None = None) -> dict:
    """Query the actual DB and inspect all conditions; never infer missing roles.

    ``domain`` is an optional SQL filter. Without it all recorded candidates are
    audited against context, retaining excluded rules and their reasons. Method
    selection is explicit. Client context and source statements are never treated
    as validated chart facts or permission to activate a professional role.
    """
    if not isinstance(context, dict):
        raise ValueError('Candidate context must be an object')
    canonical(context)
    for value in (domain, method):
        if value is not None and (not isinstance(value, str) or not value):
            raise ValueError('Candidate filters must be nonempty strings')
    if domain is not None and context.get('domain') not in (None, domain):
        raise ValueError('Candidate domain conflicts with explicit context')
    selected_context = {**context, **({'domain': domain} if domain is not None else {})}
    query = '''SELECT k.item_id,k.source_id,k.payload_json,k.data_version,s.revision_id,
        s.byte_start,s.byte_end,s.locator,d.content,d.sha256,c.title AS chapter,b.title AS book,
        (SELECT status FROM source_reviews sr WHERE sr.revision_id=s.revision_id
         ORDER BY sr.rowid DESC LIMIT 1) AS source_acceptance
        FROM knowledge_items k JOIN source_spans s USING(source_id)
        JOIN chapter_revisions r USING(revision_id) JOIN raw_documents d USING(document_id)
        JOIN chapters c USING(chapter_id) JOIN books b USING(book_id)
        WHERE json_extract(k.payload_json,'$.kind')=? AND NOT EXISTS (
            SELECT 1 FROM knowledge_items newer JOIN source_spans ns USING(source_id)
            WHERE ns.revision_id=s.revision_id
            AND json_extract(newer.payload_json,'$.kind')=json_extract(k.payload_json,'$.kind')
            AND json_extract(newer.payload_json,'$.candidate.key')=json_extract(k.payload_json,'$.candidate.key')
            AND COALESCE(json_extract(newer.payload_json,'$.record_revision'),1)>
                COALESCE(json_extract(k.payload_json,'$.record_revision'),1))'''
    parameters = [KIND]
    if domain is not None:
        query += " AND json_extract(k.payload_json,'$.candidate.domain')=?"
        parameters.append(domain)
    query += ' ORDER BY k.item_id'
    entries = []
    with connect(db) as conn:
        for row in conn.execute(query, parameters):
            payload = json.loads(row['payload_json']); candidate = payload['candidate']
            if digest(row['content']) != row['sha256'] or payload['source_sha256'] != row['sha256']:
                raise ValueError('Candidate source integrity mismatch')
            decision = _inspect_conditions(candidate, selected_context, method)
            symbolic = decision['symbolic_status']
            acceptance = row['source_acceptance'] or 'pending'
            # No promotion path is hidden in this read-only inspector: even a
            # confirmed original needs a separately compiled and tested rule.
            status = symbolic if symbolic != 'applicable' else 'reference_only'
            if acceptance == 'disputed' and symbolic == 'applicable':
                status = 'disputed'; decision['reasons'].append('source_acceptance_disputed')
            proposal = None
            if symbolic == 'applicable' and acceptance != 'disputed' and candidate.get('role_binding'):
                proposal = {**deepcopy(candidate['role_binding']), 'hypothetical': True,
                            'scope': 'source_condition_match_not_formal_binding',
                            'source_id': row['source_id'], 'source_acceptance': acceptance}
            entries.append({'candidate_key': candidate['key'], 'item_id': row['item_id'],
                'record_revision': payload.get('record_revision', 1),
                'domain': candidate['domain'], 'method_id': candidate['method_choice']['method_id'],
                'status': status, **decision, 'activation_status': 'reference_only',
                'activation_reasons': ['candidate_not_compiled_as_professional_rule'] +
                                      ([] if acceptance == 'confirmed' else ['source_not_confirmed']),
                'source_acceptance': acceptance, 'reference_only': candidate['reference_only'],
                'method_choice': deepcopy(candidate['method_choice']),
                'unique': candidate['unique'], 'notes': candidate['notes'], 'exceptions': candidate['exceptions'],
                'role_bindings': [], 'hypothetical_role_recommendation': proposal,
                'source': {'source_id': row['source_id'], 'revision_id': row['revision_id'],
                           'book': row['book'], 'chapter': row['chapter'], 'locator': row['locator'],
                           'sha256': row['sha256'], 'data_version': row['data_version'],
                           'source_lines': candidate['source_lines'], 'quote': candidate['source_quote'],
                           'excerpt': row['content'][row['byte_start']:row['byte_end']].decode('utf-8')}})
    counts = dict(Counter(entry['symbolic_status'] for entry in entries))
    return {'status': 'inspected', 'scope': 'source_scoped_candidate_conditions_only',
            'query': {'sql': query, 'parameters': parameters}, 'domain': domain, 'selected_method': method,
            'candidate_count': len(entries), 'symbolic_status_counts': counts, 'candidates': entries,
            'role_bindings': [], 'professional_analysis_completed': False, 'calendar_recomputed': False,
            'concrete_date': None, 'model_analysis': None,
            'limitation': '候选条件匹配不等于正式用神绑定；来源验收与规则编译分别跟踪。'}
