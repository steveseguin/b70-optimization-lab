#!/usr/bin/env python3
"""Coordinator-only serial packet49 chain; --plan is CPU-only and never launches."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
EARLY = ('K0', 'K1a', 'K1b', 'K2', 'W0p')
LATE = ('KD', 'W2m', 'WS', 'WSs', 'WS128x', 'WS128')
DEVICE_CORES = {0, 1, 2, 3, 16, 17, 18, 19}
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|GPU.*coredump|GuC.*(?:hang|lockup)|timed.out.*(?:job|fence)|job.*timed.out', re.I)


def user_unit_gate(cgroup):
    paths = [line.split(':', 2)[-1] for line in cgroup.splitlines()]
    if not any('/user@' in path and path.endswith('.service') and path.rsplit('/', 1)[-1] != f'user@{os.getuid()}.service' for path in paths):
        raise ValueError('durable systemd user service required for coordinator queue')


def commands(out):
    """Keep SPEED6 topology, native controller, and its retained/speed pairing."""
    base = ['ionice', '-c', '3', 'env', '-i', 'PATH=/usr/bin:/bin',
            'OMP_NUM_THREADS=2', 'LD_LIBRARY_PATH=' + os.environ.get('LD_LIBRARY_PATH', ''),
            'python3', '-B', str(P / 'window.py'), '--authorized-device-window',
            '--card', '0', '--context', '4096', '--draft-rank', '1', '--target-split', '23']
    result = {}
    for name in EARLY + LATE:
        cmd = (['nice', '-n', '19'] if name.startswith('K') else []) + base + ['--window', name, '--output', str(out / name)]
        prereqs = []
        if name != 'K0':
            prereqs.append('K0')
        if name == 'K1b':
            prereqs.append('K1a')
        if name in ('K2',) + LATE:
            prereqs += ['K1a', 'K1b']
        if name in LATE:
            prereqs.append('K2')
        if name in LATE[1:]:
            prereqs.append('W0p')
        if name in ('W2m', 'WS', 'WS128x', 'WS128'):
            prereqs.append('KD')
        for prerequisite in prereqs:
            cmd += ['--' + prerequisite.lower(), str(out / prerequisite / 'window.json')]
        if name in ('K1a', 'K1b', 'K2'):
            cmd += ['--dispatch', str(P / 'dispatch-p45.json')]
        if name in LATE:
            cmd += ['--dispatch', str(out / 'K2/run0/dispatch-measured.json')]
        if name == 'K2':
            cmd += ['--seconds', '14400']
        if name in ('KD', 'W2m'):
            cmd += ['--input', str(P / 'build/input')]
        if name == 'W2m':
            cmd += ['--oracle', str(P / 'oracle/results/incident-retrospective'), '--controller', 'native', '--retain-steps', '1-8']
        if name in ('WS', 'WSs', 'WS128x', 'WS128'):
            cmd += ['--suite-manifest', str(P / 'oracle/results/suite-manifest.json'), '--controller', 'native', '--repeat', '1',
                    '--retain-steps', 'none' if name == 'WS128' else '1-8,97-104' if name == 'WS128x' else '1-8']
        if name == 'WS128':
            cmd += ['--exactness-window', str(out / 'WS128x/window.json')]
        result[name] = cmd
    return result


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def journal(cursor=None):
    args = ['journalctl', '-k', '--no-pager', '--show-cursor']
    args += ['--after-cursor', cursor] if cursor else ['-n', '0']
    result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=10)
    lines = result.stdout.splitlines()
    cursors = [line.removeprefix('-- cursor: ') for line in lines if line.startswith('-- cursor: ')]
    if not cursors and not cursor:
        raise RuntimeError('kernel journal boundary unavailable')
    faults = [line for line in lines if FAULT.search(line)]
    if faults:
        raise RuntimeError('new GPU fault signature: ' + faults[0])
    return cursors[-1] if cursors else cursor


def oracle_ready():
    result = subprocess.run(['nice', '-n', '19', 'taskset', '-c', '4-15,20-31',
                           'python3', '-B', str(P / 'shared_oracle.py'), '--require-complete'],
                          capture_output=True, text=True)
    if result.returncode == 0:
        return True
    try:
        status = json.loads(result.stdout)
    except ValueError as error:
        raise RuntimeError('CPU oracle status validation failed; inspect status command') from error
    if status.get('status') not in ('running', 'not-started') or status.get('ready') is not False:
        raise RuntimeError('CPU oracle failed or has invalid status; no device launch')
    return False


def validate_success(name, out, rc):
    if rc:
        raise RuntimeError(f'{name} exited {rc}; no retry')
    row = json.loads((out / name / 'window.json').read_text())
    expected = {'window': name, 'passed': True, 'device_executed': True,
                'qualifying': True, 'card': 0, 'context': 4096, 'draft_rank': 1, 'target_split': 23}
    if any(type(row.get(key)) is not type(value) or row.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f'{name} lacks successful current-scope device receipt')


def admitted_output(path):
    out = path.resolve()
    allowed = (P / 'build').resolve()
    if allowed != Path('/home/steve/own-xpu-runtime-results/packet57-attribution/build'):
        raise ValueError('packet56 build must resolve to its admitted external build directory')
    from storage import REGISTERED_CHAIN
    if out != allowed / REGISTERED_CHAIN:
        raise ValueError('output must be the registered packet56 chain '+REGISTERED_CHAIN)
    return out


def prefix_prerequisites(paths):
    if paths is None or len(paths) != 2 or paths[0].resolve() == paths[1].resolve():
        raise ValueError('two distinct fresh packet56 head K windows required')
    from p56_head_window import verify_window
    from storage import digest
    rows = [verify_window(path) for path in paths]
    owners = {(row['pid'], row['process_start_ticks']) for row in rows}
    if len(owners) != 2:
        raise ValueError('head windows must use two fresh process owners')
    identity = rows[0].get('exact_output_identity')
    if not identity or rows[1].get('exact_output_identity') != identity:
        raise ValueError('fresh head owners differ in exact output identity')
    # The K window owns fresh processes, byte checks, selected-N coverage and
    # event validation. Prefix size never depends on the measured speed.
    return dict(passed=True, selection_uses_timing=False,
                windows=[dict(path=str(path.resolve()),sha256=digest(path)) for path in paths])


def run(args):
    if not args.authorized_device_window:
        raise ValueError('--authorized-device-window required to execute')
    if os.getpriority(os.PRIO_PROCESS, 0) != 0 or set(os.sched_getaffinity(0)) != DEVICE_CORES:
        raise ValueError('run inside admitted nice-0 coordinator unit on cores 0-3,16-19')
    user_unit_gate(Path('/proc/self/cgroup').read_text())
    from p49_seal import verify
    verify()  # Selection/device decision must be sealed before any queue write or launch.
    prefix_windows = prefix_prerequisites(args.prefix_windows)
    out = admitted_output(args.output_root)
    from storage import precheck
    storage = precheck()
    if not storage['passed']:
        raise RuntimeError('registered-chain storage precheck refused: '+str(storage))
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stop = out / 'STOP'
        if stop.exists():
            raise RuntimeError('STOP exists; coordinator review required, no automatic restart')
        windows = EARLY if args.phase == 'early' else LATE if args.phase == 'model' else EARLY + LATE
        if any((out / name).exists() for name in windows):
            raise RuntimeError('selected window already has output; no retry or overwrite')
        cursor = journal()
        state_path = out / 'queue-state.json'
        atomic_json(out / 'prefix-head-prerequisites.json', prefix_windows)
        state = json.loads(state_path.read_text()) if state_path.exists() else {'last_stop': 0, 'gap': 0, 'completed': []}
        try:
            for name in windows:
                if name in LATE:
                    while not oracle_ready():
                        if stop.exists():
                            raise RuntimeError('STOP while awaiting complete CPU oracle')
                        cursor = journal(cursor)
                        atomic_json(out / 'waiting.json', {'reason': 'CPU oracle incomplete or invalid', 'window': name, 'time': time.time()})
                        if not args.wait_oracle:
                            raise RuntimeError('CPU oracle incomplete; use --wait-oracle or start model phase after completion')
                        time.sleep(5)
                while time.time() < state['last_stop'] + state['gap']:
                    if stop.exists():
                        raise RuntimeError('STOP during inter-window gap')
                    cursor = journal(cursor)
                    time.sleep(min(5, state['last_stop'] + state['gap'] - time.time()))
                if stop.exists():
                    raise RuntimeError('STOP before launch')
                cursor = journal(cursor)
                from storage import early_retention_gate
                early_retention_gate(out)
                cmd = commands(out)[name]
                atomic_json(out / 'running.json', {'window': name, 'argv': cmd, 'started': time.time()})
                with (out / (name + '.log')).open('x') as log:
                    # The window owns cooperative stop, deadlines, health monitoring and teardown.
                    # No launcher timeout, process-group kill, companion, retry or affinity changer.
                    child = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                    rc = child.wait()
                state.update(last_stop=time.time(), gap=305 if name.startswith('W') else 90)
                atomic_json(state_path, state)
                cursor = journal(cursor)
                validate_success(name, out, rc)
                early_retention_gate(out)
                state['completed'].append(name)
                atomic_json(state_path, state)
            atomic_json(out / ('queue-' + args.phase + '-complete.json'), {'passed': True, 'windows': list(windows), 'time': time.time()})
        except BaseException as error:
            stop.write_text(str(error) + '\n')
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('early', 'model', 'all'), default='all')
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--authorized-device-window', action='store_true')
    parser.add_argument('--wait-oracle', action='store_true')
    parser.add_argument('--prefix-windows', type=Path, nargs=2,
                        help='Two fresh packet56 head K-window receipts; required to execute')
    args = parser.parse_args()
    if args.plan:
        chosen = EARLY if args.phase == 'early' else LATE if args.phase == 'model' else EARLY + LATE
        for name, cmd in commands(args.output_root).items():
            if name in chosen:
                print(shlex.join(cmd))
        return
    run(args)


if __name__ == '__main__':
    main()
