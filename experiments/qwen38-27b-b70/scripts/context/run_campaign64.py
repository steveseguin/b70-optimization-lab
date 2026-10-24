#!/usr/bin/env python3
"""One registered current-pi baseline; no retries, adoption, or resident server."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from run_campaign60_when_idle import FAULT, stopped
from current_pi_probe import inactive

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[3]
BASE = Path('/mnt/fast-ai/bench-results/context-longrun-20261016')
OUT = BASE / 'campaign64-current-pi'
PROBE = HERE / 'current_pi_probe.py'
RUNNER = HERE.parent / 'longrun-campaign37.sh'
REVIEW = LAB / 'experiments/qwen38-27b-b70/data/2026-10-23-campaign64-preflight/review.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    for run in ('c59a', 'c59b', 'c60', 'c61', 'c62', 'c63'):
        stopped(run, 1)
    for unit in ('ctx-fp8-tp2-server', 'ctx-keeper-proxy', 'ctx-campaign59', 'ctx-campaign60-queued', 'ctx-campaign61', 'ctx-campaign62', 'ctx-campaign63'):
        if not inactive(unit):
            raise RuntimeError(f'{unit} still active; no launch')
    if (BASE / 'c64-K32V-check-s0.json').exists() or list((BASE / 'server').glob('*-c64-*')):
        raise RuntimeError('existing c64 outputs; no reuse')
    review = json.loads(REVIEW.read_text())
    if review.get('approved') is not True or review.get('issues') != []:
        raise RuntimeError('independent review did not approve the diagnostic')
    for path in (PROBE, Path(__file__).resolve()):
        if review.get('sha256', {}).get(str(path)) != digest(path):
            raise RuntimeError(f'review does not bind current source: {path}')
    pins = {str(p): digest(p) for p in (PROBE, Path(__file__).resolve(), RUNNER,
        HERE / 'run_campaign60_when_idle.py', HERE / 'test_current_pi_probe.py',
        LAB / 'tools/agentbench/run-agent-job.sh', LAB / 'tools/agentbench/check_history.py',
        LAB / 'tools/agentbench/bridge.py', LAB / 'tools/ctxkeeper/ctxkeeper.py',
        LAB / 'tools/ctxkeeper/notesdelta.py', REVIEW)}
    (OUT / 'pins.json').write_text(json.dumps(pins, indent=2) + '\n')
    with (OUT / 'cpu-check.log').open('x') as log:
        subprocess.run([sys.executable, '-m', 'unittest', '-v', 'test_current_pi_probe'],
            cwd=HERE, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run([sys.executable, str(PROBE), '--preflight',
            '--json', str(OUT / 'preflight.json')], stdout=log, stderr=subprocess.STDOUT, check=True)
    preflight = json.loads((OUT / 'preflight.json').read_text())
    if preflight.get('preflight_ok') is not True:
        raise RuntimeError('pi image/task preflight did not pass')
    source = RUNNER.read_text()
    old = 'python3 ./concurrency_check.py'
    if source.count(old) != 1 or source.count('--rounds 3') != 1:
        raise RuntimeError('original check command no longer unique')
    source = source.replace(old, f'python3 {PROBE} --pins {OUT / "preflight.json"}')
    source = source.replace('--rounds 3', '--rounds 1')
    source = source.replace('[concurrency check]', '[current pi baseline]')
    source = source.replace('0 all same as solo, 1 some different, 2 garbage', '0 diagnostic complete; quality requires manual audit')
    driver = OUT / 'driver.sh'
    driver.write_text(source)
    subprocess.run(['bash', '-n', str(driver)], check=True)
    queue = OUT / 'queue.txt'
    queue.write_text('K32V check 0 4200\n')
    env = dict(os.environ, RUN='c64', QUEUE=str(queue), KEEPER_VERSION='1.3.0',
        RESTORE='0', IDLE_MAX='0', PER_ARM='1', LEAN_CLIENT='1', COUNT_MEMO='1',
        MTP='5', SEQS='2', PIECE='832', TAIL='1', ONE_LAUNCH='1', TRAJ='0', EDIT='0',
        PLAIN_AGENT_KIND='plain', CHECK_STRICT='1', CHECK_FAIL_STOP='0')
    env.pop('CHECK_REF', None)
    started = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    (OUT / 'status.json').write_text(json.dumps({'status': 'running', 'started': started}) + '\n')
    with (OUT / 'campaign.log').open('x') as log:
        subprocess.run(['bash', str(driver)], cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    stopped('c64', 1)
    kernel = subprocess.check_output(['sudo', '-A', 'journalctl', '-k', '--since', started,
        '--no-pager', '-o', 'short-iso'], env=env, text=True)
    (OUT / 'kernel.log').write_text(kernel)
    if any(FAULT.search(line) for line in kernel.splitlines()):
        raise RuntimeError('GPU fault; inspect saved kernel log')
    subprocess.run([sys.executable, str(PROBE), '--finalize', '--pins', str(OUT / 'preflight.json'),
        '--json', str(BASE / 'c64-K32V-check-s0.json')], check=True)
    result = json.loads((BASE / 'c64-K32V-check-s0.json').read_text())
    if result.get('complete') is not True:
        raise RuntimeError('pi baseline did not complete; preserve the partial result')
    (OUT / 'status.json').write_text(json.dumps({'status': 'complete',
        'finished': dt.datetime.now().astimezone().isoformat(),
        'quality': 'manual source-grounded audit required; no promotion'}) + '\n')
    print('Campaign 64 complete; server stopped; manual audit required.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if OUT.exists():
            (OUT / f'failure-{os.getpid()}.json').write_text(json.dumps({'error': str(exc)}) + '\n')
        raise
