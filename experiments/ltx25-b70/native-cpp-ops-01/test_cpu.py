#!/usr/bin/env python3
"""Build/test a private CPU-only exact-ATen prototype; never import the live app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
FAULT = ROOT / 'FAULT.json'
PINS = {'ltx_native_rms_backend.py': '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb',
        'ltx_native_activations_backend.py': '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def no_fault():
    require(not FAULT.exists(), 'Fault latch prohibits native CPU work')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), 'Output must be new')
    report = {'schema': 'ltx.private-cpp-operators-cpu.v1', 'status': 'started', 'cases': [],
              'scope': 'CPU-only operator feasibility; no native XPU, model, clip or speed qualification',
              'command': sys.argv, 'python_executable': sys.executable, 'python_version': sys.version,
              'source_sha256s': {str(p): sha(p) for p in (Path(__file__), HERE / 'native_ops.cpp')},
              'parent_sha256s': PINS, 'build_directory': str(args.build_dir), 'xpu_initialized': None}
    try:
        no_fault()
        for name, digest in PINS.items():
            require(sha(HERE / 'parents' / name) == digest, 'Frozen parent changed: ' + name)
        require(args.build_dir.is_absolute() and args.build_dir.parent == ROOT and
                args.build_dir.name.startswith('native-cpp-ops-cpu-') and
                not args.build_dir.exists() and not args.build_dir.is_symlink(), 'Use a new bounded build directory')
        require(shutil.which('c++') and shutil.which('ninja'), 'C++ compiler and ninja required')
        require(shutil.disk_usage(ROOT).free >= 2 * 1024**3, 'Insufficient build disk space')
        report['compiler_version'] = subprocess.run(['c++', '--version'], check=True, capture_output=True, text=True).stdout
        if args.check_only:
            report.update(status='inactive-source-check-passed', torch_imported=False, files_written_by_build=0)
            return
        for key in ('MAX_JOBS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'TORCHINDUCTOR_COMPILE_THREADS'):
            os.environ[key] = '1'
        report['environment'] = {key: os.environ[key] for key in ('MAX_JOBS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'TORCHINDUCTOR_COMPILE_THREADS')}
        no_fault()
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        require(not torch.xpu.is_initialized(), 'XPU unexpectedly initialized')
        report.update(torch=str(torch.__version__), torch_path=str(Path(torch.__file__).resolve()),
                      torch_config=torch.__config__.show(), cpu_threads=torch.get_num_threads())
        sys.path.insert(0, str(HERE / 'parents'))
        import ltx_native_rms_backend as rms
        import ltx_native_activations_backend as activations
        from torch.utils.cpp_extension import load
        no_fault()
        args.build_dir.mkdir()
        shutil.copyfile(HERE / 'native_ops.cpp', args.build_dir / 'native_ops.cpp')
        begin = time.monotonic()
        binary = load(name='ltx_exact_cpp_cpu01', sources=[str(args.build_dir / 'native_ops.cpp')],
                      build_directory=str(args.build_dir), extra_cflags=['-O2', '-g0'],
                      with_cuda=False, with_sycl=False, is_python_module=False, verbose=True)
        report['build_seconds_not_dispatch_timing'] = time.monotonic() - begin
        no_fault()
        report['binary'] = {'path': str(binary), 'sha256': sha(Path(binary))}
        torch.library.register_fake('ltx_exact_cpp_cpu01::rms')(rms._fake_native_rms)
        torch.library.register_fake('ltx_exact_cpp_cpu01::sigmoid')(activations._fake_native_sigmoid)
        torch.library.register_fake('ltx_exact_cpp_cpu01::gelu')(activations._fake_native_gelu)
        operations = {'rms': (torch.ops.ltx_exact_rms.native.default, torch.ops.ltx_exact_cpp_cpu01.rms.default),
                      'sigmoid': (torch.ops.ltx_exact_activations.sigmoid.default, torch.ops.ltx_exact_cpp_cpu01.sigmoid.default),
                      'gelu': (torch.ops.ltx_exact_activations.gelu.default, torch.ops.ltx_exact_cpp_cpu01.gelu.default)}

        def raw(tensor):
            return tensor.detach().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()

        def metadata(tensor):
            return {'shape': list(tensor.shape), 'stride': list(tensor.stride()),
                    'dtype': str(tensor.dtype), 'device': str(tensor.device), 'storage_offset': tensor.storage_offset()}

        def check(name, kind, values, expected_accept=True):
            no_fault()
            inputs = [value for value in values if isinstance(value, torch.Tensor)]
            saved = [(raw(value), metadata(value)) for value in inputs]
            row = {'name': name, 'operation': kind, 'inputs': [metadata(value) for value in inputs],
                   'expected_accept': expected_accept, 'outcomes': []}
            outputs = []
            for label, function in zip(('parent', 'candidate', 'candidate_repeat'),
                                       (operations[kind][0], operations[kind][1], operations[kind][1])):
                try:
                    output = function(*values)
                    outcome = {'implementation': label, 'accepted': True,
                               'output': metadata(output), 'sha256': hashlib.sha256(raw(output)).hexdigest(),
                               'nonalias': all(not torch._C._is_alias_of(output, value) for value in inputs)}
                    outputs.append(raw(output))
                except Exception as error:
                    outcome = {'implementation': label, 'accepted': False, 'error': repr(error)}
                    outputs.append(None)
                row['outcomes'].append(outcome)
            row['inputs_unchanged'] = all(raw(value) == bits and metadata(value) == meta
                                          for value, (bits, meta) in zip(inputs, saved))
            accepted = [outcome['accepted'] for outcome in row['outcomes']]
            row['passed'] = (accepted == [expected_accept] * 3 and row['inputs_unchanged'] and
                (not expected_accept or (outputs[0] == outputs[1] == outputs[2] and
                  all(outcome['nonalias'] for outcome in row['outcomes']) and
                  row['outcomes'][0]['output'] == row['outcomes'][1]['output'] == row['outcomes'][2]['output'])))
            report['cases'].append(row)
            require(row['passed'], 'Operator comparison failed: ' + name)

        def data(shape, dtype):
            count = 1
            for size in shape:
                count *= size
            return ((torch.arange(count, device='cpu', dtype=torch.float32) % 37 - 18) / 11 + 0.03125).reshape(shape).to(dtype)

        with torch.inference_mode():
            for dtype in (torch.bfloat16, torch.float32):
                for shape, normalized in [((2, 8), [8]), ((1, 4, 8), [8]), ((2, 4, 8), [4, 8]), ((0, 8), [8])]:
                    for eps in (None, 0.0, 1e-6, 1e-5):
                        for weighted in (False, True):
                            x = data(shape, dtype)
                            weight = data(tuple(normalized), dtype) if weighted else None
                            check(f'rms-{dtype}-{shape}-{eps}-{weighted}', 'rms', (x, normalized, weight, eps))
                for shape in ((), (1,), (2, 8), (1, 4, 8), (0, 8)):
                    x = data(shape, dtype)
                    check(f'sigmoid-{dtype}-{shape}', 'sigmoid', (x,))
                    check(f'gelu-{dtype}-{shape}', 'gelu', (x, 'tanh'))
                x = torch.empty_strided((1, 8), (80, 1), dtype=dtype, device='cpu')
                x.copy_(data((1, 8), dtype))
                check(f'singleton-strides-rms-{dtype}', 'rms', (x, [8], None, 1e-6))
                check(f'singleton-strides-sigmoid-{dtype}', 'sigmoid', (x,))
                check(f'singleton-strides-gelu-{dtype}', 'gelu', (x, 'tanh'))
                x = data((3, 8), dtype)[1:]
                check(f'offset-rms-{dtype}', 'rms', (x, [8], None, 1e-6))
                check(f'offset-sigmoid-{dtype}', 'sigmoid', (x,))
                check(f'offset-gelu-{dtype}', 'gelu', (x, 'tanh'))
            # RMS parent does not impose the activation BF16/F32 restriction.
            check('rms-float64-parent-contract', 'rms', (data((2, 8), torch.float64), [8], None, None))
            x = data((2, 8), torch.float32)
            for shape in ([], [0], [-1], [7], [1, 2, 8]):
                check('invalid-normalized-' + repr(shape), 'rms', (x, shape, None, 1e-6), False)
            for eps in (-1.0, float('nan'), float('inf')):
                check('invalid-eps-' + repr(eps), 'rms', (x, [8], None, eps), False)
            for name, weight in [('shape', data((7,), torch.float32)), ('dtype', data((8,), torch.bfloat16)),
                                 ('stride', data((16,), torch.float32)[::2])]:
                check('invalid-weight-' + name, 'rms', (x, [8], weight, 1e-6), False)
            transposed = x.t()
            check('noncontiguous-rms', 'rms', (transposed, [2], None, 1e-6), False)
            for kind in ('sigmoid', 'gelu'):
                suffix = () if kind == 'sigmoid' else ('tanh',)
                for name, value in [('transpose', transposed), ('float64', x.double()), ('int64', x.long())]:
                    check('invalid-' + kind + '-' + name, kind, (value,) + suffix, False)
            check('gelu-approximate-none', 'gelu', (x, 'none'), False)
            # Fake registrations reuse the frozen parent's exact fake contract.
            from torch._subclasses.fake_tensor import FakeTensorMode
            with FakeTensorMode():
                fake = torch.empty((1, 4, 8), dtype=torch.bfloat16, device='cpu')
                for kind, values in [('rms', (fake, [8], None, 1e-6)), ('sigmoid', (fake,)), ('gelu', (fake, 'tanh'))]:
                    left, right = [fn(*values) for fn in operations[kind]]
                    row = {'name': 'fake-' + kind, 'passed': metadata(left) == metadata(right),
                           'parent': metadata(left), 'candidate': metadata(right)}
                    report['cases'].append(row)
                    require(row['passed'], 'Fake output contract changed')
        no_fault()
        require(not torch.xpu.is_initialized(), 'XPU initialized during CPU gate')
        report.update(status='passed-cpu-operator-feasibility', xpu_initialized=False,
                      tests=len(report['cases']), inference_only=True, cpu_benchmark_performed=False)
    except BaseException as error:
        report.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        report['torch_imported'] = 'torch' in sys.modules
        report['fault_present_at_exit'] = FAULT.exists()
        if args.build_dir.exists():
            report['build_artifacts'] = {str(path): {'bytes': path.stat().st_size, 'sha256': sha(path)}
                for path in args.build_dir.iterdir() if path.is_file()}
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
        print(json.dumps({'status': report['status'], 'output': str(args.output), 'cases': len(report['cases'])}, indent=2))


if __name__ == '__main__':
    main()
