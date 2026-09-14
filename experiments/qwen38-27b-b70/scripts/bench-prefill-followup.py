#!/usr/bin/env python3
"""Bounded serial prefill measurements from unrepeated repository excerpts.

Imports the frozen short-prefill wire parsers without modifying its workload.
Owns HTTP clients only: failures never restart a server. Full token output,
raw SSE, histogram snapshots, source text, and input identities are retained.
This continuation-shape screen does not replace the natural-completion gate.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import time

HERE = Path(__file__).resolve().parent
PARSER_PATH = HERE / 'bench-short-prefill.py'
CORPUS_PATH = HERE.parent / 'data/2026-09-13-prefill-followup-corpus.json'
spec = importlib.util.spec_from_file_location('frozen_short_prefill', PARSER_PATH)
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)
save, fetch, parse_events = wire.save, wire.fetch, wire.parse_events
FIELDS = ('server_prefill_s', 'server_prefill_tokens_per_s', 'ttft_s',
          'http_prompt_tokens_per_ttft_s', 'decode_token_1_to_100_tps',
          'decode_after_ttft_tps')
CLASSES = ('prose', 'code', 'docs')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_corpus(path):
    corpus = json.loads(path.read_text())
    if corpus.get('source_repetition') is not False:
        raise ValueError('corpus must declare unrepeated source text')
    entries = corpus['sources']
    if [entry['label'] for entry in entries] != list(CLASSES):
        raise ValueError('corpus must contain prose, code, docs in order')
    for entry in entries:
        if sha(entry['text'].encode()) != entry['text_sha256']:
            raise ValueError(f"corpus text hash differs: {entry['label']}")
    return corpus


def required_metric_delta(before, after, length):
    row = wire.metric_delta(before, after, length)
    for field in ('server_prefill_s', 'server_prefill_tokens_per_s'):
        value = row[field]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'missing or invalid server-prefill histogram: {field}')
    return row


def aggregate(rows, prompts, lengths, repeats):
    result = {}
    for length in lengths:
        classes = {}
        for name in CLASSES:
            selected = [row for row in rows if row['key'] == f'{name}-{length}']
            if len(selected) != repeats or {r['repeat'] for r in selected} != set(range(repeats)):
                raise ValueError(f'incomplete repeat coverage: {name}-{length}')
            if len(prompts[f'{name}-{length}']) != length:
                raise ValueError('input length differs from declared length')
            classes[name] = {field: statistics.median(row[field] for row in selected)
                             for field in FIELDS}
        result[str(length)] = {
            **{field: statistics.median(classes[name][field] for name in CLASSES)
               for field in FIELDS},
            'samples': repeats * len(CLASSES), 'class_medians': classes,
            'aggregation': 'median within each class, then median across classes',
        }
    return result


def baseline_outputs(baseline, state):
    if baseline.get('passed') is not True:
        raise ValueError('baseline did not pass')
    if baseline.get('prompts') != state['prompts']:
        raise ValueError('baseline prompt IDs differ')
    if (baseline.get('corpus_sha256') != state['corpus_sha256'] or
            baseline['args']['max_tokens'] != state['args']['max_tokens']):
        raise ValueError('baseline corpus/output contract differs')
    expected = {}
    for row in baseline['rows']:
        ids = row['token_ids']
        if len(ids) != state['args']['max_tokens'] or any(type(x) is not int for x in ids):
            raise ValueError('baseline output IDs invalid')
        if row['key'] in expected and expected[row['key']] != ids:
            raise ValueError('baseline itself has output divergence')
        expected[row['key']] = ids
    if set(expected) != set(state['prompts']):
        raise ValueError('baseline coverage incomplete')
    return expected


def run(args):
    lengths = [int(x) for x in args.lengths.split(',')]
    if (not lengths or lengths != sorted(set(lengths)) or min(lengths) < 1 or
            max(lengths) + args.max_tokens > args.max_model_len or
            args.repeats < 2 or args.max_tokens < 100):
        raise ValueError('require ascending unique lengths, context fit, repeats >=2, output >=100')
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='neural.download.prefill-followup-client.v1', passed=False,
                 args={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                 corpus_sha256=sha(args.corpus.read_bytes()),
                 parser_sha256=sha(PARSER_PATH.read_bytes()),
                 client_sha256=sha(Path(__file__).read_bytes()),
                 prompts={}, rows=[], warmups=[], notes=[
                     'Unrepeated prose/code/documentation excerpts; numeric-token continuation prompts.',
                     'One user, zero cached tokens; ignore_eos with 128 output tokens by default.',
                     'Server histogram: first scheduled execution to first token, not isolated kernel time.',
                     'HTTP TTFT and HTTP tokens/TTFT proxy are separate metrics.',
                     'SSE burst tokens share arrival timestamps; token 1–100 uses 99 numeric-token intervals.',
                     'Separate warmups; repeated outputs checked completely. Screening, not speed promotion.'])
    save(out / 'summary.json', state)
    try:
        corpus = load_corpus(args.corpus)
        (out / 'corpus.json').write_bytes(args.corpus.read_bytes())
        for entry in corpus['sources']:
            name = entry['label']
            payload = {'model': args.model, 'prompt': entry['text'], 'add_special_tokens': False}
            save(out / f'tokenize-{name}-request.json', payload)
            with fetch(args.base_url, '/tokenize', payload, args.timeout) as response:
                tokenized = json.load(response)
            save(out / f'tokenize-{name}.json', tokenized)
            ids = tokenized.get('tokens')
            if (not isinstance(ids, list) or len(ids) < max(lengths) or
                    any(type(x) is not int or x < 0 for x in ids)):
                raise ValueError('/tokenize did not return enough valid numeric tokens; no source repetition allowed')
            for length in lengths:
                state['prompts'][f'{name}-{length}'] = ids[:length]
        state['prompt_sha256s'] = {key: sha(json.dumps(ids, separators=(',', ':')).encode())
                                  for key, ids in state['prompts'].items()}
        expected = baseline_outputs(json.loads(args.baseline.read_text()), state) if args.baseline else {}

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
                       **required_metric_delta(before, after, len(prompt)))
            state['warmups' if phase == 'warmup' else 'rows'].append(row)
            save(out / 'summary.json', state)
            if any(not isinstance(row[field], (int, float)) or not math.isfinite(row[field])
                   or row[field] <= 0 for field in FIELDS):
                raise ValueError('missing or invalid timing metric')
            if key in expected and expected[key] != row['token_ids']:
                raise ValueError(f'full numeric output mismatch: {key} {phase} repeat {repeat}')
            # Warmups establish parity too, but never enter measured aggregation.
            expected[key] = row['token_ids']
            print(json.dumps({k: v for k, v in row.items() if k not in
                              ('token_ids', 'token_offsets_s', 'usage', 'raw_delta')}), flush=True)

        for length in lengths:
            request(f'prose-{length}', 'warmup', 0)
        for repeat in range(args.repeats):
            for length in lengths[repeat % len(lengths):] + lengths[:repeat % len(lengths)]:
                for name in CLASSES[repeat % len(CLASSES):] + CLASSES[:repeat % len(CLASSES)]:
                    request(f'{name}-{length}', 'measure', repeat)
        state['by_length'] = aggregate(state['rows'], state['prompts'], lengths, args.repeats)
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
    ap.add_argument('--corpus', type=Path, default=CORPUS_PATH)
    ap.add_argument('--lengths', default='256,512')
    ap.add_argument('--max-model-len', type=int, default=1024)
    ap.add_argument('--max-tokens', type=int, default=128)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--timeout', type=int, default=600)
    run(ap.parse_args())
