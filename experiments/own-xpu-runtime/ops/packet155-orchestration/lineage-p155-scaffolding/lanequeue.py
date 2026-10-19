#!/usr/bin/env python3
"""Editable, crash-closed per-lane queue. Only `run` starts device units."""
import argparse
import ast
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
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
BOOT_ID_PATH = Path('/proc/sys/kernel/random/boot_id')
PROC = Path('/proc')
DRAIN_SPACING = 61.0
DRAIN_WAIT_LIMIT = 120.0
LIVE_WAIT_LIMIT = 1800.0
HOST_WAIT_LIMIT = 1200.0
HOST_HEADROOM = 1024 ** 3


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def drain_spacing_deadline():
    """Only a readable, completed drain on this boot adds queue spacing.

    Missing/incomplete/invalid records still go through the existing guards
    and frozen wrapper admission; this is not permission to bypass either.
    """
    try:
        row = json.loads((STAGE / 'screen/v3/teardown-state.json').read_text())
        if not isinstance(row, dict) or row.get('drained') is not True:
            return 0.0
        if row.get('boot_id') != BOOT_ID_PATH.read_text().strip():
            return 0.0
        completed = row.get('completed_monotonic')
        if type(completed) not in (int, float) or not math.isfinite(completed) or completed < 0:
            return 0.0
        return completed + DRAIN_SPACING
    except (OSError, ValueError, OverflowError):
        return 0.0


def live_window_blocker(lane):
    """Delay known live conflicts, without granting frozen-wrapper admission.

    v4 drain_gate permits only B over a matching live A lane-A reservation.
    Dead, reused, missing or unreadable owners keep the existing guard path.
    Read only: never acquire/create protocol locks or repair owner records.
    """
    def read(path):
        try:
            row = json.loads(path.read_text())
            return row if isinstance(row, dict) else {}
        except (OSError, ValueError):
            return {}

    def live(owner):
        pid = owner.get('pid')
        if type(pid) is not int or pid <= 0:
            return False
        try:
            # Match chain_devices.process_identity, including zombies and
            # comm names containing spaces/parentheses. Check PID reuse when
            # the reservation supplies start_ticks; v3 drains only have pid.
            fields = (PROC / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
            return (len(fields) >= 20 and fields[0] not in ('Z', 'X')
                    and (owner.get('start_ticks') is None
                         or int(fields[19]) == owner['start_ticks']))
        except (OSError, ValueError, IndexError):
            return False

    # Cover B's entire reservation, including before its drain record exists
    # and after drain completion but before its release/postflight finishes.
    active_b = read(COORD / 'active-lane-B.json')
    if lane == 'A' and live(active_b):
        return dict(source='active-lane-B.json', pid=active_b['pid'])
    row = read(STAGE / 'screen/v3/teardown-state.json')
    try:
        boot = BOOT_ID_PATH.read_text().strip()
    except OSError:
        return None
    if row.get('boot_id') != boot or row.get('drained') is True:
        return None
    owner = row.get('chain_reservation')
    owner = owner if isinstance(owner, dict) else {}
    if (lane == 'B' and owner == read(COORD / 'active-lane-A.json')
            and owner.get('scope') == 'lane-A' and owner.get('lane') == 'A'
            and owner.get('boot_id') == boot and owner.get('start_ticks') is not None
            and live(owner)):
        # The wrapper still verifies its own B reservation and all three locks.
        return None
    candidates = (owner,) if owner.get('pid') == row.get('pid') else (owner, row)
    for candidate in candidates:
        if live(candidate):
            return dict(source='teardown-state.json', pid=candidate['pid'])
    return None


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
    require(set(job) <= {'name', 'argv', 'script', 'env_extra', 'review', 'lane',
                         'depends_on', 'plan', 'admission'}, 'unknown job field')
    require(job.get('lane') == lane, 'job lane differs from queue')
    require(isinstance(job.get('name'), str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', job['name']), 'invalid unit name')
    deps = job.get('depends_on', [])
    require(isinstance(deps, list) and all(isinstance(d, str) and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', d) and d != job['name']
            for d in deps), 'depends_on must list other job names')
    for key in ('plan', 'admission'):
        require(key not in job or isinstance(job[key], dict), key + ' must be an object')
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


class DeviceObservation:
    """Read only: observe the unit cgroup, including grandchildren, while it runs.

    Sampling alone never proves absence of device work. A fresh job receipt
    must independently assert that it never executed, and ambiguity stops.
    """
    def __init__(self, unit):
        self.unit = unit
        self.pids = set()
        self.device_fds = set()
        self.errors = set()
        self.live = set()
        self.samples = 0

    def sample(self):
        live = set()
        try:
            processes = list(PROC.iterdir())
        except OSError:
            self.errors.add('proc unavailable')
            return
        for proc in processes:
            if not proc.name.isdigit():
                continue
            try:
                groups = proc.joinpath('cgroup').read_text().splitlines()
                if not any(self.unit in line.split(':', 2)[-1].split('/') for line in groups):
                    continue
            except FileNotFoundError:
                continue
            except OSError:
                self.errors.add('cgroup unreadable: ' + proc.name)
                continue
            live.add(int(proc.name))
            self.pids.add(int(proc.name))
            try:
                for fd in (proc / 'fd').iterdir():
                    try:
                        target = os.readlink(fd)
                    except FileNotFoundError:
                        continue  # An fd closed between enumeration and read.
                    if target.startswith(('/dev/dri/', '/dev/accel/')):
                        self.device_fds.add(target)
            except FileNotFoundError:
                # An exited task cannot supply a complete observation.
                self.errors.add('fd observation incomplete: ' + proc.name)
            except OSError:
                self.errors.add('fd observation unreadable: ' + proc.name)
        self.live = live
        self.samples += 1

    def evidence(self):
        return dict(pids=sorted(self.pids), device_fds=sorted(self.device_fds),
                    errors=sorted(self.errors), live_pids=sorted(self.live), samples=self.samples)


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
        require(type(faults) is int and faults == BASE,
                'kernel fault count changed from reviewed base 2 or is unreadable')
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
        for latch in (STAGE / 'screen/v3').glob('fault-*'):
            # V4 records the lane in the filename, not the JSON body. Only a
            # known other-lane latch on the reviewed boot can be scoped locally.
            # The global journal check above must pass first; never learn a
            # higher baseline from a latch or a restarted driver.
            match = re.fullmatch(
                r'fault-([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})-([AB])\.json',
                latch.name)
            require(match is not None and match[1].startswith(BOOT) and match[2] != lane,
                    'screen/v3 fault latch present; retained for review: ' + str(latch))
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
        unit = next(a.split('=', 1)[1] for a in cmd if a.startswith('--unit=')) + '.service'
        observation = DeviceObservation(unit)
        self.device_observation = None
        with log.open('x') as f:
            child = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=f, stderr=f)
            while True:
                observation.sample()
                rc = child.poll()  # Capture before clocks, status reads or logging.
                if rc is not None:
                    break
                time.sleep(.1)
        observation.sample()
        self.device_observation = observation.evidence()
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


def host_requirement(job, plan):
    """Take the largest declared admission bound; never import packet code."""
    bounds = []
    whole_host = False

    def visit(row):
        nonlocal whole_host
        if isinstance(row, list):
            for item in row:
                visit(item)
        elif isinstance(row, dict):
            whole_host |= row.get('scope') == 'whole-host'
            for key, value in row.items():
                if key == 'host_required_available_bytes':
                    require(type(value) is int and value > 0, 'invalid host admission bound')
                    bounds.append(value)
                elif isinstance(value, (dict, list)):
                    visit(value)

    visit(plan)
    visit(job.get('plan', {}))
    visit(job.get('admission', {}))
    if not bounds:
        packet = job_script(job).parent
        for relative in ('memory-plan.json', 'memory-budget.json', 'evidence/memory-budget.json'):
            path = packet / relative
            if path.is_file():
                visit(json.loads(path.read_text()))
    require(bounds or not whole_host, 'whole-host plan has no host admission bound')
    return max(bounds, default=0)


def mem_available():
    values = re.findall(r'^MemAvailable:\s+(\d+) kB$', (PROC / 'meminfo').read_text(), re.M)
    require(len(values) == 1, 'MemAvailable unavailable or malformed')
    return int(values[0]) * 1024


def predevice_evidence(job, observation):
    """Require fresh whole-job refusal evidence, never a fast-exit heuristic."""
    require(isinstance(observation, dict) and observation.get('samples', 0) > 0
            and observation.get('pids') and observation.get('device_fds') == []
            and observation.get('errors') == [] and observation.get('live_pids') == [],
            'complete device-free PID observations unavailable')
    require(not os.path.lexists(COORD / f"active-lane-{job['lane']}.json"),
            'lane marker remains')
    require(not list((STAGE / 'screen/v3').glob('fault-*')), 'fault latch remains')
    teardown = STAGE / 'screen/v3/teardown-state.json'
    if os.path.lexists(teardown):
        drain = json.loads(teardown.read_text())
        require(isinstance(drain, dict) and drain.get('drained') is True,
                'shared teardown undrained or unknown')
    output = option(job.get('argv', []), '--output')
    require(output, 'pre-device refusal needs explicit job --output')
    output = resolve(output)
    require(output.is_dir() and not output.is_symlink(), 'fresh job receipt directory unavailable')
    # plan_job required this output to be absent before launch. Check all
    # window/queue receipts: a later refusal cannot erase an earlier K1 run.
    paths = sorted(p for p in output.rglob('*.json') if p.name in
                   ('window.json', 'queue.json', 'refusal.json') or 'refusal' in p.name)
    proof, hashes = [], {}
    for path in paths:
        require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve()),
                'receipt escapes fresh job output')
        raw = path.read_bytes()
        row = json.loads(raw)
        require(isinstance(row, dict), 'invalid refusal receipt')
        no_load = any(isinstance(row.get(key), str) and 'no pin or model load' in row[key].lower()
                      for key in ('error', 'reason', 'message'))
        require((row.get('device_executed') is False or ('device_executed' not in row and no_load))
                and ('child_still_running' not in row or row['child_still_running'] is False)
                and not row.get('completed') and not row.get('device_complete')
                and not row.get('child_retained'),
                'receipt does not exclude device work: ' + str(path))
        hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        if row.get('passed') is False and (row.get('error') or row.get('stop_reasons') or row.get('refused') or no_load):
            proof.append(str(path))
    require(proof, 'no explicit failed pre-device job receipt')
    return dict(receipts=proof, receipt_sha256=hashes, observation=observation, teardown=str(teardown))


def dependent_names(rows, refused):
    """Transitive explicit dependencies plus the packet's smoke prerequisite."""
    dropped = {refused['name']}
    def prefix(name):
        match = re.match(r'^(?:packet|p)(\d+[a-z]*)(?=[-_.]|$)', name)
        return match[1] if match else None
    changed = True
    while changed:
        changed = False
        smoke_packets = {prefix(name) for name in dropped if 'smoke' in name.lower()} - {None}
        for row in rows:
            if row['name'] not in dropped and (dropped.intersection(row.get('depends_on', []))
                    or prefix(row['name']) in smoke_packets):
                dropped.add(row['name'])
                changed = True
    return dropped


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
        return dict(name=job['name'], plan='unsupported; static argv/environment checks only',
                    host_required_available_bytes=host_requirement(job, {}))
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
    try:
        metadata = json.loads(cp.stdout)
    except ValueError:
        require('host_required_available_bytes' not in cp.stdout and 'whole-host' not in cp.stdout,
                'host admission plan is not valid JSON')
        metadata = {}
    return dict(name=job['name'], plan='passed', seal='checked by packet plan/wrapper',
                host_required_available_bytes=host_requirement(job, metadata))


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

    def launch_interrupted(self):
        return self.stopped or any((self.directory / f'{flag}-{self.lane}').exists()
                                   for flag in ('STOP', 'PAUSE'))

    def wait_host_admission(self, job, required, limit):
        if not required:
            return not self.launch_interrupted()
        last_log = float('-inf')
        while True:
            if self.launch_interrupted():
                return False
            self.backend.guards(self.lane)
            if self.launch_interrupted():
                return False
            available = mem_available()
            shortfall = required + HOST_HEADROOM - available
            if shortfall <= 0:
                return True
            require(self.now() < limit, 'host admission wait timed out; no launch')
            if self.now() - last_log >= 30:
                self.event('WAIT-HOST-ADMISSION', name=job['name'],
                           available_bytes=available, required_bytes=required,
                           headroom_bytes=HOST_HEADROOM, shortfall_bytes=shortfall,
                           until_monotonic=limit)
                last_log = self.now()
            self.sleep(max(0.0, min(1.0, limit - self.now())))

    def wait_drain_spacing(self, job):
        # Do not hold the edit lock while waiting: pause/reorder remains usable.
        limit = self.now() + DRAIN_WAIT_LIMIT
        live_limit = self.now() + LIVE_WAIT_LIMIT
        logged = None
        logged_live = None
        while True:
            if self.launch_interrupted():
                return False
            self.backend.guards(self.lane)
            if self.launch_interrupted():
                return False
            blocker = live_window_blocker(self.lane)
            if blocker is not None:
                require(self.now() < live_limit, 'other lane live wait timed out; no launch')
                if blocker != logged_live:
                    self.event('WAIT-OTHER-LANE-LIVE', name=job['name'],
                               until_monotonic=live_limit, **blocker)
                    logged_live = blocker
                # Give a completed drain its own existing spacing budget.
                limit = self.now() + DRAIN_WAIT_LIMIT
                self.sleep(max(0.0, min(1.0, live_limit - self.now())))
                continue
            logged_live = None
            until = drain_spacing_deadline()  # Follow the latest shared drain.
            now = self.now()
            if now >= until:
                return True
            require(now < limit, 'shared drain spacing wait timed out; no launch')
            if until != logged:
                self.event('WAIT-DRAIN-SPACING', name=job['name'],
                           wait_seconds=until - now, until_monotonic=until)
                logged = until
            # Guards/logging can outlast the remainder. Never pass a negative
            # sleep, including when the bounded wait itself has expired.
            self.sleep(max(0.0, min(1.0, until - self.now(), limit - self.now())))

    def finish(self, job, record):
        # Writers use the same edit lock. Re-read after the long job; never
        # overwrite the coordinator's newly appended/reordered rows.
        predevice = record.get('outcome') == 'REFUSED-PREDEVICE'
        lanes = ('A', 'B') if predevice else (self.lane,)
        with ExitStack() as stack:
            for lane in lanes:
                stack.enter_context(lock(self.directory / f'edit-{lane}.lock'))
            rows = read_queue(self.directory, self.lane)
            matching = [r for r in rows if r['name'] == job['name']]
            require(not matching or matching == [job], 'inflight job was edited; completion retained, queue not overwritten')
            queues = {lane: read_queue(self.directory, lane) for lane in lanes}
            dropped = dependent_names([r for rs in queues.values() for r in rs], job) if predevice else {job['name']}
            if predevice:
                for lane in lanes:
                    inflight = self.directory / f'inflight-{lane}.json'
                    if lane != self.lane and os.path.lexists(inflight):
                        active = json.loads(inflight.read_text())
                        require(active['job']['name'] not in dropped, 'dependent job already inflight; stop for review')
                record['dropped_dependencies'] = sorted(dropped - {job['name']})
            with self.done.open('a') as f:
                f.write(json.dumps(dict(job=job, **record), sort_keys=True) + '\n')
                f.flush()
                os.fsync(f.fileno())
            for lane, queued in queues.items():
                skipped = [r for r in queued if r['name'] in dropped and r['name'] != job['name']]
                if skipped:
                    with (self.directory / f'done-{lane}.txt').open('a') as f:
                        for row in skipped:
                            f.write(json.dumps(dict(job=row, outcome='SKIPPED-DEPENDENCY',
                                      depends_on_refused=job['name'], end_unix=record['end_unix'])) + '\n')
                        f.flush()
                        os.fsync(f.fileno())
                    for row in skipped:
                        Queue(self.directory, lane, self.backend).event('SKIPPED-DEPENDENCY',
                                name=row['name'], depends_on_refused=job['name'])
                if lane == self.lane or skipped:
                    atomic(self.directory / f'queue-{lane}.txt', ''.join(json.dumps(r) + '\n'
                           for r in queued if r['name'] not in dropped))
        self.active.unlink()

    def run(self):
        with lock(self.directory / f'driver-{self.lane}.lock', nonblocking=True):
            require(not os.path.lexists(self.active), 'unfinished driver record exists; inspect unit and evidence, never retry automatically')
            until = self.now()
            admission_deadlines = {}
            if self.done.exists():
                records = [json.loads(line) for line in self.done.read_text().splitlines() if line.strip()]
                if records:
                    terminal = [r for r in records if r['outcome'] != 'SKIPPED-DEPENDENCY']
                    require(not terminal or terminal[-1]['outcome'] in ('DONE', 'REPORT-FAILED', 'REFUSED-PREDEVICE'), 'previous job failed; lane remains stopped for review')
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
                plan = plan_job(job, ldp)
                required = plan.get('host_required_available_bytes', 0)
                deadline = admission_deadlines.setdefault(job['name'], self.now() + HOST_WAIT_LIMIT)
                if not self.wait_host_admission(job, required, deadline):
                    continue
                review = self.backend.review(job, self.directory) if job.get('review') else None
                # Recheck after CPU preparation; no queue snapshot survives a pause.
                if not self.wait_drain_spacing(job):
                    continue
                if not self.wait_host_admission(job, required, deadline):
                    continue
                with lock(self.directory / f'edit-{self.lane}.lock'):
                    current = read_queue(self.directory, self.lane)
                    if not current or current[0] != job:
                        continue
                    faults_start = self.backend.guards(self.lane)
                    # A teardown or pause can arrive while taking the edit lock
                    # or checking guards. Discard this preparation and recheck.
                    if (self.launch_interrupted() or live_window_blocker(self.lane) is not None
                            or self.now() < drain_spacing_deadline()
                            or (required and mem_available() < required + HOST_HEADROOM)):
                        continue
                    run_id = job['name'] + '-' + uuid.uuid4().hex
                    receipt = self.directory / (run_id + '.exit.json')
                    log = self.directory / (run_id + '.log')
                    start, started = self.now(), utc()
                    save(self.active, dict(job=job, start_utc=started, receipt=str(receipt), log=str(log),
                                           review=review, faults_start=faults_start))
                self.event('START', name=job['name'])
                self.backend.device_observation = None
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
                evidence = dict(device_observation=self.backend.device_observation)
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
                        require(status['Result'] == 'exit-code' and str(status['ExecMainStatus']) == str(rc),
                                'ordinary job exit status unavailable')
                        evidence['predevice_evidence'] = predevice_evidence(job, self.backend.device_observation)
                        outcome = 'REFUSED-PREDEVICE'
                    except (ValueError, OSError) as exc:
                        evidence['predevice_rejection'] = str(exc)
                if rc != 0 and postflight_ok and outcome != 'REFUSED-PREDEVICE':
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
                elif outcome == 'REFUSED-PREDEVICE':
                    self.event('ALERT', name=job['name'], dropped_dependencies=record['dropped_dependencies'],
                               reason='Proven pre-device refusal; dependent rows dropped; continuing to an independent job; no retry')
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
