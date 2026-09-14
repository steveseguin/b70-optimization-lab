#!/usr/bin/env python3
"""Prepare a separate inactive per-call NA geometry cache; stdlib only."""
import argparse
import ast
import copy
import difflib
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen/backends/eager/na.py')
PIN = '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def candidate(text):
    old = '''        st = torch.tensor(starts, device=device)
        en = torch.tensor(ends, device=device)
        kj = torch.arange(int(en.max()), device=device)
        bools.append((kj[None, :] >= st[:, None]) & (kj[None, :] < en[:, None]))'''
    new = '''        # The cache belongs to this na3d invocation, never to model state.
        # Axis visibility is bool and independent of the additive mask dtype.
        key = (starts, ends, device) if axis_cache is not None else None
        axis = axis_cache.get(key) if axis_cache is not None else None
        if axis is None:
            st = torch.tensor(starts, device=device)
            en = torch.tensor(ends, device=device)
            kj = torch.arange(int(en.max()), device=device)
            axis = (kj[None, :] >= st[:, None]) & (kj[None, :] < en[:, None])
            # At most64 entries of4096 bool elements:256KiB tensor storage.
            # Oversized axes still execute the original uncached operations.
            if axis_cache is not None and len(axis_cache) < 64 and axis.numel() <= 4096:
                axis_cache[key] = axis
        bools.append(axis)'''
    changes = [
        ('def _group_mask(rel_bounds, dtype, device):',
         'def _group_mask(rel_bounds, dtype, device, axis_cache=None):'),
        (old, new),
        ('    out = torch.empty((batch, t, h, w, nh, hd), device=device, dtype=v.dtype)',
         '    axis_cache = {}  # Invocation-local, read-only geometry; released on return.\n'
         '    out = torch.empty((batch, t, h, w, nh, hd), device=device, dtype=v.dtype)'),
        ('mask = _group_mask(rel, q.dtype, device)',
         'mask = _group_mask(rel, q.dtype, device, axis_cache)'),
    ]
    result = text
    for before, after in changes:
        if result.count(before) != 1:
            raise ValueError('Pinned source context differs')
        result = result.replace(before, after, 1)
    # Independent AST equality after reversing only the approved substitutions.
    restored = result
    for before, after in reversed(changes):
        restored = restored.replace(after, before, 1)
    if ast.dump(ast.parse(restored)) != ast.dump(ast.parse(text)):
        raise ValueError('Unexpected AST delta')
    return result


def geometry_report(text):
    tree = ast.parse(text)
    nodes = [copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ('_window_bounds', '_pick_tiles')]
    f = copy.deepcopy(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'na3d'))
    f.name, f.returns = 'geometry', None
    for arg in f.args.args:
        arg.annotation = None
    stop = next(i for i, n in enumerate(f.body) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'out' for t in n.targets))
    f.body = f.body[:stop] + [ast.Return(ast.Name('groups', ast.Load()))]
    namespace = {'math': math, 'NA_SCORE_BUDGET': 2**25}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes + [f], type_ignores=[])),
                 'integer-geometry-only', 'exec'), namespace)
    rows = []
    for dims, kernels, depth in [((6, 8, 8), (3, 7, 7), 4),
            ((6, 16, 16), (3, 7, 7), 6), ((11, 16, 16), (3, 5, 5), 4),
            ((21, 32, 32), (3, 5, 5), 2), ((25, 64, 64), (11, 11, 11), 8)]:
        q = SimpleNamespace(shape=(1, *dims, 1, 64), device='geometry-only')
        groups = namespace['geometry'](q, None, None, kernels, None, 1.0)
        axes = {axis for group in groups for axis in group}
        costs = [len(starts) * max(ends) for starts, ends in axes]
        rows.append({'dimensions': dims, 'kernels': kernels, 'blocks': depth,
            'is_causal': None, 'groups': len(groups), 'uncached_axis_builds': 3 * len(groups),
            'cached_axis_builds': len(axes), 'axis_tensor_bytes': sum(costs),
            'max_axis_tensor_bytes': max(costs),
            'full_bf16_masks_if_all_retained_bytes': sum(
                2 * math.prod(len(s) for s, e in group) * math.prod(max(e) for s, e in group)
                for group in groups)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = SOURCE.read_bytes()
    if sha(original) != PIN:
        raise ValueError('Installed source differs from reviewed original')
    changed = candidate(original.decode()).encode()
    patch = ''.join(difflib.unified_diff(original.decode().splitlines(True),
        changed.decode().splitlines(True), fromfile='a/comfy_kitchen/backends/eager/na.py',
        tofile='b/comfy_kitchen/backends/eager/na.py')).encode()
    rows = geometry_report(original.decode())
    receipt = {'status': 'prepared-inactive-native-unqualified', 'original_sha256': sha(original),
        'candidate_sha256': sha(changed), 'patch_sha256': sha(patch),
        'preparer_sha256': sha(Path(__file__).read_bytes()), 'source_path': str(SOURCE),
        'source_derived_untiled_stages_not_runtime_shapes': rows,
        'assumed_decoder_axis_builds_original': sum(r['blocks'] * r['uncached_axis_builds'] for r in rows),
        'assumed_decoder_axis_builds_candidate': sum(r['blocks'] * r['cached_axis_builds'] for r in rows),
        'cache_scope': 'one na3d call; no cross-call or generated-output reuse',
        'max_cache_tensor_bytes': 64 * 4096, 'max_cache_entries': 64,
        'unchanged': ['q/k/v operations', 'SDPA arguments/order', 'full mask allocation/fill',
                      'mask miss arithmetic including extent scalar readback', 'tile budgets/grouping'],
        'live_source_modified': False, 'native_or_speed_claim': False}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in [('original-na.py', original), ('candidate-na.py', changed),
            ('delta.patch', patch), ('source-receipt.json', (json.dumps(receipt, indent=2) + '\n').encode())]:
        with (args.output / name).open('xb') as stream:
            stream.write(data)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
