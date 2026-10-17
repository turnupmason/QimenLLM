"""Reference-only curation profile for the confirmed Shenqi weather chapter.

The original text, conditional candidates, and complete historical narratives
remain separate from professional rule activation and model inference.
"""
from .curation import install_curated

WEATHER_SHA = '6093f9a89bd2eb889c392242892528a9022c6d9565f74be8912e2a8724663697'


def install_weather(db, revision_id, curated):
    if curated['source_sha256'] != WEATHER_SHA:
        raise ValueError('Weather chapter fingerprint mismatch')
    method = 'shenqi_weather_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-weather-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_weather_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
