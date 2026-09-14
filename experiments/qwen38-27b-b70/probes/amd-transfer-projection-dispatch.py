#!/usr/bin/env python3
"""Bounded operator-only exactness/timing screen; never launches a model server.

Default rows 1, 2. Run only when parent owns GPUs. CPU C++ compilation loads no
custom device kernels: the candidate dispatches to the existing R304 kernels.
"""
import argparse
import hashlib
import inspect
import importlib.metadata
import json
import os
from pathlib import Path
import statistics
import time
import traceback


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', default='1,2')
    parser.add_argument('--device', default='xpu:0')
    parser.add_argument('--iterations', type=int, default=24)
    parser.add_argument('--blocks', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-directory', type=Path, required=True)
    parser.add_argument('--compile-only', action='store_true')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation: never replace any previous receipt, including a
    # compile-only receipt. The build directory may be reused independently.
    with args.output.open('x', encoding='utf-8') as receipt:
        report = {
            'schema': 'neural.download.amd-transfer-projection-dispatch.v1',
            'status': 'STARTING', 'compile_only': args.compile_only,
            'classification': 'synthetic-production-shaped-operator-screen-only',
            'device': args.device, 'cases': [], 'timings': [],
            'all_exact': False, 'promotion': False,
            'realistic_final_gate': {'passed': False},
            'limitations': ['No model outputs or context-length evidence',
                           'No fresh-server confirmation',
                           'Synthetic weights and inputs; original precision retained',
                           'Measures eager dispatch; compiled endpoint benefit unproven'],
        }
        def save():
            receipt.seek(0)
            json.dump(report, receipt, indent=2)
            receipt.write('\n')
            receipt.truncate()
            receipt.flush()
            os.fsync(receipt.fileno())
        try:
            save()
            run(args, report, save)
        except BaseException as error:
            report['status'] = 'ABORTED'
            report['all_exact'] = False
            report['error'] = {'type': type(error).__name__, 'message': str(error),
                               'traceback': traceback.format_exc()}
            save()
            raise


def run(args, report, save):
    rows = [int(m) for m in args.rows.split(',')]
    if any(m < 1 or m > 4096 for m in rows) or args.iterations < 1 or args.blocks < 2:
        raise ValueError('Rows must be 1..4096, iterations positive, blocks>=2')
    if os.environ.get('VLLM_XPU_FP16_LINEAR_CLASSPAD', '0') != '0':
        raise ValueError('This prototype requires the qualified CLASSPAD=0 route')
    if os.environ.get('VLLM_XPU_FP16_LINEAR_ROWCHUNK', '32') != '32':
        raise ValueError('This prototype requires ROWCHUNK=32')
    report['package_versions'] = {}
    for package in ('torch', 'vllm', 'vllm-xpu-kernels', 'numpy', 'ninja'):
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = None
        report['package_versions'][package] = version
    report['python'] = __import__('sys').version
    report['candidate_cpp_sha256'] = digest(Path(__file__).with_suffix('.cpp'))
    report['probe_sha256'] = digest(__file__)
    report['status'] = 'IMPORTING_TORCH'
    save()
    import torch
    from torch.utils.cpp_extension import load
    source = Path(__file__).with_suffix('.cpp')
    args.build_directory.mkdir(parents=True, exist_ok=True)
    # No SYCL compilation; public ATen/dispatcher headers and torch CPU libraries.
    report['status'] = 'COMPILING'
    save()
    library = load(name='amd_transfer_projection_dispatch', sources=[str(source)],
         build_directory=str(args.build_directory), extra_cflags=['-O2'],
         is_python_module=False, verbose=True)
    # torch returns the loaded library path for is_python_module=False.
    shared_object = Path(library) if isinstance(library, str) else args.build_directory / 'amd_transfer_projection_dispatch.so'
    if not shared_object.is_file():
        raise RuntimeError('Compiled shared-object path was not resolved')
    report['compiled_library'] = {'path': str(shared_object.resolve()),
                                  'sha256': digest(shared_object),
                                  'bytes': shared_object.stat().st_size}
    report['torch'] = torch.__version__
    report['candidate_schema'] = str(torch.ops.amd_transfer.projection_pair.default._schema)
    report['status'] = 'COMPILE_ONLY_PASSED' if args.compile_only else 'IMPORTING_RUNTIME'
    save()
    if args.compile_only:
        return
    import vllm._xpu_ops as xpu_ops
    import vllm.model_executor.layers.utils as linear_utils
    import vllm.model_executor.layers.mamba.gdn.qwen_gdn_linear_attn as gdn
    if linear_utils._R290_CLASSPAD != 0 or linear_utils._R224_CHUNK != 32:
        raise RuntimeError('Imported runtime has different FP16 policy')
    # Require current timing/reference route to remain the registered operations.
    assert gdn._XPU_DETERMINISTIC_BA_MIN_TOKENS == 17
    assert gdn._XPU_DETERMINISTIC_BA_PAD_TOKENS == 256
    report['source_files'] = {inspect.getfile(m): digest(inspect.getfile(m))
                              for m in (xpu_ops, linear_utils, gdn)}
    report['native_schema'] = str(torch.ops._xpu_C.fp8_gemm_w8a16.default._schema)
    report['status'] = 'CREATING_FIXTURES'
    save()
    torch.set_grad_enabled(False)
    torch.manual_seed(1942026)
    device = torch.device(args.device)
    # CPU fixture construction avoids device RNG affecting compared operations.
    w = (torch.randn(8192,5120, dtype=torch.float16)*0.03).to(torch.float8_e4m3fn).to(device)
    w_kn = w.t()  # MUST remain the noncontiguous checkpoint NT view.
    scales = (torch.rand(40,64, dtype=torch.float32)*0.02+0.01).to(device)
    ba = (torch.randn(48,5120, dtype=torch.float16)*0.01).to(device)
    candidate = torch.ops.amd_transfer.projection_pair.default
    fp8_op = torch.ops._xpu_C.fp8_gemm_w8a16.default
    ba_prefill_op = torch.ops.vllm.qwen_gdn_ba_prefill_xpu.default
    ba_decode_op = torch.ops.vllm.xpu_fp16_linear_rowchunk.default
    def reference(x):
        q = fp8_op(x, w_kn, scales, None)
        if x.shape[0] >= 17:
            b = ba_prefill_op(x, ba)
        else:
            b = ba_decode_op(x, ba, None, 32)
        return q,b
    def treatment(x):
        return candidate(x, w_kn, scales, ba)
    def bytes_of(t):
        return t.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    def tensor_identity(t):
        return {'shape': list(t.shape), 'stride': list(t.stride()),
                'dtype': str(t.dtype),
                'sha256_logical_contiguous_bytes': hashlib.sha256(bytes_of(t)).hexdigest()}
    report['weight_and_scale_inputs'] = {
        'qkvz_kn': tensor_identity(w_kn), 'scales_kn': tensor_identity(scales),
        'ba_nk': tensor_identity(ba)}
    report['status'] = 'CHECKING_EXACTNESS'
    save()
    fixtures = {}
    for m in rows:
        random = torch.randn(m,5120, dtype=torch.float16)
        cancellation = random.clone()
        cancellation[:,1::2] = -cancellation[:,::2]
        fixtures[m] = random.to(device)
        for kind, x_cpu in [('zeros',torch.zeros_like(random)), ('random',random),
                            ('alternating-sign',cancellation)]:
            x = x_cpu.to(device)
            input_identity = tensor_identity(x)
            expected_bytes = [bytes_of(t) for t in reference(x)]
            for repeat in range(2):
                # A fresh control after each candidate independently tests
                # baseline stability; candidate repeats alone cannot do that.
                actual_bytes = [bytes_of(t) for t in treatment(x)]
                repeated_control_bytes = [bytes_of(t) for t in reference(x)]
                outputs = []
                for name, initial, candidate_bytes, control_bytes in zip(
                        ('qkvz', 'ba'), expected_bytes, actual_bytes,
                        repeated_control_bytes):
                    outputs.append({
                        'output': name,
                        'bit_exact': initial == candidate_bytes,
                        'control_repeat_bit_exact': initial == control_bytes,
                        'reference_sha256': hashlib.sha256(initial).hexdigest(),
                        'candidate_sha256': hashlib.sha256(candidate_bytes).hexdigest(),
                        'control_repeat_sha256': hashlib.sha256(control_bytes).hexdigest()})
                unchanged = tensor_identity(x) == input_identity
                report['cases'].append({'rows': m, 'fixture': kind,
                    'repeat': repeat, 'input': input_identity,
                    'input_unchanged': unchanged, 'outputs': outputs})
                save()
                if not unchanged or not all(o['bit_exact'] and
                        o['control_repeat_bit_exact'] for o in outputs):
                    raise RuntimeError('Operator equality or control stability failed; timing skipped')
    report['all_exact'] = True
    report['status'] = 'TIMING'
    save()
    def measure(fn,x):
        torch.xpu.synchronize(device)
        start=time.perf_counter_ns()
        for _ in range(args.iterations):
            output=fn(x)
        submitted=time.perf_counter_ns()
        torch.xpu.synchronize(device)
        end=time.perf_counter_ns()
        return {'wall_us':(end-start)/args.iterations/1000,
                'submission_us':(submitted-start)/args.iterations/1000}
    for m,x in fixtures.items():
        timed_input_before = tensor_identity(x)
        for _ in range(8):
            reference(x); treatment(x)
        raw=[]
        for block in range(args.blocks):
            order=('control','candidate','candidate','control') if block%2==0 else ('candidate','control','control','candidate')
            for label in order:
                raw.append({'block':block,'arm':label,**measure(reference if label=='control' else treatment,x)})
        ctr=statistics.median(r['wall_us'] for r in raw if r['arm']=='control')
        trt=statistics.median(r['wall_us'] for r in raw if r['arm']=='candidate')
        report['timings'].append({'rows':m,'iterations':args.iterations,
            'control_median_us':ctr,'candidate_median_us':trt,
            'candidate_over_control':trt/ctr,'raw':raw,
            'input_before':timed_input_before,'input_after':tensor_identity(x)})
        if report['timings'][-1]['input_after'] != timed_input_before:
            raise RuntimeError('Timing input changed during probe')
        save()
    final_inputs = {'qkvz_kn': tensor_identity(w_kn),
                    'scales_kn': tensor_identity(scales), 'ba_nk': tensor_identity(ba)}
    report['weight_and_scale_inputs_after'] = final_inputs
    report['weights_and_scales_unchanged'] = final_inputs == report['weight_and_scale_inputs']
    if not report['weights_and_scales_unchanged']:
        raise RuntimeError('Weights or scales changed during probe')
    report['status'] = 'OPERATOR_SCREEN_PASSED'
    save()
    print(json.dumps({'all_exact':report['all_exact'],'timings':[
        {k:v for k,v in t.items() if k!='raw'} for t in report['timings']]},indent=2))

if __name__ == '__main__':
    main()
