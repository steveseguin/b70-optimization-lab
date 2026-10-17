#!/usr/bin/env python3
"""Editable, crash-closed per-lane queue. Only `run` starts device units."""
import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
DRIVER = ROOT / 'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'
COORD = Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
ENV_FILE = Path('/tmp/claude-1000/-home-steve/fn-run/p49.env')
CPU = set(range(8, 16)) | set(range(24, 32))
AFFINITY = {'A': '0-3,16-19', 'B': '4-7,20-23'}
BOOT = '2cba7160'
BASE = 2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def atomic(path, value):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('x') as f:
        f.write(value)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    atomic(path, json.dumps(value, sort_keys=True) + '\n')


@contextmanager
def lock(path, nonblocking=False):
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield


def cpu_setup():
    os.setpriority(os.PRIO_PROCESS, 0, 19)
    os.sched_setaffinity(0, CPU)


def library_path(path=ENV_FILE):
    # Parse data, never source shell code or print its contents.
    values = []
    for line in path.read_text().splitlines():
        if re.match(r'^(?:export\s+)?P49_LDP=', line.strip()):
            words = shlex.split(line.strip(), comments=True)
            if words and words[0] == 'export':
                words.pop(0)
            require(len(words) == 1, 'P49_LDP must be one literal assignment')
            values.append(words[0].split('=', 1)[1])
    require(len(values) == 1 and values[0] and not any(c in values[0] for c in '$`\n\x00'),
            'P49_LDP must be one nonempty literal path')
    return values[0]


def closed_env(ldp):
    return dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2', LD_LIBRARY_PATH=ldp)


def resolve(value):
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def validate(job, lane):
    require(isinstance(job, dict), 'job must be an object')
    require(set(job) <= {'name', 'argv', 'script', 'env_extra', 'review', 'lane'}, 'unknown job field')
    require(job.get('lane') == lane, 'job lane differs from queue')
    require(isinstance(job.get('name'), str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', job['name']), 'invalid unit name')
    require(('argv' in job) != ('script' in job), 'choose argv or script')
    extra = job.get('env_extra', {})
    require(isinstance(extra, dict), 'env_extra must be an object')
    require(not extra or 'script' in job, 'env_extra is coordinator-script-only; screen environment is closed')
    for key, value in extra.items():
        require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) and key not in closed_env('')
                and isinstance(value, str) and '\x00' not in value and '\n' not in value, 'invalid env_extra')
    if 'argv' in job:
        argv = job['argv']
        require(isinstance(argv, list) and argv and all(isinstance(x, str) and x and '\x00' not in x for x in argv), 'argv must be a nonempty string list')
        # Accept direct commands, not shell/env wrappers that can defeat closure.
        require(Path(argv[0]).name not in {'env', 'bash', 'sh', 'dash', 'zsh', 'sudo', 'systemd-run', 'taskset'}, 'argv must be a direct executable; use script for coordinators')
        executable = str(resolve(argv[0])) if '/' in argv[0] else shutil.which(argv[0], path='/usr/bin:/bin')
        require(executable and os.access(executable, os.X_OK), 'argv executable unavailable')
        if Path(argv[0]).name.startswith('python'):
            require(len(argv) >= 3 and argv[1] == '-B' and resolve(argv[2]).is_file(), 'Python jobs require -B and an existing script')
        require('--plan' not in argv, 'queue the run command, not --plan')
        for i, arg in enumerate(argv):
            if arg == '--lane':
                require(i + 1 < len(argv) and argv[i + 1] == lane, 'argv lane differs')
    else:
        require(isinstance(job['script'], str) and resolve(job['script']).is_file(), 'coordinator script unavailable')
        argv = [job['script']]
    review = job.get('review')
    require(review is None or isinstance(review, str) and resolve(review).is_file(), 'review tool unavailable')
    placeholders = any('{REVIEW}' in arg for arg in argv) or any('{REVIEW}' in v for v in extra.values())
    require(bool(review) == placeholders, 'review requires a {REVIEW} placeholder (argv or coordinator env_extra)')
    return job


def read_queue(directory, lane):
    path = directory / f'queue-{lane}.txt'
    rows = []
    if path.exists():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            try:
                rows.append(validate(json.loads(line), lane))
            except (ValueError, TypeError) as exc:
                raise ValueError(f'queue line {number}: {exc}') from None
    require(len({r['name'] for r in rows}) == len(rows), 'duplicate job name')
    return rows


def fault_patterns():
    patterns = {}
    for node in ast.parse(DRIVER.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('FAULT', 'DELETED'):
                    patterns[target.id] = re.compile(ast.literal_eval(node.value.args[0]), re.I)
    require(set(patterns) == {'FAULT', 'DELETED'}, 'fault expressions unavailable')
    return patterns['FAULT'], patterns['DELETED']


class Backend:
    def __init__(self):
        self.fault, self.deleted = fault_patterns()

    def faults(self):
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        require(boot.startswith(BOOT), 'boot differs from reviewed baseline; stop for review')
        cp = subprocess.run(['/usr/bin/journalctl', '-k', '-b', '--no-pager', '-o', 'json'],
                            capture_output=True, text=True, timeout=30)
        require(cp.returncode == 0 and cp.stdout.strip() and not cp.stderr.strip(), 'complete kernel journal unavailable')
        rows = [json.loads(line) for line in cp.stdout.splitlines()]
        require(all(r.get('_BOOT_ID') == boot.replace('-', '') for r in rows), 'journal boot mismatch')
        return sum(bool(self.fault.search(line) and not self.deleted.search(line))
                   for r in rows for line in str(r.get('MESSAGE', '')).splitlines())

    def guards(self, lane):
        faults = self.faults()
        require(faults == BASE, 'kernel fault count changed from reviewed base 2')
        marker = COORD / f'active-lane-{lane}.json'
        if os.path.lexists(marker):
            try:
                pid = json.loads(marker.read_text()).get('pid')
                require(type(pid) is int and pid > 0, 'invalid marker owner pid')
                try:
                    os.kill(pid, 0)
                    state = 'live'
                except ProcessLookupError:
                    state = 'dead'
                except PermissionError:
                    state = 'unknown'
            except (ValueError, OSError):
                state = 'unknown'
            raise ValueError(f'active lane marker has {state} owner; retained for coordinator review: {marker}')
        require(not any((STAGE / 'screen/v3').glob('fault-*')), 'screen/v3 fault latch present; retained for review')
        return faults

    def review(self, job, directory):
        tool = resolve(job['review'])
        # Frozen review tools insist on their own evidence root. Only run creates this.
        output = tool.parent / 'evidence' / ('lanequeue-review-' + uuid.uuid4().hex + '.json')
        cp = subprocess.run(['/usr/bin/python3', '-B', str(tool), '--output', str(output)],
                            cwd=ROOT, env=closed_env(library_path()), stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=120)
        require(cp.returncode == 0 and output.is_file(), 'fresh fault review failed')
        return str(output)

    def execute(self, cmd, log):
        with log.open('x') as f:
            cp = subprocess.run(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=f, stderr=f)
            rc = cp.returncode  # Capture before clocks, status reads or logging.
        return rc

    def status(self, name, receipt):
        try:
            cp = subprocess.run(['/usr/bin/systemctl', '--user', 'show', 'screen-' + name + '.service',
                                 '--property=LoadState,Result,ExecMainStatus,ActiveState'],
                                capture_output=True, text=True, timeout=15)
            props = dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)
            if cp.returncode == 0 and props.get('LoadState') != 'not-found' and props.get('Result'):
                return dict(Result=props['Result'], ExecMainStatus=props.get('ExecMainStatus'), source='systemctl-show')
        except subprocess.TimeoutExpired:
            pass
        # ExecStopPost saved these before GC; never poll list-units or wait for reappearance.
        if receipt.is_file():
            return dict(json.loads(receipt.read_text()), source='ExecStopPost')
        return dict(Result='unavailable', ExecMainStatus=None, source='missing')


def command(job, review, receipt, ldp):
    require(re.fullmatch(r'[/A-Za-z0-9_.-]+', str(receipt)), 'receipt path must use plain path characters')
    env = closed_env(ldp)
    cmd = ['/usr/bin/systemd-run', '--user', '--wait', '--unit=screen-' + job['name']]
    for value in ('Restart=no', 'SendSIGKILL=no', 'KillMode=process', 'ExitType=cgroup',
                  'TimeoutStopSec=infinity', 'Nice=0', 'WorkingDirectory=' + str(ROOT),
                  'CPUAffinity=' + AFFINITY[job['lane']].replace(',', ' ')):
        cmd.append('--property=' + value)
    # systemd parses this property, not a shell. Paths are fixed or generated by us.
    cmd.append('--property=ExecStopPost=/usr/bin/python3 -B ' + str(HERE / 'lanequeue.py') + ' _receipt ' + str(receipt))
    for key, value in job.get('env_extra', {}).items():
        value = value.replace('{P49_LDP}', ldp).replace('{REVIEW}', review or '')
        cmd.append('--setenv=' + key + '=' + value)
    cmd += ['/usr/bin/taskset', '-c', AFFINITY[job['lane']]]
    if 'script' in job:
        # The bridge takes only named --setenv variables from the unit, closes the
        # rest, and invokes the coordinator. Its inner screen must use env -i.
        cmd += ['/usr/bin/python3', '-B', str(HERE / 'lanequeue.py'), '_coordinator',
                str(resolve(job['script'])), ldp, *job.get('env_extra', {}).keys()]
    else:
        cmd += ['/usr/bin/env', '-i', *[k + '=' + v for k, v in env.items()]]
        cmd += [a.replace('{REVIEW}', review or '') for a in job['argv']]
    return cmd


def job_script(job):
    if 'script' in job:
        return resolve(job['script'])
    argv = job['argv']
    if Path(argv[0]).name.startswith('python'):
        return resolve(argv[2])
    return resolve(argv[0]) if '/' in argv[0] else Path(shutil.which(argv[0], path='/usr/bin:/bin'))


def option(argv, name):
    for index, arg in enumerate(argv):
        if arg == name:
            require(index + 1 < len(argv), 'missing value for ' + name)
            return argv[index + 1]
        if arg.startswith(name + '='):
            return arg.split('=', 1)[1]
    return None


def report_failure_evidence(job):
    """Require job-local report/release proof and the shared completed drain.

    Called only after a nonzero exit and clean postflight against the launch
    fault count. Never guess outputs for coordinator scripts or nested jobs.
    """
    output = option(job.get('argv', []), '--output')
    require(output, 'report failure needs an explicit job --output')
    output = resolve(output)

    def read(path):
        row = json.loads(path.read_text())
        require(isinstance(row, dict), 'evidence must be a JSON object: ' + str(path))
        return row

    window = read(output / 'window.json')
    require(window.get('passed') is True and window.get('device_executed') is True,
            'device window did not pass and execute')
    failures = sorted(output.glob('*-report-failure.json'))
    require(failures, 'no job report-failure receipt')
    # Conflicting or malformed receipts must not hide a possible device failure.
    require(all(read(path).get('device_failure') is False for path in failures),
            'report-failure receipt does not exclude device failure')
    coordination = read(output / 'lane-coordination.json')
    require(coordination.get('released_before_report') is True or coordination.get('passed') is True,
            'lane release unproven')
    teardown = STAGE / 'screen/v3/teardown-state.json'
    require(read(teardown).get('drained') is True, 'shared teardown not drained')
    return dict(output=str(output), report_failures=[str(p) for p in failures],
                coordination=str(output / 'lane-coordination.json'), teardown=str(teardown))


def plan_job(job, ldp, invoke=subprocess.run):
    script = job_script(job)
    argv = job.get('argv', ['/usr/bin/bash', str(script)])
    output = option(argv, '--output')
    if output:
        require(not resolve(output).exists(), 'output directory already exists')
        require(not (resolve(output).parent / 'STOP').exists(), 'packet evidence STOP present')
    jobs = option(argv, '--jobs')
    if jobs:
        evidence = (script.parent if (script.parent / 'common.py').exists() else script.parent.parent) / 'evidence'
        require(not (evidence / 'STOP').exists(), 'packet quick STOP present')
        for line in resolve(jobs).read_text().splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            fields = line.split('|')
            require(len(fields) == 6 and Path(fields[0]).name == fields[0], 'unsupported quick jobs format')
            require(not (evidence / fields[0]).exists(), 'quick output directory already exists')
    source = script.read_text() if script.suffix in ('.py', '.sh') else ''
    # Never try --help/--plan on arbitrary shell wrappers: some ignore options
    # and launch devices. Only explicit Python argparse plan interfaces run.
    supports = False
    if script.suffix == '.py':
        supports = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == 'add_argument' and any(
                           isinstance(a, ast.Constant) and a.value == '--plan' for a in n.args)
                       for n in ast.walk(ast.parse(source)))
    if not supports:
        require(not jobs and not option(argv, '--seal'), 'cannot verify sealed job without --plan')
        return dict(name=job['name'], plan='unsupported; static argv/environment checks only')
    clean = []
    skip = False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg == '--fault-review':
            skip = True
        elif arg == '--authorized-device-window' or arg.startswith('--fault-review='):
            continue
        else:
            clean.append(arg)
    require(not any('{REVIEW}' in a for a in clean), 'review placeholder remains in plan command')
    env = closed_env(ldp)
    if 'script' in job:
        # A coordinator with --plan must document a CPU-only plan path.
        env.update({k: v.replace('{P49_LDP}', ldp).replace('{REVIEW}', '') for k, v in job.get('env_extra', {}).items()})
    seal = script.parent / 'quick_seal.py'
    if seal.is_file():
        seal_args = ['--verify'] if '--verify' in seal.read_text() else []
        cp = invoke(['/usr/bin/python3', '-B', str(seal), *seal_args], cwd=ROOT, env=closed_env(ldp),
                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        require(cp.returncode == 0, 'wrapper seal verification failed')
    cp = invoke(clean + ['--plan'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=120)
    require(cp.returncode == 0, 'CPU plan failed (seal, inputs or fresh outputs); inspect packet plan directly')
    return dict(name=job['name'], plan='passed', seal='checked by packet plan/wrapper')


class Queue:
    def __init__(self, directory, lane, backend=None, now=time.monotonic, sleep=time.sleep):
        self.directory, self.lane = directory, lane
        self.backend = backend or Backend()
        self.now, self.sleep = now, sleep
        self.stopped = False
        self.active = directory / f'inflight-{lane}.json'
        self.done = directory / f'done-{lane}.txt'

    def event(self, kind, **values):
        row = dict(utc=utc(), lane=self.lane, event=kind, **values)
        text = json.dumps(row, sort_keys=True)
        print(text, flush=True)
        with (self.directory / f'events-{self.lane}.jsonl').open('a') as f:
            f.write(text + '\n')
            f.flush()
            os.fsync(f.fileno())

    def boundary(self, until):
        while True:
            if self.stopped or (self.directory / f'STOP-{self.lane}').exists():
                return False
            if not (self.directory / f'PAUSE-{self.lane}').exists() and self.now() >= until:
                return True
            self.sleep(1)

    def finish(self, job, record):
        # Writers use the same edit lock. Re-read after the long job; never
        # overwrite the coordinator's newly appended/reordered rows.
        with lock(self.directory / f'edit-{self.lane}.lock'):
            rows = read_queue(self.directory, self.lane)
            matching = [r for r in rows if r['name'] == job['name']]
            require(not matching or matching == [job], 'inflight job was edited; completion retained, queue not overwritten')
            with self.done.open('a') as f:
                f.write(json.dumps(dict(job=job, **record), sort_keys=True) + '\n')
                f.flush()
                os.fsync(f.fileno())
            atomic(self.directory / f'queue-{self.lane}.txt', ''.join(json.dumps(r) + '\n' for r in rows if r['name'] != job['name']))
        self.active.unlink()

    def run(self):
        with lock(self.directory / f'driver-{self.lane}.lock', nonblocking=True):
            require(not os.path.lexists(self.active), 'unfinished driver record exists; inspect unit and evidence, never retry automatically')
            until = self.now()
            if self.done.exists():
                records = [json.loads(line) for line in self.done.read_text().splitlines() if line.strip()]
                if records:
                    require(records[-1]['outcome'] in ('DONE', 'REPORT-FAILED'), 'previous job failed; lane remains stopped for review')
                    elapsed = time.time() - records[-1]['end_unix']
                    until += max(0, 90 - elapsed)
            while self.boundary(until):
                with lock(self.directory / f'edit-{self.lane}.lock'):
                    rows = read_queue(self.directory, self.lane)
                if not rows:
                    self.sleep(1)
                    continue
                job = rows[0]
                if self.done.exists():
                    names = {json.loads(line)['job']['name'] for line in self.done.read_text().splitlines() if line.strip()}
                    require(job['name'] not in names, 'job already completed; no automatic replay')
                self.backend.guards(self.lane)
                ldp = library_path()
                plan_job(job, ldp)
                review = self.backend.review(job, self.directory) if job.get('review') else None
                # Recheck after CPU preparation; no queue snapshot survives a pause.
                if self.stopped or any((self.directory / f'{flag}-{self.lane}').exists() for flag in ('STOP', 'PAUSE')):
                    continue
                with lock(self.directory / f'edit-{self.lane}.lock'):
                    current = read_queue(self.directory, self.lane)
                    if not current or current[0] != job:
                        continue
                    faults_start = self.backend.guards(self.lane)
                    run_id = job['name'] + '-' + uuid.uuid4().hex
                    receipt = self.directory / (run_id + '.exit.json')
                    log = self.directory / (run_id + '.log')
                    start, started = self.now(), utc()
                    save(self.active, dict(job=job, start_utc=started, receipt=str(receipt), log=str(log),
                                           review=review, faults_start=faults_start))
                self.event('START', name=job['name'])
                rc = self.backend.execute(command(job, review, receipt, ldp), log)
                duration = self.now() - start
                ended, end_unix = utc(), time.time()
                status = self.backend.status(job['name'], receipt)
                outcome = 'DONE'
                if rc != 0:
                    outcome = 'REFUSED-fast' if duration < 10 else 'FAILED'
                elif status['Result'] != 'success' or str(status['ExecMainStatus']) != '0':
                    outcome = 'FAILED-status'
                postflight_ok, faults_end = False, None
                evidence = {}
                try:
                    faults_end = self.backend.guards(self.lane)
                    require(type(faults_start) is int and faults_end == faults_start,
                            'kernel fault count changed from job start')
                    postflight_ok = True
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    self.event('ALERT', reason=str(exc))
                    if outcome == 'DONE':
                        outcome = 'FAILED-postflight'
                if rc != 0 and postflight_ok:
                    try:
                        evidence['report_failure_evidence'] = report_failure_evidence(job)
                        outcome = 'REPORT-FAILED'
                    except (ValueError, OSError) as exc:
                        evidence['report_failure_rejection'] = str(exc)
                record = dict(rc=rc, **status, start_utc=started, end_utc=ended,
                              end_unix=end_unix, duration_seconds=duration, outcome=outcome,
                              log=str(log), receipt=str(receipt), review=review,
                              faults_start=faults_start, faults_end=faults_end, **evidence)
                save(self.active, dict(job=job, **record))
                self.finish(job, record)
                self.event(outcome, name=job['name'], rc=rc, Result=status['Result'])
                if outcome == 'REPORT-FAILED':
                    self.event('ALERT', name=job['name'],
                               reason='CPU report failed after passed device run and release; continuing to a different job; no retry')
                elif outcome != 'DONE':
                    self.event('ALERT', reason='lane stopped; no retry or next job')
                    return 1
                until = self.now() + 90
            self.event('STOP', reason='boundary stop requested')
            return 0


def main():
    # Unit-internal helpers do not inherit the CPU driver's nice/affinity.
    if len(sys.argv) > 1 and sys.argv[1] == '_receipt':
        save(Path(sys.argv[2]), dict(Result=os.environ.get('SERVICE_RESULT', 'unavailable'),
                                    ExecMainStatus=os.environ.get('EXIT_STATUS') if os.environ.get('EXIT_CODE') == 'exited' else None))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == '_coordinator':
        script, ldp, *keys = sys.argv[2:]
        env = closed_env(ldp)
        env.update({k: os.environ[k] for k in keys})
        os.execve('/usr/bin/env', ['env', '-i', *[k + '=' + v for k, v in env.items()], '/usr/bin/bash', script], {})
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('run', 'plan'))
    ap.add_argument('--lane', choices=('A', 'B'), required=True)
    ap.add_argument('--directory', type=Path, default=HERE)
    args = ap.parse_args()
    cpu_setup()
    directory = args.directory.resolve()
    require(directory.is_dir(), 'queue directory missing')
    if args.action == 'plan':
        failed = False
        with lock(directory / f'edit-{args.lane}.lock'):
            path = directory / f'queue-{args.lane}.txt'
            lines = path.read_text().splitlines() if path.exists() else []
        ldp = library_path()
        names = set()
        for number, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            name = None
            try:
                job = validate(json.loads(line), args.lane)
                name = job['name']
                require(name not in names, 'duplicate job name')
                names.add(name)
                row = plan_job(job, ldp)
            except (ValueError, TypeError, SyntaxError, OSError, subprocess.SubprocessError) as exc:
                row = dict(name=name, line=number, plan='FAILED', reason=str(exc))
                failed = True
            print(json.dumps(row), flush=True)
        return int(failed)
    queue = Queue(directory, args.lane)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: setattr(queue, 'stopped', True))
    try:
        return queue.run()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        queue.event('ALERT', reason=str(exc))
        return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print('ALERT: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
