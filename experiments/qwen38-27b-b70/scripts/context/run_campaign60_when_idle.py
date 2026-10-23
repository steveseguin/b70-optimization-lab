#!/usr/bin/env python3
"""Wait for campaign 59, check the small notes diagnostic, run one fresh server.

No source or live campaign files are modified. The generated driver differs
from the pinned existing runner only in its CPU/client check command and labels.
No retries, default changes, commits, pushes, or publication.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[3]
BASE = Path('/mnt/fast-ai/bench-results/context-longrun-20261016')
OUT = BASE / 'campaign60-note-evidence'
FIXTURES = LAB / 'experiments/qwen38-27b-b70/data/2026-10-23-note-evidence-fixtures'
RUNNER = HERE.parent / 'longrun-campaign37.sh'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)|soft lockup', re.I)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stopped(run, arm):
    folder = BASE / 'server' / f'tp2-w262144-s2-xp-mtp5-p832-{run}-a{arm}'
    state = json.loads((folder / 'state.json').read_text())
    if state.get('status') != 'stopped' or state.get('stop_confirmed') is not True or state.get('error'):
        raise RuntimeError(f'{run}: no clean confirmed server stop')
    if (folder / 'MEMORY-GUARD.json').exists():
        raise RuntimeError(f'{run}: memory guard fired; no new launch')


def main():
    OUT.mkdir(exist_ok=False)
    pins = {str(p): digest(p) for p in (Path(__file__).resolve(), RUNNER, HERE / 'note_evidence_probe.py',
        LAB / 'tools/ctxkeeper/ctxkeeper.py', LAB / 'tools/ctxkeeper/notesdelta.py', FIXTURES / 'manifest.json')}
    (OUT / 'pins.json').write_text(json.dumps(pins, indent=2) + '\n')
    (OUT / 'status.json').write_text(json.dumps({'status': 'waiting-for-campaign59',
        'queued': dt.datetime.now().astimezone().isoformat()}) + '\n')
    status = BASE / 'campaign59-control/status.json'
    deadline = time.monotonic() + 3 * 3600
    print('Waiting for campaign 59 to finish and release both servers.', flush=True)
    while True:
        if list(status.parent.glob('failure-*.json')):
            raise RuntimeError('campaign 59 failed; inspect it before launching another server')
        current = json.loads(status.read_text())
        if current.get('status') == 'complete':
            break
        if time.monotonic() > deadline:
            raise RuntimeError('three-hour wait expired; no launch')
        time.sleep(20)
    for run in ('c59a', 'c59b'):
        stopped(run, 1)
    for unit in ('ctx-fp8-tp2-server', 'ctx-keeper-proxy', 'ctx-campaign59'):
        # The c59 runner may be in its last few milliseconds after writing status.
        for _ in range(5):
            active = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', unit]).returncode == 0
            if not active:
                break
            time.sleep(2)
        if active:
            raise RuntimeError(f'{unit} is still active; no launch')
    for name, expected in pins.items():
        if digest(Path(name)) != expected:
            raise RuntimeError(f'pinned input changed while waiting: {name}')
    if (BASE / 'runs/c60').exists() or list((BASE / 'server').glob('*-c60-*')):
        raise RuntimeError('c60 outputs already exist; no reuse')
    # CPU preparation runs only after the experiment's model and proxy are down.
    with (OUT / 'cpu-check.log').open('x') as log:
        subprocess.run([sys.executable, str(HERE / 'note_evidence_probe.py'), '--check', str(FIXTURES)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run([sys.executable, str(HERE / 'note_evidence_probe.py'), '--fixtures', str(FIXTURES),
                        '--cpu-check', '--rounds', '1', '--json', str(OUT / 'cpu-check.json')],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    schema = OUT / 'review-schema.json'
    schema.write_text(json.dumps({'type': 'object', 'properties': {
        'approved': {'type': 'boolean'}, 'issues': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['approved', 'issues'], 'additionalProperties': False}) + '\n')
    review = OUT / 'review.json'
    prompt = '''Read-only independent review of the registered campaign 60 notes diagnostic.
Read AGENTS.md, experiments/qwen38-27b-b70/notes/2026-10-23-campaign60-note-evidence.md,
experiments/qwen38-27b-b70/scripts/context/note_evidence_probe.py,
experiments/qwen38-27b-b70/scripts/context/run_campaign60_when_idle.py,
and the small fixtures in experiments/qwen38-27b-b70/data/2026-10-23-note-evidence-fixtures/.
The model servers are DOWN. Do not launch or stop any server, GPU or Docker job. Do not edit, commit,
push, delegate or access the network. Inspect the local code and evidence only. Check request reconstruction,
tool-call pairing, fixture/counterfactual boundaries, source-claim honesty, and sequential lifecycle/failure
gates. CPU smoke output is in /mnt/fast-ai/bench-results/context-longrun-20261016/campaign60-note-evidence/.
Return approved=true and issues=[] only if this bounded diagnostic is safe and correctly scoped to run.
Otherwise approved=false and concrete blocking issues. Do not treat a completed diagnostic as quality success.'''
    with (OUT / 'review.log').open('x') as log:
        subprocess.run(['/home/steve/.local/bin/codex', 'exec', '--sandbox', 'read-only',
            '--output-schema', str(schema), '--output-last-message', str(review), prompt], cwd=LAB,
            stdout=log, stderr=subprocess.STDOUT, timeout=600, check=True)
    assessment = json.loads(review.read_text())
    if assessment.get('approved') is not True or assessment.get('issues') != []:
        raise RuntimeError('independent review requires fixes; no GPU launch (see review.json)')
    for name, expected in pins.items():
        if digest(Path(name)) != expected:
            raise RuntimeError(f'pinned input changed during checks: {name}')
    source = RUNNER.read_text()
    old = 'python3 ./concurrency_check.py'
    if source.count(old) != 1:
        raise RuntimeError('runner check command no longer unique')
    source = source.replace(old, f'python3 ./note_evidence_probe.py --fixtures {FIXTURES}')
    source = source.replace('[concurrency check]', '[note evidence check]')
    source = source.replace('0 all same as solo, 1 some different, 2 garbage', '0 diagnostic complete; manual quality review required')
    driver = OUT / 'driver.sh'
    driver.write_text(source)
    subprocess.run(['bash', '-n', str(driver)], check=True)
    queue = OUT / 'queue.txt'
    queue.write_text('K32V check 0 1800\n')
    env = dict(os.environ, RUN='c60', QUEUE=str(queue), KEEPER_VERSION='1.3.0',
        RESTORE='0', IDLE_MAX='0', PER_ARM='1', LEAN_CLIENT='1', COUNT_MEMO='0',
        MTP='5', SEQS='2', PIECE='832', TAIL='1', ONE_LAUNCH='1', TRAJ='0', EDIT='0',
        PLAIN_AGENT_KIND='plain', CHECK_STRICT='1', CHECK_FAIL_STOP='0')
    env.pop('CHECK_REF', None)
    print('CPU checks passed; starting campaign 60 notes evidence diagnostic.', flush=True)
    started = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    (OUT / 'status.json').write_text(json.dumps({'status': 'running', 'started': started}) + '\n')
    with (OUT / 'campaign.log').open('x') as log:
        subprocess.run(['bash', str(driver)], cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    stopped('c60', 1)
    kernel = subprocess.check_output(['sudo', '-A', 'journalctl', '-k', '--since', started,
                                      '--no-pager', '-o', 'short-iso'], env=env, text=True)
    (OUT / 'kernel.log').write_text(kernel)
    if any(FAULT.search(line) for line in kernel.splitlines()):
        raise RuntimeError('GPU fault during campaign 60; inspect saved kernel log')
    result = json.loads((BASE / 'c60-K32V-check-s0.json').read_text())
    if result.get('complete') is not True or result.get('cpu_check') is not False:
        raise RuntimeError('device diagnostic did not complete')
    (OUT / 'status.json').write_text(json.dumps({'status': 'complete',
        'finished': dt.datetime.now().astimezone().isoformat(), 'quality': 'manual source-grounded review required'}) + '\n')
    print('Campaign 60 complete, server stopped. Default unchanged; review all claims against source.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if OUT.exists():
            (OUT / f'failure-{os.getpid()}.json').write_text(json.dumps({'error': str(exc)}) + '\n')
        raise
