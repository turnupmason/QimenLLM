"""Context-only profile for the supplied composite appendix source."""
from .curation import install_curated

APPENDIX_SHA = 'df4a878fe719c57ef9138608a24ff12bda6c0cdbdfd577247badbdf6935fd340'


def install_appendix(db, revision_id, curated):
    if curated['source_sha256'] != APPENDIX_SHA:
        raise ValueError('Appendix fingerprint mismatch')
    method = 'shenqi_appendix_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-appendix-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_appendix_source_reading',
            'default_casting_method_changed': False,
            'professional_role_binding': False,
            'project_empirical_accuracy': None,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
