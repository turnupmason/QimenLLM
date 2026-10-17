"""Append-only acceptance of the project owner's supplied historical sources.

This is a maintainer ingestion policy, not a permission granted to public chat
inputs. User attestations are recorded as attestations; they do not claim that
the software independently researched historical events or verified forecasts.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .db import connect, now


POLICY_ID = 'user-supplied-source-confirmation-v1'
DECLARATION_SOURCE = 'docs/user_instructions/source_confirmation_2026-10-17.txt'


def attestation_note(declaration_source: str = DECLARATION_SOURCE) -> str:
    if not isinstance(declaration_source, str) or not declaration_source.strip():
        raise ValueError('A user declaration source is required')
    return json.dumps({
        'policy_id': POLICY_ID,
        'declaration_source': declaration_source,
        'verification_basis': 'user_attestation',
        'source_facts_user_confirmed': True,
        'user_declares_independent_verification': True,
        'system_performed_independent_verification': False,
        'scope': 'supplied_source_and_explicitly_reported_facts',
        'source_owner': 'current_project_user',
        'does_not_verify': ['unreported_outcomes', 'author_hypotheses',
                            'engine_recalculation', 'model_quality',
                            'prediction_accuracy', 'clinical_validity'],
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def source_confirmation(conn, revision_id: str) -> dict:
    """Return the latest source review, keeping its verification basis explicit."""
    row = conn.execute('''SELECT * FROM source_reviews WHERE revision_id=?
        ORDER BY rowid DESC LIMIT 1''', (revision_id,)).fetchone()
    status = row['status'] if row else 'pending'
    note = {}
    if row:
        try:
            parsed = json.loads(row['note'])
            if isinstance(parsed, dict):
                note = parsed
        except (ValueError, TypeError):
            pass  # Legacy review text remains authoritative and unmodified.
    accepted = bool(row and status == 'confirmed' and row['reviewer'] == 'user')
    attested = accepted and note.get('policy_id') == POLICY_ID
    return {
        'source_acceptance': status,
        'source_facts_user_confirmed': accepted,
        'verification_basis': 'user_attestation' if accepted else None,
        'user_declares_independent_verification': bool(attested and
            note.get('user_declares_independent_verification') is True),
        'system_performed_independent_verification': False,
        'declaration_source': note.get('declaration_source') if attested else None,
        'confirmation_policy': POLICY_ID if attested else None,
        'scope': 'supplied_source_and_explicitly_reported_facts' if accepted else None,
        'source_owner': 'current_project_user' if attested else None,
    }


def append_user_attestation(conn, revision_id: str, *,
                            declaration_source: str = DECLARATION_SOURCE) -> bool:
    """Append a review if needed; caller must create its associated data version."""
    note = attestation_note(declaration_source)
    latest = conn.execute('''SELECT status,reviewer,note FROM source_reviews
        WHERE revision_id=? ORDER BY rowid DESC LIMIT 1''', (revision_id,)).fetchone()
    if latest and tuple(latest) == ('confirmed', 'user', note):
        return False
    conn.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?,?)',
        (str(uuid4()), revision_id, 'confirmed', 'user', note, now()))
    return True


def accept_user_supplied_sources(db: str | Path, *,
                                declaration_source: str = DECLARATION_SOURCE,
                                revision_ids: list[str] | None = None) -> dict:
    """Apply the owner's declaration to existing sources without rewriting rows.

    The project contains only maintainer-imported user sources. A supplied
    revision list restricts scope; an unknown revision rejects the whole change.
    Calling this repeatedly with the same declaration has no data-version churn.
    """
    from .importer import new_version

    note = attestation_note(declaration_source)
    if revision_ids is not None and (not isinstance(revision_ids, list) or
            any(not isinstance(value, str) or not value for value in revision_ids)):
        raise ValueError('revision_ids must be a list of revision identities')
    with connect(db) as conn:
        conn.execute('BEGIN IMMEDIATE')
        known = [row[0] for row in conn.execute(
            'SELECT revision_id FROM chapter_revisions ORDER BY rowid')]
        if revision_ids is not None and not set(revision_ids) <= set(known):
            raise ValueError('Unknown source revision; no confirmations appended')
        selected = known if revision_ids is None else [value for value in known if value in revision_ids]
        changes = []
        for revision_id in selected:
            previous = conn.execute('''SELECT review_id,status,reviewer,note FROM source_reviews
                WHERE revision_id=? ORDER BY rowid DESC LIMIT 1''', (revision_id,)).fetchone()
            if previous and tuple(previous)[1:] == ('confirmed', 'user', note):
                continue
            changes.append({'revision_id': revision_id,
                            'previous_review_id': previous['review_id'] if previous else None})
        if changes:
            version = new_version(conn, 'accept_user_supplied_sources',
                                  {'declaration': json.loads(note), 'sources': changes})
            for change in changes:
                append_user_attestation(conn, change['revision_id'],
                                        declaration_source=declaration_source)
        else:
            version = conn.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
        return {'status': 'confirmed', 'reviewed_revisions': len(selected),
                'appended_reviews': len(changes), 'duplicate': not changes,
                'data_version': version, 'verification_basis': 'user_attestation',
                'user_declares_independent_verification': True,
                'system_performed_independent_verification': False,
                'declaration_source': declaration_source, 'confirmation_policy': POLICY_ID}
