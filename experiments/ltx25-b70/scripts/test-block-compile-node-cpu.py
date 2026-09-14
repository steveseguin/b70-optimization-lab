#!/usr/bin/env python3
"""CPU unit checks of the inactive facade; compiler/route/context are explicit spies."""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
import types

os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', TORCHINDUCTOR_COMPILE_THREADS='1')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise FileExistsError(args.output)
source = Path(__file__).with_name('block_compile_node.py')
report = {'scope': 'CPU facade unit tests; fake compiler/route/context, no Comfy model or XPU execution',
          'passed': False, 'checks': [], 'sha256s': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (source, Path(__file__))}}
try:
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    sys.modules['ltx_block_compile'] = types.ModuleType('ltx_block_compile')
    diag = types.ModuleType('encoder_diagnostics')
    diag._context = lambda: None
    sys.modules['encoder_diagnostics'] = diag
    spec = importlib.util.spec_from_file_location('node_under_test', source)
    node = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(node)
    node.counters = defaultdict(Counter)
    node.census = lambda route: {'unit_spy': True}

    def check(name, condition):
        assert condition, name
        report['checks'].append(name)

    def rejects(name, function):
        try:
            function()
        except RuntimeError:
            report['checks'].append(name)
        else:
            raise AssertionError(name)

    def inputs(n=2):
        return (torch.zeros((1, n, 4), dtype=torch.bfloat16),
                torch.full((1, 3, 2), 2., dtype=torch.bfloat16))

    class Route:
        def __init__(self, bad=False):
            self.native_calls = self.compiled_calls = 0
            self.seen = set()
            self.bad = bad
            self.block = self.native
        def _validate_execution(self):
            pass
        def native(self, x, **kwargs):
            self.native_calls += 1
            for t in x:
                t.add_(1)
            return x
        def compiled(self, x, **kwargs):
            self.compiled_calls += 1
            key = tuple(x[0].shape)
            if key not in self.seen:
                self.seen.add(key)
                node.counters['stats']['unique_graphs'] += 1
            for t in x:
                t.add_(2 if self.bad else 1)
            return x

    with tempfile.TemporaryDirectory(prefix='ltx-facade-cpu-') as temporary, torch.no_grad():
        root = Path(temporary)
        identity = {'run_name': 'unit', 'block_index': 24}
        route = Route()
        gate = node._Gate(route)
        gate.begin(root, identity)
        for i in range(11):
            x = inputs(2 if i < 8 else 4)
            result = gate(x, transformer_options={'unit': 'metadata remains present'})
            assert result is x and bool((x[0] == 1).all()) and bool((x[1] == 3).all())
        check('in_place_result_matches_one_native_execution', True)
        check('two_stage_independent_eager_and_repeat_only_once', route.native_calls == 2 and route.compiled_calls == 13)
        rows = [json.loads(p.read_text()) for p in sorted(root.glob('call-*.json'))]
        check('eleven_exclusive_passed_receipts', len(rows) == 11 and all(r['passed'] for r in rows))
        check('two_stage_qualifications_calls1_and9', [r['call'] for r in rows if r['stage_check']] == [1, 9])
        check('two_qualified_stage_graphs', rows[-1]['qualified_stage_count'] == 2 and rows[-1]['counter_delta']['stats']['unique_graphs'] == 2)
        warm = root / 'warm'; warm.mkdir()
        gate.begin(warm, identity)
        gate(inputs(2))
        check('warm_call_skips_eager_and_repeat', route.native_calls == 2 and route.compiled_calls == 14)
        rejects('reject_new_request_before11_calls', lambda: gate.begin(root, identity))
        rejects('reject_stream_aliases', lambda: node.independent_streams((x[0], x[0])))
        signed = node.exact_pair((torch.tensor([0.]), torch.tensor([1.])),
                                 (torch.tensor([-0.]), torch.tensor([1.])))
        check('signed_zero_bit_difference_detected', not signed[0]['bitwise_equal'])
        nan = node.exact_pair((torch.tensor([float('nan')]), torch.tensor([1.])),
                              (torch.tensor([float('nan')]), torch.tensor([1.])))
        check('matching_nan_is_not_qualified', not nan[0]['finite'])
        rejects('reject_third_compiler_graph', lambda: node.check_counters({'stats': {'unique_graphs': 3}}))
        rejects('reject_graph_break', lambda: node.check_counters({'graph_break': {'unit': 1}}))
        bad_dir = root / 'bad'; bad_dir.mkdir()
        bad = node._Gate(Route(bad=True)); bad.begin(bad_dir, identity)
        rejects('reject_numerical_mismatch', lambda: bad(inputs(2)))
        failed = json.loads((bad_dir / 'call-01.json').read_text())
        check('failed_comparison_evidence_preserved', not failed['passed'] and
              failed['eager_vs_compiled'][0]['bitwise_equal'] is False and bad.failed and node._failed)
    report['passed'] = True
except BaseException:
    report['error'] = traceback.format_exc()
    raise
finally:
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
