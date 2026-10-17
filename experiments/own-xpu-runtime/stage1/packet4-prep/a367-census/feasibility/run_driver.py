#!/usr/bin/env python3
"""Coordinator-only device runner; --plan is CPU-only. No kill/timeout/retry."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from common import write_json

HERE = Path(__file__).resolve().parent
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'
UNITRACE = '/home/steve/src/pti-gpu/build-unitrace-itt/unitrace'  # ITT-enabled build (pinned build has BUILD_WITH_ITT=0)
SOURCE = Path('/home/steve/src/vllm-flashnext-a367-clean-20261016')
FLAGS = ['--chrome-kernel-logging', '--chrome-itt-logging', '--verbose', '--pid',
         '--chrome-event-buffer-size', '4096']
STEPS = [('graph-control', 'graph', False, False, 90, '10-30 s'),
         ('graph-traced', 'graph', True, False, 120, '20-60 s'),
         ('graph-paused', 'graph', True, True, 120, '20-60 s'),
         ('ccl-control', 'ccl', False, False, 150, '20-60 s'),
         ('ccl-paused', 'ccl', True, True, 180, '30-120 s'),
         ('ccl-create-after-resume', 'ccl', True, True, 180, '30-120 s; expected SIGSEGV at first collective')]
SOURCE_FILES = ['vllm/platforms/xpu.py', 'vllm/v1/worker/xpu_worker.py',
                'vllm/v1/executor/multiproc_executor.py',
                'vllm/distributed/parallel_state.py', 'vllm/utils/network_utils.py']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected_environment(output):
    # The sealed packet's CPU-only builder is the authority, not our shell.
    sys.path.insert(0, str(HERE.parent))
    import a367_census
    _, server = a367_census.command_and_environment(output)
    selected = {k: v for k, v in server.items() if
                k.startswith(('CCL_', 'FI_')) or k in ('LD_PRELOAD', 'ZE_AFFINITY_MASK', 'LD_LIBRARY_PATH')}
    if selected.get('ZE_AFFINITY_MASK') != '0,1,2,3':
        raise ValueError('expected the four-card A367 environment')
    # No inherited selectors, tracing switches, CCL overrides or secrets.
    return dict(HOME='/home/steve', USER='steve', LOGNAME='steve', LANG='C.UTF-8',
                PATH='/usr/local/bin:/usr/bin:/bin', OMP_NUM_THREADS='1',
                PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1', **selected)


def select_steps(only):
    if only is None:
        return STEPS
    names = only.split(',')
    known = {row[0] for row in STEPS}
    if not names or len(set(names)) != len(names) or any(name not in known for name in names):
        raise ValueError('--only requires unique comma-separated step names: ' + ','.join(row[0] for row in STEPS))
    # Always retain registered order, including the control before reproduction.
    return [row for row in STEPS if row[0] in names]


def plan(root, only=None):
    rows = []
    for name, test, traced, paused, budget, expected in select_steps(only):
        directory = root / name
        session = 'A367Feas' + hashlib.sha256(str(directory).encode()).hexdigest()[:20]
        command = [PYTHON, '-B', str(HERE / ('graph_visibility.py' if test == 'graph' else 'ccl_init.py')),
                   '--output', str(directory)]
        if paused:
            command += ['--handshake']
        if name == 'ccl-create-after-resume':
            command += ['--create-after-resume']
        if traced:
            prefix = [UNITRACE, *FLAGS, '--result-dir', str(directory / 'unitrace')]
            if paused:
                prefix += ['--start-paused', '--session', session]
            command = prefix + command
        rows.append(dict(name=name, test=test, command=command, paused=paused, traced=traced,
                         session=session, directory=str(directory), budget_s=budget,
                         expected_time=expected, ranks=1 if test == 'graph' else 4,
                         expected_memory=('1-2 GiB host; <256 MiB device on card 0' if test == 'graph'
                                          else '4-8 GiB host total; <512 MiB device per card'),
                         tracer_extra_host='0.25-1 GiB total, unmeasured' if traced else 'none'))
    return rows


def validate_summary(summary):
    assert summary['schema'] == 'a367-tracefeas-summary-v1'
    assert summary['status'] in ('running', 'passed', 'failed')
    assert len({r['name'] for r in summary['steps']}) == len(summary['steps'])
    for row in summary['steps']:
        assert row['status'] in ('pending', 'running', 'passed', 'failed')
        assert row['rc'] is None or type(row['rc']) is int
        assert row['duration_s'] >= 0 and type(row['overrun']) is bool
        if row['status'] == 'passed':
            assert row['rc'] == 0 and not row['overrun']
        if row['status'] == 'pending':
            assert row['rc'] is None


def new_summary(root, rows, env):
    return dict(schema='a367-tracefeas-summary-v1', status='running', output=str(root),
                created_utc=datetime.now(timezone.utc).isoformat(), environment=env,
                steps=[dict(**r, status='pending', rc=None, duration_s=0., overrun=False,
                            controls=[]) for r in rows])


def save(root, summary):
    validate_summary(summary)
    write_json(root / 'summary.json', summary)


def completed_ccl_exit_crash(row, directory):
    if row['name'] != 'ccl-paused':
        return False
    try:
        exits = json.loads((directory / 'rank-exits.json').read_text())
        codes = exits['exitcodes']
        return (exits['all_ranks_exited'] is True
                and set(codes) == {str(rank) for rank in range(row['ranks'])}
                and -signal.SIGSEGV in codes.values()
                and all(type(code) is int and code in (0, -signal.SIGSEGV) for code in codes.values())
                and all((directory / f'done-{rank}').exists() for rank in range(row['ranks'])))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def run_step(row, summary, root, env):
    directory = Path(row['directory'])
    directory.mkdir()
    (directory / 'unitrace').mkdir()
    row.update(status='running', started_unix_s=time.time())
    start = time.monotonic()
    save(root, summary)
    print(f'START {row["name"]}, budget {row["budget_s"]}s', flush=True)
    # Separate session prevents terminal Ctrl-C from hard-stopping device ranks.
    with (directory / 'run.log').open('w') as log:
        try:
            child = subprocess.Popen(row['command'], env=env, stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as error:
            row.update(status='failed', error=str(error), rc=127,
                       duration_s=time.monotonic() - start)
            save(root, summary)
            return False
        row['pid'] = child.pid
        resumed, paused = False, False

        def heartbeat():
            row['duration_s'] = time.monotonic() - start
            if row['duration_s'] > row['budget_s'] and not row['overrun']:
                row['overrun'] = True
                print(f'OVERRUN {row["name"]}: waiting for cooperative exit; no kill', flush=True)
            save(root, summary)

        def control(action):
            # Separate control command; same acknowledgement check as census.
            command = [UNITRACE, '--' + action, row['session']]
            record = dict(action=action, command=command, rc=None, duration_s=0., overrun=False)
            row['controls'].append(record)
            began = time.monotonic()
            path = directory / f'{action}.log'
            # No LD_PRELOAD or inherited unitrace state in the control process.
            control_env = {k: env[k] for k in ('HOME', 'USER', 'LOGNAME', 'LANG', 'PATH')}
            with path.open('w') as output:
                try:
                    helper = subprocess.Popen(command, env=control_env, stdout=output,
                                              stderr=subprocess.STDOUT, start_new_session=True)
                except OSError as error:
                    record.update(rc=127, error=str(error), acknowledged=False,
                                  duration_s=time.monotonic() - began)
                    return False
                while helper.poll() is None:
                    record['duration_s'] = time.monotonic() - began
                    if record['duration_s'] > 10 and not record['overrun']:
                        record['overrun'] = True
                        print(f'OVERRUN {action}: waiting; no kill', flush=True)
                    heartbeat()
                    time.sleep(.5)
            record.update(rc=helper.returncode, duration_s=time.monotonic() - began)
            ack = f'Session {row["session"]} is ' + {'resume': 'resumed', 'pause': 'paused'}[action]
            record['acknowledged'] = ack in path.read_text()
            return record['rc'] == 0 and record['acknowledged'] and not record['overrun']

        while child.poll() is None:
            heartbeat()
            ready = all((directory / f'ready-{rank}').exists() for rank in range(row['ranks']))
            done = all((directory / f'done-{rank}').exists() for rank in range(row['ranks']))
            if row['paused'] and ready and not resumed and not (directory / 'abort').exists():
                resumed = True  # One attempt only, even if control fails.
                if control('resume'):
                    (directory / 'go').touch()
                else:
                    row['control_failed'] = True
                    (directory / 'abort').touch()
            if row['paused'] and done and not paused:
                paused = True
                if not control('pause'):
                    row['control_failed'] = True
                (directory / 'release').touch()
            time.sleep(.5)
        # Even a failed/early-exit session gets one final pause, no retry.
        if row['paused'] and not paused:
            if not control('pause'):
                row['control_failed'] = True
        row.update(rc=child.returncode, duration_s=time.monotonic() - start)
        row['overrun'] |= row['duration_s'] > row['budget_s']
        clean = child.returncode == 0 and not row['overrun'] and not row.get('control_failed', False)
        row['status'] = 'passed' if clean else 'failed'
        # The matched paused control may finish all work and crash at process
        # exit. Preserve failed/rc, but permit the next registered reproduction
        # only after all ranks passed the pause/release handshake and exited.
        row['expected_tracer_exit_crash'] = (
            completed_ccl_exit_crash(row, directory) and child.returncode != 0
            and paused and not row['overrun'] and not row.get('control_failed', False))
        save(root, summary)
        print(f'END {row["name"]}: rc={row["rc"]}, {row["duration_s"]:.3f}s, {row["status"]}', flush=True)
        return clean or row['expected_tracer_exit_crash']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--only', help='Comma-separated single steps, run in registered order')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = (args.output or Path('/mnt/raid-models/bench-results') / f'a367-tracefeas-{stamp}').absolute()
    if root.parent != Path('/mnt/raid-models/bench-results') or not root.name.startswith('a367-tracefeas-'):
        parser.error('output must be /mnt/raid-models/bench-results/a367-tracefeas-<stamp>')
    try:
        rows = plan(root, args.only)
    except ValueError as error:
        parser.error(str(error))
    env = selected_environment(root)
    summary = new_summary(root, rows, env)
    summary['identity'] = dict(unitrace_sha256=sha(UNITRACE),
        census_seal_sha256=sha(HERE.parent / 'seal.json'),
        sources={p: sha(SOURCE / p) for p in SOURCE_FILES},
        scripts={p.name: sha(p) for p in HERE.iterdir() if p.suffix in ('.py', '.sh')})
    if args.plan:
        print(json.dumps(summary, indent=2))
        return 0
    root.mkdir(exist_ok=False)
    # Stay present on terminal interrupts; never forward a termination to GPUs.
    def interrupted(signum, frame):
        print(f'Interrupt {signum}: waiting for current step; no further steps will start', flush=True)
        summary['interrupted'] = True
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    print(f'Output: {root}', flush=True)
    save(root, summary)
    for row in summary['steps']:
        if summary.get('interrupted') or not run_step(row, summary, root, env):
            summary['status'] = 'failed'
            break
    else:
        summary['status'] = ('passed' if not summary.get('interrupted')
                             and all(row['status'] == 'passed' for row in summary['steps']) else 'failed')
    save(root, summary)
    from analyze_feasibility import analyze
    result = analyze(root)
    write_json(root / 'feasibility.json', result)
    print(json.dumps(result['verdict'], indent=2), flush=True)
    return 0 if summary['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
