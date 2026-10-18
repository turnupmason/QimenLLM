"""Reference-only curation profile for the confirmed Shenqi life chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

LIFE_SHA = '92de6590ebf88698d9bf0137e8ecdb780b8f1ff1f66765faf0a69eb3d7eac507'


def install_life(db, revision_id, curated):
    if curated['source_sha256'] != LIFE_SHA:
        raise ValueError('Life chapter fingerprint mismatch')
    method = 'shenqi_life_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-life-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_life_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
