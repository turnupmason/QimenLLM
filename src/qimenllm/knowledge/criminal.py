"""Reference-only curation profile for the confirmed Shenqi criminal chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

CRIMINAL_SHA = '289465c220a0701545b9f093b4b91d041d600a4c9da67bf58e33a10ece0f0ea9'


def install_criminal(db, revision_id, curated):
    if curated['source_sha256'] != CRIMINAL_SHA:
        raise ValueError('Criminal chapter fingerprint mismatch')
    method = 'shenqi_criminal_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-criminal-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_criminal_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
