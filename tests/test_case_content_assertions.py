"""Deterministic regressions for the numeric-ID collision in Actions run 39046797275."""
import copy
import json
import unittest

from support import case_content_text


COLLIDING_HASH='43a2315a84b68c425eb3e38ab559e78fe2eac199155022a22e4ca78404c805b2'
COLLIDING_UUID='19910000-0000-4000-8000-000000000000'


class CaseContentAssertionTests(unittest.TestCase):
    def test_valid_opaque_id_and_digest_fields_do_not_count_as_evidence(self):
        value={key:prefix+COLLIDING_HASH for key,prefix in (
            ('case_id','case-'),('event_id','event-'),('family_id','family-'),
            ('record_id','record-'),('chart_id','chart-'),('source_id','span-'),
            ('source_sha256',''),('content_sha256',''),('sha256',''))}
        value.update(revision_id=COLLIDING_UUID,data_version=COLLIDING_UUID)
        value['source']={'source_id':COLLIDING_UUID,'text':'Known engineering context.'}
        self.assertIn('1991',json.dumps(value))  # Old check reproduces the false alarm.
        projected=json.loads(case_content_text(value))
        self.assertEqual(set(projected),set(value))
        self.assertEqual(projected['source']['text'],value['source']['text'])
        self.assertNotIn('1991',case_content_text(value))

    def test_required_year_cannot_be_satisfied_by_opaque_identity(self):
        value={'source_id':'span-'+COLLIDING_HASH.replace('1991','1921'),
               'text':'The known year is absent.'}
        self.assertIn('1921',json.dumps(value))
        self.assertNotIn('1921',case_content_text(value))
        value['text']='The known year is 1921.'
        self.assertIn('1921',case_content_text(value))

    def test_all_nested_content_paths_remain_searchable(self):
        for value in (
            {'text':'1991'}, {'source':{'text':'1991'}},
            {'evidence':[{'source':{'text':'1991'}}]},
            {'background':{'year':1991}}, {'payload':{'unknown':[1991]}},
            {'charts':[{'unexpected':{'year':1991}}]},
            {'reported_at':'1991-12-01'}, {'speaker':'1991'},
            {'unknown':[{'future_1991':None}]}):
            with self.subTest(value=value):
                self.assertIn('1991',case_content_text(value))

    def test_malformed_or_unexpected_identity_values_are_not_hidden(self):
        for value in (
            {'source_id':'born1991'}, {'source_id':1991},
            {'source_id':{'text':'1991'}}, {'source_id':['1991']},
            {'source_id':'span-'+COLLIDING_HASH+' extra1991'},
            {'revision_id':'1991'}, {'data_version':'1991年'},
            {'case_id':'wrong-'+COLLIDING_HASH}, {'sha256':'1991'},
            {'unknown_id':'span-'+COLLIDING_HASH}):
            with self.subTest(value=value):
                self.assertIn('1991',case_content_text(value))

    def test_hash_shaped_narrative_and_semantic_locators_remain_searchable(self):
        for key in ('text','locator','book_key','chapter_key','reported_at'):
            with self.subTest(key=key):
                self.assertIn('1991',case_content_text({key:COLLIDING_HASH}))
        self.assertIn('reasoning-2',case_content_text({
            'record_id':'record-'+COLLIDING_HASH,
            'source':{'locator':'case:engineering:record:reasoning-2'}}))

    def test_projection_preserves_structure_and_does_not_mutate_input(self):
        value={'source_id':'span-'+COLLIDING_HASH,'items':[{'sequence':3,'text':'Context'}],
               'payload':{},'background':None,'training_export':False}
        original=copy.deepcopy(value)
        projected=json.loads(case_content_text(value))
        self.assertEqual(value,original)
        self.assertEqual(set(projected),set(value))
        self.assertEqual(projected['items'],value['items'])
        self.assertEqual(projected['payload'],{})
        self.assertIsNone(projected['background'])
        self.assertIs(projected['training_export'],False)
