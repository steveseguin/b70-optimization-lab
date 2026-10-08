# SPDX-License-Identifier: Apache-2.0
"""Screen 1b allocation admission and drained cancellation (stdlib at import).

Only active for B70_SCREEN1B=1. No device enumeration, subprocesses, hard kill,
cache drop or host settings. A single flock serializes collective-free copies
and pin allocations across ranks. It is deliberately NOT a whole-model lock.
"""
from contextlib import contextmanager
from functools import wraps
import errno
import fcntl
import sys
import json
import math
import os
from pathlib import Path
import re
import signal
import threading
import time

COPY_LIMIT = 256 * 2**20
PRESSURE_LIMIT = 80_000_000_000
AVAILABLE_FLOOR = 32 * 2**30
WAIT_SECONDS = 120
_local = threading.local()
_tables = {}
_loading = False
_cancelled = False
_signalled_pids = set()


class LoadCancelled(RuntimeError):
    pass


def enabled():
    return os.environ.get('B70_SCREEN1B') == '1'


def root():
    return Path(os.environ.get('B70_SCREEN1B_STATE_DIR', '/screen'))


def receipt(event, **fields):
    if not enabled():
        return
    row = {'event': event, 'pid': os.getpid(), 'monotonic': time.monotonic(), **fields}
    # One append-only file per PID avoids inter-rank JSON interleaving.
    try:
        with (root() / f'loader-{os.getpid()}.jsonl').open('a') as f:
            f.write(json.dumps(row, sort_keys=True) + '\n')
    except OSError as error:
        print(f'Screen 1b receipt unavailable: {error}; {row}', file=sys.stderr, flush=True)


def request_stop(reason):
    global _cancelled
    _cancelled = True
    if enabled():
        path = root() / 'STOP'
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        except OSError as error:
            print(f'Screen 1b STOP file unavailable: {error}', file=sys.stderr, flush=True)
        else:
            try:
                with os.fdopen(fd, 'w') as f:
                    f.write(reason + '\n')
            except OSError as error:
                print(f'Screen 1b STOP write unavailable: {error}', file=sys.stderr, flush=True)
        receipt('cancel_requested', reason=reason)


def check_cancel():
    if enabled() and (_cancelled or (root() / 'STOP').exists()):
        if _loading:
            synchronize()
        raise LoadCancelled('Screen 1b cancellation latched; no new allocations/copies')


def memory():
    fields = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable'):
            fields[key] = int(value.split()[0]) * 1024
    if set(fields) != {'MemTotal', 'MemAvailable'}:
        raise RuntimeError('MemAvailable accounting unavailable')
    return fields


def check_admission(growth=0):
    check_cancel()
    if growth < 0:
        raise ValueError('negative allocation growth')
    m = memory()
    available = m['MemAvailable'] - growth
    pressure = m['MemTotal'] - m['MemAvailable'] + growth
    if available <= AVAILABLE_FLOOR or pressure >= PRESSURE_LIMIT:
        receipt('allocation_refused', next_bytes=growth, **m)
        request_stop('allocation would cross 80 GB pressure or 32 GiB MemAvailable')
        raise LoadCancelled('Screen 1b next allocation exceeds early stop margin')
    return m


@contextmanager
def admission(label, growth=0):
    if not enabled():
        yield
        return
    depth = getattr(_local, 'depth', 0)
    if depth:
        check_cancel()
        yield
        return
    # Nonblocking lock with deadline: a failed rank cannot strand a waiter.
    with (root() / 'allocation.lock').open('a') as lock:
        deadline = time.monotonic() + WAIT_SECONDS
        while True:
            check_cancel()
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    request_stop('allocation lock timed out')
                    raise LoadCancelled('bounded rank-copy admission timed out')
                time.sleep(.05)
        _local.depth = 1
        try:
            m = check_admission(growth)
            receipt('admitted', label=label, next_bytes=growth, **m)
            yield
        finally:
            _local.depth = 0
            fcntl.flock(lock, fcntl.LOCK_UN)


def synchronize():
    """Called only inside an already initialized runtime, never on CPU import."""
    import torch
    # synchronize only the worker's current accelerator, never enumerate cards.
    torch.accelerator.synchronize()


def bounded_copy(target, source, **kwargs):
    """Preserve dtype/copy arithmetic and serialize <=256 MiB row slices.

    Source is a lazy mmap view; no whole-shard .to() temporary is created.
    copy_ performs the same elementwise dtype conversion as the original copy.
    """
    import torch
    if target.shape != source.shape:
        # copy_ supports broadcasting; expand is a nonallocating view.
        source = source.expand_as(target)
    if target.numel() == 0:
        return target
    # Count both source and destination bytes as in-flight even for direct UVA.
    nbytes = target.numel() * (target.element_size() + source.element_size())
    if nbytes > COPY_LIMIT:
        if target.ndim == 0:
            raise RuntimeError('unbounded scalar copy')
        per_row = math.prod(target.shape[1:]) * (target.element_size() + source.element_size())
        if per_row > COPY_LIMIT:
            # Select a leading row until another dimension is splittable.
            for i in range(target.shape[0]):
                bounded_copy(target[i], source[i], **kwargs)
        else:
            rows = max(1, COPY_LIMIT // per_row)
            for start in range(0, target.shape[0], rows):
                bounded_copy(target[start:start + rows], source[start:start + rows], **kwargs)
        return target
    with admission('copy', nbytes):
        # Blocking copies plus explicit completion before source release.
        kwargs['non_blocking'] = False
        with torch.no_grad():
            target.copy_(source, **kwargs)
        synchronize()
    return target


def register_ple(prefix, module):
    # Checkpoint prefix differs from runtime prefix; layer number is stable.
    match = re.search(r'layers\.(\d+)\.', prefix)
    if match is None:
        raise RuntimeError(f'Cannot identify PLE owner: {prefix}')
    key = int(match.group(1))
    if key in _tables and _tables[key] is not module:
        raise RuntimeError('duplicate real PLE owner for layer')
    _tables[key] = module


def filter_ple_weight(name):
    """Skip nonowned PLE shards before safe_open.get_tensor; verify names.

    Full shard names remain for owned/boundary shards so unchanged row offsets
    and shape gates apply. No separate process table or compressed table exists.
    """
    if not enabled() or '.ngram_embedding.shard_' not in name:
        return False
    m = re.search(r'layers\.(\d+)\..*ngram_embedding\.shard_(\d+)\.weight$', name)
    if m is None:
        raise RuntimeError(f'malformed PLE checkpoint name: {name}')
    layer, shard = map(int, m.groups())
    module = _tables.get(layer)
    if module is None:
        # The MTP module's loader ignores target PLE; no allocation owner there.
        return True
    expected_all = set(range(module.split_ngram_parts))
    if shard not in expected_all:
        raise RuntimeError(f'unexpected PLE shard {shard}')
    return shard not in module.screen1b_expected_shards()


def guarded_load(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        global _loading
        if not enabled():
            return fn(*args, **kwargs)
        import torch
        from torch.utils._python_dispatch import TorchDispatchMode

        class CopyMode(TorchDispatchMode):
            def __torch_dispatch__(self, func, types, args=(), kwargs=None):
                kwargs = kwargs or {}
                check_cancel()
                if func == torch.ops.aten.copy_.default:
                    kw = dict(kwargs)
                    if len(args) > 2:
                        kw['non_blocking'] = args[2]
                    return bounded_copy(args[0], args[1], **kw)
                if func == torch.ops.aten._to_copy.default:
                    # A conversion temporary cannot hide outside the copy budget.
                    dtype = kwargs.get('dtype', args[0].dtype)
                    element = torch.empty((), dtype=dtype, device='meta').element_size()
                    nbytes = args[0].numel() * (element + args[0].element_size())
                    if nbytes > COPY_LIMIT:
                        request_stop('unbounded loader conversion')
                        raise LoadCancelled(f'conversion exceeds 256 MiB: {nbytes}')
                    with admission('conversion', nbytes):
                        out = func(*args, **kwargs)
                        synchronize()
                        return out
                return func(*args, **kwargs)

        _tables.clear()
        _loading = True
        receipt('load_begin')
        try:
            check_cancel()
            with CopyMode():
                model = fn(*args, **kwargs)
            check_cancel()
            return model
        except BaseException:
            request_stop('loader failed or cancelled')
            raise
        finally:
            # Keep all function-frame storage alive until the active transfer
            # finishes. bounded_copy already drains every admitted slice.
            synchronize()
            _loading = False
            receipt('load_drained')
    return wrapped


def loading():
    return _loading


def wait_processes(procs, *, signal_once=False):
    """No timeout-to-kill escalation; retain PID1 until every child has drained.

    The receipt after 120 seconds requests owner intervention. Waiting continues
    because exiting PID1 itself would tear down still-busy container children.
    """
    request_stop('runtime shutdown')
    if signal_once:
        for proc in procs:
            if proc.is_alive() and proc.pid and proc.pid not in _signalled_pids:
                _signalled_pids.add(proc.pid)
                try:
                    os.kill(proc.pid, signal.SIGINT)
                except OSError as error:
                    if error.errno != errno.ESRCH:
                        receipt('signal_failed', child_pid=proc.pid, error=str(error))
                        # Preserve the drain wait even on permission failure.
    start = time.monotonic()
    warned = False
    while any(p.is_alive() for p in procs):
        for p in procs:
            if p.is_alive():
                p.join(.1)
        if not warned and time.monotonic() - start >= WAIT_SECONDS:
            receipt('drain_needs_owner', pids=[p.pid for p in procs if p.is_alive()])
            warned = True
    receipt('children_drained')


def validate_ple_index(folder):
    """Require the full global shard namespace before local range filtering."""
    if not enabled() or not _tables:
        return
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise RuntimeError(f'duplicate checkpoint index key: {key}')
            out[key] = value
        return out
    index = json.loads((Path(folder) / 'model.safetensors.index.json').read_text(),
                       object_pairs_hook=unique)['weight_map']
    seen = {layer: set() for layer in _tables}
    for name in index:
        if '.ngram_embedding.shard_' not in name:
            continue
        m = re.search(r'layers\.(\d+)\..*ngram_embedding\.shard_(\d+)\.weight$', name)
        if m is None:
            raise RuntimeError(f'malformed PLE index entry: {name}')
        layer, shard = map(int, m.groups())
        if layer not in seen:
            raise RuntimeError(f'PLE index has no real owner for layer {layer}')
        if shard in seen[layer]:
            raise RuntimeError(f'duplicate PLE index shard {shard}')
        seen[layer].add(shard)
    for layer, module in _tables.items():
        expected = set(range(module.split_ngram_parts))
        if seen[layer] != expected:
            raise RuntimeError(f'global PLE index coverage mismatch at layer {layer}: '
                               f'missing={sorted(expected-seen[layer])}, '
                               f'unexpected={sorted(seen[layer]-expected)}')
    receipt('PLE_index_complete')
