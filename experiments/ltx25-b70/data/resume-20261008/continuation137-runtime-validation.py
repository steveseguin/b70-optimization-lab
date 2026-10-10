#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Three CPU Runtime cases (legacy fixture, production parent, production bulk), exact fake outputs,
and mocked client preflight.

Never executes launch wrappers. Children use run_tests_137's device/socket/signal
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
HERE = LANE / 'recovery/20261010-continuation137-stream'
OUT = Path(__file__).resolve().parent / 'continuation137-tests'
OUT.mkdir(parents=True, exist_ok=True)
PYTHON = '/home/steve/.venvs/ltx25-baseline/bin/python'
assert sys.executable == PYTHON
assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'Run this CPU driver with nice -n 19'
assert os.environ.get('OMP_NUM_THREADS') == '2', 'Run with OMP_NUM_THREADS=2'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--label', default='final', choices=('final', 'recheck', 'fixtures-final'))
args = parser.parse_args()


def source_hashes():
    return {str(path.relative_to(LANE.parents[1])): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(HERE.iterdir()) if path.is_file() and path.suffix in ('.py', '.json', '.sh')}


before_sources = source_hashes()


def execute(command, env, filename):
    log = OUT / filename
    with log.open('x') as stream:
        result = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
    return result, log


rows = []
for label, mode, dg, display, schedule, audio, residency, scan in [
        ('off', 'off', '0', 'xpu:3', 'sampler-a', 'legacy', 'legacy', 'parent'),
        ('split36-parent', 'text-shift', '1', 'xpu:3', 'eager-display', 'legacy', 'split36', 'parent'),
        ('split36-bulk', 'text-shift', '1', 'xpu:3', 'eager-display', 'legacy', 'split36', 'bulk')]:
    env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1',
               LTX_F32_SCAN=scan, LTX_TEXT_RESIDENCY=residency, LTX_AUDIO_RESIDENCY=audio, LTX_CONE_CAPTURE_RESERVE='parent', LTX_CONE_GRAPH_MEMORY=mode, LTX_DISPLAY_ALLOCATOR_RELEASE='off',
               LTX_DISPLAY_WORKER='serial', LTX_GC_INTERVAL_SECONDS='10',
               LTX_SNAPSHOT_DIGEST_CACHE='1', LTX_STORAGE_SCAN_MODE='background',
               LTX_MAINTENANCE_MODE='idle', LTX_RUN_WRITE_ALLOWANCE_GIB='16')
    env.pop('LTX_DECODER_GRAPH_POOL_CAP_GB', None)
    env.pop('LTX_DISPLAY_REPLICA_TRANSIENT_GIB', None)
    command = [PYTHON, '-B', str(HERE / 'run_tests_137.py'), '--child', str(HERE / 'harness_runtime.py'),
               '--frames', '145', '--anchor', 'frame', '--decoder-graph', dg,
               '--anchor-decode', 'cone', '--bencode-overlap', '1', '--prep-ahead', '1',
               '--snapshot-mode', 'fingerprint', '--snapshot-schedule', 'full',
               '--anchor-read-ahead', '0', '--display-schedule', schedule,
               '--display-device', display, '--audio-residency', audio, '--aux-residency', 'legacy', '--stream-chunks', '2',
               '--audio-delay', '0.01', '--decode-delay', '0.01']
    if label != 'off':
        command += ['--cpu-reference-json', str(OUT / ('cpu-parent-output-reference-' + args.label + '.json'))]
    result, log = execute(command, env, 'candidate145-' + label + '-runtime-' + args.label + '.log')
    lines = log.read_text().splitlines()
    try:
        data = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        data = {'error': 'No final harness JSON; inspect log'}
    if label == 'off' and data.get('cpu_reference_document'):
        with (OUT / ('cpu-parent-output-reference-' + args.label + '.json')).open('x') as handle:
            handle.write(json.dumps(data['cpu_reference_document'], indent=2) + '\n')
    good = (result.returncode == 0 and not data.get('error') and not data.get('halted')
            and data.get('verdict', {}).get('passed') and data.get('xpu_initialized') is False
            and data.get('decoder_drained') and data.get('preview_drained')
            and len(data.get('chunks', [])) == 11
            and data.get('verdict_file', {}).get('server_options', {}).get('f32_scan') == scan)
    row = dict(mode=mode, f32_scan=scan, text_residency=residency, audio_residency=audio, passed=bool(good), returncode=result.returncode, command=command,
               environment={key: value for key, value in env.items() if key.startswith('LTX_')},
               log=str(log.relative_to(LANE.parents[1])), sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
               qualification_chunks=9, stream_chunks=2, xpu_initialized=data.get('xpu_initialized'),
               error=data.get('error'), server_options=data.get('verdict_file', {}).get('server_options'),
               chunks=data.get('chunks'))
    rows.append(row)
    print(json.dumps({k: v for k, v in row.items() if k not in ('chunks', 'command', 'environment')}, ensure_ascii=False), flush=True)
    if not good:
        break

out = dict(schema='ltx.stream137.cpu-runtime.v1', cases=rows,
           scope='Real Runtime with actual anchor-file finite scanner, nine qualification chunks and two stream chunks per case; CPU fake devices, decoder and NativeBindings. Separate predicate/native-binding unit tests cover the guard scanner. Not native exactness, allocation feasibility or speed')
out['passed'] = len(rows) == 3 and all(row['passed'] for row in rows)
if out['passed']:
    comparisons = [dict(reference_scan=rows[0]['f32_scan'], candidate_scan=other['f32_scan'], name=a['name'], names_equal=a['name'] == b['name'],
                        decoded_tensors_equal=a['decoded_tensors'] == b['decoded_tensors'],
                        last_frame_equal=a['last_frame_sha256'] == b['last_frame_sha256'])
                   for other in rows[1:] for a, b in zip(rows[0]['chunks'], other['chunks'])]
    out['off_on_exact_cpu_outputs'] = comparisons
    direct = [dict(name=a['name'], names_equal=a['name'] == b['name'],
                   decoded_tensors_equal=a['decoded_tensors'] == b['decoded_tensors'],
                   last_frame_equal=a['last_frame_sha256'] == b['last_frame_sha256'])
              for a, b in zip(rows[1]['chunks'], rows[2]['chunks'])]
    out['production_parent_bulk_exact_cpu_outputs'] = direct
    out['reference_scope'] = 'Synthetic CPU fake-numerics reference generated by legacy parent fixture, not native output authority'
    out['matched_production_configs'] = {key: value for key, value in rows[1]['environment'].items() if key != 'LTX_F32_SCAN'} == {key: value for key, value in rows[2]['environment'].items() if key != 'LTX_F32_SCAN'}
    out['passed'] = len(comparisons) == 22 and all(row['names_equal'] and row['decoded_tensors_equal'] and row['last_frame_equal'] for row in comparisons)
    out['passed'] = out['passed'] and out['matched_production_configs'] and len(direct) == 11 and all(row['names_equal'] and row['decoded_tensors_equal'] and row['last_frame_equal'] for row in direct)

preflight = LANE / 'stream/tests/test_client_preflight_118b.py'
code = ('import runpy, unittest; namespace=runpy.run_path(' + repr(str(preflight)) + '); '
        'suite=unittest.defaultTestLoader.loadTestsFromTestCase(namespace["Preflight118b"]); '
        'result=unittest.TextTestRunner(verbosity=2).run(suite); '
        'raise SystemExit(not (result.wasSuccessful() and result.testsRun == 10))')
command = [PYTHON, '-B', str(HERE / 'run_tests_137.py'), '--child', '-c', code]
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
raise SystemExit(not out['passed'])
