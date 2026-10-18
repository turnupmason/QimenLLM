"""Reference-only curation profile for the confirmed Shenqi accuracy chapter.

Author arguments, claimed percentages and method disagreements remain
reference annotations, separate from project empirical evaluation.
"""
from .curation import install_curated

ACCURACY_SHA = '528174a11b617ab7d32b9c2a0a85e57a739851b4145f3a5bd544451857efbde3'


def install_accuracy(db, revision_id, curated):
    if curated['source_sha256'] != ACCURACY_SHA:
        raise ValueError('Accuracy chapter fingerprint mismatch')
    method = 'shenqi_accuracy_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-accuracy-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_methodology_source_reading',
            'project_empirical_accuracy': None,
            'automatic_empirical_score': False,
            'default_casting_method_changed': False,
            'professional_role_binding': False,
            'automatic_accuracy_prediction': False,
            'cross_method_mixing': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
