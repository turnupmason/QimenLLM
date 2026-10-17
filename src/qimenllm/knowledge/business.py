"""Reference-only curation profile for the confirmed Shenqi business chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

BUSINESS_SHA = '55cdc039b2e23b3cac1f71340aa433a9f3b50d15c230a67bc9649b9fcb296ee6'


def install_business(db, revision_id, curated):
    if curated['source_sha256'] != BUSINESS_SHA:
        raise ValueError('Business chapter fingerprint mismatch')
    method = 'shenqi_business_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-business-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_business_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
