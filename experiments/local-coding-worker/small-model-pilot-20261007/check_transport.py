#!/usr/bin/env python3
"""One real worker-adapter request, without executing the proposed action."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'worker'))
from model import LocalModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--server-state', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    if (args.server_state / 'FAULT.json').exists() or (args.server_state / 'shutdown.json').exists():
        raise RuntimeError('Server unavailable or faulted; no request sent')
    os.environ['MSWEA_GLOBAL_CONFIG_DIR'] = str(args.out / 'mini-config')
    os.environ['MSWEA_SILENT_STARTUP'] = '1'
    config = json.loads((HERE / 'worker-profile.json').read_text())
    model = LocalModel(config['base_url'], config['model'], args.out / 'requests',
                       max_input_tokens=512, max_output_tokens=64, observation_format='tool_response')
    result = {'schema': 'lab.small-model-transport.v1', 'no_commands_executed': True,
              'status': 'failed', 'model': config['model']}
    try:
        response = model.query([
            {'role': 'system', 'content': 'You are a coding assistant. Reply with exactly one fenced bash code block.'},
            {'role': 'user', 'content': 'Return a command that prints pilot-ok. Do not add any explanation.'},
        ])
        result.update(status='passed', proposed_message=response)
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
        (args.server_state / 'STOP').write_text('Transport gate failed; no retry.\n')
    result.update(model_requests=len(model.calls), requests=model.calls)
    with (args.out / 'result.json').open('w') as stream:
        json.dump(result, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__': raise SystemExit(main())
