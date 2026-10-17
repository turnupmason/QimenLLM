"""Reference-only curation profile for the confirmed Shenqi lost chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

LOST_SHA = 'ed3c80f32c213563bf35d9f9790e330ea04e4def404f6e6ca904006a94a9eaf9'


def install_lost(db, revision_id, curated):
    if curated['source_sha256'] != LOST_SHA:
        raise ValueError('Lost chapter fingerprint mismatch')
    method = 'shenqi_lost_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-lost-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_lost_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
