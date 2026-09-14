#!/usr/bin/env python3
"""CPU-only native activation layout and graph-preservation checks; no XPU use."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json').exists():
        raise RuntimeError('Existing host fault; no native imports')
    import torch
    import torch.nn.functional as F
    import ltx_native_activations_backend as candidate
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True, warn_only=False)
    checks = []
    def check(name, condition):
        if not condition:
            raise RuntimeError(name)
        checks.append(name)
    def rejects(name, fn):
        try:
            fn()
        except RuntimeError:
            checks.append(name)
        else:
            raise RuntimeError('Expected rejection: ' + name)
    with torch.inference_mode():
        for dtype in (torch.bfloat16, torch.float32):
            x = torch.linspace(-20, 20, 1024, dtype=dtype).reshape(1, 32, 32)
            for kind, op, ref, fake in (
                ('sigmoid', candidate.native_sigmoid, torch.sigmoid, candidate._fake_native_sigmoid),
                ('gelu', lambda x: candidate.native_gelu(x, 'tanh'),
                 lambda x: F.gelu(x, approximate='tanh'), lambda x: candidate._fake_native_gelu(x, 'tanh'))):
                got, expected, repeated, abstract = op(x), ref(x), op(x), fake(x)
                check(f'{kind}-{dtype}-exact-repeat', torch.equal(got.view(torch.uint8), expected.view(torch.uint8)) and torch.equal(got.view(torch.uint8), repeated.view(torch.uint8)))
                check(f'{kind}-{dtype}-layout-no-alias', got.stride() == abstract.stride() == expected.stride() and got.shape == abstract.shape == x.shape and got.dtype == abstract.dtype == x.dtype and got.device == abstract.device == x.device and got.data_ptr() != x.data_ptr() and abstract.data_ptr() not in (got.data_ptr(), x.data_ptr()))
            rejects(f'noncontiguous-{dtype}', lambda: candidate.native_sigmoid(x.transpose(1, 2)))
        rejects('unsupported-dtype', lambda: candidate.native_sigmoid(torch.ones(8, dtype=torch.float64)))
        rejects('unsupported-gelu-approximation', lambda: candidate.native_gelu(torch.ones(8), 'none'))

        class Fixture(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.weight = torch.nn.Parameter(torch.ones(32, dtype=torch.bfloat16))
            def forward(self, x):
                normalized = F.rms_norm(x, (32,), self.weight, 1e-5)
                return torch.sigmoid(normalized) + F.gelu(normalized, approximate='tanh')
        gm = torch.fx.symbolic_trace(Fixture())
        code = gm.code
        identities = {name: id(value) for name, value in gm.named_parameters()}
        rms_graph, rms_sites = candidate.rms.rewrite_rms(gm, expected_count=1)
        after, sites = candidate.rewrite_activations(rms_graph, expected_activation_counts={'sigmoid': 1, 'gelu': 1})
        check('original-graph-preserved', gm.code == code)
        check('parameter-identities-preserved-through-both-copies', identities == {name: id(value) for name, value in rms_graph.named_parameters()} == {name: id(value) for name, value in after.named_parameters()})
        check('replacement-counts', len(rms_sites) == 1 and [r['kind'] for r in sites] == ['sigmoid', 'gelu'])
        x = torch.linspace(-3, 3, 64, dtype=torch.bfloat16).reshape(2, 32)
        check('rewritten-graph-exact', torch.equal(gm(x).view(torch.uint8), after(x).view(torch.uint8)))
        rejects('count-mismatch', lambda: candidate.rewrite_activations(rms_graph))
        for label, args_value, kwargs_value in (
                ('missing-input', (), {}), ('duplicate-input', ('INPUT',), {'input': 'INPUT'}),
                ('unknown-keyword', ('INPUT',), {'other': 1})):
            graph = torch.fx.Graph()
            xnode = graph.placeholder('x')
            arguments = tuple(xnode if x == 'INPUT' else x for x in args_value)
            keywords = {k: xnode if v == 'INPUT' else v for k, v in kwargs_value.items()}
            out = graph.call_function(torch.sigmoid, arguments, keywords)
            graph.output(out)
            module = torch.fx.GraphModule({}, graph)
            rejects(label, lambda: candidate.rewrite_activations(module, expected_activation_counts={'sigmoid': 1, 'gelu': 0}))
        graph = torch.fx.Graph(); xnode = graph.placeholder('x')
        out = graph.call_function(F.gelu, (xnode,), {'approximate': 'none'}); graph.output(out)
        module = torch.fx.GraphModule({}, graph)
        rejects('FX-wrong-gelu-approximation', lambda: candidate.rewrite_activations(module, expected_activation_counts={'sigmoid': 0, 'gelu': 1}))
    report = {'scope': 'CPU graph/alias/layout/signature guards, no Inductor or XPU qualification',
              'passed': True, 'checks': checks, 'count': len(checks), 'torch': str(torch.__version__),
              'backend_sha256': hashlib.sha256(Path(candidate.__file__).read_bytes()).hexdigest(),
              'rms_dependency_sha256': candidate.RMS_BACKEND_SHA256,
              'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with args.output.open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps({'passed': True, 'checks': len(checks)}))


if __name__ == '__main__':
    main()
