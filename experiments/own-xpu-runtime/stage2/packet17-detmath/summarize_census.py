#!/usr/bin/env python3
"""Summarize a completed W-A receipt on CPU; never launches any executable."""
import argparse
import json
from pathlib import Path

UNARY = ('expf', 'logf', 'sqrtf', 'rsqrt-plain', 'reciprocal', 'sinf', 'cosf',
         'rsqrt-barrier', 'rsqrt-corrected')
CANDIDATES = ('rsqrt-plain', 'rsqrt-barrier', 'rsqrt-corrected')


def summarize(path):
    groups = {}
    pilots = {}
    final = None
    with Path(path).open() as f:
        for line in f:
            row = json.loads(line)
            final = row
            kind = row.get('kind')
            if kind == 'coverage-selection':
                name = row['function']
                if name in pilots:
                    raise ValueError('duplicate coverage selection: ' + name)
                pilots[name] = row
                continue
            if kind not in ('native-exhaustive', 'native-stratified', 'triples', 'rope-arguments', 'actual-fixture-inputs'):
                continue
            key = (kind, row['function'])
            group = groups.setdefault(key, dict(kind=kind, function=row['function'], count=0,
                                                differing_bits_results=0, both_nan_encoding_differences=0,
                                                device_vs_separate=0, device_vs_fma=0,
                                                kernel_seconds=0., max_kernel_seconds=0., ulp_histogram=[0] * 34))
            n, diff, both = row['count'], row['different'], row['both_nan_different']
            hist = row['ulp_histogram']
            if row['start'] != group['count'] or n <= 0 or not 0 <= both <= diff <= n:
                raise ValueError('invalid or noncontiguous census coverage')
            if len(hist) != 34 or any(v < 0 for v in hist) or sum(hist) != n or hist[0] != n - diff:
                raise ValueError('invalid ULP histogram')
            group['count'] += n
            group['differing_bits_results'] += diff
            group['both_nan_encoding_differences'] += both
            group['device_vs_separate'] += row.get('device_vs_separate', 0)
            group['device_vs_fma'] += row.get('device_vs_fma', 0)
            group['kernel_seconds'] += row['seconds']
            group['max_kernel_seconds'] = max(group['max_kernel_seconds'], row['seconds'])
            group['ulp_histogram'] = [a + b for a, b in zip(group['ulp_histogram'], hist)]
    if not final or final.get('complete') is not True:
        raise ValueError('census did not finish')
    unary = {}
    for name in UNARY:
        p = pilots.get(name)
        if not p or p['selected_bits'] not in (28, 32):
            raise ValueError('missing required unary coverage: ' + name)
        kind = 'native-exhaustive' if p['selected_bits'] == 32 else 'native-stratified'
        g = groups.get((kind, name))
        if not g or g['count'] != 1 << p['selected_bits']:
            raise ValueError('incomplete unary coverage: ' + name)
        unary[name] = g
        g['coverage_selection'] = p
    for g in groups.values():
        # A one-NaN-versus-finite/infinity mismatch is NOT subtracted. Only two
        # NaN results with different signs/payloads are exempted from this gate.
        g['semantic_or_non_nan_bit_differences'] = g['differing_bits_results'] - g['both_nan_encoding_differences']
    for name in ('division', 'mul-add', 'fma', 'separate'):
        if groups.get(('triples', name), {}).get('count') != 1 << 26:
            raise ValueError('incomplete triple coverage: ' + name)
    fixture_count = sum(g['count'] for (kind, _), g in groups.items() if kind == 'actual-fixture-inputs')
    if fixture_count <= 0 or fixture_count != final.get('fixture_calls'):
        raise ValueError('incomplete actual fixture coverage')
    if groups.get(('rope-arguments', 'pow-sin-cos-rope'), {}).get('count') != 3 * 32 * 151:
        raise ValueError('incomplete RoPE argument coverage')
    def relevant(name, field):
        return unary[name][field] + groups.get(('actual-fixture-inputs', name), {}).get(field, 0)
    sqrt_ok = relevant('sqrtf', 'semantic_or_non_nan_bit_differences') == 0
    candidates = {}
    for name in CANDIDATES:
        differences = relevant(name, 'semantic_or_non_nan_bit_differences')
        candidates[name] = dict(exact_on_tested_inputs=sqrt_ok and differences == 0,
                                sqrt_reference_gate_passed=sqrt_ok,
                                non_exempt_differences=differences,
                                ignored_both_nan_encoding_differences=relevant(name, 'both_nan_encoding_differences'),
                                exhaustive_unary_evidence=pilots[name]['selected_bits'] == pilots['sqrtf']['selected_bits'] == 32)
    choice = next((name for name in ('rsqrt-barrier', 'rsqrt-plain', 'rsqrt-corrected')
                   if candidates[name]['exact_on_tested_inputs']), None)
    return dict(schema='own-runtime.packet17.census-summary.v1', complete=True,
                nan_policy='Only differing encodings where BOTH results are NaNs are exempt; one-NaN mismatches fail.',
                functions=list(groups.values()), reciprocal_sqrt_candidates=candidates,
                selected_spelling=choice,
                decision='candidate matches on tested unary and fixture inputs; check coverage before claiming full-domain equality'
                if choice else 'no candidate qualified; reciprocal-square-root device identity remains blocked',
                selection_policy='prefer current integer-barrier spelling, then plain, then corrected')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    result = summarize(a.input)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('selected_spelling', 'decision', 'reciprocal_sqrt_candidates')}, indent=2))


if __name__ == '__main__':
    main()
