#!/usr/bin/env python3
"""Registered c59 seed-2 off/on control; sequential fresh servers, no retries.

Uses the existing campaign runner for server lifecycle and health guards. Run in
its own systemd user unit, from this directory, after all CPU work is finished.
Results stay under /mnt until both servers are down; never commits or pushes.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = Path('/mnt/fast-ai/bench-results/context-longrun-20261016')
OUT = BASE / 'campaign59-control'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)|soft lockup', re.I)


def main():
    OUT.mkdir(exist_ok=False)
    for run in ('c59a', 'c59b'):
        if (BASE / 'runs' / run).exists() or list((BASE / 'proxy-state').glob(f'{run}-*')):
            raise RuntimeError(f'refusing existing run {run}')
    queue = OUT / 'queue.txt'
    queue.write_text('K32V hostile2mk 2 14400\n')
    started = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    env = dict(os.environ, QUEUE=str(queue), KEEPER_VERSION='1.3.0', LEAN_CLIENT='1',
               RESTORE='0', IDLE_MAX='0', PER_ARM='1', PLAIN_AGENT_KIND='plain-stable-fixture',
               SANDBOX_ROOT_MTIME='1792687500', MTP='5', SEQS='2', PIECE='832',
               TAIL='1', ONE_LAUNCH='1', TRAJ='0', EDIT='0')
    # Freeze the existing server identity and all model/proxy settings; only the
    # explicit memo switch changes between stages. No other task should run here.
    for run, memo in (('c59a', '0'), ('c59b', '1')):
        stage_env = dict(env, RUN=run, COUNT_MEMO=memo)
        (OUT / 'status.json').write_text(json.dumps({'status': 'running', 'stage': run,
            'count_memo': memo, 'started': started}, indent=2) + '\n')
        print(f'{run}: starting memo={memo}, sandbox root mtime=1792687500', flush=True)
        with (OUT / f'{run}.log').open('x') as log:
            subprocess.run(['bash', str(HERE.parent / 'longrun-campaign37.sh')], cwd=HERE,
                           env=stage_env, stdout=log, stderr=subprocess.STDOUT, check=True)
        server_dir = BASE / 'server' / f'tp2-w262144-s2-xp-mtp5-p832-{run}-a1'
        if (server_dir / 'MEMORY-GUARD.json').exists() or (BASE / f'CUT-{run}.txt').exists():
            raise RuntimeError(f'{run}: guard stop or cut trial; no further launch')
        # The old runner can exit zero after refusing an arm. Require complete
        # saved evidence and confirmed clean shutdown before the next launch.
        kernel = subprocess.check_output(['sudo', '-A', 'journalctl', '-k', '--since', started,
                                          '--no-pager', '-o', 'short-iso'], env=env, text=True)
        (OUT / f'{run}-kernel.log').write_text(kernel)
        if any(FAULT.search(line) for line in kernel.splitlines()):
            raise RuntimeError(f'{run}: GPU fault; no further launch')
        subprocess.run([sys.executable, str(HERE / 'campaign59_result.py'), '--run', run,
                        '--out', str(OUT / f'{run}.json')], check=True)
        print(f'{run}: complete, server stopped, audit recorded', flush=True)
    subprocess.run([sys.executable, str(HERE / 'campaign59_result.py'), '--compare',
                    '--out', str(OUT / 'comparison.json')], check=True)
    subprocess.run([sys.executable, str(HERE / 'campaign_time_budget.py'),
                    'c55', 'K32V', '2', 'c59a', 'K32V', '2', 'c59b', 'K32V', '2',
                    '--json', str(OUT / 'time-budget.json')], check=True)
    (OUT / 'status.json').write_text(json.dumps({'status': 'complete', 'started': started,
        'finished': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'decision': 'audit required; default and public figures unchanged'}, indent=2) + '\n')
    print('Campaign 59 complete; servers down; compare receipts before any promotion.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if OUT.exists():
            # Never destroy a prior run's status on an accidental second invocation.
            error = OUT / f'failure-{os.getpid()}.json'
            error.write_text(json.dumps({'error': str(exc)}, indent=2) + '\n')
        raise
