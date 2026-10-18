"""Alternate learning source is retained and linked without duplicating knowledge."""
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
import import_shenqi_learning as importer


class LearningSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        cls.db=cls.path/'db';cls.raw=cls.path/'raw'
        restore_snapshot(ROOT/'data/snapshots/current',cls.db,cls.raw)
        with connect(cls.db) as c:
            cls.before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in APPEND_ONLY+('books','dataset_releases')}
        cls.result=importer.ingest(cls.db,cls.raw);cls.source=importer.UPLOAD.read_bytes()
        cls.art=json.loads((importer.DATA/'learning_curated.json').read_bytes())
        cls.svc=QimenService(cls.db)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_exact_new_lf_source_and_both_source_selectors(self):
        self.assertEqual((digest(self.source),len(self.source),len(self.source.splitlines())),(importer.LEARNING_SHA,11761,51))
        self.assertNotIn(b'\r',self.source)
        relation=self.art['source_relationship']
        for p in (relation['existing_source_selector'],relation['new_source_selector']):
            raw=(ROOT/'data/provenance/uploads'/(p['source_sha256']+'.utf8')).read_bytes()
            self.assertEqual(digest(raw),p['source_sha256'])
            self.assertEqual(raw[p['byte_start']:p['byte_end']].decode(),p['source_quote'])
        self.assertEqual(self.art['annotations'][0]['payload']['dataset']['rows'][0]['source_quote'],self.source.decode())

    def test_normalized_full_article_equality_and_only_explicit_page_header_excluded(self):
        r=self.art['source_relationship'];p=r['existing_source_selector']
        old=(ROOT/'data/provenance/uploads'/(p['source_sha256']+'.utf8')).read_bytes().decode().splitlines(keepends=True)
        self.assertEqual(r['comparison']['excluded_old_source_lines'],[93])
        new=re.sub(r'\s+','',self.source.decode())
        comparison=re.sub(r'\s+','',''.join(old[n-1] for n in range(77,140) if n!=93))
        self.assertEqual(comparison,new);self.assertEqual(len(new),3988)
        self.assertEqual(digest(new.encode()),r['comparison']['normalized_sha256'])
        self.assertEqual(r['comparison']['lexical_differences'],[])

    def test_fourteen_old_context_groups_still_resolve_to_original_source(self):
        r=self.art['source_relationship'];keys=r['existing_context_group_keys']
        self.assertEqual(len(keys),14)
        with connect(self.db) as c:
            for key in keys:
                rows=c.execute("SELECT d.sha256 FROM knowledge_items k JOIN source_spans s USING(source_id) JOIN chapter_revisions cr USING(revision_id) JOIN raw_documents d USING(document_id) WHERE json_extract(k.payload_json,'$.key')=?",(key,)).fetchall()
                self.assertEqual([row[0] for row in rows],[r['existing_source_selector']['source_sha256']])
        self.assertFalse(r['existing_source_modified']);self.assertFalse(r['new_substantive_article'])

    def test_no_duplicate_people_concepts_methods_cases_charts_candidates_or_tasks(self):
        unchanged=('books','concepts','concept_links','methods','cases','events','case_events','event_families','charts','case_records','evidence_links','rules','rule_conditions','rule_disagreements','training_tasks','task_inputs','dataset_releases')
        with connect(self.db) as c:
            for t in unchanged:self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM '+t)],self.before[t],t)
            before_candidates=[r for r in self.before['knowledge_items'] if 'source_selection_candidate' in str(r)]
            after_candidates=[tuple(r) for r in c.execute("SELECT * FROM knowledge_items WHERE json_extract(payload_json,'$.kind')='source_selection_candidate'")]
            self.assertEqual(set(before_candidates),set(after_candidates))
        self.assertEqual(self.svc.cases('appendix-learning-clean')['cases'],[])

    def test_only_two_reference_annotations_and_literal_wording(self):
        with connect(self.db) as c:
            rows=c.execute('SELECT compiled,reference_only,applicability_confirmed,method_id,payload_json FROM knowledge_items JOIN source_spans USING(source_id) WHERE revision_id=?',(self.result['source']['revision_id'],)).fetchall()
            self.assertEqual(len(rows),2)
            self.assertTrue(all(tuple(r[:4])==(0,1,0,None) for r in rows))
            self.assertEqual(sorted(json.loads(r['payload_json'])['kind'] for r in rows),['context_group','source_quality_issue'])
        self.assertIn('连门也人不了',self.source.decode())
        self.assertNotIn('连门也入不了',self.source.decode())
        self.assertIn('张志春',self.art['annotations'][0]['payload']['attribution'])
        self.assertEqual(self.art['annotations'][0]['payload']['concepts'],[])

    def test_actual_learning_reference_cli_and_wsgi_read_confirmed_new_source(self):
        r=self.svc.learning.learn('精校来源')
        self.assertTrue(any(b['payload'].get('key')=='learning_clean_source_occurrence' for b in r['knowledge_blocks']))
        ref=self.svc.reference('learning_clean_source_reference',{})
        self.assertEqual(ref['total'],1);self.assertFalse(ref['professional_analysis_completed'])
        self.assertEqual(ref['role_bindings'],[])
        for s in ref['sources'].values():
            self.assertEqual(s['sha256'],importer.LEARNING_SHA);self.assertEqual(s['source_acceptance'],'confirmed')
        app=create_app(self.svc);b=json.dumps({'family':'learning_clean_source_reference','filters':{}}).encode();status=[]
        out=b''.join(app({'PATH_INFO':'/v1/reference','REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)},lambda s,h:status.append(s)))
        self.assertEqual(status,['200 OK']);self.assertEqual(json.loads(out)['entries'][0]['record']['source_quote'],self.source.decode())
        out=subprocess.run([sys.executable,'-m','qimenllm','--db',str(self.db),'reference','learning_clean_source_reference','--filters','{}'],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(out.stdout)['entries'][0]['record']['source_quote'],self.source.decode())

    def test_replay_and_bad_source_or_bad_old_relationship_guard(self):
        with connect(self.db) as c:n=c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0]
        self.assertTrue(importer.ingest(self.db,self.raw)['curation']['duplicate'])
        bad=self.path/'bad.txt';bad.write_bytes(self.source.replace(b'\n',b'\r\n'))
        with patch.object(importer,'UPLOAD',bad),self.assertRaises(ValueError):importer.ingest(self.db,self.raw)
        badart=copy.deepcopy(self.art);badart['source_relationship']['existing_source_selector']['source_quote']='changed'
        data=self.path/'data';data.mkdir();(data/'learning_curated.json').write_text(json.dumps(badart))
        with patch.object(importer,'DATA',data),self.assertRaises(ValueError):importer.ingest(self.db,self.raw)
        with connect(self.db) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM data_versions').fetchone()[0],n)

    def test_all_old_rows_remain_exact_and_integrity_audit_passes(self):
        with connect(self.db) as c:
            for t,old in self.before.items():
                current=[tuple(r) for r in c.execute('SELECT * FROM '+t)]
                self.assertTrue(all(r in current for r in old),t)
        self.assertTrue(audit(self.db,self.raw)['ok'])

    def test_snapshot_roundtrip_exact_new_and_old_sources(self):
        a,b=self.path/'snapshot',self.path/'again';db,raw=self.path/'restore.db',self.path/'restore-raw'
        export_snapshot(self.db,self.raw,a);restore_snapshot(a,db,raw);export_snapshot(db,raw,b)
        self.assertEqual({str(p.relative_to(a)):p.read_bytes() for p in a.rglob('*') if p.is_file()},
                         {str(p.relative_to(b)):p.read_bytes() for p in b.rglob('*') if p.is_file()})
        self.assertEqual((a/'raw'/(importer.LEARNING_SHA+'.bin')).read_bytes(),self.source)

    def test_appendix_one_received_after_two_and_three_old_cases_stay_linked(self):
        self.assertEqual(self.art['printed_appendix_number'],1)
        self.assertTrue(self.source.decode().startswith('附录\n\n一、学习奇门遁甲并不难'))
        with connect(self.db) as c:
            sequence=dict(c.execute("SELECT chapter_key,sequence FROM chapters WHERE chapter_key IN ('appendix-learning-clean','appendix-biography-clean')").fetchall())
            self.assertEqual(sequence,{'appendix-learning-clean':26,'appendix-biography-clean':25})
            links=self.art['source_relationship']['existing_case_summary_links']
            self.assertEqual([r['existing_case_key'] for r in links],['business-case-12','employment-election19961027','lost-case-07'])
            for link in links:
                fid='family-'+digest(json.dumps(link['existing_family']['family_key'],ensure_ascii=False,separators=(',',':')).encode())
                self.assertEqual(c.execute('SELECT description FROM event_families WHERE family_id=?',(fid,)).fetchone()[0],link['existing_family']['description'])
                self.assertFalse(link['new_case_created']);self.assertFalse(link['new_chart_created'])
        text=self.source.decode()
        for phrase in ('化繁为简','去伪存真','规范统一','因为他已有奇门其他方面的基础知识','中五宫一律寄坤二宫','一律用天盘八神'):
            self.assertIn(phrase,text)
