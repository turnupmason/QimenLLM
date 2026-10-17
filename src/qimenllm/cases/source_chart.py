"""Read-only projection of reviewed source tables, separate from chart computation.

The four columns have an explicit, hash-scoped transcription convention. No
calendar, void, horse, extra star or medical conclusion is inferred here.
"""
from __future__ import annotations
from collections import Counter
from ..knowledge.db import connect, digest
from ..knowledge.source_confirmation import source_confirmation
from ..retrieval.repository import KnowledgeRepository

HEALTH_SHA='73ec9d99ea673dcd811ace001adb42b18f39de609b57c5c186a1f84611d5793d'
MARRIAGE_SHA='041ef45b448249e3367023ec4948c48e73c85ba2802c9d5c97686165d090e5e5'
PREGNANCY_SHA='adeaa9afad8237bba88ea3b277ec2d8cab4cb0c336b86479189fd2a3530d8d69'
EXAM_SHA='7db765dab78a42d193160e2655579af2445aa9ce24c872e39e73acae554ef2fc'
EMPLOYMENT_SHA='7a677644dcf41da4d360814a9847f07e014ae202524a9c56012a3838e6073853'
BUSINESS_SHA='55cdc039b2e23b3cac1f71340aa433a9f3b50d15c230a67bc9649b9fcb296ee6'
TRAVEL_SHA='c273c803eb78a02cfb3c6c00065da81312c1851a679a1e3bca4911acdbc3bc55'
MISSING_SHA='5eca2a1a0914691ec439040a9b538fb8e4385fa5cf8ac5286bc5ae86d25b6574'
PROJECTION='shenqi_health_table_projection_v1'
SOURCE_POLICIES={HEALTH_SHA:PROJECTION,MARRIAGE_SHA:'shenqi_marriage_table_projection_v1',
                 PREGNANCY_SHA:'shenqi_pregnancy_table_projection_v1',
                 EXAM_SHA:'shenqi_exam_table_projection_v1',
                 EMPLOYMENT_SHA:'shenqi_employment_table_projection_v1',
                 BUSINESS_SHA:'shenqi_business_table_projection_v1',
                 TRAVEL_SHA:'shenqi_travel_unicode_grid_projection_v1',
                 MISSING_SHA:'shenqi_missing_unicode_grid_projection_v1'}
NUMERALS=dict(zip('一二三四五六七八九',range(1,10)))


def _unique_name(names,short):
    matches=[name for name in names if short in name]
    if len(matches)!=1: raise ValueError('Ambiguous or unsupported source abbreviation')
    return matches[0]


def project_chart(db,case_id,chart_id):
    """Project the SAME original chart ID; return exact row citations and scope."""
    with connect(db) as conn:
        row=conn.execute('''SELECT ch.*,s.revision_id,s.byte_start,s.byte_end,d.content,d.sha256
            FROM charts ch JOIN case_events ce USING(event_id)
            JOIN source_spans s ON s.source_id=ch.source_id
            JOIN chapter_revisions cr ON cr.revision_id=s.revision_id
            JOIN raw_documents d ON d.document_id=cr.document_id
            WHERE ce.case_id=? AND ch.chart_id=? AND ch.source_or_engine='original' ''',
            (case_id,chart_id)).fetchone()
        if row is None: raise KeyError(chart_id)
        if digest(row['content'])!=row['sha256'] or digest(row['chart_json'].encode())!=row['content_sha256']:
            raise ValueError('Original chart/source integrity mismatch')
        if row['sha256'] not in SOURCE_POLICIES:
            return {'status':'not_covered','reason':'No reviewed table convention for this source',
                    'chart_id':chart_id,'professional_analysis_completed':False}
        raw=row['content']; text=raw[row['byte_start']:row['byte_end']].decode()
        review=conn.execute('SELECT status FROM source_reviews WHERE revision_id=? ORDER BY rowid DESC LIMIT 1',
                            (row['revision_id'],)).fetchone()
        confirmation=source_confirmation(conn,row['revision_id'])
    knowledge=KnowledgeRepository(db)
    compiled=knowledge.compiled_datasets('shenqi_ch1_foundation_v1')
    families={r['payload']['dataset']['key']:r for r in compiled}
    needed=('stars','doors','deities','stem_attributes')
    if any(key not in families for key in needed):
        return {'status':'not_covered','reason':'Source abbreviation reference datasets unavailable',
                'chart_id':chart_id,'professional_analysis_completed':False}
    names={key:[r['name'] for r in families[key]['payload']['dataset']['rows']] for key in needed[:3]}
    stems={r['stem'] for r in families['stem_attributes']['payload']['dataset']['rows']}
    source_lines=text.splitlines(keepends=True); start_line=raw[:row['byte_start']].count(b'\n')+1
    grid_sources={}
    if row['sha256']==TRAVEL_SHA:
        # Read literal grid cells in place. Synthetic rows are local projection
        # inputs only; their citations retain all three exact Unicode source lines.
        lines=[]
        for i,line in enumerate(source_lines):
            if '八神：' not in line: continue
            cells=[v.split('│')[1:4] for v in source_lines[i:i+3]]
            if len(cells)!=3 or any(len(v)!=3 for v in cells):
                raise ValueError('Incomplete Unicode palace row')
            for column in range(3):
                label,deity=cells[0][column].strip().split('八神：')
                door=cells[1][column].strip().split('：',1)[1]
                star=cells[2][column].strip().split('：',1)[1] if '：' in cells[2][column] else '—'
                synthetic=' '.join((label.strip(),deity,door,star))
                lines.append((i,synthetic))
                grid_sources[label.strip()]={'text':''.join(source_lines[i:i+3]),
                    'line_end':start_line+i+2,'grid_column':column+1}
        headers=[0]
    elif row['sha256']==MISSING_SHA:
        # This upload uses four unlabelled lines per grid row. The second
        # centre line is the native centre stem, never an eighth deity.
        lines=[]
        for i,line in enumerate(source_lines):
            if '│' not in line or '宫' not in line: continue
            cells=[v.split('│')[1:4] for v in source_lines[i:i+4]]
            if len(cells)!=4 or any(len(v)!=3 for v in cells):
                raise ValueError('Incomplete unlabelled Unicode palace row')
            for column in range(3):
                label=cells[0][column].strip()
                if label=='中五宫':
                    deity,door,star='—',cells[1][column].strip(),'—'
                    if cells[2][column].strip() or cells[3][column].strip():
                        raise ValueError('Unexpected native centre layout')
                else:
                    deity,door,star=(cells[n][column].strip() for n in (1,2,3))
                lines.append((i,' '.join((label,deity,door,star))))
                grid_sources[label]={'text':''.join(source_lines[i:i+4]),
                    'line_end':start_line+i+3,'grid_column':column+1}
        headers=[0]
    else:
        headers=[i for i,line in enumerate(source_lines) if line.split()==['宫位','八神','门位','星位']]
        if len(headers)!=1: raise ValueError('Expected one complete original table header')
        lines=[(i,line) for i,line in enumerate(source_lines) if i>headers[0] and line.strip()]
    if len(lines)!=9: raise ValueError('Expected nine source table rows without trailing analysis')
    palaces={}; evidence=[]
    for i,line in lines:
        cells=line.split()
        if len(cells)!=4: raise ValueError('Expected the four original table columns')
        label,deity,door,star=cells
        if len(label)!=3 or label[-1]!='宫' or label[1] not in NUMERALS:
            raise ValueError('Unsupported source palace label')
        palace=NUMERALS[label[1]]
        if palace in palaces: raise ValueError('Repeated source palace')
        source={'source_id':row['source_id'],'sha256':row['sha256'],'line':start_line+i,
                'text':line,'column_cells':cells}
        if label in grid_sources: source.update(grid_sources[label])
        if palace==5:
            # The business chapter's ninth case prints 禽己 in the native
            # centre cell. Preserve 禽 as a literal marker, without treating it
            # as an independently placed heaven star or altering its 己 stem.
            special_centre = row['sha256'] == BUSINESS_SHA and door == '禽己'
            if deity!='—' or star!='—' or (door not in stems and not special_centre):
                raise ValueError('Unsupported central palace representation')
            item={'palace':palace,'earth_stem':'己' if special_centre else door,
                  'door':None,'star':None,'deity':None,
                  'heaven_stem':None,'heaven_prefix_marker':None,'star_prefix_marker':None}
            if special_centre:
                item['native_center_prefix_marker']='禽'
                item['source_cell_as_written']='禽己'
        else:
            if len(deity)!=1: raise ValueError('Unsupported deity cell')
            # Adjacent main stems are supported by this chapter's explicit
            # overlays (e.g. case1 壬+戊, case3 乙+庚, case5 癸+庚).
            def split_cell(cell,family):
                matches=[(index,char) for index,char in enumerate(cell) if
                         char not in stems and any(char in name for name in names[family])]
                if len(matches)!=1: raise ValueError('Unsupported star/door cell')
                index,short=matches[0]; prefix=cell[:index]; suffix=cell[index+1:]
                if len(prefix)>1 or any(c not in stems for c in prefix) or len(suffix)!=1 or suffix not in stems:
                    raise ValueError('Unsupported stem markers')
                return _unique_name(names[family],short),suffix,prefix or None
            door_name,heaven,prefix=split_cell(door,'doors')
            companion = row['sha256']==TRAVEL_SHA and star=='芮禽己'
            star_name,earth,star_prefix=split_cell('芮己' if companion else star,'stars')
            item={'palace':palace,'earth_stem':earth,'heaven_stem':heaven,
                  'door':door_name,'star':star_name,'deity':_unique_name(names['deities'],deity),
                  'heaven_prefix_marker':prefix,'star_prefix_marker':star_prefix}
            if companion:
                item['source_star_cell_as_written']=star
                item['additional_star_as_written']='禽'
                item['additional_star_carried_stem']=None
        item['source']=source; palaces[palace]=item
    if set(palaces)!=set(range(1,10)): raise ValueError('Incomplete nine-palace source table')
    for key in needed:
        r=families[key]; evidence.append({'dataset':key,'source':knowledge.source(r['source_id'])})
    metadata={}
    for line in source_lines[:headers[0]]:
        if '：' in line:
            key,value=line.strip().split('：',1); metadata[key]=value
    result={'status':'projected','case_id':case_id,'chart_id':chart_id,'event_id':row['event_id'],
            'projection_method':SOURCE_POLICIES[row['sha256']],'source_sha256':row['sha256'],
            'source_acceptance':review[0] if review else 'pending',
            'source_confirmation':confirmation,
            'original_validation_status':row['validation_status'],'source_metadata':metadata,
            'palaces':{str(p):palaces[p] for p in sorted(palaces)},'reference_evidence':evidence,
            'raw_table_complete':True,'interpretation_basis':'reviewed_transcription_convention_not_engine_recalculation',
            'prefix_policy':'preserve literal markers; star-prefix meaning not assigned; no extra star inferred',
            'training_export':False,'purpose':'historical_source_chart_reading',
            'original_chart_modified':False,'engine_verified':False,'calendar_recomputed':False,
            'voids':None,'horse':None,'medical_inference':None,'professional_analysis_completed':False}
    if row['sha256'] in (MARRIAGE_SHA,PREGNANCY_SHA,EXAM_SHA,EMPLOYMENT_SHA,BUSINESS_SHA):
        counts=Counter(p['earth_stem'] for p in palaces.values())
        result['source_table_observations']={'distinct_primary_earth_stems':len(counts),
            'duplicate_primary_earth_stems':{s:[p['palace'] for p in palaces.values() if p['earth_stem']==s]
                for s,n in counts.items() if n>1},
            'scope':'literal_source_table_observation_not_original_correction_or_rejection'}
    return result


def compare_chart(projected,paper,method):
    """Compare given source symbols under an EXPLICIT alternative computation.

    A missing method is never silently filled from the example's bureau method.
    Disagreement concerns computation coverage, not acceptance of the source.
    """
    if projected['status']!='projected': return {'status':'not_covered','reason':'Source table not projected'}
    meta=projected['source_metadata']
    required=('遁法','局数','时干支')
    if any(k not in meta for k in required): return {'status':'conditional','missing':[k for k in required if k not in meta]}
    bureau_text=meta['局数']
    if not bureau_text.endswith('局') or not bureau_text[:-1].isdigit(): raise ValueError('Explicit source bureau required')
    computed=paper.calculate('symbolic_chart',{'dun':meta['遁法'],'bureau':int(bureau_text[:-1]),
                            'hour_ganzhi':meta['时干支'],'method':method})
    if computed['status']!='computed':
        return {'status':'not_covered','calculation':computed,'source_rejected':False,'engine_verified':False}
    chart=computed['result'];checks=[]
    def check(path,source,actual):
        checks.append({'path':path,'source_value':source,'computed_value':actual,'matches':source==actual})
    for palace,p in projected['palaces'].items():
        check(f'palaces.{palace}.earth_stem',p['earth_stem'],chart['earth_plate'][palace])
        if palace=='5': continue
        check(f'palaces.{palace}.door',p['door'],chart['doors'][palace])
        check(f'palaces.{palace}.deity',p['deity'],chart['deities'][palace])
        stars=[s for s in chart['heaven_plate'][palace] if s['name']==p['star']]
        check(f'palaces.{palace}.star',p['star'],stars[0]['name'] if stars else None)
        check(f'palaces.{palace}.heaven_stem',p['heaven_stem'],stars[0]['carried_stem'] if stars else None)
        if p['heaven_prefix_marker']:
            extras=[s['carried_stem'] for s in chart['heaven_plate'][palace] if s['name']!=p['star']]
            check(f'palaces.{palace}.heaven_prefix_marker',p['heaven_prefix_marker'],extras[0] if len(extras)==1 else extras)
    chief_fields={'旬首':'xun_head','值符':'zhifu_star','值使':'zhishi_door'}
    for source_key,fact_key in chief_fields.items():
        if source_key in meta:check('source_metadata.'+source_key,meta[source_key],chart['derived_facts'][fact_key])
    for source_key,fact_key in (('值符落宫','zhifu_layout_palace'),('值使落宫','zhishi_landing_palace')):
        if source_key in meta:
            digits=[c for c in meta[source_key] if c in '123456789']
            if len(digits)==2 and '寄' in meta[source_key] and source_key=='值符落宫':
                check('source_metadata.'+source_key+'.original',int(digits[0]),
                      chart['derived_facts']['zhifu_landing_original_palace'])
                check('source_metadata.'+source_key+'.hosted',int(digits[1]),chart['derived_facts'][fact_key])
            elif len(digits)==1:
                check('source_metadata.'+source_key,int(digits[0]),chart['derived_facts'][fact_key])
            else:raise ValueError('Unsupported source chief palace notation')
    return {'status':'matches' if all(c['matches'] for c in checks) else 'mismatch',
            'comparison_method':method,'source_chart_id':projected['chart_id'],
            'computed_chart_id':chart['chart_id'],'checks':checks,'calculation_evidence':computed['evidence'],
            'checked_field_count':len(checks),
            'uncompared_fields':['star_prefix_marker semantics','full nine-star expansion',
                'year/month/day calendar','voids/horse','author reasoning/clinical outcome'],
            'scope':'given_source_symbols_and_transcription_only_not_calendar_or_medical_judgment',
            'source_rejected':False,'original_chart_modified':False,'engine_verified':False,'calendar_recomputed':False}
