#!/usr/bin/env python3
"""One diagnostic gather. Importing this module never imports Torch/Triton.

Only the coordinator may admit execution. The parent is a CPU receipt guardian;
exactly one child owns the sole XPU, with an OS-enforced 120-second SIGALRM.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import traceback
import time

HERE = Path(__file__).resolve().parent
PACKAGE = Path(os.environ.get('FLASHNEXT_PROBE_PACKAGE', HERE.parent))
CONF = 'pinned_max_round_threshold_mb:1,pinned_max_cached_size_mb:1'
ALIASES = ('PYTORCH_ALLOC_CONF', 'PYTORCH_CUDA_ALLOC_CONF', 'PYTORCH_HIP_ALLOC_CONF')
ROWS = [3, 0, 2, 1]
SLAB_BYTES = 3 * 2**20
VIEW_OFFSET = 4096
ROW_BYTES = 4096
FAILED_BOOT = '10192010'  # attempt-7 boot prefix; no same-boot retry


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    tmp.replace(path)


def lane():
    sys.path.insert(0, str(PACKAGE))
    import screen  # stdlib-only import; no operational functions invoked
    return screen


def production_placement():
    path = PACKAGE / 'overlay/vllm/q38_expert_placement.py'
    manifest = json.loads((PACKAGE / 'overlay-manifest.json').read_text())
    require(digest(path.read_bytes()) == manifest['files']['vllm/q38_expert_placement.py'],
            'production placement differs from overlay manifest')
    spec = importlib.util.spec_from_file_location('probe_production_placement', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def admission(health_path, *, env=None, boot_id=None, now=None):
    env = os.environ if env is None else env
    require(env.get('FLASHNEXT_PROBE_ADMIT') == '1', 'FLASHNEXT_PROBE_ADMIT=1 required')
    require(all(env.get(k) == CONF for k in ALIASES), 'all exact-size allocator aliases required before Torch import')
    require(env.get('NEOReadDebugKeys') == '1' and env.get('EnableDeferBacking') == '0',
            'lane per-process driver aliases required')
    boot = boot_id or Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(not boot.startswith(FAILED_BOOT), 'attempt-7 fault boot is forbidden')
    raw = Path(health_path).read_bytes()
    now = now or dt.datetime.now(dt.timezone.utc)
    end = lane().verify_health_receipt(json.loads(raw), boot, now)
    return {'boot_id': boot, 'health_sha256': digest(raw), 'health_end_unix': end.timestamp()}


def check_watcher(directory, boot, health_sha256=None):
    require(not (directory / 'STOP').exists(), 'fault watcher STOP latched; no submissions')
    status = json.loads((directory / 'watcher.json').read_text())
    require(status.get('boot_id') == boot and status.get('passed') is True,
            'fault watcher is not clean on this boot')
    if health_sha256 is not None:
        require(status.get('health_sha256') == health_sha256, 'watcher used a different health receipt')
    age = dt.datetime.now(dt.timezone.utc).timestamp() - status['updated_unix']
    require(0 <= age < 5, 'fault watcher receipt is stale or future-dated')
    return status


def wait_postflight(directory, receipt, requested_unix, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = check_watcher(directory, receipt['boot_id'], receipt['health_sha256'])
        if status.get('read_started_unix', 0) >= requested_unix:
            return status
        time.sleep(.05)
    raise RuntimeError('no kernel journal sample began after worker exit; cannot pass')


def table_values(resident_base, host_base):
    all_rows = production_placement().offsets(resident_base, host_base, [], list(range(4)), ROW_BYTES, 1)
    values = [all_rows[r] for r in ROWS]
    reconstructed = [(resident_base + value) % 2**64 for value in values]
    expected = [(host_base + r * ROW_BYTES) % 2**64 for r in ROWS]
    require(reconstructed == expected, 'production signed table reconstruction failed')
    return values, reconstructed


def query_usm_kind(torch, stream, slab_ptr, view_ptr):
    """Inspect only read-only bindings; never cast a queue address to a context.

    Reviewed Torch/XPU-kernels/Triton Python exports have no such binding.
    A runtime exposing a SYCL queue object with get_context() can use the
    context's get_pointer_type() query. No allocation-import fallback exists.
    """
    result = {'status': 'unavailable', 'queue_handle': int(stream.sycl_queue),
              'pointers': [slab_ptr, view_ptr], 'kinds': None,
              'reason': 'no read-only pointer-kind query in launch queue context',
              'inspected': ['launch stream.get_context']}
    context_getter = getattr(stream, 'get_context', None)
    if context_getter is None:
        return result
    context = context_getter()
    result['inspected'].append('launch context.get_pointer_type')
    query = getattr(context, 'get_pointer_type', None)
    if query is None:
        return result
    kinds = [str(query(ptr)) for ptr in (slab_ptr, view_ptr)]
    result.update(status='queried', kinds=kinds, api='stream.get_context().get_pointer_type',
                  reason=None)
    return result


def run_device(args, receipt, save):
    # ALL refusal/identity checks precede device initialization.
    import importlib.metadata as metadata
    expected = {'torch': '2.13.0+xpu', 'triton': '3.7.2+xpu', 'vllm': '0.30.0+xpu',
                'vllm-xpu-kernels': '0.1.14.1', 'transformers': '5.16.1'}
    receipt['versions'] = {name: metadata.version(name) for name in expected}
    require(receipt['versions'] == expected, 'runtime identity differs from attempt 7')
    require('torch' not in sys.modules, 'Torch was imported before admission')
    import torch
    import triton
    from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor
    from slab_kernels import indirect_gather, direct_gather
    check = lambda: check_watcher(args.receipt_dir, receipt['boot_id'], receipt['health_sha256'])
    check()
    require(torch.xpu.device_count() == 1, 'exactly one visible XPU required')
    torch.xpu.set_device(0)
    stream = torch.xpu.current_stream(0)
    receipt['queue_handle'] = int(stream.sycl_queue)
    receipt['stage'] = 'allocate_slab'
    save()
    check()
    # SAME allocator path as allocate_weight: Torch CPU empty(pin_memory=True),
    # with all three exact-size aliases set before import. No custom allocator.
    slab = torch.empty(SLAB_BYTES, dtype=torch.uint8, device='cpu', pin_memory=True)
    slab.fill_(0)
    view = slab[VIEW_OFFSET:VIEW_OFFSET + 4 * ROW_BYTES].view(4, ROW_BYTES)
    source = (torch.arange(4 * ROW_BYTES, dtype=torch.int64, device='cpu') % 251).to(torch.uint8).view(4, ROW_BYTES)
    view.copy_(source)
    require(slab.is_pinned() and view.is_pinned(), 'slab/view must be pinned')
    require(slab.untyped_storage().nbytes() == SLAB_BYTES, 'wrong slab storage span')
    require(view.storage_offset() == VIEW_OFFSET and view.is_contiguous(), 'wrong interior view')
    require(view.stride() == (ROW_BYTES, 1) and view.dtype == torch.uint8, 'wrong CPU layout')
    require(view.data_ptr() == slab.data_ptr() + VIEW_OFFSET, 'CPU interior pointer mismatch')
    check()
    # Exactly one native UVA view; retain slab, view and UVA until completion.
    with torch.xpu.device(0):
        uva = get_accelerator_view_from_cpu_tensor(view)
    require(uva.device == torch.device('xpu:0'), 'UVA belongs to wrong device')
    require(uva.data_ptr() == view.data_ptr() and uva.dtype == view.dtype,
            'native UVA pointer/dtype mismatch')
    require(tuple(uva.shape) == (4, ROW_BYTES) and uva.stride() == (ROW_BYTES, 1)
            and uva.is_contiguous(), 'native UVA shape/stride mismatch')
    require(uva.storage_offset() == 0 and uva.untyped_storage().nbytes() == 4 * ROW_BYTES,
            'native UVA interior-storage contract changed')
    receipt['tensors'] = {}
    for name, tensor in [('slab', slab), ('view', view), ('uva', uva)]:
        receipt['tensors'][name] = {'data_ptr': tensor.data_ptr(), 'shape': list(tensor.shape),
            'stride': list(tensor.stride()), 'dtype': str(tensor.dtype),
            'storage_offset': tensor.storage_offset(), 'logical_bytes': tensor.numel(),
            'storage_bytes': tensor.untyped_storage().nbytes(),
            'span': [tensor.data_ptr(), tensor.data_ptr() + tensor.numel()],
            'is_pinned': tensor.is_pinned() if tensor.device.type == 'cpu' else None}
    receipt['input_sha256'] = digest(view.numpy().tobytes())
    receipt['slab_sha256'] = digest(slab.numpy().tobytes())
    save()
    receipt['usm_query'] = query_usm_kind(torch, stream, slab.data_ptr(), view.data_ptr())
    save()
    if receipt['usm_query']['status'] == 'queried':
        require(receipt['usm_query']['kinds'] == ['host', 'host'],
                'USM kind is not host in launch queue context: ' + repr(receipt['usm_query']['kinds']))
    check()
    resident = torch.empty(4 * ROW_BYTES, dtype=torch.uint8, device='xpu:0')
    values, addresses = table_values(resident.data_ptr(), uva.data_ptr())
    table = torch.tensor(values, dtype=torch.int64, device='cpu').to('xpu:0')
    readback = table.cpu()
    require(readback.tolist() == values, 'device offset table changed on readback')
    require([(resident.data_ptr() + x) % 2**64 for x in readback.tolist()] == addresses,
            'readback table failed CPU address reconstruction')
    output = torch.empty((4, ROW_BYTES), dtype=torch.uint8, device='xpu:0')
    receipt.update(resident_base=resident.data_ptr(), resident_span=[resident.data_ptr(), resident.data_ptr()+4*ROW_BYTES],
                   table_values=values, reconstructed_addresses=addresses,
                   table_sha256=digest(readback.numpy().tobytes()), table_ptr=table.data_ptr(),
                   table_span=[table.data_ptr(), table.data_ptr() + 32],
                   output_ptr=output.data_ptr(), output_span=[output.data_ptr(), output.data_ptr()+4*ROW_BYTES], rows=ROWS)
    if args.direct_host_pointer:
        local_rows = torch.tensor(ROWS, dtype=torch.int64, device='cpu').to('xpu:0')
        selectors = torch.ones(4, dtype=torch.uint8, device='cpu').to('xpu:0')
        kernel, operands = direct_gather, (resident, uva, local_rows, selectors, output)
    else:
        kernel, operands = indirect_gather, (resident, table, output)
    receipt['stage'] = 'compile_only'
    save()
    check()
    compiled = kernel.warmup(*operands, grid=(4,), num_warps=4)
    ir_dir = args.receipt_dir / 'ir'
    ir_dir.mkdir(exist_ok=True)
    receipt['triton_ir'] = {}
    for name in ('ttir', 'ttgir', 'llir', 'spv'):
        content = compiled.asm.get(name)
        if content is not None:
            data = content.encode() if isinstance(content, str) else bytes(content)
            path = ir_dir / ('slab_gather.' + name)
            path.write_bytes(data)
            receipt['triton_ir'][name] = {'path': str(path), 'sha256': digest(data)}
    require('ttir' in receipt['triton_ir'], 'compiler returned no Triton IR')
    receipt['stage'] = 'gather'
    save()
    check()
    require(int(torch.xpu.current_stream(0).sycl_queue) == receipt['queue_handle'], 'launch queue changed')
    receipt['gather_launches'] = 1
    save()
    kernel[(4,)](*operands, num_warps=4)  # the ONE diagnostic launch
    check()
    receipt['explicit_synchronizations'] = 1
    save()
    torch.xpu.synchronize(0)  # the ONE explicit synchronization
    check()
    actual = output.cpu()  # blocking transport, not another explicit synchronize
    expected_output = source[ROWS]
    receipt.update(output_sha256=digest(actual.numpy().tobytes()),
                   expected_sha256=digest(expected_output.numpy().tobytes()))
    require(torch.equal(actual, expected_output), 'gather differs from rows [3,0,2,1]')
    receipt['watcher_at_completion'] = check()
    receipt.update(stage='bytes_equal_waiting_postflight', bytes_equal=True, passed=False, exception=None)
    save()
    # Owners remain live through the exact comparison; normal return frees them.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--health-receipt', type=Path, required=True)
    parser.add_argument('--receipt-dir', type=Path, required=True)
    parser.add_argument('--direct-host-pointer', action='store_true')
    args = parser.parse_args(argv)
    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    path = args.receipt_dir / 'receipt.json'
    # Preserve every prior attempt, including a refusal. Never auto-retry.
    with path.open('x') as out:
        json.dump({'passed': False, 'stage': 'admission'}, out)
    receipt = {'schema': 'neural.download.flashnext-slab-probe.v1', 'passed': False,
               'variant': 'direct' if args.direct_host_pointer else 'indirect',
               'stage': 'admission', 'exception': None, 'triton_ir': {},
               'gather_launches': 0, 'explicit_synchronizations': 0,
               'timeout_seconds': 120, 'source_sha256': digest(Path(__file__).read_bytes())}
    save = lambda: atomic_json(path, receipt)
    try:
        receipt.update(admission(args.health_receipt))
        check_watcher(args.receipt_dir, receipt['boot_id'], receipt['health_sha256'])
        production_placement()
        save()
    except BaseException as exc:
        receipt['exception'] = {'type': type(exc).__name__, 'message': str(exc),
                                'repr': repr(exc), 'traceback': traceback.format_exc()}
        save()
        return 2
    # Fork BEFORE importing Torch. CPU parent can retain signal/crash/timeout
    # evidence even when native code cannot return to a Python signal handler.
    pid = os.fork()
    if pid == 0:
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.alarm(120)
        try:
            run_device(args, receipt, save)
        except BaseException as exc:
            receipt.update(passed=False, exception={'type': type(exc).__name__, 'message': str(exc),
                'repr': repr(exc), 'traceback': traceback.format_exc()})
            save()
            # No further device calls, cleanup synchronize, or retry on failure.
            os._exit(2)
        os._exit(0)
    forwarded = []
    def forward_once(signum, frame):
        if not forwarded:
            forwarded.append(signum)
            try:
                os.kill(pid, signum)
            except ProcessLookupError:
                pass
    signal.signal(signal.SIGINT, forward_once)
    signal.signal(signal.SIGTERM, forward_once)
    _, status = os.waitpid(pid, 0)
    receipt = json.loads(path.read_text())
    receipt['worker_wait_status'] = status
    receipt['postflight_requested_unix'] = time.time()
    receipt['forwarded_signals'] = forwarded
    save()
    if os.WIFSIGNALED(status):
        sig = os.WTERMSIG(status)
        receipt.update(passed=False, exception={'type': 'NativeSignal', 'signal': sig,
            'name': signal.Signals(sig).name,
            'message': 'hard 120-second alarm' if sig == signal.SIGALRM else 'native process terminated by signal'})
    elif os.WEXITSTATUS(status) != 0:
        receipt['passed'] = False
    try:
        receipt['watcher_after_worker'] = wait_postflight(args.receipt_dir, receipt, receipt['postflight_requested_unix'])
        receipt['passed'] = (os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
                             and receipt.get('bytes_equal') is True and not forwarded)
        if receipt['passed']:
            receipt['stage'] = 'complete'
    except BaseException as exc:
        receipt['passed'] = False
        receipt['postflight_exception'] = {'type': type(exc).__name__, 'message': str(exc)}
    save()
    return 0 if receipt['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
