"""Whole supplied employment, transfer, retirement and election source contexts."""
from .curation import install_curated
from ..cases.source_chart import EMPLOYMENT_SHA


def install_employment(db,revision_id,curated):
    if curated['source_sha256']!=EMPLOYMENT_SHA:
        raise ValueError('Employment chapter fingerprint mismatch')
    method='shenqi_employment_reference_v1'
    return install_curated(db,revision_id,curated,profile={
        'compiler_version':'shenqi-employment-reference-v1','method_id':method,
        'methods':{method:{'kind':'contextual_source_reading','professional_role_binding':False,
                           'automatic_personality_judgment':False,'event_prediction':False}},
        'compiled_datasets':frozenset(),'row_requirements':{}})
