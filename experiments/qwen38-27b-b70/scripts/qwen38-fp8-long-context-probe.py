#!/usr/bin/env python3
"""Long-context probe for the FP8 lane: can the server read and use a window far beyond 33K tokens, exactly?

Client only (CPU): builds a ledger of numbered records with random codes up to a target token count, asks for the
codes of a few records spread from the start to the end, and records time to first token (prompt reading), decode
rate, whether every code came back exactly, and the answer's token ids (so two servers can be compared bit for bit).

  python3 qwen38-fp8-long-context-probe.py --base-url http://127.0.0.1:18196 --model qwen38-27b-fp8 \
      --tokenizer /mnt/fast-ai/llm-models/qwen3.8-27b-fp8 --lengths 8000,30000,60000,120000,200000,250000 --out probe.json

Needs the `tokenizers` library only (~/.venvs/vllm-xpu has it). Operator diagnostic; not a quality benchmark.
"""
from __future__ import annotations

import argparse
import json
import random
import time
import urllib.request
from pathlib import Path

LETTERS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'


class LightTokenizer:
    """The model's tokenizer through the `tokenizers` library alone. Importing `transformers` costs about a gigabyte of
    host memory for a moment, and beside a two-card server with the full window that was enough to trip the host
    memory guard (2026-10-05, the guard stopped the server as this client started)."""

    def __init__(self, path):
        from tokenizers import Tokenizer
        self.t = Tokenizer.from_file(str(Path(path) / 'tokenizer.json'))

    def __call__(self, text, add_special_tokens=False):
        return {'input_ids': self.t.encode(text, add_special_tokens=add_special_tokens).ids}

    def decode(self, ids, **_):
        return self.t.decode(list(ids), skip_special_tokens=False)


def code(rng: random.Random) -> str:
    return (''.join(rng.choice(LETTERS) for _ in range(3)) + '-' + ''.join(rng.choice('0123456789') for _ in range(5))
            + '-' + ''.join(rng.choice(LETTERS) for _ in range(2)))


WORDS = ('the of and to in is that it was for on are as with his they at be this from have or by one had not but what all '
         'were when we there can an your which their said if do will each about how up out them then she many some so '
         'these would other into has more her two like him see time could no make than first been its who now people my '
         'made over did down only way find use may water long little very after words called just where most know get '
         'through back much before go good new write our used me man too any day same right look think also around '
         'another came come work three word must because does part even place well such here take why things help put '
         'years different away again off went old number great tell men say small every found still between name should '
         'home big give air line set own under read last never us left end along while might next sound below saw '
         'something thought both few those always looked show large often together asked house world going want').split()


def build(tok, target_tokens: int, seed: int, asks: int, style: str = 'ledger'):
    """Ledger of `Record NNNNNN: code XXX-00000-XX` lines sized to target_tokens, and a question about `asks` records.
    style 'prose' puts about forty ordinary words after each record, so the codes are a small part of the text."""
    rng = random.Random(seed)
    head = ('The following is a ledger of records. Each record has a number and a code. '
            'Read it carefully; questions about specific records follow at the end.\n\n')
    lines, codes = [], {}
    filler = (lambda r: '. Remark: ' + ' '.join(r.choice(WORDS) for _ in range(40)) + '.') if style == 'prose' else (lambda r: '')
    sample_rng = random.Random(0)
    sample = ''.join(f'Record {i:06d}: code {code(sample_rng)}{filler(sample_rng)}\n' for i in range(40))
    per_line = max(1, len(tok(sample, add_special_tokens=False)['input_ids']) // 40)
    count = max(asks, (target_tokens - 220) // per_line)
    for i in range(count):
        c = code(rng)
        codes[i] = c
        lines.append(f'Record {i:06d}: code {c}{filler(rng)}\n')
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


def ask(base: str, model: str, prompt: str, max_tokens: int, timeout: int, api: str = 'completions'):
    body = {'model': model, 'max_tokens': max_tokens, 'temperature': 0, 'seed': 42, 'stream': True,
            'return_token_ids': True, 'stream_options': {'include_usage': True}}
    if api == 'chat':  # the chat template with thinking off, the way an application would ask
        body.update(messages=[{'role': 'user', 'content': prompt}], chat_template_kwargs={'enable_thinking': False})
    else:
        body['prompt'] = prompt
    path = '/v1/chat/completions' if api == 'chat' else '/v1/completions'
    req = urllib.request.Request(base.rstrip('/') + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    first = None
    text, ids, usage, stamps, finish = '', [], None, [], None
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
                piece = choice.get('text') or (choice.get('delta') or {}).get('content') or ''
                new_ids = choice.get('token_ids') or []
                finish = choice.get('finish_reason') or finish
                if (piece or new_ids) and first is None:
                    first = time.perf_counter()
                text += piece
                ids += new_ids
                if new_ids:
                    stamps.append((time.perf_counter(), len(new_ids)))
    end = time.perf_counter()
    return {'text': text, 'token_ids': ids, 'usage': usage, 'finish_reason': finish, 'ttft_s': (first or end) - t0, 'total_s': end - t0,
            'decode_tok_s': (len(ids) - stamps[0][1]) / (end - first) if first and len(stamps) > 1 and end > first else None,
            'steps': len(stamps)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--model', default='qwen38-27b-fp8')
    ap.add_argument('--tokenizer', default='/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
    ap.add_argument('--lengths', default='8000,30000,60000,120000,200000,250000')
    ap.add_argument('--asks', type=int, default=6)
    ap.add_argument('--max-tokens', type=int, default=400)
    ap.add_argument('--seed', type=int, default=20261005)
    ap.add_argument('--repeat', type=int, default=1, help='ask each length this many times (the second shows cache reuse)')
    ap.add_argument('--timeout', type=int, default=3600)
    ap.add_argument('--api', choices=('completions', 'chat'), default='completions')
    ap.add_argument('--bisect', default='', help='LOW,HIGH,STEP: after --lengths, halve the gap between a length that '
                    'answers every code (LOW) and one that does not (HIGH) until it is at most STEP tokens')
    ap.add_argument('--style', choices=('ledger', 'prose'), default='ledger')
    ap.add_argument('--one-ledger', action='store_true', help='every length is a prefix of the same ledger (same seed)')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    tok = LightTokenizer(a.tokenizer)
    report = {'schema': 'qwen38-fp8-long-context-probe.v1', 'base_url': a.base_url, 'api': a.api, 'style': a.style, 'rows': []}
    targets = [int(x) for x in a.lengths.split(',') if x]
    low, high, step = ([int(x) for x in a.bisect.split(',')] if a.bisect else (0, 0, 0))
    if a.bisect:
        targets.append((low + high) // 2)
    for target in targets:  # the bisection appends to this list as results come in
        prompt, n, expected, picks = build(tok, target, a.seed if a.one_ledger else a.seed + target, a.asks, a.style)
        for rep in range(a.repeat):
            row = {'target_tokens': target, 'prompt_tokens_client': n, 'repeat': rep, 'asked_records': picks, 'expected': expected}
            try:
                r = ask(a.base_url, a.model, prompt, a.max_tokens, a.timeout, a.api)
                got = [c.strip() for c in r['text'].split('\n')[0].split(',')]
                row.update(r, correct=[e in r['text'] for e in expected], all_correct=all(e in r['text'] for e in expected),
                           in_order=got[:len(expected)] == expected,
                           prompt_read_tok_s=n / r['ttft_s'] if r['ttft_s'] else None)
            except Exception as error:  # noqa: BLE001  (a refused length is a result, not a crash)
                row['error'] = f'{type(error).__name__}: {error}'[:400]
                if 'Connection refused' in row['error'] or 'RemoteDisconnected' in row['error']:
                    report['rows'].append(row)  # the server is gone: nothing after this would be a measurement
                    a.out.write_text(json.dumps(report, indent=1) + '\n')
                    print(f"PROBE target={target} tokens={n} server gone: {row['error']}", flush=True)
                    return 3
            report['rows'].append(row)
            a.out.write_text(json.dumps(report, indent=1) + '\n')
            print(f"PROBE target={target} tokens={n} rep={rep} "
                  + (f"error={row['error']}" if 'error' in row else
                     f"first_token_s={row['ttft_s']:.1f} read_tok_s={row['prompt_read_tok_s']:.0f} "
                     f"decode_tok_s={row['decode_tok_s'] and round(row['decode_tok_s'], 1)} correct={sum(row['correct'])}/{len(expected)} "
                     f"in_order={row['in_order']} out_tokens={len(row['token_ids'])} first_ids={row['token_ids'][:6]} finish={row['finish_reason']}"), flush=True)
        if a.bisect and target == targets[-1] and low < target < high:
            low, high = (target, high) if report['rows'][-1].get('all_correct') else (low, target)
            if high - low > step:
                targets.append((low + high) // 2)
            else:
                report['edge'] = {'longest_all_correct': low, 'shortest_not_all_correct': high}
                a.out.write_text(json.dumps(report, indent=1) + '\n')
                print(f'EDGE longest_all_correct={low} shortest_not_all_correct={high}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
