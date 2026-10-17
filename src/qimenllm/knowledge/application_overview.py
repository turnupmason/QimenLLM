"""Explicit compiler scope for the supplied, unnumbered application overview."""
from .curation import install_curated

SOURCE_SHA='2022ad633e935eeca7970b74c0df7af8c980ebb2867def3a0d2593e32656ac9a'
METHOD='shenqi_application_facts_v1'
REQUIREMENTS={
    'inner_outer_palaces':(16,{'dun','palace','classification','scope'}),
    'timing_chief_examples':(9,{'xun_head','palace','trigger','branch','time_unit'}),
    'comparison_scopes':(3,{'axis','basis','source_lines'}),
}

def install_application(db,revision_id,curated):
    if curated['source_sha256']!=SOURCE_SHA:
        raise ValueError('Application overview fingerprint mismatch')
    present={g['dataset']['key'] for g in curated['groups'] if g.get('dataset')}
    if not set(REQUIREMENTS)<=present: raise ValueError('Missing application fact datasets')
    return install_curated(db,revision_id,curated,profile={
        'compiler_version':'shenqi-application-overview-v1','method_id':METHOD,
        'methods':{METHOD:{'kind':'source_symbolic_facts','professional_role_binding':False,
                          'calendar_engine':False,'timing_scope':'exact_source_examples_only'}},
        'compiled_datasets':frozenset(REQUIREMENTS),'row_requirements':REQUIREMENTS})
