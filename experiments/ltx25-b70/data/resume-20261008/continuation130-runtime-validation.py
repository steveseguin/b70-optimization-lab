#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU runtime and output identity cases; never executes a launch wrapper."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

LANE = Path(__file__).resolve().parents[2]
HERE = LANE / 'recovery/20261010-continuation130-stream'
OUT = Path(__file__).resolve().parent / 'continuation130-tests'
rows = []
for mode in ('off', 'before-admission'):
    env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1',
        LTX_DISPLAY_ALLOCATOR_RELEASE=mode, LTX_DISPLAY_WORKER='parallel',
        LTX_GC_INTERVAL_SECONDS='10', LTX_SNAPSHOT_DIGEST_CACHE='0',
        LTX_STORAGE_SCAN_MODE='background', LTX_MAINTENANCE_MODE='idle',
        LTX_RUN_WRITE_ALLOWANCE_GIB='16', LTX_DISPLAY_REPLICA_TRANSIENT_GIB='6.5')
    command = [sys.executable, '-B', str(HERE/'run_tests_130.py'), '--child', str(HERE/'harness_runtime.py'),
        '--frames', '169', '--anchor', 'frame', '--decoder-graph', '0',
        '--anchor-decode', 'cone', '--bencode-overlap', '1', '--prep-ahead', '1',
        '--snapshot-mode', 'fingerprint', '--display-schedule', 'eager-display',
        '--display-device', 'xpu:2', '--aux-residency', 'legacy', '--stream-chunks', '2',
        '--audio-delay', '0.01', '--decode-delay', '0.01']
    log = OUT / ('candidate169-' + mode + '-runtime.log')
    with log.open('x') as stream:
        result = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
    lines = log.read_text().splitlines()
    d = json.loads(lines[-1])
    good = (result.returncode == 0 and not d.get('error') and not d.get('halted')
            and d.get('verdict', {}).get('passed') and d.get('xpu_initialized') is False
            and d.get('decoder_drained') and d.get('preview_drained') and len(d.get('chunks', [])) == 11)
    row = dict(mode=mode, passed=bool(good), returncode=result.returncode, command=command,
               log=str(log.relative_to(LANE.parents[1])), sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
               qualification_chunks=9, stream_chunks=2, xpu_initialized=d.get('xpu_initialized'),
               error=d.get('error'), server_options=d.get('verdict_file', {}).get('server_options'),
               chunks=d.get('chunks'))
    rows.append(row)
    print(json.dumps({k:v for k,v in row.items() if k not in ('chunks','command')}, ensure_ascii=False), flush=True)
    if not good: break
out = dict(schema='ltx.stream130.cpu-runtime.v1', cases=rows,
           scope='Real Runtime, qualification, receipts and previews with CPU fake devices/decoder; allocator mechanism separately tested with counters mocked; not native exactness or speed')
out['passed'] = len(rows) == 2 and all(r['passed'] for r in rows)
if out['passed']:
    comparisons = [dict(name=a['name'], decoded_tensors_equal=a['decoded_tensors']==b['decoded_tensors'],
                        last_frame_equal=a['last_frame_sha256']==b['last_frame_sha256'])
                   for a,b in zip(rows[0]['chunks'], rows[1]['chunks'])]
    out['off_on_exact_cpu_outputs'] = comparisons
    out['passed'] = len(comparisons)==11 and all(r['decoded_tensors_equal'] and r['last_frame_equal'] for r in comparisons)
(OUT/'candidate-runtime-summary.json').write_text(json.dumps(out, indent=2, ensure_ascii=False)+'\n')
raise SystemExit(not out['passed'])
