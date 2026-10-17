"""Context-complete supplied education/examination methods and case references."""
from .curation import install_curated
from ..cases.source_chart import EXAM_SHA


def install_exam(db,revision_id,curated):
    if curated['source_sha256']!=EXAM_SHA:
        raise ValueError('Education/examination chapter fingerprint mismatch')
    method='shenqi_exam_reference_v1'
    return install_curated(db,revision_id,curated,profile={
        'compiler_version':'shenqi-exam-reference-v1','method_id':method,
        'methods':{method:{'kind':'contextual_source_reading','professional_role_binding':False,
                           'legal_decision_support':False,'event_prediction':False}},
        'compiled_datasets':frozenset(),'row_requirements':{}})
