#!/usr/bin/env python3
"""Bounded Screen 1b controller. Default is a no-network, no-GPU dry run.

prepare --execute pulls only after admission; run --execute starts one server.
No automatic retry, restart, hard kill, settings changes, or installations.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import threading

import calibration

from memory_watchdog import MemoryWatchdog, sample_memory, trip_reason
from memory_plan import (build_prediction, format_table, enforce_prediction,
                         collect_observations, paired_observations)
from apply_overlay import verify_package
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PLAN = json.loads((HERE / 'image-plan.json').read_text())
OVERLAY = json.loads((HERE / 'overlay-manifest.json').read_text())
MODEL = Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
# Mirrored from local LTX packet 115 launch/serve-encoder.py: journal
# classification and complete four-card probe evidence, with Screen's legacy
# engine-reset/timeout spellings retained. No runtime dependency on that packet.
FAULT = re.compile(
    r'Fault response|CAT error|engine.*reset|reset.*engine|GPU HANG|GuC.*reset|coredump|timed.?out job|job[^\n]*timed\s*out|wedged|'
    r'\bBUG:[ \t]+soft lockup[ \t]+-[ \t]+CPU#\d+[ \t]+stuck for[ \t]+\d+(?:\.\d+)?s!|'
    r'\bINFO:[ \t]+rcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+(?:self-)?detected[ \t]+(?:expedited[ \t]+)?stalls?[ \t]+on[ \t]+(?:CPUs?(?:/tasks)?|tasks)\b|'
    r'\brcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+kthread starved for[ \t]+\d+[ \t]+jiffies\b|'
    r'\bINFO:[ \t]+task[ \t]+[^\r\n]+:\d+[ \t]+blocked for more than[ \t]+\d+(?:\.\d+)?[ \t]+seconds\.'
    , re.I)

# Match LTX's known xe GuC stall tolerance; GPU faults always latch.
# Only a hard-lockup trace naming xe_guc_irq_handler/g2h_read can explain
# a following HOST_STALL within 180 seconds. Full journals retain the evidence.
GPU_FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|GPU HANG|GuC.*reset|coredump|timed.?out job|job[^\n]*timed\s*out|wedged',
                       re.I)
# Packet115: the driver deleting an earlier devcoredump is cleanup, not a fault (the 114 false latch of
# 2026-10-08 15:06:16 UTC). Creation lines and the devcoredump trace still latch.
COREDUMP_DELETED = re.compile(r'coredump has been deleted', re.I)
HOST_STALL = re.compile(FAULT.pattern.split('wedged|', 1)[1], re.I)
STALL_FOLLOWER = re.compile(HOST_STALL.pattern + r'|\bclocksource: Long readout', re.I)
HARD_LOCKUP = re.compile(r'hard LOCKUP on cpu', re.I)
XE_STALL_TRACE = re.compile(r'\bxe_guc_irq_handler\b|\bg2h_read\b')
STALL_WINDOW_S = 180
STALL_LEAD_S = 10        # the watchdog reports a hard lockup after about 10 s of it
_TS_UNIX = re.compile(r'^(\d{9,11}\.\d+)\s')
_TS_ISO = re.compile(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?[+-]\d\d:?\d\d)\s')
_TS_CLASSIC = re.compile(r'^([A-Z][a-z]{2} [ \d]\d \d\d:\d\d:\d\d)\s')


def line_time(line, year=None):
    """Unix time of a journal line (short-unix, ISO or classic short format), or None."""
    m = _TS_UNIX.match(line)
    if m:
        return float(m.group(1))
    m = _TS_ISO.match(line)
    if m:
        return datetime.datetime.fromisoformat(m.group(1)).timestamp()
    m = _TS_CLASSIC.match(line)
    if m:
        year = year or datetime.datetime.now().year
        return datetime.datetime.strptime('%d %s' % (year, m.group(1)), '%Y %b %d %H:%M:%S').timestamp()
    return None


def classify_journal(journal, year=None):
    """Split a kernel journal into GPU faults, unexplained host stalls (both latch) and
    known xe GuC stall events (tolerated, retained in journal snapshots)."""
    rows, last = [], None
    for line in journal.splitlines():
        t = line_time(line, year)
        last = t if t is not None else last
        rows.append((last, line))
    events = []
    for i, (t, line) in enumerate(rows):
        if t is None or not HARD_LOCKUP.search(line):
            continue
        second = int(t)
        trace = [l for tt, l in rows[i + 1:i + 200] if tt is not None and int(tt) == second and XE_STALL_TRACE.search(l)]
        if trace:
            events.append({'start_unix': t, 'end_unix': t, 'anchor': line, 'trace': trace[0], 'lines': [line]})
    gpu, unexplained = [], []
    for t, line in rows:
        if GPU_FAULT.search(line) and not COREDUMP_DELETED.search(line):
            gpu.append(line)
            continue
        if HOST_STALL.search(line) or STALL_FOLLOWER.search(line):
            owner = next((e for e in events if t is not None and e['start_unix'] <= t <= e['start_unix'] + STALL_WINDOW_S),
                         None)
            if owner is not None:
                owner['lines'].append(line)
                owner['end_unix'] = max(owner['end_unix'], t)
            elif HOST_STALL.search(line):
                unexplained.append(line)
    for e in events:
        e['window_unix'] = [e['start_unix'] - STALL_LEAD_S, e['end_unix']]
        e['duration_s'] = round(e['end_unix'] - e['start_unix'] + STALL_LEAD_S, 1)
    return {'gpu_faults': gpu, 'unexplained_host': unexplained, 'stalls': events,
            'latch': bool(gpu or unexplained)}


HEALTH_SCHEMA = 'ltx.four-card-health.v1'
HEALTH_MAX_AGE = datetime.timedelta(hours=6)
# The probe's own pass thresholds (scripts/check-four-card-health.py).
HEALTH_FP32_MAX_ERR = 1e-2
HEALTH_BF16_MAX_ERR = 5.0
HEALTH_DEVICES = ('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3')


def parse_utc(text):
    return datetime.datetime.strptime(text, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=datetime.timezone.utc)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < float("inf")


def verify_health_receipt(receipt, boot_id, now):
    """Return the receipt's end time if it admits a same-boot start, else raise.

    Requires the complete evidence check-four-card-health.py writes, re-checked
    against that probe's own thresholds; a bare {"pass": true} is not evidence."""
    req = require
    req(isinstance(receipt, dict) and receipt.get('schema') == HEALTH_SCHEMA,
        'Health receipt schema is not ' + HEALTH_SCHEMA)
    req(receipt.get('passed') is True, 'Health receipt did not pass')
    for key in ('kernel', 'torch', 'boot_id', 'start_utc', 'end_utc'):
        req(isinstance(receipt.get(key), str) and receipt[key].strip(), 'Health receipt lacks ' + key)
    req(receipt.get('boot_id') == boot_id, 'Health receipt is from another boot')
    req('journal_fault_lines_during_probe' in receipt and receipt['journal_fault_lines_during_probe'] == [],
        'Health receipt saw fault lines during its own probe, or lacks that evidence')
    cards = receipt.get('cards')
    req(receipt.get('device_count') == 4 and isinstance(cards, list) and len(cards) == 4,
        'Health receipt does not show four passing cards')
    req([c.get('device') if isinstance(c, dict) else None for c in cards] == list(HEALTH_DEVICES),
        'Health receipt does not show four passing cards (devices xpu:0..3 in order)')
    for i, c in enumerate(cards):
        ok = (isinstance(c.get('name'), str) and c['name'].strip() and c.get('pass') is True and
              'error' not in c and c.get('copy_roundtrip_exact') is True and c.get('gemm_repeat_exact') is True and
              _number(c.get('gemm_fp32_max_abs_err')) and c['gemm_fp32_max_abs_err'] < HEALTH_FP32_MAX_ERR and
              _number(c.get('gemm_bf16_max_abs_err')) and c['gemm_bf16_max_abs_err'] < HEALTH_BF16_MAX_ERR and
              (i == 0 or c.get('staged_from_previous_exact') is True))
        req(ok, 'Health receipt does not show four passing cards (card %d evidence missing or out of bounds)' % i)
    try:
        start, end = parse_utc(receipt['start_utc']), parse_utc(receipt['end_utc'])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError('Health receipt has no readable start_utc/end_utc')
    req(start <= end, 'Health receipt ends before it starts')
    req(end <= now, 'Health receipt end_utc is in the future')
    req(now - end < HEALTH_MAX_AGE, 'Health receipt is 6 hours old or older')
    return end


GIB = 2**30


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def fault_incidents(lines):
    """Cluster GPU fault lines by adjacent gaps of at most 60 seconds."""
    times = [line_time(line) for line in lines]
    require(all(t is not None for t in times),
            'Cannot timestamp GPU fault evidence; no launch')
    times.sort()
    return int(bool(times)) + sum(b - a > 60 for a, b in zip(times, times[1:]))


def new_fault_lines(whole_boot, cutoff):
    # Classify the whole journal first: known host-stall trace context may
    # precede the cutoff. Never let that tolerance suppress a GPU fault.
    verdict = classify_journal(whole_boot)
    lines = verdict['gpu_faults'] + verdict['unexplained_host']
    later = []
    for line in lines:
        timestamp = line_time(line)
        require(timestamp is not None, 'Cannot timestamp fault evidence; no launch')
        # Receipt timestamps have one-second precision. Include the boundary
        # second, just as LTX's journalctl --since does: only OLDER lines qualify.
        if timestamp >= cutoff:
            later.append(line)
    return later


def admit_journal(whole_boot, receipt=None, *, boot_id=None, now=None):
    """Validate recovery and return (admitted lines, monitoring cutoff)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    verdict = classify_journal(whole_boot)
    incidents = fault_incidents(verdict['gpu_faults'])
    require(incidents < 2,
            f'{incidents} GPU fault incidents this boot; owner must decide (reboot). No launch')
    lines = verdict['gpu_faults'] + verdict['unexplained_host']
    require(not lines or receipt is not None,
            'Fault signature in this boot; --health-receipt PATH required after one bounded '
            'four-card health probe; no launch')
    cutoff = (verify_health_receipt(receipt, boot_id, now).timestamp()
              if receipt is not None else now.timestamp())
    later = new_fault_lines(whole_boot, cutoff)
    require(not later, 'Kernel device or host fault after the health receipt: ' +
            (later[:1] or [''])[0][:200])
    return lines, cutoff


def journal_admission(args):
    # Take the clean-boot cutoff BEFORE reading the journal, so there is no
    # unmonitored gap between admission and server startup.
    now = datetime.datetime.now(datetime.timezone.utc)
    receipt_path = getattr(args, 'health_receipt', None)
    receipt, receipt_bytes = None, None
    if receipt_path is not None:
        try:
            receipt_bytes = Path(receipt_path).read_bytes()
            receipt = json.loads(receipt_bytes)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f'Cannot read health receipt: {exc}') from exc
        require(isinstance(receipt, dict), 'Health receipt must be a JSON object')
    whole_boot = journal()
    admitted, cutoff = admit_journal(
        whole_boot, receipt, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), now=now)
    run = getattr(args, 'run_dir', None)
    if run is not None and run.is_dir():
        (run / 'kernel-preflight.log').write_text(whole_boot)
        (run / 'journal-admitted-faults.txt').write_text(''.join(line + '\n' for line in admitted))
        if receipt_bytes is not None:
            (run / 'health-receipt.json').write_bytes(receipt_bytes)
            (run / 'health-receipt.sha256').write_text(
                hashlib.sha256(receipt_bytes).hexdigest() + '  health-receipt.json\n')
    return cutoff


def call(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, text=True, **kwargs)


def show(args):
    print(shlex.join([str(x) for x in args]), flush=True)


def journal(since=None):
    args = ['journalctl', '-k', '-b', '--no-pager', '-o', 'short-iso-precise']
    if since:
        args += ['--since', since]
    p = call(args, capture_output=True)
    if 'permission' in p.stderr.lower() or 'not seeing messages' in p.stderr.lower():
        raise RuntimeError('Cannot verify the complete kernel journal without existing read access')
    if not p.stdout.strip():
        raise RuntimeError('Kernel journal unavailable/empty; no clean-log inference')
    return p.stdout


def overlay_check():
    verify_package(HERE)


SCAN_SNIPPET = r'''
import json, os, sys
from pathlib import Path
targets = set(sys.argv[1:])
held, unreadable = [], []
for proc in Path('/proc').glob('[0-9]*'):
    try:
        fds = list((proc / 'fd').iterdir())
    except FileNotFoundError:
        continue
    except PermissionError:
        unreadable.append(proc.name)
        continue
    for fd in fds:
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        except PermissionError:
            unreadable.append(proc.name)
            break
        if target in targets:
            held.append({'pid': proc.name, 'node': target})
print(json.dumps({'held': held, 'unreadable': sorted(set(unreadable))}))
'''


def privileged_scan(targets):
    """Run the same fd scan as root so every PID is visible. The sudo password is read from the
    owner's local file (outside Git) and passed on stdin only; it is never logged or echoed."""
    pw_file = os.environ.get('SCREEN_SUDO_PASSWORD_FILE', '/home/steve/SUDOPASSWORD.txt')
    with open(pw_file, 'rb') as fh:
        pw = fh.read()
    p = subprocess.run(['sudo', '-S', '-p', '', '/usr/bin/python3', '-c', SCAN_SNIPPET, *sorted(targets)],
                       input=pw, capture_output=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError('privileged render-node scan failed (rc=%d)' % p.returncode)
    out = json.loads(p.stdout.decode().strip().splitlines()[-1])
    return out['held'], out['unreadable']


def idle():
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    if len(nodes) != 4:
        raise RuntimeError(f'Expected four render nodes, found {len(nodes)}')
    targets = {str(n) for n in nodes}
    if os.environ.get('SCREEN_PRIVILEGED_FD_SCAN') == '1':
        held, unreadable = privileged_scan(targets)
        if held or unreadable:
            raise RuntimeError(f'Render-node idle check failed (privileged scan): holders={held}, inaccessible PIDs={unreadable}.')
        return
    # fuser may silently miss inaccessible PIDs. Refuse incomplete /proc visibility.
    held, unreadable = [], []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            fds = list((proc / 'fd').iterdir())
        except FileNotFoundError:
            continue
        except PermissionError:
            unreadable.append(proc.name)
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except FileNotFoundError:
                continue
            except PermissionError:
                unreadable.append(proc.name)
                break
            if target in targets:
                held.append({'pid': proc.name, 'node': target})
    if held or unreadable:
        raise RuntimeError(f'Render-node idle check failed: holders={held}, inaccessible PIDs={sorted(set(unreadable))}. No sudo fallback.')


def storage(required):
    # Both destinations must pass, even if Docker is later moved to another disk.
    for path in (Path('/var/lib/docker'), HERE):
        free = shutil.disk_usage(path).free / GIB
        print(f'{path}: {free:.2f} GiB free; require {required} GiB', flush=True)
        if free < required:
            raise RuntimeError('Disk admission refused; no files are deleted automatically')


def preflight(args, image_present=False, observations=None):
    if socket.gethostname() != 'steve-b70s':
        raise RuntimeError('Wrong host')
    if call(['git', '-C', REPO, 'branch', '--show-current'], capture_output=True).stdout.strip() != 'main':
        raise RuntimeError('Must remain on main')
    storage(PLAN['required_when_present_gib'] if image_present else PLAN['required_before_pull_gib'])
    overlay_check()
    prediction = memory_prediction(args, args.run_dir if hasattr(args, 'run_dir') else HERE / 'runs' / 'screen1b-mtp1', observations)
    if args.mode == 'calibrate-load':
        print('Load-only admission: prediction is diagnostic; the watchdog controls measurement.')
        # Measurement admission is the watchdog, never the unknown prediction.
        reason = calibration.trip_reason(calibration.parse_meminfo(Path('/proc/meminfo').read_text()))
        if reason:
            raise RuntimeError(reason)
    elif getattr(args, 'calibration', None):
        if args.mode != 'mtp1':
            raise RuntimeError('Load calibration only qualifies the identical MTP1 configuration')
        calibration.enforce_receipt(args.calibration, calibration.identity(
            launch(args, args.run_dir), HERE, MODEL))
    else:
        enforce_prediction(prediction, require_post_hash=observations is not None)
    idle()
    with socket.socket() as s:
        s.bind(('127.0.0.1', args.port))
    cutoff = journal_admission(args)
    print('Passive admission passed. Full 185.6 GB model hashing remains required before launch.')
    return cutoff


def launch(args, run):
    mode = 'mtp1' if args.mode == 'calibrate-load' else args.mode
    cmd = ['docker', 'run', '--name', 'flashnext-screen1-' + run.name,
           '--pull=never', '--restart=no', '--network=host', '--device=/dev/dri',
           '--ipc=host', '--security-opt=seccomp=unconfined', '--stop-signal=SIGINT',
           '--entrypoint=/bin/bash', '-w', '/opt/venv']
    env = {
        'ZE_AFFINITY_MASK': '0,1,2,3', 'ZE_FLAT_DEVICE_HIERARCHY': 'FLAT',
        'CCL_ZE_IPC_EXCHANGE': 'sockets', 'CCL_SYCL_ALLGATHERV_TMP_BUF': '1',
        'CCL_SYCL_ALLREDUCE_TMP_BUF': '1', 'VLLM_TARGET_DEVICE': 'xpu',
        'VLLM_WORKER_MULTIPROC_METHOD': 'spawn', 'VLLM_USE_V2_MODEL_RUNNER': '1',
        'VLLM_XPU_ENABLE_XPU_GRAPH': '1', 'B70_GDN_MODE': 'official',
        'Q38_EXPERT_HOST_PLACEMENT': '/screen-package/placement-certified-v5.json',
        'B70_SCREEN1B': '1', 'B70_SCREEN1B_STATE_DIR': '/screen',
        'B70_PLE_FP8': '0', 'B70_PLE_INT8': '0', 'B70_PLE_DIRECT_PINNED': '0',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'HF_DATASETS_OFFLINE': '1', 'HF_HOME': '/screen/cache/hf',
        'TRITON_CACHE_DIR': '/screen/cache/triton', 'VLLM_CACHE_ROOT': '/screen/cache/vllm',
        'XDG_CACHE_HOME': '/screen/cache/xdg', 'TMPDIR': '/screen/cache/tmp',
        'PYTHONDONTWRITEBYTECODE': '1',
    }
    for key, value in env.items():
        cmd += ['-e', f'{key}={value}']
    cmd += ['-v', f'{MODEL}:/model:ro', '-v', f'{run}:/screen',
            '-v', f'{HERE / "container-entrypoint.sh"}:/screen-entrypoint.sh:ro']
    # Apply hash-checked Python files inside the disposable container layer.
    cmd += ['-v', f'{HERE}:/screen-package:ro']
    cmd += [PLAN['image'], '/screen-entrypoint.sh', '--execute', 'serve', '/model',
            '--host', '127.0.0.1', '--port', str(args.port),
            '--served-model-name', 'qwen38-flash-next-fp8-tp4',
            '--tensor-parallel-size', '4', '--enable-expert-parallel',
            '--expert-placement-strategy', 'linear',
            '--all2all-backend', 'allgather_reducescatter',
            '--dtype', 'bfloat16', '--quantization', 'fp8',
            '--kv-cache-dtype', 'auto', '--max-model-len', '4352',
            '--max-num-seqs', '1', '--max-num-batched-tokens', '64',
            '--enable-chunked-prefill', '--no-enable-prefix-caching',
            '--no-async-scheduling', '--generation-config', 'vllm',
            '--gpu-memory-utilization', '0.92', '--kv-cache-memory-bytes', '376569856',
            '--offload-backend', 'uva', '--cpu-offload-gb', '12.25',
            '--cpu-offload-params', 'ple_embedding.ngram_embedding.weight',
            'embed_tokens.weight',
            '--safetensors-load-strategy', 'lazy',
            '--moe-backend', 'triton', '--enable-prompt-tokens-details',
            '--limit-mm-per-prompt', '{"image":0,"video":0}',
            '--compilation-config', json.dumps({'mode': 0, 'compile_sizes': [], 'cudagraph_num_of_warmups': 1, 'cudagraph_mode': 'FULL_DECODE_ONLY', 'cudagraph_capture_sizes': {'mtp0': [1], 'mtp1': [1, 2], 'mtp3': [1, 4]}[mode]}),
            '--cudagraph-metrics']
    if mode != 'mtp0':
        cmd += ['--speculative-config', json.dumps({'method': 'mtp', 'num_speculative_tokens': int(mode[-1]), 'rejection_sample_method': 'standard'})]
    return cmd


def memory_prediction(args, run, observations=None):
    prediction = build_prediction(launch(args, run), model_root=MODEL,
                                  observations=observations)
    print(format_table(prediction), flush=True)
    if run.is_dir():
        (run / 'host-memory-prediction.json').write_text(json.dumps(prediction, indent=2) + '\n')
    return prediction


def supervise(args, run):
    # A systemd unit owns this controller and its attached docker client.
    # kill-mode=process + SendSIGKILL=no prevents cgroup hard kills on busy GPUs.
    with open('/tmp/flashnext-screen1.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return supervise_locked(args, run)


def supervise_locked(args, run):
    preflight(args, image_present=True)
    with open(run / 'image-inspect.json', 'w') as receipt:
        call(['docker', 'image', 'inspect', PLAN['image']], stdout=receipt)
    before_hash = collect_observations()
    (run / 'memory-before-hash.json').write_text(json.dumps(before_hash, indent=2) + '\n')
    call([sys.executable, REPO / 'scripts/verify-qwen38-flash-next-fp8-tree.py',
          '--model-root', MODEL, '--receipt', run / 'model-verification.json'])
    after_hash = collect_observations()
    (run / 'memory-after-hash.json').write_text(json.dumps(after_hash, indent=2) + '\n')
    # Model hashing takes time. Recheck ground truth immediately before launch.
    journal_cutoff = preflight(args, image_present=True,
                               observations=paired_observations(before_hash, after_hash))
    cmd = launch(args, run)
    (run / 'launch.json').write_text(json.dumps(cmd, indent=2) + '\n')
    since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    (run / 'started-utc.txt').write_text(since + '\n')
    stopping = False
    def stop_signal(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    server = None
    client = None
    name = 'flashnext-screen1-' + run.name
    base = f'http://127.0.0.1:{args.port}'
    start = time.monotonic()
    stop_lock = threading.Lock()
    stop_sent = False
    def request_stop(reason):
        nonlocal stopping, stop_sent
        stopping = True
        # All workers see the latch before the entry process receives SIGINT.
        with stop_lock:
            latch_error = None
            try:
                (run / 'STOP').write_text(reason + '\n')
            except OSError as exc:
                latch_error = str(exc)
            if server is None or stop_sent:
                return
            if calibrating:
                # docker run may still be creating the container when the first
                # sample trips. Keep STOP latched; defer the sole signal until
                # inspection confirms the owned container is running.
                try:
                    state = subprocess.run(['docker', 'inspect', '--format', '{{.State.Running}}', name],
                                           capture_output=True, text=True, timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    return
                if state.returncode != 0 or state.stdout.strip() != 'true':
                    return
            stop_sent = True  # never retry, including a failed Docker signal
            try:
                p = subprocess.run(['docker', 'kill', '--signal=SIGINT', name],
                                   capture_output=True, text=True, timeout=10)
                result = {'rc': p.returncode, 'stderr': p.stderr}
            except (OSError, subprocess.TimeoutExpired) as exc:
                result = {'rc': None, 'error': str(exc)}
            (run / 'graceful-stop.json').write_text(json.dumps({
                'signal': 'SIGINT', **result,
                'reason': reason, 'monotonic': time.monotonic(),
                'container_name': name, 'latch_error': latch_error,
            }, indent=2) + '\n')
    calibrating = args.mode == 'calibrate-load'
    sampler = calibration.Sampler() if calibrating else None
    ready = False
    clean_exit = False
    failure = None
    watchdog = (MemoryWatchdog(run, request_stop, sampler,
                              threshold=calibration.trip_reason, interval=calibration.INTERVAL)
                if calibrating else MemoryWatchdog(run, request_stop))
    try:
        if watchdog.check():
            raise RuntimeError('Memory watchdog refused allocation before launch')
        with open(run / 'server.log', 'w') as log, open(run / 'client.log', 'w') as client_log:
            # Start before Popen: no unmonitored first-second allocation window.
            if calibrating:
                watchdog.start()
            if stopping:
                raise RuntimeError('Watchdog stopped before launch')
            server = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            if not calibrating:
                watchdog.start()
            ready = False
            while time.monotonic() - start < 1800:
                if stopping or server.poll() is not None:
                    raise RuntimeError('Startup stopped/exited; no retry')
                check_live(run, journal_cutoff, calibrating=calibrating)
                if sampler and sampler.container_pid is None:
                    info = subprocess.run(['docker', 'inspect', '--format', '{{.State.Pid}}', name],
                                          capture_output=True, text=True, timeout=2)
                    if info.returncode == 0 and info.stdout.strip().isdigit() and int(info.stdout) > 0:
                        sampler.container_pid = int(info.stdout)
                try:
                    with urllib.request.urlopen(base + '/health', timeout=2) as res:
                        ready = res.status == 200
                except OSError:
                    pass
                if ready:
                    with urllib.request.urlopen(base + '/v1/models', timeout=5) as res:
                        models = json.load(res)
                    (run / 'models.json').write_text(json.dumps(models, indent=2))
                    if not any(m['id'] == 'qwen38-flash-next-fp8-tp4' for m in models['data']):
                        raise RuntimeError('Wrong served model')
                    if not calibrating:
                        with urllib.request.urlopen(base + '/metrics', timeout=5) as res:
                            (run / 'metrics-before.txt').write_bytes(res.read())
                    break
                time.sleep(2)
            if not ready:
                raise RuntimeError('30 minute readiness bound exceeded')
            if calibrating:
                sampler.phase = 'plateau'
                watchdog.check()
                plateau_start = time.monotonic()
                while time.monotonic() - plateau_start < calibration.PLATEAU_SECONDS:
                    if stopping or server.poll() is not None:
                        raise RuntimeError('Calibration plateau interrupted')
                    check_live(run, journal_cutoff, calibrating=True)
                    time.sleep(.5)
                watchdog.check()
                if stopping:
                    raise RuntimeError('Calibration plateau watchdog trip')
            else:
                client_cmd = [sys.executable, str(HERE / 'protocol.py'), '--mode', args.mode,
                              '--base-url', base, '--output-dir', str(run / 'client'), '--execute']
                client = subprocess.Popen(client_cmd, stdout=client_log, stderr=subprocess.STDOUT)
                while client.poll() is None:
                    if stopping or server.poll() is not None or time.monotonic() - start > 5400:
                        raise RuntimeError('Stop/server exit/90 minute experiment bound; no retry')
                    check_live(run, journal_cutoff)
                    time.sleep(2)
                if client.returncode:
                    raise RuntimeError(f'Client failed: {client.returncode}')
                with urllib.request.urlopen(base + '/metrics', timeout=5) as res:
                    (run / 'metrics-after.txt').write_bytes(res.read())
    except BaseException as exc:
        failure = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if client and client.poll() is None:
            try:
                client.terminate()  # client owns no GPU; never kill server by pattern
                client.wait(timeout=30)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                (run / 'client-stop-timeout.txt').write_text('Client did not drain in 30s; continue mandatory GPU shutdown.\n')
        try:
            if sampler:
                sampler.phase = 'shutdown'
            if server:
                # docker stop with a timeout escalates to SIGKILL: deliberately avoid it.
                request_stop('controller completion or failure')
                deadline = time.monotonic() + 300
                while time.monotonic() < deadline:
                    state = subprocess.run(['docker', 'inspect', '--format', '{{.State.Running}}', name], capture_output=True, text=True, timeout=5)
                    if state.returncode == 0 and state.stdout.strip() == 'false':
                        if calibrating:
                            status = subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', name],
                                                    capture_output=True, text=True, timeout=5)
                            if status.returncode == 0:
                                state_data = json.loads(status.stdout)
                                clean_exit = (state_data.get('ExitCode') == 0 and
                                              not state_data.get('OOMKilled') and not state_data.get('Error'))
                                (run / 'container-exit.json').write_text(json.dumps(state_data, indent=2) + '\n')
                        break
                    if calibrating and not stop_sent:
                        request_stop('deferred stop after container creation')
                    time.sleep(2)
                else:
                    raise RuntimeError('Graceful shutdown did not finish within 300s. Preserve container, do not relaunch; owner must review.')
                if server.poll() is None:
                    server.wait(timeout=15)
            watchdog.close()
            end = journal()
            (run / 'kernel-postflight.log').write_text(end)
            idle()
            if new_fault_lines(end, journal_cutoff):
                raise RuntimeError('Fault recorded; no recovery or second launch is automated')
        except BaseException as exc:
            failure = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            watchdog.close()
            if calibrating:
                result = write_calibration(run, cmd, ready, clean_exit, watchdog.reason, failure)
        if calibrating and not result['verdict']['passed']:
            raise RuntimeError('Load measured; MTP1 still refused: ' + '; '.join(result['verdict']['refusal_reasons']))


def write_calibration(run, cmd, ready, clean_exit, watchdog_reason, failure):
    samples_path = run / 'host-memory-samples.jsonl'
    samples = ([json.loads(line) for line in samples_path.read_text().splitlines()]
               if samples_path.exists() else [])
    result = {'schema': 'neural.download.screen1b-calibration-load.v1',
              'identity': calibration.identity(cmd, HERE, MODEL),
              'generation_requests': 0, 'ready': ready, 'clean_exit': clean_exit,
              'watchdog_reason': watchdog_reason, 'failure': failure,
              'samples_sha256': calibration.file_hash(samples_path) if samples_path.exists() else None,
              'verdict': calibration.verdict(samples, ready=ready, clean_exit=clean_exit,
                                             watchdog_reason=watchdog_reason, failure=failure)}
    (run / 'calibration-load.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def check_live(run, journal_cutoff, *, calibrating=False):
    text = journal()  # whole current boot avoids empty --since false negatives
    (run / 'kernel-latest.log').write_text(text)
    if new_fault_lines(text, journal_cutoff):
        raise RuntimeError('GPU fault: stop new requests and preserve evidence')
    if shutil.disk_usage(run).free < 50 * GIB:
        raise RuntimeError('50 GiB reserve breached; gracefully stop')
    reason = (calibration.trip_reason(calibration.parse_meminfo(Path('/proc/meminfo').read_text()))
              if calibrating else trip_reason(sample_memory()))
    if reason:
        raise RuntimeError(reason + '; gracefully stop')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['preflight', 'prepare', 'run', '_worker'])
    p.add_argument('--mode', choices=['mtp0', 'mtp1', 'mtp3', 'calibrate-load'], default='mtp1')
    p.add_argument('--health-receipt', type=Path,
                   help='Same-boot four-card health receipt (<6 h); required after a boot fault')
    p.add_argument('--calibration', type=Path, help='Qualified calibration-load.json for MTP1')
    p.add_argument('--port', type=int, default=19988)
    p.add_argument('--run-dir', type=Path, default=None)
    x = p.add_mutually_exclusive_group()
    x.add_argument('--execute', action='store_true')
    x.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    run = (args.run_dir or HERE / 'runs' / ('screen1b-' + args.mode)).resolve()
    if args.calibration:
        args.calibration = args.calibration.resolve()
    if args.health_receipt:
        args.health_receipt = args.health_receipt.resolve()
    if args.mode == 'calibrate-load' and args.action not in ('run', '_worker', 'preflight'):
        p.error('calibrate-load uses the already-present image; prepare is not a calibration action')
    args.run_dir = run
    if args.port == 8188 or not 1024 <= args.port <= 65535:
        p.error('Choose an unused non-LTX unprivileged port')
    overlay_check()
    print(json.dumps({'mode': args.mode, 'image': PLAN['image'], 'disk_before_pull_gib': 89,
                      'requests': 0 if args.mode == 'calibrate-load' else 16, 'launches': 1, 'promotion_eligible': False}, indent=2))
    if not args.execute:
        prediction = build_prediction(launch(args, run), model_root=MODEL)
        print(format_table(prediction))
        if args.mode == 'calibrate-load':
            print('CALIBRATE-LOAD: diagnostic prediction does not gate loading; zero generation requests; 0.5s watchdog; 20s plateau.')
        print('DRY RUN: reads config/index/tensor headers only; no GPU, network, process inspection, Docker operation or writes.')
        if args.action == 'prepare':
            show(['docker', 'pull', PLAN['image']])
        show([sys.executable, REPO / 'scripts/verify-qwen38-flash-next-fp8-tree.py', '--model-root', MODEL, '--receipt', run / 'model-verification.json'])
        show(launch(args, run))
        if args.mode != 'calibrate-load':
            show([sys.executable, HERE / 'protocol.py', '--mode', args.mode, '--base-url', f'http://127.0.0.1:{args.port}', '--output-dir', run / 'client', '--execute'])
        return
    if args.action == 'preflight':
        preflight(args)
        run.mkdir(parents=True, exist_ok=False)
        call([sys.executable, REPO / 'scripts/verify-qwen38-flash-next-fp8-tree.py',
              '--model-root', MODEL, '--receipt', run / 'model-verification.json'])
    elif args.action == 'prepare':
        preflight(args)
        call(['docker', 'pull', PLAN['image']])
        storage(60)
    elif args.action == 'run':
        if run.exists():
            raise RuntimeError('Result directory already exists; preserve it and choose a fresh --run-dir')
        preflight(args, image_present=True)
        call(['docker', 'image', 'inspect', PLAN['image']], stdout=subprocess.DEVNULL)
        run.mkdir(parents=True, exist_ok=False)
        for d in ['tmp', 'hf', 'triton', 'vllm', 'xdg']:
            (run / 'cache' / d).mkdir(parents=True)
        unit = 'flashnext-screen1-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        passthrough = [f'--setenv={k}={os.environ[k]}' for k in ('SCREEN_PRIVILEGED_FD_SCAN', 'SCREEN_SUDO_PASSWORD_FILE') if k in os.environ]
        command = ['systemd-run', '--user', '--unit', unit, '--collect', *passthrough,
                   '--property=Restart=no', '--property=KillMode=process', '--property=SendSIGKILL=no',
                   '--property=TimeoutStopSec=360', sys.executable, str(HERE / 'screen.py'), '_worker',
                   '--mode', args.mode, '--port', str(args.port), '--run-dir', str(run), '--execute']
        if args.calibration:
            command += ['--calibration', str(args.calibration)]
        if args.health_receipt:
            command += ['--health-receipt', str(args.health_receipt)]
        (run / 'unit.txt').write_text(unit + '\n')
        call(command)
        print(f'Follow: journalctl --user -fu {unit}; stop gracefully: systemctl --user stop {unit}')
    else:
        supervise(args, run)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f'REFUSED/STOPPED: {exc}', file=sys.stderr)
        sys.exit(2)
