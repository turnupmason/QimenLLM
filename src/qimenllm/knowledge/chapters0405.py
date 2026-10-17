"""Explicit, scoped compilers for this combined upload. Interpretations stay references."""
from .curation import install_curated


SOURCE_SHAS={
    4:'15ce23c3fff0c9d3a48b595ee3bbf115d0c1e98a64ce1efc88bdb27e67eab22a',
    5:'e153de133f4c5b6c325361ff30a572e782becbb245bb471599d678bb6349679d',
}
REQUIREMENTS={
    4:{
        'branch_attributes':(12,{'branch','polarity','element'}),
        'stem_life_stages':(10,{'stem','stages'}),
        'stem_clashes':(4,{'stems','relation','symmetric_pair'}),
        'door_seasonal_strength':(8,{'door','states'}),
        'door_palace_profiles':(8,{'door','home_palace','profiles'}),
        'star_strength_rules':(5,{'relation','state'}),
        'branch_relations':(38,{'relation','branches','directed'}),
        'element_edges_ch4':(7,{'source','relation','target'}),
    },
    5:{
        'element_edges_ch5':(7,{'source','relation','target'}),
        'six_instrument_punishments':(6,{'heaven_stem','palace'}),
        'wonder_tomb_palaces':(4,{'heaven_stem','palace','convention'}),
        'wonder_restraints':(10,{'heaven_stem','condition_type','palace','earth_stem'}),
        'door_palace_relations':(4,{'subject','relation','object','name'}),
        'door_pressure_pairs':(13,{'door','door_element','palace','palace_element'}),
        'five_missed_hour_pairs':(10,{'day_stem','hour_ganzhi','same_polarity_required'}),
        'heavenly_manifest_hours':(12,{'day_stem','hour_ganzhi'}),
    },
}


def profile(chapter):
    method=f'shenqi_ch{chapter}_facts_v1'
    methods={method:{'kind':'source_symbolic_facts','professional_role_binding':False,
                     'event_prediction':False}}
    if chapter==4:
        methods['shenqi_ch4_star_month_v1']={'kind':'author_selected_star_strength',
            'basis':'given_month_build_element','star_generates_month':'旺','same':'相',
            'month_generates_star':'废','star_controls_month':'休','month_controls_star':'囚',
            'palace_is_not_a_substitute_for_month':True}
    else:
        methods['shenqi_ch5_tomb_stem_v1']={'kind':'wonder_tomb_convention','basis':'stem_life_stage',
                                          'favorable_unfavorable_prediction':False}
        methods['shenqi_ch5_tomb_wood_v1']={'kind':'wonder_tomb_convention','basis':'general_wood',
                                          'favorable_unfavorable_prediction':False}
    return {'compiler_version':f'shenqi-chapter{chapter:02d}-v1','method_id':method,
            'methods':methods,'compiled_datasets':frozenset(REQUIREMENTS[chapter]),
            'row_requirements':REQUIREMENTS[chapter]}


def install_chapter(db, revision_id, curated, chapter):
    if chapter not in SOURCE_SHAS or curated['source_sha256']!=SOURCE_SHAS[chapter]:
        raise ValueError('Uploaded chapter fingerprint mismatch')
    present={g['dataset']['key'] for g in curated['groups'] if g.get('dataset')}
    if not set(REQUIREMENTS[chapter])<=present: raise ValueError('Missing explicit fact datasets')
    return install_curated(db,revision_id,curated,profile=profile(chapter))
