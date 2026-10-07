#!/usr/bin/env python3
"""One frozen, representative worker request; never execute its proposed action."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'worker'))
from model import LocalModel
from run import SYSTEM

ISSUE = ('This is a no-execution workflow smoke check. Return one command that prints '
         'pilot-ok. Do not inspect or edit files, run tests, or submit a completed task.')
USER = ('Issue: ' + ISSUE + '\n\nAcceptance command: printf "%s\\n" pilot-ok\n'
        'Read relevant project instructions, fix the issue, and add an appropriate regression test.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--server-state', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    if any((args.server_state / name).exists() for name in ('STOP', 'FAULT.json', 'shutdown.json')):
        raise RuntimeError('Server unavailable or faulted; no request sent')
    os.environ['MSWEA_GLOBAL_CONFIG_DIR'] = str(args.out / 'mini-config')
    os.environ['MSWEA_SILENT_STARTUP'] = '1'
    profile = (HERE / 'worker-profile.json').read_bytes()
    config = json.loads(profile)
    model = LocalModel(config['base_url'], config['model'], args.out / 'requests',
                       config['max_input_tokens'], config['max_output_tokens'],
                       generation=config.get('generation'),
                       observation_format=config['observation_format'])
    result = {'schema': 'lab.worker-transport.v1', 'no_commands_executed': True,
              'status': 'failed', 'model': config['model'],
              'system_sha256': hashlib.sha256(SYSTEM.encode()).hexdigest(),
              'profile_sha256': hashlib.sha256(profile).hexdigest()}
    try:
        boundary = json.loads((HERE / 'boundary-protocol.json').read_text())
        if result['system_sha256'] != boundary['worker_system_sha256']:
            raise ValueError('Frozen worker instructions changed')
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': USER}]
        with model.fetch('/tokenize', {'model': model.model, 'messages': messages,
                'add_generation_prompt': True, 'chat_template_kwargs': model.template_kwargs}) as stream:
            count = json.load(stream)['count']
        if type(count) is not int or count <= 300:
            raise ValueError('Actual worker prompt is unexpectedly short for the restricted runtime')
        result['admitted_input_tokens'] = count
        if any((args.server_state / name).exists() for name in ('STOP', 'FAULT.json', 'shutdown.json')):
            raise RuntimeError('Server became unavailable; no generation sent')
        response = model.query(messages)
        wire = json.loads((args.out / 'requests/001/response.json').read_text())
        if wire.get('token_ids_available') is not True or len(wire.get('token_ids', [])) != wire['completion_tokens']:
            raise ValueError('Complete output token identities are required')
        actions = response['extra']['actions']
        if len(actions) != 1:
            raise ValueError('Expected exactly one action')
        words = shlex.split(actions[0]['command'])
        if words not in [['echo', 'pilot-ok'], ['printf', '%s\\n', 'pilot-ok'],
                         ['printf', 'pilot-ok\\n']]:
            raise ValueError('Canary did not propose the requested simple marker print')
        result.update(status='passed', proposed_message=response)
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
        (args.server_state / 'STOP').write_text('Transport gate failed; no retry.\n')
    result.update(model_requests=len(model.calls), requests=model.calls)
    with (args.out / 'result.json').open('w') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
