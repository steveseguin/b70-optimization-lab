#!/usr/bin/env python3
"""Small CPU operator/rewrite/Inductor gate; no model load or GPU operations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if FAULT.exists():
        raise RuntimeError('Fault latch prohibits native testing')
    args.output.mkdir(parents=True)
    os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', TORCHINDUCTOR_COMPILE_THREADS='1',
                      TORCHINDUCTOR_CACHE_DIR=str(args.output.resolve() / 'inductor-cache'),
                      TRITON_CACHE_DIR=str(args.output.resolve() / 'triton-cache'))
    report = {'scope': 'CPU RMS operator, FX rewrite and small compiled computation only',
              'passed': False, 'xpu_tested': False, 'full_native_block_tested': False, 'rows': [], 'checks': []}
    try:
        import torch
        import torch.nn.functional as F
        import ltx_native_rms_backend as candidate
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)
        report['torch'] = str(torch.__version__)
        report['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (Path(__file__), Path(candidate.__file__))}
        report['determinism'] = {'enabled': torch.are_deterministic_algorithms_enabled(),
                                 'warn_only': torch.is_deterministic_algorithms_warn_only_enabled()}

        def check(condition, name):
            if not condition:
                raise RuntimeError(name)
            report['checks'].append(name)

        def exact(a, b):
            return (a.shape == b.shape and a.dtype == b.dtype and a.stride() == b.stride()
                    and torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)))

        with torch.inference_mode():
            for dtype in (torch.bfloat16, torch.float32):
                for width in (32, 2048, 4096):
                    gen = torch.Generator().manual_seed(17 + width)
                    x = torch.randn(2, 4, width, generator=gen).to(dtype)
                    weight = torch.randn(width, generator=gen).to(dtype)
                    for weighted, eps in ((False, None), (False, 1e-6), (True, 1e-5)):
                        w = weight if weighted else None
                        original = F.rms_norm(x, (width,), w, eps)
                        got = candidate.native_rms(x, [width], w, eps)
                        repeat = candidate.native_rms(x, [width], w, eps)
                        check(exact(original, got) and exact(got, repeat), f'native-{dtype}-{width}-{weighted}-{eps}')
                        check(got.data_ptr() != x.data_ptr(), f'no-alias-{dtype}-{width}-{weighted}-{eps}')
            try:
                candidate.native_rms(torch.ones(3, 4).t(), [3], None, 1e-6)
            except RuntimeError:
                report['checks'].append('reject-noncontiguous-input')
            else:
                raise RuntimeError('noncontiguous input accepted')

            class Weighted(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.weight = torch.nn.Parameter(torch.ones(32), requires_grad=False)

            graph = torch.fx.Graph()
            x = graph.placeholder('x')
            w = graph.get_attr('weight')
            y = graph.call_function(torch.rms_norm, (x, (32,), w), {'eps': 1e-5})
            graph.output(y)
            original_gm = torch.fx.GraphModule(Weighted(), graph)
            original_code = original_gm.code
            rewritten, census = candidate.rewrite_rms(original_gm, expected_count=1)
            check(original_gm.code == original_code, 'original-graph-unchanged')
            check(rewritten.weight is original_gm.weight, 'parameter-object-preserved')
            check(census[0]['eps'] == 1e-5 and census[0]['weighted'], 'weight-and-epsilon-preserved')
            sample = torch.randn(2, 32)
            check(exact(original_gm(sample), rewritten(sample)), 'rewritten-weighted-graph-exact')
            try:
                candidate.rewrite_rms(original_gm, expected_count=2)
            except RuntimeError:
                report['checks'].append('reject-wrong-site-count')
            else:
                raise RuntimeError('site census mismatch accepted')
            empty = torch.fx.Graph()
            placeholder = empty.placeholder('x')
            empty.output(placeholder)
            try:
                candidate.rewrite_rms(torch.fx.GraphModule({}, empty))
            except RuntimeError:
                report['checks'].append('reject-zero-sites')
            else:
                raise RuntimeError('zero RMS sites accepted')

            def computation(x, weight):
                a = F.rms_norm(x * 1.25, (x.shape[-1],), weight, 1e-5)
                b = F.rms_norm(a + 0.125, (x.shape[-1],), None, 1e-6)
                return b * 0.75

            options = {'compile_threads': 1, 'emulate_precision_casts': True,
                       'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
                       'max_autotune': False, 'max_autotune_gemm': False}
            backend = candidate.make_backend(options, args.output / 'graphs', expected_count=2)
            compiled = torch.compile(computation, backend=backend, fullgraph=True, dynamic=False)
            for width in (32, 2048, 4096):
                if FAULT.exists():
                    raise RuntimeError('Fault appeared during CPU gate')
                gen = torch.Generator().manual_seed(width)
                x = torch.randn(2, width, generator=gen).to(torch.bfloat16)
                weight = torch.randn(width, generator=gen).to(torch.bfloat16)
                expected = computation(x, weight)
                actual, repeat = compiled(x, weight), compiled(x, weight)
                passed = exact(expected, actual) and exact(actual, repeat)
                report['rows'].append({'width': width, 'exact': passed,
                                       'finite': bool(torch.isfinite(actual).all()),
                                       'output_sha256': hashlib.sha256(actual.view(torch.uint8).numpy().tobytes()).hexdigest()})
                check(passed and report['rows'][-1]['finite'], f'compiled-exact-{width}')
        report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
        report['traceback'] = traceback.format_exc()
    finally:
        with (args.output / 'receipt.json').open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    print(json.dumps({'passed': report['passed'], 'checks': len(report['checks']), 'error': report.get('error')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
