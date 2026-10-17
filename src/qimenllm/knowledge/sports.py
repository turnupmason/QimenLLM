"""Reference-only curation profile for the confirmed Shenqi sports chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

SPORTS_SHA = '784f49224b8a540850dde469a0fe720d23ee4ab551fa9600dca6137eb4fb5a2b'


def install_sports(db, revision_id, curated):
    if curated['source_sha256'] != SPORTS_SHA:
        raise ValueError('Sports chapter fingerprint mismatch')
    method = 'shenqi_sports_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-sports-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_sports_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
