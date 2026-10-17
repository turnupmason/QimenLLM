"""Install context-complete, reviewed source annotations without rewriting originals."""
from __future__ import annotations

import json
from pathlib import Path
from .db import connect, digest
from .importer import add_annotations, canonical, new_version


COMPILER_VERSION='shenqi-chapter01-v1'
COMPILED_DATASETS=frozenset({
    'stem_attributes','hidden_jia','earth_sequence','sexagenary_xun','term_bureaus',
    'day_yuan','stars','doors','deities','operational_hour_halves','explicit_element_relations',
    'trigram_classifications',
})
METHODS={
    'shenqi_ch1_foundation_v1':{'kind':'provided_chapter_foundation','calendar_engine':False},
    'shenqi_ch1_chaibu_v1':{'kind':'casting_method','name':'拆补法','requires_known_term_and_day':True,
                           'boundary':'交节时辰；未提供完整公历转换与时区约定'},
    'shenqi_ch1_zhirun_reference_v1':{'kind':'reference_method','name':'置闰法','executable':False},
    'shenqi_ch1_maoshan_reference_v1':{'kind':'reference_method','name':'茅山法','executable':False},
    'shenqi_ch1_deity_follow_star_reference_v1':{'kind':'reference_method','name':'小值符随大值符','executable':False},
    'shenqi_ch1_deity_per_xun_reference_v1':{'kind':'reference_method','name':'地盘八神每旬移宫','executable':False},
}
ROW_REQUIREMENTS={
    'stem_attributes':(10,{'stem','polarity','element'}),
    'hidden_jia':(6,{'xun_head','instrument'}),
    'earth_sequence':(9,{'position','stem'}),
    'sexagenary_xun':(6,{'xun_head','ganzhi'}),
    'term_bureaus':(24,{'term','dun','upper','middle','lower','palace','trigram','direction'}),
    'day_yuan':(12,{'yuan','yuan_key','fu_head','days'}),
    'stars':(9,{'name','home_palace','element','aliases','direction'}),
    'doors':(8,{'name','home_palace','element','includes_central_palace'}),
    'deities':(8,{'name','element','element_basis','description_status'}),
    'operational_hour_halves':(2,{'half','stems'}),
    'explicit_element_relations':(3,{'source','relation','target'}),
    'trigram_classifications':(2,{'classification','yang','yin'}),
}


def install_curated(db: str | Path, revision_id: str, curated: dict, *, profile: dict | None = None) -> dict:
    # Explicit trusted compiler profiles isolate successive chapters without rewriting v1 data.
    profile=profile or {'compiler_version':COMPILER_VERSION,'method_id':'shenqi_ch1_foundation_v1',
                       'methods':METHODS,'compiled_datasets':COMPILED_DATASETS,'row_requirements':ROW_REQUIREMENTS}
    compiler_version=profile['compiler_version']; method_id=profile['method_id']
    methods=profile['methods']; compiled_datasets=profile['compiled_datasets']
    row_requirements=profile['row_requirements']
    if method_id not in methods: raise ValueError('Compiler profile method missing')
    canonical(curated)  # validate serialization before any data write
    with connect(db) as conn:
        record=conn.execute('''SELECT r.*,d.content,d.sha256 FROM chapter_revisions r
            JOIN raw_documents d USING(document_id) WHERE revision_id=?''',(revision_id,)).fetchone()
        if record is None: raise ValueError('Unknown source revision')
        raw=record['content']
        if digest(raw)!=curated['source_sha256']: raise ValueError('Curated source hash mismatch')
        full_source=conn.execute('''SELECT source_id FROM source_spans WHERE revision_id=?
            AND byte_start=0 AND byte_end=? AND locator='full chapter' ''',(revision_id,len(raw))).fetchone()[0]
        for registered_method in methods:
            existing=conn.execute('SELECT source_id,conventions_json FROM methods WHERE method_id=?',(registered_method,)).fetchone()
            if existing is not None and existing[0]!=full_source:
                raise ValueError('A different source revision requires an explicit method/compiler version')
            if existing is not None and existing[1]!=canonical(methods[registered_method]):
                raise ValueError('Changed method conventions require an explicit version')
    lines=raw.splitlines(keepends=True)
    starts=[0]
    for line in lines: starts.append(starts[-1]+len(line))
    coverage=set(); keys=set(); datasets=set(); annotations=[]
    for group in curated['groups']:
        start,end=group['line_start'],group['line_end']
        if not 1<=start<=end<=len(lines): raise ValueError('Invalid context line range')
        if group['key'] in keys: raise ValueError('Duplicate context group')
        keys.add(group['key']); coverage.update(range(start,end+1))
        dataset=group.get('dataset')
        if dataset:
            if dataset['key'] in datasets: raise ValueError('Duplicate dataset')
            datasets.add(dataset['key'])
        annotations.append({'category':group['category'],'byte_start':starts[start-1],
            'byte_end':starts[end],'locator':f"{group['title']}；输入行 {start}–{end}",
            'payload':{'kind':'context_group',**group}})
    required={i for i,line in enumerate(lines,1) if line.strip()}
    if not required<=coverage: raise ValueError('Uncovered source paragraphs')
    for group in curated['groups']:
        if not isinstance(group.get('concepts',[]),list) or any(not isinstance(c,str) for c in group.get('concepts',[])):
            raise ValueError('Concept index requires string names')
        dataset=group.get('dataset')
        if not dataset: continue
        if any(key not in keys for key in dataset.get('supporting_group_keys',[])):
            raise ValueError('Unknown supporting context group')
        if dataset['key'] in row_requirements:
            count,fields=row_requirements[dataset['key']]
            rows=dataset.get('rows')
            if not isinstance(rows,list) or len(rows)!=count or any(not isinstance(r,dict) or not fields<=set(r) for r in rows):
                raise ValueError('Incomplete compiled dataset: '+dataset['key'])
            if dataset['key']=='earth_sequence' and not {'center_original_palace','center_host_palace'}<=set(dataset.get('conventions',{})):
                raise ValueError('Earth hosting convention source required')
    for collection,kind,category in ((curated.get('quality_issues',[]),'source_quality_issue','commentary'),
                                      (curated.get('worked_examples',[]),'worked_example','casting')):
        for entry in collection:
            start,end=entry['line_start'],entry['line_end']
            if not 1<=start<=end<=len(lines): raise ValueError('Invalid audit/example context')
            annotations.append({'category':category,'byte_start':starts[start-1],'byte_end':starts[end],
                'locator':f"{kind} {entry['key']}；输入行 {start}–{end}",
                'payload':{'kind':kind,'record':entry}})
    imported=add_annotations(db,revision_id,annotations)
    pending=[]
    with connect(db) as conn:
        conn.execute('BEGIN IMMEDIATE')
        sources={}
        for group,entry in zip(curated['groups'],annotations):
            span=conn.execute('''SELECT source_id FROM source_spans WHERE revision_id=? AND byte_start=?
                AND byte_end=? AND locator=?''',(revision_id,entry['byte_start'],entry['byte_end'],entry['locator'])).fetchone()[0]
            sources[group['key']]=span
        for group in curated['groups']:
            span=sources[group['key']]
            dataset=group.get('dataset')
            if dataset and dataset['key'] in compiled_datasets:
                payload={'kind':'compiled_dataset','compiler_version':compiler_version,
                         'source_sha256':curated['source_sha256'],'dataset':dataset,
                         'supporting_source_ids':[sources[key] for key in dataset.get('supporting_group_keys',[])],
                         'validation_scope':'provided_text_only','author_attribution':group['attribution']}
                item_id='compiled-'+digest(canonical([revision_id,payload]).encode())
                if not conn.execute('SELECT 1 FROM knowledge_items WHERE item_id=?',(item_id,)).fetchone():
                    pending.append((item_id,group['category'],span,payload))
        new_methods=[m for m in methods if not conn.execute('SELECT 1 FROM methods WHERE method_id=?',(m,)).fetchone()]
        concept_entries=[]
        for group in curated['groups']:
            for name in group.get('concepts',[]):
                concept_id='concept-'+digest(canonical([revision_id,group['key'],name]).encode())
                if not conn.execute('SELECT 1 FROM concepts WHERE concept_id=?',(concept_id,)).fetchone():
                    concept_entries.append((concept_id,name,group['category'],sources[group['key']],
                                            '上下文索引：'+group['summary']))
        version=None
        if pending or new_methods or concept_entries:
            version=new_version(conn,'compile_source_foundations',{'source_sha256':curated['source_sha256'],
                'compiler':compiler_version,'datasets':[p[3]['dataset']['key'] for p in pending],
                'methods':new_methods,'concept_entries':len(concept_entries)})
        for method in new_methods:
            conn.execute('INSERT INTO methods VALUES (?,?,?,?,?)',
                         (method,method,'1',full_source,canonical(methods[method])))
        for row in concept_entries: conn.execute('INSERT INTO concepts VALUES (?,?,?,?,?)',row)
        for item_id,category,span,payload in pending:
            conn.execute('''INSERT INTO knowledge_items(item_id,category,source_id,method_id,payload_json,
                structured,applicability_confirmed,compiled,reference_only,data_version)
                VALUES (?,?,?,?,?,1,1,1,0,?)''',
                         (item_id,category,span,method_id,canonical(payload),version))
        current_version=conn.execute('SELECT version_id FROM data_versions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
    return {'structured_records_added':imported['added'],'context_groups':len(curated['groups']),
            'quality_records':len(curated.get('quality_issues',[])),
            'worked_examples':len(curated.get('worked_examples',[])),
            'compiled_families_added':len(pending),
            'concept_entries_added':len(concept_entries),'methods_added':len(new_methods),
            'data_version':current_version,
            'source_acceptance':'tracked_separately','professional_prediction_available':False}
