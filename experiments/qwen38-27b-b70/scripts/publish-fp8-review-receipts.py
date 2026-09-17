#!/usr/bin/env python3
"""Copy the 2026-09-16 review campaign receipts into the repository and derive the two-card package's measured
profiles from them. Read-only against the raw root; writes only under experiments/.../data and the package manifest.

usage: publish-fp8-review-receipts.py [--raw /mnt/fast-ai/bench-results/fp8-review-20260916] [--write-package]
"""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-16-fp8-review'
PACKAGE = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/package.json'
STAGES = ['tp1-mtp0', 'tp1-pkg-recommended', 'tp2-mtp0', 'tp2-mtp5', 'tp2-mtp4', 'tp2-mtp3', 'tp2-mtp1-shortlist', 'tp2-mtp1-control',
          'service-restored-6']
TP2_SCOPE = ('Two Intel Arc Pro B70s, official Qwen3.8-27B-FP8, FP16 activations and KV, one user, prompt caching off, R310 image, '
             '33,024-token context. Exact 2K/8K/16K-token inputs from unrepeated prose, code and documentation, 128-token '
             'continuations, two repeats; median within each of three content types, then across types (6 requests per point). '
             'Every continuation is identical to the no-MTP server. ')


def copy_receipts(raw):
    DATA.mkdir(parents=True, exist_ok=True)
    for name in ('results.json', 'campaign.log'):
        shutil.copy(raw / name, DATA / name)
    for stage in STAGES:
        for src, dst in ((raw / f'{stage}-strict/performance.json', f'{stage}-strict-performance.json'),
                         (raw / f'{stage}-strict/canaries.json', f'{stage}-strict-canaries.json'),
                         (raw / f'{stage}-strict/campaign-identity.json', f'{stage}-strict-identity.json'),
                         (raw / f'{stage}-strict-vs-reference.json', f'{stage}-strict-vs-reference.json'),
                         (raw / f'{stage}-context/summary.json', f'{stage}-context-summary.json'),
                         (raw / f'{stage}-ladder-vs-mtp0.json', f'{stage}-ladder-vs-mtp0.json'),
                         (raw / f'{stage}-quality.json', f'{stage}-quality.json'),
                         (raw / f'{stage}-history/summary.json', f'{stage}-history-summary.json'),
                         (raw / stage / 'launch.json', f'{stage}-launch.json'),
                         (raw / stage / 'state.json', f'{stage}-state.json'),
                         (raw / stage / 'container-final.json', f'{stage}-container-final.json')):
            if src.exists():
                shutil.copy(src, DATA / dst)
    # the one-card no-MTP ladder came from the first attempt (same image, same recipe)
    first = raw.parent / 'fp8-review-20260916-attempt1/tp1-mtp0-ladder.json'
    if first.exists():
        shutil.copy(first, DATA / 'tp1-mtp0-ladder.json')
    for name in ('tp2-mtp0-ladder.json',):
        if (raw / name).exists():
            shutil.copy(raw / name, DATA / name)


def strict_median(stage):
    path = DATA / f'{stage}-strict-performance.json'
    if not path.exists():
        return None
    return json.loads(path.read_text())['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def context_points(stage, metric):
    summary = json.loads((DATA / f'{stage}-context-summary.json').read_text())
    key = {'decode': 'decode_token_1_to_100_tps', 'prefill': 'server_prefill_tokens_per_s'}[metric]
    return [{'context_tokens': int(length), 'value': round(row[key], 3 if metric == 'decode' else 1), 'samples': row['samples']}
            for length, row in summary['by_length'].items()]


def profiles():
    ev = 'experiments/qwen38-27b-b70/data/2026-09-16-fp8-review/'
    out = []
    for stage, label, tag in (('tp2-mtp5', 'MTP depth 5 · INT4 draft shortlist', 'recommended (MTP depth 5)'),
                              ('tp2-mtp0', 'No MTP', 'no MTP')):
        for metric, what, how in (('decode', 'Writing speed after the prompt', 'Writing speed is tokens 1-100 after the first token.'),
                                  ('prefill', 'Prompt reading speed', 'Prompt reading is input tokens divided by server prefill time from the vLLM histogram.')):
            out.append({'id': f'r310-{metric}-vs-context-{stage}', 'label': f'{what} · {label}', 'metric': metric, 'unit': 'tok/s',
                        'x_metric': 'context_tokens', 'x_label': 'Input tokens', 'scope': TP2_SCOPE + how,
                        'evidence': ev + f'{stage}-context-summary.json', 'points': context_points(stage, metric),
                        'public_label': f'{what} · {tag}'})
    depths = [(0, 'tp2-mtp0'), (1, 'tp2-mtp1-shortlist'), (3, 'tp2-mtp3'), (4, 'tp2-mtp4'), (5, 'tp2-mtp5')]
    points = [{'speculative_tokens': d, 'value': round(strict_median(s), 3), 'samples': 1} for d, s in depths if strict_median(s)]
    out.append({'id': 'r310-decode-vs-mtp-depth', 'label': 'Writing speed by MTP depth · INT4 draft shortlist', 'metric': 'decode',
                'unit': 'tok/s', 'x_metric': 'speculative_tokens', 'x_label': 'MTP draft tokens',
                'scope': 'Strict 12-prompt suite (512-token answers, class-balanced median of tokens 1-100) on fresh R310 two-card servers '
                         'in one session, 33,024-token context; every depth 12/12 identical to no MTP and 64/64 on the sequential oracle. '
                         'Depth 1 here uses the draft shortlist; the depth-1 control without it is in results.json.',
                'evidence': ev + 'results.json', 'points': points, 'public_label': 'Writing speed by MTP depth (strict suite)'})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw', type=Path, default=Path('/mnt/fast-ai/bench-results/fp8-review-20260916'))
    ap.add_argument('--write-package', action='store_true')
    a = ap.parse_args()
    copy_receipts(a.raw)
    new = profiles()
    print(json.dumps([(p['id'], [(x.get('context_tokens', x.get('speculative_tokens')), x['value']) for x in p['points']]) for p in new], indent=0))
    if a.write_package:
        package = json.loads(PACKAGE.read_text())
        keep = [p for p in package['performance_profiles'] if not p['id'].startswith('r310-')]
        package['performance_profiles'] = new + keep
        PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + '\n')
        print('package profiles written')


if __name__ == '__main__':
    main()
