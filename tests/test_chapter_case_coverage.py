"""Dynamic case-family split coverage requirements; no sealed task input is read."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'training'))
from chapter_case_coverage import (
    case_chapters, evaluate_case_family_coverage, suggest_split_for_new_family,
    require_minimum_case_coverage,
)

ORIGINAL = json.loads((ROOT/'data/splits/book_method_curriculum_v1.json').read_bytes())


def case(ch, family, split, *, eligible=True, chronology=True, complete=True):
    return {
        'chapter': ch, 'case_id': 'case-'+family, 'family_id': family,
        'split': split, 'complete_case_reviewed': complete,
        'input_chronology_reviewed': chronology,
        'independent_initial_prediction_eligible': eligible,
    }


class ChapterCaseCoverageTests(unittest.TestCase):
    def test_existing_book_fifteen_topics_and_no_fake_full_pass(self):
        self.assertEqual(len(case_chapters(ORIGINAL['chapter_coverage'])), 15)
        self.assertFalse(evaluate_case_family_coverage(ORIGINAL)['all_categories_have_independent_case_test_and_validation'])
        with self.assertRaisesRegex(ValueError, 'gate blocked'):
            require_minimum_case_coverage(ORIGINAL, [])

    def test_duplicate_subtasks_or_multiple_event_views_count_as_one_family(self):
        meta = copy.deepcopy(ORIGINAL)
        k = 'work-employment'
        meta['family_assignments']['case-family-unique'] = 'test'
        row = case(k, 'case-family-unique', 'test')
        # Same source case/review emitted as many task rows: 1 family only.
        result = evaluate_case_family_coverage(meta, [row, row, dict(row, case_id='another-view-same-family')])
        self.assertEqual(result['case_chapters'][k]['verified_review_metadata_sealed_test_families'], 1)
        self.assertFalse(result['case_chapters'][k]['ready_for_independent_whole_chapter_claim'])

    def test_only_full_pre_prediction_case_counts_not_retrospective(self):
        meta = copy.deepcopy(ORIGINAL)
        k = 'education-examinations'
        meta['family_assignments']['real-case-family'] = 'test'
        for broken in (case(k, 'real-case-family', 'test', eligible=False),
                       case(k, 'real-case-family', 'test', chronology=False),
                       case(k, 'real-case-family', 'test', complete=False)):
            result = evaluate_case_family_coverage(meta, [broken])
            self.assertFalse(result['case_chapters'][k]['heldout_test_case_minimum_met'])

    def test_family_ownership_mismatch_is_blocked(self):
        meta = copy.deepcopy(ORIGINAL)
        meta['family_assignments']['family-x'] = 'train'
        with self.assertRaisesRegex(ValueError,'split mismatch'):
            evaluate_case_family_coverage(meta, [case('work-employment','family-x','test')])

    def test_future_new_chapter_is_dynamic_and_needs_genuine_case_evidence(self):
        meta = copy.deepcopy(ORIGINAL)
        meta['chapter_coverage']['new-user-topic'] = {
            'title': '新增预测专题', 'modes': {'initial': 2},
            'task_counts': {'train': 1, 'test': 1, 'validation': 1}
        }
        meta['family_assignments'].update({'new-family-test':'test','new-family-val':'validation'})
        topics = case_chapters(meta['chapter_coverage'])
        self.assertIn('new-user-topic', topics)
        result = evaluate_case_family_coverage(meta, [case('new-user-topic','new-family-test','test')])
        self.assertIn('new-user-topic', result['missing_unseen_validation_cases'])
        result = evaluate_case_family_coverage(meta, [
            case('new-user-topic','new-family-test','test'),
            case('new-user-topic','new-family-val','validation')
        ])
        self.assertTrue(result['case_chapters']['new-user-topic']['ready_for_independent_whole_chapter_claim'])
        self.assertFalse(result['all_categories_have_independent_case_test_and_validation'])

    def test_future_case_split_proposals_do_not_reassign_any_frozen_family(self):
        meta = copy.deepcopy(ORIGINAL)
        existing = next(fid for fid,s in meta['family_assignments'].items() if s == 'train')
        reuse = suggest_split_for_new_family(meta,'education-examinations',existing)
        self.assertEqual(reuse['split'],'train')
        self.assertFalse(reuse['can_publish_without_review'])
        new = suggest_split_for_new_family(meta, 'education-examinations','brand-new-event')
        self.assertEqual(new['split'], 'test')
        meta['family_assignments']['sample-sealed'] = 'test'
        meta['chapter_coverage']['education-examinations']['task_counts']['test'] = 1
        next_one = suggest_split_for_new_family(meta,'education-examinations','brand-new-event',
                                                 [case('education-examinations','sample-sealed','test')])
        self.assertEqual(next_one['split'],'validation')
        other = suggest_split_for_new_family(meta,'topic-not-yet-registered','brand-new-event')
        self.assertIsNone(other['split'])
        self.assertIn('registration', other['action'])

    def test_no_test_or_development_exposure_needed_for_this_audit(self):
        result = evaluate_case_family_coverage(ORIGINAL)
        self.assertEqual(result['scope'],'candidate_release_case_family_metadata_audit_no_sealed_content_access')
        self.assertFalse(result['test_model_inference_performed'])
        self.assertIsNone(result['professional_prediction_accuracy'])


if __name__ == '__main__':
    unittest.main()
