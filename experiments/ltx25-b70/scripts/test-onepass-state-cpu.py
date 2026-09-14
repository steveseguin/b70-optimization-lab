#!/usr/bin/env python3
"""Bounded CPU acceptance comparison of pinned parent/one-pass metadata guards."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import traceback
import types

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PATCH = LANE / 'patches/multiblock-onepass-state-04'
PINS = {
    PATCH / 'original.py': '79b4e76b10f49094f3ad11cc70ba62334c2ccf10e50960ac209fb5a0cdd2a584',
    PATCH / 'candidate.py': 'ba89394822e9ec607cc8ec7aad092a3afa7d87e0f723b781cf27f1f6158c031b',
    SOURCE / 'comfy/ldm/lightricks/av_model.py': '6582ee5c9fe1119b0dfa85a7c5e4f6d94a899f3b551b1886546fd787c3799e7d',
    SOURCE / 'comfy/ldm/lightricks/model.py': 'f0292be2a39491d411ad3cf4b58cebd87e62bf2568aafa35814b954828733718',
    LANE / 'scripts/ltx_layer_shard.py': '0c836c2c19ef678360c4e5dddb09173d60e0fd011e44430370485abd63336d3b',
}


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', action='store_true', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    require(args.cpu and 'torch' not in sys.modules, 'Explicit CPU admission before native imports required')
    require(not (ROOT / 'FAULT.json').exists(), 'Recorded fault prohibits native imports')
    output = args.output_dir.absolute()
    require(output.parent == ROOT and output.name.startswith('onepass-state-cpu-') and
            not output.exists() and not any(p.is_symlink() for p in (output, *output.parents)),
            'Expected fresh onepass-state-cpu-* evidence directory')
    for path, expected in PINS.items():
        require(sha(path) == expected, 'Source identity changed: ' + str(path))
    output.mkdir(exist_ok=False)
    (output / 'tested-harness.py').write_bytes(Path(__file__).read_bytes())
    for name in ('original.py', 'candidate.py'):
        (output / name).write_bytes((PATCH / name).read_bytes())
    os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', TORCHINDUCTOR_COMPILE_THREADS='1')
    sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-comfy-compiler',
                '--disable-async-offload', '--disable-pinned-memory',
                '--use-pytorch-cross-attention', '--disable-xformers']
    report = {'schema': 'ltx.onepass-state-cpu-acceptance.v1', 'status': 'running',
              'phase': 'before-native-import', 'pid': os.getpid(), 'guard_argv': list(sys.argv),
              'source_sha256s': {str(p): digest for p, digest in PINS.items()},
              'harness_sha256': sha(Path(__file__)), 'cases': [],
              'scope': 'Pinned _validate bodies on actual tiny native block metadata; compare acceptance, not first-error priority',
              'block_forward_executed': False, 'compiler_executed': False, 'xpu_execution_qualified': False}
    write(output / 'preregistration.json', report)
    print(json.dumps({'pid': os.getpid(), 'phase': report['phase'], 'output': str(output)}), flush=True)
    torch = None
    try:
        sys.path.insert(0, str(SOURCE))
        import comfy.options
        comfy.options.enable_args_parsing()
        import torch
        from torch import nn
        import comfy.ops
        from comfy.ldm.lightricks import av_model
        from ltx_layer_shard import _BlockRoute
        require(not torch.xpu.is_initialized(), 'XPU initialized during import')
        report['xpu_initialized_after_import'] = False
        report['torch'] = torch.__version__
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)
        cpu = torch.device('cpu')
        validators = {}
        for name in ('original', 'candidate'):
            path = PATCH / (name + '.py')
            tree = ast.parse(path.read_text())
            block_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CompiledBlockRoute')
            method = next(n for n in block_class.body if isinstance(n, ast.FunctionDef) and n.name == '_validate')
            namespace = {'torch': torch, 'av_model': av_model, '_BlockRoute': _BlockRoute}
            exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
            validators[name] = namespace['_validate']

        def block():
            return av_model.BasicAVTransformerBlock(v_dim=32, a_dim=32, v_heads=1, a_heads=1,
                vd_head=32, ad_head=32, v_context_dim=32, a_context_dim=32,
                apply_gated_attention=True, cross_attention_adaln=True,
                ff_bias=False, audio_ff_bias=True, dtype=torch.bfloat16,
                device='cpu', operations=comfy.ops.manual_cast).eval()

        def tensor(dtype=torch.bfloat16, device='cpu'):
            return torch.empty((1,), dtype=dtype, device=device)

        def snapshot(current):
            return {'modules': [(name, id(module)) for name, module in current.named_modules()],
                    'state': [(kind, name, id(value), str(value.dtype), str(value.device))
                        for kind, values in (('parameter', current.named_parameters()), ('buffer', current.named_buffers()))
                        for name, value in values]}

        def shared_module(current, cleanup):
            current.shared_attention = current.attn1
        def parameter_alias(current, cleanup):
            current.register_parameter('parameter_alias', current.scale_shift_table)
        def buffer_alias(current, cleanup):
            value = tensor()
            current.register_buffer('buffer_a', value)
            current.attn1.register_buffer('buffer_b', value)
        def cross_registry(current, cleanup):
            current.attn1.register_buffer('parameter_as_buffer', current.scale_shift_table)
        def none_entries(current, cleanup):
            current.register_parameter('none_parameter', None)
            current.attn1.register_buffer('none_buffer', None)
        def empty(current, cleanup):
            for module in current.modules():
                module._parameters.clear()
                module._buffers.clear()
        def all_none(current, cleanup):
            for module in current.modules():
                for registrations in (module._parameters, module._buffers):
                    for name in registrations:
                        registrations[name] = None
        def bad_parameter(current, cleanup):
            current.register_parameter('bad_parameter', nn.Parameter(tensor(dtype=torch.float32)))
        def bad_buffer(current, cleanup):
            current.register_buffer('bad_buffer', tensor(dtype=torch.float32))
        def wrong_device(current, cleanup):
            current.register_buffer('meta_buffer', tensor(device='meta'))
        def wrong_device_parameter(current, cleanup):
            current.register_parameter('meta_parameter', nn.Parameter(tensor(device='meta')))
        def shared_bad_buffer(current, cleanup):
            value = tensor(dtype=torch.float32)
            current.register_buffer('bad_a', value)
            current.attn1.register_buffer('bad_b', value)
        def shared_bad_parameter(current, cleanup):
            value = nn.Parameter(tensor(dtype=torch.float32))
            current.register_parameter('bad_parameter', value)
            current.attn1.register_parameter('bad_alias', value)
        def cross_registry_bad(current, cleanup):
            value = nn.Parameter(tensor(dtype=torch.float32))
            current.register_parameter('bad_parameter', value)
            current.attn1.register_buffer('bad_parameter_as_buffer', value)
        def combined_aliases(current, cleanup):
            shared_module(current, cleanup)
            parameter_alias(current, cleanup)
            buffer_alias(current, cleanup)
            cross_registry(current, cleanup)
            none_entries(current, cleanup)
        def local_hook(method):
            def mutate(current, cleanup):
                handle = getattr(current.attn1, method)(lambda *args: None)
                cleanup.append(handle.remove)
            return mutate
        def global_hook(method):
            def mutate(current, cleanup):
                handle = getattr(torch.nn.modules.module, method)(lambda *args: None)
                cleanup.append(handle.remove)
            return mutate

        cases = [('native_unmodified', lambda b, c: None, True, True),
                 ('shared_module', shared_module, True, True),
                 ('parameter_alias', parameter_alias, True, True),
                 ('buffer_alias', buffer_alias, True, True),
                 ('cross_registry_alias', cross_registry, True, True),
                 ('none_registrations', none_entries, True, True),
                 ('combined_aliases_and_none', combined_aliases, True, True),
                 ('empty_state', empty, False, False), ('all_none_state', all_none, False, False),
                 ('bad_parameter_dtype', bad_parameter, False, False),
                 ('bad_buffer_dtype', bad_buffer, False, False),
                 ('shared_bad_buffer_dtype', shared_bad_buffer, False, False),
                 ('shared_bad_parameter_dtype', shared_bad_parameter, False, False),
                 ('cross_registry_bad_dtype', cross_registry_bad, False, False),
                 ('wrong_buffer_device', wrong_device, True, False),
                 ('wrong_parameter_device', wrong_device_parameter, True, False)]
        for method in ('register_forward_hook', 'register_forward_pre_hook',
                       'register_full_backward_hook', 'register_full_backward_pre_hook'):
            cases.append(('late_local_' + method, local_hook(method), False, False))
        for method in ('register_module_forward_hook', 'register_module_forward_pre_hook',
                       'register_module_full_backward_hook', 'register_module_full_backward_pre_hook'):
            cases.append(('late_global_' + method, global_hook(method), False, False))
        report['phase'] = 'acceptance-cases'
        with torch.inference_mode():
            for name, mutate, expected_false, expected_true in cases:
                require(not (ROOT / 'FAULT.json').exists(), 'Fault appeared; stop CPU cases')
                current = block()
                require(len(tuple(current.parameters())) + len(tuple(current.buffers())) == 84,
                        'Expected native84 state registrations before case mutation')
                route = types.SimpleNamespace(block=current, original_route=_BlockRoute(cpu, cpu, False),
                    _route_identity=(cpu, cpu, False), _binding=None)
                # Establish that hooks/metadata mutations are late relative to
                # successful validation of this same block, not constructor errors.
                for validator in validators.values():
                    validator(route, check_device=True)
                cleanup = []
                row = {'case': name, 'passed': False, 'results': []}
                report['cases'].append(row)
                try:
                    mutate(current, cleanup)
                    before = snapshot(current)
                    for check_device, expected in ((False, expected_false), (True, expected_true)):
                        results = {}
                        for implementation, validator in validators.items():
                            try:
                                validator(route, check_device=check_device)
                            except Exception as error:
                                results[implementation] = {'accepted': False, 'error_type': type(error).__name__,
                                                           'error': str(error)}
                            else:
                                results[implementation] = {'accepted': True}
                        row['results'].append({'check_device': check_device, 'expected_acceptance': expected,
                                               'implementations': results})
                        require(all(value['accepted'] is expected for value in results.values()),
                                'Acceptance mismatch for ' + name)
                    require(snapshot(current) == before, 'Metadata validation mutated registered state')
                    row['passed'] = True
                finally:
                    for undo in reversed(cleanup):
                        undo()
                    write(output / (name + '.json'), row)
            report['cases_passed'] = len(cases)
            report['validation_comparisons'] = len(cases) * 2
        require(not torch.xpu.is_initialized(), 'XPU initialized during CPU cases')
        require(all(sha(path) == expected for path, expected in PINS.items()), 'Pinned source changed')
        report.update(status='passed', phase='completed')
    except BaseException as error:
        report.update(status='failed', error=repr(error), traceback=traceback.format_exc())
    finally:
        if torch is not None:
            report['xpu_initialized_after_work'] = torch.xpu.is_initialized()
            if report['xpu_initialized_after_work']:
                report['status'] = 'failed'
        report['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write(output / 'result.json', report)
    print(json.dumps({key: report[key] for key in ('status', 'phase', 'max_rss_kib')}, indent=2), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
