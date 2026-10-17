from ..retrieval.repository import KnowledgeRepository


class LearningService:
    def __init__(self, knowledge: KnowledgeRepository): self.knowledge = knowledge

    def learn(self, term: str) -> dict:
        hits = self.knowledge.search(term)
        return {'status':'sources_found' if hits else 'awaiting_sources',
                'original_sources':hits, 'system_explanation':None,
                'author_judgment':None, 'model_analysis':None,
                'message':'仅返回研究用原文；课程与模型讲解尚未实现。'}
