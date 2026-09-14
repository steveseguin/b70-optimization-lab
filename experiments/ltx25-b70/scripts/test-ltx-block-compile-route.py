#!/usr/bin/env python3
"""CPU-only native block route/compiler unit gate; no checkpoint or speed claim."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import traceback

LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    os.environ.update(TORCHINDUCTOR_COMPILE_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    report = {'scope': 'CPU unit/capture gate: actual native tiny BF16 block through original route; no XPU, checkpoint quality, or speed evidence',
        'passed': False, 'phase': 'import', 'checks': [], 'rows': [],
        'source_commit': subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip(),
        'sha256s': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            Path(__file__), LANE / 'scripts/ltx_block_compile.py', LANE / 'scripts/ltx_layer_shard.py',
            LANE / 'scripts/test-ltx-block-compile-cpu.py', SOURCE / 'comfy/ldm/lightricks/av_model.py')}}
    with tempfile.TemporaryDirectory(prefix='ltx-compiled-route-cpu-') as cache:
        os.environ['TORCHINDUCTOR_CACHE_DIR'] = cache
        os.environ['TRITON_CACHE_DIR'] = str(Path(cache) / 'triton')
        try:
            sys.path.insert(0, str(SOURCE))
            sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-comfy-compiler',
                        '--disable-async-offload', '--disable-pinned-memory', '--use-pytorch-cross-attention', '--disable-xformers']
            import comfy.options
            comfy.options.enable_args_parsing()
            import torch
            from torch import nn
            import comfy.ops
            from comfy.model_patcher import ModelPatcher
            from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep, LTXAVModel
            from torch._dynamo.utils import counters
            import ltx_block_compile as compiler_adapter
            from ltx_layer_shard import LTXLayerShardedPatcher, _BlockRoute, _forward_transfers, CACHE_KEY, KEY
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
            torch.use_deterministic_algorithms(True, warn_only=False)
            report['torch'] = torch.__version__
            report['options'] = compiler_adapter.OPTIONS
            cpu = torch.device('cpu')

            def check(value, name):
                if not value:
                    raise AssertionError(name)
                report['checks'].append(name)

            def rejects(call, name):
                try:
                    call()
                except (RuntimeError, TypeError, ValueError):
                    report['checks'].append(name)
                else:
                    raise AssertionError('Expected rejection: ' + name)

            def make_block():
                block = BasicAVTransformerBlock(v_dim=32, a_dim=32, v_heads=1, a_heads=1,
                    vd_head=32, ad_head=32, v_context_dim=32, a_context_dim=32,
                    apply_gated_attention=True, cross_attention_adaln=True, dtype=torch.bfloat16,
                    device='cpu', operations=comfy.ops.manual_cast).eval()
                generator = torch.Generator(device='cpu').manual_seed(20260913)
                with torch.no_grad():
                    for name, p in block.named_parameters():
                        value = torch.randn(p.shape, generator=generator) * .02
                        if name.endswith('q_norm.weight') or name.endswith('k_norm.weight'):
                            value += 1
                        p.copy_(value)
                return block

            # Reuse the exact earlier unit fixture generator by extracting only
            # its function AST. The earlier script/main is never executed.
            fixture_path = LANE / 'scripts/test-ltx-block-compile-cpu.py'
            fixture_tree = ast.parse(fixture_path.read_text())
            inputs_ast = next(node for node in ast.walk(fixture_tree)
                              if isinstance(node, ast.FunctionDef) and node.name == 'inputs')
            fixture_namespace = {'torch': torch, 'CompressedTimestep': CompressedTimestep}
            exec(compile(ast.Module(body=[inputs_ast], type_ignores=[]), str(fixture_path), 'exec'), fixture_namespace)
            inputs = fixture_namespace['inputs']
            av_path = SOURCE / 'comfy/ldm/lightricks/av_model.py'
            native_ast = next(node for node in ast.walk(ast.parse(av_path.read_text()))
                              if isinstance(node, ast.FunctionDef) and node.name == 'block_wrap')
            block = make_block()
            original_route = _BlockRoute(cpu, cpu, True)
            report['phase'] = 'native_argument_mapping'
            calls = []
            def recorder(*positional, **keywords):
                calls.append((positional, keywords))
                return positional[0]
            native_namespace = {'block': recorder}
            exec(compile(ast.Module(body=[native_ast], type_ignores=[]), str(av_path), 'exec'), native_namespace)
            fake_compilers = []
            def fake_compiler(model, **kwargs):
                fake_compilers.append((model, kwargs))
                return recorder
            adapter = compiler_adapter.CompiledBlockRoute(block, original_route, compiler=fake_compiler)
            for optional in (False, True):
                x, kw = inputs(64, 17)
                routed = {'img': x, 'attention_mask': None, **kw}
                if optional:
                    routed.update(self_attention_mask=object(), v_prompt_timestep=object(), a_prompt_timestep=object())
                else:
                    for name in ('self_attention_mask', 'v_prompt_timestep', 'a_prompt_timestep'):
                        routed.pop(name, None)
                native_namespace['block_wrap'](routed)
                adapter._call_native(routed)
                native, translated = calls[-2:]
                check(native[0][0] is translated[0][0] and native[1].keys() == translated[1].keys() and
                      all(native[1][k] is translated[1][k] for k in native[1]), f'exact_source_mapping_optional_{optional}')
            check(fake_compilers[0][0] is block and fake_compilers[0][1] == {
                'backend': 'inductor', 'fullgraph': True, 'dynamic': False, 'options': compiler_adapter.OPTIONS},
                'original_module_and_fixed_compile_options')

            report['phase'] = 'clone_ownership_restore'
            class TinyDiffusion(LTXAVModel):
                def __init__(self):
                    nn.Module.__init__(self)
                    self.transformer_blocks = nn.ModuleList([make_block() for _ in range(48)])
            class TinyModel(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.diffusion_model = TinyDiffusion()
                def get_dtype(self):
                    return torch.bfloat16
            patcher = LTXLayerShardedPatcher.install(ModelPatcher(TinyModel(), cpu, cpu), cpu, cpu, 24)
            def ownership(p):
                shard, = p.get_additional_models_with_key(KEY)
                return [(prefix + name, id(t), tuple(t.shape), str(t.dtype), t.nbytes)
                        for prefix, owner in [('primary/', p.model), ('secondary/', shard.model)]
                        for name, t in list(owner.named_parameters()) + list(owner.named_buffers())]
            before = ownership(patcher)
            callbacks = patcher.model_options['transformer_options']['patches_replace']['dit'].copy()
            candidate = compiler_adapter.apply_block_compile(patcher, index=24)
            compiled_callbacks = candidate.model_options['transformer_options']['patches_replace']['dit']
            check(ownership(candidate) == before and candidate.model is patcher.model, 'shared_registered_ownership_unchanged')
            check(all(callbacks[k] is patcher.model_options['transformer_options']['patches_replace']['dit'][k] for k in callbacks),
                  'parent_callback_dictionary_unchanged')
            check(sum(compiled_callbacks[k] is not callbacks[k] for k in callbacks) == 1,
                  'only_selected_clone_callback_changes')
            sibling = candidate.clone()
            restored = compiler_adapter.remove_block_compile(candidate)
            check(restored.model_options['transformer_options']['patches_replace']['dit'][('double_block', 24)] is callbacks[('double_block', 24)],
                  'restore_exact_original_route')
            check(sibling.model_options['transformer_options']['patches_replace']['dit'][('double_block', 24)] is compiled_callbacks[('double_block', 24)],
                  'restore_does_not_change_sibling_or_input')
            check(ownership(restored) == before and all('forward' not in b.__dict__ for b in patcher.model.diffusion_model.transformer_blocks),
                  'restore_preserves_registration_and_forward_methods')
            rejects(lambda: compiler_adapter.apply_block_compile(candidate, 0), 'reject_second_compiled_block')
            rejects(lambda: compiler_adapter.apply_block_compile(patcher, 48), 'reject_out_of_range_block')
            rejects(lambda: compiler_adapter.remove_block_compile(patcher), 'reject_restore_without_compiler')
            rejects(lambda: compiler_adapter.CompiledBlockRoute(nn.Linear(1, 1), original_route), 'reject_foreign_block')
            rejects(lambda: compiler_adapter.CompiledBlockRoute(block, lambda a, b: None), 'reject_foreign_route')
            handle = block.register_forward_hook(lambda m, a, b: b)
            try:
                rejects(lambda: compiler_adapter.CompiledBlockRoute(block, original_route), 'reject_module_hook')
            finally:
                handle.remove()

            report['phase'] = 'forward_cache_lifetime'
            held = []
            for fail in (False, True):
                def executor(*positional, **kwargs):
                    cache = positional[5][CACHE_KEY]
                    held.append(cache)
                    cache['sentinel'] = torch.ones(1)
                    if fail:
                        raise RuntimeError('unit failure')
                    return True
                if fail:
                    rejects(lambda: _forward_transfers(executor, None, None, None, None, None, {}),
                            'forward_failure_propagates')
                else:
                    _forward_transfers(executor, None, None, None, None, None, {})
                check(held[-1] == {}, f'forward_cache_cleared_failure_{fail}')
            check(held[0] is not held[1], 'cache_not_shared_across_forwards')

            report['phase'] = 'compiled_route_capture'
            route = compiler_adapter.CompiledBlockRoute(block, original_route)
            native_namespace['block'] = block
            counters.clear()
            for tokens in (64, 256):
                for seed in (17, 123):
                    report['current_case'] = {'video_tokens': tokens, 'audio_tokens': 26, 'seed': seed}
                    x, kw = inputs(tokens, seed)
                    options = copy_options = {
                        'patches_replace': {'dit': {('double_block', i): original_route for i in range(48)}},
                        'wrappers': {'diffusion_model': {KEY: [_forward_transfers]}},
                        'callbacks': {'on_pre_run': {KEY: [patcher.verify_placement]}},
                        'cond_or_uncond': [0], 'sigmas': torch.tensor([1.0]),
                        'sample_sigmas': torch.tensor([1., .5, 0.]),
                        'original_shape': [1, 128, 4, 4 if tokens == 64 else 8, 4 if tokens == 64 else 8],
                        'run_vx': True, 'run_ax': True, 'a2v_cross_attn': True, 'v2a_cross_attn': True,
                    }
                    caches = []
                    def execute_route(chosen):
                        def run(*positional):
                            opts = positional[5]
                            # Simulate retained source/destination pairs left by
                            # an earlier routed block; they are not read by math.
                            opts[CACHE_KEY][('prior_tensor', cpu)] = (x[0], x[0])
                            caches.append(opts[CACHE_KEY])
                            args_dict = {'img': tuple(t.clone() for t in x), 'attention_mask': None,
                                         **kw, 'transformer_options': opts}
                            return chosen(args_dict, {'original_block': native_namespace['block_wrap']})['img']
                        with torch.inference_mode():
                            return _forward_transfers(run, None, None, None, None, None, options)
                    expected = execute_route(original_route)
                    actual = execute_route(route)
                    repeated = execute_route(route)
                    row = {**report['current_case'], 'outputs': []}
                    for name, ref, got, again in zip(('video', 'audio'), expected, actual, repeated):
                        row['outputs'].append({'name': name, 'shape': list(got.shape), 'dtype': str(got.dtype),
                            'exact_eager': torch.equal(ref.view(torch.uint8), got.view(torch.uint8)),
                            'exact_repeat': torch.equal(got.view(torch.uint8), again.view(torch.uint8)),
                            'finite': bool(torch.isfinite(got).all()), 'unequal_values': int((ref != got).sum()),
                            'max_abs_diff': float((ref.float() - got.float()).abs().max())})
                    report['rows'].append(row)
                    check(all(c == {} for c in caches) and len({id(c) for c in caches}) == 3,
                          f'actual_route_caches_cleared_{tokens}_{seed}')
                    check(all(v['exact_eager'] and v['exact_repeat'] and v['finite'] for v in row['outputs']),
                          f'native_route_exact_{tokens}_{seed}')
            report['dynamo_counters'] = {group: dict(value) for group, value in counters.items()}
            check(counters['stats']['unique_graphs'] == 2 and not counters['graph_break'], 'exactly_two_graphs_no_breaks')
            check(counters['aot_autograd']['ok'] == 2, 'two_successful_compiler_graphs')
            report['phase'], report['passed'] = 'completed', True
        except Exception as error:
            report.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
            if 'counters' in locals():
                report['dynamo_counters'] = {group: dict(value) for group, value in counters.items()}
        finally:
            report['max_parent_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x') as handle:
                json.dump(report, handle, indent=2)
                handle.write('\n')
    print(json.dumps({k: report[k] for k in ('passed', 'phase', 'max_parent_rss_kib')}, indent=2))
    if 'error' in report:
        print(report['error'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
