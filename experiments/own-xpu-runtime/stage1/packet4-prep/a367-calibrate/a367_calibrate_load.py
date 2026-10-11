#!/usr/bin/env python3
"""CPU supervisor for ONE owner-admitted A367 load; no native imports here.

--plan is CPU only. --execute is a future native window, never preparation.
The historical host-control shell scripts are evidence, never executed.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'driver'))
import window_driver as w

REG = HERE / 'preregistration.json'
SEAL = HERE / 'seal.json'
INTERVAL = .5
PLATEAU = 20
GAP = 305
LIVE_FLOOR_KIB = 12_000_000  # A367 supervisor reserve, NOT a launch floor
GRAPH = '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"compile_sizes":[],"cudagraph_num_of_warmups":1}'


def paths():
    result = {k: Path(v) for k, v in w.read(w.PREREG)['defaults'].items()}
    # The certified A367 launcher uses the retained USB publisher copy.
    result['model'] = Path('/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8')
    return result


def command_and_environment(output):
    p = paths()
    command = w.build_command(p)
    command.remove('--enforce-eager')
    command[command.index('--compilation-config') + 1] = GRAPH
    del command[command.index('--worker-cls'):]
    command.append('--cudagraph-metrics')
    env = w.build_environment(p, output)
    env['VLLM_XPU_ENABLE_XPU_GRAPH'] = '1'
    env['TORCH_TRACE'] = str(output / 'torch-trace')
    return command, env


def verify_seals():
    p = w.read(w.PREREG)
    for relative, digest in w.read(SEAL)['files'].items():
        w.require(w.sha(w.REPO / relative) == digest, 'calibration seal mismatch: ' + relative)
    members = {k: v for k, v in p['repo_pins'].items() if k.startswith('patches/')}
    w.require(len(members) == p['patch_seal_members'] == 75, '75-member seal required')
    for relative, digest in p['repo_pins'].items():
        w.require(w.sha(w.REPO / relative) == digest, 'A367 seal mismatch: ' + relative)
    return p


def fault_paths(output):
    # Include nested run latches, not only the top-level campaign markers.
    result = [output / 'FAULT.json']
    for root in w.FAULT_ROOTS:
        if root.exists():
            result.extend(root.rglob('FAULT.json'))
    return result


def calibration_approval_text(floor):
    return (f'I authorize one A367 calibrate-load measurement on steve-b70s with a '
            f'calibration-only MemAvailable start floor of {floor} KiB, a 0.5-second '
            f'watchdog and the 12000000 KiB live reserve, under preregistration SHA256 '
            f'{w.sha(REG)} and seal SHA256 {w.sha(SEAL)}. This accepts the unmatched '
            'loading-memory risk, does not lower the packet-4 fixture floor, and '
            'does not resolve the halt or authorize another launch.')


def calibration_floor(owner):
    exception = owner.get('calibration_memory_exception')
    if exception is None:
        return 120_000_000
    w.require(type(exception) is dict and set(exception) ==
              {'approved', 'approved_by', 'minimum_mem_available_kib', 'owner_approval_text'},
              'calibration exception fields')
    floor = exception['minimum_mem_available_kib']
    w.require(type(floor) is int and LIVE_FLOOR_KIB < floor < 120_000_000,
              'calibration exception floor range')
    w.require(exception['approved'] is True and exception['approved_by'] == 'owner'
              and exception['owner_approval_text'] == calibration_approval_text(floor),
              'calibration exception requires exact owner approval')
    return floor


def verify_admission(owner, health, boot, now, output, rows, faults, available_kib):
    w.verify_admission(owner, health, boot, now, output, rows, faults)
    w.require(owner.get('purpose') == 'a367-calibrate-load', 'calibration purpose absent')
    w.require(owner.get('calibration_preregistration_sha256') == w.sha(REG), 'calibration preregistration pin')
    w.require(owner.get('calibration_seal_sha256') == w.sha(SEAL), 'calibration seal pin')
    # Default intentionally cannot fit this boot; never infer a lower floor.
    w.require(owner.get('admission_revision_sha256') is None, 'fixture revision is not calibration admission')
    w.require(available_kib >= calibration_floor(owner), 'A367/calibration-approved admission floor not met')


def meminfo(text):
    result = {}
    for line in text.splitlines():
        key, value = line.split(':', 1)
        fields = value.split()
        if fields and fields[0].isdigit():
            result[key] = int(fields[0]) * (1024 if len(fields) > 1 and fields[1] == 'kB' else 1)
    w.require('MemTotal' in result and 'MemAvailable' in result, 'missing host memory observation')
    w.require(0 <= result['MemAvailable'] <= result['MemTotal'], 'invalid host memory counters')
    return result


def snapshot(pid=None, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup')):
    """No device opens/API calls. Unknown attribution remains null, never zero.

    Session membership limits rank discovery. cgroup.current may cover siblings;
    report its path/scope and never add it to host pressure or worker RSS.
    """
    mem = meminfo((proc / 'meminfo').read_text())
    row = {'monotonic': time.monotonic(), 'unix': time.time(),
           'mem_total_bytes': mem['MemTotal'], 'mem_available_bytes': mem['MemAvailable'],
           'host_pressure_bytes': mem['MemTotal'] - mem['MemAvailable'],
           'gpu_active_bytes': mem.get('GPUActive'), 'driver_shadow_bytes': None,
           'driver_shadow_note': 'GPUActive is observable but not uniquely attributable to this job',
           'ranks': {str(i): None for i in range(4)}, 'cgroups': []}
    if pid is None:
        return row
    cg_paths = set()
    for entry in proc.glob('[0-9]*'):
        try:
            if os.getsid(int(entry.name)) != pid:
                continue
            label = (entry / 'comm').read_text() + ' ' + (entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            match = re.search(r'(?:Worker[_-]TP|VllmWorker[-_])([0-3])(?=$|[^0-9])', label, re.I)
            if match:
                rank = match[1]
                w.require(row['ranks'][rank] is None, 'ambiguous rank PID attribution')
                status = meminfo_status((entry / 'status').read_text())
                row['ranks'][rank] = {'pid': int(entry.name), 'rss_bytes': status.get('VmRSS'),
                                      'source': str(entry / 'status')}
            for line in (entry / 'cgroup').read_text().splitlines():
                if line.startswith('0::'):
                    cg_paths.add(line[3:])
        except FileNotFoundError:
            continue
    for relative in sorted(cg_paths):
        target = cgroups / relative.lstrip('/') / 'memory.current'
        try:
            value = int(target.read_text())
        except (FileNotFoundError, PermissionError):
            value = None
        row['cgroups'].append({'path': str(target), 'memory_current_bytes': value,
                              'scope': 'existing cgroup, may include sibling processes; not exclusive'})
    return row


def meminfo_status(text):
    return {m[1]: int(m[2]) * 1024 for m in re.finditer(r'^(VmRSS):\s+(\d+) kB$', text, re.M)}


def summarize(rows):
    w.require(len(rows) >= 2, 'insufficient samples')
    times = [r['monotonic'] for r in rows]
    gaps = [b - a for a, b in zip(times, times[1:])]
    w.require(all(0 < gap <= 1.5 for gap in gaps), 'sampling gap/reversed time')
    w.require(rows[0]['phase'] == 'baseline', 'pre-launch baseline missing')
    w.require(len({r['mem_total_bytes'] for r in rows}) == 1, 'MemTotal changed')
    w.require(all(r['mem_available_bytes'] >= LIVE_FLOOR_KIB * 1024 for r in rows), 'live reserve crossed')
    w.require(all(0 <= r['mem_available_bytes'] <= r['mem_total_bytes'] for r in rows), 'invalid memory counters')
    phases = [r['phase'] for r in rows]
    order = {'baseline': 0, 'loading': 1, 'plateau': 2, 'shutdown': 3}
    w.require(all(p in order for p in phases) and all(order[a] <= order[b] for a, b in zip(phases, phases[1:])), 'phase order')
    plateau = [r for r in rows if r['phase'] == 'plateau']
    w.require(plateau and plateau[-1]['monotonic'] - plateau[0]['monotonic'] >= PLATEAU, 'incomplete 20s plateau')
    w.require('loading' in phases and phases[-1] == 'shutdown', 'incomplete phase coverage')
    for row in plateau:
        w.require(set(row['ranks']) == {'0', '1', '2', '3'} and all(
            r is not None and type(r['rss_bytes']) is int and r['rss_bytes'] > 0
            for r in row['ranks'].values()), 'missing plateau rank RSS')
        w.require(len({r['pid'] for r in row['ranks'].values()}) == 4, 'rank PID coverage')
        w.require(row['cgroups'] and all(type(c['memory_current_bytes']) is int
                  and c['memory_current_bytes'] >= 0 for c in row['cgroups']), 'missing plateau cgroup current')
    minimum = min(r['mem_available_bytes'] for r in rows)
    decline = max(0, rows[0]['mem_available_bytes'] - minimum)
    return {'baseline_available_bytes': rows[0]['mem_available_bytes'],
            'minimum_available_bytes': minimum, 'observed_need_bytes': decline,
            'observed_need_kib': (decline + 1023) // 1024,
            'max_sample_gap_seconds': max(gaps), 'sample_count': len(rows),
            'phase_min_available_bytes': {p: min(r['mem_available_bytes'] for r in rows if r['phase'] == p)
                                          for p in set(phases)},
            'scope': 'sampled startup/ready/shutdown need; generation and fixture demand unmeasured'}


class Stop:
    """Latch once, and send SIGINT once to the captured API PID, even on races."""
    def __init__(self, root):
        self.root, self.child, self.reason, self.sent = root, None, None, False
        self.lock = threading.RLock()

    def request(self, reason):
        with self.lock:
            self.reason = self.reason or reason
            if self.child is not None and not self.sent and self.child.poll() is None:
                self.sent = True
                w.write(self.root / 'stop-request.json', {'pid': self.child.pid, 'signal': 'SIGINT',
                        'unix': time.time(), 'reason': self.reason})
                try:
                    self.child.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass

    def attach(self, child):
        with self.lock:
            self.child = child
            if self.reason:
                self.request(self.reason)


class Sampler:
    def __init__(self, root, stop, live_check, sample=snapshot):
        self.root, self.stop, self.live_check, self.sample = root, stop, live_check, sample
        self.phase = 'baseline'
        self.rows = []
        self.failed = None
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def take(self):
        with self.lock:
            row = self.sample(self.stop.child.pid if self.stop.child else None)
            row['phase'] = self.phase
            with (self.root / 'samples.jsonl').open('a') as stream:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                stream.flush()
            self.rows.append(row)
            w.require(row['mem_available_bytes'] >= LIVE_FLOOR_KIB * 1024, 'A367 live memory reserve crossed')
            if len(self.rows) > 1:
                w.require(row['monotonic'] - self.rows[-2]['monotonic'] <= 1.5, 'sampler delayed >1.5s')
        return row

    def run(self):
        due = time.monotonic() + INTERVAL
        while not self.done.wait(max(0, due - time.monotonic())):
            try:
                self.take()
                self.live_check()
            except BaseException as exc:
                self.failed = self.failed or str(exc)
                self.stop.request('memory/admission watcher: ' + self.failed)
                # Keep sampling shutdown even after a trip, preserving the first failure.
            due += INTERVAL
            if due < time.monotonic():
                due = time.monotonic() + INTERVAL


def ready():
    # Exactly these two GET routes. No generation client, metrics probe or retries of a launch.
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{w.PORT}/health', timeout=.4) as response:
            if response.status != 200:
                return False
        with urllib.request.urlopen(f'http://127.0.0.1:{w.PORT}/v1/models', timeout=.4) as response:
            data = json.load(response)
        return [r['id'] for r in data['data']] == ['qwen38-flash-next-fp8-tp4']
    except (urllib.error.URLError, TimeoutError):
        return False


def lifecycle(root, command, env, sampler, stop, watch, *, launch=subprocess.Popen,
              is_ready=ready, clock=time.monotonic, sleep=time.sleep,
              owners_gone=w.owned_session_gone, process_rows=w.processes, mock=False):
    """Injectable control plane for CPU mocks. No test-only CLI launch bypass."""
    error = None
    reached_ready = clean_exit = gap_complete = False
    child = None
    try:
        sampler.take()  # baseline is committed before Popen
        sampler.phase = 'loading'
        sampler.thread.start()
        watch.poll()
        watch.thread.start()
        w.require(not stop.reason and not sampler.failed and not watch.failed, 'prelaunch monitor failure')
        with (root / 'server.log').open('xb') as log:
            child = launch(command, env=env, cwd=root, stdout=log,
                           stderr=subprocess.STDOUT, start_new_session=True)
            stop.attach(child)
            w.write(root / 'launch.json', {'pid': child.pid, 'unix': time.time()})
            deadline = clock() + 1200
            plateau_start = None
            while True:
                w.require(not stop.reason, str(stop.reason))
                w.require(not watch.failed, 'kernel watcher failed: ' + str(watch.failed))
                w.require(child.poll() is None, 'server exited before plateau completed')
                w.require(clock() < deadline, '1200s loading/plateau budget exceeded')
                if plateau_start is None and is_ready():
                    reached_ready = True
                    sampler.phase = 'plateau'
                    plateau_start = sampler.take()['monotonic']
                if plateau_start is not None and clock() - plateau_start >= PLATEAU:
                    sampler.take()  # endpoint sample proves full plateau, not just wall sleep
                    break
                sleep(INTERVAL)
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        sampler.phase = 'shutdown'
        stop.request(error or '20s plateau complete; zero generation requests')
        if child is not None:
            deadline = clock() + 300
            overrun = False
            # Wait for the ENTIRE session, not just the API PID. No escalation.
            while child.poll() is None or not owners_gone(child.pid):
                if clock() >= deadline and not overrun:
                    error = error or '300s teardown overrun; manual recovery required'
                    w.write(root / 'teardown-incomplete.json', {'reason': error, 'pid': child.pid})
                    overrun = True
                sleep(INTERVAL)
            try:
                sampler.take()
                watch.poll()  # fresh kernel read after every session owner has gone
                w.require(not w.conflicts(process_rows()), 'native conflict after exit')
                w.require(child.returncode == 0 and not overrun, 'unclean server/session teardown')
                w.require(not watch.failed and not sampler.failed, 'watcher/sampler failed')
                clean_exit = True
                completed = time.time()
                w.write(root / 'stop.json', {'all_owners_gone': True, 'returncode': child.returncode,
                        'completed_unix': completed, 'next_launch_not_before_unix': completed + GAP})
                sampler.done.set()
                if sampler.thread.ident is not None:
                    sampler.thread.join(5)
                w.require(not sampler.thread.is_alive(), 'sampler did not stop')
                # Gate the actual return as well as the receipt. Keep fault watch alive.
                until = clock() + GAP
                while clock() < until:
                    w.require(not watch.failed, 'fault during 305s gap')
                    sleep(min(INTERVAL, until - clock()))
                watch.poll()
                gap_complete = True
            except BaseException as exc:
                error = error or str(exc)
        sampler.done.set()
        watch.stop.set()
        for thread in (sampler.thread, watch.thread):
            if thread.ident is not None:
                thread.join(5)
            if thread.is_alive():
                error = error or 'monitor did not stop'
        if child is None or (child.poll() is not None and owners_gone(child.pid)):
            shutil.rmtree(root / 'scratch')
        else:
            w.write(root / 'scratch-retained.json', {'reason': 'owner uncertain; no cleanup'})
    summary = None
    try:
        w.require(error is None and reached_ready and clean_exit and gap_complete, error or 'incomplete lifecycle')
        summary = summarize(sampler.rows)
    except (ValueError, KeyError) as exc:
        error = error or str(exc)
    receipt = {'schema': 'own-xpu-runtime.packet4.a367-calibration.v1', 'passed': error is None,
               'ready': reached_ready, 'clean_exit': clean_exit, 'gap_complete': gap_complete,
               'generation_requests': 0, 'failure': error, 'summary': summary,
               'samples_sha256': w.sha(root / 'samples.jsonl') if (root / 'samples.jsonl').exists() else None,
               'identity_sha256': w.sha(root / 'identity.json'), 'mock': mock,
               'stop_sha256': w.sha(root / 'stop.json') if (root / 'stop.json').exists() else None}
    w.write(root / 'calibration.json', receipt)
    return 0 if receipt['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    for option in ('owner-window', 'health-receipt', 'payload-receipt'):
        parser.add_argument('--' + option, type=Path)
    args = parser.parse_args(argv)
    w.require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get('OMP_NUM_THREADS') == '2', 'nice19 OMP2 required')
    root = args.output.absolute()
    command, env = command_and_environment(root)
    if args.plan:
        print(json.dumps({'command': command, 'environment': env, 'deltas': w.read(REG)['identity_deltas'],
                          'native_executed': False, 'generation_requests': 0}, indent=2))
        return 0
    w.require(all((args.owner_window, args.health_receipt, args.payload_receipt)), 'owner/health/payload required')
    with (HERE.parent / 'extraction-window.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        owner, health = w.read(args.owner_window), w.read(args.health_receipt)
        owner_hash = w.sha(args.owner_window)
        def admit():
            w.require(w.sha(args.owner_window) == owner_hash, 'owner flag changed')
            w.require(Path(owner['health_path']).resolve() == args.health_receipt.resolve(), 'health path differs')
            verify_admission(owner, health, boot, time.time(), root, w.processes(), fault_paths(root),
                             snapshot()['mem_available_bytes'] // 1024)
        admit()
        prereg = verify_seals()
        audit = w.verify_environment(paths(), prereg)  # historical payload mismatch remains a blocker
        stage = paths()['stage'] / 'vllm_xpu_kernels'
        expected_members = {line.split(maxsplit=1)[1].strip().lstrip('*') for line in
                            (w.LANE / 'data/runtime-stage-gdn-roundstate-v2-loadable.sha256').read_text().splitlines()}
        actual_members = {str(p.relative_to(stage)) for p in stage.rglob('*')
                          if p.is_file() and p.suffix in ('.py', '.so')}
        w.require(actual_members == expected_members, 'A367 stage loadable file set changed')
        payload = w.read(args.payload_receipt)
        w.require(payload.get('passed') is True and payload.get('model_root') == str(paths()['model'])
                  and payload.get('revision') == 'bcd9f01ddc9cff2316eb84281bebcd5b058bddce'
                  and payload.get('all_files_sha256_verified') is True
                  and 0 <= time.time() - payload['verified_unix'] <= 3600
                  and w.sha(args.payload_receipt) == owner['payload_sha256'], 'fresh matched payload receipt required')
        w.require(shutil.disk_usage(root.parent).free >= prereg['minimum_disk_free_bytes'], 'disk reserve')
        with socket.socket() as port:
            port.bind(('127.0.0.1', w.PORT))
        baseline = w.journal()
        w.require(not w.fault_lines(baseline), 'fault-bearing boot refused')
        admit()  # repeat freshness/owners/floor after byte audit
        root.mkdir()
        (root / 'scratch/rpc').mkdir(parents=True)
        w.write(root / 'environment.json', audit)
        (root / 'kernel-before.log').write_text(baseline)
        for name, source in [('owner-window.json', args.owner_window), ('health.json', args.health_receipt), ('payload.json', args.payload_receipt)]:
            shutil.copyfile(source, root / name)
        w.write(root / 'identity.json', {'schema': 'own-xpu-runtime.packet4.a367-calibration-identity.v1',
            'mock': False, 'recipe': 'A367', 'host': socket.gethostname(), 'boot_id': boot,
            'kernel': health['kernel'], 'firmware': owner['firmware'], 'pci_ids': owner['pci_ids'],
            'preregistration_sha256': w.sha(REG), 'seal_sha256': w.sha(SEAL),
            'environment': env, 'command': command, 'audit_sha256': w.sha(root / 'environment.json'),
            'owner_sha256': owner_hash, 'payload_sha256': w.sha(args.payload_receipt),
            'identity_deltas': w.read(REG)['identity_deltas'],
            'calibration_memory_exception': owner.get('calibration_memory_exception'),
            'minimum_mem_available_kib': calibration_floor(owner)})
        stop = Stop(root)
        watch = w.Watch(root, baseline, boot)
        def live_check():
            w.require(w.sha(args.owner_window) == owner_hash and time.time() < owner['expires_unix'], 'owner revoked/expired')
            w.require(not watch.failed, 'kernel watcher failed')
            w.require(not (root / 'STOP.json').exists(), 'STOP latch')
            w.require(not any((p / 'FAULT.json').exists() for p in (*w.FAULT_ROOTS, root)), 'FAULT latch')
        sampler = Sampler(root, stop, live_check)
        old = {s: signal.signal(s, lambda *_: stop.request('coordinator interrupted')) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            return lifecycle(root, command, env, sampler, stop, watch)
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        sys.exit(2)
