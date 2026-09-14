#!/usr/bin/env python3
"""Prepare an inactive one-line mask-extent patch; stdlib source checks only."""
import argparse
import ast
import copy
import difflib
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct
import sys

SOURCE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen/backends/eager/na.py')
BEFORE = 'torch.arange(int(en.max()), device=device)'
AFTER = 'torch.arange(max(ends), device=device)'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(source, output):
    original = source.read_bytes()
    text = original.decode()
    if text.count(BEFORE) != 1:
        raise ValueError('expected exactly one original scalar-readback expression')
    changed = text.replace(BEFORE, AFTER)
    tree, candidate = ast.parse(text), ast.parse(changed)
    # Prove the AST differs only at the specific _group_mask arange argument.
    target = next(n for n in candidate.body if isinstance(n, ast.FunctionDef) and n.name == '_group_mask')
    replacements = 0
    for node in ast.walk(target):
        if isinstance(node, ast.Call) and ast.unparse(node) == AFTER:
            node.args[0] = ast.parse('int(en.max())', mode='eval').body
            replacements += 1
    if replacements != 1 or ast.dump(candidate) != ast.dump(tree):
        raise ValueError('candidate changes more than the declared extent expression')

    # Extract only integer geometry from the pinned source, without executing
    # imports, annotations, decorators, tensor operations or custom-op setup.
    names = ('_window_bounds', '_pick_tiles')
    functions = [copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    geometry = copy.deepcopy(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'na3d'))
    geometry.name = 'geometry_groups'
    geometry.decorator_list = []
    geometry.returns = None
    for arg in geometry.args.args:
        arg.annotation = None
    stop = next(i for i, n in enumerate(geometry.body)
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'out' for t in n.targets))
    geometry.body = geometry.body[:stop] + [ast.Return(value=ast.Name(id='groups', ctx=ast.Load()))]
    module = ast.fix_missing_locations(ast.Module(body=functions + [geometry], type_ignores=[]))
    namespace = {'math': math, 'NA_SCORE_BUDGET': 2**25}
    exec(compile(module, str(source) + ':integer-geometry-only', 'exec'), namespace)

    axes, windows = 0, 0
    for length, kernel, causal in itertools.product((1, 2, 3, 5, 7, 11, 16, 25, 32),
                                                   (1, 2, 3, 5, 7, 11, 32, 40), (False, True)):
        starts, ends = namespace['_window_bounds'](length, kernel, causal)
        for begin in range(length):
            for end in range(begin + 1, length + 1):
                relative = tuple(x - starts[begin] for x in ends[begin:end])
                # Signed int64 serialization checks exact representability.
                # Independent reduction over reconstructed integer values.
                packed = struct.pack('<' + 'q' * len(relative), *relative)
                reconstructed = struct.unpack('<' + 'q' * len(relative), packed)
                maximum = reconstructed[0]
                for value in reconstructed[1:]:
                    if value > maximum:
                        maximum = value
                if max(relative) != maximum or not all(0 < v < 2**63 for v in relative):
                    raise ValueError('extent representability/equality failure')
                windows += 1
        axes += 1

    class ShapeOnly:
        def __init__(self, dims):
            self.shape = (1, *dims, 1, 64)
            self.device = 'not-a-runtime-device'

    # These are source-derived untiled full-decoder shapes for latent [4,8,8]
    # with default padding/upscales. Actual runtime tiling is not attested here.
    stages = [((6, 8, 8), (3, 7, 7), 4), ((6, 16, 16), (3, 7, 7), 6),
              ((11, 16, 16), (3, 5, 5), 4), ((21, 32, 32), (3, 5, 5), 2),
              ((25, 64, 64), (11, 11, 11), 8)]
    rows = []
    for dims, kernels, depth in stages:
        groups = namespace['geometry_groups'](ShapeOnly(dims), None, None, kernels, None, 1.0)
        for relative in groups:
            for starts, ends in relative:
                if not ends or any(type(x) is not int for x in ends) or max(ends) >= 2**63:
                    raise ValueError('actual source geometry violates extent assumptions')
        rows.append({'dimensions': dims, 'kernels': kernels, 'depth_assumption': depth,
                     'geometry_groups_per_block': len(groups),
                     'removed_scalar_readback_calls_per_block': 3 * len(groups),
                     'tiles_per_block': sum(map(len, groups.values()))})

    patch = ''.join(difflib.unified_diff(text.splitlines(keepends=True), changed.splitlines(keepends=True),
                                      fromfile='a/comfy_kitchen/backends/eager/na.py',
                                      tofile='b/comfy_kitchen/backends/eager/na.py'))
    report = {'schema': 'ltx25.na-mask-extent-source-candidate.v1',
              'status': 'source-checks-passed-runtime-unqualified',
              'source_path': str(source), 'original_sha256': digest(original),
              'candidate_sha256': digest(changed.encode()), 'patch_sha256': digest(patch.encode()),
              'preparer_sha256': digest(Path(__file__).read_bytes()),
              'only_changed_expression': {'before': BEFORE, 'after': AFTER},
              'axis_configurations_checked': axes, 'nonempty_axis_subranges_checked': windows,
              'integer_extent_parity': True, 'ast_delta_only_declared_expression': True,
              'source_derived_untiled_stages': rows,
              'assumed_full_decoder_removed_scalar_readbacks': sum(r['removed_scalar_readback_calls_per_block'] *
                                                                  r['depth_assumption'] for r in rows),
              'torch_imported': 'torch' in sys.modules, 'native_mask_parity_tested': False,
              'native_attention_parity_tested': False, 'full_clip_parity_tested': False,
              'timing_measured': False, 'live_source_modified': False,
              'limitations': ['integer/source checks only; native execution pending',
                              'stage dimensions assume default full untiled decoder; not a runtime trace',
                              'removed scalar reads are source counts, not measured synchronization durations',
                              'finite int64 nonempty ends from current na3d grouping are required']}
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in [('original-na.py', original), ('candidate-na.py', changed.encode()),
                      ('remove-mask-extent-readback.patch', patch.encode()),
                      ('source-checks.json', (json.dumps(report, indent=2) + '\n').encode())]:
        with (output / name).open('xb') as stream:
            stream.write(raw)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    print(json.dumps(prepare(args.source, args.output), indent=2))


if __name__ == '__main__':
    main()
