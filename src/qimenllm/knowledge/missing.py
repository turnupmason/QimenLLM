"""Reference-only curation profile for the confirmed Shenqi missing chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

MISSING_SHA = '5eca2a1a0914691ec439040a9b538fb8e4385fa5cf8ac5286bc5ae86d25b6574'


def install_missing(db, revision_id, curated):
    if curated['source_sha256'] != MISSING_SHA:
        raise ValueError('Missing chapter fingerprint mismatch')
    method = 'shenqi_missing_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-missing-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_missing_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
