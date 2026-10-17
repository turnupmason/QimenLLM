"""Source-scoped symbolic conditions, not an automated divination verdict."""
from __future__ import annotations

from .foundations import NotCovered
from .paper import PaperCalculator


class JudgmentFactsCalculator(PaperCalculator):
    METHOD_IDS=PaperCalculator.METHOD_IDS+('shenqi_ch4_facts_v1','shenqi_ch5_facts_v1')
    OPERATIONS={
        'branch_attribute':{'branch'},'stem_life_stage':{'stem','stage'},
        'stem_clash':{'first','second'},'branch_group':{'relation','branches'},
        'sourced_element_relation':{'source','target'},
        'door_season_strength':{'door','season'},'door_source_profile':{'door','palace'},
        'star_month_strength':{'star','month_branch','method'},
        'door_palace_relation':{'door','palace'},
        'instrument_punishment_pair':{'instrument','palace'},
        'wonder_tomb':{'stem','palace','convention'},
        'wonder_restraint_palace':{'stem','palace'},
        'wonder_restraint_stem':{'heaven_stem','earth_stem'},
        'five_missed_hour':{'day_stem','hour_ganzhi'},
        'heavenly_manifest_hour':{'day_stem','hour_ganzhi'},
    }

    def _branch_attribute(self, branch): return self._one('branch_attributes','branch',branch)

    def _stem_life_stage(self, stem, stage):
        row=self._one('stem_life_stages','stem',stem)
        if stage not in row['stages']: raise NotCovered('Only five life stages are explicitly supplied')
        return {'stem':stem,'stage':stage,'branch':row['stages'][stage],
                'scope':'source_stem_life_stage_not_door_tomb_or_general_element_tomb'}

    def _stem_clash(self, first, second):
        self._stem_attribute(first); self._stem_attribute(second)
        rows=self._rows('stem_clashes')
        matched=[r for r in rows if len(r['stems'])==2 and set(r['stems'])=={first,second} and first!=second]
        return {'first':first,'second':second,'listed_pair_match':bool(matched),'relation':'冲',
                'scope':'four_listed_symmetric_stem_pairs','prediction':None}

    def _branch_group(self, relation, branches):
        given=list(branches)
        if len(given) not in (2,3): raise ValueError('Use two or three branch characters')
        for b in given: self._branch_attribute(b)
        rows=self._rows('branch_relations')
        if relation not in {r['relation'] for r in rows}: raise NotCovered('Unprovided branch relation')
        matched=[r for r in rows if r['relation']==relation and
                 (r['branches']==given if r['directed'] else sorted(r['branches'])==sorted(given))]
        return {'relation':relation,'branches':given,'listed_group_match':bool(matched),
                'source_records':matched,'actual_transformation_applied':False,'prediction':None,
                'scope':'chapter_four_graph_not_chapter_five_instrument_punishment_derivation'}

    def _edges(self):
        return self._rows('element_edges_ch4')+self._rows('element_edges_ch5')

    def _relationship(self, first, second):
        elements={r['element'] for r in self._rows('branch_attributes')}
        if first not in elements or second not in elements: raise ValueError('Unknown element symbol')
        if first==second: return 'same_element'
        edges={(r['source'],r['relation'],r['target']) for r in self._edges()}
        kinds=[]
        for rel,kind,inverse in (('生','generates','generated_by'),('克','controls','controlled_by')):
            if (first,rel,second) in edges: kinds.append(kind)
            if (second,rel,first) in edges: kinds.append(inverse)
        if len(kinds)!=1: raise NotCovered('No unique directed relationship in supplied sources')
        return kinds[0]

    def _sourced_element_relation(self, source, target):
        return {'source':source,'target':target,'relation_kind':self._relationship(source,target),
                'scope':'directed_source_graph','prediction':None}

    @staticmethod
    def _season_key(value):
        # Representation aliases only; not a calendar or priority rule for special months.
        aliases={'春季':'春','夏季':'夏','秋季':'秋','冬季':'冬',
                 '四季末':'四季末月','四季月':'四季末月'}
        return aliases.get(value,value)

    def _door_season_strength(self, door, season):
        row=self._one('door_seasonal_strength','door',door)
        key=self._season_key(season)
        if key not in {'春','夏','秋','冬','四季末月'}: raise ValueError('Explicit season label required')
        states=[{'state':s,'source_season':v} for s,v in row['states'].items()
                if s!='特别' and v is not None and self._season_key(v)==key]
        if not states: raise NotCovered('Seasonal state omitted in this door source; not filled from a generic element table')
        return {'door':door,'season':key,'states':states,
                'special_months_as_written':row['states'].get('特别'),
                'special_month_priority':'not_assumed','missing_states':[k for k,v in row['states'].items() if v is None],
                'scope':'general_season_sentence_not_a_single_month_override','prediction':None}

    def _door_source_profile(self, door, palace):
        self._palace(palace); row=self._one('door_palace_profiles','door',door)
        matches=[r for r in row['profiles'] if palace in r['target_palaces']]
        if not matches: raise NotCovered('No explicit source label for this door and palace')
        return {'door':door,'palace':palace,'source_profiles':matches,
                'applicability_status':'reference_only','prediction':None}

    def _star_month_strength(self, star, month_branch, method):
        if method!='shenqi_ch4_star_month_v1': raise NotCovered('Select the author month-build method explicitly')
        row=self._named('stars',star); month=self._branch_attribute(month_branch)
        kind=self._relationship(row['element'],month['element'])
        rule_key={'generates':'star_generates_month','same_element':'same_element',
                  'generated_by':'month_generates_star','controls':'star_controls_month',
                  'controlled_by':'month_controls_star'}[kind]
        rule=self._one('star_strength_rules','relation',rule_key)
        return {'star':row['name'],'star_element':row['element'],'month_branch':month_branch,
                'month_element':month['element'],'state':rule['state'],'relation':rule_key,'method':method,
                'basis':'given_month_build','landing_palace_used_as_month':False,'prediction':None}

    def _door_palace_relation(self, door, palace):
        self._palace(palace); attribute=self._named('doors',door)
        supported={r['palace_element'] for r in self._rows('door_pressure_pairs') if r['palace']==palace}
        if len(supported)!=1: raise NotCovered('No unique explicit palace element; center not inferred from its star')
        element=next(iter(supported)); kind=self._relationship(attribute['element'],element)
        name='same_element'
        if kind!='same_element':
            subject='door' if kind in ('generates','controls') else 'palace'
            predicate='generates' if kind in ('generates','generated_by') else 'controls'
            rows=[r for r in self._rows('door_palace_relations') if r['subject']==subject and r['relation']==predicate]
            if len(rows)!=1: raise NotCovered('Ambiguous door/palace relation terminology')
            name=rows[0]['name']
        return {'door':attribute['name'],'door_element':attribute['element'],'palace':palace,
                'palace_element':element,'relation_kind':kind,'classification':name,
                'scope':'symbolic_direction_only','prediction':None}

    def _instrument_punishment_pair(self, instrument, palace):
        self._palace(palace); row=self._one('six_instrument_punishments','heaven_stem',instrument)
        return {'instrument':instrument,'palace':palace,'listed_palace':row['palace'],
                'listed_pair_match':palace==row['palace'],'professional_applicability':'reference_only',
                'unresolved_scope':'source alternates current chief and even-if-chief wording',
                'basis':'explicit_chapter_five_pairs_not_derived_from_chapter_four_branch_graph','prediction':None}

    def _wonder_tomb(self, stem, palace, convention):
        self._palace(palace)
        if convention not in ('stem_life_stage','general_wood'):
            raise NotCovered('Choose one of the two explicitly separated source rationales')
        rows=[r for r in self._rows('wonder_tomb_palaces') if r['heaven_stem']==stem and r['convention']==convention]
        if not rows: raise NotCovered('This source convention does not supply a tomb for that wonder')
        return {'stem':stem,'palace':palace,'convention':convention,
                'listed_pair_match':any(r['palace']==palace for r in rows),
                'source_palaces':[r['palace'] for r in rows],'prediction':None}

    def _wonder_restraint_palace(self, stem, palace):
        self._palace(palace); self._stem_attribute(stem)
        rows=[r for r in self._rows('wonder_restraints') if r['condition_type']=='palace' and r['heaven_stem']==stem]
        if not rows: raise NotCovered('Wonder palace-restraint table does not cover that stem')
        return {'stem':stem,'palace':palace,'listed_pair_match':any(r['palace']==palace for r in rows),
                'earth_stem_condition_evaluated':False,'prediction':None}

    def _wonder_restraint_stem(self, heaven_stem, earth_stem):
        self._stem_attribute(heaven_stem); self._stem_attribute(earth_stem)
        rows=[r for r in self._rows('wonder_restraints') if r['condition_type']=='earth_stem' and r['heaven_stem']==heaven_stem]
        if not rows: raise NotCovered('Wonder earth-stem restraint table does not cover that stem')
        return {'heaven_stem':heaven_stem,'earth_stem':earth_stem,
                'listed_pair_match':any(r['earth_stem']==earth_stem for r in rows),
                'palace_condition_evaluated':False,'prediction':None}

    def _given_hour_valid(self, day_stem, hour_ganzhi):
        self._xun(hour_ganzhi)
        value=self._hour_ganzhi(day_stem,hour_ganzhi[1])
        if value['hour_ganzhi']!=hour_ganzhi: raise ValueError('Given hour pillar conflicts with the source day-to-hour table')

    def _five_missed_hour(self, day_stem, hour_ganzhi):
        self._given_hour_valid(day_stem,hour_ganzhi)
        row=self._one('five_missed_hour_pairs','day_stem',day_stem)
        return {'day_stem':day_stem,'hour_ganzhi':hour_ganzhi,
                'listed_hour_match':row['hour_ganzhi']==hour_ganzhi,'source_hour':row['hour_ganzhi'],
                'scope':'source_time_condition_not_an_outcome_verdict','prediction':None}

    def _heavenly_manifest_hour(self, day_stem, hour_ganzhi):
        self._given_hour_valid(day_stem,hour_ganzhi)
        rows=[r for r in self._rows('heavenly_manifest_hours') if r['day_stem']==day_stem]
        return {'day_stem':day_stem,'hour_ganzhi':hour_ganzhi,
                'listed_hour_match':any(r['hour_ganzhi']==hour_ganzhi for r in rows),
                'automatic_fuyin_judgment_override':False,'prediction':None}
