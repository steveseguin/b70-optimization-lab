#!/usr/bin/env python3
"""Retain closed pipeline-run metadata without copying raw state arrays.

The resulting state-set.json feeds engine/tools/compare_pipeline_state.py.
Raw arrays remain at their recorded source paths, hashes, and sizes until the
coordinator archives them. This script does not launch or stop anything.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--dest', required=True, type=Path)
    args = parser.parse_args()
    run, dest = args.run.resolve(), args.dest.resolve()
    result = json.loads((run / 'result.json').read_text())
    require(result['passed'] is True and result['error'] is None and not result['live_pids']
            and all(code == 0 for code in result['returncodes'].values()), 'closed successful run required')
    plan = json.loads((run / 'plan.json').read_text())
    require(plan['mode'] == result['mode'] == 'target-only', 'target-only run required')
    require(result['input_position'] == len(plan['prompt_tokens']) + len(result['output_ids']) - 1,
            'terminal position differs from prompt/output count')
    pins = plan['pins']
    engine_pins = [value for key, value in pins.items() if key.endswith('/own-engine')]
    require(len(engine_pins) == 1, 'unique binary pin required')
    staged = []
    inventory, raw_arrays, stages = [], [], []
    def keep(path, relative):
        data = path.read_bytes()
        staged.append((relative, data))
        inventory.append({'source': str(path), 'retained': str(relative), 'sha256': sha(data), 'bytes': len(data)})
    for name in ('result.json', 'plan.json', 'admission.json', 'unit.json', 'tokens.jsonl', 'observations.jsonl'):
        keep(run / name, Path(name))
    for stage in plan['stages']:
        ordinal = stage['id']
        relative = Path(f'stage{ordinal}')
        native = Path(stage['native_output'])
        dump = native / 'state-2147483647'
        for name in ('launch-plan.json', 'pipeline-stage.json'):
            keep(native / name, relative / name)
        for name in ('state.json', 'state-index.tsv', 'state-seal.txt'):
            keep(dump / name, relative / 'state-2147483647' / name)
        keep(run / relative / 'launch.json', relative / 'launch.json')
        keep(run / relative / 'process.log', relative / 'process.log')
        seal = (dump / 'state-seal.txt').read_text().splitlines()
        require(len(seal) == 5 and seal[0] == 'GSQ_STATE_SEAL_V1', 'invalid state seal')
        bundle = dump / 'state.bundle'
        require(bundle.stat().st_size == int(seal[1]), 'state bundle length differs from seal')
        raw_arrays.append({'path': str(bundle), 'bytes': int(seal[1]), 'sha256_from_seal': seal[2],
                           'metadata_retained': str(relative / 'state-2147483647'),
                           'verification': 'Full payload verification is performed by the separate sealed-state comparator.',
                           'archive_status': 'pending coordinator durable archive; RAM source is not durable'})
        stages.append({'id': ordinal, 'begin': stage['begin'], 'end': stage['end'], 'dump': str(dump),
                       'plan': str(relative / 'launch-plan.json'), 'metadata': str(relative / 'pipeline-stage.json')})
    identity = {'model_sha256': plan['model_identity_sha256'],
                'prompt_token_sha256': sha(json.dumps(plan['prompt_tokens'], separators=(',', ':')).encode()),
                'output_token_sha256': sha(json.dumps(result['output_ids'], separators=(',', ':')).encode()),
                'arithmetic': plan['activation_dtype'], 'engine_sha256': engine_pins[0],
                'position': result['input_position']}
    manifest = {'schema': 'ownrt.pipeline-state-set.v1', 'mode': 'target-only',
                'layer_count': plan['boundaries'][-1], 'input_identity': identity, 'stages': stages}
    rows = [json.loads(line) for line in (run / 'tokens.jsonl').read_text().splitlines() if line]
    require([row['token'] for row in rows] == result['output_ids'], 'timing/output token rows differ')
    timing = {'schema': 'ownrt.pipeline-step-diagnostic.v1', 'qualifying': False, 'speed_claim': False,
              'output_tokens': len(rows), 'prompt_tokens': len(plan['prompt_tokens']), 'mode': 'target-only',
              'window': 'one elapsed target half-chain per generated token, including first output; not first-99 inter-token timestamps',
              'step_ms_mean': statistics.mean(row['elapsed_ms'] for row in rows),
              'step_ms_median': statistics.median(row['elapsed_ms'] for row in rows),
              'stage_ms_mean': [statistics.mean(row['stage_ms'][i] for row in rows) for i in range(len(stages))],
              'wall_seconds_including_startup': result['wall_seconds'],
              'limitations': 'One 87-token prompt and 32-token answer; serial target-only stages, no MTP, no full suite or independent repeat.'}
    for name, data in [('state-set.json', manifest), ('retention.json', {'files': inventory, 'raw_arrays': raw_arrays}),
                       ('timing-diagnostic.json', timing)]:
        staged.append((Path(name), (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode()))
    dest.mkdir(parents=True, exist_ok=False)
    for relative, data in staged:
        out = dest / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open('xb') as f:
            f.write(data)
    print(json.dumps({'state_set': str(dest / 'state-set.json'), 'raw_state_bytes': sum(row['bytes'] for row in raw_arrays),
                      'timing': timing}, indent=2))


if __name__ == '__main__':
    main()
