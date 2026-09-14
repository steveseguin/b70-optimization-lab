#!/usr/bin/env python3
"""Small matched CPU dispatcher experiment; gives no XPU speed prediction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), 'Output must be new')
    report = {'schema': 'ltx.private-cpp-operators-cpu-timing.v1', 'status': 'started', 'rows': [],
        'scope': 'Synchronous CPU operator+Python dispatch only; no XPU/kernel/model/clip/streaming speed inference',
        'script_sha256': sha(Path(__file__)), 'qualification_sha256': sha(args.qualification), 'command': sys.argv}
    try:
        require(not FAULT.exists(), 'Fault latch prohibits native work')
        qualification = json.loads(args.qualification.read_text())
        require(qualification['status'] == 'passed-cpu-operator-feasibility' and qualification['xpu_initialized'] is False,
                'CPU qualification required')
        for name, digest in qualification['parent_sha256s'].items():
            require(sha(HERE / 'parents' / name) == digest, 'Parent pin changed')
        for name, digest in qualification['source_sha256s'].items():
            require(sha(Path(name)) == digest, 'Qualified source changed')
        binary = Path(qualification['binary']['path'])
        require(sha(binary) == qualification['binary']['sha256'], 'Qualified binary changed')
        for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
            os.environ[key] = '1'
        import torch
        torch.set_num_threads(1); torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        require(not torch.xpu.is_initialized(), 'Unexpected XPU initialization')
        require(str(torch.__version__) == qualification['torch'], 'Torch identity changed')
        sys.path.insert(0, str(HERE / 'parents'))
        import ltx_native_rms_backend
        import ltx_native_activations_backend
        torch.ops.load_library(str(binary))
        pairs = {'rms': (torch.ops.ltx_exact_rms.native.default, torch.ops.ltx_exact_cpp_cpu01.rms.default),
                 'sigmoid': (torch.ops.ltx_exact_activations.sigmoid.default, torch.ops.ltx_exact_cpp_cpu01.sigmoid.default),
                 'gelu': (torch.ops.ltx_exact_activations.gelu.default, torch.ops.ltx_exact_cpp_cpu01.gelu.default)}
        def raw(tensor):
            return tensor.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
        def timed(function, values, count):
            start = time.perf_counter_ns()
            for _ in range(count):
                result = function(*values)
            return (time.perf_counter_ns() - start) / count, result
        with torch.inference_mode():
            for shape, count in [((1, 8), 200), ((1, 64, 4096), 40)]:
                x = (torch.arange(torch.tensor(shape).prod().item(), device='cpu', dtype=torch.float32) % 37 - 18).reshape(shape).to(torch.bfloat16)
                for kind, (parent, candidate) in pairs.items():
                    require(not FAULT.exists(), 'Fault latch prohibits more CPU timing')
                    weight = torch.ones((shape[-1],), device='cpu', dtype=x.dtype)
                    values = (x, [shape[-1]], weight, 1e-6) if kind == 'rms' else ((x,) if kind == 'sigmoid' else (x, 'tanh'))
                    original_bytes = [raw(value) for value in values if isinstance(value, torch.Tensor)]
                    expected = raw(parent(*values))
                    require(raw(candidate(*values)) == expected, 'Pre-timing parity failed')
                    for _ in range(10):
                        parent(*values); candidate(*values)
                    intervals = []
                    for _ in range(5):
                        a, left = timed(parent, values, count)
                        b, middle = timed(candidate, values, count)
                        c, right = timed(parent, values, count)
                        require(raw(left) == raw(middle) == raw(right) == expected, 'Timing output parity failed')
                        intervals.append({'parent_before_ns_per_call': a, 'candidate_ns_per_call': b,
                            'parent_after_ns_per_call': c, 'candidate_minus_parent_mean_ns': b - (a + c) / 2})
                    require([raw(value) for value in values if isinstance(value, torch.Tensor)] == original_bytes, 'Timing input mutation')
                    report['rows'].append({'operation': kind, 'shape': shape, 'dtype': str(x.dtype),
                        'calls_per_interval': count, 'paired_triples': intervals,
                        'median_candidate_ns': statistics.median(row['candidate_ns_per_call'] for row in intervals),
                        'median_parent_mean_ns': statistics.median((row['parent_before_ns_per_call'] + row['parent_after_ns_per_call']) / 2 for row in intervals),
                        'median_candidate_minus_parent_mean_ns': statistics.median(row['candidate_minus_parent_mean_ns'] for row in intervals),
                        'output_sha256': hashlib.sha256(expected).hexdigest(), 'byte_parity': True, 'inputs_unchanged': True})
        require(not FAULT.exists() and not torch.xpu.is_initialized(), 'Unexpected fault/XPU initialization')
        report.update(status='passed-cpu-dispatch-observation', xpu_initialized=False, cpu_threads=1,
                      torch=str(torch.__version__), binary=qualification['binary'])
    except BaseException as error:
        report.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2); stream.write('\n')
        print(json.dumps({'status': report['status'], 'output': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
