"""Case-family-level, chapter-dynamic release gate and safe new-case split planning.

For *release creation*, not model training/inference. Accepts only reviewed
metadata (no answers, source spans, held-out task prompts or test JSONL).
A chapter with several questions from one story counts as ONE family. The
existing frozen family assignments are never changed. Missing evidence blocks
certification; it never invents independent cases.
"""
from collections import defaultdict

SOURCE_ONLY_MODES = frozenset({'reference_reading', 'source_reading'})
SPLITS = frozenset({'train', 'validation', 'development', 'test'})
MINIMUM_SEALED_TEST_CASE_FAMILIES = 1
MINIMUM_UNSEEN_VALIDATION_CASE_FAMILIES = 1


def case_chapters(chapter_coverage):
    """Automatically include a newly registered chapter when it has case tasks."""
    return {
        key for key, source in chapter_coverage.items()
        if any(mode not in SOURCE_ONLY_MODES and count > 0
               for mode, count in source.get('modes', {}).items())
    }


def evaluate_case_family_coverage(release, reviewed_cases=()):
    """Examine *metadata* collected in the offline freeze review, no model test IO.

    reviewed_cases: metadata-only records from reviewed complete cases, each with
    chapter, case_id, family_id, split, complete_case_reviewed,
    input_chronology_reviewed, and independent_initial_prediction_eligible.
    The last field must not be inferred from task count, JSON conformity or
    retrospective/source-conditioned imitation.
    """
    coverage = release['chapter_coverage']
    categories = case_chapters(coverage)
    families = release['family_assignments']
    grouped = defaultdict(lambda: defaultdict(set))
    evidence = set()
    for row in reviewed_cases:
        if not isinstance(row, dict):
            raise ValueError('Case review evidence must be metadata records')
        chapter = row.get('chapter')
        if chapter not in categories:
            raise ValueError('An unregistered/new chapter needs reviewed source registration')
        family = row.get('family_id')
        split = row.get('split')
        if not family or families.get(family) != split or split not in SPLITS:
            raise ValueError('Event-family split mismatch; never reassign frozen families')
        case_id = row.get('case_id')
        if not case_id:
            raise ValueError('A full real historical case ID is mandatory')
        key = (chapter, case_id, family, split)
        if key in evidence:
            continue
        evidence.add(key)
        if (row.get('complete_case_reviewed') is True
                and row.get('input_chronology_reviewed') is True
                and row.get('independent_initial_prediction_eligible') is True):
            # Same family with 20 tasks remains exactly one family.
            grouped[chapter][split].add(family)

    results = {}
    for chapter in sorted(categories):
        counts = {s: len(grouped[chapter][s]) for s in SPLITS}
        eligible_validation = counts['validation']
        eligible_final_test = counts['test']
        results[chapter] = {
            'title': coverage[chapter]['title'],
            'verified_review_metadata_validation_families': eligible_validation,
            'verified_review_metadata_sealed_test_families': eligible_final_test,
            'heldout_test_case_minimum_met': eligible_final_test >= MINIMUM_SEALED_TEST_CASE_FAMILIES,
            'unseen_validation_case_minimum_met': eligible_validation >= MINIMUM_UNSEEN_VALIDATION_CASE_FAMILIES,
            'ready_for_independent_whole_chapter_claim': (
                eligible_final_test >= MINIMUM_SEALED_TEST_CASE_FAMILIES
                and eligible_validation >= MINIMUM_UNSEEN_VALIDATION_CASE_FAMILIES
            ),
        }
    return {
        'scope': 'candidate_release_case_family_metadata_audit_no_sealed_content_access',
        'expected_case_chapters': len(categories),
        'case_chapters': results,
        'missing_sealed_test_cases': [k for k in results if not results[k]['heldout_test_case_minimum_met']],
        'missing_unseen_validation_cases': [k for k in results if not results[k]['unseen_validation_case_minimum_met']],
        'all_categories_have_independent_case_test_and_validation': bool(results) and all(
            value['ready_for_independent_whole_chapter_claim'] for value in results.values()
        ),
        'test_model_inference_performed': False,
        'professional_prediction_accuracy': None,
        'note': 'Metadata eligibility is necessary, never sufficient for model professional pass.',
    }


def suggest_split_for_new_family(release, chapter, family_id, reviewed_cases=()):
    """Non-mutating recommendation for future NEW families, before next freeze.

    All existing families retain their original group, even in another chapter.
    Reserve a sealed independent case first where missing, then a validation
    case; other new families are candidates for train. No automatic freeze.
    """
    if not family_id:
        raise ValueError('Family ID required; match cross-book repeats before assignment')
    existing = release['family_assignments'].get(family_id)
    if existing is not None:
        return {'chapter': chapter, 'family_id': family_id, 'split': existing,
                'action': 'reuse_original_family_split_do_not_move_or_clone',
                'can_publish_without_review': False}
    if chapter not in release['chapter_coverage']:
        return {'chapter': chapter, 'family_id': family_id, 'split': None,
                'action': 'new_chapter_source_review_and_registration_required',
                'can_publish_without_review': False}
    if chapter not in case_chapters(release['chapter_coverage']):
        return {'chapter': chapter, 'family_id': family_id, 'split': None,
                'action': 'new_case_chapter_classification_review_required',
                'can_publish_without_review': False}
    matrix = evaluate_case_family_coverage(release, reviewed_cases)
    ch = matrix['case_chapters'][chapter]
    # Do not inspect sealed test input/labels to decide this recommendation.
    if not ch['heldout_test_case_minimum_met']:
        split = 'test'
    elif not ch['unseen_validation_case_minimum_met']:
        split = 'validation'
    else:
        split = 'train'
    return {'chapter': chapter, 'family_id': family_id, 'split': split,
            'action': 'proposal_only_require_case_source_and_family_review_before_new_release',
            'can_publish_without_review': False}


def require_minimum_case_coverage(release, reviewed_cases):
    """Fail closed before claiming a NEW version has whole-book held-out coverage."""
    audit = evaluate_case_family_coverage(release, reviewed_cases)
    if not audit['all_categories_have_independent_case_test_and_validation']:
        raise ValueError('Independent per-chapter case gate blocked: missing sealed test or validation case families')
    return audit
