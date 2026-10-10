#!/usr/bin/env python3
"""Prepared diagnostic: one rank, one 64-token FP8 layer, control then host rows.

Import/help/refusal are stdlib-only. The CPU guardian spawns one fresh Python
worker. Unlike the historical slab probe, the bound latches STOP and preserves
the worker; it never sends a signal or hard-exits. Only a future coordinator
may execute the printed container command with a fresh kernel watcher.
"""
import argparse
from contextlib import contextmanager
import datetime as dt
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace

import single_rank_slab_probe as harness

HERE = Path(__file__).resolve().parent
PACKAGE = harness.PACKAGE
SHAPES = {'w13_weight': (128, 1280, 2560), 'w2_weight': (128, 2560, 640)}
TOKENS, TOPK = 64, 10
BOUND = 120
VERSIONS = {'torch': '2.13.0+xpu', 'triton': '3.7.2+xpu', 'vllm': '0.30.0+xpu',
            'vllm-xpu-kernels': '0.1.14.1', 'transformers': '5.16.1'}


def load_stdlib(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_overlay(expected):
    actual = harness.digest((PACKAGE / 'overlay-manifest.json').read_bytes())
    harness.require(actual == expected, 'overlay manifest SHA-256 differs from preparation')
    application = load_stdlib('first_forward_overlay', PACKAGE / 'apply_overlay.py')
    manifest = application.verify_package(PACKAGE)
    harness.require('vllm/screen1b_teardown.py' in manifest['files'], 'teardown patch is required')
    return application, manifest


def geometry():
    placement = json.loads((PACKAGE / 'placement-attempt6-v5.json').read_text())
    resident, host = harness.production_placement().row_plan(placement, 0, 0)
    harness.require(len(host) == 27 and len(resident) == 101, 'rank-0 layer-0 geometry changed')
    return resident, host


def routes(resident, host):
    # Each token selects five host and five resident experts, no duplicates.
    return [[host[(token * 5 + j) % len(host)] for j in range(5)] +
            [resident[(token * 5 + j) % len(resident)] for j in range(5)]
            for token in range(TOKENS)]


def event(directory, phase, **fields):
    row = dict(phase=phase, pid=os.getpid(), utc=dt.datetime.now(dt.timezone.utc).isoformat(),
               unix=time.time(), monotonic_ns=time.monotonic_ns(), **fields)
    with (directory / 'stages.jsonl').open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
        stream.flush()
    return row


def native_trace_status(root=Path('/sys/kernel/tracing')):
    # Read-only discovery only. Never mount tracefs, enable events or consume
    # trace_pipe. A missing VM-close event leaves causality explicitly open.
    result = {'status': 'unavailable', 'causal_separation_complete': False,
              'reason': 'no validated retained fatal-signal/VM-close trace', 'settings': {}}
    for relative in ('tracing_on', 'current_tracer', 'events/signal/signal_deliver/enable',
                     'events/sched/sched_process_exit/enable', 'events/xe/xe_vm_close/enable'):
        try:
            with (root / relative).open() as stream:
                result['settings'][relative] = stream.read(4096).strip()
        except OSError as exc:
            result['settings'][relative] = {'unavailable': type(exc).__name__}
    return result


def stop(directory, reason):
    try:
        with (directory / 'STOP').open('x') as stream:
            stream.write(reason + '\n')
    except FileExistsError:
        pass


def preserve(directory, reason):
    stop(directory, reason)
    event(directory, 'preserved_no_retry', reason=reason)
    # Keep native ownership alive for the coordinator. No signals or reset.
    while True:
        time.sleep(1)


def span(tensor):
    logical = tensor.numel() * tensor.element_size()
    return dict(pointer=tensor.data_ptr(), span=[tensor.data_ptr(), tensor.data_ptr() + logical],
                storage_bytes=tensor.untyped_storage().nbytes(), shape=list(tensor.shape),
                stride=list(tensor.stride()), dtype=str(tensor.dtype), device=str(tensor.device),
                storage_offset=tensor.storage_offset())


def tensor_spans(value, prefix='arg'):
    if hasattr(value, 'data_ptr') and hasattr(value, 'numel'):
        return {prefix: span(value)}
    result = {}
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            result.update(tensor_spans(item, f'{prefix}.{index}'))
    elif isinstance(value, dict):
        for key, item in value.items():
            result.update(tensor_spans(item, f'{prefix}.{key}'))
    return result


@contextmanager
def instrument(module, torch, directory, check, arm):
    """Wrap real eager production stages; never replace their arithmetic.

    A stage can contain more than one native kernel. Synchronization changes
    timing, so this is localization evidence, never a performance measurement.
    """
    originals = []
    counts = {}
    def wrap(owner, name):
        original = getattr(owner, name)
        originals.append((owner, name, original))
        def measured(*args, **kwargs):
            index = counts.get(name, 0)
            counts[name] = index + 1
            label = f'{arm}.{name}.{index}'
            check()
            torch.xpu.synchronize()
            check()
            event(directory, label + '.before', tensors=tensor_spans((args, kwargs)))
            result = original(*args, **kwargs)
            check()
            torch.xpu.synchronize()
            check()
            event(directory, label + '.after', tensors=tensor_spans(result))
            return result
        setattr(owner, name, measured)
    for name in ('moe_kernel_quantize_input', '_prepare_expert_assignment',
                 'dispatch_fused_moe_kernel', 'apply_moe_activation'):
        wrap(module, name)
    wrap(module.ops, 'moe_sum')
    original_kernel = module.fused_moe_kernel
    class KernelCapture:
        def __getitem__(self, grid):
            launch = original_kernel[grid]
            def call(*args, **kwargs):
                check()
                event(directory, arm + '.triton_launch', tensors=tensor_spans(args))
                compiled = launch(*args, **kwargs)
                check()
                ir = directory / 'ir'
                ir.mkdir(exist_ok=True)
                index = counts.get('triton', 0)
                counts['triton'] = index + 1
                records = {}
                for kind, content in getattr(compiled, 'asm', {}).items():
                    if kind not in ('ttir', 'ttgir', 'llir', 'spv'):
                        continue
                    raw = content.encode() if isinstance(content, str) else bytes(content)
                    name = f'{arm}-{index}.{kind}'
                    (ir / name).write_bytes(raw)
                    records[name] = harness.digest(raw)
                event(directory, arm + '.triton_ir', files=records,
                      unavailable=not bool(records))
                return compiled
            return call
    module.fused_moe_kernel = KernelCapture()
    try:
        yield
    finally:
        module.fused_moe_kernel = original_kernel
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def execute_arms(run, compare, check):
    """Fault/missing watcher/control failure cannot fall through to mixed."""
    check()
    control = run('control')
    check()
    mixed = run('mixed')
    check()
    harness.require(compare(control, mixed), 'mixed FP8 output differs from all-device control')
    return control, mixed


def allocate_layer(torch, placement, guard, resident, host, mixed, directory, check):
    layer = torch.nn.Module()
    layer.layer_name = 'model.layers.0.mlp.experts'
    guard.retain_module(layer)  # partial construction is owned by teardown
    for name, shape in SHAPES.items():
        check()
        if mixed:
            # Only rank discovery is injected: no distributed group/collective.
            # Allocation, guard, native UVA wrapper and table are production code.
            previous = placement.layer_rows
            placement.layer_rows = lambda _layer, _experts: (resident, host)
            try:
                with torch.device('xpu:0'):
                    weight = placement.allocate_weight(layer, name, shape, torch.float8_e4m3fn)
            finally:
                placement.layer_rows = previous
        else:
            weight = torch.nn.Parameter(torch.empty(shape, dtype=torch.float8_e4m3fn,
                                                    device='xpu:0'), requires_grad=False)
            weight._q38_num_experts = 128
            offsets = placement.offsets(weight.data_ptr(), 0, list(range(128)), [],
                                        shape[1] * shape[2], 1)
            weight._q38_base_table = torch.tensor(offsets, dtype=torch.int64,
                                                 device='cpu').to('xpu:0')
        setattr(layer, name, weight)
        # One bounded CPU row at a time; exact reproducible FP8 values, varied by
        # logical expert AND coordinate, so table errors cannot hide in zeros.
        coordinate = torch.arange(shape[1] * shape[2], dtype=torch.int32, device='cpu')
        pattern = ((coordinate % 17).float() - 8) / 64
        for logical in range(128):
            check()
            values = (pattern + (logical - 64) / 128).to(torch.float8_e4m3fn).view(shape[1:])
            placement.row_view(weight, logical).copy_(values)
        del values, coordinate, pattern
        torch.xpu.synchronize()
        check()
        table = weight._q38_base_table.cpu()
        row_bytes = shape[1] * shape[2]
        expected = {}
        if mixed:
            for rows, base in ((resident, weight.data_ptr()),
                               (host, weight._q38_host_storage.data_ptr())):
                expected.update({logical: base + index * row_bytes for index, logical in enumerate(rows)})
            harness.require(weight._q38_host_cpu.untyped_storage().nbytes() == len(host) * row_bytes,
                            'production host slab storage size changed')
        else:
            expected = {index: weight.data_ptr() + index * row_bytes for index in range(128)}
        addresses = [(weight.data_ptr() + offset) % 2**64 for offset in table.tolist()]
        harness.require(addresses == [expected[index] for index in range(128)], 'table readback/address mismatch')
        tensors = {name: weight, 'table': weight._q38_base_table}
        if mixed:
            tensors.update(host=weight._q38_host_cpu, uva=weight._q38_host_storage)
        event(directory, ('mixed' if mixed else 'control') + '.weight_ready',
              tensors=tensor_spans(tensors), table=table.tolist(), addresses=addresses,
              table_sha256=harness.digest(table.numpy().tobytes()))
    return layer


def teardown_owned(runner, proc, guard, torch, teardown):
    # Enter the production rank path first so submissions/queues precede drain.
    # The tiny worker adapter supplies the same runner-release callback used by
    # a real XPU worker, without constructing whole-model services/collectives.
    proc.worker = SimpleNamespace(worker=None,
        shutdown=lambda: teardown.release_runner(runner, guard, torch))
    teardown.shutdown_rank(proc, guard, torch, lambda: None, lambda: None)
    harness.require(teardown._complete, 'rank teardown did not complete')


def validate_teardown(directory):
    validator = load_stdlib('first_forward_teardown_receipts', PACKAGE / 'teardown_receipts.py')
    return validator.validate_rank_receipts(directory / 'teardown', expected_ranks=[0])


def device_work(args, receipt, save):
    application, manifest = verify_overlay(args.overlay_sha256)
    harness.require(sys.executable == '/opt/venv/bin/python', 'execute only inside the pinned container')
    receipt['overlay_application'] = application.apply_overlay(
        Path('/opt/venv/lib/python3.12/site-packages'), PACKAGE)
    receipt['versions'] = {key: importlib.metadata.version(key) for key in VERSIONS}
    harness.require(receipt['versions'] == VERSIONS, 'runtime identity differs from attempt 7')
    save()
    import torch
    from vllm import screen1b_guard as guard, screen1b_teardown as teardown
    from vllm import q38_expert_placement as placement
    moe = importlib.import_module('vllm.model_executor.layers.fused_moe.fused_moe')
    state = args.receipt_dir / 'teardown'
    state.mkdir(exist_ok=True)
    harness.require(guard.enabled() and guard.root() == state, 'separate teardown state path required')
    signal.signal(signal.SIGINT, guard.signal_stop)
    signal.signal(signal.SIGTERM, guard.signal_stop)
    runner = SimpleNamespace(model=torch.nn.ModuleList())
    proc = SimpleNamespace(rank=0, use_async_scheduling=False, worker=None)
    old_mark = teardown.mark
    def cleanup_mark(phase):
        old_mark(phase)
        event(args.receipt_dir, 'teardown.' + phase)
    teardown.mark = cleanup_mark
    def check():
        guard.check_cancel()
        harness.check_watcher(args.receipt_dir, receipt['boot_id'], receipt['health_sha256'])
    error = None
    try:
        check()
        harness.require(torch.xpu.device_count() == 1, 'exactly one visible XPU required')
        torch.xpu.set_device(0)
        receipt['queue_handle'] = int(torch.xpu.current_stream(0).sycl_queue)
        receipt['native_trace'] = native_trace_status()
        receipt['context_identity'] = {'status': 'unavailable',
            'reason': 'opaque queue handle is not a queried native context'}
        resident, host = geometry()
        receipt['geometry'] = dict(tokens=TOKENS, topk=TOPK, rank=0, layer=0,
                                   host_rows=host, resident_rows=resident, shapes=SHAPES,
                                   host_w13_bytes=88473600, host_w2_bytes=44236800)
        save()
        def run(arm):
            check()
            event(args.receipt_dir, arm + '.begin')
            layer = allocate_layer(torch, placement, guard, resident, host, arm == 'mixed', args.receipt_dir, check)
            runner.model.append(layer)
            check()
            # CPU construction, identical bytes in both arms; scales retain
            # the real 128x128 block shape and target's BF16 activation type.
            def transfer(source):
                check()
                value = source.to('xpu:0')
                check()
                return value
            hidden = transfer((((torch.arange(TOKENS * 2560, device='cpu') % 31).float() - 15) / 32).to(torch.bfloat16).view(TOKENS, 2560))
            ids = transfer(torch.tensor(routes(resident, host), dtype=torch.int32, device='cpu'))
            weights = transfer(torch.full((TOKENS, TOPK), 1 / TOPK, dtype=torch.float32, device='cpu'))
            scale1 = transfer(torch.full((128, 10, 20), 1 / 128, dtype=torch.float32, device='cpu'))
            scale2 = transfer(torch.full((128, 20, 5), 1 / 128, dtype=torch.float32, device='cpu'))
            # Runner owns all scratch/input aliases until normal teardown.
            runner.inputs = (hidden, ids, weights, scale1, scale2)
            if arm == 'mixed':
                receipt['usm_queries'] = {}
                for name in SHAPES:
                    parameter = getattr(layer, name)
                    query = harness.query_usm_kind(torch, torch.xpu.current_stream(0),
                        parameter._q38_host_cpu.data_ptr(), parameter._q38_host_storage.data_ptr())
                    receipt['usm_queries'][name] = query
                    if query['status'] == 'queried':
                        harness.require(query['kinds'] == ['host', 'host'], 'unexpected USM allocation kind')
                del parameter
                save()
            with instrument(moe, torch, args.receipt_dir, check, arm):
                output = moe.fused_experts_impl(hidden, layer.w13_weight, layer.w2_weight,
                    weights, ids, use_fp8_w8a8=True, w1_scale=scale1, w2_scale=scale2,
                    block_shape=[128, 128], global_num_experts=128)
            runner.output = output
            check()
            torch.xpu.synchronize()
            check()
            actual = output.cpu()
            harness.require(bool(torch.isfinite(actual).all()), 'non-finite FP8 output')
            raw = actual.view(torch.uint8).numpy().tobytes()
            (args.receipt_dir / (arm + '-output.bf16')).write_bytes(raw)
            event(args.receipt_dir, arm + '.complete', tensors=tensor_spans(output),
                  output_sha256=harness.digest(raw), output_bytes=len(raw))
            # Require a journal read begun after the control, before host work.
            harness.wait_postflight(args.receipt_dir, receipt, time.time())
            return raw
        control, mixed = execute_arms(run, lambda left, right: left == right, check)
        receipt.update(bytes_equal=True, output_sha256=harness.digest(mixed),
                       control_sha256=harness.digest(control), stage='matched_before_teardown')
        save()
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        receipt.update(passed=False, exception={'type': type(exc).__name__, 'message': str(exc),
                                               'traceback': traceback.format_exc()})
        save()
    finally:
        # No further device submission after watcher fault/timeout. Keep the
        # process alive instead of permitting abrupt native finalization.
        if (args.receipt_dir / 'STOP').exists():
            preserve(args.receipt_dir, 'watcher/guardian stopped submissions; native ownership preserved')
        if torch.xpu.is_initialized():
            teardown_owned(runner, proc, guard, torch, teardown)
            receipt['teardown_complete'] = bool(teardown._complete)
            save()
        teardown.mark = old_mark
    if error is not None:
        raise RuntimeError(error)


def worker(args):
    path = args.receipt_dir / 'receipt.json'
    receipt = json.loads(path.read_text())
    save = lambda: harness.atomic_json(path, receipt)
    receipt['worker_pid'] = os.getpid()
    event(args.receipt_dir, 'worker.start')
    save()
    try:
        harness.check_watcher(args.receipt_dir, receipt['boot_id'], receipt['health_sha256'])
        device_work(args, receipt, save)
        event(args.receipt_dir, 'worker.before_normal_exit')
        return 0
    except BaseException as exc:
        receipt.update(passed=False, exception={'type': type(exc).__name__, 'message': str(exc),
                                               'traceback': traceback.format_exc()})
        save()
        # A cleanup exception cannot fall through to Python native finalization.
        if 'torch' in sys.modules and sys.modules['torch'].xpu.is_initialized() and not receipt.get('teardown_complete'):
            preserve(args.receipt_dir, 'failed teardown; preserve worker')
        return 2


def guardian(args, receipt):
    directory = args.receipt_dir
    deadline = time.monotonic() + BOUND
    def intent(signum, frame):
        stop(directory, 'guardian signal: ' + signal.Signals(signum).name)
    signal.signal(signal.SIGINT, intent)
    signal.signal(signal.SIGTERM, intent)
    harness.require(not (directory / 'STOP').exists(), 'STOP before spawn; no worker submission')
    with (directory / 'worker.log').open('x') as log:
        child = subprocess.Popen([sys.executable, '-u', '-B', str(Path(__file__).resolve()),
            '--worker', '--health-receipt', str(args.health_receipt), '--receipt-dir', str(directory),
            '--overlay-sha256', args.overlay_sha256], stdout=log, stderr=subprocess.STDOUT)
        event(directory, 'guardian.spawn', child_pid=child.pid)
        bounded = False
        while child.poll() is None:
            if not bounded and time.monotonic() >= deadline:
                stop(directory, '120-second worker bound exceeded; preserve process, no kill')
                event(directory, 'guardian.timeout', child_pid=child.pid)
                bounded = True
            try:
                status = Path(f'/proc/{child.pid}/status').read_text()
                mem = Path('/proc/meminfo').read_text()
                with (directory / 'memory.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(unix=time.time(), monotonic_ns=time.monotonic_ns(),
                        pid=child.pid, status=status, meminfo=mem)) + '\n')
            except FileNotFoundError:
                pass
            time.sleep(.5)
        result = json.loads((directory / 'receipt.json').read_text())
        result['worker_wait_status'] = child.returncode << 8 if child.returncode >= 0 else -child.returncode
        result['postflight_requested_unix'] = time.time()
        result['worker_returncode'] = child.returncode
        result['guardian_timeout'] = bounded
        harness.atomic_json(directory / 'receipt.json', result)
        event(directory, 'guardian.worker_exit', returncode=child.returncode)
        if child.returncode != 0:
            stop(directory, 'worker failed or received a native signal; no next arm')
        try:
            result['watcher_after_worker'] = harness.wait_postflight(directory, result, result['postflight_requested_unix'])
            result['teardown_validation'] = validate_teardown(directory)
            result['passed'] = (child.returncode == 0 and result.get('bytes_equal') is True
                                and result['teardown_validation']['passed'] is True
                                and result.get('teardown_complete') is True and not bounded)
        except BaseException as exc:
            result.update(passed=False, postflight_exception=str(exc))
        result['stage'] = 'complete' if result['passed'] else 'failed'
        harness.atomic_json(directory / 'receipt.json', result)
        return 0 if result['passed'] else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--health-receipt', type=Path, required=True)
    parser.add_argument('--receipt-dir', type=Path, required=True)
    parser.add_argument('--overlay-sha256', required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        # The child independently rechecks health, journal and overlay before
        # any runtime import. Direct --worker cannot bypass admission.
        harness.admission(args.health_receipt)
        verify_overlay(args.overlay_sha256)
        return worker(args)
    harness.require(args.receipt_dir.is_dir(), 'create a new empty receipt directory first')
    with (args.receipt_dir / 'receipt.json').open('x') as out:
        json.dump({'passed': False, 'stage': 'admission'}, out)
    receipt = dict(schema='neural.download.flashnext-first-forward.v1', passed=False,
                   stage='admission', bytes_equal=False, teardown_complete=False,
                   overlay_sha256=args.overlay_sha256, source_sha256=harness.digest(Path(__file__).read_bytes()),
                   diagnostic_only=True, native_queue_destruction_verified=False,
                   image=json.loads((PACKAGE / 'image-plan.json').read_text())['image'],
                   image_plan_sha256=harness.digest((PACKAGE / 'image-plan.json').read_bytes()),
                   support_source_sha256={str(path.relative_to(PACKAGE)): harness.digest(path.read_bytes())
                        for path in (PACKAGE / 'placement-attempt6-v5.json',
                            PACKAGE / 'teardown_receipts.py', HERE / 'single_rank_slab_probe.py',
                            HERE / 'watch_kernel.py', HERE / 'container_command.py',
                            HERE / 'first_forward_command.py', HERE / 'run-first-forward-in-container.sh')},
                   environment={key: value for key, value in os.environ.items()
                                if key.startswith('FLASHNEXT_PROBE_') or key in harness.ALIASES})
    try:
        receipt.update(harness.admission(args.health_receipt))
        harness.check_watcher(args.receipt_dir, receipt['boot_id'], receipt['health_sha256'])
        verify_overlay(args.overlay_sha256)
        geometry()
    except BaseException as exc:
        receipt['exception'] = {'type': type(exc).__name__, 'message': str(exc)}
        harness.atomic_json(args.receipt_dir / 'receipt.json', receipt)
        return 2
    harness.atomic_json(args.receipt_dir / 'receipt.json', receipt)
    return guardian(args, receipt)


if __name__ == '__main__':
    raise SystemExit(main())
