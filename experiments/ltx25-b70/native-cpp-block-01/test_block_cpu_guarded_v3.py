#!/usr/bin/env python3
"""Inactive guarded diagnostic v3: explicit CPU availability policy, unchanged native gates."""
import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LANE = HERE.parent
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
FAULT = ROOT / 'FAULT.json'
FIXTURE_SOURCE = LANE / 'scripts/test-ltx-native-activations-block-cpu.py'
FIXTURE_SHA = '09632eba818a3cf925a7627b14f9b61db326dcb310e6ab2b282f51720d1cd18d'
OPTIONS_SOURCE = LANE / 'scripts/ltx_block_compile.py'
OPTIONS_SHA = '96871c075b1c9851882171b84223d7e2b2294a734f15242278f75cc462b21ea4'
QUALIFICATION = LANE / 'native-cpp-ops-01/cpu-result-01.json'
QUALIFICATION_SHA = 'feba23a06a7baf237055c526a135b2a68290e6ada53f688d71093729c0fcbd71'
SOURCE_PINS = {'comfy/ldm/lightricks/av_model.py': '6582ee5c9fe1119b0dfa85a7c5e4f6d94a899f3b551b1886546fd787c3799e7d',
               'comfy/ldm/lightricks/model.py': 'f0292be2a39491d411ad3cf4b58cebd87e62bf2568aafa35814b954828733718',
               'comfy/ops.py': '6058f688d936b083c49fa49a57964837476db6d95750ea70198ad60e884ffed0'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def no_fault():
    require(not FAULT.exists(), 'Fault latch prohibits native work')


def source_gate():
    no_fault()
    require(sha(FIXTURE_SOURCE) == FIXTURE_SHA and sha(OPTIONS_SOURCE) == OPTIONS_SHA and
            sha(QUALIFICATION) == QUALIFICATION_SHA, 'Prior source/qualification pin changed')
    qualification = json.loads(QUALIFICATION.read_text())
    require(qualification['status'] == 'passed-cpu-operator-feasibility' and qualification['xpu_initialized'] is False,
            'CPU operator qualification required')
    require(sha(Path(qualification['binary']['path'])) == qualification['binary']['sha256'], 'CPU binary changed')
    for name, digest in SOURCE_PINS.items():
        require(sha(SOURCE / name) == digest, 'Actual block source changed: ' + name)
    parent_main = next(n for n in ast.parse(FIXTURE_SOURCE.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    parent_body = next(n for n in parent_main.body if isinstance(n, ast.Try)).body
    parent_inputs = next(n for n in parent_body if isinstance(n, ast.FunctionDef) and n.name == 'inputs')
    functions = {n.name: n for n in ast.parse((HERE / 'fixture.py').read_text()).body if isinstance(n, ast.FunctionDef)}
    require([ast.dump(n) for n in parent_inputs.body] == [ast.dump(n) for n in functions['make_inputs'].body], 'Input arithmetic changed')
    index = next(i for i, n in enumerate(parent_body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'block' for t in n.targets))
    require([ast.dump(n) for n in parent_body[index:index+3]] == [ast.dump(n) for n in functions['make_block'].body[:-1]], 'Block initialization changed')
    option_nodes = ast.parse(OPTIONS_SOURCE.read_text()).body
    options = ast.literal_eval(next(n.value for n in option_nodes if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'OPTIONS' for t in n.targets)))
    return options


def emitted_census(directory):
    namespaces = {'python': {'ltx_exact_rms.native': 'rms', 'ltx_exact_activations.sigmoid': 'sigmoid', 'ltx_exact_activations.gelu': 'gelu'},
                  'cpp': {'ltx_exact_cpp_cpu01.rms': 'rms', 'ltx_exact_cpp_cpu01.sigmoid': 'sigmoid', 'ltx_exact_cpp_cpu01.gelu': 'gelu'}}
    output = {'python': [], 'cpp': []}
    for path in directory.rglob('*.py'):
        require(path.stat().st_size <= 5 * 1024**2, 'Unexpectedly large generated wrapper')
        text = path.read_text()
        if not any(namespace in text for names in namespaces.values() for namespace in names):
            continue
        calls = [ast.unparse(n.func) for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Call)]
        for arm, names in namespaces.items():
            counts = {kind: sum(name == 'torch.ops.' + target + '.default' for name in calls) for target, kind in names.items()}
            if any(counts.values()):
                require(counts == {'rms': 15, 'sigmoid': 6, 'gelu': 2}, 'Unexpected emitted wrapper operation counts')
                output[arm].append({'path': str(path), 'sha256': sha(path), 'operation_counts': counts})
    require(all(len(rows) == 2 for rows in output.values()), 'Exactly two emitted wrappers per compiled arm required')
    return output


def persist_startup(evidence_dir, report):
    require('torch' not in sys.modules, 'Startup identity must be saved before Torch import')
    record = {'schema': 'ltx.cpp-cpu-guarded-startup.v1',
              'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'pid': os.getpid(), 'ppid': os.getppid(), 'torch_imported': False,
              'command': list(report['command']), 'helper_sha256s': dict(report['helper_sha256s']),
              'source_pins': dict(report['source_pins']),
              'fixture_parent_sha256': report['fixture_parent_sha256'],
              'operator_qualification_sha256': report['operator_qualification_sha256'],
              'options': dict(report['options']), 'compiler_environment': dict(report['compiler_environment']),
              'cpu_import_policy_requested': report['cpu_import_policy_requested']}
    path = evidence_dir / 'startup-identity.json'
    with path.open('x') as out:
        json.dump(record, out, indent=2); out.write('\n')
        out.flush(); os.fsync(out.fileno())
    report['startup_receipt'] = {'path': str(path), 'sha256': sha(path)}
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), 'Output must be new')
    require(args.evidence_dir.is_absolute() and args.evidence_dir.parent == ROOT and
            args.evidence_dir.name.startswith('native-cpp-block-cpu-') and not args.evidence_dir.exists() and
            not args.evidence_dir.is_symlink(), 'Evidence directory must be new and bounded')
    report = {'schema': 'ltx.cpp-actual-tiny-block-cpu.v1', 'passed': False, 'phase': 'source-gate', 'rows': [],
              'calls': [], 'command': sys.argv, 'pid': os.getpid(), 'ppid': os.getppid(), 'scope': 'Tiny actual BF16 CPU block exactness only; no XPU/model/clip/speed qualification',
              'source_pins': SOURCE_PINS, 'fixture_parent_sha256': FIXTURE_SHA, 'operator_qualification_sha256': QUALIFICATION_SHA,
              'helper_sha256s': {str(p): sha(p) for p in (Path(__file__), HERE / 'fixture.py', HERE / 'backend.py', HERE / 'accelerator_guard_v2.py', HERE / 'cpu_import_policy_v3.py')},
              'evidence_directory': str(args.evidence_dir), 'torch_imported': False}
    try:
        policy_spec = importlib.util.spec_from_file_location('private_cpu_import_policy_v3', HERE / 'cpu_import_policy_v3.py')
        policy = importlib.util.module_from_spec(policy_spec); policy_spec.loader.exec_module(policy)
        report['cpu_import_policy_requested'] = copy.deepcopy(policy.DESCRIPTION)
        options = source_gate(); report['options'] = options
        report['fixture_AST_contract'] = {'block_initialization_unchanged': True, 'input_arithmetic_unchanged': True}
        if args.check_only:
            report.update(passed=True, phase='source-check-only-passed', native_calls=0)
            return 0
        for key in ('MAX_JOBS', 'TORCHINDUCTOR_COMPILE_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
            os.environ[key] = '1'
        os.environ['TORCHINDUCTOR_CACHE_DIR'] = str(args.evidence_dir / 'inductor-cache')
        os.environ['TRITON_CACHE_DIR'] = str(args.evidence_dir / 'triton-cache')
        report['compiler_environment'] = {key: os.environ[key] for key in ('MAX_JOBS', 'TORCHINDUCTOR_COMPILE_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'TORCHINDUCTOR_CACHE_DIR', 'TRITON_CACHE_DIR')}
        args.evidence_dir.mkdir()
        persist_startup(args.evidence_dir, report)
        no_fault(); report['phase'] = 'CPU-import'
        sys.path.insert(0, str(SOURCE))
        sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-comfy-compiler',
                    '--disable-pinned-memory', '--disable-async-offload', '--use-pytorch-cross-attention', '--disable-xformers']
        import comfy.options
        comfy.options.enable_args_parsing()
        import torch
        report['torch_imported'] = True
        report['phase'] = 'install-accelerator-traps-before-Kitchen-Inductor'
        guard_spec = importlib.util.spec_from_file_location('private_cpu_accelerator_guard_v2', HERE / 'accelerator_guard_v2.py')
        guard = importlib.util.module_from_spec(guard_spec); guard_spec.loader.exec_module(guard)
        guard.install(torch, report)
        require_cpu_policy = policy.install(torch, report, guard)
        require_cpu_policy()
        report['phase'] = 'guarded-Kitchen-Inductor-import'
        import comfy.ops
        import comfy.model_management
        from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep
        from torch._dynamo.utils import counters
        require_cpu_policy()
        require(not torch.xpu.is_initialized(), 'XPU unexpectedly initialized')
        torch.set_num_threads(1); torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)
        report.update(torch=str(torch.__version__), torch_imported=True,
            dynamo_limits={'recompile_limit': torch._dynamo.config.recompile_limit,
                           'accumulated_recompile_limit': torch._dynamo.config.accumulated_recompile_limit},
            determinism={'enabled': torch.are_deterministic_algorithms_enabled(), 'warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
                         'threads': torch.get_num_threads(), 'interop_threads': torch.get_num_interop_threads()},
            source_commit=subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip())
        require(report['dynamo_limits'] == {'recompile_limit': 8, 'accumulated_recompile_limit': 256}, 'Compiler limits changed')
        spec = importlib.util.spec_from_file_location('private_cpp_block_backend', HERE / 'backend.py')
        backend = importlib.util.module_from_spec(spec); spec.loader.exec_module(backend)
        rms, activations = backend.initialize()
        spec = importlib.util.spec_from_file_location('private_cpp_block_fixture', HERE / 'fixture.py')
        fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
        report['binary'] = {'path': str(backend.BINARY), 'sha256': backend.BINARY_SHA}
        block = fixture.make_block(torch, BasicAVTransformerBlock, comfy)
        require(sum(p.numel() for p in block.parameters()) == 43654 and
                sum(p.numel() * p.element_size() for p in block.parameters()) == 87308,
                'Tiny fixture parameter identity changed')
        original_forward = type(block).forward
        report['block_dimensions'] = {'video': 32, 'audio': 32, 'heads': 1, 'head_dim': 32, 'context_tokens': 8, 'audio_tokens': 26}
        report['video_stages'] = [64, 256]
        def raw(tensor):
            return tensor.detach().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
        def state():
            return {name: {'id': id(value), 'sha256': hashlib.sha256(raw(value)).hexdigest(),
                           'shape': list(value.shape), 'stride': list(value.stride()), 'dtype': str(value.dtype), 'device': str(value.device)}
                    for name, value in list(block.named_parameters()) + list(block.named_buffers())}
        initial_state = state(); report['state_before'] = initial_state
        python_backend = activations.make_backend(options, args.evidence_dir / 'python-graphs', expected_count=15)
        cpp_backend = backend.make_backend(options, args.evidence_dir / 'cpp-graphs', rms, activations)
        compiled = {'python': torch.compile(block, backend=python_backend, fullgraph=True, dynamic=False),
                    'cpp': torch.compile(block, backend=cpp_backend, fullgraph=True, dynamic=False)}
        def snapshot():
            return {key: dict(value) for key, value in counters.items()}
        def difference(after, before):
            return {group: {key: after.get(group, {}).get(key, 0) - before.get(group, {}).get(key, 0)
                            for key in set(after.get(group, {})) | set(before.get(group, {}))}
                    for group in set(after) | set(before)}
        def execute(function, arm, tokens, seed, expected_new_graphs):
            no_fault()
            require_cpu_policy()
            x, kwargs = fixture.make_inputs(torch, CompressedTimestep, tokens, seed)
            before = snapshot()
            result = function(tuple(value.clone() for value in x), **kwargs)
            require_cpu_policy()
            delta = difference(snapshot(), before)
            report['calls'].append({'arm': arm, 'video_tokens': tokens, 'seed': seed,
                'expected_new_graphs': expected_new_graphs, 'counter_delta': delta, 'cpu_import_policy_schema': policy.DESCRIPTION['schema']})
            require(delta.get('stats', {}).get('unique_graphs', 0) == expected_new_graphs, 'Unexpected graph reuse/recompile/fallback: ' + arm)
            require(not sum(delta.get('graph_break', {}).values()) and not sum(delta.get('unimplemented', {}).values()),
                    'Graph break or unsupported fallback: ' + arm)
            require(type(block).forward is original_forward and state() == initial_state, 'Original module/parameter state changed')
            require(not torch.xpu.is_initialized(), 'XPU initialized during CPU execution')
            return result
        with torch.inference_mode():
            for tokens in (64, 256):
                for seed in (17, 123):
                    report['current_case'] = {'video_tokens': tokens, 'seed': seed}
                    report['phase'] = 'eager'
                    outputs = {'eager': execute(block, 'eager', tokens, seed, 0)}
                    for arm in ('python', 'cpp'):
                        report['phase'] = arm + '-compile-and-execute'
                        outputs[arm] = execute(compiled[arm], arm, tokens, seed, int(seed == 17))
                        report['phase'] = arm + '-repeat'
                        outputs[arm + '_repeat'] = execute(compiled[arm], arm + '_repeat', tokens, seed, 0)
                    comparisons = []
                    for index, name in enumerate(('video', 'audio')):
                        tensors = {arm: values[index] for arm, values in outputs.items()}
                        expected = raw(tensors['eager'])
                        meta = lambda value: {'shape': list(value.shape), 'stride': list(value.stride()), 'dtype': str(value.dtype), 'device': str(value.device)}
                        rows = {arm: {'sha256': hashlib.sha256(raw(value)).hexdigest(), 'metadata': meta(value),
                                      'finite': bool(torch.isfinite(value).all()), 'exact_eager_bytes': raw(value) == expected}
                                for arm, value in tensors.items()}
                        passed = all(row['finite'] and row['exact_eager_bytes'] and row['metadata'] == rows['eager']['metadata'] for row in rows.values())
                        comparisons.append({'output': name, 'passed': passed, 'arms': rows})
                    report['rows'].append({**report['current_case'], 'outputs': comparisons})
                    require(all(row['passed'] for row in comparisons), 'Tiny block byte/metadata/finite parity failed')
        no_fault(); require_cpu_policy(); report['phase'] = 'graph-census'
        report['graphs'] = {}
        for arm in ('python', 'cpp'):
            paths = sorted((args.evidence_dir / (arm + '-graphs')).glob('graph-*.json'))
            require(len(paths) == 2, 'Two stage receipts required per arm')
            records = []
            for path in paths:
                value = json.loads(path.read_text())
                counts = {'rms': len(value.get('replacements', [])),
                          **{kind: sum(row['kind'] == kind for row in value.get('activation_replacements', [])) for kind in ('sigmoid', 'gelu')}}
                require(counts == {'rms': 15, 'sigmoid': 6, 'gelu': 2}, 'FX operation census changed')
                require(value['status'] == ('compiled-native-activations-boundary' if arm == 'python' else 'compiled-cpp-cpu-boundaries'), 'Graph receipt did not pass')
                require(value['options'] == options, 'Graph compiler options changed')
                records.append({'path': str(path), 'sha256': sha(path), 'counts': counts, 'status': value['status']})
            report['graphs'][arm] = records
        report['generated_wrapper_census'] = emitted_census(args.evidence_dir / 'inductor-cache')
        report['state_after'] = state()
        require(report['state_after'] == initial_state, 'Final state changed')
        report.update(passed=True, phase='completed-cpu-compiled-block', xpu_initialized=False, native_model_calls=len(report['calls']))
    except BaseException as error:
        report.update(error=repr(error), traceback=traceback.format_exc())
    finally:
        if report.get('accelerator_guard_tripped') or report.get('accelerator_guard_attempts'):
            report['passed'] = False
            report.setdefault('error', 'CPU diagnostic remains halted after accelerator access')
        report['torch_imported'] = 'torch' in sys.modules
        report['fault_present_at_exit'] = FAULT.exists()
        report['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if 'torch' in sys.modules:
            report['xpu_initialized_at_exit'] = sys.modules['torch'].xpu.is_initialized()
            report['cuda_initialized_at_exit'] = sys.modules['torch'].cuda.is_initialized()
        with args.output.open('x') as out:
            json.dump(report, out, indent=2); out.write('\n')
        print(json.dumps({'passed': report['passed'], 'phase': report['phase'], 'output': str(args.output), 'error': report.get('error')}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
