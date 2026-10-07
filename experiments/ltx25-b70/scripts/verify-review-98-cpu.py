#!/usr/bin/env python3
"""Offline review verification only: guarded CPU tests and inactive startup gates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'data/size-98-offline'
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98')


def main():
    assert sys.executable == '/home/steve/.venvs/ltx25-baseline/bin/python'
    ap = argparse.ArgumentParser()
    ap.add_argument('--tests', action='store_true')
    ap.add_argument('--gates', action='store_true')
    a = ap.parse_args()
    digest = hashlib.sha256((PACKET/'manifest.json').read_bytes()).hexdigest()
    failed = False
    if a.tests:
        results = []
        tests = sorted(p for p in HERE.glob('test-packet*.py')
                       if re.match(r'test-packet(?:90c|9[1-8])', p.name))
        with tempfile.TemporaryDirectory(prefix='packet98-review-guard-') as tmp:
            Path(tmp, 'sitecustomize.py').write_bytes((HERE/'cpu-guard-98.py').read_bytes())
            env = dict(os.environ, PYTHONPATH=tmp, PYTHONDONTWRITEBYTECODE='1',
                       ONEAPI_DEVICE_SELECTOR='opencl:cpu', ZE_AFFINITY_MASK='99',
                       OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
            for test in tests:
                p = subprocess.run([sys.executable, '-B', str(test)], env=env,
                                   capture_output=True, text=True, timeout=180)
                log = p.stdout + p.stderr
                log_path = OUT / ('review-' + test.stem + '.log')
                log_path.write_text(log)
                count = re.search(r'Ran (\d+) tests? in', log)
                groups = int(count[1]) if count else sum(line.startswith('ok  ') for line in log.splitlines())
                results.append({'test': test.name, 'returncode': p.returncode,
                                'check_groups': groups, 'log': log_path.name})
                print(test.name, p.returncode, groups, flush=True)
                failed |= p.returncode != 0
        (OUT/'review-tests.json').write_text(json.dumps({'manifest_sha256': digest,
                                                       'results': results}, indent=2)+'\n')
    if a.gates:
        health = max((HERE.parent/'data/health').glob('*.json'),
                     key=lambda p: json.loads(p.read_text()).get('end_utc', ''))
        results = []
        for workers, batch, size in ((2,1,'256x256'), (1,1,'640x384'), (2,2,'640x384'),
                                     (1,1,'512x320'), (2,2,'512x320')):
            run = f'encoder-server-size-98-two-way-w{workers}-b{batch}-p1-dxpu2-s{size}'
            env = dict(os.environ, LTX_OUTPUT_SIZE=size, LTX_SAMPLER_PLACEMENT='two-way',
                       LTX_SAMPLER_WORKERS=str(workers), LTX_SAMPLER_BATCH=str(batch),
                       LTX_SAMPLER_SHARED_POOL='1', LTX_DECODE_REPLICA_DEVICE='xpu:2',
                       LTX_DECODE_REPLICAS='1', LTX_BUSY_WINDOWS='0',
                       NEOReadDebugKeys='1', EnableDeferBacking='0', PYTHONDONTWRITEBYTECODE='1')
            for receipt in (None, health):
                command = [sys.executable, '-B', str(PACKET/'launch/serve-encoder.py'),
                           '--packet', str(PACKET), '--manifest-sha256', digest,
                           '--run-name', run, '--check-only']
                if receipt: command += ['--health-receipt', str(receipt)]
                p = subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)
                row = {'run': run, 'health_receipt': str(receipt) if receipt else None,
                       'command': command, 'returncode': p.returncode}
                if p.returncode: row.update(stdout=p.stdout, stderr=p.stderr)
                else: row['result'] = json.loads(p.stdout)
                results.append(row)
                print(run, 'health' if receipt else 'no-health', p.returncode, flush=True)
                failed |= p.returncode != 0
        (OUT/'gates.json').write_text(json.dumps({'manifest_sha256': digest,
                                                'results': results}, indent=2)+'\n')
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
