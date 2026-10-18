"""Reference profile for the source author's afterword; no prediction rules."""
from .curation import install_curated

AFTERWORD_SHA = 'ae609b92f0e1e1f475bece88879e811f7ded8161035e246003ecaa081f18a4eb'


def install_afterword(db, revision_id, curated):
    if curated['source_sha256'] != AFTERWORD_SHA:
        raise ValueError('Afterword fingerprint mismatch')
    method = 'shenqi_afterword_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-afterword-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_author_afterword_source_reading',
            'project_empirical_accuracy': None,
            'professional_role_binding': False,
            'automatic_prediction': False,
            'default_casting_method_changed': False,
            'external_sources_imported': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
