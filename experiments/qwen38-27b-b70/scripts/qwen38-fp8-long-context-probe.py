#!/usr/bin/env python3
"""Long-context probe for the FP8 lane: can the server read and use a window far beyond 33K tokens, exactly?

Client only (CPU): builds a ledger of numbered records with random codes up to a target token count, asks for the
codes of a few records spread from the start to the end, and records time to first token (prompt reading), decode
rate, whether every code came back exactly, and the answer's token ids (so two servers can be compared bit for bit).

  python3 qwen38-fp8-long-context-probe.py --base-url http://127.0.0.1:18196 --model qwen38-27b-fp8 \
      --tokenizer /mnt/fast-ai/llm-models/qwen3.8-27b-fp8 --lengths 8000,30000,60000,120000,200000,250000 --out probe.json

Needs `transformers` for the tokenizer only (~/.venvs/vllm-xpu has it). Operator diagnostic; not a quality benchmark.
"""
from __future__ import annotations

import argparse
import json
import random
import time
import urllib.request
from pathlib import Path

LETTERS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'


def code(rng: random.Random) -> str:
    return (''.join(rng.choice(LETTERS) for _ in range(3)) + '-' + ''.join(rng.choice('0123456789') for _ in range(5))
            + '-' + ''.join(rng.choice(LETTERS) for _ in range(2)))


def build(tok, target_tokens: int, seed: int, asks: int):
    """Ledger of `Record NNNNNN: code XXX-00000-XX` lines sized to target_tokens, and a question about `asks` records."""
    rng = random.Random(seed)
    head = ('The following is a ledger of records. Each record has a number and a code. '
            'Read it carefully; questions about specific records follow at the end.\n\n')
    lines, codes = [], {}
    per_line = len(tok(f'Record 000000: code {code(random.Random(0))}\n', add_special_tokens=False)['input_ids'])
    count = max(asks, (target_tokens - 220) // per_line)
    for i in range(count):
        c = code(rng)
        codes[i] = c
        lines.append(f'Record {i:06d}: code {c}\n')
    # shrink until the whole prompt fits the target (tokenisation of digits varies a little by number)
    while True:
        picks = sorted({0, count - 1} | {int(count * (j + 1) / (asks - 1)) for j in range(asks - 2)} if asks > 2 else {0, count - 1})
        picks = [min(p, count - 1) for p in picks][:asks]
        question = ('\nQuestion: what are the codes of records ' + ', '.join(f'{p:06d}' for p in picks)
                    + '? Answer with the codes only, in that order, separated by commas.\nAnswer:')
        prompt = head + ''.join(lines[:count]) + question
        n = len(tok(prompt, add_special_tokens=False)['input_ids'])
        if n <= target_tokens or count <= asks:
            return prompt, n, [codes[p] for p in picks], picks
        count -= max(1, (n - target_tokens) // per_line + 1)


def ask(base: str, model: str, prompt: str, max_tokens: int, timeout: int):
    body = json.dumps({'model': model, 'prompt': prompt, 'max_tokens': max_tokens, 'temperature': 0, 'seed': 42,
                       'stream': True, 'return_token_ids': True,
                       'stream_options': {'include_usage': True}}).encode()
    req = urllib.request.Request(base.rstrip('/') + '/v1/completions', data=body, headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    first = None
    text, ids, usage, stamps = '', [], None, []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'):
                continue
            payload = line[5:].strip()
            if payload == '[DONE]':
                break
            chunk = json.loads(payload)
            if chunk.get('usage'):
                usage = chunk['usage']
            for choice in chunk.get('choices', []):
                piece = choice.get('text') or ''
                new_ids = choice.get('token_ids') or []
                if (piece or new_ids) and first is None:
                    first = time.perf_counter()
                text += piece
                ids += new_ids
                if new_ids:
                    stamps.append((time.perf_counter(), len(new_ids)))
    end = time.perf_counter()
    return {'text': text, 'token_ids': ids, 'usage': usage, 'ttft_s': (first or end) - t0, 'total_s': end - t0,
            'decode_tok_s': (len(ids) - stamps[0][1]) / (end - first) if first and len(stamps) > 1 and end > first else None,
            'steps': len(stamps)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--model', default='qwen38-27b-fp8')
    ap.add_argument('--tokenizer', default='/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
    ap.add_argument('--lengths', default='8000,30000,60000,120000,200000,250000')
    ap.add_argument('--asks', type=int, default=6)
    ap.add_argument('--max-tokens', type=int, default=96)
    ap.add_argument('--seed', type=int, default=20261005)
    ap.add_argument('--repeat', type=int, default=1, help='ask each length this many times (the second shows cache reuse)')
    ap.add_argument('--timeout', type=int, default=3600)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    report = {'schema': 'qwen38-fp8-long-context-probe.v1', 'base_url': a.base_url, 'rows': []}
    for target in [int(x) for x in a.lengths.split(',') if x]:
        prompt, n, expected, picks = build(tok, target, a.seed + target, a.asks)
        for rep in range(a.repeat):
            row = {'target_tokens': target, 'prompt_tokens_client': n, 'repeat': rep, 'asked_records': picks, 'expected': expected}
            try:
                r = ask(a.base_url, a.model, prompt, a.max_tokens, a.timeout)
                got = [c.strip() for c in r['text'].split('\n')[0].split(',')]
                row.update(r, correct=[e in r['text'] for e in expected], all_correct=all(e in r['text'] for e in expected),
                           in_order=got[:len(expected)] == expected,
                           prompt_read_tok_s=n / r['ttft_s'] if r['ttft_s'] else None)
            except Exception as error:  # noqa: BLE001  (a refused length is a result, not a crash)
                row['error'] = f'{type(error).__name__}: {error}'[:400]
            report['rows'].append(row)
            a.out.write_text(json.dumps(report, indent=1) + '\n')
            print(f"PROBE target={target} tokens={n} rep={rep} "
                  + (f"error={row['error']}" if 'error' in row else
                     f"first_token_s={row['ttft_s']:.1f} read_tok_s={row['prompt_read_tok_s']:.0f} "
                     f"decode_tok_s={row['decode_tok_s'] and round(row['decode_tok_s'], 1)} correct={sum(row['correct'])}/{len(expected)} "
                     f"in_order={row['in_order']} out_tokens={len(row['token_ids'])}"), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
