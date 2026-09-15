#!/usr/bin/env python3
"""Tabulate one-card FP8 rungs across every measured dimension (offline, read-only).

For each rung directory under the campaign root: launch settings (depth, draft
head, overlays, context), KV tokens, strict class-balanced decode (tokens 1-100),
strict full-answer wall rate, per-class medians, identity vs a reference strict
attempt, and the context screen (server prefill, decode after prompt, pass/fail).
Prints a Markdown table and writes JSON next to it.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def rung_row(root: Path, label: str, reference: str):
    launch = load(root / label / 'launch.json') or {}
    rung = launch.get('rung', {})
    log = (root / label / 'server.log')
    kv = None
    if log.exists():
        found = re.findall(r'GPU KV cache size: ([\d,]+)', log.read_text(errors='replace'))
        kv = int(found[-1].replace(',', '')) if found else None
    row = dict(label=label, mtp=rung.get('mtp'), context=rung.get('max_model_len'), mem=rung.get('mem'),
               draft=('fp16-shortlist' if rung.get('draft_fp16_shortlist') else 'int4-shortlist' if rung.get('shortlist')
                      else 'int4' if rung.get('draft_int4') else 'fp16-shared'),
               gdn_groups=rung.get('gdn_head_groups', 0), fa_rows=rung.get('fa_verify_rows', False),
               image=str(rung.get('image', ''))[:19], kv_tokens=kv)
    perf = load(root / f'{label}-strict' / 'performance.json')
    if perf:
        summary = perf['summary']
        row.update(strict_tok_s=round(summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median'], 3),
                   strict_wall_tok_s=round(summary['tok_s_wall_full']['median'], 2),
                   strict_gate=perf['realistic_final_gate']['passed'],
                   classes={k: round(v, 1) for k, v in
                            summary['class_balanced_tok_s_1_100_intervals_after_ttft']['class_medians'].items()})
    parity = load(root / f'parity-{label}-vs-{reference}.json')
    if parity:
        row['strict_exact'] = f"{parity['comparison']['exact_prompts']}/{parity['comparison']['total_prompts']}"
    context = load(root / f'{label}-context' / 'summary.json')
    if context:
        row['context_passed'] = context.get('passed')
        row['context_error'] = context.get('error')
        for length, values in (context.get('by_length') or {}).items():
            row[f'prefill_{length}'] = round(values['server_prefill_tokens_per_s'])
            row[f'decode_after_{length}'] = round(values['decode_token_1_to_100_tps'], 1)
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('/mnt/fast-ai/bench-results/optimization-validation-20260915'))
    ap.add_argument('--reference', default='35')
    ap.add_argument('labels', nargs='+')
    args = ap.parse_args()
    rows = [rung_row(args.root, label, args.reference) for label in args.labels]
    cols = ['label', 'mtp', 'draft', 'context', 'kv_tokens', 'strict_tok_s', 'strict_wall_tok_s', 'strict_exact',
            'context_passed', 'prefill_512', 'prefill_2048', 'prefill_12288', 'decode_after_512',
            'decode_after_2048', 'decode_after_12288']
    print('| ' + ' | '.join(cols) + ' |')
    print('|' + '---|' * len(cols))
    for row in rows:
        print('| ' + ' | '.join(str(row.get(c, '')) for c in cols) + ' |')
    out = args.root / 'fp8-tp1-rung-summary.json'
    out.write_text(json.dumps(rows, indent=1))
    print(f'\nwrote {out}')


if __name__ == '__main__':
    main()
