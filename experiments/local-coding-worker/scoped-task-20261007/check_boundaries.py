#!/usr/bin/env python3
"""Frozen finite prompt-boundary diagnostic; no retries or model-quality claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'worker'))
from model import LocalModel
from run_guarded_worker import make_health_guard, guard_model


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--server-state', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    profile_bytes = (HERE / 'worker-profile.json').read_bytes()
    profile = json.loads(profile_bytes)
    protocol_bytes = (HERE / 'boundary-protocol.json').read_bytes()
    protocol = json.loads(protocol_bytes)
    result = {'schema': 'lab.worker.boundary-diagnostic.v1', 'status': 'failed',
              'scope': 'finite marker/repeat diagnostic; not an arithmetic oracle or general qualification',
              'profile_sha256': hashlib.sha256(profile_bytes).hexdigest(),
              'protocol_sha256': hashlib.sha256(protocol_bytes).hexdigest(),
              'started_epoch_s': time.time(), 'requests': []}
    healthy = make_health_guard(args.server_state)
    def timeout(signum, frame):
        raise TimeoutError('Boundary diagnostic exceeded 300 seconds')
    def interrupted(signum, frame):
        raise InterruptedError('Boundary diagnostic interrupted')
    old_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        healthy()
        if protocol['profile_sha256'] != result['profile_sha256']:
            raise ValueError('Frozen profile changed')
        save(args.out / 'protocol.json', protocol)
        model = LocalModel(profile['base_url'], profile['model'], args.out / 'requests',
                           max_input_tokens=28000, max_output_tokens=16,
                           generation=profile.get('generation'))
        guard_model(model, healthy, minimum_input_exclusive=1)
        if model.thinking:
            raise ValueError('Boundary protocol requires nonthinking generation')
        signal.signal(signal.SIGALRM, timeout); signal.alarm(300)
        observed = {}
        for index, case_id in enumerate(protocol['order'], 1):
            healthy()
            case = protocol['cases'][case_id]
            messages = case['messages']
            with model.fetch('/tokenize', {'model': model.model, 'messages': messages,
                    'add_generation_prompt': True, 'chat_template_kwargs': model.template_kwargs}) as stream:
                count = json.load(stream)['count']
            if count != case['input_tokens'] or count <= 1:
                raise ValueError('Frozen CPU/server token count differs or unsupported one-token prompt')
            directory = model.out / f'{index:03d}'; directory.mkdir()
            save(directory / 'token-count.json', {'input_tokens': count, 'expected': case['input_tokens']})
            payload = {'model': model.model, 'messages': messages, **model.sampling,
                       'max_tokens': 16, 'n': 1, 'stream': True,
                       'stream_options': {'include_usage': True}, 'return_token_ids': True,
                       'chat_template_kwargs': model.template_kwargs}
            with model.fetch('/metrics') as stream: before = stream.read().decode()
            (directory / 'metrics-before.txt').write_text(before)
            healthy()
            attempt = {'directory': directory.name, 'case': case_id, 'input_tokens': count,
                       'status': 'attempted'}
            result['requests'].append(attempt)
            response = model.wire.request_one(model.base, payload, directory, opener=model.opener.open)
            save(directory / 'response.json', response)
            healthy()
            with model.fetch('/metrics') as stream: after = stream.read().decode()
            (directory / 'metrics-after.txt').write_text(after)
            save(directory / 'metric-delta.json', model.metrics_wire.metric_delta(before, after, count))
            if response['prompt_tokens'] != count or response['cached_tokens'] != 0:
                raise ValueError('Prompt accounting/cache mismatch')
            if response.get('token_ids_available') is not True or len(response['token_ids']) != response['completion_tokens']:
                raise ValueError('Complete token identities required')
            if response['text'].strip() != case['expected_text']:
                raise ValueError('Marker output differs from frozen expectation')
            if case_id in observed and observed[case_id] != response['token_ids']:
                raise ValueError('Identical prompt produced different output token IDs')
            observed[case_id] = response['token_ids']
            attempt.update(status='passed', output_tokens=response['completion_tokens'])
            print(f'Boundary {index}/{len(protocol["order"])}: {count} tokens passed', flush=True)
        result['status'] = 'passed'
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = f'{type(error).__name__}: {error}'
        if args.server_state.is_dir() and not (args.server_state / 'STOP').exists():
            (args.server_state / 'STOP').write_text('Boundary gate failed; no retry.\n')
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGTERM, old_term)
        result['finished_epoch_s'] = time.time()
        save(args.out / 'result.json', result)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
