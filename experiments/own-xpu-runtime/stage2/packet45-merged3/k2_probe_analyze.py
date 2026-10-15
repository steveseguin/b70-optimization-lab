#!/usr/bin/env python3
"""Analyze actual autoregressive g2 guesses; never infer them from adjacent g1 hits.

Input is a diagnostic suite's run/ directory (or its parent window directory).
Forecasts are projections, never a qualifying performance result.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def samples(receipt, probe):
    need(receipt.get('passed') is True, 'request did not pass target exactness')
    need(receipt.get('diagnostic_unsealed') is True and receipt.get('qualifying') is False
         and receipt.get('mtp_k2_probe') is True, 'not a diagnostic k2 request')
    tokens = receipt['tokens']
    first = receipt['prompt_tokens']
    need(type(first) is int and first > 0 and tokens, 'missing emitted tokens/position origin')
    normal = {r['position']: r['guess'] for r in receipt['draft_rows'] if r.get('guess') is not None}
    need(set(normal) == set(range(first, first+len(tokens))), 'not every emitted position has a normal draft guess')
    need(not any(r.get('provider_error') for r in receipt['draft_rows']), 'provider failure would bias acceptance')
    seen = set()
    rows = []
    censored = 0
    for row in probe:
        need(row.get('diagnostic_unsealed') is True and row.get('qualifying') is False,
             'probe marker mismatch')
        need(not row.get('skipped'), 'capacity-censored probe; use an admitted complete run')
        pos = row['g1_position']
        need(pos not in seen, 'duplicate probe position')
        seen.add(pos)
        need(row.get('schema') == 'packet45.mtp-k2-probe.v1', 'probe schema')
        need(row['g2_position'] == pos + 1, 'g2 must be the next position')
        need(row['g1'] == normal.get(pos), 'probe g1 differs from published normal guess')
        need(row['embedding_token'] == row['g1'] and row['state_restored'] is True,
             'autoregressive embedding/state restoration missing')
        need(row['hidden_source'] == 'previous-draft-pre-final-mixer-four-stream', 'wrong hidden source')
        need(row['context_extent_before'] == row['context_extent_restored'], 'binding extent not restored')
        for key in ('extra_step_ms', 'first_step_ms', 'backup_ms', 'restore_and_check_ms'):
            need(math.isfinite(row[key]) and row[key] >= 0, 'invalid timing '+key)
        i = pos - first
        need(0 <= i < len(tokens), 'g1 not aligned to emitted output')
        hit1 = row['g1'] == tokens[i]
        hit2 = row['g2'] == tokens[i+1] if i+1 < len(tokens) else None
        censored += hit2 is None
        rows.append(dict(g1_correct=hit1, g2_correct=hit2, **{
            k: row[k] for k in ('extra_step_ms', 'first_step_ms', 'backup_ms', 'restore_and_check_ms')}))
    need(seen == set(normal), 'missing or additional probe samples')
    need(rows, 'no probe samples')
    return rows, censored


def summarize(rows):
    paired = [r for r in rows if r['g2_correct'] is not None]
    first_hits = sum(r['g1_correct'] for r in paired)
    both_hits = sum(r['g1_correct'] and r['g2_correct'] for r in paired)
    med = lambda key: statistics.median(r[key] for r in paired) if paired else None
    return dict(g1_samples=len(rows), paired_samples=len(paired),
                g1_correct_all=sum(r['g1_correct'] for r in rows),
                p_g1_all=sum(r['g1_correct'] for r in rows)/len(rows) if rows else None,
                g1_correct_paired=first_hits, both_correct=both_hits,
                g2_correct_unconditional=sum(r['g2_correct'] for r in paired),
                p_g1=first_hits/len(paired) if paired else None,
                p_g2_given_g1=both_hits/first_hits if first_hits else None,
                p_g2_unconditional=sum(r['g2_correct'] for r in paired)/len(paired) if paired else None,
                first_drafter_ms_median=med('first_step_ms'),
                extra_drafter_ms_median=med('extra_step_ms'),
                backup_ms_median=med('backup_ms'), restore_and_check_ms_median=med('restore_and_check_ms'))


def forecast(stats, baseline=39.422009, verify3=(40., 45., 50., 55.)):
    p1, q2 = stats['p_g1'], stats['p_g2_given_g1']
    need(p1 is not None, 'not enough paired samples for a forecast')
    draft = stats['first_drafter_ms_median'] + stats['extra_drafter_ms_median']
    emitted = 1 + p1 + stats['both_correct']/stats['paired_samples']
    budget = 1000*emitted/baseline - draft
    return dict(projected_not_measured=True, qualifying=False, baseline_tok_s=baseline,
                expected_tokens_per_k2_cycle=emitted, drafter_ms=draft,
                formula='1000*(1+p1+p1*q2)/(T3+D1+D2)',
                two_position_k1_historical_threshold_ms=42.52,
                distinction='42.52 ms is the prior k=1 two-position verification budget; '
                            'k=2 with a bonus token requires three target positions. T3 is unmeasured.',
                k2_three_position_verification_must_be_below_ms=budget,
                excluded_diagnostic_costs='host state backup, restore/check, logging; never use probe suite tok/s',
                scenarios=[dict(verify_three_positions_ms=t, projected_tok_s=1000*emitted/(t+draft)) for t in verify3])


def analyze(root):
    root = Path(root)
    if (root/'run').is_dir():
        root /= 'run'
    files = sorted(root.glob('repeat-*/*/receipt.json'))
    need(files, 'no suite request receipts')
    groups = {}
    all_rows = []
    evidence = []
    censored = 0
    for file in files:
        receipt = json.loads(file.read_text())
        log = file.parent/'rank1/mtp-k2-probe.jsonl'
        probe = [json.loads(line) for line in log.read_text().splitlines()]
        rows, end = samples(receipt, probe)
        cls = receipt['prompt_class']
        need(cls and cls != 'unclassified', 'missing suite prompt class')
        groups.setdefault(cls, []).extend(rows)
        all_rows.extend(rows)
        censored += end
        evidence.append(dict(request=str(file), request_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                             probe_sha256=hashlib.sha256(log.read_bytes()).hexdigest(), samples=len(rows)))
    stats = summarize(all_rows)
    return dict(schema='packet45.mtp-k2-analysis.v1', diagnostic_unsealed=True, qualifying=False,
                requests=len(files), end_of_request_g2_censored=censored, all=stats,
                per_class={k: summarize(v) for k, v in sorted(groups.items())},
                forecast=forecast(stats), evidence=evidence,
                uncertainty='Correlated positions within only 12 prompts; acceptance is empirical. '
                            'No binomial independence assumption, and T3 must be measured separately.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    row = analyze(args.suite)
    args.output.write_text(json.dumps(row, indent=2)+'\n')
    print(json.dumps(row, indent=2))


if __name__ == '__main__':
    main()
