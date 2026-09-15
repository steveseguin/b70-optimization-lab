#!/usr/bin/env python3
"""Replay saved greedy requests in chosen orders and report history-dependent outputs.

Operator diagnostic only; owns an HTTP client, never a server. Each request is a
saved /v1/completions payload (exact prompt token ids, greedy, ignore_eos). The
first output seen for each key is its reference; every later occurrence of that
key is compared token by token. Output: one JSON line per request plus summary.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import urllib.request


def post(base, payload, timeout):
    body = dict(payload, stream=False)
    body.pop('stream_options', None)
    request = urllib.request.Request(base + '/v1/completions', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--requests', type=Path, required=True, help='directory of <phase>-<key>-<n>-request.json files')
    ap.add_argument('--sequence', required=True, help='comma-separated keys, e.g. prose-2048,docs-12288,prose-2048')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--logprobs', type=int, default=0, help='request top-N logprobs per generated token and compare them exactly')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    payloads = {}
    for key in dict.fromkeys(args.sequence.split(',')):
        path = next(iter(sorted(args.requests.glob(f'*-{key}-0-request.json'))))
        payloads[key] = json.loads(path.read_text())
        if args.logprobs:
            payloads[key]['logprobs'] = args.logprobs
    reference, reference_lp, results = {}, {}, []
    with (args.out / 'requests.jsonl').open('w') as log:
        for index, key in enumerate(args.sequence.split(',')):
            start = time.perf_counter()
            response = post(args.base_url, payloads[key], args.timeout)
            choice = response['choices'][0]
            ids = choice.get('token_ids')
            usage = response.get('usage') or {}
            cached = ((usage.get('prompt_tokens_details') or {}).get('cached_tokens')) or 0
            if not isinstance(ids, list) or len(ids) != payloads[key]['max_tokens']:
                raise RuntimeError(f'bad output for {key}')
            first = reference.setdefault(key, ids)
            divergence = next((i for i, (a, b) in enumerate(zip(first, ids)) if a != b), None)
            lp = (choice.get('logprobs') or {}).get('token_logprobs') if args.logprobs else None
            first_lp = reference_lp.setdefault(key, lp)
            lp_divergence = None if lp is None else next(
                (i for i, (a, b) in enumerate(zip(first_lp, lp)) if a != b), None)
            row = dict(index=index, key=key, seconds=round(time.perf_counter() - start, 3), cached_tokens=cached,
                       is_reference=first is ids, first_divergence=divergence,
                       first_logprob_divergence=lp_divergence, token_ids=ids, token_logprobs=lp)
            results.append(row)
            log.write(json.dumps(row) + '\n')
            log.flush()
            print(index, key, 'ref' if first is ids else ('same' if divergence is None else f'DIVERGES at {divergence}'),
                  '' if lp is None or first is ids else f'logprobs first differ at {lp_divergence}', flush=True)
    summary = dict(sequence=args.sequence.split(','),
                   divergent=[dict(index=r['index'], key=r['key'], at=r['first_divergence'])
                              for r in results if r['first_divergence'] is not None],
                   logprob_divergent=[dict(index=r['index'], key=r['key'], at=r['first_logprob_divergence'])
                                      for r in results if r['first_logprob_divergence'] is not None],
                   cached_tokens_all_zero=all(r['cached_tokens'] == 0 for r in results))
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
