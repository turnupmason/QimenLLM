"""Reference-only curation profile for the confirmed Shenqi geography chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

GEOGRAPHY_SHA = 'c755e3879432b2f84329e0b9491eabdb48b865fa2f1cad96a0187f1bb7a3f5c1'


def install_geography(db, revision_id, curated):
    if curated['source_sha256'] != GEOGRAPHY_SHA:
        raise ValueError('Geography chapter fingerprint mismatch')
    method = 'shenqi_geography_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-geography-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_geography_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
