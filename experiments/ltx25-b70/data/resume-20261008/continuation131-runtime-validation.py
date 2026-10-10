#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Two guarded CPU Runtime cases, exact fake outputs, and mocked client preflight.

Never executes launch wrappers. Children use run_tests_131's device/socket/signal
guards; each harness removes only its own /dev/shm scratch in its finally block.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

LANE = Path(__file__).resolve().parents[2]
HERE = LANE / 'recovery/20261010-continuation131-stream'
OUT = Path(__file__).resolve().parent / 'continuation131-tests'
OUT.mkdir(parents=True, exist_ok=True)
PYTHON = '/home/steve/.venvs/ltx25-baseline/bin/python'
assert sys.executable == PYTHON
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--label', default='final', choices=('final', 'recheck'))
parser.add_argument('--reuse-preflight-summary', type=Path)
parser.add_argument('--promote-final', action='store_true')
args = parser.parse_args()


def source_hashes():
    return {str(path.relative_to(LANE.parents[1])): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(HERE.glob('*.py'))}


before_sources = source_hashes()


def execute(command, env, filename):
    log = OUT / filename
    with log.open('x') as stream:
        result = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
    return result, log


rows = []
for mode, dg, display, schedule in [('off', '0', 'xpu:3', 'sampler-a'),
                                    ('replica-release', '1', 'xpu:2', 'eager-display')]:
    env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1',
               LTX_CONE_GRAPH_MEMORY=mode, LTX_DISPLAY_ALLOCATOR_RELEASE='off',
               LTX_DISPLAY_WORKER='serial', LTX_GC_INTERVAL_SECONDS='60',
               LTX_SNAPSHOT_DIGEST_CACHE='1', LTX_STORAGE_SCAN_MODE='background',
               LTX_MAINTENANCE_MODE='idle', LTX_RUN_WRITE_ALLOWANCE_GIB='16')
    env.pop('LTX_DECODER_GRAPH_POOL_CAP_GB', None)
    command = [PYTHON, '-B', str(HERE / 'run_tests_131.py'), '--child', str(HERE / 'harness_runtime.py'),
               '--frames', '145', '--anchor', 'frame', '--decoder-graph', dg,
               '--anchor-decode', 'cone', '--bencode-overlap', '1', '--prep-ahead', '1',
               '--snapshot-mode', 'fingerprint', '--snapshot-schedule', 'full',
               '--anchor-read-ahead', '0', '--display-schedule', schedule,
               '--display-device', display, '--aux-residency', 'legacy', '--stream-chunks', '2',
               '--audio-delay', '0.01', '--decode-delay', '0.01']
    result, log = execute(command, env, 'candidate145-' + mode + '-runtime-' + args.label + '.log')
    lines = log.read_text().splitlines()
    try:
        data = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        data = {'error': 'No final harness JSON; inspect log'}
    good = (result.returncode == 0 and not data.get('error') and not data.get('halted')
            and data.get('verdict', {}).get('passed') and data.get('xpu_initialized') is False
            and data.get('decoder_drained') and data.get('preview_drained')
            and len(data.get('chunks', [])) == 11)
    row = dict(mode=mode, passed=bool(good), returncode=result.returncode, command=command,
               environment={key: value for key, value in env.items() if key.startswith('LTX_')},
               log=str(log.relative_to(LANE.parents[1])), sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
               qualification_chunks=9, stream_chunks=2, xpu_initialized=data.get('xpu_initialized'),
               error=data.get('error'), server_options=data.get('verdict_file', {}).get('server_options'),
               chunks=data.get('chunks'))
    rows.append(row)
    print(json.dumps({k: v for k, v in row.items() if k not in ('chunks', 'command', 'environment')}, ensure_ascii=False), flush=True)
    if not good:
        break

out = dict(schema='ltx.stream131.cpu-runtime.v1', cases=rows,
           scope='Real Runtime, nine qualification chunks and two stream chunks per case, receipts and previews with CPU fake devices/decoder; admission mechanism separately counter-mocked; not native exactness, allocation feasibility or speed')
out['passed'] = len(rows) == 2 and all(row['passed'] for row in rows)
if out['passed']:
    comparisons = [dict(name=a['name'], names_equal=a['name'] == b['name'],
                        decoded_tensors_equal=a['decoded_tensors'] == b['decoded_tensors'],
                        last_frame_equal=a['last_frame_sha256'] == b['last_frame_sha256'])
                   for a, b in zip(rows[0]['chunks'], rows[1]['chunks'])]
    out['off_on_exact_cpu_outputs'] = comparisons
    out['passed'] = len(comparisons) == 11 and all(row['names_equal'] and row['decoded_tensors_equal'] and row['last_frame_equal'] for row in comparisons)

preflight = LANE / 'stream/tests/test_client_preflight_118b.py'
code = ('import runpy, unittest; namespace=runpy.run_path(' + repr(str(preflight)) + '); '
        'suite=unittest.defaultTestLoader.loadTestsFromTestCase(namespace["Preflight118b"]); '
        'result=unittest.TextTestRunner(verbosity=2).run(suite); '
        'raise SystemExit(not (result.wasSuccessful() and result.testsRun == 10))')
if args.reuse_preflight_summary:
    prior = json.loads(args.reuse_preflight_summary.read_bytes())
    out['preflight'] = dict(prior['preflight'], reused=True,
                            prior_summary_sha256=hashlib.sha256(args.reuse_preflight_summary.read_bytes()).hexdigest(),
                            reason='Client preflight inputs unchanged; only recovery residency-scope contract changed')
    log = LANE.parents[1] / out['preflight']['log']
    assert hashlib.sha256(log.read_bytes()).hexdigest() == out['preflight']['sha256']
else:
    command = [PYTHON, '-B', str(HERE / 'run_tests_131.py'), '--child', '-c', code]
    result, log = execute(command, dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1'), 'preflight10-' + args.label + '.log')
    out['preflight'] = dict(passed=result.returncode == 0, returncode=result.returncode, tests=10,
                            command=command, log=str(log.relative_to(LANE.parents[1])),
                            sha256=hashlib.sha256(log.read_bytes()).hexdigest())
out['source_sha256'] = before_sources
out['source_unchanged_during_cases'] = before_sources == source_hashes()
out['passed'] = out['passed'] and out['source_unchanged_during_cases']
out['passed'] = out['passed'] and out['preflight']['passed']
summary_path = OUT / ('candidate-runtime-summary-' + args.label + '.json')
with summary_path.open('x') as handle:
    handle.write(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
if args.promote_final and args.label != 'final' and out['passed']:
    final = OUT / 'candidate-runtime-summary-final.json'
    with (OUT / 'candidate-runtime-summary-development.json').open('xb') as handle:
        handle.write(final.read_bytes())
    final.write_bytes(summary_path.read_bytes())
raise SystemExit(not out['passed'])
