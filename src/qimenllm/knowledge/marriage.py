"""Whole-source marriage literature annotations, without automatic conclusions."""
from .curation import install_curated
from ..cases.source_chart import MARRIAGE_SHA

def install_marriage(db,revision_id,curated):
    if curated['source_sha256']!=MARRIAGE_SHA:raise ValueError('Marriage chapter fingerprint mismatch')
    method='shenqi_marriage_reference_v1'
    return install_curated(db,revision_id,curated,profile={
        'compiler_version':'shenqi-marriage-reference-v1','method_id':method,
        'methods':{method:{'kind':'contextual_source_reading','professional_role_binding':False,
                           'factual_relationship_allegations':False,'event_prediction':False}},
        'compiled_datasets':frozenset(),'row_requirements':{}})
