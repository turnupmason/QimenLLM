"""Appendix three alternate source and explicitly supplied chart relayout."""
import copy
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from qimenllm.api.app import create_app
from qimenllm.knowledge.db import APPEND_ONLY, connect, digest
from qimenllm.knowledge.integrity import audit
from qimenllm.knowledge.snapshot import export_snapshot, restore_snapshot
from qimenllm.reasoning.service import QimenService
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import import_shenqi_demo as importer


class DemoSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db,cls.raw=cls.path/'db',cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:
            cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY+('books','dataset_releases')}
        cls.result=importer.ingest(cls.db,cls.raw);cls.source=importer.UPLOAD.read_bytes()
        cls.art=json.loads((importer.DATA/'demo_curated.json').read_bytes())
        cls.gold=json.loads((importer.DATA/'demo_gold.json').read_bytes())
        cls.relation=cls.art['source_relationship'];cls.chart=cls.art['annotations'][1]['payload']
        cls.svc=QimenService(cls.db)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_source_bytes_and_every_new_and_old_byte_selector(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(importer.DEMO_SHA,15047,140))
        self.assertNotIn(b'\r',self.source)
        cache={}
        def walk(v):
            if isinstance(v,dict):
                if {'source_sha256','byte_start','byte_end','source_quote'} <= v.keys():
                    sha=v['source_sha256']
                    if sha not in cache:cache[sha]=(ROOT/'data/provenance/uploads'/(sha+'.utf8')).read_bytes()
                    self.assertEqual(digest(cache[sha]),sha)
                    self.assertEqual(cache[sha][v['byte_start']:v['byte_end']].decode(),v['source_quote'])
                for child in v.values():walk(child)
            elif isinstance(v,list):
                for child in v:walk(child)
        walk(self.art)

    def test_narrative_equality_excludes_explicit_chart_representations_only(self):
        r=self.relation;p=r['existing_source_selector']
        old=(ROOT/'data/provenance/uploads'/(p['source_sha256']+'.utf8')).read_bytes().decode().splitlines(keepends=True)
        new=self.source.decode().splitlines(keepends=True)
        self.assertEqual(r['comparison']['excluded_old_source_lines'],[230]+list(range(241,255)))
        self.assertEqual(r['comparison']['excluded_new_source_lines'],list(range(91,108)))
        a=re.sub(r'\s+','',''.join(old[n-1] for n in range(172,277) if n!=230 and not 241<=n<=254))
        b=re.sub(r'\s+','',''.join(new[n-1] for n in range(1,141) if not 91<=n<=107))
        self.assertEqual(a,b);self.assertEqual(len(b),4387)
        self.assertEqual(digest(b.encode()),r['comparison']['normalized_narrative_sha256'])
        self.assertEqual(r['comparison']['lexical_narrative_differences'],[])

    def test_all_thirty_alignment_records_resolve_to_original_text_and_phases(self):
        self.assertEqual(len(self.relation['event_record_alignments']),30)
        with connect(self.db) as c:
            for a in self.relation['event_record_alignments']:
                r=c.execute('SELECT text,kind,knowledge_phase FROM case_records WHERE record_id=?',(a['existing_record_id'],)).fetchone()
                self.assertEqual(tuple(r),(a['existing_source_selector']['source_quote'],a['kind'],a['knowledge_phase']))
                old=''.join(l for l in r['text'].splitlines(keepends=True) if not ('458' in l and '神 奇 之 门' in l))
                self.assertEqual(re.sub(r'\s+','',old),re.sub(r'\s+','',a['new_source_selector']['source_quote']))

    def test_real_existing_case_two_events_and_chart_references_unchanged(self):
        with connect(self.db) as c:
            case=c.execute('SELECT title FROM cases WHERE case_id=?',(self.relation['existing_case_id'],)).fetchone()
            self.assertIn('现场表演',case['title'])
            for e in self.relation['existing_event_links']:
                row=c.execute('SELECT family_id FROM events WHERE event_id=?',(e['existing_event_id'],)).fetchone()
                self.assertEqual(row[0],e['existing_family_id'])
                actual=[r[0] for r in c.execute('SELECT chart_id FROM charts WHERE event_id=?',(e['existing_event_id'],))]
                self.assertEqual(actual,e['existing_chart_ids'])
        self.assertEqual(len(self.relation['existing_event_links']),2)
        self.assertEqual(len({e['existing_family_id'] for e in self.relation['existing_event_links']}),1)

    def test_supplied_chart_disclaimer_does_not_establish_scan_or_engine_verification(self):
        self.assertIn('根据提供的文字原盘重排',self.chart['source_claim_selector']['source_quote'])
        self.assertEqual(self.chart['representation_kind'],'user_supplied_relayout_from_prior_text_not_original_scan')
        for key in ('new_independent_chart','engine_verified','original_scan_verified','existing_chart_records_modified'):
            self.assertFalse(self.chart[key])
        self.assertEqual(self.gold['palace_order'],[4,9,2,3,5,7,8,1,6])

    def test_all_nine_literal_palaces_against_independent_manual_gold_and_source_cells(self):
        rows=self.chart['dataset']['rows'];self.assertEqual(len(rows),9)
        self.assertEqual([r['source_cells_as_written'] for r in rows],self.gold['cells'])
        for r in rows:
            lines=r['source_selector']['source_quote'].splitlines()
            col=r['source_grid_column']
            cells=[line.split('│')[col].strip() for line in lines]
            self.assertEqual(cells,r['source_cells_as_written'])
            self.assertEqual(r['applicability_status'],'reference_only')
        self.assertEqual(rows[3]['door_as_written'],'生乙')
        self.assertEqual(rows[4]['center_text_as_written'],'壬');self.assertIsNone(rows[4]['door_as_written'])
        self.assertEqual(rows[8]['door_as_written'],'壬惊丙')

    def test_chronology_rejection_continuation_letter_and_later_note_preserved(self):
        alignment={a['existing_record_key']:a for a in self.relation['event_record_alignments']}
        denied=alignment['appendix-accident-lines-211-212'];continuation=alignment['appendix-accident-lines-213-213']
        self.assertEqual(denied['new_source_selector']['line_start'],55)
        self.assertEqual(continuation['knowledge_phase'],'post_feedback')
        self.assertEqual(continuation['new_source_selector']['line_start'],59)
        later=alignment['appendix-publication-lines-276-276']
        self.assertEqual(later['new_source_selector']['line_start'],140)
        self.assertEqual(later['knowledge_phase'],'post_feedback')
        self.assertIn('2000年2月',later['new_source_selector']['source_quote'])
        self.assertIn('只可能在北方',alignment['appendix-publication-lines-222-234']['new_source_selector']['source_quote'])

    def test_initial_view_and_old_fragment_case_chart_status_stay_unchanged(self):
        cid=self.relation['existing_case_id'];v=self.svc.case(cid,'before_prediction')
        self.assertFalse(v['training_export'])
        for e in v['events']:self.assertFalse(e['charts'])
        s=json.dumps(v,ensure_ascii=False)
        for term in ('张贵河','王成周','第八根肋条','中国异人传奇','死俩伤仨'):self.assertNotIn(term,s)
        for e in self.relation['existing_event_links']:
            for chartid in e['existing_chart_ids']:
                r=self.svc.case_chart(cid,chartid);self.assertEqual((r['status'],r['chart_id']),('not_covered',chartid))

    def test_no_duplicate_substantive_tables_or_rule_candidates(self):
        unchanged=('books','concepts','concept_links','methods','cases','events','case_events','event_families','charts','case_records','evidence_links','rules','rule_conditions','rule_disagreements','training_tasks','task_inputs','dataset_releases')
        with connect(self.db) as c:
            for t in unchanged:self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM '+t)],self.before[t],t)
            before=[r for r in self.before['knowledge_items'] if 'source_selection_candidate' in str(r)]
            after=[tuple(r) for r in c.execute("SELECT * FROM knowledge_items WHERE json_extract(payload_json,'$.kind')='source_selection_candidate'")]
            self.assertEqual(set(before),set(after))
        self.assertEqual(self.svc.cases('appendix-demo-clean')['cases'],[])

    def test_four_annotations_remain_reference_only_and_appendix_order_is_three(self):
        with connect(self.db) as c:
            rows=c.execute('SELECT compiled,reference_only,applicability_confirmed,method_id,payload_json FROM knowledge_items JOIN source_spans USING(source_id) WHERE revision_id=?',(self.result['source']['revision_id'],)).fetchall()
            self.assertEqual(len(rows),4);self.assertTrue(all(tuple(r[:4])==(0,1,0,None) for r in rows))
            self.assertEqual(sorted(json.loads(r['payload_json'])['kind'] for r in rows),['context_group']*2+['source_quality_issue']*2)
            seq=dict(c.execute("SELECT chapter_key,sequence FROM chapters WHERE chapter_key IN ('appendix-biography-clean','appendix-learning-clean','appendix-demo-clean')").fetchall())
        self.assertEqual(seq,{'appendix-biography-clean':25,'appendix-learning-clean':26,'appendix-demo-clean':27})
        self.assertEqual(self.art['printed_appendix_number'],3)

    def test_reference_filters_and_learning_read_all_new_supplied_palaces(self):
        allrows=self.svc.reference('demo_clean_palaces_reference',{})
        self.assertEqual(allrows['total'],9);self.assertFalse(allrows['professional_analysis_completed'])
        for palace in self.gold['palace_order']:
            r=self.svc.reference('demo_clean_palaces_reference',{'palace':palace})
            self.assertEqual(r['total'],1);self.assertEqual(r['entries'][0]['record']['palace'],palace)
        for s in allrows['sources'].values():
            self.assertEqual(s['sha256'],importer.DEMO_SHA);self.assertEqual(s['source_acceptance'],'confirmed')
        r=self.svc.learning.learn('附录三精校来源')
        self.assertTrue(any(b['payload'].get('key')=='demo_clean_source_occurrence' for b in r['knowledge_blocks']))

    def test_actual_cli_and_wsgi_read_same_literal_relayout(self):
        app=create_app(self.svc);body=json.dumps({'family':'demo_clean_palaces_reference','filters':{'palace':6}}).encode();status=[]
        out=b''.join(app({'PATH_INFO':'/v1/reference','REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)},lambda s,h:status.append(s)))
        self.assertEqual(status,['200 OK']);self.assertEqual(json.loads(out)['entries'][0]['record']['door_as_written'],'壬惊丙')
        r=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'reference','demo_clean_palaces_reference','--filters','{}'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual([e['record']['source_cells_as_written'] for e in json.loads(r.stdout)['entries']],self.gold['cells'])

    def test_replay_source_and_relationship_guards_and_all_old_rows(self):
        with connect(self.db) as c:
            n=c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
            for t,old in self.before.items():
                current=[tuple(x) for x in c.execute('SELECT * FROM '+t)]
                self.assertTrue(all(r in current for r in old),t)
        self.assertTrue(importer.ingest(self.db,self.raw)['curation']['duplicate'])
        p=self.path/'bad.txt';p.write_bytes(self.source.replace(b'\n',b'\r\n'))
        with patch.object(importer,'UPLOAD',p),self.assertRaises(ValueError):importer.ingest(self.db,self.raw)
        art=copy.deepcopy(self.art);art['source_relationship']['existing_source_selector']['source_quote']='changed'
        d=self.path/'data';d.mkdir();(d/'demo_curated.json').write_text(json.dumps(art))
        with patch.object(importer,'DATA',d),self.assertRaises(ValueError):importer.ingest(self.db,self.raw)
        with connect(self.db) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],n)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_snapshot_roundtrip_keeps_original_fragments_and_new_relayout_source(self):
        a,b=self.path/'snapshot',self.path/'again';db,raw=self.path/'restore.db',self.path/'restore-raw'
        export_snapshot(self.db,self.raw,a);restore_snapshot(a,db,raw);export_snapshot(db,raw,b)
        self.assertEqual({str(p.relative_to(a)):p.read_bytes() for p in a.rglob('*') if p.is_file()},
                         {str(p.relative_to(b)):p.read_bytes() for p in b.rglob('*') if p.is_file()})
        self.assertEqual((a/'raw'/(importer.DEMO_SHA+'.bin')).read_bytes(),self.source)
