#!/usr/bin/env python3
"""Prove the host-read removal is exactly equivalent.

Loads the packet's original `ltx_na_axis_candidate` and the fixed successor, and
compares `_group_mask` bit-for-bit across many real window geometries on CPU.
No XPU, no ComfyUI, no server.
"""
import importlib.util, itertools, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
import torch

HERE = Path(__file__).resolve().parent
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-graph-capture-22')
ORIGINAL = PACKET / 'source/scripts/ltx_na_axis_candidate.py'
FIXED = HERE / 'ltx_na_axis_candidate_v2.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


a = load('na_original', ORIGINAL)
b = load('na_fixed', FIXED)
device = torch.device('cpu')
results, mismatches = [], []

for length, kernel, causal in itertools.product((1, 2, 3, 5, 8, 13, 16, 25, 32),
                                                (1, 2, 3, 4, 7, 8, 15, 16),
                                                (False, True)):
    starts, ends = a._window_bounds(length, kernel, causal)
    s2, e2 = b._window_bounds(length, kernel, causal)
    if (starts, ends) != (s2, e2):
        mismatches.append({'case': 'window_bounds', 'length': length, 'kernel': kernel, 'causal': causal})
        continue
    rel = tuple((tuple(starts), tuple(ends)) for _ in range(3))
    for dtype in (torch.bfloat16, torch.float32):
        ma = a._group_mask(rel, dtype, device, {})
        mb = b._group_mask(rel, dtype, device, {})
        view = (lambda t: t.view(torch.int16)) if dtype == torch.bfloat16 else (lambda t: t.view(torch.int32))
        same = ma.shape == mb.shape and torch.equal(view(ma), view(mb))
        results.append(same)
        if not same:
            mismatches.append({'case': '_group_mask', 'length': length, 'kernel': kernel,
                               'causal': causal, 'dtype': str(dtype)})

# The fixed version must never read a tensor back to size another tensor.
# Strip comments first: the explanatory comment names the pattern it removed.
code = '\n'.join(line.split('#', 1)[0] for line in FIXED.read_text().splitlines())
clean = 'int(en.max())' not in code and '.max())' not in code
still_present_in_original = 'int(en.max())' in '\n'.join(
    line.split('#', 1)[0] for line in ORIGINAL.read_text().splitlines())

# The cache now outlives a call, so a HIT must return exactly what a cold miss
# computes. Exercise both paths against the packet original.
# the persistent store now lives in na3d's keyword-only default
import inspect
_persist = inspect.signature(b.na3d).parameters['_axis_cache'].default
cache_results = []
for length, kernel, causal in itertools.product((3, 8, 16, 25), (2, 4, 8), (False, True)):
    starts, ends = b._window_bounds(length, kernel, causal)
    rel = tuple((tuple(starts), tuple(ends)) for _ in range(3))
    for dtype in (torch.bfloat16, torch.float32):
        view = (lambda t: t.view(torch.int16)) if dtype == torch.bfloat16 else (lambda t: t.view(torch.int32))
        cold = a._group_mask(rel, dtype, device, {})          # packet original, uncached
        shared = {}
        first = b._group_mask(rel, dtype, device, shared)      # fixed version, cold miss
        second = b._group_mask(rel, dtype, device, shared)     # fixed version, cache HIT
        third = b._group_mask(rel, dtype, device, _persist)
        fourth = b._group_mask(rel, dtype, device, _persist)
        cache_results.append(torch.equal(view(cold), view(first)) and
                             torch.equal(view(cold), view(second)) and
                             torch.equal(view(cold), view(third)) and
                             torch.equal(view(cold), view(fourth)))
        if not cache_results[-1]:
            mismatches.append({'case': 'persistent cache', 'length': length, 'kernel': kernel,
                               'causal': causal, 'dtype': str(dtype)})
bounded = len(_persist) <= 64 and all(
    t.numel() <= 4096 for t in _persist.values())

out = {'cache_comparisons': len(cache_results), 'cache_all_equal': all(cache_results),
       'persistent_cache_entries': len(_persist), 'cache_bounded': bounded,
       'comparisons': len(results), 'all_bitwise_equal': all(results) and not mismatches,
       'mismatches': mismatches[:10], 'host_read_removed_from_code': clean,
       'host_read_present_in_original': still_present_in_original,
       'uncached_path_exercised': True,
       'note': 'axis_cache passed empty every call, so the previously host-reading branch runs every time'}
print(json.dumps(out, indent=2))
sys.exit(0 if out['all_bitwise_equal'] and clean and out['cache_all_equal'] and out['cache_bounded'] else 1)
