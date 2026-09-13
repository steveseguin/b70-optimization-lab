#!/usr/bin/env python3
"""Diagnostic exact-ID boundary gate; oracle must use the same image with MTP=0.

Example: --mode oracle --base http://localhost:8000 --model MODEL --out oracle.json
Then: --mode compare --base URL --model MODEL --oracle oracle.json --out gate.json
The runner must record image/config identity and disable prefix caching. This
probe records supplied --identity and rejects nonzero cache metadata when present.
Synthetic boundary coverage is not a realistic performance/promotion gate.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

SCHEMA = 'boundary-token-id-v1'
WORDS = 'the quick brown fox jumps over the lazy dog while seven wizards juggle bright lanterns near a quiet river bank at dawn'


def post(base, path, payload, timeout):
    req = urllib.request.Request(base.rstrip('/') + path, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def ids(value, name):
    if not isinstance(value, list) or not value or any(type(x) is not int or x < 0 for x in value):
        raise ValueError(f'{name} must be a nonempty list of nonnegative integer token IDs')
    return value


def validate_response(response, prompt, count):
    choices = response['choices']
    if len(choices) != 1:
        raise ValueError('expected exactly one choice')
    choice = choices[0]
    got = ids(choice.get('token_ids'), 'choice.token_ids')
    usage = response['usage']
    if len(got) != count or usage.get('completion_tokens') != count:
        raise ValueError(f'incomplete completion: requested {count}, IDs={len(got)}, usage={usage}')
    if usage.get('prompt_tokens') != len(prompt):
        raise ValueError(f'prompt token count mismatch: {usage}')
    echoed = response.get('prompt_token_ids', choice.get('prompt_token_ids'))
    if echoed is not None and echoed != prompt:
        raise ValueError('returned prompt IDs differ from submitted IDs')
    cache = []
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'cached_tokens' and item is not None:
                    cache.append(item)
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(response)
    if any(type(x) is not int or x != 0 for x in cache):
        raise ValueError(f'nonzero or invalid cached_tokens: {cache}')
    if choice.get('finish_reason') != 'length':
        raise ValueError(f'unexpected finish reason: {choice.get("finish_reason")}')
    return {'token_ids': got, 'usage': usage, 'cached_tokens': cache or None,
            'cache_metadata_present': bool(cache), 'finish_reason': choice['finish_reason']}


def complete(args, case, repeat, concurrency):
    start = time.monotonic()
    row = {'case': case['id'], 'repeat': repeat, 'concurrency': concurrency,
           'prompt_tokens': len(case['prompt_ids']), 'max_tokens': case['max_tokens']}
    try:
        response = post(args.base, '/v1/completions', {
            'model': args.model, 'prompt': case['prompt_ids'], 'max_tokens': case['max_tokens'],
            'temperature': 0, 'ignore_eos': True, 'seed': 1, 'return_token_ids': True,
        }, args.timeout)
        row.update(validate_response(response, case['prompt_ids'], case['max_tokens']))
        want = case.get('expected_ids')
        row['exact'] = want is None or row['token_ids'] == want
        if want is not None:
            row['first_diff'] = next((i for i, (x, y) in enumerate(zip(row['token_ids'], want)) if x != y), None)
        row['passed'] = row['exact']
    except Exception as exc:
        row.update(passed=False, exact=False, error=f'{type(exc).__name__}: {exc}')
    row['seconds'] = round(time.monotonic() - start, 3)
    return row


def save(path, evidence):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n')
    os.replace(temporary, path)


def numbers(value):
    result = [int(x) for x in value.split(',')]
    if not result or len(set(result)) != len(result):
        raise argparse.ArgumentTypeError('supply distinct comma-separated integers')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=['oracle', 'compare'])
    parser.add_argument('--base', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--oracle')
    parser.add_argument('--identity', default='', help='runner-supplied immutable image/config identity')
    parser.add_argument('--max-model-len', type=int, default=256)
    parser.add_argument('--lengths', type=numbers, default=list(range(8, 28)))
    parser.add_argument('--tail-length', type=int, default=14)
    parser.add_argument('--tail-offsets', type=numbers, default=list(range(236, 242)))
    parser.add_argument('--concurrency', type=numbers, default=[1, 4])
    parser.add_argument('--iters', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args(argv)
    if args.iters < 2 or min(args.concurrency) < 1 or min(args.lengths) < 1 or max(args.lengths) >= args.max_model_len:
        parser.error('require iters>=2, concurrency>=1 and 0<lengths<max-model-len')
    evidence = {'schema': SCHEMA, 'mode': args.mode, 'base': args.base, 'model': args.model,
                'identity': args.identity, 'max_model_len': args.max_model_len,
                'configuration': vars(args), 'cases': [], 'rows': [], 'status': 'running', 'passed': False}
    save(args.out, evidence)
    try:
        if args.mode == 'oracle':
            tokenized = post(args.base, '/tokenize', {'model': args.model, 'prompt': ' '.join([WORDS] * 8)}, args.timeout)
            seed_ids = ids(tokenized.get('tokens'), 'tokenize.tokens')
            if len(seed_ids) < max(args.lengths):
                raise ValueError('tokenized fixture shorter than requested lengths')
            cases = [{'id': f'L{length}', 'prompt_ids': seed_ids[:length], 'max_tokens': args.max_model_len - length} for length in args.lengths]
        else:
            if not args.oracle:
                raise ValueError('--oracle is required in compare mode')
            raw = Path(args.oracle).read_bytes()
            oracle = json.loads(raw)
            evidence['oracle_sha256'] = hashlib.sha256(raw).hexdigest()
            evidence['oracle_identity'] = oracle.get('identity')
            if oracle.get('schema') != SCHEMA or oracle.get('mode') != 'oracle' or not oracle.get('passed') or oracle.get('status') != 'complete':
                raise ValueError('oracle must be a completed passing token-ID oracle')
            if oracle['model'] != args.model or oracle['max_model_len'] != args.max_model_len:
                raise ValueError('oracle model or context limit mismatch')
            cases = []
            for length in args.lengths:
                case = next(c for c in oracle['cases'] if c['id'] == f'L{length}')
                ids(case['expected_ids'], 'oracle expected_ids')
                if len(case['expected_ids']) != args.max_model_len - length or len(case['prompt_ids']) != length:
                    raise ValueError('oracle case length mismatch')
                cases.append(dict(case))
            tail = next(c for c in oracle['cases'] if c['id'] == f'L{args.tail_length}')
            for offset in args.tail_offsets:
                if not 0 <= offset < len(tail['expected_ids']):
                    raise ValueError(f'invalid tail offset {offset}')
                cases.append({'id': f'L{args.tail_length}-tail{offset}',
                              'prompt_ids': tail['prompt_ids'] + tail['expected_ids'][:offset],
                              'max_tokens': len(tail['expected_ids']) - offset,
                              'expected_ids': tail['expected_ids'][offset:]})
        evidence['cases'] = cases
        save(args.out, evidence)
        # Capture each baseline serially, then test repeats and concurrent shapes.
        if args.mode == 'oracle':
            for case in cases:
                row = complete(args, case, -1, 1)
                evidence['rows'].append(row)
                if not row['passed']:
                    raise ValueError(f'oracle capture failed: {row}')
                case['expected_ids'] = row['token_ids']
                save(args.out, evidence)
        for concurrency in args.concurrency:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                jobs = [pool.submit(complete, args, case, repeat, concurrency)
                        for repeat in range(args.iters) for case in cases]
                for job in concurrent.futures.as_completed(jobs):
                    row = job.result()
                    evidence['rows'].append(row)
                    save(args.out, evidence)
                    print(json.dumps({k: v for k, v in row.items() if k != 'token_ids'}), flush=True)
        evidence['status'] = 'complete'
        evidence['passed'] = bool(evidence['rows']) and all(row['passed'] for row in evidence['rows'])
    except Exception as exc:
        evidence.update(status='error', error=f'{type(exc).__name__}: {exc}', passed=False)
    save(args.out, evidence)
    print(json.dumps({'out': args.out, 'status': evidence['status'], 'passed': evidence['passed'], 'rows': len(evidence['rows']), 'error': evidence.get('error')}), flush=True)
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
