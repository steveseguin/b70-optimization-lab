#!/usr/bin/env python3
"""Bounded actual Kitchen CPU dispatch proof, XPU queries explicitly blocked."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')


def require(value, message):
    if not value:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(args.cpu and not FAULT.exists(), 'CPU guard/fault latch failed before Torch import')
    require(os.environ.get('OMP_NUM_THREADS') == os.environ.get('MKL_NUM_THREADS') == '1', 'Use OMP/MKL_NUM_THREADS=1')
    args.output.mkdir(exist_ok=False)
    state = {'status': 'running', 'pid': os.getpid(), 'phase': 'before-torch-import', 'checks': [],
             'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    def save():
        (args.output / 'receipt.json').write_text(json.dumps(state, indent=2) + '\n')
    save()
    try:
        import torch
        state.update(phase='guarding-kitchen-import', xpu_initialized_before=torch.xpu.is_initialized())
        require(state['xpu_initialized_before'] is False, 'XPU already initialized')
        torch.set_num_threads(1)
        state['suppressed_availability_probes'] = []
        state['forbidden_device_calls'] = []
        def unavailable(name):
            def probe(*args, **kwargs):
                state['suppressed_availability_probes'].append(name)
                return False
            return probe
        def forbidden(name):
            def fail(*args, **kwargs):
                state['forbidden_device_calls'].append(name)
                raise AssertionError('Forbidden device access: ' + name)
            return fail
        for name in ('init', '_lazy_init', 'device_count', 'current_device', 'get_device_properties',
                     'get_device_name', 'get_device_capability', 'set_device'):
            if hasattr(torch.xpu, name):
                setattr(torch.xpu, name, forbidden('torch.xpu.' + name))
        for name in ('_xpu_init', '_xpu_getDeviceCount'):
            if hasattr(torch._C, name):
                setattr(torch._C, name, forbidden('torch._C.' + name))
        torch.xpu.is_available = unavailable('torch.xpu.is_available')
        torch.cuda.is_available = unavailable('torch.cuda.is_available')
        save()
        import comfy_kitchen
        require(not FAULT.exists(), 'Fault latch appeared during CPU import')
        source = LANE / 'scripts/ltx_na_axis_router.py'
        spec = importlib.util.spec_from_file_location('axis_router_under_test', source)
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        state['router_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        candidate = LANE / 'data/na-axis-cache-01/candidate-na.py'
        state['candidate_sha256'] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        router = adapter.install(candidate)
        state['phase'] = 'cpu-dispatch-lifecycle'
        save()
        def check(name):
            require(not FAULT.exists(), 'Fault latch appeared')
            state['checks'].append({'name': name, 'passed': True})
        def equal(a, b):
            return a.shape == b.shape and a.dtype == b.dtype and torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8))
        def expect_error(action):
            try:
                action()
            except Exception:
                return
            raise AssertionError('Expected rejection did not occur')
        shape = (1, 2, 3, 3, 1, 4)
        base = torch.arange(72, dtype=torch.float32, device='cpu').reshape(shape)
        q, k, v = [((base % n - 3) / 8).to(torch.bfloat16) for n in (7, 11, 13)]
        def call():
            return comfy_kitchen.na3d(q, k, v, [3, 3, 3], None, 1.0)
        with torch.inference_mode():
            reference = router.original(q, k, v, [3, 3, 3], None, 1.0)
            require(equal(call(), reference) and router._mode.get() is None, 'Default route differs')
            check('actual-custom-op-default-original')
            with router.scope('original', 'cpu-original', expected_calls=1) as original:
                require(equal(call(), reference), 'Scoped original differs')
            with router.scope('axis-cache', 'cpu-candidate', expected_calls=1) as cached:
                require(equal(call(), reference), 'Scoped candidate differs')
            require(original['scope_reset'] and cached['scope_reset'] and cached['calls'][0]['mode'] == 'axis-cache', 'Scope receipt differs')
            state['example_receipts'] = [original, cached]
            check('actual-custom-op-context-and-exact-bf16-output')
            with router.scope('axis-cache', 'cpu-outer', expected_calls=2) as outer:
                call()
                with router.scope('original', 'cpu-inner', expected_calls=1) as inner:
                    call()
                require(router._mode.get() is outer, 'Nested scope not restored')
                call()
            require(len(inner['calls']) == 1 and len(outer['calls']) == 2 and router._mode.get() is None, 'Nested receipts leaked')
            check('nested-token-restoration')
            worker_result = []
            def worker():
                try:
                    worker_result.append({'default_context': router._mode.get() is None, 'exact': equal(call(), reference)})
                except BaseException as error:
                    worker_result.append({'error': repr(error)})
            with router.scope('axis-cache', 'cpu-thread', expected_calls=1) as thread_receipt:
                thread = threading.Thread(target=worker, daemon=True)
                thread.start()
                thread.join(timeout=10)
                require(not thread.is_alive(), 'CPU worker exceeded bound')
                call()
            require(worker_result == [{'default_context': True, 'exact': True}] and len(thread_receipt['calls']) == 1, 'Scope leaked to thread')
            check('separate-thread-default-no-context-leak')
            failed = None
            try:
                with router.scope('axis-cache', 'cpu-exception', expected_calls=1) as failed:
                    call()
                    raise ValueError('synthetic decode failure')
            except ValueError:
                pass
            require(failed['status'] == 'failed' and failed['scope_reset'] and router._mode.get() is None, 'Exception leaked mode')
            require(equal(call(), reference), 'Original not restored after failure')
            check('exception-restores-default')
            def no_calls():
                with router.scope('axis-cache', 'cpu-missing'):
                    pass
            expect_error(no_calls)
            def wrong_count():
                with router.scope('axis-cache', 'cpu-wrong-count', expected_calls=2):
                    call()
            expect_error(wrong_count)
            check('missing-and-partial-coverage-rejected')
            invalid = None
            try:
                with router.scope('axis-cache', 'cpu-invalid', expected_calls=1) as invalid:
                    comfy_kitchen.na3d(q.reshape(1, -1), k, v, [3, 3, 3], None, 1.0)
            except Exception:
                pass
            require(invalid['status'] == 'failed' and invalid['calls'] == [] and router._mode.get() is None,
                    'Registry constraints bypassed or context leaked')
            check('actual-registry-rejects-invalid-shape-before-routing')
            expect_error(lambda: adapter.install(candidate))
            check('duplicate-installation-rejected')
            router.validate()
            require(router._registry_state() == router._baseline, 'Registry changed')
            check('constraints-priority-other-ops-unchanged')
            router.eager.na3d = router.original
            try:
                expect_error(router.validate)
            finally:
                router.eager.na3d = router.wrapper
            router.validate()
            check('late-router-ownership-change-rejected')
            saved_candidate = router.candidate
            router.candidate = router.original
            try:
                expect_error(router.validate)
            finally:
                router.candidate = saved_candidate
            router.validate()
            check('late-candidate-callable-change-rejected')
        require(not state['forbidden_device_calls'], 'Forbidden device entry was attempted')
        state['xpu_initialized_after'] = torch.xpu.is_initialized()
        require(state['xpu_initialized_after'] is False, 'CPU gate initialized XPU')
        state.update(status='passed-cpu-lifecycle', phase='complete',
            limitation='CPU-only registry availability probes were explicitly suppressed; no native XPU routing/quality/speed or VAEDecode node integration is qualified.')
        save()
        print(json.dumps({'status': state['status'], 'checks': len(state['checks']), 'output': str(args.output)}, indent=2))
    except BaseException as error:
        state.update(status='failed-unqualified', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    main()
