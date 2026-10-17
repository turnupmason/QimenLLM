"""Report distinct failure modes; refusal is never a completed professional answer."""
from collections import Counter


def summarize(results: list[dict]) -> dict:
    counts=Counter(r['status'] for r in results)
    total=len(results)
    return {'total':total,'status_counts':dict(counts),
            'professional_completions':sum(r.get('professional_analysis_completed') is True for r in results),
            'structural_successes':counts['structurally_verified'],
            'generation_failures':counts['generation_error'],
            'evidence_failures':counts['verification_failed']+counts['final_verification_failed'],
            'professional_correctness':None,'real_world_predictive_accuracy':None}
