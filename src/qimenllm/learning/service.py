from ..retrieval.repository import KnowledgeRepository


class LearningService:
    def __init__(self, knowledge: KnowledgeRepository): self.knowledge = knowledge

    def learn(self, term: str) -> dict:
        hits = self.knowledge.search(term)
        blocks=self.knowledge.context_groups(term)
        blocks=[{**block,'source':self.knowledge.source(block['source_id'])} for block in blocks]
        return {'status':'sources_found' if hits or blocks else 'awaiting_sources',
                'original_sources':hits,'knowledge_blocks':blocks,
                'system_explanation':[{'text':b['payload']['summary'],'source_id':b['source_id'],
                    'attribution':b['payload']['attribution'],'kind':'curated_explanation_not_original'} for b in blocks] or None,
                'author_judgment':None, 'model_analysis':None,
                'message':'按出处区分原文和人工结构化说明；模型讲解与完整课程尚未实现。'}

    def reference(self, family: str, filters: dict) -> dict:
        if not isinstance(family,str) or not family.strip() or not isinstance(filters,dict):
            raise ValueError('Reference family and filters object required')
        if any(not isinstance(k,str) or type(v) not in (str,int) for k,v in filters.items()):
            raise ValueError('Reference filters must contain string keys and scalar source values')
        records=self.knowledge.reference_dataset(family)
        entries=[]; sources={}
        for record in records:
            rows=record['payload']['dataset'].get('rows',[])
            available={key for row in rows for key in row}
            if set(filters)-available: raise ValueError('Unknown reference field')
            matches=[row for row in rows if all(type(row.get(k)) is type(v) and row.get(k)==v for k,v in filters.items())]
            if not matches: continue
            source_id=record['source_id']; sources[source_id]=self.knowledge.source(source_id)
            for row in matches:
                entries.append({'record':row,'source_id':source_id,'context_item_id':record['item_id'],
                    'author_attribution':record['payload']['attribution'],
                    'applicability_status':'reference_only'})
        return {'status':'sources_found' if entries else 'not_found','family':family,
                'entries':entries,'sources':sources,'total':len(entries),'truncated':False,
                'query_trace':{'operation':'reference_dataset','family':family,'context_records':len(records)},
                'mode':'source_reference_not_prediction','professional_analysis_completed':False,
                'role_bindings':[],'model_analysis':None,
                'message':'以下为有出处的传统条文及整理；条件、例外和盘层未明确处仍需保留，未形成问事结论。'}
