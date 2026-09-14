#!/usr/bin/env python3
"""CPU-only composed native multi-block capture gate; retain all tested evidence."""
import argparse
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import traceback

SCRIPTS = Path(__file__).resolve().parent
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')
INDICES = (0, 47)
OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
           'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
           'max_autotune': False, 'max_autotune_gemm': False}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_fault():
    if FAULT.exists():
        raise RuntimeError('Existing fault latch prohibits native work')


def function_ast(path, name):
    found = [node for node in ast.walk(ast.parse(path.read_text()))
             if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(found) != 1:
        raise RuntimeError('Expected exactly one fixture function: ' + name)
    return ast.Module(body=found, type_ignores=[])


def opaque_calls(path):
    counts = {'rms': 0, 'sigmoid': 0, 'gelu': 0}
    targets = {'torch.ops.ltx_exact_rms.native.default': 'rms',
               'torch.ops.ltx_exact_activations.sigmoid.default': 'sigmoid',
               'torch.ops.ltx_exact_activations.gelu.default': 'gelu'}
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            kind = targets.get(ast.unparse(node.func))
            if kind:
                counts[kind] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True,
                        help='New exclusive directory; source snapshots and caches are retained')
    parser.add_argument('--adapter-sha256', required=True)
    parser.add_argument('--indices', type=int, nargs='+', default=list(INDICES),
                        help='Distinct zero-based blocks, sorted for composed native execution')
    args = parser.parse_args()
    if (not args.indices or len(set(args.indices)) != len(args.indices)
            or any(index < 0 or index >= 48 for index in args.indices)):
        parser.error('--indices must contain distinct block indices in 0..47')
    indices = tuple(sorted(args.indices))
    if args.output.exists() or args.evidence.exists():
        raise FileExistsError('Output and evidence paths must both be new')
    evidence = args.evidence.resolve()
    report = {'schema': 'ltx25.multiblock-capture-cpu.v1', 'passed': False,
              'phase': 'fault-gate', 'checks': [], 'rows': [], 'graphs': [],
              'scope': 'Actual composed tiny native BF16 CPU blocks through native ModelPatcher lifecycle and complete options registry',
              'not_claimed': ['XPU qualification', 'full checkpoint quality', 'generation speed'],
              'selected_blocks': list(indices), 'owned_blocks': 48, 'split': 21,
              'block_dimensions': {'video': 32, 'audio': 32, 'heads': 1, 'head_dim': 32},
              'video_tokens': [64, 256], 'audio_tokens': 26, 'seeds': [17, 123],
              'fullgraph': True, 'dynamic': False, 'guard_filter': None,
              'evidence_directory': str(evidence), 'compilation_executed': False}

    def check(value, label):
        if not value:
            raise AssertionError(label)
        report['checks'].append(label)

    try:
        check_fault()
        check(len(args.adapter_sha256) == 64 and
              all(c in '0123456789abcdef' for c in args.adapter_sha256), 'adapter_hash_format')
        adapter_path = SCRIPTS / 'ltx_multiblock_compile.py'
        check(digest(adapter_path) == args.adapter_sha256, 'adapter_source_hash_matches')
        evidence.mkdir(parents=True, exist_ok=False)
        snapshots = evidence / 'tested-source'
        snapshots.mkdir()
        paths = [Path(__file__).resolve(), adapter_path,
                 SCRIPTS / 'ltx_layer_shard.py', SCRIPTS / 'ltx_native_activations_backend.py',
                 SCRIPTS / 'ltx_native_rms_backend.py',
                 SCRIPTS / 'test-ltx-block-compile-route.py',
                 SCRIPTS / 'test-ltx-block-compile-cpu.py']
        report['source_snapshots'] = []
        for source in paths:
            target = snapshots / source.name
            target.write_bytes(source.read_bytes())
            report['source_snapshots'].append({'source': str(source), 'snapshot': str(target),
                                               'sha256': digest(target)})
        check(digest(snapshots / adapter_path.name) == args.adapter_sha256,
              'copied_adapter_hash_matches')
        report['comfy_commit'] = subprocess.check_output(
            ['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
        report['comfy_sources'] = []
        for name in ('comfy/model_patcher.py', 'comfy/patcher_extension.py', 'comfy/ops.py',
                     'comfy/ldm/lightricks/av_model.py', 'comfy/ldm/lightricks/model.py'):
            target = snapshots / 'comfy-provenance' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / name).read_bytes())
            report['comfy_sources'].append({'source': str(SOURCE / name),
                                            'snapshot': str(target), 'sha256': digest(target)})
        os.environ.update(TORCHINDUCTOR_COMPILE_THREADS='1', OMP_NUM_THREADS='1',
                          MKL_NUM_THREADS='1',
                          TORCHINDUCTOR_CACHE_DIR=str(evidence / 'inductor-cache'),
                          TRITON_CACHE_DIR=str(evidence / 'triton-cache'))
        report['compiler_environment'] = {key: os.environ[key] for key in (
            'TORCHINDUCTOR_COMPILE_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
            'TORCHINDUCTOR_CACHE_DIR', 'TRITON_CACHE_DIR')}
        check_fault()
        report['phase'] = 'import'
        sys.path.insert(0, str(SOURCE))
        sys.path.insert(0, str(snapshots))
        sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-comfy-compiler',
                    '--disable-async-offload', '--disable-pinned-memory',
                    '--use-pytorch-cross-attention', '--disable-xformers']
        import comfy.options
        comfy.options.enable_args_parsing()
        import torch
        from torch import nn
        import comfy.ops
        import comfy.utils
        from comfy.model_patcher import ModelPatcher
        from comfy.patcher_extension import CallbacksMP
        from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep, LTXAVModel
        from torch._dynamo.utils import counters
        from ltx_layer_shard import LTXLayerShardedPatcher, KEY, CACHE_KEY, _forward_transfers
        adapter = importlib.import_module('ltx_multiblock_compile')
        check(Path(adapter.__file__).resolve() == snapshots / adapter_path.name,
              'import_uses_copied_adapter')
        check(adapter.OPTIONS == OPTIONS, 'unchanged_compiler_options')
        report['options'] = dict(adapter.OPTIONS)
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)
        report['torch'] = str(torch.__version__)
        report['dynamo_limits'] = {key: getattr(torch._dynamo.config, key) for key in
                                  ('recompile_limit', 'accumulated_recompile_limit')}
        report['determinism'] = {'enabled': torch.are_deterministic_algorithms_enabled(),
                                 'warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
                                 'cpu_threads': torch.get_num_threads(),
                                 'interop_threads': torch.get_num_interop_threads()}
        namespace = {'torch': torch, 'nn': nn, 'comfy': comfy,
                     'BasicAVTransformerBlock': BasicAVTransformerBlock,
                     'CompressedTimestep': CompressedTimestep}
        for name, function in (('test-ltx-block-compile-route.py', 'make_block'),
                               ('test-ltx-block-compile-cpu.py', 'inputs')):
            path = snapshots / name
            exec(compile(function_ast(path, function), str(path), 'exec'), namespace)
        make_block, inputs = namespace['make_block'], namespace['inputs']
        cpu = torch.device('cpu')

        class TinyDiffusion(LTXAVModel):
            def __init__(self):
                nn.Module.__init__(self)
                self.transformer_blocks = nn.ModuleList([make_block() for _ in range(48)])
                # Distinct deterministic final-block weights make routing mistakes observable.
                with torch.no_grad():
                    for parameter in self.transformer_blocks[47].parameters():
                        parameter.mul_(0.875)

        class TinyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.diffusion_model = TinyDiffusion()
                self.current_patcher = None

            def get_dtype(self):
                return torch.bfloat16

        def ownership(patcher):
            shard, = patcher.get_additional_models_with_key(KEY)
            return [(prefix + name, id(value), list(value.shape), str(value.dtype), str(value.device))
                    for prefix, owner in (('primary/', patcher.model), ('secondary/', shard.model))
                    for name, value in list(owner.named_parameters()) + list(owner.named_buffers())]

        report['phase'] = 'instantiate'
        report['fixture_final_block_weight_multiplier'] = 0.875
        parent = LTXLayerShardedPatcher.install(ModelPatcher(TinyModel(), cpu, cpu), cpu, cpu, 21)
        original_ownership = ownership(parent)
        original_routes = parent.model_options['transformer_options']['patches_replace']['dit'].copy()
        candidate = adapter.apply_blocks_compile(parent, indices, receipt_root=evidence / 'graphs',
                                                  compiler=torch.compile)
        routes = candidate.model_options['transformer_options']['patches_replace']['dit']
        check(ownership(candidate) == original_ownership, 'registered_ownership_unchanged')
        check(all(parent.model_options['transformer_options']['patches_replace']['dit'][key] is route
                  for key, route in original_routes.items()), 'parent_routes_unchanged')
        check(type(candidate).pre_run is ModelPatcher.pre_run, 'native_pre_run_method')
        candidate.pre_run()
        check(candidate.model.current_patcher is candidate, 'native_pre_run_binds_candidate')
        options = comfy.utils.deepcopy_list_dict(candidate.model_options['transformer_options'])
        options['callbacks'] = candidate.callbacks
        options['wrappers'] = candidate.wrappers
        options.update(cond_or_uncond=[0], sigmas=torch.tensor([1.0]),
                       sample_sigmas=torch.tensor([1.0, 0.5, 0.0]))
        for index in indices:
            check(options['callbacks'][CallbacksMP.ON_PRE_RUN][adapter.LIFECYCLE_KEY][0]
                  is routes[('double_block', index)]._lifecycle,
                  f'aggregate_lifecycle_present_in_capture_registry_{index}')
        native_path = snapshots / 'comfy-provenance/comfy/ldm/lightricks/av_model.py'
        native_functions = {}
        for index in indices:
            native_ns = {'block': routes[('double_block', index)].block}
            exec(compile(function_ast(native_path, 'block_wrap'), str(native_path), 'exec'), native_ns)
            native_functions[index] = native_ns['block_wrap']

        def run(x, kwargs, compiled):
            intermediates = []

            def execute(*positional):
                opts = positional[5]
                opts[CACHE_KEY][('prior', cpu)] = (x[0], x[0])
                current = tuple(t.clone() for t in x)
                for index in indices:
                    chosen = routes[('double_block', index)]
                    if not compiled:
                        chosen = chosen.original_route
                    values = {'img': current, 'attention_mask': None,
                              **kwargs, 'transformer_options': opts}
                    current = chosen(values, {'original_block': native_functions[index]})['img']
                    intermediates.append(current)
                return current

            with torch.inference_mode():
                _forward_transfers(execute, None, None, None, None, None, options)
            return intermediates

        def graph_receipts():
            rows = []
            for index in indices:
                directory = evidence / 'graphs' / f'block-{index:02d}'
                paths = sorted(directory.glob('graph-*.json'))
                for path in paths:
                    entry = json.loads(path.read_text())
                    activations = entry.get('activation_replacements', [])
                    counts = {kind: sum(row['kind'] == kind for row in activations)
                              for kind in ('sigmoid', 'gelu')}
                    check(entry['status'] == 'compiled-native-activations-boundary' and
                          len(entry.get('replacements', [])) == 15 and
                          counts == {'sigmoid': 6, 'gelu': 2} and entry['options'] == OPTIONS,
                          f'graph_receipt_exact_native_operations_{index}_{entry["graph"]}')
                    rows.append({'block': index, 'graph': entry['graph'], 'path': str(path),
                                 'sha256': digest(path), 'rms_count': 15,
                                 'activation_counts': counts, 'status': entry['status']})
            return rows

        counters.clear()
        for stage, tokens in enumerate((64, 256), start=1):
            for seed in (17, 123):
                check_fault()
                report['current_case'] = {'video_tokens': tokens, 'seed': seed}
                x, kwargs = inputs(tokens, seed)
                report['phase'] = 'eager_composed'
                expected = run(x, kwargs, False)
                check_fault()
                report['phase'] = 'compiled_composed'
                report['compilation_executed'] = True
                actual = run(x, kwargs, True)
                check_fault()
                report['phase'] = 'repeat_composed'
                repeated = run(x, kwargs, True)
                row = {**report['current_case'], 'blocks': []}
                report['rows'].append(row)
                for index, refs, outputs, repeats in zip(indices, expected, actual, repeated):
                    block_row = {'index': index, 'outputs': []}
                    row['blocks'].append(block_row)
                    for name, ref, got, again in zip(('video', 'audio'), refs, outputs, repeats):
                        ref_bytes = ref.contiguous().view(torch.uint8)
                        got_bytes = got.contiguous().view(torch.uint8)
                        again_bytes = again.contiguous().view(torch.uint8)
                        result = {'name': name, 'shape': list(got.shape), 'dtype': str(got.dtype),
                                  'device': str(got.device), 'stride': list(got.stride()),
                                  'finite': all(bool(torch.isfinite(t).all()) for t in (ref, got, again)),
                                  'exact_eager': torch.equal(ref_bytes, got_bytes),
                                  'exact_repeat': torch.equal(got_bytes, again_bytes),
                                  'eager_sha256': hashlib.sha256(ref_bytes.numpy().tobytes()).hexdigest(),
                                  'compiled_sha256': hashlib.sha256(got_bytes.numpy().tobytes()).hexdigest(),
                                  'repeat_sha256': hashlib.sha256(again_bytes.numpy().tobytes()).hexdigest()}
                        block_row['outputs'].append(result)
                        check(result['finite'] and result['exact_eager'] and result['exact_repeat'],
                              f'exact_composed_{tokens}_{seed}_block_{index}_{name}')
                report['graphs'] = graph_receipts()
                check(all(sum(g['block'] == index for g in report['graphs']) == stage
                          for index in indices), f'one_graph_per_block_per_stage_{tokens}_{seed}')
                check(counters['stats']['unique_graphs'] == stage * len(indices) and
                      counters['aot_autograd']['ok'] == stage * len(indices) and
                      not counters['graph_break'] and not counters['aot_autograd']['not_ok'] and
                      not counters['unimplemented'], f'no_extra_graphs_or_fallback_{tokens}_{seed}')
        report['phase'] = 'emitted_wrapper_audit'
        wrappers = []
        for path in sorted((evidence / 'inductor-cache').rglob('*.py')):
            source = path.read_text()
            if 'torch.ops.ltx_exact_rms.native.default(' not in source:
                continue
            counts = opaque_calls(path)
            check(counts == {'rms': 15, 'sigmoid': 6, 'gelu': 2},
                  'emitted_wrapper_preserves_native_operations_' + path.stem)
            wrappers.append({'path': str(path), 'sha256': digest(path), 'opaque_calls': counts})
        report['generated_wrappers'] = wrappers
        report['wrapper_accounting'] = 'Backend receipts bind two graphs to each block; physical generated code can be shared across block instances.'
        check(bool(wrappers), 'actual_inductor_wrappers_retained')
        candidate.cleanup()
        check(candidate.model.current_patcher is None, 'native_cleanup_clears_execution')
        restored = adapter.remove_blocks_compile(candidate)
        check(ownership(restored) == original_ownership, 'restored_registered_ownership_unchanged')
        check(all(restored.model_options['transformer_options']['patches_replace']['dit'][key] is route
                  for key, route in original_routes.items()), 'restored_original_routes')
        check_fault()
        check(all(digest(row['source']) == row['sha256'] for row in report['comfy_sources']),
              'native_comfy_sources_stable_during_test')
        report.update(passed=True, phase='completed')
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        if FAULT.exists():
            report['fault_sha256'] = digest(FAULT)
    finally:
        if 'counters' in locals():
            report['dynamo_counters'] = {key: dict(value) for key, value in counters.items()}
        report['torch_imported'] = 'torch' in sys.modules
        report['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
    print(json.dumps({key: report[key] for key in ('passed', 'phase', 'max_rss_kib')}))
    if 'error' in report:
        print(report['error'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
