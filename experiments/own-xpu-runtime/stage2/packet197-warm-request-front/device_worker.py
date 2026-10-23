#!/usr/bin/env python3
"""Fixed eight-request lifecycle, one experimental warm owner; --plan is CPU-only.

The window coordinator alone owns endpoints, privileged passive inventories and
queue PAUSE bytes. This worker owns the inherited whole-host lease/drain permit.
There is no restart, retry, precision change, benchmark or submission path.
"""
import argparse
import hashlib
import gzip
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
ONE = P.parent / 'packet181-session-swap-v3/one-card'
CLIENT = ROOT / 'experiments/own-xpu-runtime/integration/request_front/client.py'
QUEUE = ROOT / 'experiments/own-xpu-runtime/ops/lane-queue'
OUTPUT = P / 'evidence/device-p197-lifecycle-A-a'
REVIEW = P / 'evidence/fault-review-device-a.json'
READY = P / 'READY-FOR-DEVICE.json'
UNIT = 'packet197-warm-request-front-a'
IDS = ['fresh-a', 'fresh-b', 'resume-a', 'append-a', 'append-repeat',
       'append-fresh', 'fresh-a-reference', 'fresh-b-repeat']
HOST_REQUIRED = 98_990_252_032
PLANNED_WRITES = 800_000_000  # five <80 MB states at N<=596; 64 MB logs +336 MB margin
DISK_FLOOR = 27_000_000_000
VIRTUAL_FLOOR = 8 * 1024**3
VOCAB = 248320


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, row):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(row, indent=2, allow_nan=False) + '\n')
    os.replace(temporary, path)


def parent_modules():
    # These historical modules use bare imports. In a dedicated worker process
    # admit their explicit namespace, and refuse collisions instead of replacing.
    names = ['common', 'conditions', 'chain_devices', 'lane_admission', 'drain_gate',
             'native_env', 'exec_limits', 'fault_review']
    for name in names:
        if name in sys.modules:
            require(Path(sys.modules[name].__file__).resolve() == ONE / (name + '.py'),
                    'parent namespace collision: ' + name)
    if sys.path[0] != str(ONE):
        sys.path.insert(0, str(ONE))
    modules = {name: importlib.import_module(name) for name in names}
    for name, module in modules.items():
        require(Path(module.__file__).resolve() == ONE / (name + '.py'), 'wrong parent import: ' + name)
    return modules


def client_module():
    spec = importlib.util.spec_from_file_location('p197_device_front_client', CLIENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bounded_journal_run(argv, **kwargs):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, timeout=15, **kwargs)


def journal(cursor=None):
    return parent_modules()['common'].S.journal(cursor, runner=bounded_journal_run)


def capture_review():
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    text, cursor = journal()
    return parent_modules()['fault_review'].inspect(text, boot, cursor), text


def validate_review(path):
    # Exact parent review semantics with a bounded journal runner, without
    # monkeypatching the historical supervisor or importing an operational driver.
    modules = parent_modules(); review = modules['fault_review']
    recorded = read(path)
    captured = gzip.decompress(Path(recorded['kernel_capture']).read_bytes()).decode()
    original = review.inspect(captured, recorded['boot_id'], recorded['cursor'])
    require(all(recorded.get(key) == value for key, value in original.items()), 'review/capture mismatch')
    current, text = capture_review()
    for name in ('schema', 'boot_id', 'fault_count', 'faults', 'driver_sha256'):
        require(current[name] == recorded.get(name), 'fault review changed: ' + name)
    modules['common'].S.fault_review(recorded['through'], time.time_ns() // 1000)
    require(current['through_us'] >= recorded['through_us'], 'kernel journal moved backward')
    fresh, cursor = journal(recorded['cursor'])
    require(not review.fault_lines(fresh), 'new kernel fault after review')
    return recorded, text, fresh, cursor


class IncidentStop:
    """Signal only the one retained native PID, at most once; never a group."""
    def __init__(self, record, child):
        self.record, self.child, self.sent = record, child, False

    def __call__(self, reason):
        if reason not in self.record['stop_reasons']:
            self.record['stop_reasons'].append(reason)
        child = self.child()
        if child is not None and child.poll() is None and not self.sent:
            self.sent = True
            self.record['incident_sigterm_count'] = 1
            try:
                child.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                require(child.poll() is not None, 'native signal target disappeared without exit')


def guarded_poll(check, incident):
    try:
        check()
        return True
    except BaseException as error:
        incident(str(error))
        return False


def native_argv():
    argv = read(ONE / 'parent-native-argv.json')
    argv[0] = str(P / 'build/device/own-rt-iq3')
    for flag in ('--suite-inputs', '--input'):
        index = argv.index(flag)
        del argv[index:index + 2]
    changes = {'--plan': ONE / 'inputs/plan.tsv', '--identity': ONE / 'inputs/identity.tsv',
               '--selection': ONE / 'selection.json', '--selection-sha256': sha(ONE / 'selection.json'),
               '--dispatch': ONE / 'dispatch.json', '--output': OUTPUT / 'owner',
               '--max-new': 512, '--seconds': 7200, '--wait-seconds': 600}
    for flag, value in changes.items():
        require(argv.count(flag) == 1, 'ambiguous parent flag ' + flag)
        argv[argv.index(flag) + 1] = str(value)
    argv += ['--request-front', '--request-front-max-requests', '8',
             '--request-front-idle-seconds', '300', '--request-front-checkpoints', str(OUTPUT / 'checkpoints'),
             '--request-front-tokenizer-identity', str(ONE / 'tokenizer-identity.tsv')]
    return ['/usr/bin/ionice', '-c3', *argv]


def fixtures():
    life = read(ONE / 'lifecycle.json')
    require((life['prompt_id'], life['K'], life['M1'], life['context']) ==
            ('incident-retrospective', 256, 128, 4096), 'parent lifecycle identity')
    a = list(map(int, (ONE / 'inputs/incident-retrospective/tokens.txt').read_text().split()))
    b = list(map(int, (ONE / 'inputs/decision-memo/tokens.txt').read_text().split()))
    turn = life['turn']['tokens']
    require(len(a) == 87 and len(turn) == 126 and turn == list(map(int,
            (ONE / life['turn']['source']).read_text().split()))[:126], 'canonical NEW469 turn')
    reference = read(ONE / 'reference-p179-row-a.json')['prompts']
    oracle = read(ONE / 'lineage/oracle128/incident-retrospective.json')['tokens']
    require(reference['incident-retrospective']['tokens'][:128] == oracle[:128], 'parent/oracle disagreement')
    return a, b, turn, reference, oracle


def source_paths():
    # Local immutable parent source closure, no model/object copies into Git.
    paths = list(ONE.glob('*.py'))
    paths += [ONE / name for name in ('parent-native-argv.json', 'lifecycle.json', 'budget.json',
              'reference-p179-row-a.json', 'identity.json', 'selection.json', 'dispatch.json',
              'tokenizer-identity.tsv', 'inputs/plan.tsv', 'inputs/identity.tsv',
              'inputs/incident-retrospective/tokens.txt', 'inputs/decision-memo/tokens.txt',
              'inputs/prefill512/tokens.txt', 'lineage/oracle128/incident-retrospective.json',
              'lineage/window_driver.py',
              'evidence/device-p181-lifecycle-A-b/run/checkpoints/s1/manifest.json',
              'evidence/device-p181-lifecycle-A-b/run/checkpoints/s2/manifest.json')]
    paths += [P / name for name in ('device_worker.py', 'device_fault_review.py', 'device_gates.py',
              'tests/test_device_worker.py', 'native/request_front.hpp', 'parent-pins.json',
              'native-request-front.patch', 'evidence/source-overlay.json',
              'evidence/build-compile-only.json', 'evidence/host-probe.json',
              'evidence/host-probe-artifacts.json', 'host_probe.py', 'build_engine.py')]
    paths.append(CLIENT)
    paths += [ROOT / name for name in read(P / 'parent-pins.json')['sources']]
    build = read(P / 'evidence/build-compile-only.json')
    for target in build['plans']:
        paths.append(Path(target['binary']))
        paths += [ROOT / name for name in target['repository_dependencies']]
    return sorted(set(path.resolve() for path in paths))


def verify_ready():
    ready = read(READY)
    require(ready.get('passed') is True and ready.get('device_executed') is False, 'CPU readiness missing')
    for name, digest in ready['files_sha256'].items():
        require(sha(ROOT / name) == digest, 'device input/source drift: ' + name)
    require(set(ready['files_sha256']) == {str(p.relative_to(ROOT)) for p in source_paths()}, 'readiness closure changed')
    gate = read(P / 'evidence/device-cpu-gates.json')
    require(gate['passed'] is True and ready['gates_sha256'] == sha(P / 'evidence/device-cpu-gates.json'), 'CPU gate mismatch')
    require(ready['native_argv'] == native_argv(), 'native argv differs from CPU interception')
    fixtures()
    return ready


def plan():
    ready = verify_ready()
    return dict(passed=True, device_executed=False, unit=UNIT, output=str(OUTPUT), fault_review=str(REVIEW),
                terminal_receipt=str(OUTPUT / 'worker.json'), ready=str(READY), ready_sha256=sha(READY),
                worker_argv=['/usr/bin/python3', '-B', str(P / 'device_worker.py'), '--authorized-device-window',
                             '--output', str(OUTPUT), '--fault-review', str(REVIEW)],
                native_argv=native_argv(), fault_review_command=['/usr/bin/python3', '-B', str(P / 'device_fault_review.py'),
                                                               '--output', str(REVIEW)],
                expected_request_ids=IDS, host_required_available_bytes=HOST_REQUIRED,
                planned_write_bytes=PLANNED_WRITES, disk_floor_bytes=DISK_FLOOR,
                cpu_affinity='0-3,16-19', nice=0, max_native_processes=1, max_requests=8,
                precision='full BF16 KV', context=4096, cache_bytes=21552729600,
                checkpoint_scope='experimental-warm-front / v1.2+p197', submission_eligible=False,
                source_count=len(ready['files_sha256']))


def memory(required):
    values = {line.split(':', 1)[0]: int(line.split()[1]) * 1024
              for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:', 'SwapFree:'))}
    require(values['MemAvailable'] >= required, 'host MemAvailable floor')
    return values


def storage(planned=0):
    free = shutil.disk_usage(P).free
    require(free - planned >= DISK_FLOOR, 'root free-after-writes floor 27 GB')
    return dict(free_bytes=free, planned_write_bytes=planned, floor_bytes=DISK_FLOOR)


def unit_gate():
    require(any(line.endswith('/' + UNIT + '.service') for line in Path('/proc/self/cgroup').read_text().splitlines()),
            'fixed coordinator worker unit required')
    keys = ('Restart', 'SendSIGKILL', 'KillMode', 'ExitType', 'TimeoutStopUSec')
    cp = subprocess.run(['/usr/bin/systemctl', '--user', 'show', UNIT + '.service',
                         *[arg for key in keys for arg in ('-p', key)]], stdin=subprocess.DEVNULL,
                        env=dict(PATH='/usr/bin:/bin', XDG_RUNTIME_DIR='/run/user/' + str(os.getuid())),
                        capture_output=True, text=True, timeout=15)
    props = dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)
    require(cp.returncode == 0 and props == dict(Restart='no', SendSIGKILL='no', KillMode='process',
            ExitType='cgroup', TimeoutStopUSec='infinity'), 'nonrestarting graceful worker properties')
    return props


def start_owner(argv, env, log, popen=None):
    require(argv == native_argv(), 'native exec argv drift')
    require(env['OMP_NUM_THREADS'] == '2' and env['FilterBdfPath'] == '0000:23:00.0', 'closed one-card environment')
    # Production path never calls the host probe or changes resource limits.
    parent_modules()['exec_limits'].check()
    return (popen or subprocess.Popen)(argv, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)


def exact(left, right, label):
    if left != right:
        index = next((i for i, pair in enumerate(zip(left, right)) if pair[0] != pair[1]), min(len(left), len(right)))
        raise ValueError(f'{label} mismatch at {index}; lengths {len(left)}/{len(right)}; '
                         f'actual={left[index:index+4]} expected={right[index:index+4]}')


def lifecycle(front, output, guard, persist):
    a, b, turn, reference, oracle = fixtures()
    rows = []
    owner = output / 'owner'
    def request(name, tokens, cap, **options):
        guard()  # No new input after any fault, stop, memory pressure or identity failure.
        response = front.request(name, tokens, cap, **options)
        guard()
        row = read(owner / 'requests' / name / 'result.json')
        require(row['passed'] is True and row['tokens'] == response['tokens'] and len(row['tokens']) == cap,
                'stream/result/cap mismatch: ' + name)
        require(row['request_front_scope'] == 'experimental-warm-owner-v1'
                and row['session_reuse'] is bool(options.get('restore')), 'session identity: ' + name)
        expected_cached = row['checkpoint']['restore']['saved_prefix_length'] if options.get('restore') else 0
        require(row['cached_tokens'] == expected_cached, 'restored prefix accounting: ' + name)
        require(read(owner / 'requests' / name / 'reset.json')['cached_tokens'] == 0, 'reset before restore')
        rows.append(dict(id=name, cap=cap, input_tokens=len(tokens), tokens=row['tokens'],
                         result_sha256=sha(owner / 'requests' / name / 'result.json'), cached_tokens=row['cached_tokens']))
        persist(rows)
        return row['tokens']
    saved = request('fresh-a', a, 256, save='s1')
    exact(saved, reference['incident-retrospective']['tokens'][:256], 'A parent prefix')
    exact(saved[:128], oracle[:128], 'A CPU oracle128')
    first_b = request('fresh-b', b, 128)
    exact(first_b, reference['decision-memo']['tokens'][:128], 'B parent prefix')
    resumed = request('resume-a', a, 128, restore='s1', save='s2')
    appended = a + saved + turn
    require(len(appended) == 469, 'canonical appended prompt length')
    x = request('append-a', appended, 128, restore='s1', save='s3')
    y = request('append-repeat', appended, 128, restore='s1', save='s4')
    z = request('append-fresh', appended, 128, save='s5')
    uninterrupted = request('fresh-a-reference', a, 384)
    repeated_b = request('fresh-b-repeat', b, 128)
    exact(saved + resumed, uninterrupted, 'A same-owner uninterrupted')
    exact(uninterrupted, reference['incident-retrospective']['tokens'][:384], 'A parent384')
    exact(x, y, 'append repeat'); exact(x, z, 'append fresh'); exact(first_b, repeated_b, 'B repeat')
    states = {}
    for name in ('s1', 's2', 's3', 's4', 's5'):
        folder = output / 'checkpoints' / name
        manifest = read(folder / 'manifest.json')
        require(manifest['label'] == 'experimental-warm-front' and manifest['contract'] == 'v1.2+p197'
                and manifest['qualified_by']['device_gates'] == [], 'experimental checkpoint scope')
        require(manifest['engine']['binary_sha256'] == sha(P / 'build/device/own-rt-iq3'), 'checkpoint owner identity')
        states[name] = {item: sha(folder / item) for item in
                        ['tokens.bin', *[blob['name'] + '.bin' for blob in manifest['blobs']]]}
    require(states['s3'] == states['s4'] == states['s5'], 'append/repeat/fresh state mismatch')
    return dict(A_parent_prefix=True, A_oracle128=True, A_resume_uninterrupted=True,
                append_repeat_fresh_tokens=True, append_repeat_fresh_state=True, B_parent_prefix=True, B_repeat=True), states


def execute(spec, fault_path):
    m = parent_modules(); common = m['common']; devices = m['chain_devices']
    m['conditions'].lane_gate('A'); m['exec_limits'].check()
    unit = unit_gate(); memory(HOST_REQUIRED); storage(PLANNED_WRITES)
    require(not os.path.lexists(OUTPUT), 'fresh output required; no retry')
    reviewed, initial, fresh, cursor = validate_review(fault_path)
    OUTPUT.mkdir()
    (OUTPUT / 'kernel-initial.jsonl').write_text(initial + fresh)
    record = dict(passed=False, device_executed=False, native_process_count=0, model_loads=0,
                  completed_requests=[], child_still_running=False, safe_to_exit=False, devices_drained=False,
                  submission_eligible=False, plan=spec, unit=unit, stop_reasons=[], started_utc_ns=time.time_ns())
    child = None
    stop_monitor = threading.Event()
    monitor_thread = None
    guard_lock = threading.RLock()
    monitor = devices.DeviceMonitor('A')
    deadline = time.monotonic() + 7200
    last_poll = 0
    def persist():
        save(OUTPUT / 'worker.json', record)
    stop_once = IncidentStop(record, lambda: child)
    def check(force=True):
        nonlocal cursor, last_poll
        with guard_lock:
            require(not record['stop_reasons'], 'intake halted: ' + str(record['stop_reasons']))
            require(time.monotonic() < deadline, 'whole worker deadline')
            for path in (QUEUE / 'STOP-A', QUEUE / 'STOP-B', QUEUE / 'PAUSE-A', OUTPUT / 'STOP'):
                require(not os.path.lexists(path), 'stop/admission latch ' + str(path))
            if not force and time.monotonic() - last_poll < 1:
                return
            last_poll = time.monotonic()
            text, cursor = journal(cursor)
            with (OUTPUT / 'kernel-window.jsonl').open('a') as log:
                log.write(text)
            require(not m['fault_review'].fault_lines(text), 'new GPU fault')
            storage(); memory(VIRTUAL_FLOOR)
            if child is not None:
                monitor.poll(force=True)
                require(all(fd['pci'] == '0000:23:00.0' for owner in monitor.owners.values() for fd in owner['fds']),
                        'owner escaped single card0')
                devices.admit_clients('whole-host', owned=monitor.live_identities())
                if child.poll() is None:
                    sample = common.SUPPORT.process_tree_anon(child.pid)
                    record['anonymous_peak_bytes'] = max(record.get('anonymous_peak_bytes', 0), sample['anonymous_bytes'])
                    require(sample['anonymous_bytes'] < HOST_REQUIRED - VIRTUAL_FLOOR - 256 * 1024**2,
                            'native anonymous-memory stop threshold')
    def background():
        try:
            os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 19)
            os.sched_setaffinity(threading.get_native_id(), set(range(8, 16)) | set(range(24, 32)))
            while not stop_monitor.wait(1):
                with guard_lock:
                    if guarded_poll(check, stop_once):
                        continue
                    persist()
                    return
        except BaseException as error:
            with guard_lock:
                stop_once('passive monitor failed: ' + str(error)); persist()
    handlers = {number: signal.signal(number, lambda n, f: stop_once('worker signal ' + str(n)))
                for number in (signal.SIGTERM, signal.SIGINT)}
    lease = m['lane_admission'].Reservation('A', window='screen', timing_claim=True, check=check)
    # timing_claim=True only selects the inherited stronger whole-host lock;
    # this lifecycle never qualifies a throughput claim.
    try:
        with lease:
            require(lease.scope == 'whole-host', 'whole-host reservation required')
            devices.admit_clients('whole-host'); devices.topology_admit('A'); check()
            record['reservation'] = lease.record
            env = devices.private_home(m['native_env'].environment('A'), OUTPUT / 'driver-home')
            record['environment'] = env; persist()
            with m['drain_gate'].DrainPermit(OUTPUT, check=check, reservation=lease.record) as permit:
                memory(HOST_REQUIRED); storage(PLANNED_WRITES); check()
                with (OUTPUT / 'native.stderr.log').open('wb') as log:
                    child = start_owner(native_argv(), env, log)
                    record.update(device_executed=True, native_process_count=1, pid=child.pid, child_still_running=True)
                    monitor.register(child.pid); persist()
                    monitor_thread = threading.Thread(target=background, name='p197-passive-guard', daemon=True)
                    monitor_thread.start()
                    front = client_module().NativeFront(child, context=4096, vocab=VOCAB, max_requests=8,
                                                       startup_timeout=900, request_timeout=900)
                    record['model_loads'] = front.ready['model_loads']; check()
                    require(monitor.owners[child.pid]['seen'], 'ready owner has no card0 FD proof')
                    def progress(rows):
                        with guard_lock:
                            record['requests'] = rows; record['completed_requests'] = [row['id'] for row in rows]; persist()
                    correctness, states = lifecycle(front, OUTPUT, check, progress)
                    stopped = front.close(timeout=120)
                    stop_monitor.set(); monitor_thread.join(timeout=20)
                    require(not monitor_thread.is_alive(), 'passive guard did not stop')
                    proof = read(OUTPUT / 'owner/receipt.json')
                    require(proof['passed'] is True and proof['safe_to_exit'] is True
                            and proof['device_executed'] is True and child.returncode == 0,
                            'successful native shutdown proof missing')
                    monitor.finish(); devices.admit_clients('whole-host'); check()
                    permit.complete(); lease.complete(drained=True)
                    record.update(passed=True, safe_to_exit=True, devices_drained=True, child_still_running=False,
                                  correctness=correctness, checkpoint_state_sha256=states, isolation=monitor.owners,
                                  stopped=stopped, finished_utc_ns=time.time_ns())
                    persist()
                    return 0
    except BaseException as error:
        with guard_lock:
            stop_once(str(error)); record['error'] = str(error)
        stop_monitor.set()
        if monitor_thread is not None:
            monitor_thread.join(timeout=20)
        if child is not None and child.poll() is None:
            try:
                child.wait(timeout=65)
            except subprocess.TimeoutExpired:
                pass
        record.update(child_still_running=child is not None and child.poll() is None,
                      child_returncode=child.returncode if child is not None else None,
                      incident_sigterm_count=int(stop_once.sent), finished_utc_ns=time.time_ns())
        persist()  # Lease/drain markers stay crash-closed on every failure.
        return 75 if record['child_still_running'] else 1
    finally:
        stop_monitor.set()
        for number, handler in handlers.items():
            signal.signal(number, handler)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--authorized-device-window', action='store_true')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--fault-review', type=Path)
    args = ap.parse_args()
    spec = plan()
    if args.plan:
        require(not args.authorized_device_window, 'plan cannot authorize a device')
        print(json.dumps(spec)); return 0
    require(args.authorized_device_window and args.output == OUTPUT and args.fault_review == REVIEW,
            'fixed coordinator authorization/output/fault review required')
    return execute(spec, args.fault_review)


if __name__ == '__main__':
    raise SystemExit(main())
