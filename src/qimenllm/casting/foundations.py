"""Partial source-grounded teaching calculations, not a complete date-to-chart engine."""
from __future__ import annotations

from ..knowledge.db import digest
from ..knowledge.importer import canonical
from ..retrieval.repository import KnowledgeRepository


class NotCovered(ValueError):
    pass


class AmbiguousSource(ValueError):
    pass


class FoundationCalculator:
    METHOD_IDS=('shenqi_ch1_foundation_v1',)
    INTEGER_ARGS=frozenset({'bureau','palace'})
    OPERATIONS={
        'stem_attribute':{'stem'},'hidden_jia':{'xun_head'},'earth_plate':{'dun','bureau'},
        'xun':{'ganzhi'},'day_yuan':{'day_ganzhi'},'bureau':{'solar_term','day_ganzhi','method'},
        'star_attribute':{'star'},'door_attribute':{'door'},'deity_attribute':{'deity'},
        'palace_attribute':{'palace'},'operational_hour_half':{'stem'},
        'trigram_classification':{'classification'},'element_relation':{'source','target'},
        'duty':{'dun','bureau','hour_ganzhi'},
    }

    def __init__(self, knowledge: KnowledgeRepository):
        self.knowledge=knowledge

    def calculate(self, operation: str, args: dict) -> dict:
        # Keep per-call evidence state isolated, including in future concurrent servers.
        return type(self)(self.knowledge)._calculate(operation,args)

    def _calculate(self, operation: str, args: dict) -> dict:
        if operation not in self.OPERATIONS: raise ValueError('Unsupported calculation operation')
        if not isinstance(args,dict) or set(args)-self.OPERATIONS[operation]:
            raise ValueError('Unknown calculation argument')
        missing=sorted(self.OPERATIONS[operation]-set(args))
        if missing: return {'status':'conditional','missing':missing,'professional_analysis_completed':False}
        if any(value is None for value in args.values()):
            return {'status':'conditional','missing':[k for k,v in args.items() if v is None],
                    'professional_analysis_completed':False}
        for key,value in args.items():
            if key not in self.INTEGER_ARGS and not isinstance(value,str):
                raise ValueError('Symbolic calculation arguments must be strings')
        self._families={}; self._used={}
        records=[record for method in self.METHOD_IDS for record in self.knowledge.compiled_datasets(method)]
        for record in records:
            payload=record['payload']
            if payload.get('kind')!='compiled_dataset': continue
            key=payload['dataset']['key']
            if key in self._families: raise AmbiguousSource('Multiple compiled versions require explicit resolution')
            self._families[key]=record
        try:
            value=getattr(self,'_'+operation)(**args)
        except NotCovered as exc:
            return {'status':'not_covered','reason':str(exc),'professional_analysis_completed':False}
        evidence=[]
        for key,record in self._used.items():
            ids=[record['source_id'],*record['payload'].get('supporting_source_ids',[])]
            for source_id in dict.fromkeys(ids):
                source=self.knowledge.source(source_id)
                if source['sha256']!=record['payload']['source_sha256']:
                    raise ValueError('Compiled source fingerprint mismatch')
                evidence.append({'dataset':key,'item_id':record['item_id'],'source_id':source_id,
                    'book':source['book'],'chapter':source['chapter'],'locator':source['locator'],
                    'sha256':source['sha256'],'source_acceptance':record['source_acceptance']})
        return {'status':'computed','operation':operation,'inputs':dict(args),'result':value,
                'calculation_id':digest(canonical([operation,args,evidence]).encode()),'evidence':evidence,
                'validation_scope':'provided_symbolic_inputs_only',
                'source_acceptance':'reported_per_citation_not_assumed',
                'complete_chart':False,'professional_analysis_completed':False,
                'calendar_recomputed':False,'model_analysis':None}

    def _rows(self, key: str) -> list[dict]:
        record=self._families.get(key)
        if record is None: raise NotCovered('Required source dataset unavailable: '+key)
        self._used[key]=record
        return record['payload']['dataset']['rows']

    def _one(self, key, field, value):
        rows=[row for row in self._rows(key) if row.get(field)==value]
        if len(rows)!=1: raise NotCovered('No unique source record for '+str(value))
        return dict(rows[0])

    @staticmethod
    def _direction(dun):
        if dun in ('阳遁','yang'): return 1,'阳遁'
        if dun in ('阴遁','yin'): return -1,'阴遁'
        raise ValueError('dun must explicitly be 阳遁 or 阴遁')

    @staticmethod
    def _palace(value):
        if type(value) is not int or not 1<=value<=9: raise ValueError('Palace/bureau must be an integer 1..9')
        return value

    def _stem_attribute(self, stem): return self._one('stem_attributes','stem',stem)

    def _hidden_jia(self, xun_head):
        row=self._one('hidden_jia','xun_head',xun_head)
        return {**row,'hidden_stem':row['instrument']}

    def _earth_plate(self, dun, bureau):
        step,label=self._direction(dun); self._palace(bureau)
        sequence=sorted(self._rows('earth_sequence'),key=lambda row:row['position'])
        if len(sequence)!=9 or len({row['stem'] for row in sequence})!=9:
            raise ValueError('Incomplete source earth sequence')
        conventions=self._families['earth_sequence']['payload']['dataset']['conventions']
        original=self._palace(conventions['center_original_palace'])
        host=self._palace(conventions['center_host_palace'])
        # Hosting is separately cited in the complete source example table.
        # It is not a tenth palace or a replacement of palace 2's original stem.
        palaces={str((bureau-1+step*i)%9+1):row['stem'] for i,row in enumerate(sequence)}
        return {'dun':label,'bureau':bureau,'palaces':dict(sorted(palaces.items(),key=lambda p:int(p[0]))),
                'center':{'original_palace':original,'stem':palaces[str(original)],'host_palace':host},
                'scope':'earth_stems_only','full_heaven_doors_deities':False}

    def _xun(self, ganzhi):
        for row in self._rows('sexagenary_xun'):
            if ganzhi in row['ganzhi']:
                hidden=self._hidden_jia(row['xun_head'])
                return {'ganzhi':ganzhi,'xun_head':row['xun_head'],'hidden_stem':hidden['hidden_stem'],
                        'hour_in_xun':row['ganzhi'].index(ganzhi)+1}
        raise NotCovered('Stem/branch pair not present in the supplied sixty-item table')

    def _day_yuan(self, day_ganzhi):
        for row in self._rows('day_yuan'):
            if day_ganzhi in row['days']:
                return {'day_ganzhi':day_ganzhi,'fu_head':row['fu_head'],'yuan':row['yuan'],
                        'yuan_key':row['yuan_key'],'day_in_yuan':row['days'].index(day_ganzhi)+1,
                        'is_fu_head':day_ganzhi==row['fu_head']}
        raise NotCovered('Day stem/branch pair not provided')

    def _bureau(self, solar_term, day_ganzhi, method):
        if method not in ('chaibu','shenqi_ch1_chaibu_v1'):
            raise NotCovered('This operation supports only the explicitly selected source 拆补法')
        yuan=self._day_yuan(day_ganzhi)
        term=self._one('term_bureaus','term',solar_term)
        _,dun=self._direction(term['dun'])
        return {'solar_term':solar_term,'day_ganzhi':day_ganzhi,'fu_head':yuan['fu_head'],
                'yuan':yuan['yuan'],'dun':dun,'bureau':term[yuan['yuan_key']],
                'method':'shenqi_ch1_chaibu_v1','term_boundary':'caller_supplied; no clock-time inference'}

    def _named(self,key,name):
        rows=[row for row in self._rows(key) if row['name']==name or name in row.get('aliases',[])]
        if len(rows)!=1: raise NotCovered('Name/alias not explicitly provided in this dataset')
        return dict(rows[0])

    def _star_attribute(self, star):
        return {**self._named('stars',star),'palace_dimension':'native_home_not_actual_landing'}

    def _door_attribute(self, door):
        return {**self._named('doors',door),'palace_dimension':'native_home_not_actual_landing'}

    def _deity_attribute(self, deity): return self._named('deities',deity)

    def _palace_attribute(self, palace):
        self._palace(palace)
        star=self._one('stars','home_palace',palace)
        terms=[r for r in self._rows('term_bureaus') if r['palace']==palace]
        return {'palace':palace,'trigram':terms[0]['trigram'] if terms else None,
                'direction':star['direction'],'home_star':star['name'],
                'home_star_element':star['element'],'palace_element':None,
                'element_scope':'star element is explicit; separate palace-element rule not supplied'}

    def _operational_hour_half(self, stem):
        self._stem_attribute(stem)
        for row in self._rows('operational_hour_halves'):
            if stem in row['stems']:
                return {**row,'stem':stem,'classification':'source_five_hour_halves_not_stem_polarity'}
        raise NotCovered('Operational time classification unavailable')

    def _trigram_classification(self, classification):
        return self._one('trigram_classifications','classification',classification)

    def _element_relation(self, source, target):
        rows=[r for r in self._rows('explicit_element_relations') if r['source']==source and r['target']==target]
        if not rows: raise NotCovered('This directed relation was not supplied; unknown does not mean false')
        return {'source':source,'target':target,'relations':[r['relation'] for r in rows]}

    def _duty(self, dun, bureau, hour_ganzhi):
        earth=self._earth_plate(dun,bureau); xun=self._xun(hour_ganzhi)
        positions={stem:int(palace) for palace,stem in earth['palaces'].items()}
        native=positions[xun['hidden_stem']]
        if native==5:
            raise NotCovered('Chief identity/hosting at central xun origin needs an explicit method convention')
        star=self._one('stars','home_palace',native)
        door=self._one('doors','home_palace',native)
        if self._families['stars']['payload']['dataset'].get('movement_rule')!='follow_hour_stem_earth_palace':
            raise NotCovered('Star chief movement convention unavailable')
        if self._families['doors']['payload']['dataset'].get('movement_rule')!='signed_hour_offset_from_xun_origin':
            raise NotCovered('Door chief movement convention unavailable')
        stem=hour_ganzhi[0]
        effective=xun['hidden_stem'] if stem not in positions else stem
        landing=positions[effective]
        step,_=self._direction(dun)
        door_landing=(native-1+step*(xun['hour_in_xun']-1))%9+1
        return {'xun_head':xun['xun_head'],'hidden_stem':xun['hidden_stem'],
                'zhifu_star':star['name'],'zhifu_native_palace':native,'zhifu_landing_palace':landing,
                'zhifu_hosted_palace':earth['center']['host_palace'] if landing==earth['center']['original_palace'] else None,
                'zhishi_door':door['name'],'zhishi_native_palace':native,
                'zhishi_landing_palace':door_landing,'zhishi_hosted_palace':None,
                'door_center_hosting':'not_specified' if door_landing==5 else 'not_applicable',
                'remaining_star_and_door_positions':'not_computed'}
