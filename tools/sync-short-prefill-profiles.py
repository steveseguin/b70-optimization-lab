#!/usr/bin/env python3
"""Project the frozen short-input control measurements into package profiles.

Run after updating package metadata; --check verifies rather than writing.
The allocation candidate is deliberately excluded from public measurements.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'experiments/qwen38-27b-b70/data/2026-09-13-short-prefill/summary.json'
REPORT = 'experiments/qwen38-27b-b70/notes/2026-09-13-short-prefill-results.md'
PROFILE_ID = 'short-prompt-server-prefill-control'
PACKAGES = {
    '4b': ('qwen35-4b-w4a16-b70', 1, 3, 'W4A16', 'R308'),
    '9b': ('qwen35-9b-w4a16-b70', 1, 3, 'W4A16', 'R308'),
    '27b-int4': ('qwen38-27b-int4-fixed-k-tp2-b70', 2, 4, 'INT4', 'R304'),
    '27b-fp8': ('qwen38-27b-fp8-tp2-b70', 2, 1, 'FP8', 'R304'),
}


def measured_profiles():
    source = json.loads((ROOT / SOURCE).read_text())
    if not source['complete']:
        raise ValueError('Short-input measurements are incomplete')
    result = {}
    for key, (package, cards, depth, quant, parent) in PACKAGES.items():
        measured = source['profiles'][key]
        if not measured['complete'] or not measured['quality_exact']:
            raise ValueError(f'{key}: incomplete measurements or output mismatch')
        points = []
        for point in measured['points']:
            arms = point['arms']
            value = sum(arms[arm]['server_prefill_tokens_per_s']
                        for arm in ('baseline', 'final-control')) / 2
            points.append({'context_tokens': point['prompt_tokens'], 'value': value,
                           'samples': 2 * point['classes'] * point['repeats_per_class_per_arm']})
        if [p['context_tokens'] for p in points] != [128, 256, 512]:
            raise ValueError(f'{key}: unexpected input lengths')
        card_label = f'{cards} GPU' + ('s' if cards != 1 else '')
        scope = (f'One user, {card_label}, 128–512 input tokens; no saved prompt cache. '
                 'A separate short-input test, using the existing allocation method.')
        result[key] = {
            'id': PROFILE_ID,
            'label': f'Reading speed with a short prompt · {card_label}',
            'public_label': f'Reading speed · {card_label} · {depth}-token draft',
            'metric': 'prefill', 'unit': 'tok/s',
            'x_metric': 'context_tokens', 'x_label': 'Input length (tokens)',
            'scope': scope, 'public_scope': ('How fast the server reads a short prompt before making its first token. ' 'One user; no saved prompt cache. A separate short-input test.'),
            'measurement_kind': 'server_prefill',
            'evidence': REPORT,
            'source_data': SOURCE,
            'operating_profile': {
                'tensor_parallel_size': cards, 'speculative_tokens': depth,
                'quantization': quant, 'parent_runtime': parent,
                'allocation_mode': 'original branch through disabled experimental dispatcher',
                'activations': 'FP16', 'kv_cache': 'native',
                'concurrency': 1, 'max_model_len': 1024,
                'max_num_batched_tokens': 1024, 'max_num_seqs': 1,
                'prefix_caching': False, 'classpad': 0, 'rowchunk': 32,
            },
            'technical_method': (
                'Measured 2026-09-13 on ASRock B70. Input tokens divided by vLLM server prefill '
                'duration (first scheduled execution to first token), obtained from the '
                'one-request histogram delta; not isolated GPU throughput or HTTP TTFT. '
                'Each value is the arithmetic mean of baseline and final-control aggregate '
                'rates. Each arm aggregates three repeats per prose/code/documentation class '
                'by median, then takes the median across the three classes: 18 control requests '
                'per input length. Numeric input IDs; 128 output tokens; ignore_eos enabled; '
                'zero cached tokens. One loaded server per model with a default-off experimental '
                'overlay; controls execute the original allocation branch, not an unmodified '
                'parent process. Complete control outputs matched the qualified parent outputs. '
                'These short-input screening measurements do not promote the allocation '
                'candidate or replace historical decode records. Runtime identities, repeats, '
                'control drift and hash-bound raw evidence are linked in the report.'),
            'promotion_qualified': False,
            'points': points,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    failures = []
    profiles = measured_profiles()
    for key, profile in profiles.items():
        path = ROOT / 'packages' / PACKAGES[key][0] / 'package.json'
        package = json.loads(path.read_text())
        rows = package.setdefault('performance_profiles', [])
        current = next((p for p in rows if p['id'] == PROFILE_ID), None)
        missing_dependencies = [p for p in (REPORT, SOURCE) if p not in package['dependencies']]
        if current != profile or missing_dependencies:
            if args.check:
                failures.append(str(path.relative_to(ROOT)))
            else:
                rows[:] = [p for p in rows if p['id'] != PROFILE_ID]
                rows.append(profile)
                package['dependencies'].extend(missing_dependencies)
                path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + '\n')
    homepage = ROOT / 'index.html'
    html = homepage.read_text()
    for key, profile in profiles.items():
        value = next(p['value'] for p in profile['points'] if p['context_tokens'] == 512)
        expected = f'{value:,.0f}'
        pattern = re.compile(r'(<td\b[^>]*data-prefill-profile="' + re.escape(key)
                             + r'"[^>]*>.*?<a\b[^>]*>)([^<]*)(</a>)', re.S)
        matches = list(pattern.finditer(html))
        if len(matches) != 1:
            failures.append(f'index.html: expected exactly one prefill cell for {key}')
            continue
        if matches[0].group(2) != expected:
            if args.check:
                failures.append(f'index.html: wrong prefill value for {key}')
            else:
                html = pattern.sub(lambda m: m.group(1) + expected + m.group(3), html)
    if not args.check and html != homepage.read_text():
        homepage.write_text(html)
    if failures:
        raise SystemExit('\n'.join(failures))
    print('Verified four short-input prefill profiles and homepage values.' if args.check
          else 'Updated four short-input prefill profiles and homepage values.')


if __name__ == '__main__':
    main()
