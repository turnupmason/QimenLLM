"""Explicit compiler scope for the newly supplied second chapter."""
from .curation import install_curated


SOURCE_SHA='617c7936aeb2dff7b82a9d461ac030ec37011ee83e8c4169429288f10075ff92'
PROFILE={
    'compiler_version':'shenqi-chapter02-v1',
    'method_id':'shenqi_ch2_foundation_v1',
    'methods':{
        'shenqi_ch2_foundation_v1':{'kind':'provided_chapter_foundation','calendar_engine':False},
        'shenqi_ch2_paper_v1':{'kind':'paper_rotation','requires_known_dun_bureau_hour':True,
            'center_star_follows_companion':True,'final_door_in_center':'not_covered',
            'calendar_engine':False,'voids_and_horse':False},
    },
    'compiled_datasets':frozenset({'palm_branches','palm_palaces','hour_windows','five_rat_hours',
        'stem_combinations','rotation_conventions','explicit_palace_elements','chapter_element_relations'}),
    'row_requirements':{
        'palm_branches':(12,{'branch'}),'palm_palaces':(9,{'palace'}),
        'hour_windows':(12,{'branch','start_hour','end_hour'}),
        'five_rat_hours':(5,{'day_stems','hours'}),'stem_combinations':(5,{'stems','element'}),
        'rotation_conventions':(1,{'clockwise_palaces','center_original_palace','center_host_palace',
            'center_star','center_companion_star','deity_order'}),
        'explicit_palace_elements':(3,{'palace','element'}),
        'chapter_element_relations':(2,{'source','relation','target'}),
    },
}


def install_chapter02(db, revision_id, curated):
    if curated['source_sha256']!=SOURCE_SHA:
        raise ValueError('Chapter two source revision mismatch')
    return install_curated(db,revision_id,curated,profile=PROFILE)
