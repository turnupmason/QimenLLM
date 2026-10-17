"""Source-limited comparison scopes and timing examples; never an event forecast."""
from .judgment_facts import JudgmentFactsCalculator
from .foundations import NotCovered
from ..knowledge.application_overview import METHOD


class ApplicationFactsCalculator(JudgmentFactsCalculator):
    METHOD_IDS=JudgmentFactsCalculator.METHOD_IDS+(METHOD,)
    INTEGER_ARGS=JudgmentFactsCalculator.INTEGER_ARGS|{'first_palace','second_palace'}
    OPERATIONS={
        'inner_outer':{'dun','palace'},
        'horizontal_palace_relation':{'first_palace','second_palace'},
        'vertical_symbol_relation':{'kind','name','palace'},
        'timing_chief_example':{'xun_head','palace','trigger'},
    }

    def _inner_outer(self,dun,palace):
        _,label=self._direction(dun); self._palace(palace)
        rows=[r for r in self._rows('inner_outer_palaces') if r['dun']==label and r['palace']==palace]
        if len(rows)!=1: raise NotCovered('Central palace classification not supplied; no hosting inferred')
        return {**rows[0],'exact_distance':None,'exact_duration':None,'prediction':None}

    def _palace_element(self,palace):
        self._palace(palace)
        values={r['palace_element'] for r in self._rows('door_pressure_pairs') if r['palace']==palace}
        if len(values)!=1: raise NotCovered('No unique supplied palace element; center not inferred')
        return next(iter(values))

    def _horizontal_palace_relation(self,first_palace,second_palace):
        self._one('comparison_scopes','axis','horizontal')
        first=self._palace_element(first_palace); second=self._palace_element(second_palace)
        return {'first_palace':first_palace,'second_palace':second_palace,
                'first_palace_element':first,'second_palace_element':second,
                'relation_kind':self._relationship(first,second),
                'basis':'actual_landing_palace_elements','fixed_symbol_elements_used':False,
                'role_bindings':[],'prediction':None}

    def _vertical_symbol_relation(self,kind,name,palace):
        self._one('comparison_scopes','axis','vertical')
        if kind=='deity':
            self._named('deities',name)
            self._one('comparison_scopes','axis','deity_vertical_exclusion')
            return {'status':'reference_only','kind':kind,'name':name,'palace':self._palace(palace),
                    'relation_kind':None,'reason':'source normally excludes deity fixed-element versus palace',
                    'prediction':None}
        if kind not in ('star','door'): raise ValueError('Explicit star, door or deity kind required')
        attribute=self._named('stars' if kind=='star' else 'doors',name)
        element=self._palace_element(palace)
        return {'kind':kind,'name':attribute['name'],'symbol_element':attribute['element'],
                'palace':palace,'palace_element':element,
                'relation_kind':self._relationship(attribute['element'],element),
                'basis':'fixed_symbol_element_within_given_landing_palace','prediction':None}

    def _timing_chief_example(self,xun_head,palace,trigger):
        self._palace(palace)
        if trigger not in ('冲','刑'): raise ValueError('Only explicitly supplied clash or punishment examples')
        rows=[r for r in self._rows('timing_chief_examples') if
              (r['xun_head'],r['palace'],r['trigger'])==(xun_head,palace,trigger)]
        if len(rows)!=1: raise NotCovered('No exact source example; no generic timing extrapolation')
        return {**rows[0],'calendar_date':None,'method_scope':'exact_source_example_only',
                'timing_prediction_completed':False,'prediction':None}
