#!/usr/bin/env python3
"""CPU control plane for the sealed two-arm A367 glue01 screen.

Lifecycle copied from a367-calibrate/a367_calibrate_load.py at 5efca23e3
(seal b75d9f86); admission, ESRCH handling, short IPC and ext4 scratch retained.
The calibration and driver are immutable dependencies, not edited here.

--plan is CPU only. --execute is a future native window, never preparation.
The historical host-control shell scripts are evidence, never executed.
"""
from __future__ import annotations
from sample_writer import SampleWriter
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
# 1800 s (was 1200): attempt 3 needed 731 s to load and reached graph capture at 895 s on a cold
# per-run Triton cache; a budget trip there would SIGINT a capturing four-card server.
LOAD_BUDGET = 1800
GAP = 305
RPC_PATH_MAX = 107
# Caches/rpc/tmp live on local ext4, not the output NTFS mount: ntfs-3g rename-over is not
# atomic, so four ranks sharing a Triton cache saw a published .llir vanish (attempt 3).
LOCAL_SCRATCH = Path('/home/steve/.cache/a367-scratch')
LOCAL_SCRATCH_MIN_FREE = 4 * 2**30
TRACE_SOFT_STOP = 6 * 2**30

def trace_dir(output):
    return output



def scratch_dir(output):
    return LOCAL_SCRATCH / output.name
LIVE_FLOOR_KIB = 12_000_000  # A367 supervisor reserve, NOT a launch floor
GRAPH = '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"compile_sizes":[],"cudagraph_num_of_warmups":1}'


ARMS = ('control', 'candidate')

def paths(arm='control'):
    result = {k: Path(v) for k, v in w.read(w.PREREG)['defaults'].items()}
    # Reviewed byte-identical reconstruction; no shared fixture default change.
    result['source'] = Path('/home/steve/src/vllm-flashnext-a367-clean-20261016')
    # The certified A367 launcher uses the retained USB publisher copy.
    result['model'] = Path('/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8')
    if arm == 'candidate':
        result['source'] = Path('/home/steve/src/vllm-flashnext-a367-glue01-20261017')
    return result


def command_and_environment(output, arm='control'):
    w.require(arm in ARMS, 'unknown arm')
    p = paths(arm)
    command = w.build_command(p)
    command.remove('--enforce-eager')
    command[command.index('--compilation-config') + 1] = GRAPH
    del command[command.index('--worker-cls'):]
    command.append('--cudagraph-metrics')
    env = w.build_environment(p, output)
    shared, local = str(output / 'scratch'), str(scratch_dir(output))
    for key, value in env.items():
        if value == shared or value.startswith(shared + '/'):
            env[key] = local + value[len(shared):]
    w.require(not any(shared in value for value in env.values()), 'scratch path left on output mount')
    env['VLLM_XPU_ENABLE_XPU_GRAPH'] = '1'
    env['OMP_NUM_THREADS'] = '1'
    env.update(HOME='/home/steve', USER='steve', LOGNAME='steve', LANG='C.UTF-8')
    env['PATH'] = '/opt/intel/oneapi/compiler/2025.3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
    env['TORCH_TRACE'] = str(output / 'torch-trace')
    if arm == 'candidate':
        env['Q38_M2_GLUE_ROW_COPY'] = '1'
        env['A367_GLUE_OPERATOR_RECEIPTS'] = str(output / 'operator')
        env['PYTHONPATH'] = str(HERE) + ':' + env['PYTHONPATH']
        command[2] = str(HERE / 'glue_entry.py')
    return command, env


def verify_seals():
    p = w.verify_repo(scope='calibration')
    for relative, digest in w.read(SEAL)['files'].items():
        w.require(w.sha(w.REPO / relative) == digest, 'glue01 seal mismatch: ' + relative)
    members = {k: v for k, v in p['calibration_repo_pins'].items() if k.startswith('patches/')}
    w.require(len(members) == p['patch_seal_members'] == 75, '75-member seal required')
    for relative, digest in p['calibration_repo_pins'].items():
        w.require(w.sha(w.REPO / relative) == digest, 'A367 seal mismatch: ' + relative)
    return p


def fault_paths(output):
    return w.fault_paths(output)


def glue_approval_text(floor=114_840_824):
    return (f'I authorize the A367 glue01 row-copy screen on steve-b70s: one control then one candidate, '
            f'each once on a fresh server, with a MemAvailable start floor of {floor} KiB, '
            f'a 0.5-second watchdog and the 12000000 KiB live reserve, under preregistration SHA256 '
            f'{w.sha(REG)} and seal SHA256 {w.sha(SEAL)}. The coordinator records this approval under '
            'the owner standing instruction. Each arm requires its own fresh health receipt, owner window '
            'and 305-second gap. This accepts unmeasured generation-memory risk, does not lower the '
            'packet-4 fixture floor and permits only the single hash-bound resolved fault.')


def glue_floor(owner):
    exception = owner.get('glue_memory_exception')
    w.require(type(exception) is dict and set(exception) ==
              {'approved', 'approved_by', 'minimum_mem_available_kib', 'owner_approval_text'},
              'glue exception fields required; default refuses')
    w.require(exception['minimum_mem_available_kib'] == 114_840_824
              and type(exception['minimum_mem_available_kib']) is int, 'glue floor must be 114840824 KiB')
    w.require(exception['approved'] is True and exception['approved_by'] == 'owner'
              and exception['owner_approval_text'] == glue_approval_text(), 'exact approval required')
    return 114_840_824


def verify_admission(owner, health, boot, now, output, rows, faults, available_kib,
                     arm='control', kernel_log=None):
    from resolved_fault import validate_resolution, journal
    resolution = validate_resolution(owner, health, boot, journal() if kernel_log is None else kernel_log)
    # Only the already-validated historical count is adapted for the immutable driver.
    # Its hash binding still checks the unmodified original health receipt on disk.
    checked_health = dict(health, fault_lines_earlier_this_boot=0)
    latch = w.verify_admission(owner, checked_health, boot, now, output, rows, faults)
    w.require(owner.get('purpose') == 'a367-glue01-screen', 'glue purpose absent')
    w.require(owner.get('glue_arm') == arm and arm in ARMS, 'glue arm binding')
    w.require(owner.get('glue_preregistration_sha256') == w.sha(REG), 'glue preregistration pin')
    w.require(owner.get('glue_seal_sha256') == w.sha(SEAL), 'glue seal pin')
    w.require(owner.get('admission_revision_sha256') is None, 'fixture revision not glue admission')
    w.require(available_kib >= glue_floor(owner), 'glue admission floor not met')
    verify_campaign(owner, arm)
    return dict(latch, resolved_fault=resolution)


def verify_campaign(owner, arm):
    """Two fixed unique arms; an exclusive claim is consumed before any server launch."""
    campaign = Path(owner['campaign_path'])
    w.require(campaign.is_absolute() and campaign.resolve() == campaign, 'absolute campaign path required')
    w.require(w.sha(campaign) == owner['campaign_sha256'], 'campaign pin')
    plan = w.read(campaign)
    w.require(plan['preregistration_sha256'] == w.sha(REG) and plan['seal_sha256'] == w.sha(SEAL), 'campaign identity')
    w.require(set(plan['arms']) == set(ARMS) and len(set(plan['arms'].values())) == 2, 'two unique arms required')
    w.require(plan['arms'][arm] == owner['output'], 'campaign output binding')
    w.require(not (claim_directory() / (arm + '.claimed.json')).exists(), 'arm already consumed; no retry')
    if arm == 'candidate':
        control = Path(plan['arms']['control'])
        result = w.read(control / 'glue01-run.json')
        identity = w.read(control / 'identity.json')
        w.require(result.get('passed') is True and result.get('mock') is False
                  and result.get('clean_exit') is True and result.get('gap_complete') is True
                  and result.get('all_owners_gone') is True, 'control did not qualify')
        w.require(result['identity_sha256'] == w.sha(control / 'identity.json'), 'control identity hash')
        w.require(identity['arm'] == 'control' and identity['seal_sha256'] == w.sha(SEAL)
                  and identity['preregistration_sha256'] == w.sha(REG), 'control identity binding')
        w.require(identity['campaign_sha256'] == owner['campaign_sha256'], 'control campaign binding')
        stop = w.read(control / 'stop.json')
        w.require(result['stop_sha256'] == w.sha(control / 'stop.json'), 'control stop hash')
        w.require(owner['previous_teardown_completed_unix'] == stop['completed_unix'], 'candidate stop gap binding')
        health = w.read(owner['health_path'])
        w.require(w.timestamp(health['start_utc']) >= stop['completed_unix'] + GAP, 'candidate requires fresh health after control gap')
        w.require(owner['health_sha256'] != w.read(control / 'owner-window.json')['health_sha256'], 'candidate needs new health receipt')
        from compare import check_arm
        check_arm(control, 'control')
    return campaign


def claim_directory():
    return w.REPO / 'data/2026-10-17-flash-next-a367-glue01-build/launch-claims' / w.sha(SEAL)


def claim_arm(owner, arm):
    campaign = verify_campaign(owner, arm)
    claim_directory().mkdir(parents=True, exist_ok=True)
    with (claim_directory() / (arm + '.claimed.json')).open('x') as stream:
        json.dump({'arm': arm, 'output': owner['output'], 'unix': time.time(),
                   'campaign_sha256': owner['campaign_sha256']}, stream)


def verify_export():
    from build_export import manifest, CLEAN, CANDIDATE, CHANGED
    export = w.read(HERE / 'source-export.json')
    candidate = manifest(CANDIDATE)
    w.require(candidate == export['candidate_files'], 'candidate export changed')
    clean_expected = dict(candidate)
    clean_expected[CHANGED] = {'sha256': export['changed_files'][CHANGED]['before']}
    w.require(manifest(CLEAN) == clean_expected, 'clean export changed')
    return {'files': len(candidate), 'changed_files': export['changed_files'], 'passed': True}


def source_preregistration(prereg, arm):
    import copy
    p = copy.deepcopy(prereg)
    if arm == 'candidate':
        export = w.read(HERE / 'source-export.json')
        w.require(len(export['changed_files']) == 1, 'single source delta required')
        for relative, delta in export['changed_files'].items():
            w.require(p['source_pins'][relative] == delta['before'], 'candidate base pin')
            p['source_pins'][relative] = delta['after']
    return p


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


# Rank identity per (proc root, pid). /proc/<pid>/cmdline takes the target's mmap lock, so a
# worker stalled in a FUSE page fault blocked the 0.5 s sample for 1.74 s (replay b, 22:24 UTC).
# comm/status/cgroup do not take that lock; cmdline is read only until a worker's rank is known.
_RANK_CACHE = {}
WORKER_COMM = re.compile(r'Worker|VllmWorker', re.I)


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
    return row


def attribution(pid=None, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup')):
    # Timestamp START of scan: blocked reads cannot make old data look fresh.
    row = {'attribution_monotonic': time.monotonic(), 'attribution_unix': time.time(),
           'ranks': {str(i): None for i in range(4)}, 'cgroups': []}
    if pid is None:
        return row
    cg_paths = set()
    for entry in proc.glob('[0-9]*'):
        try:
            if os.getsid(int(entry.name)) != pid:
                continue
            comm = (entry / 'comm').read_text()
            key = (str(proc), int(entry.name))
            rank = _RANK_CACHE.get(key) if WORKER_COMM.search(comm) else None
            if rank is None and WORKER_COMM.search(comm):
                label = comm + ' ' + (entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
                match = re.search(r'(?:Worker[_-]TP|VllmWorker[-_])([0-3])(?=$|[^0-9])', label, re.I)
                if match:
                    rank = _RANK_CACHE[key] = match[1]
            if rank is not None:
                w.require(row['ranks'][rank] is None, 'ambiguous rank PID attribution')
                status = meminfo_status((entry / 'status').read_text())
                row['ranks'][rank] = {'pid': int(entry.name), 'rss_bytes': status.get('VmRSS'),
                                      'source': str(entry / 'status')}
            for line in (entry / 'cgroup').read_text().splitlines():
                if line.startswith('0::'):
                    cg_paths.add(line[3:])
        except (FileNotFoundError, ProcessLookupError):
            continue  # host process exited during the scan (getsid ESRCH, /proc ENOENT)
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
    order = {'baseline': 0, 'loading': 1, 'plateau': 2, 'client_wait': 3, 'generation': 4, 'shutdown': 5}
    w.require(all(p in order for p in phases) and all(order[a] <= order[b] for a, b in zip(phases, phases[1:])), 'phase order')
    plateau = [r for r in rows if r['phase'] == 'plateau']
    w.require(plateau and plateau[-1]['monotonic'] - plateau[0]['monotonic'] >= PLATEAU, 'incomplete 20s plateau')
    w.require('loading' in phases and phases[-1] == 'shutdown', 'incomplete phase coverage')
    for row in plateau:
        validate_attribution(row)
    minimum = min(r['mem_available_bytes'] for r in rows)
    decline = max(0, rows[0]['mem_available_bytes'] - minimum)
    return {'baseline_available_bytes': rows[0]['mem_available_bytes'],
            'minimum_available_bytes': minimum, 'observed_need_bytes': decline,
            'observed_need_kib': (decline + 1023) // 1024,
            'max_sample_gap_seconds': max(gaps), 'sample_count': len(rows),
            'phase_min_available_bytes': {p: min(r['mem_available_bytes'] for r in rows if r['phase'] == p)
                                          for p in set(phases)},
            'scope': 'sampled startup/ready/generation/shutdown need; fixture demand unmeasured'}


def validate_attribution(row):
    age = row['monotonic'] - row.get('attribution_monotonic', float('-inf'))
    w.require(0 <= age <= 2, 'plateau attribution older than 2s or invalid')
    w.require(not row.get('attribution_error'), 'plateau attribution failed')

    w.require(set(row['ranks']) == {'0', '1', '2', '3'} and all(
        r is not None and type(r['rss_bytes']) is int and r['rss_bytes'] > 0
        for r in row['ranks'].values()), 'missing plateau rank RSS')
    w.require(len({r['pid'] for r in row['ranks'].values()}) == 4, 'rank PID coverage')
    w.require(row['cgroups'] and all(type(c['memory_current_bytes']) is int
              and c['memory_current_bytes'] >= 0 for c in row['cgroups']), 'missing plateau cgroup current')


class Attribution:
    """Slow /proc and cgroup work never owns the sampler lock."""
    def __init__(self, stop, done, scan=attribution):
        self.stop, self.done, self.scan = stop, done, scan
        self.latest = None
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.done.is_set():
            try:
                # Publish a completed immutable dict in one assignment. No reader lock.
                row = self.scan(self.stop.child.pid if self.stop.child else None)
                self.latest = row
                self.error = None
            except Exception as exc:
                self.error = str(exc)
            self.done.wait(INTERVAL)


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
                # A slow output mount must not postpone the one graceful signal.
                try:
                    self.child.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
                try:
                    w.write(self.root / 'stop-request.json', {'pid': self.child.pid, 'signal': 'SIGINT',
                            'unix': time.time(), 'reason': self.reason})
                except OSError as exc:
                    self.reason += f'; stop receipt write failed: {exc}'

    def attach(self, child):
        with self.lock:
            self.child = child
            if self.reason:
                self.request(self.reason)


class WriteBudget:
    """Independent file-metadata scan; never delay memory reads with RAID traversal."""
    def __init__(self, root, stop, done):
        self.root, self.stop, self.done = root, stop, done
        self.latest_bytes = 0
        self.thread = threading.Thread(target=self.run, daemon=True)

    def measure(self):
        # Account all run files, including trace buffers flushed by all ranks.
        total = 0
        if not self.root.exists():
            return 0  # The optional untraced arm creates no trace directory.
        for directory, _, files in os.walk(self.root, onerror=lambda e: (_ for _ in ()).throw(e)):
            for name in files:
                try:
                    total += (Path(directory) / name).stat().st_size
                except FileNotFoundError:
                    continue
        self.latest_bytes = total
        return total

    def take(self):
        total = self.measure()
        w.require(total < TRACE_SOFT_STOP, '6 GiB local trace soft stop; reserve for drain')
        return total

    def run(self):
        while not self.done.is_set():
            try:
                self.take()
            except Exception as exc:
                self.stop.request('output budget watcher: ' + str(exc))
            self.done.wait(1)


class Sampler:
    def __init__(self, root, stop, live_check, sample=snapshot, scan=attribution):
        self.root, self.stop, self.live_check, self.sample = root, stop, live_check, sample
        self.phase = 'baseline'
        self.rows = []
        self.failed = None
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.attribution = Attribution(stop, self.done, scan)
        self.budget = WriteBudget(trace_dir(root), stop, self.done)
        self.writer = SampleWriter(scratch_dir(root) / 'samples.jsonl')
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.live_thread = threading.Thread(target=self.run_live, daemon=True)

    def take(self):
        with self.lock:
            latest = self.attribution.latest
            row = self.sample(self.stop.child.pid if self.stop.child else None)
            if latest is not None:
                row.update(latest)
            row['attribution_error'] = self.attribution.error
            row['phase'] = self.phase
            self.rows.append(row)
            self.writer.enqueue(row)
            if row['phase'] == 'plateau':
                validate_attribution(row)
            w.require(row['mem_available_bytes'] >= LIVE_FLOOR_KIB * 1024, 'A367 live memory reserve crossed')
            if len(self.rows) > 1:
                w.require(row['monotonic'] - self.rows[-2]['monotonic'] <= 1.5, 'sampler delayed >1.5s')
        return row

    def run(self):
        due = time.monotonic() + INTERVAL
        while not self.done.wait(max(0, due - time.monotonic())):
            try:
                self.take()
            except BaseException as exc:
                self.failed = self.failed or str(exc)
                # Keep sampling shutdown even after a trip, preserving the first failure.
            due += INTERVAL
            if due < time.monotonic():
                due = time.monotonic() + INTERVAL

    def check_live(self):
        # File checks and stop receipts must never run in the timed sample thread.
        w.require(not self.failed, self.failed)
        w.require(not self.writer.failure, self.writer.failure)
        self.live_check()

    def run_live(self):
        while not self.done.is_set():
            try:
                self.check_live()
            except BaseException as exc:
                self.failed = self.failed or str(exc)
                self.stop.request('memory/admission watcher: ' + self.failed)
            self.done.wait(INTERVAL)

    def persist(self):
        self.writer.finish()
        local = self.writer.path
        # Compare the exact serialized rows before copying; scratch cleanup follows.
        expected = ''.join(json.dumps(r, allow_nan=False) + '\n' for r in self.rows).encode()
        w.require(local.read_bytes() == expected, 'local samples differ from memory rows')
        shutil.copyfile(local, self.root / 'samples.jsonl')
        digest = w.sha(local)
        w.require(w.sha(self.root / 'samples.jsonl') == digest, 'sample copy hash mismatch')
        w.write(self.root / 'samples-persistence.json', {
            'local_path': str(local), 'output_path': str(self.root / 'samples.jsonl'),
            'rows': len(self.rows), 'sha256': digest, 'equals_in_memory_rows': True})


def ready():
    # Readiness uses only these GET routes; generation is a separate, once-only phase.
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{w.PORT}/health', timeout=.4) as response:
            if response.status != 200:
                return False
        with urllib.request.urlopen(f'http://127.0.0.1:{w.PORT}/v1/models', timeout=.4) as response:
            data = json.load(response)
        return [r['id'] for r in data['data']] == ['qwen38-flash-next-fp8-tp4']
    except (urllib.error.URLError, TimeoutError):
        return False


REPRO = w.REPO / 'repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913'
CLIENT_BUDGET = 2700
CLIENT_CORES = '4-15,20-31'
RESULT = 'realistic-suite-v1-result.json'
EXTRA = '{"chat_template_kwargs":{"enable_thinking":false},"seed":20260609,"temperature":0,"top_p":1.0}'


def online_cpus():
    result = set()
    for part in Path('/sys/devices/system/cpu/online').read_text().strip().split(','):
        bounds = [int(x) for x in part.split('-')]
        result.update(range(bounds[0], bounds[-1] + 1))
    return result


def verify_process_profile():
    # A nice19 parent cannot restore nice0 without privileges. Start the future
    # durable unit at nice0/unrestricted, never silently inherit calibration limits.
    w.require(os.getpriority(os.PRIO_PROCESS, 0) == 0, 'execute requires normal priority (nice0)')
    w.require(os.sched_getaffinity(0) == online_cpus(), 'execute requires unrestricted online CPU affinity')


def verify_scratch_filesystem():
    result = subprocess.run(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(LOCAL_SCRATCH)],
                            capture_output=True, text=True, check=True)
    w.require(result.stdout.strip() == 'ext4', 'local scratch must be ext4')


def client_command(root, arm='control'):
    return ['taskset', '-c', CLIENT_CORES, '/usr/bin/python3', '-B',
            str(HERE / 'battery_client.py'), '--output', str(root), '--arm', arm,
            '--base-url', f'http://127.0.0.1:{w.PORT}']


def client_environment():
    return {'HOME': '/home/steve', 'USER': 'steve', 'LOGNAME': 'steve', 'LANG': 'C.UTF-8',
            'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            'PYTHONDONTWRITEBYTECODE': '1'}


def client_phase(root, sampler, stop, watch, server, *, clock=time.monotonic,
                 sleep=time.sleep, launch=subprocess.Popen, clients=None, arm='control'):
    def live():
        w.require(not stop.reason and not sampler.failed and not watch.failed,
                  stop.reason or sampler.failed or watch.failed)
        w.require(server.poll() is None, 'server exited during client phase')
    sampler.phase = 'client_wait'
    # Preserve the record's full 30s sleep, after the separate 20s plateau.
    until = clock() + 30
    while clock() < until:
        live()
        sleep(min(INTERVAL, until - clock()))
    live()
    w.require(not (root / RESULT).exists(), 'refusing to overwrite suite result')
    if arm == 'candidate':
        from operator_gate import validate_receipts
        validate_receipts(root / 'operator')
    sampler.phase = 'generation'
    receipt = {'attempted': True, 'launches': 1, 'returncode': None,
               'command': client_command(root, arm), 'budget_seconds': CLIENT_BUDGET}
    w.write(root / 'client.json', receipt)
    child = None
    try:
        with (root / 'client.log').open('xb') as log:
            child = launch(receipt['command'], env=client_environment(), cwd=w.REPO,
                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            if clients is not None:
                clients.append(child)
            receipt['pid'] = child.pid
            deadline = clock() + CLIENT_BUDGET
            while child.poll() is None:
                try:
                    live()
                    w.require(clock() < deadline, '2700s client wall budget exceeded')
                except BaseException as exc:
                    # Latch and SIGINT server once. Never kill/retry client or server.
                    receipt.setdefault('failure', str(exc))
                    stop.request('client watchdog: ' + str(exc))
                    break  # teardown proceeds while the CPU client drains; never kill it
                sleep(INTERVAL)
            receipt['returncode'] = child.returncode
    finally:
        w.write(root / 'client.json', receipt)
    return receipt


def compare_result(root):
    from compare import check_arm
    identity = w.read(root / 'identity.json')
    comparison = check_arm(root, identity['arm'])
    w.write(root / 'comparison.json', comparison)
    return comparison


def lifecycle(root, command, env, sampler, stop, watch, *, launch=subprocess.Popen,
              is_ready=ready, clock=time.monotonic, sleep=time.sleep,
              owners_gone=w.owned_session_gone, process_rows=w.processes, mock=False,
              run_client=None, check_result=None):
    """Injectable control plane for CPU mocks. No test-only CLI launch bypass."""
    error = None
    reached_ready = clean_exit = gap_complete = False
    child = None
    clients = []
    comparison = None
    client_receipt = {'attempted': False}
    all_owners_gone = False
    run_client = run_client or client_phase
    check_result = check_result or compare_result
    try:
        sampler.writer.start()
        sampler.take()  # baseline is committed before Popen
        sampler.phase = 'loading'
        sampler.budget.thread.start()
        sampler.attribution.thread.start()
        sampler.thread.start()
        sampler.live_thread.start()
        watch.poll()
        watch.thread.start()
        w.require(not stop.reason and not sampler.failed and not watch.failed, 'prelaunch monitor failure')
        with (root / 'server.log').open('xb') as log:
            child = launch(command, env=env, cwd=root, stdout=log,
                           stderr=subprocess.STDOUT, start_new_session=True)
            stop.attach(child)
            w.write(root / 'launch.json', {'pid': child.pid, 'unix': time.time()})
            deadline = clock() + LOAD_BUDGET
            plateau_start = None
            while True:
                w.require(not stop.reason, str(stop.reason))
                w.require(not sampler.failed, 'memory sampler failed: ' + str(sampler.failed))
                w.require(not sampler.writer.failure, 'sample writer failed: ' + str(sampler.writer.failure))
                w.require(not watch.failed, 'kernel watcher failed: ' + str(watch.failed))
                w.require(child.poll() is None, 'server exited before plateau completed')
                w.require(clock() < deadline, f'{LOAD_BUDGET}s loading/plateau budget exceeded')
                if plateau_start is None and is_ready():
                    reached_ready = True
                    sampler.phase = 'plateau'
                    plateau_start = clock()
                plateau_rows = [r for r in sampler.rows if r['phase'] == 'plateau']
                if plateau_rows and plateau_rows[-1]['monotonic'] - plateau_rows[0]['monotonic'] >= PLATEAU:
                    break
                sleep(INTERVAL)
            client_receipt = run_client(root, sampler, stop, watch, child,
                                        clock=clock, sleep=sleep, clients=clients)
            w.require(client_receipt['returncode'] == 0 and not stop.reason,
                      'client failed or stop latched')
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        sampler.phase = 'shutdown'
        stop.request(error or 'record suite complete; one client attempt')
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
            all_owners_gone = True
            # Always observe the full post-exit gap, including failed client/monitor runs.
            try:
                sampler.take()
                watch.poll()
                w.require(not w.conflicts(process_rows()), 'native conflict after exit')
                clean_exit = child.returncode == 0
                w.require(not overrun, 'unclean server/session teardown')
                w.require(clean_exit, 'unclean server/session teardown')
            except BaseException as exc:
                error = error or str(exc)
            completed = time.time()
            w.write(root / 'stop.json', {'all_owners_gone': True, 'returncode': child.returncode,
                    'completed_unix': completed, 'next_launch_not_before_unix': completed + GAP})
            sampler.done.set()
            if sampler.thread.ident is not None:
                sampler.thread.join(5)
            until = clock() + GAP
            while clock() < until:
                if watch.failed or sampler.failed:
                    error = error or watch.failed or sampler.failed
                sleep(min(INTERVAL, until - clock()))
            try:
                watch.poll()
                w.require(not watch.failed, 'fault during 305s gap')
                gap_complete = True
            except BaseException as exc:
                error = error or str(exc)
            # CPU clients receive no signals. A stalled client cannot delay GPU teardown
            # or its post-exit watch; keep ownership/lock until it drains or owner recovery.
            for client in clients:
                if client.poll() is None:
                    error = error or 'client still running after server exit/watch; manual recovery required'
                    w.write(root / 'client-incomplete.json', {'pid': client.pid, 'reason': error})
                while client.poll() is None:
                    sleep(INTERVAL)
        sampler.done.set()
        watch.stop.set()
        for thread in (sampler.thread, sampler.live_thread, sampler.attribution.thread, sampler.budget.thread, watch.thread):
            if thread.ident is not None:
                thread.join(5)
            if thread.is_alive():
                error = error or 'monitor did not stop'
        persisted = False
        try:
            sampler.persist()
            persisted = True
        except Exception as exc:
            error = error or 'sample persistence: ' + str(exc)
        if persisted and (child is None or (child.poll() is not None and owners_gone(child.pid))):
            shutil.rmtree(scratch_dir(root))
        else:
            w.write(root / 'scratch-retained.json', {'reason': 'owner uncertain; no cleanup',
                                                    'path': str(scratch_dir(root))})
    if watch.failed or sampler.failed:
        error = error or watch.failed or sampler.failed
    summary = None
    try:
        w.require(stop.reason == 'record suite complete; one client attempt', stop.reason or 'missing completion stop')
        w.require(error is None and reached_ready and all_owners_gone and gap_complete, error or 'incomplete lifecycle')
        summary = summarize(sampler.rows)
    except (ValueError, KeyError) as exc:
        error = error or str(exc)
    # The frozen checker runs only after every server owner and the watch have finished.
    if child is not None and child.poll() is not None and owners_gone(child.pid):
        try:
            comparison = check_result(root)
            w.require(comparison['exact'], 'record output/battery/operator gate mismatch')
        except Exception as exc:
            error = error or f'glue01 comparison: {exc}'
    if (root / 'client.json').exists():
        client_receipt = w.read(root / 'client.json')
    try:
        size = sampler.budget.measure()
        w.write(root / 'write-budget.json', {'bytes_after_owners_and_client_exit': size, 'limit_bytes': 10 * 2**30,
                                          'passed': size <= 10 * 2**30, 'soft_stop_bytes': TRACE_SOFT_STOP,
                                          'measured_directory': str(trace_dir(root))})
        w.require(size <= 10 * 2**30, '10 GiB write budget exceeded after trace drain')
    except Exception as exc:
        error = error or str(exc)
    receipt = {'schema': 'own-xpu-runtime.packet4.a367-glue01.v1', 'passed': error is None,
               'ready': reached_ready, 'clean_exit': clean_exit, 'gap_complete': gap_complete,
               'all_owners_gone': all_owners_gone, 'gpu_fault_lines': 0 if gap_complete and not watch.failed else None,
               'client': client_receipt, 'comparison': comparison, 'failure': error, 'summary': summary,
               'samples_sha256': w.sha(root / 'samples.jsonl') if (root / 'samples.jsonl').exists() else None,
               'identity_sha256': w.sha(root / 'identity.json'), 'mock': mock,
               'stop_sha256': w.sha(root / 'stop.json') if (root / 'stop.json').exists() else None}
    w.write(root / 'glue01-run.json', receipt)
    return 0 if receipt['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=ARMS, required=True)
    for option in ('owner-window', 'health-receipt', 'payload-receipt'):
        parser.add_argument('--' + option, type=Path)
    args = parser.parse_args(argv)
    root = args.output.absolute()
    command, env = command_and_environment(root, args.arm)
    # vLLM binds ipc://<VLLM_RPC_BASE_PATH>/<36-char uuid>; Unix socket paths cap at 107 chars.
    w.require(len(env['VLLM_RPC_BASE_PATH']) + 37 <= RPC_PATH_MAX, 'scratch path too long for vLLM ipc sockets')
    if args.plan:
        print(json.dumps({'command': command, 'environment': env, 'deltas': w.read(REG)['identity_deltas'],
                          'native_executed': False, 'arm': args.arm, 'client_command': client_command(root, args.arm),
                          'execute_profile': 'normal priority, unrestricted online CPUs; client pinned only'}, indent=2))
        return 0
    w.require(all((args.owner_window, args.health_receipt, args.payload_receipt)), 'owner/health/payload required')
    verify_process_profile()
    with (HERE.parent / 'extraction-window.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        owner, health = w.read(args.owner_window), w.read(args.health_receipt)
        owner_hash = w.sha(args.owner_window)
        def admit():
            w.require(w.sha(args.owner_window) == owner_hash, 'owner flag changed')
            w.require(Path(owner['health_path']).resolve() == args.health_receipt.resolve(), 'health path differs')
            return verify_admission(owner, health, boot, time.time(), root, w.processes(), fault_paths(root),
                             snapshot()['mem_available_bytes'] // 1024, args.arm)
        initial_admission = admit()
        prereg = verify_seals()
        audit = {'exports': verify_export()}
        w.verify_environment(paths(args.arm), source_preregistration(prereg, args.arm), audit, calibration=True)
        stage = paths()['stage'] / 'vllm_xpu_kernels'
        expected_members = {line.split(maxsplit=1)[1].strip().lstrip('*') for line in
                            (w.LANE / 'data/runtime-stage-gdn-roundstate-v2-loadable.sha256').read_text().splitlines()}
        actual_members = {str(p.relative_to(stage)) for p in stage.rglob('*')
                          if p.is_file() and p.suffix in ('.py', '.so')}
        w.require(actual_members == expected_members, 'A367 stage loadable file set changed')
        w.verify_calibration_payload(args.payload_receipt, owner, paths()['model'], prereg, time.time())
        w.require(shutil.disk_usage(root.parent).free >= max(prereg['minimum_disk_free_bytes'], 60 * 2**30) + 10 * 2**30, 'disk reserve plus planned writes')
        LOCAL_SCRATCH.mkdir(parents=True, exist_ok=True)
        verify_scratch_filesystem()
        w.require(shutil.disk_usage(LOCAL_SCRATCH).free >= LOCAL_SCRATCH_MIN_FREE, 'local scratch reserve')
        w.require(not scratch_dir(root).exists(), 'local scratch already exists')
        with socket.socket() as port:
            port.bind(('127.0.0.1', w.PORT))
        from resolved_fault import journal, validate_resolution, ResolvedWatch
        baseline = journal()
        validate_resolution(owner, health, boot, baseline)
        final_admission = admit()  # repeat freshness/owners/floor after byte audit
        w.verify_calibration_payload(args.payload_receipt, owner, paths()['model'], prereg, time.time())
        claim_arm(owner, args.arm)
        root.mkdir()
        (scratch_dir(root) / 'rpc').mkdir(parents=True)
        w.write(root / 'admission.json', {'initial': initial_admission, 'final': final_admission})
        audit['fault_latch_admission'] = w.artifact(root / 'admission.json')
        audit['passed'] = True  # verify_environment raises on failure; explicit aggregate fixes derive_floor schema bug.
        w.write(root / 'environment.json', audit)
        (root / 'kernel-before.log').write_text(baseline)
        for name, source in [('owner-window.json', args.owner_window), ('health.json', args.health_receipt), ('payload.json', args.payload_receipt)]:
            shutil.copyfile(source, root / name)
        w.write(root / 'identity.json', {'schema': 'own-xpu-runtime.packet4.a367-glue01-identity.v1',
            'mock': False, 'recipe': 'A367', 'arm': args.arm, 'campaign_sha256': owner['campaign_sha256'], 'host': socket.gethostname(), 'boot_id': boot,
            'kernel': health['kernel'], 'firmware': owner['firmware'], 'pci_ids': owner['pci_ids'],
            'preregistration_sha256': w.sha(REG), 'seal_sha256': w.sha(SEAL),
            'environment': env, 'command': command,
            'nice': os.getpriority(os.PRIO_PROCESS, 0), 'affinity': sorted(os.sched_getaffinity(0)),
            'client_command': client_command(root, args.arm), 'audit_sha256': w.sha(root / 'environment.json'),
            'owner_sha256': owner_hash, 'payload_sha256': w.sha(args.payload_receipt),
            'identity_deltas': w.read(REG)['identity_deltas'],
            'glue_memory_exception': owner.get('glue_memory_exception'),
            'minimum_mem_available_kib': glue_floor(owner)})
        stop = Stop(root)
        watch = ResolvedWatch(root, baseline, boot, owner, health)
        def live_check():
            w.require(w.sha(args.owner_window) == owner_hash and time.time() < owner['expires_unix'], 'owner revoked/expired')
            w.require(not watch.failed, 'kernel watcher failed')
            w.require(not (root / 'STOP.json').exists(), 'STOP latch')
            w.require(not any((p / 'FAULT.json').exists() for p in (*w.FAULT_ROOTS, root)), 'FAULT latch')
        sampler = Sampler(root, stop, live_check)
        old = {s: signal.signal(s, lambda *_: stop.request('coordinator interrupted')) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            return lifecycle(root, command, env, sampler, stop, watch,
                run_client=lambda *a, **kw: client_phase(*a, **kw, arm=args.arm))
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        sys.exit(2)
