#!/usr/bin/env python3
"""Coordinator-only packet58 single-card windows. Import and --help are CPU only."""
import argparse
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

import memory_plan as M
import onecard_admission as A
from views import VIEWS, selection, digest, DEFAULT_MAINTENANCE
from exec_limits import check as check_exec_limits
from owner_teardown import finish_model_owner
from launch_identity import lane_unit_prefix

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
_spec = importlib.util.spec_from_file_location('packet58_supervision', HERE / 'p56_head_support.py')
SUPPORT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SUPPORT)
S = SUPPORT.SUPERVISION
require, sha, save = S.require, S.sha, S.save
PCI = {0: '0000:23:00.0', 2: '0000:43:00.0'}
# Expected durations are conservative planning bounds, not speed measurements.
CONFIG = {'K1': (20, 600), 'WSCREEN': (1560, 7200)}
WRITES = {'K1': 128*1024**2, 'WSCREEN': 1024*1024**2}
PREVIOUS = {}  # Screening has no KD/layer-repeat/model-reload prerequisite.


def storage(output, writes):
    free=shutil.disk_usage('/').free
    require(free-writes>=25_000_000_000,'root storage below 25 GB after reserved writes')
    row=SUPPORT.storage(output,writes)
    return dict(row,root_free_bytes=free,root_stop_floor_bytes=25_000_000_000)


def install_fault_policy():
    # Each window is a fresh Python process; queue imports do not carry over.
    from fault_review import FaultFilter
    S.FAULT=FaultFilter()



def closed_environment(source=None):
    env = dict(os.environ if source is None else source)
    require(set(env) <= {'PATH', 'LD_LIBRARY_PATH', 'LC_CTYPE', 'OMP_NUM_THREADS'}, 'closed environment required')
    require(env.get('PATH', '/usr/bin:/bin') == '/usr/bin:/bin', 'fixed PATH required')
    require(env.get('OMP_NUM_THREADS', '2') == '2', 'OMP_NUM_THREADS=2 required')
    return S.environment_gate({k:v for k,v in env.items() if k not in ('PATH', 'OMP_NUM_THREADS')})


def memory_fence(sysroot=Path('/sys/devices/system/memory')):
    states = {str(n): (sysroot / f'memory{n}' / 'state').read_text().strip() for n in range(53, 58)}
    require(all(states[str(n)] == 'offline' for n in (54, 56)), 'failing memory blocks 54/56 must remain offline')
    return states  # Other three blocks are best-effort margin under the service contract.


def selected_clients(card, proc=Path('/proc')):
    selected, other, hidden = [], [], 0
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            infos = list((pid / 'fdinfo').iterdir())
        except PermissionError:
            hidden += 1
            continue
        except FileNotFoundError:
            continue
        for info in infos:
            try:
                fields = dict(line.split(':', 1) for line in info.read_text().splitlines() if ':' in line)
            except PermissionError:
                hidden += 1
                continue
            except (FileNotFoundError, ProcessLookupError):
                continue
            if fields.get('drm-driver', '').strip() == 'xe':
                pci = fields.get('drm-pdev', '').strip()
                row = dict(pid=int(pid.name), fd=info.name, pci=pci)
                (selected if pci == PCI[card] or not pci else other).append(row)
    require(not selected, 'selected card owned or client identity missing: ' + str(selected))
    return dict(selected=selected, other=other, inaccessible_entries=hidden,
                hidden_clients_require_coordinator_ownership=True)


def safe_path(root, name):
    rel = Path(name)
    path = (root / rel).resolve()
    require(not rel.is_absolute() and '..' not in rel.parts and path.is_relative_to(root.resolve()), 'unsafe identity path')
    return path


def verify_files(root, files):
    require(isinstance(files, dict) and bool(files), 'empty file identity')
    for name, digest in files.items():
        require(sha(safe_path(root, name)) == digest, 'identity changed: ' + name)


def build_gate():
    path = HERE / 'build-receipt.json'
    row = json.loads(path.read_text())
    require(row.get('schema') == 'own-runtime.packet58.build.v1' and row.get('passed') is True
            and row.get('device_executed') is False, 'CPU build receipt incomplete')
    from input_scope import check_pins
    for root, pins in ((REPO,row.get('sources')),(HERE,row.get('artifacts')),(HERE,row.get('gates'))):
        check_pins(root,pins)
    verify_files(REPO, row.get('sources'))
    verify_files(HERE, row.get('artifacts'))
    verify_files(HERE, row.get('gates'))
    require({'build/device/own-rt-iq3', 'build/device/p58-cache-fixtures'} <= set(row['artifacts']), 'both native binaries must be bound')
    require('evidence/postload-allocation-cpu.json' in row['gates'], 'post-load allocation gate required')
    require('evidence/fullshape-submit-cpu.json' in row['gates'], 'full-shape submit gate required')
    require('evidence/argument-gate.json' in row['gates'], 'real launch startup CPU gate required')
    for name in row['gates']:
        gate = json.loads(safe_path(HERE, name).read_text())
        require(gate.get('passed') is True and gate.get('device_executed') is False, 'CPU gate failed: ' + name)
    startup = json.loads((HERE/'evidence/argument-gate.json').read_text())
    require({(r['candidate'], r['window']) for r in startup['records']} ==
            {(v, w) for v in ('smoke', 'max') for w in ('K1a', 'K1b', 'WSCREEN')} and
            all(r.get('real_queue_entry') is True and r.get('real_unit_and_environment_gates') is True
                and r.get('live_host_admission') is True and r.get('native_exec_intercepted') is True
                for r in startup['records']), 'complete real startup paths required')
    return row


def prerequisite(path, name, identity):
    require(path is not None, 'missing prerequisite ' + name)
    path = Path(path).resolve()
    row = json.loads(path.read_text())
    require(row.get('schema') == 'own-runtime.packet58.window.v1' and row.get('passed') is True
            and row.get('device_executed') is True and row.get('child_still_running') is False
            and row.get('window') == name and row.get('stop_reasons') == []
            and row.get('qualifying') is (name != 'K1'), 'invalid prerequisite ' + name)
    A.verify(row)
    for key in ('boot_id', 'build_receipt_sha256', 'artifacts_sha256', 'environment', 'card', 'context', 'gpu_count', 'view', 'selection_sha256'):
        require(row.get(key) == identity.get(key), 'prerequisite differs: ' + key)
    require(type(row.get('pid')) is int and row['pid'] > 0
            and type(row.get('process_start_ticks')) is int and row['process_start_ticks'] > 0, 'fresh owner identity missing')
    closure = {'summary.json', 'kernel-before.jsonl', 'kernel-window.jsonl'}
    if name == 'K1':
        closure |= {'run/k1.json', 'run/k1-cases.jsonl'}
    else:
        closure |= {str(p.relative_to(path.parent)) for p in (path.parent/'run').rglob('*') if p.is_file()}
        require({'run/receipt.json', 'run/summary.json', 'run/run/receipt.json'} <= closure, 'model prerequisite receipt closure missing')
    require(set(row.get('native_files', {})) == closure, 'prerequisite native closure incomplete')
    verify_files(path.parent, row.get('native_files'))
    if name != 'K1':
        proof = row.get('postload_memory', {})
        require(proof.get('complete_postload') is True, 'complete postload proof missing')
        verify_files(path.parent, proof.get('sources'))
        require(sha(path.parent/'host-memory.jsonl') == row.get('memory_samples_sha256'),
                'supervisor memory samples changed')
    for leaf in ('kernel-before.jsonl', 'kernel-window.jsonl'):
        require(not S.FAULT.search((path.parent/leaf).read_text()), 'prerequisite kernel fault')
    return row


def cpu_k1_digest():
    row = json.loads((HERE/'k1-cpu.json').read_text())
    require(row.get('passed') is True and row.get('device_executed') is False,
            'CPU production fixture receipt missing')
    return row.get('exact_output_sha256')


def k1_summary(native, cpu_digest=None):
    require(native.get('passed') is True and native.get('zero_copy_bytes_equal') is True
            and native.get('mixed_bytes_equal') is True and native.get('streamed_bytes_equal') is True, 'K1 byte equality failed')
    require(native.get('safe_to_exit') is True and native.get('device_executed') is True
            and native.get('zero_copy_supported') is True, 'K1 device support or teardown unproved')
    digest = native.get('exact_output_sha256')
    require(isinstance(digest, str) and len(digest) == 64
            and all(c in '0123456789abcdef' for c in digest), 'K1 exact output hash missing')
    require(digest == (cpu_k1_digest() if cpu_digest is None else cpu_digest), 'K1 differs from CPU production kernel bytes')
    require(native.get('cold_rotation') is True and type(native.get('working_set_bytes')) is int
            and native['working_set_bytes'] >= 128*1024**2, 'K1 must rotate cold host backing')
    size = native.get('bytes_per_iteration')
    require(isinstance(size, int) and size > 0, 'K1 useful bytes missing')
    times = {k: native.get(k) for k in ('host_ms', 'vram_ms', 'streamed_ms')}
    require(all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in times.values()), 'K1 invalid timing')
    bandwidth = size / (times['host_ms'] * 1e6)
    return dict(**native, zero_copy_useful_GB_s=bandwidth,
                selected_miss_path='zero-copy' if bandwidth >= 12.5 else 'streamed',
                selection_threshold_GB_s=12.5, threshold_basis='half packet55 measured 25 GB/s copy floor',
                microbenchmark_only=True, model_speed_claim=False)


def selected_miss_path(paths, identity):
    require(paths is not None and len(paths) == 2 and Path(paths[0]).resolve() != Path(paths[1]).resolve(), 'two distinct fresh K1 windows required')
    rows = [prerequisite(path, 'K1', identity) for path in paths]
    require(len({(r['pid'], r['process_start_ticks']) for r in rows}) == 2, 'K1 owners not fresh')
    summaries = [k1_summary(json.loads((Path(path).parent / 'run/k1.json').read_text())) for path in paths]
    require(summaries[0]['exact_output_sha256'] == summaries[1]['exact_output_sha256'], 'K1 fresh-process output bytes differ')
    return 'zero-copy' if all(r['selected_miss_path'] == 'zero-copy' for r in summaries) else 'streamed'


def native_command(args, output, miss_path):
    if args.window == 'K1':
        return [str(HERE/'build/device/p58-cache-fixtures'), '--card', '0', '--output', str(output/'run'),
                '--iterations', '20', '--down-layout', json.loads(selection(getattr(args,'view','production')).read_text())['choices']['down'], '--authorized-device-window']
    return ['/usr/bin/python3', '-B', str(HERE/'suite_driver.py'), '--window', args.window, '--view', getattr(args,'view','max'),
            '--cache-maintenance',getattr(args,'cache_maintenance',DEFAULT_MAINTENANCE),
            '--card', str(args.card), '--output', str(output/'run'), '--miss-mode', 'zerocopy' if miss_path == 'zero-copy' else 'streamed',
            '--authorized-device-window']


def user_unit_gate(cgroup):
    paths = [line.split(':', 2)[-1] for line in cgroup.splitlines()]
    require(any('/user@' in p and p.rsplit('/', 1)[-1].startswith(('packet58-', lane_unit_prefix())) and p.endswith('.service') for p in paths),
            'coordinator-owned packet58-* or packet58x lanequeue systemd user service required')


class PinnedExpertProgress:
    """Credit only complete, unique census-matched host banks from this owner.

    Native progress is flushed AFTER allocation and fill. An in-flight bank
    receives no credit (conservative); it must fit inside the shadow allowance.
    The load log remains in run/run when request logs move to subdirectories.
    """
    def __init__(self, path, budget):
        self.path = Path(path)
        census = REPO / budget['census']['source_path']
        require(sha(census) == budget['census']['source_sha256'], 'pinned census changed')
        self.expected = {r['name']: r['bytes'] for r in json.loads(census.read_text())['tensors']
                         if r['component'] == 'routed_experts'}
        require(sum(self.expected.values()) == budget['census']['pinned_expert_bytes'], 'pinned census total changed')
        self.seen = set()
        self.offset = 0
        self.total = 0
        self.identity = None

    def read(self):
        try:
            stream = self.path.open('rb')
        except FileNotFoundError:
            require(self.identity is None, 'pinned progress disappeared')
            return self.total
        with stream:
            stat = os.fstat(stream.fileno())
            identity = (stat.st_dev, stat.st_ino)
            require(self.identity in (None, identity) and stat.st_size >= self.offset,
                    'pinned progress replaced or truncated')
            self.identity = identity
            stream.seek(self.offset)
            while True:
                line = stream.readline(65537)
                require(len(line) <= 65536, 'oversized pinned progress row')
                if not line or not line.endswith(b'\n'):
                    break  # Incomplete append gets no credit until its newline arrives.
                row = json.loads(line)
                if row.get('phase') == 'pinned-expert':
                    name, size = row.get('name'), row.get('bytes')
                    require(name in self.expected and name not in self.seen,
                            'unknown or duplicate pinned expert')
                    require(type(size) is int and size == self.expected[name], 'pinned expert bytes differ from census')
                    self.seen.add(name)
                    self.total += size
                self.offset = stream.tell()
        return self.total


def account_memory(sample, snapshot, baseline_gpuactive, pinned_bytes, budget, full_model=True):
    """Disjoint conservative charges; never subtract pinned bytes from RSS too."""
    sample['host'] = snapshot
    require(snapshot['MemAvailable'] >= M.HOST_RESERVE, 'host available memory below 8 GiB stop floor')
    require('GPUActive' in snapshot, 'GPUActive sensor missing')
    require(type(pinned_bytes) is int and 0 <= pinned_bytes <= (budget['census']['pinned_expert_bytes'] if full_model else 0),
            'pinned expert total exceeds admitted bound')
    growth = max(0, snapshot['GPUActive'] - baseline_gpuactive)
    shadow = max(0, growth - pinned_bytes)
    bound = budget['host_categories']['gpuactive_shadow_bound'] if full_model else 4*M.GIB
    sample.update(gpuactive_growth_bytes=growth, pinned_expert_bytes=pinned_bytes,
                  gpuactive_pinned_credit_bytes=min(growth, pinned_bytes),
                  gpuactive_shadow_bytes=shadow, gpuactive_shadow_bound_bytes=bound)
    require(shadow <= bound, 'GPUActive shadow exceeds admitted bound')
    if full_model:
        # RSS is charged in full: this driver does not expose the pinned USM
        # in RssAnon. No double credit if a different driver does expose it.
        file_bound = (0 if budget.get('admission_mode') == 'census-plus-measured-shadow'
                      else budget['host_categories']['file_backed_nonexpert_and_lookup_bound'])
        combined = pinned_bytes + shadow + sample['anonymous_bytes'] + file_bound
        combined_bound = budget['host_required_available_bytes'] - budget['host_reserve_bytes']
        sample.update(host_accounted_bytes=combined, host_accounted_bound_bytes=combined_bound)
        require(combined <= combined_bound, 'combined host memory exceeds admitted bound')
    return sample


def live_memory_sensor(pid, baseline_gpuactive=0, *, full_model=True, budget=None,
                       pinned_progress=None, sample_log=None, admission=None):
    budget = M.plan() if budget is None else budget
    # Read completed allocations before /proc, so future allocations cannot be
    # credited against an earlier GPUActive observation.
    pinned = pinned_progress.read() if full_model and pinned_progress is not None else 0
    sample = SUPPORT.process_tree_anon(pid)
    if not sample['root_seen'] and SUPPORT._exited_status(Path('/proc'), pid):
        sample['root_seen'] = True
        sample['root_pf_exiting_or_gone'] = True
    sample['sample_utc_ns'] = time.time_ns()
    snapshot = M.meminfo()
    try:
        if admission is not None:
            admission.observe(sample)
        if full_model:
            import device_memory
            sample['device_occupancy']=device_memory.observe(sample.get('processes',[]))
            require(sample['device_occupancy']['passed'],'device occupancy violates 1.5 GB reserve')
        return account_memory(sample, snapshot, baseline_gpuactive, pinned, budget, full_model)
    except Exception as error:
        sample['sensor_error'] = str(error)
        raise
    finally:
        if sample_log is not None:
            sample_log.write(json.dumps(sample, allow_nan=False) + '\n')
            sample_log.flush()  # Include the offending sample before cooperative stop.


def postload_observation(output, budget, admission):
    """Require actual post-cache native samples AND a complete native census.

    The old 58c end/teardown sample cannot satisfy this check. No device sample
    is invented by CPU preparation. Observations may only raise the seed;
    all unmeasured device backing remains in the next exactness plan.
    """
    run = output / 'run/run'
    snapshots = [json.loads(line) for line in (run/'host-memory.jsonl').read_text().splitlines()]
    loaded = [r for r in snapshots if r.get('phase') == 'after_load']
    require(len(loaded) == 1 and type(loaded[0].get('GPUActive')) is int,
            'complete after_load memory sample required')
    require(loaded[0]['GPUActive'] >= 0 and loaded[0]['MemAvailable'] >= M.HOST_RESERVE,
            'after_load memory sample violates reserve')
    censuses = json.loads((run/'census.json').read_text())
    require(isinstance(censuses, list) and len(censuses) == 1, 'one-card allocation census required')
    allocations = [r for r in censuses[0]['allocations'] if r.get('live') is True]
    experts = [r for r in allocations if ':pinned-experts:' in r['label']]
    expected = PinnedExpertProgress(run/'progress.jsonl', budget)
    require(expected.read() == budget['census']['pinned_expert_bytes'], 'incomplete postload pin census')
    require(len(experts) == 144 and {r['label'].split(':pinned-experts:')[1]:r['bytes'] for r in experts}
            == expected.expected and all(r['memory'] == 'host-pinned' for r in experts), 'postload expert census differs')
    cache = [r for r in allocations if r['label'] == 'card0:immutable-expert-cache']
    require(len(cache) == 1 and cache[0]['bytes'] == M.CACHE_BYTES, 'full cache census missing')
    kv = sum(r['bytes'] for r in allocations if r['category'] == 'KV')
    require(kv == budget['allocation_inventory']['kv_index_bytes'], 'full BF16 KV census missing')
    require(sum(r['bytes'] for r in allocations if r['memory'] == 'device') <= budget['device_owned_bound_bytes'],
            'native allocation census exceeds device bound')
    samples = [json.loads(line) for line in (output/'host-memory.jsonl').read_text().splitlines()]
    baseline = admission['baseline_gpuactive_bytes']
    peak = M.observed_shadow(samples, baseline, budget['census']['pinned_expert_bytes'])
    after = max(0, loaded[0]['GPUActive'] - baseline - budget['census']['pinned_expert_bytes'])
    return dict(peak_shadow_bytes=max(peak, after, M.seed_observation()['peak_shadow_bytes']),
                complete_postload=True, after_load_shadow_bytes=after,
                observed_supervisor_peak_bytes=peak, full_cache_bytes=M.CACHE_BYTES,
                kv_bytes=kv, pinned_expert_bytes=expected.total,
                source='successful same-chain native after_load plus complete allocation census',
                sources={str(p.relative_to(output)):sha(p) for p in
                         (run/'census.json', run/'host-memory.jsonl', output/'host-memory.jsonl')},
                attribution='host-global GPUActive; other-lane activity may inflate or mask delta; '
                            'full census backing bound remains reserved independently')


def finish_k1_devices(child, reasons, admission):
    """Call only after supervise's journal postflight; fail closed on any stop."""
    require(child.poll() == 0 and not reasons, 'native exit/postflight failed')
    admission.devices_drained()


def main(argv=None):
    install_fault_policy()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window', choices=tuple(CONFIG), required=True)
    parser.add_argument('--cache-maintenance',choices=('serial','overlap'),default=DEFAULT_MAINTENANCE)
    parser.add_argument('--view', choices=VIEWS, default='max')
    parser.add_argument('--card', type=int, choices=(0,), default=0)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--k1', type=Path, action='append')
    parser.add_argument('--faults-reviewed-through', required=True)
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args(argv)
    require(args.authorized_device_window, 'coordinator device-window authorization required')
    require(os.getpriority(os.PRIO_PROCESS, 0) == (0 if args.window.startswith('W') else 19), 'window priority differs')
    require(set(os.sched_getaffinity(0)) == set(range(4)) | set(range(16,20)) if args.window.startswith('W') else set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'window affinity differs')
    cgroup = Path('/proc/self/cgroup').read_text()
    user_unit_gate(cgroup)
    env = closed_environment()
    build = build_gate()
    output = args.output.resolve()
    require(output.is_relative_to((HERE/'evidence').resolve()) and not output.exists(), 'new packet58 evidence output required')
    budget = M.window_plan(args.window)
    # The definitive check follows the lane/whole-host wait. A live B screen
    # must be allowed to drain before WS128 tests its whole-host memory floor.
    memory = dict(pending_lane_admission=True, plan=budget)
    disk = storage(output, WRITES[args.window])
    build_bytes = sum(p.stat().st_size for p in (HERE/'build').rglob('*') if p.is_file())
    require(build_bytes <= 200_000_000, 'packet58x build exceeds 200 MB')
    review, through = S.fault_review(args.faults_reviewed_through, time.time_ns()//1000)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch_path = HERE / ('fault-'+boot+'.json')
    require(not latch_path.exists(), 'retained fault/uncertain-owner latch; coordinator recovery required')
    record = dict(schema='own-runtime.packet58.window.v1', window=args.window, passed=False, qualifying=False,
                  device_executed=False, child_still_running=False, card=args.card, pci_bdf=PCI[args.card],
                  native_visible_card=0, context=4096, gpu_count=1, decode_mode='plain',
                  view=args.view,selection_sha256=digest(args.view),
                  boot_id=boot, build_receipt_sha256=sha(HERE/'build-receipt.json'),
                  artifacts_sha256=build['artifacts'], environment=dict(env, **A.D.onecard_mask()), coordinator_fault_review=review,
                  started_utc_ns=time.time_ns(), expected_seconds=CONFIG[args.window][0],
                  watchdog_seconds=CONFIG[args.window][1], memory_admission=memory,
                  storage_admission=disk, systemd_cgroup=cgroup)
    if args.window in PREVIOUS:
        previous = prerequisite(args.previous, PREVIOUS[args.window], record)
        record['previous'] = dict(path=str(args.previous.resolve()), sha256=sha(args.previous))
        if args.window not in ('KD', 'WS128'):
            observation = previous.get('postload_memory')
            require(observation is not None and observation.get('complete_postload') is True,
                    'previous full post-load memory census required')
            budget = M.window_plan(args.window, observation)
    miss_path = None if args.window == 'K1' else selected_miss_path(args.k1, record)
    if args.window not in ('K1', 'KD', 'WSCREEN'):
        require(previous.get('miss_path') == miss_path, 'miss path differs from previous full-model gate')
    if args.window!='K1':require(miss_path=='zero-copy','overlap requires qualified zero-copy K1; no fallback')
    record['miss_path'] = miss_path
    if args.k1:
        record['k1_refs'] = [dict(path=str(p.resolve()), sha256=sha(p),
            native_k1_sha256=sha(p.parent/'run/k1.json')) for p in args.k1]
    output.mkdir(parents=True)
    record['device_topology'] = A.D.onecard_topology()
    env = A.D.onecard_environment(env, output/'native-home')
    record['native_environment'] = env  # Per-window private HOME; stable mask identity above.
    reasons, child, handlers = [], None, {}
    record['stop_reasons'] = reasons
    def persist():
        save(output/'window.json', record)
    def latch(reason):
        if child is not None or S.FAULT.search(reason):
            save(latch_path, dict(boot_id=boot, reason=reason, output=str(output), pid=None if child is None else child.pid))
    handlers = {sig: signal.signal(sig, lambda signum, frame: reasons.append('coordinator stop '+str(signum)))
                for sig in (signal.SIGTERM, signal.SIGINT)}
    wait_cursor = None
    def waiting_check():
        nonlocal wait_cursor
        require(not reasons, 'coordinator stop during admission')
        fresh, wait_cursor = S.journal(wait_cursor, since_us=through)
        if S.FAULT.search(fresh):
            latch('new GPU fault during lane admission')
            require(False, 'new GPU fault during lane admission')
    admission = A.Admission(args.window, output/'window.json', waiting_check)
    record['lane_admission'] = admission.record
    persist()
    try:
        with (HERE/'window.lock').open('a') as lock, admission:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record['memory_fence'] = memory_fence()
            record['clients'] = selected_clients(args.card)
            initial, cursor = S.journal()
            (output/'kernel-boot-before-review.jsonl').write_text(initial)
            initial, cursor = S.journal(cursor, since_us=through)
            (output/'kernel-before.jsonl').write_text(initial)
            require(not S.FAULT.search(initial), 'unreviewed GPU fault')
            binary = HERE/'build/device'/('p58-cache-fixtures' if args.window == 'K1' else 'own-rt-iq3')
            record['ldd'] = S.ldd_preflight(binary, env)
            # Recheck after locks, prerequisite hashing and journal preflight.
            memory = M.admit(M.meminfo(), budget)
            record['memory_admission'] = memory
            record['memory_fence'] = memory_fence()
            record['storage_admission'] = storage(output, WRITES[args.window])
            command = native_command(args, output, miss_path)
            record['command'] = command
            # Private inherited supervisor constants: full pinned experts are expected,
            # unlike the predecessor's small-fixture 8-GiB anonymous ceiling.
            S.ANONYMOUS_LIMIT_BYTES = budget['census']['pinned_expert_bytes'] + 4*M.GIB if args.window != 'K1' else 4*M.GIB
            S.ANONYMOUS_STOP_BYTES = S.ANONYMOUS_LIMIT_BYTES - 256*1024**2
            pinned_progress = PinnedExpertProgress(output/'run/run/progress.jsonl', budget) if args.window != 'K1' else None
            def after_drain_wait():
                nonlocal memory
                waiting_check()
                memory = M.admit(M.meminfo(), budget)
                record['memory_admission'] = memory
                record['memory_fence'] = memory_fence()
                record['storage_admission'] = storage(output, WRITES[args.window])
                A.D.verify_onecard_environment(env)
            with (output/'native.log').open('w') as log, (output/'kernel-window.jsonl').open('w') as kernel, (output/'host-memory.jsonl').open('w') as sample_log:
                A.D.verify_onecard_environment(env)
                admission.before_launch(after_drain_wait)
                check_exec_limits()
                child = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
                record.update(pid=child.pid, process_start_ticks=SUPPORT.process_start(child.pid), device_executed=True)
                persist()
                sensor = lambda pid: live_memory_sensor(pid, memory['snapshot'].get('GPUActive',0), full_model=args.window!='K1', budget=budget, pinned_progress=pinned_progress, sample_log=sample_log, admission=admission)
                record.update(S.supervise(child, CONFIG[args.window][1], cursor, kernel, reasons, latch, persist,
                    observe_memory=record.update, memory_sensor=sensor))
            if record['child_still_running']:
                record['child_retained'] = True
                persist()
                return 75
            if args.window != 'K1' and not reasons:
                record['teardown_confirmed_before_reporting']=finish_model_owner(child,output,admission,waiting_check)
            require(not reasons and child.returncode == 0, 'native window failed or interrupted')
            if args.window == 'K1':
                # supervise has waited for exit and performed journal postflight.
                # Reporting failure cannot leave a completed device job undrained.
                finish_k1_devices(child, reasons, admission)
            record['memory_samples_sha256'] = sha(output/'host-memory.jsonl')
            if args.window == 'K1':
                summary = k1_summary(json.loads((output/'run/k1.json').read_text()))
                record['native_files'] = {name:sha(output/name) for name in ('run/k1.json', 'run/k1-cases.jsonl')}
            else:
                receipt = json.loads((output/'run/receipt.json').read_text())
                require(receipt.get('passed') is True and receipt.get('safe_to_exit') is True
                        and receipt.get('window') == args.window, 'native driver receipt incomplete')
                summary = json.loads((output/'run/summary.json').read_text())
                record['postload_memory'] = postload_observation(output, budget, memory)
                record['native_files'] = {str(p.relative_to(output)):sha(p) for p in (output/'run').rglob('*') if p.is_file()}
            summary['timing_claim_eligible'] = False
            summary['evidence_label'] = 'screen'
            summary['submission_eligible'] = False
            summary['lane_scope'] = admission.scope
            save(output/'summary.json', summary)
            record['native_files']['summary.json'] = sha(output/'summary.json')
            for leaf in ('kernel-before.jsonl', 'kernel-window.jsonl'):
                record['native_files'][leaf] = sha(output/leaf)
            admission.complete()
            record.update(passed=True, qualifying=False, finished_utc_ns=time.time_ns())
            persist()
            return 0
    except Exception as error:
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            record.update(child_still_running=True, child_retained=True)
            latch('supervision failed; live child retained for coordinator')
        persist()
        return 75 if record.get('child_still_running') else 1
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)

if __name__ == '__main__':
    raise SystemExit(main())
