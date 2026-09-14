#!/usr/bin/env python3
"""Serial exact-ID short-prefill screen. Owns clients only; never restarts servers.

HTTP prompt tokens / TTFT is an end-to-end proxy, not GPU prefill throughput.
Server histogram deltas are reported independently when exposed. Outputs use
ignore_eos to make the decode timing window uniform; this is a speed screen,
not a replacement for natural-completion quality qualification.
"""
import argparse
import json
import os
from pathlib import Path
import re
import statistics
import time
import urllib.request

CONTEXTS = {
    'prose': 'Explain the argument and continue the account. A coastal town recorded rainfall every morning. The librarian compared these observations with farm diaries, noting uncertainty and changes in measurement. ',
    'code': 'Review and extend this Python program with an explanation.\ndef aggregate(rows):\n    totals = {}\n    for name, value in rows:\n        totals[name] = totals.get(name, 0) + value\n    return sorted(totals.items())\n',
    'docs': 'Summarize this engineering documentation and give operational examples. Requests enter a FIFO queue. The service validates the schema, records a request identifier, performs the calculation, and returns a structured response. Errors include an explicit cause and preserve audit records. ',
}


def save(path, obj):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, indent=2) + '\n')
    os.replace(temp, path)


def fetch(base, path, payload=None, timeout=600):
    req = urllib.request.Request(base.rstrip('/') + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={} if payload is None else {'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


def metrics(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r'([^\s{]+)(?:\{[^}]*\})?\s+([-+0-9.eE]+)(?:\s|$)', line)
        if m and any(m[1].endswith(s) for s in (
            'request_prefill_time_seconds_sum', 'request_prefill_time_seconds_count',
            'prompt_tokens_total')):
            out[m[1]] = out.get(m[1], 0.0) + float(m[2])
    return out


def parse_events(events, expected_prompt, expected_output):
    ids, offsets, usage, done = [], [], None, False
    for record in events:
        data = record['data']
        if data == '[DONE]':
            done = True
            continue
        event = json.loads(data)
        if event.get('error'):
            raise ValueError(f"server error: {event['error']}")
        if event.get('usage') is not None:
            usage = event['usage']
        for choice in event.get('choices', []):
            if choice.get('index', 0) != 0:
                raise ValueError('unexpected multiple choices')
            chunk = choice.get('token_ids', [])
            if not isinstance(chunk, list) or any(type(x) is not int for x in chunk):
                raise ValueError('invalid numeric token IDs')
            ids.extend(chunk)
            offsets.extend([record['elapsed_s']] * len(chunk))
    if not done or not usage or len(ids) != expected_output:
        raise ValueError(f'incomplete SSE/usage/IDs: done={done}, ids={len(ids)}')
    if usage.get('prompt_tokens') != expected_prompt or usage.get('completion_tokens') != len(ids):
        raise ValueError('usage does not match exact prompt/output IDs')
    cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
    if cached != 0:
        raise ValueError(f'cached_tokens must explicitly be zero, got {cached!r}')
    ttft = offsets[0]
    decode = (len(ids) - 1) / (offsets[-1] - ttft) if offsets[-1] > ttft else None
    window = 99 / (offsets[99] - ttft) if len(ids) >= 100 and offsets[99] > ttft else None
    return dict(token_ids=ids, token_offsets_s=offsets, usage=usage, ttft_s=ttft,
        http_prompt_tokens_per_ttft_s=expected_prompt / ttft,
        decode_token_1_to_100_tps=window, decode_after_ttft_tps=decode)


def metric_delta(before, after, prompt_length):
    b, a = metrics(before), metrics(after)
    delta = {k: a[k] - b.get(k, 0) for k in a}
    def value(suffix):
        found = [v for k, v in delta.items() if k.endswith(suffix)]
        return sum(found) if found else None
    count = value('request_prefill_time_seconds_count')
    seconds = value('request_prefill_time_seconds_sum')
    tokens = value('prompt_tokens_total')
    if count is not None and count != 1:
        raise ValueError(f'prefill metrics count delta {count}, expected one serial request')
    if tokens is not None and tokens != prompt_length:
        raise ValueError(f'prompt metric delta {tokens}, expected {prompt_length}')
    return dict(raw_delta=delta, server_prefill_s=seconds if count == 1 else None,
        server_prefill_tokens_per_s=prompt_length / seconds if count == 1 and seconds and seconds > 0 else None)


def run(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    lengths = [int(x) for x in args.lengths.split(',')]
    if min(lengths) < 1 or max(lengths) + args.max_tokens > args.max_model_len or args.repeats < 2 or args.max_tokens < 100:
        raise ValueError('require positive lengths, context fit, repeats >=2, output >=100')
    state = dict(schema=1, passed=False, args={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}, prompts={}, rows=[], warmups=[], notes=[
        'c1 serial; HTTP tokens/TTFT is a proxy including transport, queueing, prefill and first decode.',
        'Server prefill is vLLM histogram elapsed time, not isolated GPU kernel time.',
        'SSE burst tokens share arrival timestamp; token 1–100 uses 99 numeric-token intervals.',
        'No cache, errors, missing IDs or output divergence permitted.'])
    save(out / 'summary.json', state)
    try:
        for name, context in CONTEXTS.items():
            with fetch(args.base_url, '/tokenize', {'model': args.model, 'prompt': context * (max(lengths) // 20 + 10), 'add_special_tokens': False}, args.timeout) as response:
                tokenized = json.load(response)
            ids = tokenized.get('tokens')
            if not isinstance(ids, list) or len(ids) < max(lengths) or any(type(x) is not int for x in ids):
                raise ValueError('/tokenize did not return enough numeric tokens')
            save(out / f'tokenize-{name}.json', tokenized)
            for length in lengths:
                state['prompts'][f'{name}-{length}'] = ids[:length]
        baseline = json.loads(args.baseline.read_text()) if args.baseline else None
        if baseline and baseline.get('passed') is not True:
            raise ValueError('baseline did not pass its own checks')
        if baseline and baseline['prompts'] != state['prompts']:
            raise ValueError('baseline prompt IDs differ')
        expected = {}
        if baseline:
            for row in baseline['rows']:
                key = row['key']
                if key in expected and expected[key] != row['token_ids']:
                    raise ValueError('baseline itself has output divergence')
                expected[key] = row['token_ids']
            if set(expected) != set(state['prompts']):
                raise ValueError('baseline coverage incomplete')
        def request(key, phase, repeat):
            prompt = state['prompts'][key]
            stem = f'{phase}-{key}-{repeat}'
            with fetch(args.base_url, '/metrics', timeout=args.timeout) as response:
                before = response.read().decode()
            (out / f'{stem}-metrics-before.txt').write_text(before)
            payload = dict(model=args.model, prompt=prompt, max_tokens=args.max_tokens,
                temperature=0, seed=42, ignore_eos=True, return_token_ids=True,
                stream=True, stream_options={'include_usage': True}, n=1)
            save(out / f'{stem}-request.json', payload)
            events = []
            start = time.perf_counter()
            with (out / f'{stem}-sse.jsonl').open('w') as raw:
                with fetch(args.base_url, '/v1/completions', payload, args.timeout) as response:
                    for line in response:
                        elapsed = time.perf_counter() - start
                        text = line.decode().strip()
                        if text.startswith('data:'):
                            record = {'elapsed_s': elapsed, 'data': text[5:].strip()}
                            events.append(record)
                            raw.write(json.dumps(record) + '\n')
                            raw.flush()
            wall = time.perf_counter() - start
            with fetch(args.base_url, '/metrics', timeout=args.timeout) as response:
                after = response.read().decode()
            (out / f'{stem}-metrics-after.txt').write_text(after)
            row = dict(key=key, phase=phase, repeat=repeat, wall_s=wall,
                **parse_events(events, len(prompt), args.max_tokens),
                **metric_delta(before, after, len(prompt)))
            state['warmups' if phase == 'warmup' else 'rows'].append(row)
            save(out / 'summary.json', state)
            if phase != 'warmup':
                if key in expected and expected[key] != row['token_ids']:
                    raise ValueError(f'full numeric output mismatch: {key} repeat {repeat}')
                expected[key] = row['token_ids']
            print(json.dumps({k: v for k, v in row.items() if k not in ('token_ids', 'token_offsets_s', 'usage', 'raw_delta')}), flush=True)
        for length in lengths:
            request(f'prose-{length}', 'warmup', 0)
        for repeat in range(args.repeats):
            for length in lengths[repeat % len(lengths):] + lengths[:repeat % len(lengths)]:
                for name in CONTEXTS:
                    request(f'{name}-{length}', 'measure', repeat)
        state['by_length'] = {}
        for length in lengths:
            rows = [r for r in state['rows'] if len(state['prompts'][r['key']]) == length]
            state['by_length'][str(length)] = {field: statistics.median([r[field] for r in rows if r[field] is not None]) if any(r[field] is not None for r in rows) else None for field in (
                'ttft_s', 'http_prompt_tokens_per_ttft_s', 'server_prefill_s', 'server_prefill_tokens_per_s', 'decode_token_1_to_100_tps', 'decode_after_ttft_tps')}
        state['passed'] = True
    except Exception as exc:
        state['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        save(out / 'summary.json', state)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--baseline', type=Path)
    ap.add_argument('--lengths', default='128,256,512')
    ap.add_argument('--max-model-len', type=int, default=1024)
    ap.add_argument('--max-tokens', type=int, default=128)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--timeout', type=int, default=600)
    run(ap.parse_args())
