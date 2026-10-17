"""Chapter-two paper rotation with explicit symbolic inputs, not a calendar engine."""
from __future__ import annotations

from ..contracts import Chart
from ..knowledge.db import digest
from ..knowledge.importer import canonical
from .foundations import FoundationCalculator, NotCovered


PAPER_METHOD='shenqi_ch2_paper_v1'


class PaperCalculator(FoundationCalculator):
    METHOD_IDS=('shenqi_ch1_foundation_v1','shenqi_ch2_foundation_v1')
    INTEGER_ARGS=FoundationCalculator.INTEGER_ARGS|{'clock_hour','clock_minute'}
    OPERATIONS={
        'hour_branch':{'clock_hour','clock_minute'},
        'hour_ganzhi':{'day_stem','hour_branch'},
        'stem_combination':{'stem'},
        'palm_branch':{'branch'},'palm_palace':{'palace'},
        'documented_palace_element':{'palace'},
        'documented_element_relation':{'source','target'},
        'symbolic_chart':{'dun','bureau','hour_ganzhi','method'},
    }

    def _hour_branch(self, clock_hour, clock_minute):
        if type(clock_hour) is not int or not 0<=clock_hour<24:
            raise ValueError('clock_hour must be an integer 0..23')
        if type(clock_minute) is not int or not 0<=clock_minute<60:
            raise ValueError('clock_minute must be an integer 0..59')
        minute=clock_hour*60+clock_minute
        for row in self._rows('hour_windows'):
            start=row['start_hour']*60; end=row['end_hour']*60
            inside=(start<=minute<end) if start<end else (minute>=start or minute<end)
            if inside:
                return {'hour_branch':row['branch'],'clock_basis':'caller_supplied_clock_reading',
                        'day_assignment':'not_determined','timezone_conversion':False,
                        'boundary_convention':'start_inclusive_end_exclusive'}
        raise NotCovered('No source clock interval')

    def _hour_ganzhi(self, day_stem, hour_branch):
        self._one('hour_windows','branch',hour_branch)
        for row in self._rows('five_rat_hours'):
            if day_stem in row['day_stems']:
                matches=[h for h in row['hours'] if isinstance(h,str) and len(h)==2 and h[1]==hour_branch]
                if len(matches)!=1: raise ValueError('Incomplete source hour-pillar table')
                value=matches[0]
                xun=self._xun(value)
                return {'day_stem':day_stem,'hour_branch':hour_branch,'hour_ganzhi':value,
                        'xun_head':xun['xun_head'],'hidden_stem':xun['hidden_stem'],
                        'day_stem_is_caller_supplied':True,'midnight_day_convention':'not_inferred'}
        raise NotCovered('Day stem not provided in source five-rat table')

    def _stem_combination(self, stem):
        for row in self._rows('stem_combinations'):
            if stem in row['stems']:
                return {**row,'scope':'traditional_correspondence_only',
                        'actual_transformation_applied':False,'applicability_conditions':'not_provided'}
        raise NotCovered('Stem combination not provided')

    def _palm_branch(self, branch): return self._one('palm_branches','branch',branch)

    def _palm_palace(self, palace):
        self._palace(palace)
        return self._one('palm_palaces','palace',palace)

    def _documented_palace_element(self, palace):
        self._palace(palace)
        return self._one('explicit_palace_elements','palace',palace)

    def _documented_element_relation(self, source, target):
        rows=self._rows('explicit_element_relations')+self._rows('chapter_element_relations')
        found=[r for r in rows if r['source']==source and r['target']==target]
        if not found: raise NotCovered('Directed relationship not explicitly provided in these chapters')
        return {'source':source,'target':target,'relations':sorted({r['relation'] for r in found}),
                'unlisted_relationships':'unknown_not_false'}

    def _symbolic_chart(self, dun, bureau, hour_ganzhi, method):
        if method!=PAPER_METHOD:
            raise NotCovered('Select the supplied chapter-two paper method explicitly')
        convention=self._rows('rotation_conventions')[0]
        policies={'star_sequence_direction':'clockwise_both_duns','door_sequence_direction':'clockwise_both_duns',
            'deity_direction':'yang_clockwise_yin_anticlockwise','deity_anchor':'chief_star_layout_palace',
            'center_xun_door_policy':'host_door_count_from_original',
            'chief_star_center_target_policy':'retain_original_use_host_for_layout',
            'final_center_door_policy':'not_covered','center_star_policy':'follow_companion'}
        if any(convention.get(k)!=v for k,v in policies.items()):
            raise NotCovered('Source rotation conventions need an explicitly supported method version')
        ring=convention['clockwise_palaces']
        if len(ring)!=8 or len(set(ring))!=8 or set(ring)!={1,2,3,4,6,7,8,9}:
            raise ValueError('Incomplete source outer-palace ring')
        center=convention['center_original_palace']; host=convention['center_host_palace']
        if self._one('stars','home_palace',center)['name']!=convention['center_star'] or \
           self._one('stars','home_palace',host)['name']!=convention['center_companion_star']:
            raise NotCovered('Center-star and companion convention conflicts with supplied native positions')
        earth=self._earth_plate(dun,bureau); positions={v:int(k) for k,v in earth['palaces'].items()}
        xun=self._xun(hour_ganzhi); native=positions[xun['hidden_stem']]
        star=self._one('stars','home_palace',native)
        door_home=host if native==center else native
        door=self._one('doors','home_palace',door_home)
        hour_stem=hour_ganzhi[0]
        target=positions[hour_stem if hour_stem in positions else xun['hidden_stem']]
        star_layout=host if target==center else target
        step,label=self._direction(dun)
        door_target=(native-1+step*(xun['hour_in_xun']-1))%9+1
        if door_target==center:
            raise NotCovered('Final chief door lands in palace five; no supplied hosting convention')
        shift=(ring.index(star_layout)-ring.index(host if native==center else native))%8
        heaven={str(p):[] for p in range(1,10)}
        for row in self._rows('stars'):
            home=row['home_palace']; anchor=host if home==center else home
            destination=ring[(ring.index(anchor)+shift)%8]
            heaven[str(destination)].append({'name':row['name'],
                'carried_stem':earth['palaces'][str(home)],'native_palace':home})
        door_shift=(ring.index(door_target)-ring.index(door_home))%8
        doors={str(p):None for p in range(1,10)}
        for row in self._rows('doors'):
            destination=ring[(ring.index(row['home_palace'])+door_shift)%8]
            doors[str(destination)]=row['name']
        deities={str(p):None for p in range(1,10)}
        deity_order=convention['deity_order']
        if len(deity_order)!=8 or len(set(deity_order))!=8:
            raise ValueError('Incomplete source deity sequence')
        for offset,name in enumerate(deity_order):
            destination=ring[(ring.index(star_layout)+step*offset)%8]
            deities[str(destination)]=name
        palaces={str(p):{'earth_stem':earth['palaces'][str(p)],'heaven_stars':heaven[str(p)],
                         'door':doors[str(p)],'deity':deities[str(p)]} for p in range(1,10)}
        chiefs={'xun_head':xun['xun_head'],'hidden_stem':xun['hidden_stem'],
                'zhifu_star':star['name'],'zhifu_native_palace':native,
                'zhifu_landing_original_palace':target,'zhifu_layout_palace':star_layout,
                'zhishi_door':door['name'],'zhishi_native_palace':door_home,
                'zhishi_counting_origin_palace':native,'zhishi_landing_palace':door_target}
        sources=sorted({record['source_id'] for record in self._used.values()}|
                       {s for record in self._used.values() for s in record['payload'].get('supporting_source_ids',[])})
        chart={'input_datetime':None,'timezone':None,'location':None,'casting_method':method,
               'method_version':'1','four_pillars':{'year':None,'month':None,'day':None,'hour':hour_ganzhi},
               'bureau':{'dun':label,'number':bureau},'palaces':palaces,
               'earth_plate':earth['palaces'],'heaven_plate':heaven,'doors':doors,'deities':deities,
               'voids':None,'horse':None,'derived_facts':chiefs,
               'center':{**earth['center'],'native_star':convention['center_star'],
                         'actual_star_in_center':False,'companion_star':convention['center_companion_star']},
               'source_or_engine':{'engine':'source_paper_rotation_v1','source_ids':sources},
               'validation_status':'symbolic_verified','plate_layout_complete':True,
               'validation_scope':'supplied_dun_bureau_hour_only','calendar_recomputed':False,
               'complete_chart':False,'professional_analysis_completed':False}
        chart['chart_id']='chart-'+digest(canonical(chart).encode())
        return chart

    @staticmethod
    def immutable_chart(result: dict) -> Chart:
        if result.get('status')!='computed' or not result['result'].get('plate_layout_complete'):
            raise ValueError('A computed symbolic layout is required')
        payload=result['result']
        return Chart(payload['chart_id'],payload['casting_method'],payload['method_version'],
                     canonical(payload),payload['validation_status'])
