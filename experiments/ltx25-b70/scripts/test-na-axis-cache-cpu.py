#!/usr/bin/env python3
"""Exact CPU mask/attention and invocation-local cache tests; no GPU path."""
import argparse
import ast
import gc
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import weakref

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
PACKET = LANE / 'data/na-axis-cache-01'
FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_fault():
    require(not FAULT.exists(), 'Fault latch: stop before native work')


def load_functions(source, torch):
    tree = ast.parse(source)
    wanted = ('_window_bounds', '_pick_tiles', '_group_mask', 'na3d')
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    require(len(nodes) == 4, 'Missing source functions')
    constants = {}  # Production constants checked without executing imports.
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in (
                'NA_SCORE_BUDGET', 'NA_KV_STACK_BUDGET'):
            constants[n.targets[0].id] = eval(compile(ast.Expression(n.value), '<constant>', 'eval'),
                                             {'__builtins__': {}})
    require(constants == {'NA_SCORE_BUDGET': 2**25, 'NA_KV_STACK_BUDGET': 2**28}, 'Budget changed')
    ns = {'torch': torch, 'functional': torch.nn.functional, 'math': math, **constants}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 '<saved-na-functions>', 'exec'), ns)
    return ns


def run():
    check_fault()
    source_receipt = json.loads((PACKET / 'source-receipt.json').read_text())
    sources = [(PACKET / (name + '-na.py')).read_bytes() for name in ('original', 'candidate')]
    for name, raw in zip(('original', 'candidate'), sources):
        require(digest(raw) == source_receipt[name + '_sha256'], 'Saved source hash differs')
    import torch
    check_fault()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True, warn_only=False)
    original, candidate = [load_functions(raw.decode(), torch) for raw in sources]
    cpu = torch.device('cpu')
    checks = []

    def same(a, b):
        return (a.shape == b.shape and a.dtype == b.dtype and a.device == b.device and
                torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)))

    def rel(dims, kernels, causal, ranges=None):
        result = []
        for i, (d, k, c) in enumerate(zip(dims, kernels, causal)):
            starts, ends = original['_window_bounds'](d, k, c)
            lo, hi = (0, d) if ranges is None else ranges[i]
            origin = starts[lo]
            result.append((tuple(x - origin for x in starts[lo:hi]),
                           tuple(x - origin for x in ends[lo:hi])))
        return tuple(result)

    with torch.inference_mode():
        geometries = [
            ((1, 1, 1), (1, 1, 1), (False, False, False), None),
            ((3, 4, 4), (3, 3, 3), (False, False, False), None),
            ((3, 4, 5), (7, 8, 9), (False, False, False), ((1, 3), (0, 3), (2, 5))),
            ((4, 4, 4), (2, 3, 4), (True, False, True), None),
            ((3, 4, 5), (2, 4, 4), (True, True, True), ((0, 3), (1, 4), (2, 5))),
        ]
        for case, args in enumerate(geometries):
            bounds, cache = rel(*args), {}
            for dtype in (torch.bfloat16, torch.float32):
                expected = original['_group_mask'](bounds, dtype, cpu)
                got = candidate['_group_mask'](bounds, dtype, cpu, cache)
                repeated = candidate['_group_mask'](bounds, dtype, cpu, cache)
                require(same(expected, got) and same(got, repeated), 'Mask bytes differ')
                require(got.data_ptr() != repeated.data_ptr(), 'Additive mask unexpectedly cached')
                snapshot = {key: value.clone() for key, value in cache.items()}
                got.fill_(123)
                require(all(same(value, snapshot[key]) for key, value in cache.items()), 'Returned mask aliases cache')
                require(same(expected, candidate['_group_mask'](bounds, dtype, cpu, cache)), 'Mutation poisoned geometry')
                require(all(value.dtype == torch.bool and value.device.type == 'cpu'
                            for value in cache.values()), 'Cache dtype/device differs')
            checks.append({'case': 'mask-boundary-dtype-mutation', 'index': case, 'passed': True})

        # Repeated identical axes share one bool tensor; device-qualified keys
        # stay distinct even for CPU aliases. This does not qualify XPU placement.
        bounds = rel((3, 3, 3), (3, 3, 3), (False, False, False))
        cache = {}
        candidate['_group_mask'](bounds, torch.float32, cpu, cache)
        require(len(cache) == 1, 'Same geometry on distinct axes was not reused')
        candidate['_group_mask'](bounds, torch.bfloat16, torch.device('cpu:0'), cache)
        require(len(cache) == 2, 'Device keys were not separated')
        checks.append({'case': 'identical-axes-device-key', 'passed': True})

        # Every added entry is small, with no eviction or persistent global state.
        cache = {}
        singleton = ((0,), (1,))
        for size in range(1, 81):
            candidate['_group_mask']((((0,), (size,)), singleton, singleton), torch.float32, cpu, cache)
        require(len(cache) == 64 and sum(v.numel() * v.element_size() for v in cache.values()) <= 262144,
                'Cache capacity exceeded')
        large_cache = {}
        candidate['_group_mask']((((0,), (4097,)), singleton, singleton), torch.float32, cpu, large_cache)
        require(all(v.numel() <= 4096 for v in large_cache.values()), 'Oversized axis was retained')
        checks.append({'case': '64-entry-4096-element-bounds', 'passed': True})

        cases = [((1, 1, 1), (1, 1, 1), None, None),
                 ((2, 3, 3), (3, 3, 3), None, 1.0),
                 ((3, 4, 5), (7, 8, 9), [False, False, False], 0.75),
                 ((3, 4, 5), (2, 3, 4), [True, False, True], None)]
        for dtype in (torch.bfloat16, torch.float32):
            for case, (dims, kernels, causal, scale) in enumerate(cases):
                for budget in (2**25, 64):
                    # A separately labelled tiny budget exercises the real tiled
                    # loop on small CPU tensors; the saved candidate stays native.
                    shape = (1, *dims, 2, 4)
                    values = torch.arange(math.prod(shape), dtype=torch.float32).reshape(shape)
                    q, k, v = [((values % mod - 3) / 8).to(dtype) for mod in (7, 11, 13)]
                    before = [x.clone() for x in (q, k, v)]
                    traces, outputs, axes = [], [], []
                    for impl in (original, candidate, candidate):
                        check_fault()
                        trace = []
                        def sdpa(a, b, c, **kwargs):
                            trace.append(([x.clone() for x in (a, b, c, kwargs['attn_mask'])],
                                          {key: value for key, value in kwargs.items() if key != 'attn_mask'}))
                            return torch.nn.functional.scaled_dot_product_attention(a, b, c, **kwargs)
                        impl['functional'] = SimpleNamespace(scaled_dot_product_attention=sdpa)
                        impl['NA_SCORE_BUDGET'] = budget
                        group_mask = impl['_group_mask']
                        def capture_cache(*args):
                            mask = group_mask(*args)
                            if len(args) == 4:
                                axes.extend(weakref.ref(tensor) for tensor in args[3].values())
                            return mask
                        impl['_group_mask'] = capture_cache
                        try:
                            outputs.append(impl['na3d'](q, k, v, list(kernels), causal, scale))
                        finally:
                            impl['_group_mask'] = group_mask
                            impl['functional'] = torch.nn.functional
                            impl['NA_SCORE_BUDGET'] = 2**25
                        traces.append(trace)
                    require(same(outputs[0], outputs[1]) and same(outputs[1], outputs[2]), 'Attention output differs')
                    require(all(torch.isfinite(x).all() for x in outputs), 'Nonfinite attention')
                    require(all(same(a, b) for a, b in zip(before, (q, k, v))), 'Input mutated')
                    for trace in traces[1:]:
                        require(len(trace) == len(traces[0]), 'SDPA call count changed')
                        for (ta, ka), (tb, kb) in zip(traces[0], trace):
                            require(ka == kb and all(same(a, b) for a, b in zip(ta, tb)), 'SDPA inputs/order changed')
                    gc.collect()
                    require(axes and all(ref() is None for ref in axes), 'Axis tensor escaped invocation')
                    checks.append({'case': 'attention-exact-inputs-order-release', 'index': case,
                        'dtype': str(dtype), 'tile_budget': budget, 'sdpa_calls': len(traces[0]), 'passed': True})
    check_fault()
    require(not torch.xpu.is_initialized(), 'Unexpected XPU initialization')
    require(digest(Path(source_receipt['source_path']).read_bytes()) == source_receipt['original_sha256'],
            'Installed source changed during test')
    return {'status': 'cpu-exact-parity-and-cache-lifecycle-passed', 'passed': True,
        'checks': checks, 'check_count': len(checks), 'torch_version': str(torch.__version__),
        'xpu_initialized': False, 'strict_enabled': torch.are_deterministic_algorithms_enabled(),
        'strict_warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
        'original_sha256': source_receipt['original_sha256'],
        'candidate_sha256': source_receipt['candidate_sha256'],
        'driver_sha256': digest(Path(__file__).read_bytes()),
        'limitations': ['CPU only; no native decoder/full-clip or performance qualification',
                        '64-element test tile budget is fixture-only; production budgets unchanged',
                        'Device alias test does not prove XPU or cross-stream behavior'],
        'installed_source_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Receipt already exists')
    receipt = run()
    with args.output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: value for key, value in receipt.items() if key != 'checks'}, indent=2))
