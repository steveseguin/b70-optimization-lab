#!/usr/bin/env python3
"""Prefix-cache exactness probe (E0): is a request answered from the prefix cache bit-identical to the same request
answered cold?

Client only (CPU). Prompts are sent as token-id lists so every variant shares exactly the tokens it is meant to share.
Prompt families: the eight long-prompt-suite prompts plus generated ledgers (3K/10K/30K tokens, the long-context
probe's builder). Variants of each family's prompt P:
  a  P, first time (cold on the cache server; checks cache-on cold == cache-off cold)
  b  P again (full hit: everything but the last partial block is reused)
  c  P with its last --tail-tokens tokens replaced by other text (hit up to the block before the change)
  d  P plus a new paragraph (hit on all of P's full blocks)
  e  P with --edit-tokens tokens deleted at 50% (hit up to the edit, re-read after it)
  f0 P cut to end --answer-cross tokens before a block boundary (hit on earlier blocks; its 16-token answer crosses
     the boundary, so the next block holds tokens the server computed while *writing*, not reading)
  f  f0 + f0's answer + a new paragraph: a chat-style next turn. The reused block holds decode-made state; the cold
     twin reads those tokens as prompt. Reported separately: NOT expected to be exact (see the prereg note).
Each variant is compared token for token (ids) and by the top-5 logprobs of the first --max-tokens generated tokens
with a cold twin of the same request.

Cold twins, in order of preference:
  --compare-with ref.json  a saved run of this probe with --save against a cache-OFF server (fresh server, never had a
                           cache). Use this when only one server fits on the host: run the control first, stop it,
                           start the cache server, then run the cache pass with --compare-with.
  --control-url URL        a second, cache-off server answering live.
  (neither)                the cache server itself with a unique cache_salt per cold request: no shared blocks, same
                           tokens, but the server is not fresh (marked cold_source=salted-same-server).

  # 1) control server (cache off, same chunk size): save cold answers
  python3 qwen38-fp8-prefix-cache-exactness-probe.py --base-url http://127.0.0.1:18132 --save control.json
  # 2) cache server (--prefix-cache align --batched 832): compare
  python3 qwen38-fp8-prefix-cache-exactness-probe.py --base-url http://127.0.0.1:18132 --compare-with control.json \
      --out cache.json

Needs `transformers` for the tokenizer only (~/.venvs/vllm-xpu has it). Exit code 0 = every a..e/f0 comparison equal.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import time
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITE = HERE.parent / 'data/2026-10-04-fp8-multiuser/long-prompt-suite.json'
REPLACEMENT = ('Unrelated note inserted for the cache test: the weather station on the north ridge logged light rain, '
               'a steady westerly breeze and a pressure drop of four hectopascals over the afternoon, after which the '
               'readings settled and the technician closed the shelter for the night. ')
PARAGRAPH = ('\n\nAdditional paragraph added after the original text: summarise in one sentence what the text above '
             'is about, then name the single most specific detail it contains.\n')
NEXT_TURN = '\n\nFollow-up: continue from where the previous answer stopped, in the same style.\n'
EXACT_VARIANTS = ('a', 'b', 'c', 'd', 'e', 'f0')


def ids_sha(ids):
    return hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:16]


def load_ledger_builder():
    spec = importlib.util.spec_from_file_location('lcp', HERE / 'qwen38-fp8-long-context-probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build


def families(tok, ledgers, seed, only):
    out = []
    for item in json.loads(SUITE.read_text())['prompts']:
        out.append((item['id'], tok(item['prompt'], add_special_tokens=False)['input_ids']))
    build = load_ledger_builder()
    for target in ledgers:
        prompt, _, _, _ = build(tok, target, seed + target, 6)
        out.append((f'ledger{target // 1000}k', tok(prompt, add_special_tokens=False)['input_ids']))
    return [f for f in out if not only or f[0] in only]


def text_ids(tok, text, count=None):
    ids = tok(text, add_special_tokens=False)['input_ids']
    if count is None:
        return ids
    while len(ids) < count:
        ids += ids
    return ids[:count]


def ask(base, model, ids, a, salt=None):
    body = {'model': model, 'prompt': ids, 'max_tokens': a.max_tokens, 'temperature': 0, 'seed': 42,
            'logprobs': a.logprobs, 'return_tokens_as_token_ids': True, 'return_token_ids': True,
            'stream': True, 'stream_options': {'include_usage': True}}
    if salt:
        body['cache_salt'] = salt
    req = urllib.request.Request(base.rstrip('/') + '/v1/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    first = None
    out_ids, top, chosen, usage = [], [], [], None
    with urllib.request.urlopen(req, timeout=a.timeout) as resp:
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
                new_ids = choice.get('token_ids') or []
                if new_ids and first is None:
                    first = time.perf_counter()
                out_ids += new_ids
                lp = choice.get('logprobs') or {}
                top += lp.get('top_logprobs') or []
                chosen += lp.get('token_logprobs') or []
    end = time.perf_counter()
    details = (usage or {}).get('prompt_tokens_details') or {}
    return {'token_ids': out_ids, 'top_logprobs': top, 'token_logprobs': chosen,
            'prompt_tokens': (usage or {}).get('prompt_tokens'), 'cached_tokens': details.get('cached_tokens'),
            'ttft_s': (first or end) - t0, 'total_s': end - t0, 'salt': salt}


def compare(hit, cold):
    """Token ids and top-k logprobs, exact. Returns a dict with the first differing positions and the largest gap."""
    t1, t2 = hit['token_ids'], cold['token_ids']
    first_tok = next((i for i, (x, y) in enumerate(zip(t1, t2)) if x != y), None)
    if first_tok is None and len(t1) != len(t2):
        first_tok = min(len(t1), len(t2))
    first_lp, gap, set_differs = None, 0.0, False
    for i, (p, q) in enumerate(zip(hit['top_logprobs'], cold['top_logprobs'])):
        p, q = p or {}, q or {}
        if p != q and first_lp is None:
            first_lp = i
        if set(p) != set(q):
            set_differs = True
        for key in set(p) & set(q):
            if p[key] is not None and q[key] is not None and math.isfinite(p[key]) and math.isfinite(q[key]):
                gap = max(gap, abs(p[key] - q[key]))
    if first_lp is None and len(hit['top_logprobs']) != len(cold['top_logprobs']):
        first_lp = min(len(hit['top_logprobs']), len(cold['top_logprobs']))
    if first_lp is None and hit['token_logprobs'] != cold['token_logprobs']:
        first_lp = next((i for i, (x, y) in enumerate(zip(hit['token_logprobs'], cold['token_logprobs'])) if x != y), 0)
    return {'equal_tokens': first_tok is None, 'first_token_diff': first_tok,
            'equal_logprobs': first_lp is None, 'first_logprob_diff': first_lp,
            'max_logprob_gap': gap, 'top_set_differs': set_differs}


def lcp(x, y):
    n = 0
    for p, q in zip(x, y):
        if p != q:
            break
        n += 1
    return n


def expected_hit(ids, seen, block):
    """Largest block-aligned reuse the source predicts: shared prefix with an earlier sequence of this run (its prompt
    plus all but the last generated token), at most len(ids) - 1, floored to the block grid."""
    best = 0
    for old in seen:
        shared = min(lcp(ids, old), len(old) // block * block, len(ids) - 1)
        best = max(best, shared // block * block)
    return best


def variants(tok, ids, a, f0_answer=None):
    half = len(ids) // 2
    cut = max(a.block, (len(ids) // a.block) * a.block) - a.answer_cross
    out = {'a': ids, 'b': ids,
           'c': ids[:-a.tail_tokens] + text_ids(tok, REPLACEMENT, a.tail_tokens),
           'd': ids + text_ids(tok, PARAGRAPH),
           'e': ids[:half] + ids[half + a.edit_tokens:],
           'f0': ids[:cut] if cut > 0 else ids}
    if f0_answer is not None:
        out['f'] = out['f0'] + list(f0_answer) + text_ids(tok, NEXT_TURN)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', required=True, help='the server under test (or the control server with --save)')
    ap.add_argument('--control-url', default='', help='a live cache-off server for cold twins')
    ap.add_argument('--save', type=Path, help='cold-reference mode: answer every variant cold (unique salt each) and save')
    ap.add_argument('--compare-with', type=Path, help='cold twins from a saved --save run (control server)')
    ap.add_argument('--out', type=Path, help='JSON report (cache pass); default prefix-cache-probe-<time>.json')
    ap.add_argument('--model', default='qwen38-27b-fp8')
    ap.add_argument('--tokenizer', default='/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
    ap.add_argument('--ledgers', default='3000,10000,30000')
    ap.add_argument('--only', default='', help='comma-separated family ids (e.g. prose2k,ledger3k)')
    ap.add_argument('--seed', type=int, default=20261005)
    ap.add_argument('--max-tokens', type=int, default=16)
    ap.add_argument('--logprobs', type=int, default=5)
    ap.add_argument('--tail-tokens', type=int, default=200)
    ap.add_argument('--edit-tokens', type=int, default=300)
    ap.add_argument('--block', type=int, default=832, help='attention block size (server.log); for expected hits only')
    ap.add_argument('--answer-cross', type=int, default=8, help='f0 ends this many tokens before a block boundary')
    ap.add_argument('--timeout', type=int, default=3600)
    a = ap.parse_args()
    if a.save and (a.compare_with or a.control_url):
        ap.error('--save is the control pass; it takes no cold source')
    if a.compare_with and a.control_url:
        ap.error('use one cold source')
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    fams = families(tok, [int(x) for x in a.ledgers.split(',') if x], a.seed, set(filter(None, a.only.split(','))))
    run = uuid.uuid4().hex

    if a.save:  # control pass: every distinct request cold, f built from this server's own f0 answer
        ref = {'schema': 'qwen38-fp8-prefix-cache-exactness-probe.control.v1', 'base_url': a.base_url,
               'settings': {k: getattr(a, k) for k in ('max_tokens', 'logprobs', 'tail_tokens', 'edit_tokens', 'block',
                                                      'answer_cross', 'ledgers', 'seed')}, 'cases': {}}
        for fid, ids in fams:
            v = variants(tok, ids, a)
            for name in ('a', 'c', 'd', 'e', 'f0'):
                r = ask(a.base_url, a.model, v[name], a, salt=f'cold-{run}-{fid}-{name}')
                ref['cases'][f'{fid}/{name}'] = r | {'prompt_sha': ids_sha(v[name]), 'prompt_len': len(v[name])}
                print(f"COLD prompt={fid} variant={name} tokens={len(v[name])} cached_tokens={r['cached_tokens']} "
                      f"ttft={r['ttft_s']:.2f}", flush=True)
            v = variants(tok, ids, a, ref['cases'][f'{fid}/f0']['token_ids'])
            r = ask(a.base_url, a.model, v['f'], a, salt=f'cold-{run}-{fid}-f')
            ref['cases'][f'{fid}/f'] = r | {'prompt_sha': ids_sha(v['f']), 'prompt_len': len(v['f'])}
            print(f"COLD prompt={fid} variant=f tokens={len(v['f'])} cached_tokens={r['cached_tokens']} "
                  f"ttft={r['ttft_s']:.2f}", flush=True)
            a.save.write_text(json.dumps(ref, indent=1) + '\n')
        bad = [k for k, r in ref['cases'].items() if r.get('cached_tokens')]
        print(f"SAVED {a.save} cases={len(ref['cases'])} nonzero_cached={bad or 'none'}")
        return 0

    ref = json.loads(a.compare_with.read_text()) if a.compare_with else None
    if ref:
        for key in ('max_tokens', 'logprobs', 'tail_tokens', 'edit_tokens', 'answer_cross', 'ledgers', 'seed'):
            if ref['settings'][key] != getattr(a, key):
                raise SystemExit(f'--{key.replace("_", "-")} differs from the saved control run')
    cold_source = 'saved-control' if ref else ('control-server' if a.control_url else 'salted-same-server')
    out = a.out or Path(f'prefix-cache-probe-{time.strftime("%Y%m%d-%H%M%S")}.json')
    report = {'schema': 'qwen38-fp8-prefix-cache-exactness-probe.v1', 'base_url': a.base_url, 'cold_source': cold_source,
              'control': str(a.compare_with or a.control_url or ''), 'run_salt': run, 'rows': []}
    seen = []  # prompt + generated ids (minus the last) of every request answered in this run (cache candidates)

    def cold_twin(fid, name, ids):
        if ref:
            r = ref['cases'].get(f'{fid}/{name}')
            if r is None or r['prompt_sha'] != ids_sha(ids):
                raise SystemExit(f'{fid}/{name}: saved control has no case with these exact prompt tokens')
            return r
        if a.control_url:
            return ask(a.control_url, a.model, ids, a)
        return ask(a.base_url, a.model, ids, a, salt=f'cold-{run}-{fid}-{name}-{uuid.uuid4().hex}')

    for fid, ids in fams:
        v = variants(tok, ids, a)
        f0_answer = None
        for name in ('a', 'b', 'c', 'd', 'e', 'f0', 'f'):
            if name == 'f':
                # the next turn uses the answer the cold reference gave to f0, so both sides send the same tokens
                f0_answer = (ref['cases'][f'{fid}/f0']['token_ids'] if ref else f0_answer)
                v = variants(tok, ids, a, f0_answer)
            prompt = v[name]
            expect = expected_hit(prompt, seen, a.block)
            hit = ask(a.base_url, a.model, prompt, a, salt=f'run-{run}')
            seen.append(prompt + hit['token_ids'][:-1])
            if name == 'f0' and not ref:
                f0_answer = hit['token_ids']
            # b is the same request as a. In salted mode, a's "hit" is itself cold (fresh run salt), so a's row
            # checks cold-to-cold repeatability on one server.
            twin = cold_twin(fid, 'a' if name == 'b' else name, prompt)
            cmp = compare(hit, twin)
            row = {'prompt': fid, 'variant': name, 'prompt_len': len(prompt), 'cached_tokens': hit['cached_tokens'],
                   'expected_cached_tokens': expect, 'cold_cached_tokens': twin.get('cached_tokens'),
                   'ttft_cold': twin['ttft_s'], 'ttft_hit': hit['ttft_s'], **cmp,
                   'exact_rule': name in EXACT_VARIANTS, 'hit': hit, 'cold': twin}
            report['rows'].append(row)
            out.write_text(json.dumps(report, indent=1) + '\n')
            print(f"CACHE prompt={fid} variant={name} cached_tokens={hit['cached_tokens']} "
                  f"equal_tokens={cmp['equal_tokens']} equal_logprobs={cmp['equal_logprobs']} "
                  f"ttft_cold={twin['ttft_s']:.2f} ttft_hit={hit['ttft_s']:.2f}"
                  + ('' if hit['cached_tokens'] in (None, expect) else f' expected_cached={expect}')
                  + ('' if name in EXACT_VARIANTS else ' (decode-made blocks; not in the pass rule)'), flush=True)

    rows = report['rows']
    ruled = [r for r in rows if r['exact_rule']]
    diffs = [{k: r[k] for k in ('prompt', 'variant', 'cached_tokens', 'first_token_diff', 'first_logprob_diff',
                                'max_logprob_gap', 'top_set_differs')}
             for r in ruled if not (r['equal_tokens'] and r['equal_logprobs'])]
    cached = [r['cached_tokens'] for r in rows if r['cached_tokens']]
    report['summary'] = {
        'cold_source': cold_source,
        'cold_clean': cold_source != 'salted-same-server',
        'comparisons': len(ruled), 'all_equal': not diffs, 'differences': diffs,
        'cache_unused': [f"{r['prompt']}/{r['variant']}" for r in ruled if r['variant'] != 'a' and not r['cached_tokens']],
        'cached_tokens_unexpected': [f"{r['prompt']}/{r['variant']}" for r in rows
                                     if r['cached_tokens'] is not None and r['cached_tokens'] != r['expected_cached_tokens']],
        'block_size_from_hits': math.gcd(*cached) if cached else None,
        'decode_made_blocks_f': [{k: r[k] for k in ('prompt', 'cached_tokens', 'equal_tokens', 'equal_logprobs',
                                                    'first_token_diff', 'max_logprob_gap')} for r in rows if r['variant'] == 'f'],
        'ttft_saving_s': sum(r['ttft_cold'] - r['ttft_hit'] for r in ruled if r['variant'] != 'a'),
    }
    out.write_text(json.dumps(report, indent=1) + '\n')
    s = report['summary']
    print(f"SUMMARY all_equal={s['all_equal']} comparisons={s['comparisons']} differences={len(diffs)} "
          f"cold_source={cold_source} cold_clean={s['cold_clean']} block_from_hits={s['block_size_from_hits']} "
          f"unused_cache={len(s['cache_unused'])} report={out}")
    return 0 if s['all_equal'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
