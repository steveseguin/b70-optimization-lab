#!/usr/bin/env python3
"""One-step answers for decisions: read a choice from the first step instead of decoding it.

When the answer must be one of a known set of labels whose first tokens differ, the label is already decided by the
logits the prompt pass produces: the best allowed first token. This client measures, on generated decision items of
four kinds (yes/no, A-D choice, sentiment, routing), three ways of getting the answer from the same chat prompt:

  one_step   max_tokens=1 with sampling restricted to the labels' first tokens (`allowed_token_ids`): the server
             returns the best-scoring allowed first token, which names the label. (The first version read the top-20
             scores instead; asking a drafting two-card server for scores makes it compile a scoring routine that
             needs over a gigabyte of host memory for some seconds, and the host memory guard stopped the server.
             `--scores` keeps that variant for servers with the headroom.)
  decode     thinking off, the label decoded normally (greedy), parsed from the text
  think      thinking on, full reasoning then the label (greedy), parsed from the text after the reasoning

and reports agreement between them, accuracy against the generated ground truth, and time per item.
`one_step` is exactly what greedy decoding restricted to the label set would output as its first token; whether that
equals unrestricted decoding is what the agreement column measures. CPU client; needs the `tokenizers` library only.

  python3 qwen38-fp8-one-step-choice-probe.py --base-url http://127.0.0.1:18196 --out choice.json
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


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


def items(seed: int, per_kind: int):
    rng = random.Random(seed)
    out = []
    for _ in range(per_kind):
        a, b = rng.sample(range(100, 999), 2)
        out.append({'kind': 'yes_no', 'labels': ['yes', 'no'], 'truth': 'yes' if a > b else 'no',
                    'question': f'Is {a} greater than {b}? Answer with exactly one word: yes or no.'})
    for _ in range(per_kind):
        nums = rng.sample(range(10, 99), 4)
        letter = 'ABCD'[nums.index(max(nums))]
        out.append({'kind': 'choice', 'labels': list('ABCD'), 'truth': letter,
                    'question': 'Which option is the largest number? ' + ' '.join(f'{l}) {n}' for l, n in zip('ABCD', nums))
                                + ' Answer with exactly one letter: A, B, C or D.'})
    good = ['excellent', 'wonderful', 'reliable', 'fast and friendly', 'exactly what I wanted']
    bad = ['terrible', 'broken on arrival', 'slow and rude', 'a waste of money', 'falling apart']
    flat = ['delivered on Tuesday', 'blue, as listed', 'packed in a cardboard box', 'the standard size', 'made in 2024']
    for _ in range(per_kind):
        label, pool = rng.choice([('positive', good), ('negative', bad), ('neutral', flat)])
        out.append({'kind': 'sentiment', 'labels': ['positive', 'negative', 'neutral'], 'truth': label,
                    'question': f'Classify the sentiment of this review: "The product was {rng.choice(pool)}." '
                                'Answer with exactly one word: positive, negative or neutral.'})
    routes = {'billing': ['I was charged twice this month', 'my invoice shows the wrong amount', 'please refund my last payment'],
              'technical': ['the app crashes when I open settings', 'I get error 500 on upload', 'the device will not turn on'],
              'account': ['I forgot my password', 'please change the email on my profile', 'I cannot log in after the update'],
              'shipping': ['my parcel has not arrived', 'the tracking number does not work', 'the box was delivered to the wrong address']}
    for _ in range(per_kind):
        label = rng.choice(list(routes))
        out.append({'kind': 'routing', 'labels': list(routes), 'truth': label,
                    'question': f'Route this support ticket: "{rng.choice(routes[label])}". '
                                'Answer with exactly one word: billing, technical, account or shipping.'})
    return out


def chat(base, model, question, max_tokens, thinking, logprobs, timeout=900, allowed=None):
    body = {'model': model, 'messages': [{'role': 'user', 'content': question}], 'max_tokens': max_tokens,
            'temperature': 0, 'seed': 42, 'chat_template_kwargs': {'enable_thinking': thinking}}
    if logprobs:
        body.update(logprobs=True, top_logprobs=20)
    if allowed:
        body.update(allowed_token_ids=sorted(allowed), return_token_ids=True)
    req = urllib.request.Request(base.rstrip('/') + '/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as error:  # show the server's reason, not just the status
        raise RuntimeError(f'HTTP {error.code}: {error.read().decode("utf-8", "replace")[:600]}') from error
    return data, time.perf_counter() - t0


def parse(text, labels):
    """First label mentioned in the text (after any reasoning block), case-insensitive, as a whole word."""
    text = text.split('</think>')[-1]
    best = None
    for label in labels:
        m = re.search(r'(?<![A-Za-z])' + re.escape(label) + r'(?![A-Za-z])', text, re.I if len(label) > 1 else 0)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), label)
    return best[1] if best else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--model', default='qwen38-27b-fp8')
    ap.add_argument('--tokenizer', default='/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
    ap.add_argument('--per-kind', type=int, default=20)
    ap.add_argument('--seed', type=int, default=20261005)
    ap.add_argument('--think-items', type=int, default=24, help='how many items also get the slow thinking pass')
    ap.add_argument('--scores', action='store_true', help='read the top-20 scores instead of restricting sampling')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    tok = LightTokenizer(a.tokenizer)
    first = lambda s: tok(s, add_special_tokens=False)['input_ids'][0]
    rows = []
    data = items(a.seed, a.per_kind)
    random.Random(a.seed).shuffle(data)
    for index, item in enumerate(data):
        # every surface form a label can start with at the start of the assistant turn
        starts = {}
        for label in item['labels']:
            for form in {label, label.capitalize(), label.upper(), ' ' + label, ' ' + label.capitalize()}:
                starts.setdefault(first(form), label)
        distinct = len({first(l) for l in item['labels']}) == len(item['labels'])
        row = {'kind': item['kind'], 'truth': item['truth'], 'labels_first_tokens_distinct': distinct}
        if a.scores:
            one, t_one = chat(a.base_url, a.model, item['question'], 1, False, True)
            top = one['choices'][0]['logprobs']['content'][0]['top_logprobs'] if one['choices'][0].get('logprobs') else []
            scored = []
            for entry in top:
                ids = tok(entry['token'], add_special_tokens=False)['input_ids']
                if len(ids) == 1 and ids[0] in starts:
                    scored.append((entry['logprob'], starts[ids[0]]))
            row.update(one_step=max(scored)[1] if scored else None, one_step_s=t_one,
                       one_step_margin=(sorted(scored, reverse=True)[0][0] - sorted(scored, reverse=True)[1][0]) if len(scored) > 1 else None,
                       one_step_top_token=top[0]['token'] if top else None,
                       prompt_tokens=one.get('usage', {}).get('prompt_tokens'))
        else:
            one, t_one = chat(a.base_url, a.model, item['question'], 1, False, False, allowed=starts)
            choice = one['choices'][0]
            ids = choice.get('token_ids') or tok(choice['message'].get('content') or '', add_special_tokens=False)['input_ids']
            row.update(one_step=starts.get(ids[0]) if ids else None, one_step_s=t_one, one_step_token_id=ids[0] if ids else None,
                       one_step_text=choice['message'].get('content'), prompt_tokens=one.get('usage', {}).get('prompt_tokens'))
        dec, t_dec = chat(a.base_url, a.model, item['question'], 16, False, False)
        text = dec['choices'][0]['message'].get('content') or ''
        row.update(decode=parse(text, item['labels']), decode_s=t_dec, decode_tokens=dec.get('usage', {}).get('completion_tokens'),
                   decode_text=text[:60])
        if index < a.think_items:
            th, t_th = chat(a.base_url, a.model, item['question'], 2048, True, False)
            msg = th['choices'][0]['message']
            row.update(think=parse((msg.get('content') or ''), item['labels']), think_s=t_th,
                       think_tokens=th.get('usage', {}).get('completion_tokens'))
        rows.append(row)
        a.out.write_text(json.dumps({'schema': 'qwen38-fp8-one-step-choice-probe.v1', 'rows': rows}, indent=1) + '\n')
    n = len(rows)
    agree = sum(r['one_step'] == r['decode'] for r in rows)
    th = [r for r in rows if 'think' in r]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    summary = {'items': n, 'one_step_answered': sum(r['one_step'] is not None for r in rows),
               'one_step_equals_decode': f'{agree}/{n}',
               'accuracy': {k: f"{sum(r.get(k) == r['truth'] for r in (rows if k != 'think' else th))}/{len(rows if k != 'think' else th)}"
                            for k in ('one_step', 'decode', 'think')},
               'one_step_equals_think': f"{sum(r['one_step'] == r['think'] for r in th)}/{len(th)}",
               'median_seconds': {'one_step': med([r['one_step_s'] for r in rows]), 'decode': med([r['decode_s'] for r in rows]),
                                  'think': med([r['think_s'] for r in th])},
               'median_tokens': {'decode': med([r['decode_tokens'] for r in rows if r.get('decode_tokens')]),
                                 'think': med([r['think_tokens'] for r in th if r.get('think_tokens')])}}
    a.out.write_text(json.dumps({'schema': 'qwen38-fp8-one-step-choice-probe.v1', 'summary': summary, 'rows': rows}, indent=1) + '\n')
    print('CHOICE ' + json.dumps(summary), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
