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
        # A sibling's traceback only identifies where it noticed STOP. Keep
        # the first writer's cause visible instead of blaming that operation.
        try:
            with (root() / 'STOP').open() as f:
                reason = f.read(4096).strip() or 'first stop reason not yet written'
        except OSError:
            reason = 'first stop reason unavailable; see loader receipts'
        raise LoadCancelled('Screen 1b cancellation latched; no new allocations/copies; '
                            f'first stop: {reason}')


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
        reason = ('allocation would cross 80 GB pressure or 32 GiB MemAvailable: '
                  f'pid={os.getpid()}, pressure_bytes={pressure-growth}, '
                  f'next_bytes={growth}, projected_pressure_bytes={pressure}, '
                  f'MemAvailable={m["MemAvailable"]}')
        receipt('allocation_refused', next_bytes=growth,
                pressure_bytes=pressure-growth, projected_pressure_bytes=pressure, **m)
        request_stop(reason)
        raise LoadCancelled(f'Screen 1b next allocation exceeds early stop margin; {reason}')
    return m


@contextmanager
def admission(label, growth=0):
    if not enabled():
        yield
        return
    depth = getattr(_local, 'depth', 0)
    if depth:
        check_admission(growth)
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
    # Hold the cross-rank lock over a logical copy and all slices, so the
    # retained-conversion headroom cannot shrink under the slicing decision.
    if not getattr(_local, 'depth', 0):
        with admission('copy_sequence'):
            return bounded_copy(target, source, **kwargs)
    ledger = root() / 'staging-live.json'
    live = json.loads(ledger.read_text())['live'] if ledger.exists() else {}
    limit = COPY_LIMIT - sum(v['bytes'] for v in live.values())
    if limit <= 0:
        raise LoadCancelled('no transient staging headroom')
    if nbytes > limit:
        if target.ndim == 0:
            raise RuntimeError('unbounded scalar copy')
        per_row = math.prod(target.shape[1:]) * (target.element_size() + source.element_size())
        if per_row > limit:
            # Select a leading row until another dimension is splittable.
            for i in range(target.shape[0]):
                bounded_copy(target[i], source[i], **kwargs)
        else:
            rows = max(1, limit // per_row)
            for start in range(0, target.shape[0], rows):
                bounded_copy(target[start:start + rows], source[start:start + rows], **kwargs)
        return target
    with admission('copy', nbytes):
        # Blocking copies plus explicit completion before source release.
        kwargs['non_blocking'] = False
        token = reserve_staging(nbytes, 'copy')
        try:
            # Explicit UVA/PLE copies can enter here with CopyMode still on
            # the dispatch stack. This leaf already owns its reservation;
            # intercepting it again double-charges the same bytes and splits
            # against only the rounding remainder (4 KiB in attempt 1).
            previous = getattr(_local, 'copy_in_progress', False)
            _local.copy_in_progress = True
            try:
                with torch.no_grad():
                    target.copy_(source, **kwargs)
            finally:
                _local.copy_in_progress = previous
            synchronize()
        finally:
            release_staging(token)
    return target


def register_ple(prefix, module):
    # Checkpoint prefix differs from runtime prefix; layer number is stable.
    match = re.search(r'layers\.(\d+)\.', prefix)
    if match is None:
        raise RuntimeError(f'Cannot identify PLE owner: {prefix}')
    key = int(match.group(1))
    if _tables and key not in _tables:
        raise RuntimeError('Screen 1b 4 GiB total cache contract permits one PLE table only')
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
    if hasattr(getattr(module, 'ngram_embedding', None), '_screen1b_cache'):
        return True
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
                    if getattr(_local, 'copy_in_progress', False):
                        # Only the already-admitted leaf bypasses our second
                        # reservation. Other dispatch modes still see the op.
                        return func(*args, **kwargs)
                    kw = dict(kwargs)
                    if len(args) > 2:
                        kw['non_blocking'] = args[2]
                    return bounded_copy(args[0], args[1], **kw)
                if func == torch.ops.aten._to_copy.default:
                    source_device = args[0].device
                    target_device = torch.device(kwargs.get('device') or source_device)
                    if target_device.type == 'meta':
                        # V30 records reload metadata after construction.
                        # A meta tensor has no payload allocation or transfer.
                        return func(*args, **kwargs)
                    if (source_device.type == 'xpu'
                            and target_device.type == 'xpu'
                            and target_device.index in (None, source_device.index)):
                        # Constructor buffers (notably RoPE's FP32 -> BF16
                        # cache) stay on the worker's device. They allocate no
                        # transient host staging. Keep native conversion and
                        # cancellation, without charging the host copy ledger.
                        return func(*args, **kwargs)
                    # A conversion temporary cannot hide outside the copy budget.
                    dtype = kwargs.get('dtype', args[0].dtype)
                    element = torch.empty((), dtype=dtype, device='meta').element_size()
                    nbytes = args[0].numel() * (element + args[0].element_size())
                    if nbytes > COPY_LIMIT:
                        request_stop('unbounded loader conversion')
                        raise LoadCancelled(f'conversion exceeds 256 MiB: {nbytes}')
                    with admission('conversion', nbytes):
                        import weakref
                        token = reserve_staging(nbytes, 'conversion')
                        try:
                            out = func(*args, **kwargs)
                            synchronize()
                        except BaseException:
                            release_staging(token)
                            raise
                        # Storage rather than tensor lifetime: views can outlive
                        # the returned tensor. PyTorch storage wrapper owns data.
                        if out.device.type == 'cpu':
                            weakref.finalize(out.untyped_storage(), release_staging, token)
                        else:
                            # Device destination is final device storage, not
                            # retained host staging. Transfer is drained above.
                            release_staging(token)
                        return out
                return func(*args, **kwargs)

        _loading = True
        receipt('load_begin')
        try:
            check_cancel()
            with CopyMode():
                model = fn(*args, **kwargs)
            check_cancel()
            allocation_snapshot(model)
            return model
        except BaseException as error:
            receipt('load_failed', error_type=type(error).__name__, error=str(error))
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
    for layer, module in _tables.items():
        if hasattr(module, 'ngram_embedding'):
            from vllm.screen1b_ple import bind_module
            names = [n.rsplit('.shard_', 1)[0] for n in index
                     if re.search(rf'layers\.{layer}\..*ngram_embedding\.shard_0\.weight$', n)]
            if len(names) != 1:
                raise RuntimeError('ambiguous PLE checkpoint prefix')
            bind_module(module, folder, names[0])
    receipt('PLE_index_complete')


# Shared reservation ledger. Conversion storage can outlive its copy call;
# retain its reservation until the returned tensor is collected. A crashed
# rank leaves a reservation behind and STOP/timeout fails closed, never retries.
def reserve_staging(size, label):
    import uuid
    if not 0 <= size <= COPY_LIMIT:
        raise LoadCancelled('staging reservation exceeds global 256 MiB cap')
    token = f'{os.getpid()}-{uuid.uuid4().hex}'
    with admission('staging_reservation', size):
        path = root() / 'staging-live.json'
        state = json.loads(path.read_text()) if path.exists() else {'live': {}, 'peak_bytes': 0}
        total = sum(v['bytes'] for v in state['live'].values()) + size
        if total > COPY_LIMIT:
            request_stop('live staging allocations exceed global 256 MiB cap')
            raise LoadCancelled('live staging cap exceeded; no allocation attempted')
        state['live'][token] = {'bytes': size, 'label': label, 'pid': os.getpid()}
        state['peak_bytes'] = max(total, state['peak_bytes'])
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(state))
        os.replace(temp, path)
        receipt('staging_reserved', token=token, bytes=size, global_live_bytes=total)
    return token


def release_staging(token):
    # Cleanup must work after STOP. Same process-thread nesting as admission.
    from contextlib import nullcontext
    nested = getattr(_local, 'depth', 0)
    with (nullcontext() if nested else (root() / 'allocation.lock').open('a')) as lock:
        if not nested:
            deadline = time.monotonic() + WAIT_SECONDS
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        request_stop('staging cleanup lock timed out; reservation retained')
                        return
                    time.sleep(.05)
        try:
            path = root() / 'staging-live.json'
            state = json.loads(path.read_text())
            state['live'].pop(token)
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(state))
            os.replace(temp, path)
            receipt('staging_released', token=token,
                    global_live_bytes=sum(v['bytes'] for v in state['live'].values()))
        finally:
            if not nested:
                fcntl.flock(lock, fcntl.LOCK_UN)


_models = []
_snapshot_sequence = 0


def allocation_snapshot(model, phase='load_complete', contract_path='/screen-package/memory-contract.json', extra_tensor_groups=None):
    """Retained tensor inventory, not RSS+pins or a complete allocator census.

    UVA device-labelled aliases are charged to their CPU backing storage once.
    Unknown non-tensor driver/graph/workspace bytes remain explicitly unknown.
    Per-mapping RSS is an observation of shared file pages, not another pin.
    """
    global _snapshot_sequence
    import hashlib
    from vllm.distributed import get_tensor_model_parallel_rank
    from vllm.screen1b_ple import metadata_bytes
    if model is not None and all(m is not model for m in _models):
        _models.append(model)
    rank = get_tensor_model_parallel_rank()
    groups, seen, runtime = {}, set(), {}
    def add(group, tensor, kind=None):
        if tensor is None or tensor.numel() == 0:
            return
        storage = tensor.untyped_storage()
        key = (str(tensor.device), storage.data_ptr())
        if key in seen:
            return
        seen.add(key)
        kind = kind or ('pinned_bytes' if tensor.device.type == 'cpu' and tensor.is_pinned()
                        else 'host_pageable_bytes' if tensor.device.type == 'cpu' else 'device_bytes')
        row = groups.setdefault(group, dict(pinned_bytes=0, host_pageable_bytes=0,
                                            device_bytes=0, mmap_resident_bytes=0, mmap_payload_bytes=0))
        row[kind] += storage.nbytes()
    for owner in _models:
        for name, tensor in list(owner.named_parameters()) + list(owner.named_buffers()):
            group = ('PLE' if 'ple_embedding' in name else 'experts' if '.experts.' in name
                     else 'input_embedding' if 'embed_tokens' in name else 'other_model')
            host = getattr(tensor, '_screen1b_host_storage', None)
            if host is not None:
                add(group, host)
            else:
                add(group, tensor)
            add('experts', getattr(tensor, '_q38_host_cpu', None))
            add('experts', getattr(tensor, '_q38_base_table', None))
    def add_tree(group, value):
        if hasattr(value, 'untyped_storage'):
            add(group, value)
        elif isinstance(value, dict):
            for item in value.values():
                add_tree(group, item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                add_tree(group, item)
    for group, tensors in (extra_tensor_groups or {}).items():
        add_tree(group, tensors)
    for module in _tables.values():
        embedding = module.ngram_embedding
        cache = getattr(embedding, '_screen1b_cache', None)
        if cache is None:
            continue
        add('PLE_cache', embedding._screen1b_cache_slab)
        add('PLE_step', embedding._screen1b_step_host)
        add('PLE_step', embedding._screen1b_step_device)
        store = cache.store
        groups[f'PLE_mmap_layer{next(k for k,v in _tables.items() if v is module)}'] = dict(pinned_bytes=0, device_bytes=0,
            host_pageable_bytes=metadata_bytes(store.end-store.start, len(cache.buffer), store.width),
            mmap_payload_bytes=(store.end-store.start)*store.width,
            mmap_resident_bytes=store.resident_bytes(),
            cache_hits=cache.hits, cache_misses=cache.misses, cache_evictions=cache.evictions)
        runtime['PLE'] = dict(rows=store.rows, row_bytes=store.width,
            owned_rows=[store.start, store.end], cache_bytes=len(cache.buffer),
            cache_slots=cache.capacity, metadata_bytes=metadata_bytes(store.end-store.start, len(cache.buffer), store.width),
            step_tokens=embedding._screen1b_step_capacity,
            step_heads=embedding._screen1b_step_host.shape[1],
            step_host_bytes=embedding._screen1b_step_host.numel(),
            step_device_bytes=embedding._screen1b_step_device.numel(),
            index_sha256=store.index_sha256, header_sha256=store.header_sha256)
    contract_path = Path(contract_path)
    raw = contract_path.read_bytes()
    contract = json.loads(raw)
    runtime['pinned_expert_bytes'] = groups.get('experts', {}).get('pinned_bytes', 0)
    runtime['pinned_input_embedding_bytes'] = groups.get('input_embedding', {}).get('pinned_bytes', 0)
    row = dict(schema='screen1b.rank-allocation.v1', rank=rank, pid=os.getpid(), phase=phase,
               groups=groups, actual_runtime_inputs=runtime, host_ram_prediction_inputs=contract,
               prediction_inputs_sha256=hashlib.sha256(raw).hexdigest(),
               copy_cap_bytes=COPY_LIMIT, memory=memory(),
               untracked_runtime_driver_graph_bytes=None,
               accounting='unique retained tensor storage; mmap RSS shared, never sum with host pressure')
    phase_path = root()/f'allocations-rank{rank}-{phase}-{_snapshot_sequence:04d}.json'
    _snapshot_sequence += 1
    # Preserve construction/load/capture history as well as a convenient latest.
    with phase_path.open('x') as stream:
        stream.write(json.dumps(row, indent=2)+'\n')
    path = root()/f'allocations-rank{rank}.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(row, indent=2)+'\n')
    os.replace(temp, path)
    receipt('allocation_snapshot', rank=rank, phase=phase, path=str(phase_path))
