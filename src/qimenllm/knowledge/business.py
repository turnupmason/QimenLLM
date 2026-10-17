"""Confirmed, complete business/finance methods remain source-scoped references."""
from .curation import install_curated
from ..cases.source_chart import BUSINESS_SHA


def install_business(db, revision_id, curated):
    if curated['source_sha256'] != BUSINESS_SHA:
        raise ValueError('Business source fingerprint mismatch')
    method = 'shenqi_business_reference_v1'
    return install_curated(db, revision_id, curated, profile={
        'compiler_version': 'shenqi-business-reference-v1',
        'method_id': method,
        'methods': {method: {
            'kind': 'contextual_source_reading',
            'professional_role_binding': False,
            'automatic_prediction': False,
            'professional_financial_advice': False,
        }},
        'compiled_datasets': frozenset(),
        'row_requirements': {},
    })
