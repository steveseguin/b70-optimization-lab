#!/usr/bin/env python3
"""One profiler request; trace timings are diagnostic and excluded from rates."""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def post(base, path, body=None):
    data = b'' if body is None else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=data,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read().decode()


def run(args):
    args.out.mkdir(parents=True, exist_ok=False)
    baseline = json.loads(args.baseline.read_text())
    assert baseline['passed'] is True
    key = 'prose-512'
    payload = dict(model=args.model, prompt=baseline['prompts'][key], max_tokens=1,
                   temperature=0, seed=42, ignore_eos=True, return_token_ids=True)
    (args.out / 'request.json').write_text(json.dumps(payload, indent=2) + '\n')
    (args.out / 'start-response.txt').write_text(post(args.base_url, '/start_profile'))
    try:
        start = time.perf_counter()
        raw = post(args.base_url, '/v1/completions', payload)
        (args.out / 'response.json').write_text(raw + '\n')
        response = json.loads(raw)
        usage = response['usage']
        assert usage['prompt_tokens'] == 512
        assert usage['prompt_tokens_details']['cached_tokens'] == 0
        expected = next(row['token_ids'][0] for row in baseline['rows'] if row['key'] == key)
        assert response['choices'][0]['token_ids'] == [expected]
        (args.out / 'summary.json').write_text(json.dumps({'passed': True,
            'wall_s_with_profiler': time.perf_counter() - start,
            'first_token_matches_unprofiled': True,
            'scope': 'One diagnostic 512-token request; profiler overhead excluded from published measurements.'}, indent=2) + '\n')
    finally:
        (args.out / 'stop-response.txt').write_text(post(args.base_url, '/stop_profile'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    run(parser.parse_args())
