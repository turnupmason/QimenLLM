"""Trusted local whole-book research via QimenService.ask, never production bypass."""
from dataclasses import dataclass
import hashlib,json
from pathlib import Path
from ..contracts import GenerationError,ModelUnavailable
from ..knowledge.db import connect
from .method import check_output,score_task

def digest(raw):return hashlib.sha256(raw).hexdigest()

@dataclass(frozen=True)
class BookMethodRequest:
    manifest_path:str
    manifest_sha256:str
    data_dir:str
    split:str
    task_id:str
    seen_training_diagnostic:bool=False
    sealed_final_test:bool=False

def load_task(request,db):
    raw=Path(request.manifest_path).read_bytes()
    if digest(raw)!=request.manifest_sha256:raise ValueError('Frozen curriculum changed')
    release=json.loads(raw)
    if release.get('release_id')!='shenqi-book-method-curriculum-v1' or release.get('frozen') is not True or release.get('scope')!='reviewed_book_method_curriculum':raise ValueError('Unsupported curriculum')
    if request.split not in ('train','validation','development','test'):raise ValueError('Unknown split')
    if request.split=='train' and not request.seen_training_diagnostic:raise ValueError('Train can only be explicitly seen diagnostic')
    if request.split=='test' and not request.sealed_final_test:raise ValueError('Test remains sealed during iteration')
    data=(Path(request.data_dir)/(request.split+'.jsonl')).read_bytes()
    if digest(data)!=release['files'][request.split+'.jsonl']['sha256']:raise ValueError('Frozen curriculum tasks changed')
    rows=[json.loads(line) for line in data.splitlines()]
    if any(r['split']!=request.split or release['family_assignments'].get(r['family_id'])!=request.split for r in rows):raise ValueError('Family ownership changed')
    if any(r['family_id'] in release['excluded_training_families'] for r in rows):raise ValueError('Quarantined duplicate present')
    matches=[t for t in rows if t['task_id']==request.task_id]
    if len(matches)!=1:raise ValueError('Task missing or duplicated')
    task=matches[0];body={k:v for k,v in task.items() if k!='sha256'}
    encoded=(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    if digest(encoded)!=task['sha256']:raise ValueError('Task digest changed')
    with connect(db) as con:
        version=con.execute('select version_id from data_versions order by rowid desc limit 1').fetchone()[0]
        if version!=release['source_data_version'] or task['source_data_version']!=version:raise ValueError('Source version changed')
        if task['event_id'] is not None:
            event=con.execute('select family_id from events where event_id=?',(task['event_id'],)).fetchone()
            if event is None or event['family_id']!=task['family_id'] or release['original_event_family_assignments'].get(task['family_id'])!=request.split:raise ValueError('Original event family differs')
        elif task['context_mode']!='reference_reading' or release['reference_document_groups'].get(task['family_id'])!='train':raise ValueError('Invalid knowledge group')
        for ref in task['input_sources']+task['supervision_sources']:
            source=con.execute('select d.content,d.sha256 from raw_documents d join chapter_revisions r using(document_id) where r.revision_id=?',(ref['revision_id'],)).fetchone()
            if source is None or digest(source['content'])!=ref['document_sha256']:raise ValueError('Document bytes changed')
            a,b=ref['byte_start'],ref['byte_end'];blob=source['content'][a:b]
            if not 0<=a<b<=len(source['content']) or digest(blob)!=ref['excerpt_sha256'] or blob.decode()!=ref['text']:raise ValueError('Source selector changed')
    return task

def check_book_output(output,payload):
    errors=check_output(output,payload)
    kind=payload['task_type']
    if any(not isinstance(s,str) or not s.strip() for s in output['uncertainties']):raise GenerationError('Invalid uncertainty list')
    if kind=='role_selection':
        bindings=output.get('bindings')
        if not isinstance(bindings,list) or not bindings or any(not isinstance(b,dict) or any(not isinstance(b.get(k),str) or not b[k].strip() for k in ('role','symbol','condition')) for b in bindings):raise GenerationError('Required conditional role bindings missing')
    if kind=='timing_analysis' and (not isinstance(output.get('methods'),list) or not output['methods'] or any(not isinstance(m,str) or not m.strip() for m in output['methods'])):raise GenerationError('Required timing methods missing')
    if kind=='feedback_continuation' and output.get('chart_action')!='reuse_original':errors.append('original_chart_reuse_missing')
    if kind=='chart_evidence':
        scope=payload.get('representation_scope')
        if scope=='partial_source_reading':
            facts=output.get('reported_facts');text=payload['references']['source']['text']
            if not isinstance(facts,list) or not facts or output.get('complete_nine_palace_chart') is not False:raise GenerationError('Partial source scope missing')
            if any(not isinstance(f,dict) or not isinstance(f.get('value'),str) or not f['value'] or f['value'] not in f.get('quote','') or f['quote'] not in text for f in facts):errors.append('partial_source_quote_mismatch')
        elif scope=='user_relayout_reading':
            cells=output.get('palaces_as_written')
            if output.get('representation')!='user_supplied_relayout_not_original_scan' or not isinstance(cells,list) or len(cells)!=9:raise GenerationError('Relayout representation missing')
            text=payload['references']['source']['text'];seen=set()
            for p in cells:
                if not isinstance(p,dict) or type(p.get('palace')) is not int or p['palace'] not in range(1,10) or p['palace'] in seen or not isinstance(p.get('source_cells_as_written'),list) or len(p['source_cells_as_written'])!=4:raise GenerationError('Malformed relayout cells')
                seen.add(p['palace'])
                if any(not isinstance(v,str) or v not in text for v in p['source_cells_as_written']):errors.append('relayout_cell_not_in_source')
        else:
            observations=output.get('observations')
            if not isinstance(observations,list) or not observations:raise GenerationError('Required literal observations missing')
            for f in observations:
                if type(f.get('palace')) is not int or f.get('field') not in ('heaven_stem','earth_stem','door','star','deity','heaven_prefix_marker','star_prefix_marker') or f.get('citation')!='chart':errors.append('literal_field_or_citation_invalid')
    return list(dict.fromkeys(errors))

def book_method_ask(service,inquiry,request):
    task=load_task(request,service.knowledge.db)
    if inquiry.text!=task['task_id'] or inquiry.context or inquiry.domain is not None:raise ValueError('Research inquiry only identifies task')
    messages=task['messages'][:2];payload=json.loads(messages[1]['content'])
    result={'status':'model_unavailable','scope':'whole_book_source_reviewed_research','professional_analysis_completed':False,'split':request.split,'context_mode':task['context_mode'],'seen_training_diagnostic':request.split=='train','forecast_evaluation_eligible':task['forecast_evaluation_eligible'],'payload_sha256':digest(json.dumps(messages,ensure_ascii=False,sort_keys=True).encode()),'author_method_accuracy':None,'reported_feedback_accuracy':None,'independent_real_world_accuracy':None}
    try:
        output,telemetry=service.model.generate_method(messages);result['telemetry']=telemetry
        errors=check_book_output(output,payload);result.update(status='method_generated' if not errors else 'method_evidence_error',output=output,evidence_errors=errors)
    except (ModelUnavailable,AttributeError):pass
    except GenerationError:result['status']='generation_error'
    return result
