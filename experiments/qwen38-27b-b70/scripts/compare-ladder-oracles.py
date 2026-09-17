#!/usr/bin/env python3
"""Compare the sequential oracle (and every batch row) of one concurrency-ladder run against another run's oracle.

Both inputs are `bench-openai-concurrency-oracle.py` outputs. The reference's `oracle.rows` (one greedy answer per
expanded prompt, produced one request at a time) is the truth; every row of the candidate's oracle and of each of
its batches is matched by prompt id and prompt hash and compared token id by token id. Reports first divergence
per row, exact counts, and a verdict. Read-only; owns no server.
"""
import argparse
import json
from pathlib import Path


def rows_by_id(rows):
    out = {}
    for row in rows:
        out[row['prompt_id']] = row
    return out


def compare_rows(candidate_rows, reference):
    exact, mismatches = 0, []
    for row in candidate_rows:
        ref = reference.get(row['prompt_id'])
        if ref is None:
            mismatches.append({'prompt_id': row['prompt_id'], 'reason': 'missing in reference'})
            continue
        if ref['prompt_sha256'] != row['prompt_sha256']:
            mismatches.append({'prompt_id': row['prompt_id'], 'reason': 'prompt hash differs'})
            continue
        a, b = row['token_ids'], ref['token_ids']
        if a == b:
            exact += 1
            continue
        first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        mismatches.append({'prompt_id': row['prompt_id'], 'first_divergence': first, 'candidate_len': len(a),
                           'reference_len': len(b), 'candidate_tokens': a[first:first + 8],
                           'reference_tokens': b[first:first + 8]})
    return exact, mismatches


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('candidate', type=Path)
    ap.add_argument('reference', type=Path)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    cand, ref = json.loads(a.candidate.read_text()), json.loads(a.reference.read_text())
    reference = rows_by_id(ref['oracle']['rows'])
    result = {'schema': 'b70-lab.ladder-oracle-comparison.v1', 'candidate': str(a.candidate), 'reference': str(a.reference),
              'reference_rows': len(reference), 'sections': []}
    all_exact = True
    exact, mismatches = compare_rows(cand['oracle']['rows'], reference)
    result['sections'].append({'section': 'sequential-oracle', 'exact': exact, 'total': len(cand['oracle']['rows']),
                               'mismatches': mismatches})
    all_exact &= not mismatches and exact == len(reference)
    for batch in cand.get('batches', []):
        exact, mismatches = compare_rows(batch['rows'], reference)
        result['sections'].append({'section': f"batch-c{batch['concurrency']}-r{batch['repeat']}", 'exact': exact,
                                   'total': len(batch['rows']), 'mismatches': mismatches,
                                   'cached_tokens_all_zero': batch.get('cached_tokens_all_zero')})
        all_exact &= not mismatches and batch.get('cached_tokens_all_zero') is True
    result['all_exact'] = all_exact
    if a.output:
        a.output.write_text(json.dumps(result, indent=2) + '\n')
    for s in result['sections']:
        print(f"{s['section']}: {s['exact']}/{s['total']}" + (f" first divergences {[(m['prompt_id'], m.get('first_divergence', m.get('reason'))) for m in s['mismatches']]}" if s['mismatches'] else ''))
    print('ALL EXACT' if all_exact else 'NOT EXACT')
    return 0 if all_exact else 1


if __name__ == '__main__':
    raise SystemExit(main())
