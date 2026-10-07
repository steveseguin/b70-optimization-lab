#!/usr/bin/env python3
"""Seed-7 one-batch extraction calibration; true prior state, not a memory benchmark."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
from pathlib import Path
import re
import time

from pilot import (ask, atomic, append, StubClient, HTTPClient, busy_endpoint, endpoint_lock_path,
                   ANSWER_GENERATION, INGESTION_GENERATION)
from tasks import verify


DEVELOPMENT_INDICES = [1, 2, 3, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 47, 48]


def source_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('test_')}


def signature(event):
    if not isinstance(event, dict) or not {'counter', 'op', 'amount', 'quote'} <= set(event):
        raise ValueError('event must contain counter, op, amount and quote')
    if set(event) - {'id', 'counter', 'op', 'amount', 'quote'}:
        raise ValueError('unknown event fields')
    counter, op, amount, quote = (event[k] for k in ('counter', 'op', 'amount', 'quote'))
    if not isinstance(counter, str) or not re.fullmatch(r'[a-z]+[0-9]{2}', counter):
        raise ValueError('counter must be a ledger name')
    if not isinstance(op, str) or op not in {'set', 'add', 'sub', 'remove', 'reopen'}:
        raise ValueError('unsupported event operation')
    if ((op == 'remove' and amount is not None) or (op != 'remove' and type(amount) is not int)
            or (op in {'add', 'sub'} and amount <= 0)):
        raise ValueError('amount must be an integer, positive for add/sub, or null for remove')
    if not isinstance(quote, str) or not quote.strip():
        raise ValueError('quote must be a nonempty string')
    return counter, op, amount, ' '.join(quote.split())


def validate_indices(indices, batches):
    if (not isinstance(indices, (list, tuple)) or not indices or len(indices) > min(32, batches)
            or any(type(n) is not int or not 1 <= n <= batches for n in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError('select 1–32 unique integer batch indices within this task')


def diagnose(task, client, out, indices, *, limit=32768, identity=None):
    verify(task)
    validate_indices(indices, len(task['batches']))
    if type(limit) is not int or not 12000 <= limit <= 32768:
        raise ValueError('calibration context budget must be 12000–32768 UTF-8 bytes')
    if client.kind == 'model' and task['seed'] != 7:
        raise ValueError('live extraction calibration is restricted to development seed 7')
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    provenance = {'protocol': 'durable-context-r4', 'task_sha256': task['task_sha256'], 'measurement_kind': client.kind,
                  'answer_generation': dict(ANSWER_GENERATION), 'ingestion_generation': dict(INGESTION_GENERATION),
                  'seed': task['seed'], 'style': task['style'], 'indices': list(indices),
                  'source_sha256': source_hashes(), 'context_limit_utf8_bytes': limit,
                  'model': getattr(client, 'model', None), 'endpoint': getattr(client, 'endpoint', None),
                  'server_identity': identity,
                  'scope': 'True prior state supplied independently each batch; no long-term memory measured.'}
    atomic(out / 'identity.json', provenance)
    atomic(out / 'status.json', {'status': 'started', 'time': time.time()})
    rows = []
    try:
        for n in indices:
            if source_hashes() != provenance['source_sha256']:
                raise ValueError('source files changed during calibration')
            batch = task['batches'][n-1]
            response = ask(client, out, {
                'instruction': 'Extract every actual counter update in source order. Return {"events":[{"counter":"name","op":"set|add|sub","amount":1,"quote":"exact complete source sentence"}]}.',
                'state': task['oracle']['after_batch'][n-2] if n > 1 else {},
                'batch_id': n, 'text': batch['text']}, 'extract', n, limit)
            expected_order = [signature(e) for e in task['oracle']['events'][n-1]]
            expected = Counter(expected_order)
            events = response.get('events')
            valid, error = isinstance(events, list), None
            try:
                actual_order = [signature(e) for e in events] if valid else []
                actual = Counter(actual_order)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                valid, error, actual_order, actual = False, str(exc), [], Counter()
            matched = sum((expected & actual).values())
            row = {'batch_id': n, 'valid_format': valid, 'format_error': error,
                   'expected_events': sum(expected.values()), 'predicted_events': sum(actual.values()),
                   'matched_events': matched, 'missed_events': sum((expected - actual).values()),
                   'extra_events': sum((actual - expected).values()),
                   'exact_order': valid and actual_order == expected_order}
            rows.append(row); append(out / 'rows.jsonl', row)
        if source_hashes() != provenance['source_sha256']:
            raise ValueError('source files changed during calibration')
        expected = sum(row['expected_events'] for row in rows)
        predicted = sum(row['predicted_events'] for row in rows)
        matched = sum(row['matched_events'] for row in rows)
        recall = matched / expected if expected else 0
        precision = matched / predicted if predicted else 0
        result = {**provenance, 'schema': 'durable-extraction-diagnostic.v4', 'status': 'completed',
                  'rows': rows, 'event_recall': recall, 'event_precision': precision,
                  'gate_passed': (client.kind == 'model' and bool(expected)
                                  and all(row['valid_format'] and row['exact_order'] for row in rows)
                                  and recall == 1 and precision == 1),
                  'gate_policy': '100% exact event/quote extraction in source order on the selected batches; campaign qualification additionally requires the fixed 16-batch development selection and task identity.',
                  'limit': 'Exact event/quote format diagnostic; semantic equivalents may be conservatively counted wrong.'}
        atomic(out / 'result.json', result)
        atomic(out / 'status.json', {'status': 'completed', 'time': time.time()})
        return result
    except BaseException as exc:
        failure = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}',
                   'completed_batches': len(rows), 'time': time.time()}
        append(out / 'failures.jsonl', failure); atomic(out / 'status.json', failure)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--indices', type=int, nargs='+', default=DEVELOPMENT_INDICES,
                        help='defaults to the fixed 16 development batches; custom selections are diagnostic only')
    parser.add_argument('--stub', action='store_true'); parser.add_argument('--endpoint')
    parser.add_argument('--model', default='qwen38-27b-fp8'); parser.add_argument('--server-identity', type=Path)
    parser.add_argument('--context-bytes', type=int, default=32768)
    args = parser.parse_args(); task = json.loads(args.task.read_text())
    try:
        validate_indices(args.indices, len(task['batches']))
    except ValueError as exc:
        parser.error(str(exc))
    if not args.stub and (not args.endpoint or not args.server_identity):
        parser.error('live calibration requires --endpoint and --server-identity')
    client = StubClient(task) if args.stub else HTTPClient(args.endpoint, args.model)
    identity = None if args.stub else {'endpoint': args.endpoint, 'model': args.model,
        'launch_sha256': hashlib.sha256(args.server_identity.read_bytes()).hexdigest()}
    with endpoint_lock_path(None if args.stub else args.endpoint).open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not args.stub and busy_endpoint(args.endpoint):
            raise RuntimeError('protected campaign active; no requests sent')
        print(json.dumps(diagnose(task, client, args.out, args.indices,
                                 limit=args.context_bytes, identity=identity), indent=2))


if __name__ == '__main__':
    main()
