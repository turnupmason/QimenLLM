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
