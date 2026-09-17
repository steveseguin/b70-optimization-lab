#!/usr/bin/env python3
"""Move the one-card FP8 package manifest to the 24,576-token profile (2,048-token prefill chunk) from receipts.

Reads the one-card 24K campaign receipts (data/2026-09-17-fp8-onecard-24k, copied by publish-fp8-review-receipts.py
--data) and the follow-up probe (data/2026-09-17-fp8-followup/tp1-ctx-24k-b2048-*), which together are the two fresh
servers at this setting. Rewrites the recommended-profile fields and the two recommended context charts; the
no-quantization and no-MTP charts and the depth chart stay as measured on September 15-16.
"""
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'packages/qwen38-27b-fp8-tp1-b70/package.json'
CAMPAIGN = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-onecard-24k/'
FOLLOWUP = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-followup/'
SCOPE = ('One Intel Arc Pro B70, official Qwen3.8-27B-FP8, FP16 activations and KV, one user, prompt caching off, R310 image at the '
         '24,576-token context with a 2,048-token prefill chunk, through the package launcher. Exact 2K/8K/16K-token inputs from '
         'unrepeated prose, code and documentation, 128-token continuations, two repeats; median within each of three content '
         'types, then across types (6 requests per point). Every continuation is identical to the no-MTP server. ')


def strict_median(path):
    return json.loads((ROOT / path).read_text())['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def points(path, metric):
    by = json.loads((ROOT / path).read_text())['by_length']
    key = {'decode': 'decode_token_1_to_100_tps', 'prefill': 'server_prefill_tokens_per_s'}[metric]
    return [{'context_tokens': int(k), 'value': round(v[key], 3 if metric == 'decode' else 1), 'samples': v['samples']} for k, v in by.items()]


def main():
    results = json.loads((ROOT / CAMPAIGN / 'results.json').read_text())
    stage = results['tp1-pkg-24k']
    assert stage['strict']['exact'] == '12/12' and stage['ladder']['verdict'] == 'exact' and stage['context']['passed'] and \
        stage['quality']['baseline_match_all'] and not stage['history']['divergent'] and not stage['history']['logprob_divergent'], stage
    pair = [strict_median(FOLLOWUP + 'tp1-ctx-24k-b2048-strict-performance.json'), strict_median(CAMPAIGN + 'tp1-pkg-24k-strict-performance.json')]
    package = json.loads(PACKAGE.read_text())
    lib = package['library']
    for key in ('summary', 'public_summary'):
        lib[key] = lib[key].replace('16,384 tokens of context', '24,576 tokens of context')
    lib['benchmark_status'] = (f'Strict 12-prompt suite on two fresh servers at the 24,576-token context: {pair[0]:.2f} / {pair[1]:.2f} tok/s, '
                               '12/12 identical to no MTP; 64-prompt sequential oracle plus queued passes 64/64; 2K/8K/16K prompts, a chat '
                               'quality suite and a 21-request logprob replay all match no MTP (September 17). The 16,384-token setting '
                               'measured the same on September 16; a 2,048-token prefill chunk frees the memory for the longer context '
                               'at no measured cost. Clean-host install and multiple users are untested.')
    lib['featured_metric'] = {
        'value': statistics.median(pair), 'unit': 'tok/s', 'label': 'Writing speed · MTP depth 5 · one card',
        'scope': (f'Median of two fresh R310 servers ({pair[0]:.3f} / {pair[1]:.3f}) at a 24,576-token context (2,048-token prefill chunk) on '
                  'the fixed 12-prompt six-class suite, 512-token answers, class-balanced median of tokens 1-100, cache zero, canaries '
                  'passed, 12/12 complete outputs identical to no-MTP decoding, 64/64 on the sequential oracle.'),
        'evidence': CAMPAIGN + 'tp1-pkg-24k-strict-performance.json'}
    tags = lib['tags']
    if '24K context' not in tags:
        tags.append('24K context')
    setup = package['recommended_setup']
    setup.update(max_model_len=24576, max_num_batched_tokens=2048, evidence='experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md',
                 strict_pair_decode_tokens_s=pair, previous_context={'max_model_len': 16384, 'max_num_batched_tokens': 4096,
                                                                     'strict_pair_decode_tokens_s': [53.57586792283578, 53.45447005701281],
                                                                     'evidence': 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-one-card-followups.md'})
    package['missing'] = [m.replace('contexts above 16,384 tokens on one card', 'contexts above 24,576 tokens on one card') for m in package['missing']]
    for profile in package['performance_profiles']:
        if profile['id'] == 'decode-vs-context-recommended':
            profile.update(scope=SCOPE + 'Writing speed is tokens 1-100 after the first token.', evidence=CAMPAIGN + 'tp1-pkg-24k-context-summary.json',
                           points=points(CAMPAIGN + 'tp1-pkg-24k-context-summary.json', 'decode'))
        if profile['id'] == 'prefill-vs-context-recommended':
            profile.update(scope=SCOPE + 'Prompt reading is input tokens divided by server prefill time from the vLLM histogram.',
                           evidence=CAMPAIGN + 'tp1-pkg-24k-context-summary.json', points=points(CAMPAIGN + 'tp1-pkg-24k-context-summary.json', 'prefill'))
    deps = package['dependencies']
    for item in (CAMPAIGN + 'results.json', CAMPAIGN + 'tp1-pkg-24k-strict-performance.json', CAMPAIGN + 'tp1-pkg-24k-strict-vs-reference.json',
                 CAMPAIGN + 'tp1-pkg-24k-context-summary.json', CAMPAIGN + 'tp1-pkg-24k-ladder-vs-mtp0.json', CAMPAIGN + 'tp1-pkg-24k-quality.json',
                 CAMPAIGN + 'tp1-pkg-24k-history-summary.json', FOLLOWUP + 'tp1-ctx-24k-b2048-strict-performance.json',
                 FOLLOWUP + 'tp1-ctx-24k-b2048-context-summary.json', FOLLOWUP + 'tp1-ctx-24k-b2048-ladder-vs-mtp0.json',
                 FOLLOWUP + 'results.json', 'experiments/qwen38-27b-b70/scripts/run-20260917-fp8-onecard-24k-campaign.py',
                 'experiments/qwen38-27b-b70/scripts/run-20260917-fp8-followup-campaign.py',
                 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py',
                 'experiments/qwen38-27b-b70/scripts/compare-ladder-oracles.py',
                 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md'):
        if item not in deps:
            deps.append(item)
    PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + '\n')
    print(f'one-card manifest updated: featured {statistics.median(pair):.3f} tok/s from {pair}')


if __name__ == '__main__':
    main()
