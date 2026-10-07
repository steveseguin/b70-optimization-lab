#!/usr/bin/env python3
"""One frozen, representative worker request; never execute its proposed action."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'worker'))
from model import LocalModel
from run import SYSTEM, instance_prompt
from run_guarded_worker import make_health_guard, guard_model

ISSUE = ('This is a no-execution workflow smoke check. Return one command that prints '
         'pilot-ok. Do not inspect or edit files, run tests, or submit a completed task.')
def messages_for_canary():
    # Exercise the same instance-template/scoped-notice construction with a dummy
    # scope. No real issue, source path, known fix or task-specific hint is sent.
    from jinja2 import Template
    template, variables = instance_prompt({'source_scope': {
        'mode': 'explicit-task-scope', 'selected_files': {'AGENTS.md': {}},
        'allowed_new_paths': []}})
    user = Template(template).render(task=ISSUE,
        acceptance_command='printf "%s\\n" pilot-ok', **variables)
    return [{'role':'system','content':SYSTEM}, {'role':'user','content':user}]



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--server-state', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    healthy = make_health_guard(args.server_state)
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
    def interrupted(signum, frame):
        raise InterruptedError('Transport canary interrupted')
    old_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        healthy()
        guard_model(model, healthy)
        messages = messages_for_canary()
        with (args.out / 'prompt.json').open('x') as stream:
            json.dump(messages, stream, ensure_ascii=False, indent=2); stream.write('\n')
        result['messages_sha256'] = hashlib.sha256(json.dumps(messages, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        response = model.query(messages)
        wire = json.loads((args.out / 'requests/001/response.json').read_text())
        if wire.get('token_ids_available') is not True or len(wire.get('token_ids', [])) != wire['completion_tokens']:
            raise ValueError('Complete output token identities are required')
        actions = response['extra']['actions']
        if len(actions) != 1:
            raise ValueError('Expected exactly one action')
        words = shlex.split(actions[0]['command'])
        if words not in [['echo', 'pilot-ok'], ['printf', r'%s\n', 'pilot-ok'],
                         ['printf', r'pilot-ok\n']]:
            raise ValueError('Canary did not propose the requested simple marker print')
        result.update(status='passed', proposed_message=response)
    except (Exception, KeyboardInterrupt) as error:
        result['error'] = f'{type(error).__name__}: {error}'
        if not (args.server_state / 'STOP').exists():
            (args.server_state / 'STOP').write_text('Transport gate failed; no retry.\n')
    finally:
        signal.signal(signal.SIGTERM, old_term)
    result.update(model_requests=len(model.calls), requests=model.calls)
    with (args.out / 'result.json').open('w') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
