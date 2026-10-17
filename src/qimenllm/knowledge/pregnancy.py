"""Whole supplied pregnancy/childbirth literature, with explicit reference scope."""
from .curation import install_curated
from ..cases.source_chart import PREGNANCY_SHA


def install_pregnancy(db,revision_id,curated):
    if curated['source_sha256']!=PREGNANCY_SHA:
        raise ValueError('Pregnancy chapter fingerprint mismatch')
    method='shenqi_pregnancy_reference_v1'
    return install_curated(db,revision_id,curated,profile={
        'compiler_version':'shenqi-pregnancy-reference-v1','method_id':method,
        'methods':{method:{'kind':'contextual_source_reading','professional_role_binding':False,
                           'medical_decision_support':False,'event_prediction':False}},
        'compiled_datasets':frozenset(),'row_requirements':{}})
