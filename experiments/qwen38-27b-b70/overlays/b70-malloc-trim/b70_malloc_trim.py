"""Return free heap pages to the host on request (research overlay). Enabled with B70_MALLOC_TRIM=1.

Every vLLM process (API server, engine core, each tensor-parallel worker) loads this plugin. It starts one daemon
thread that watches a directory (B70_MALLOC_TRIM_DIR, default /b70trim). When a file named `now` appears or changes
there, the thread calls glibc's `malloc_trim(0)` in its own process and writes `<pid>.json` with the process's
anonymous memory before and after. With B70_MALLOC_TRIM_AFTER_S=<seconds> it also trims once by itself that long
after the process started (for a launcher that wants it without a trigger).

Why: a loaded two-card FP8 server holds about 9 GiB of host memory on a 15 GiB machine, and over a gigabyte in each
worker is ordinary allocator heap left behind by loading 29 GB of weights through host buffers. `malloc_trim` hands
the free pages inside that heap back to the kernel. It changes no tensor and no arithmetic: it only releases memory
the process had already freed. Do not attach a debugger from the host to do this instead; that killed a server on
2026-10-04 (different PID namespaces).
"""
import ctypes
import json
import os
import threading
import time


def _rss_anon_kb():
    try:
        with open('/proc/self/status') as handle:
            for line in handle:
                if line.startswith('RssAnon:'):
                    return int(line.split()[1])
    except OSError:
        pass
    return -1


def _trim(directory, reason):
    libc = ctypes.CDLL('libc.so.6', use_errno=True)
    before = _rss_anon_kb()
    started = time.time()
    released = int(libc.malloc_trim(0))
    record = {'pid': os.getpid(), 'reason': reason, 'at': started, 'seconds': round(time.time() - started, 4),
              'malloc_trim_returned': released, 'rss_anon_kb_before': before, 'rss_anon_kb_after': _rss_anon_kb()}
    try:
        name = ''
        with open('/proc/self/comm') as handle:
            name = handle.read().strip()
        record['comm'] = name
        tmp = os.path.join(directory, f'.{os.getpid()}.json.tmp')
        with open(tmp, 'w') as handle:
            json.dump(record, handle)
        os.replace(tmp, os.path.join(directory, f'{os.getpid()}-{int(started)}.json'))
    except OSError:
        pass
    return record


def _census(directory):
    """Which live CPU tensors does this process hold? Written to <pid>-census.json when a `census` file appears."""
    import gc
    record = {'pid': os.getpid(), 'rss_anon_kb': _rss_anon_kb()}
    try:
        import torch
        seen, rows, total = set(), [], 0
        for obj in gc.get_objects():
            try:
                if not isinstance(obj, torch.Tensor) or obj.device.type != 'cpu' or obj.numel() == 0:
                    continue
                storage = obj.untyped_storage()
                key = storage.data_ptr()
                if key in seen:
                    continue
                seen.add(key)
                size = storage.nbytes()
                total += size
                rows.append((size, list(obj.shape), str(obj.dtype), type(obj).__name__))
            except Exception:
                continue
        rows.sort(reverse=True)
        record.update(cpu_tensor_storages=len(rows), cpu_tensor_bytes=total,
                      largest=[{'bytes': r[0], 'shape': r[1], 'dtype': r[2], 'type': r[3]} for r in rows[:20]])
    except Exception as exc:
        record['error'] = repr(exc)
    try:
        with open('/proc/self/comm') as handle:
            record['comm'] = handle.read().strip()
        with open(os.path.join(directory, f'{os.getpid()}-census.json'), 'w') as handle:
            json.dump(record, handle)
    except OSError:
        pass


def _watch(directory, after_s):
    trigger = os.path.join(directory, 'now')
    census = os.path.join(directory, 'census')
    census_seen = None
    seen = None
    started = time.time()
    auto_done = after_s <= 0
    while True:
        time.sleep(1.0)
        if not auto_done and time.time() - started >= after_s:
            auto_done = True
            _trim(directory, f'auto after {after_s:g} s')
        try:
            stamp = os.stat(census).st_mtime_ns
            if stamp != census_seen:
                census_seen = stamp
                _census(directory)
        except OSError:
            pass
        try:
            stamp = os.stat(trigger).st_mtime_ns
        except OSError:
            continue
        if stamp != seen:
            seen = stamp
            _trim(directory, 'trigger')


def register():
    if os.environ.get('B70_MALLOC_TRIM', '').strip() != '1':
        return
    if getattr(register, '_started', False):
        return
    register._started = True
    directory = os.environ.get('B70_MALLOC_TRIM_DIR', '/b70trim')
    after_s = float(os.environ.get('B70_MALLOC_TRIM_AFTER_S', '0') or 0)
    threading.Thread(target=_watch, args=(directory, after_s), name='b70-malloc-trim', daemon=True).start()
    print(f'b70_malloc_trim: watching {directory} in pid {os.getpid()} (auto after {after_s:g} s)', flush=True)
