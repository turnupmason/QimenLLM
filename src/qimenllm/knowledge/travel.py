"""Reference-only curation profile for the confirmed Shenqi travel chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

TRAVEL_SHA = 'c273c803eb78a02cfb3c6c00065da81312c1851a679a1e3bca4911acdbc3bc55'


def install_travel(db, revision_id, curated):
    if curated['source_sha256'] != TRAVEL_SHA:
        raise ValueError('Travel chapter fingerprint mismatch')
    method = 'shenqi_travel_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-travel-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_travel_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
