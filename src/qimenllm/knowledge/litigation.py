"""Reference-only curation profile for the confirmed Shenqi litigation chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

LITIGATION_SHA = 'a0cf2a05700bfb832420d3318b2982d25f6150e7a5c5e8c5ecc1ae07f5c810d2'


def install_litigation(db, revision_id, curated):
    if curated['source_sha256'] != LITIGATION_SHA:
        raise ValueError('Litigation chapter fingerprint mismatch')
    method = 'shenqi_litigation_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-litigation-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_litigation_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
