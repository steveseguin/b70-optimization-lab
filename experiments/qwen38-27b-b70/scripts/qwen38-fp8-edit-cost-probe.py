#!/usr/bin/env python3
"""What does an edit in the middle of a long context cost on a server with the exact prefix cache?

Client only (CPU). For each context length: a ledger text is read once (cold), sent again (full reuse), and then sent
with a few lines removed at different places: in the last block, at 90 %, at 50 % and at 10 % of its length. Each
edited prompt is sent twice. Recorded per request: tokens reported as served from the cache, wait for the first
token, and how many tokens lie after the edit (what an exact scheme has to re-read at the least).

The edits go from the end of the text towards its start, so the expensive ones come last and each still finds the
original text's cache.

  python3 qwen38-fp8-edit-cost-probe.py --base-url http://127.0.0.1:18196 --lengths 30000,120000,200000 --out edit-cost.json

Needs the `tokenizers` library only. Operator diagnostic; timings are from one server.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_probe():
    spec = importlib.util.spec_from_file_location('longctx', HERE / 'qwen38-fp8-long-context-probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ask(base, model, prompt, max_tokens, timeout):
    body = {'model': model, 'prompt': prompt, 'max_tokens': max_tokens, 'temperature': 0, 'seed': 42, 'stream': True,
            'stream_options': {'include_usage': True}}
    req = urllib.request.Request(base.rstrip('/') + '/v1/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    first, usage = None, None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:') or line[5:].strip() == '[DONE]':
                continue
            chunk = json.loads(line[5:].strip())
            usage = chunk.get('usage') or usage
            if first is None and any((c.get('text') or '') for c in chunk.get('choices', [])):
                first = time.perf_counter()
    end = time.perf_counter()
    details = (usage or {}).get('prompt_tokens_details') or {}
    return {'first_token_s': (first or end) - t0, 'prompt_tokens': (usage or {}).get('prompt_tokens'),
            'cached_tokens': details.get('cached_tokens')}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--model', default='qwen38-27b-fp8')
    ap.add_argument('--tokenizer', default='/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
    ap.add_argument('--lengths', default='30000,120000,200000')
    ap.add_argument('--places', default='last,0.9,0.5,0.1', help='where the lines are removed: a fraction of the text, or "last"')
    ap.add_argument('--remove-lines', type=int, default=4, help='lines removed per edit (about 75 tokens each in prose style)')
    ap.add_argument('--seed', type=int, default=20261005)
    ap.add_argument('--timeout', type=int, default=3600)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    probe = load_probe()
    tok = probe.LightTokenizer(a.tokenizer)
    count = lambda text: len(tok(text, add_special_tokens=False)['input_ids'])
    report = {'schema': 'qwen38-fp8-edit-cost-probe.v1', 'base_url': a.base_url, 'rows': []}

    def record(length, label, prompt, after_edit, note):
        r = ask(a.base_url, a.model, prompt, 8, a.timeout)
        row = {'length': length, 'request': label, 'tokens_after_edit': after_edit, **r, 'note': note}
        report['rows'].append(row)
        a.out.write_text(json.dumps(report, indent=1) + '\n')
        print(f"EDIT length={length} request={label} prompt_tokens={r['prompt_tokens']} cached={r['cached_tokens']} "
              f"after_edit={after_edit} first_token_s={r['first_token_s']:.2f}", flush=True)

    for length in [int(x) for x in a.lengths.split(',') if x]:
        prompt, n, _, _ = probe.build(tok, length, a.seed + length, 6, 'prose')
        head_end = prompt.index('Record 000000')
        tail_start = prompt.index('\nQuestion: what are the codes of records')
        lines = prompt[head_end:tail_start].splitlines(keepends=True)
        question = prompt[tail_start:]
        record(length, 'cold', prompt, None, 'first read of this text')
        record(length, 'repeat', prompt, 0, 'the same text again')
        for place in a.places.split(','):
            at = len(lines) - a.remove_lines - 2 if place == 'last' else int(len(lines) * float(place))
            edited = prompt[:head_end] + ''.join(lines[:at] + lines[at + a.remove_lines:]) + question
            after = count(''.join(lines[at + a.remove_lines:]) + question)
            record(length, f'edit@{place}', edited, after, f'{a.remove_lines} lines removed at line {at} of {len(lines)}')
            record(length, f'edit@{place}-again', edited, after, 'the same edited text again')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
