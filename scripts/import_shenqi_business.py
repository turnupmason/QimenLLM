#!/usr/bin/env python3
"""Source-bound import of the user's confirmed Shenqi business chapter.

Conservative, deterministic editorial segmentation. This is NOT an oracle or
independent gold transcription and creates no formal rules/training samples.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

from qimenllm.cases.ingestion import import_cases
from qimenllm.github_sync import SyncError, sync_github
from qimenllm.knowledge.curation import install_curated
from qimenllm.knowledge.importer import import_chapter
from qimenllm.rules.candidates import install_candidates

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = '55cdc039b2e23b3cac1f71340aa433a9f3b50d15c230a67bc9649b9fcb296ee6'
SOURCE_FILE = ROOT / 'data/provenance/uploads' / (SOURCE_SHA + '.utf8')
DATA = ROOT / 'data/structured/shenqi'
# Each authored case is kept whole; case 12 contains three source charts and
# five distinct time/day observations within ONE event family.
CASE_STARTS = [171,233,309,397,479,535,592,682,792,898,978,1032,1254,1307]
SECTIONS = [(1,16,'经营求财总论','analysis'),(17,22,'交易求财','role'),
    (23,34,'投资求财','analysis'),(35,46,'买货求财','analysis'),
    (47,64,'卖货求财','analysis'),(65,80,'房地产买卖','analysis'),
    (81,94,'开店求财','analysis'),(95,106,'合伙求财','role'),
    (107,124,'贷款或借钱','role'),(125,140,'放贷','role'),
    (141,168,'讨债','role'),(169,170,'实例解析标题','commentary')]
CANDIDATE_LINES = [(3,'general_profit','general_roles',['日干','时干','甲子戊','生门']),
    (19,'transaction','buyer_seller_broker',['日干','时干','六合']),
    (25,'investment','capital_interest',['甲子戊','生门']),
    (37,'purchase_goods','buyer_goods',['日干','时干']),
    (49,'sale_goods','seller_buyer',['值符','值使']),
    (55,'sale_goods','seller_goods_capital',['日干','时干','甲子戊','生门']),
    (67,'real_estate','property_deed',['生门','死门','值符']),
    (83,'open_shop','shop_operator',['日干','开门']),
    (97,'partnership','self_partner',['日干','时干']),
    (103,'partnership','earth_self_heaven_partner',['地盘日干','天盘之干']),
    (109,'borrow','bank_borrower',['值符','值使']),
    (117,'borrow','direction_star_guest_host',['天盘星','地盘星']),
    (127,'lend','lender_borrower_interest',['值符','天乙','生门']),
    (143,'collect_debt','creditor_debtor_collector',['值符','天乙','伤门'])]


def source_lines(raw: bytes) -> list[str]:
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Business source bytes differ from the user upload')
    text = raw.decode('utf-8')
    lines = text.splitlines(keepends=True)
    if len(raw) != 56047 or len(lines) != 1366 or not raw.endswith(b'\n'):
        raise ValueError('Unexpected source dimensions')
    starts=[i for i,t in enumerate(lines,1) if re.match(r'^实例[一二三四五六七八九十]+：',t)]
    if starts != CASE_STARTS or sum('九宫盘面：' in l for l in lines) != 16:
        raise ValueError('Missing or reordered historical stories/charts')
    return lines


def quote(lines, start, end):
    return ''.join(lines[start-1:end]).rstrip('\r\n')


def build_artifacts(raw: bytes):
    lines=source_lines(raw)
    curated={'source_sha256':SOURCE_SHA,'source_byte_count':len(raw),'source_line_count':len(lines),
             'chapter_title':'经营求财预测','chapter_key_suggestion':'business-finance',
             'printed_chapter_number':None,'groups':[],'quality_issues':[],
             'worked_examples':[]}
    for n,(left,right,title,category) in enumerate(SECTIONS):
        rows=[]
        for line_no in range(left,right+1):
            if lines[line_no-1].strip():
                rows.append({'key':f'business-section{n:02d}-line{line_no}',
                             'source_lines':[line_no,line_no],
                             'source_quote':quote(lines,line_no,line_no),
                             'applicability_status':'reference_only',
                             'automatic_role_binding':False,
                             'automatic_prediction':False})
        curated['groups'].append({'key':f'business-section-{n:02d}',
            'title':title,'category':category,'line_start':left,'line_end':right,
            'attribution':'《神奇之门》本节叙述者',
            'summary':'保留完整来源语境及具体条件；不能用语义相似度激活专业规则。',
            'concepts':[title],
            'dataset':{'key':f'business-section-{n:02d}-source-reference','rows':rows}})
    case_ends=[x-1 for x in CASE_STARTS[1:]]+[len(lines)]
    allcases=[]
    for idx,(start,end) in enumerate(zip(CASE_STARTS,case_ends),1):
        title=lines[start-1].strip()
        curated['groups'].append({'key':f'business-case-{idx:02d}-whole',
            'title':title,'category':'commentary','line_start':start,'line_end':end,
            'attribution':'保留叙述者、具体预测者、后来反馈与按语的独立归属',
            'summary':'完整历史故事；仅有原书已提供的盘；不把事后解释变成事前输入。',
            'concepts':['经营求财预测',title],'dataset':None})
        # Case 12 has forecasts/observations across distinct date-hour slots.
        cuts=[start,1054,1119,1180,1236,1248,end+1] if idx==12 else [start,end+1]
        if idx==12:
            # The introductory letter contains explicit later outcomes, so it is
            # retained as a separate unknown-phase event, not forecast input.
            event_ranges=list(zip(cuts[:-1],cuts[1:]))
        else:
            event_ranges=[(start,end+1)]
        events=[]
        for event_num,(lo,stop) in enumerate(event_ranges):
            charts=[]; occupied=set(); chart_start_indices=[]
            for n in range(lo,stop):
                if lines[n-1].strip()=='奇门格局：':
                    header=next((k for k in range(n+1,stop) if lines[k-1].strip()=='宫位      八神    门位       星位'),None)
                    if header is None or header+9>=stop:
                        raise ValueError(f'Incomplete nine-palace chart at {n}')
                    chart_end=header+9
                    cells=[lines[k-1].strip().split() for k in range(header+1,chart_end+1)]
                    if len(cells)!=9 or any(len(c)!=4 for c in cells):
                        raise ValueError('Original four-column chart missing rows')
                    if [c[0] for c in cells]!=['巽四宫','离九宫','坤二宫','震三宫','中五宫','兑七宫','艮八宫','坎一宫','乾六宫']:
                        raise ValueError('Original palace ordering changed')
                    metadata={}
                    for k in range(n+1,header):
                        if '：' in lines[k-1]:
                            a,b=lines[k-1].strip().split('：',1)
                            if a in ('起局时间','年干支','月干支','日干支','时干支','旬首',
                                  '遁法','局数','值符','值符落宫','值使','值使落宫','日空亡','时空亡'):
                                metadata[a]=b
                    key=f'business-{idx:02d}-event{event_num}-chart{len(charts)+1}'
                    charts.append({'chart_key':key,'source_lines':[n,chart_end],
                        'casting_method':None,'method_version':None,
                        'source_or_engine':'original','validation_status':'original_unparsed',
                        'input_datetime':None,'timezone':None,'location':None,
                        'payload':{'chart_role':'source_original_nine_palace_table',
                            'metadata_as_written':metadata,
                            'row_cells_as_written':cells,
                            'chart_text_as_written':quote(lines,n,chart_end),
                            'source_sha256':SOURCE_SHA,
                            'original_chart_modified':False,'engine_verified':False,
                            'independent_gold_checked':False}})
                    occupied.update(range(n,chart_end+1))
                    chart_start_indices.append(n)
            records=[]
            paragraph=[]
            def emit():
                nonlocal paragraph
                if not paragraph:return
                a,b=paragraph[0],paragraph[-1];t=quote(lines,a,b)
                # The first-forecast view is deliberately narrower than the
                # narrative: analysis, charts, results and hindsight are withheld.
                safe_ends={1:175,2:239,3:317,4:407,5:487,6:543,
                           7:600,8:690,9:796,10:904,11:984,12:0,13:1262,14:1312}
                pre=(event_num==0 and b<=safe_ends[idx] and
                     not any(w in t for w in ('结果是','后来验证','事实证明','实际被抽','后经验证')))
                phase='pre_prediction' if pre else 'unknown'
                kind='dialogue' if ('“' in t or '”' in t) else 'author_reasoning'
                # Date-tagged reported outcomes are always post-feedback.
                if t.startswith(('结果：','后来验证','后经验证','结果是','事实是','实际被抽','翌年立春后')) or (
                    idx in (1,2,3,4,5,6,7,8,9,10,11,13,14) and a in (229,231,295,301,303,305,307,391,393,395,473,475,477,533,588,590,606,610,612,614,616,724,726,728,806,824,826,828,830,922,924,930,988,1305,1323)):
                    phase='post_feedback';kind='outcome' if ('结果' in t or '验证' in t or t.startswith('翌年')) else 'feedback'
                # Printed later analysis is not promoted to an author-time input.
                prediction_starts={1:{227},2:{291,293},3:{363,373,383,387},
                    4:{469},5:{531},6:{586},7:{602},8:{692,712,720},
                    9:{814,816,818,820},10:{906,920},11:{986},
                    12:set(),13:set(),14:{1319}}
                if a in prediction_starts[idx]:kind='prediction';phase='prediction'
                record={'record_key':f'business-{idx:02d}-e{event_num}-record{len(records):03d}',
                    'sequence':len(records),'source_lines':[a,b],'text':t,
                    'kind':kind,'knowledge_phase':phase,
                    'explicitness':'author_explicit',
                    'payload':{'source_stage_policy':'source-stage-v1',
                        'attribution_scope':'quoted source; no inferred reasoning',
                        'pre_prediction_release_allowed':pre}}
                # Source chart IDs can link explanation to the correct event,
                # including when book prints the chart after an outcome.
                if charts and not pre:record['chart_key']=charts[0]['chart_key']
                records.append(record);paragraph=[]
            for n in range(lo,stop):
                if n in occupied or not lines[n-1].strip():emit();continue
                paragraph.append(n)
            emit()
            if not records:raise ValueError('Empty event narrative')
            events.append({'event_key':f'business-{idx:02d}-event{event_num}',
                'title':title+(f'：来源时段{event_num}' if idx==12 else ''),
                'background':{'source_chapter':'经营求财预测',
                    'case_title_as_written':title,
                    'inquiry_type_as_written':title.split('：',1)[-1],
                    'multi_event_note':'实例十二同一抽奖故事，按时辰/日期分别记录；后两天没有原盘' if idx==12 else None,
                    'original_outcome_not_independently_verified_by_system':True},
                'chronology_status':'unknown',
                'prediction_input_policy':{'mode':'first_forecast_only_conservative',
                    'unrestricted_background_withheld':True,
                    'unknown_explanations_withheld':True,
                    'full_source_and_feedback_withheld':True},
                'charts':charts,'records':records,'evidence_links':[
                    {'record_key':r['record_key'],'source_lines':r['source_lines'],
                     'relation':'explicit_source_step','chart_key':r.get('chart_key')}
                    for r in records if r['kind'] in ('prediction','author_reasoning','timing') and r.get('chart_key')]})
        allcases.append({'case_key':f'business-finance-case-{idx:02d}',
            'title':title,'completeness':'confirmed_complete',
            'source_ranges':[[start,end]],
            'family':{'family_key':f'shenqi-business-case-{idx:02d}-first-edition',
                'description':f'{title}；单一完整历史故事，所有事件和原盘共享家族，不与相同企业的其他独立问测混作一次。'},
            'events':events})
    counts={'cases':len(allcases),'events':sum(len(c['events']) for c in allcases),
            'charts':sum(len(e['charts']) for c in allcases for e in c['events']),
            'records':sum(len(e['records']) for c in allcases for e in c['events'])}
    if (counts['cases'],counts['events'],counts['charts'])!=(14,19,16):
        raise ValueError(f'Case/event/chart integrity failed: {counts}')
    cases={'source_sha256':SOURCE_SHA,'temporal_payload_contract':'source-stage-v1',
        'source_acceptance':'user_attestation',
        'cases':allcases,'expected_counts':counts}
    candidates=[]
    for n,(at,scope,subtype,symbols) in enumerate(CANDIDATE_LINES):
        line=quote(lines,at,at)
        candidates.append({'key':f'business-{n:02d}-{scope}-{subtype}',
            'domain':'business_finance','scope':scope,
            'require':[{'field':'domain','op':'eq','value':'business_finance'},
                       {'field':'analysis_context','op':'eq','value':scope},
                       {'field':'method_subtype','op':'eq','value':subtype}],
            'exclude':[],'method_choice':{'status':'explicit_choice_required',
                                          'method_id':f'shenqi_business_{scope}_{subtype}_v1'},
            'source_lines':[at],'source_quote':line,'exceptions':[],
            'unique':False,'notes':['仅为来源候选，明确条件与不同口径，不可自动正式绑定。'],
            'unknown_policy':'conditional_never_true_by_default',
            'selection_scope':'symbolic_source_condition_match_only',
            'formal_role_activation_allowed':False,'professional_prediction_completed':False,
            'reference_only':True,
            'role_binding':{'symbols':symbols,'semantic_role':subtype,
                            'binding_kind':'source_candidate','automatic_activation':False,
                            'uniqueness':'not_claimed'}})
    rules={'schema_version':'source_selection_candidates_v1','title':'经营求财预测',
        'source_sha256':SOURCE_SHA,'source_byte_count':len(raw),'source_line_count':len(lines),
        'candidate_count':len(candidates),'candidate_record_count':len(candidates),
        'candidates':candidates}
    return curated,cases,rules,counts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=SOURCE_FILE)
    p.add_argument('--db',type=Path,default=ROOT/'data/qimenllm.sqlite3')
    p.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw_books')
    p.add_argument('--local-only',action='store_true')
    args=p.parse_args()
    raw=args.source.read_bytes();curated,cases,rules,counts=build_artifacts(raw)
    DATA.mkdir(parents=True,exist_ok=True)
    for kind,payload in [('curated',curated),('cases',cases),('rule_candidates',rules)]:
        target=DATA/f'business_{kind}.json'
        canonical=json.dumps(payload,ensure_ascii=False,indent=2)+'\n'
        if target.exists() and target.read_text(encoding='utf-8')!=canonical:
            raise ValueError(f'Existing reviewed artifact changed: {target}')
        target.write_text(canonical,encoding='utf-8')
    imported=import_chapter(args.db,args.raw_dir,raw,book_key='shenqi-user-text-v1',
        book_title='神奇之门',chapter_key='business-finance',chapter_title='经营求财预测',
        sequence=12,origin='user-upload:经营求财预测_完整原文.txt; sha256:'+SOURCE_SHA)
    profile_id='shenqi_business_finance_reference_v1'
    profile={'compiler_version':'shenqi-business-finance-reference-v1',
        'method_id':profile_id,'methods':{profile_id:{'kind':'contextual_source_reading',
            'professional_role_binding':False,'compiled_datasets':[]}},
        'compiled_datasets':frozenset(),'row_requirements':{}}
    result={'source':imported,'curation':install_curated(args.db,imported['revision_id'],curated,profile=profile),
            'cases':import_cases(args.db,imported['revision_id'],cases),
            'candidates':install_candidates(args.db,imported['revision_id'],rules),
            'input_counts':counts}
    if args.local_only:
        result['github_sync']={'status':'pending','reason':'Staged validation before GitHub integration'}
    else:
        try:result['github_sync']=sync_github(ROOT,args.db,args.raw_dir,
            'Ingest confirmed business-finance chapter and 14 complete cases')
        except (SyncError,ValueError) as e:
            result['github_sync']={'status':'pending','reason':str(e)}
            print(json.dumps(result,ensure_ascii=False,indent=2));return 2
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
