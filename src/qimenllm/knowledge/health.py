"""Contextual health literature annotations; no compiled medical rules."""
from .curation import install_curated
from ..cases.source_chart import HEALTH_SHA

def install_health(db,revision_id,curated):
    if curated['source_sha256']!=HEALTH_SHA: raise ValueError('Health chapter fingerprint mismatch')
    method='shenqi_health_reference_v1'
    return install_curated(db,revision_id,curated,profile={
        'compiler_version':'shenqi-health-reference-v1','method_id':method,
        'methods':{method:{'kind':'contextual_source_reading','medical_diagnosis':False,
                           'professional_role_binding':False,'event_prediction':False}},
        'compiled_datasets':frozenset(),'row_requirements':{}})
