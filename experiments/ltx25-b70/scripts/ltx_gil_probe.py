"""Packet 92a: is the pipeline bound by its shared interpreter?

Three standard-library instruments, none of which touches a tensor, a stream,
a device, RNG state or the order of GPU work, and none of which can raise into
a clip (every public function catches everything):

1. Per-thread CPU time. `cpu_snapshot()` reads utime+stime of every thread of
   this process from /proc/self/task/<tid>/stat (10 ms ticks), names each
   thread from `threading` (lane threads are named `ltx-*`; the ComfyUI
   prompt thread registers itself with `mark_lane_thread`). The analyzer takes
   differences between receipts, so CPU-seconds per wall-second per thread
   and summed over lane threads come from the same clock as the arm.
   Per-job CPU seconds (`time.thread_time`) are recorded by ltx_pipeline's
   worker loop and by each node's `_apply`.
2. Lock-wait probe. One daemon thread sleeps 0.5 ms in a loop and records how
   much longer than 0.5 ms each sleep took: the time it waited to get the
   interpreter lock back (plus OS wake-up). Overshoots go into a fixed
   geometric histogram; each receipt drains it. The probe reports its own CPU
   seconds so its cost is visible. Caveat: a thread that wants the lock makes
   the holder hand it over at the next switch interval, so the probe adds at
   most one forced hand-off per switch interval to the contention it measures.
3. Switch-interval knob. `set_switch_interval` applies `sys.setswitchinterval`
   only when no pipeline job is queued or running (waits a bounded time, then
   refuses), and `restore_default` puts back 5 ms (called by the runner's last
   arm and by any node that latches a failure).
"""
import os
import sys
import threading
import time

DEFAULT_SWITCH_INTERVAL = 0.005
PROBE_SLEEP = 0.0005
# Histogram edges in microseconds: geometric, ratio 2**(1/4), 4 us .. ~16 s.
EDGES_US = [4.0 * 2 ** (i / 4.0) for i in range(89)]
_LOCK = threading.Lock()
_HIST = [0] * (len(EDGES_US) + 1)
_STATE = {'samples': 0, 'started': None, 'thread': None, 'probe_cpu_s': 0.0, 'errors': 0,
          'lane_threads': {}, 'knob_log': []}
_TICK = os.sysconf('SC_CLK_TCK') if hasattr(os, 'sysconf') else 100


def _bucket(us):
    lo, hi = 0, len(EDGES_US)
    while lo < hi:
        mid = (lo + hi) // 2
        if us < EDGES_US[mid]:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _probe_loop():
    sleep, clock = time.sleep, time.perf_counter
    cpu0 = time.thread_time()
    local = [0] * len(_HIST)
    n = 0
    last_flush = clock()
    while True:
        try:
            t0 = clock()
            sleep(PROBE_SLEEP)
            over_us = (clock() - t0 - PROBE_SLEEP) * 1e6
            local[_bucket(max(0.0, over_us))] += 1
            n += 1
            if n >= 256 or clock() - last_flush > 0.25:
                with _LOCK:
                    for i, c in enumerate(local):
                        if c:
                            _HIST[i] += c
                    _STATE['samples'] += n
                    _STATE['probe_cpu_s'] = time.thread_time() - cpu0
                local = [0] * len(_HIST)
                n = 0
                last_flush = clock()
        except Exception:  # noqa: BLE001  (diagnostic only)
            _STATE['errors'] += 1
            time.sleep(0.01)


def start_probe():
    """Start the lock-wait probe once per process. Never raises."""
    try:
        with _LOCK:
            if _STATE['thread'] is not None and _STATE['thread'].is_alive():
                return True
            t = threading.Thread(target=_probe_loop, daemon=True, name='ltx-gil-probe')
            _STATE['thread'] = t
            _STATE['started'] = time.time()
        t.start()
        return True
    except Exception:  # noqa: BLE001
        return False


def drain_lag():
    """Histogram counts since the last drain (bucket i: < EDGES_US[i]; last: overflow)."""
    try:
        with _LOCK:
            counts = list(_HIST)
            for i in range(len(_HIST)):
                _HIST[i] = 0
            samples, _STATE['samples'] = _STATE['samples'], 0
            cpu = _STATE['probe_cpu_s']
        return {'counts': counts, 'samples': samples, 'probe_cpu_s_total': round(cpu, 4),
                'sleep_s': PROBE_SLEEP}
    except Exception as error:  # noqa: BLE001
        return {'error': repr(error)[:200]}


def mark_lane_thread(role):
    """Record the calling thread (e.g. the ComfyUI prompt thread) as a lane thread."""
    try:
        _STATE['lane_threads'][threading.get_native_id()] = role
    except Exception:  # noqa: BLE001
        pass


def cpu_snapshot():
    """{tid: {'name', 'cpu_s'}} for every thread of this process, plus wall time. Never raises."""
    try:
        names = {t.native_id: t.name for t in threading.enumerate() if t.native_id is not None}
        lane = dict(_STATE['lane_threads'])
        rows = {}
        for tid in os.listdir('/proc/self/task'):
            try:
                with open('/proc/self/task/%s/stat' % tid) as handle:
                    fields = handle.read().rsplit(')', 1)[1].split()
                cpu = (int(fields[11]) + int(fields[12])) / _TICK
                t = int(tid)
                name = names.get(t)
                if name is None:
                    with open('/proc/self/task/%s/comm' % tid) as handle:
                        name = 'native:' + handle.read().strip()
                role = lane.get(t)
                rows[tid] = {'name': name if role is None else 'lane-prompt:' + role,
                             'cpu_s': round(cpu, 3)}
            except Exception:  # noqa: BLE001  (thread exited between listdir and read)
                continue
        return {'wall_unix': time.time(), 'process_cpu_s': round(sum(r['cpu_s'] for r in rows.values()), 3),
                'threads': rows, 'tick_s': 1.0 / _TICK}
    except Exception as error:  # noqa: BLE001
        return {'error': repr(error)[:200]}


def report(drain=True):
    """What every receipt carries. Never raises."""
    try:
        out = {'switch_interval_s': sys.getswitchinterval(), 'cpu': cpu_snapshot()}
        if drain:
            out['lag'] = drain_lag()
        return out
    except Exception as error:  # noqa: BLE001
        return {'error': repr(error)[:200]}


def set_switch_interval(seconds, busy, wait_s=60.0, poll_s=0.5, sleep=time.sleep):
    """Apply `sys.setswitchinterval(seconds)` only when `busy()` is 0.

    Waits up to `wait_s` for the pipeline to go idle, then refuses. Returns a
    record {'applied', 'requested_s', 'previous_s', 'now_s', 'reason'}.
    Never raises."""
    record = {'applied': False, 'requested_s': seconds, 'previous_s': None, 'now_s': None, 'reason': ''}
    try:
        record['previous_s'] = sys.getswitchinterval()
        if not (isinstance(seconds, (int, float)) and 0.0001 <= float(seconds) <= 0.1):
            record['reason'] = 'switch interval outside 0.1-100 ms'
            return record
        waited = 0.0
        while True:
            pending = busy()
            if not pending:
                break
            if waited >= wait_s:
                record['reason'] = 'pipeline busy (%s jobs queued or running) after %.0f s' % (pending, waited)
                return record
            sleep(poll_s)
            waited += poll_s
        sys.setswitchinterval(float(seconds))
        record.update(applied=True, now_s=sys.getswitchinterval(), waited_s=waited)
        return record
    except Exception as error:  # noqa: BLE001
        record['reason'] = 'error: ' + repr(error)[:200]
        return record
    finally:
        try:
            _STATE['knob_log'].append(dict(record, unix=time.time()))
        except Exception:  # noqa: BLE001
            pass


def restore_default(reason=''):
    """Put the 5 ms default back (failed arm / end of campaign). Never raises."""
    try:
        previous = sys.getswitchinterval()
        sys.setswitchinterval(DEFAULT_SWITCH_INTERVAL)
        _STATE['knob_log'].append({'restored': True, 'previous_s': previous, 'reason': reason,
                                   'unix': time.time()})
        return True
    except Exception:  # noqa: BLE001
        return False


def percentile_us(counts, q):
    """Upper bucket edge (us) holding quantile q of a drained histogram; None if empty."""
    total = sum(counts)
    if not total:
        return None
    target = q * total
    run = 0
    for i, c in enumerate(counts):
        run += c
        if run >= target:
            return EDGES_US[i] if i < len(EDGES_US) else float('inf')
    return float('inf')
