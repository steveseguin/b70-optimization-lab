#!/usr/bin/env python3
"""How fast does the server write at a given context length, and why?

Client only (CPU). One ledger text (prose style, one seed, so each shorter text is a prefix of the longer ones) is
cut at each length and followed by a writing task: `copy` (copy the first records, the same answer at every length)
and `story` (a short story unrelated to the ledger). Each answer is exactly `--tokens` tokens (end of text ignored).
Recorded per request: wait for the first token, writing time after it, and from the server's own counters the number
of draft-and-check steps and accepted draft tokens, so the writing time splits into steps x time per step.

  python3 probe-write-rate-vs-context.py --base-url http://127.0.0.1:18196 --out write-rate.json

Needs the `tokenizers` library only. Operator diagnostic; timings are from one server.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = {
    'copy': '\n\nTask: copy records 000000 to 000029 from the ledger above exactly as written, one per line, with their '
            'remarks.\nCopy:\n',
    'story': '\n\nTask: set the ledger aside and write a short story about a lighthouse keeper who finds a message in a '
             'bottle.\nStory:\n',
}


def load_probe():
    spec = importlib.util.spec_from_file_location('longctx', HERE / 'qwen38-fp8-long-context-probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def counters(base):
    text = urllib.request.urlopen(base.rstrip('/') + '/metrics', timeout=30).read().decode()
    out = {}
    for name, value in re.findall(r'^(vllm:spec_decode_num_\w+?)(?:_total)?(?:\{[^}]*\})? ([0-9.e+]+)$', text, re.M):
        out[name] = out.get(name, 0.0) + float(value)
    return out


def ask(base, model, prompt, tokens, timeout):
    body = {'model': model, 'prompt': prompt, 'max_tokens': tokens, 'min_tokens': tokens, 'ignore_eos': True,
            'temperature': 0, 'seed': 42, 'stream': True, 'stream_options': {'include_usage': True}}
    req = urllib.request.Request(base.rstrip('/') + '/v1/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    first, usage, text = None, None, []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:') or line[5:].strip() == '[DONE]':
                continue
            chunk = json.loads(line[5:].strip())
            usage = chunk.get('usage') or usage
            pieces = [c.get('text') or '' for c in chunk.get('choices', [])]
            text += pieces
            if first is None and any(pieces):
                first = time.perf_counter()
    end = time.perf_counter()
    details = (usage or {}).get('prompt_tokens_details') or {}
    return {'first_token_s': (first or end) - t0, 'write_s': end - (first or end),
            'prompt_tokens': (usage or {}).get('prompt_tokens'), 'cached_tokens': details.get('cached_tokens'),
            'completion_tokens': (usage or {}).get('completion_tokens'), 'text': ''.join(text)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--model', default='qwen38-27b-fp8')
    ap.add_argument('--tokenizer', default='/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
    ap.add_argument('--lengths', default='1000,32000,64000,100000,137000,200000,246000')
    ap.add_argument('--tasks', default='copy,story')
    ap.add_argument('--tokens', type=int, default=512)
    ap.add_argument('--seed', type=int, default=20261017)
    ap.add_argument('--timeout', type=int, default=3600)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    probe = load_probe()
    tok = probe.LightTokenizer(a.tokenizer)
    report = {'schema': 'qwen38-fp8-write-rate-vs-context.v1', 'base_url': a.base_url, 'tokens': a.tokens, 'rows': []}
    for length in [int(x) for x in a.lengths.split(',') if x]:
        prompt, _, _, _ = probe.build(tok, length - 60, a.seed, 2, 'prose')
        body = prompt[:prompt.index('\nQuestion: what are the codes of records')]
        for task in a.tasks.split(','):
            before = counters(a.base_url)
            r = ask(a.base_url, a.model, body + TASKS[task], a.tokens, a.timeout)
            after = counters(a.base_url)
            d = {k: after.get(k, 0.0) - before.get(k, 0.0) for k in after}
            steps = d.get('vllm:spec_decode_num_drafts', 0.0)
            acc = d.get('vllm:spec_decode_num_accepted_tokens', 0.0)
            row = {'length': length, 'task': task, **r, 'counter_deltas': d,
                   'tokens_per_step': round((steps + acc) / steps, 3) if steps else None,
                   'ms_per_step': round(r['write_s'] * 1e3 / steps, 2) if steps else None,
                   'write_tok_s': round((r['completion_tokens'] - 1) / r['write_s'], 2) if r['write_s'] else None}
            report['rows'].append(row)
            a.out.write_text(json.dumps(report, indent=1) + '\n')
            print(f"WRITE length={length} task={task} prompt={r['prompt_tokens']} cached={r['cached_tokens']} "
                  f"first={r['first_token_s']:.1f}s write={r['write_s']:.2f}s tok/s={row['write_tok_s']} "
                  f"steps={steps:.0f} tok/step={row['tokens_per_step']} ms/step={row['ms_per_step']}", flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
