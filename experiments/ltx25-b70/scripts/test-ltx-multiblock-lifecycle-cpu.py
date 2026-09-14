#!/usr/bin/env python3
"""CPU multiblock native-pre_run lifecycle gates; compiler dispatch spy only."""
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

LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--adapter-sha256', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json').exists():
        raise RuntimeError('Existing fault prohibits native imports')
    if hashlib.sha256(args.adapter.read_bytes()).hexdigest() != args.adapter_sha256:
        raise RuntimeError('Adapter source differs from selected pin')
    if args.output.exists():
        raise FileExistsError(args.output)
    os.environ.update(TORCHINDUCTOR_COMPILE_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    report = {'scope': 'CPU lifecycle gate with native ModelPatcher.pre_run; compiler replaced by dispatch spy; no GPU/checkpoint/speed claim',
              'passed': False, 'phase': 'prepare', 'checks': []}
    paths = [Path(__file__), args.adapter, LANE / 'scripts/ltx_layer_shard.py',
             LANE / 'scripts/test-ltx-block-compile-route.py', LANE / 'scripts/test-ltx-block-compile-cpu.py',
             SOURCE / 'comfy/model_patcher.py', SOURCE / 'comfy/ldm/lightricks/av_model.py']
    report['sha256s'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    args.evidence.mkdir(parents=True, exist_ok=False)
    from contextlib import nullcontext
    with nullcontext(args.evidence.resolve()) as root:
        os.environ['TORCHINDUCTOR_CACHE_DIR'] = str(root / 'inductor')
        os.environ['TRITON_CACHE_DIR'] = str(root / 'triton')
        try:
            (root / 'scripts').mkdir()
            target = root / 'scripts/ltx_multiblock_compile.py'
            target.write_bytes(args.adapter.read_bytes())
            os.environ['LTX_ENCODER_RUN_DIR'] = str(root / 'runtime')
            candidate_source = target.read_text()
            report['effective_adapter_sha256'] = hashlib.sha256(candidate_source.encode()).hexdigest()
            sys.path.insert(0, str(SOURCE))
            sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-comfy-compiler',
                        '--disable-async-offload', '--disable-pinned-memory', '--use-pytorch-cross-attention', '--disable-xformers']
            import comfy.options
            comfy.options.enable_args_parsing()
            import torch
            from torch import nn
            import comfy.ops
            from comfy.model_patcher import ModelPatcher
            from comfy.patcher_extension import CallbacksMP
            from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep, LTXAVModel
            from ltx_layer_shard import LTXLayerShardedPatcher, _Shard, KEY, CACHE_KEY, _forward_transfers, _verify_placement
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
            torch.use_deterministic_algorithms(True, warn_only=False)
            report['torch'] = torch.__version__
            mod = types.ModuleType('ltx_multiblock_lifecycle_candidate')
            mod.__file__ = str(target)
            sys.modules[mod.__name__] = mod
            exec(compile(candidate_source, str(target), 'exec'), mod.__dict__)
            ns = {'torch': torch, 'nn': nn, 'comfy': comfy,
                  'BasicAVTransformerBlock': BasicAVTransformerBlock, 'CompressedTimestep': CompressedTimestep}
            for file, name in [('test-ltx-block-compile-route.py', 'make_block'),
                               ('test-ltx-block-compile-cpu.py', 'inputs')]:
                tree = ast.parse((LANE / 'scripts' / file).read_text())
                function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
                exec(compile(ast.Module(body=[function], type_ignores=[]), file, 'exec'), ns)
            make_block, inputs = ns['make_block'], ns['inputs']
            cpu = torch.device('cpu')
            class TinyDiffusion(LTXAVModel):
                def __init__(self):
                    nn.Module.__init__(self)
                    self.transformer_blocks = nn.ModuleList([make_block() for _ in range(48)])
            class TinyModel(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.diffusion_model = TinyDiffusion()
                    self.current_patcher = None
                def get_dtype(self):
                    return torch.bfloat16
            parent = LTXLayerShardedPatcher.install(ModelPatcher(TinyModel(), cpu, cpu), cpu, cpu, 21)
            original_routes = parent.model_options['transformer_options']['patches_replace']['dit'].copy()
            original_callbacks = parent.callbacks
            def ownership(p):
                secondary, = p.get_additional_models_with_key(KEY)
                return [(prefix, name, id(t), tuple(t.shape), str(t.dtype))
                        for prefix, owner in [('primary', p.model), ('secondary', secondary.model)]
                        for name, t in owner.named_parameters()]
            original_ownership = ownership(parent)
            calls = []
            def fake_compiler(block, **kwargs):
                def spy(x, **kw):
                    calls.append('compute')
                    return x
                return spy
            selection = (0, 20, 21, 47)
            candidate = mod.apply_blocks_compile(parent, selection, receipt_root=root / 'graphs', compiler=fake_compiler)
            route = candidate.model_options['transformer_options']['patches_replace']['dit'][('double_block', 21)]
            guard = route._lifecycle
            def check(value, label):
                if not value:
                    raise AssertionError(label)
                report['checks'].append(label)
            def rejects(call, label):
                previous_calls = len(calls)
                try:
                    call()
                except (RuntimeError, TypeError, ValueError):
                    check(len(calls) == previous_calls, label + '_before_compiled_compute')
                else:
                    raise AssertionError('Missing rejection: ' + label)
            original_binding = mod._registered_bindings
            binding_calls = []
            def counted_binding(*arguments, **keywords):
                binding_calls.append(arguments[-1])
                return original_binding(*arguments, **keywords)
            mod._registered_bindings = counted_binding
            report['phase'] = 'native_pre_run_rejection_gate'
            check(type(candidate).pre_run is ModelPatcher.pre_run, 'actual_native_pre_run_method')
            check(candidate.get_all_callbacks(CallbacksMP.ON_PRE_RUN) == [guard, _verify_placement],
                  'lifecycle_guard_first_original_placement_second')
            rejects(lambda: route({}, {}), 'reject_missing_native_pre_run')
            binding_calls.clear()
            candidate.pre_run()
            report['registry_walks_per_pre_run'] = len(binding_calls)
            check(len(binding_calls) == 1, 'expected_pre_run_registry_walks')
            x, kwargs = inputs(64, 17)
            numerical = {'img': x, 'attention_mask': None, **kwargs}
            binding_calls.clear()
            route._call_native(numerical)
            report['registry_walks_per_native_dispatch'] = len(binding_calls)
            check(len(binding_calls) == 1, 'expected_dispatch_registry_walks')
            check(len(calls) == 1, 'valid_native_pre_run_permits_dispatch')
            sibling = candidate.clone()
            sibling.pre_run()
            route._call_native(numerical)
            check(len(calls) == 2, 'shared_clone_uses_its_own_native_pre_run')

            saved = candidate.model
            candidate.model = TinyModel()
            try:
                rejects(candidate.pre_run, 'reject_replaced_top_level_model')
            finally:
                candidate.model = saved
            saved_diffusion = parent.model.diffusion_model
            parent.model.diffusion_model = TinyDiffusion()
            try:
                rejects(candidate.pre_run, 'reject_replaced_diffusion_owner')
            finally:
                parent.model.diffusion_model = saved_diffusion
            saved_models = candidate.additional_models[KEY]
            old_owner = saved_models[0].model
            # Internally consistent replacement sharing the same block objects:
            # this escaped the previous retained-owner-only validation.
            candidate.additional_models[KEY] = [ModelPatcher(_Shard(list(old_owner.blocks), torch.bfloat16), cpu, cpu)]
            try:
                rejects(candidate.pre_run, 'reject_replaced_secondary_owner')
            finally:
                candidate.additional_models[KEY] = saved_models
            for field in ('patches', 'weight_wrapper_patches', 'injections', 'wrappers'):
                prior = getattr(candidate, field)
                setattr(candidate, field, {'late': object()})
                try:
                    rejects(candidate.pre_run, 'reject_late_' + field)
                finally:
                    setattr(candidate, field, prior)
            callback_calls = []
            candidate.add_callback_with_key(CallbacksMP.ON_PRE_RUN, 'foreign', lambda p: callback_calls.append('ran'))
            try:
                rejects(candidate.pre_run, 'reject_late_foreign_callback')
                check(callback_calls == [], 'appended_foreign_callback_not_executed')
            finally:
                candidate.remove_callbacks_with_key(CallbacksMP.ON_PRE_RUN, 'foreign')
            # remove_callbacks_with_key leaves an empty group on this pin.
            candidate.callbacks[CallbacksMP.ON_PRE_RUN].pop('foreign', None)
            candidate.pre_run()
            saved_callbacks = candidate.callbacks
            candidate.callbacks = {CallbacksMP.ON_PRE_RUN: {KEY: [_verify_placement]}}
            try:
                candidate.pre_run()  # Native placement still runs; lifecycle was removed.
                rejects(lambda: route({}, {}), 'removed_guard_rejected_before_routing')
            finally:
                candidate.callbacks = saved_callbacks
            candidate.pre_run()
            candidate.weight_wrapper_patches = {'late_after_pre_run': object()}
            try:
                rejects(lambda: route({}, {}), 'late_patch_after_pre_run_rejected')
            finally:
                candidate.weight_wrapper_patches = {}
            parent.pre_run()
            rejects(lambda: route({}, {}), 'control_parent_cannot_dispatch_retained_compiler')
            candidate.pre_run()
            candidate.pre_run()
            candidate.weight_wrapper_patches = {'failed_pre_run': object()}
            try:
                rejects(candidate.pre_run, 'failed_pre_run_clears_previous_success')
            finally:
                candidate.weight_wrapper_patches = {}
            rejects(lambda: route({}, {}), 'cleared_success_requires_fresh_pre_run')
            candidate.pre_run()
            candidate.cleanup()
            rejects(lambda: route({}, {}), 'native_cleanup_clears_current_execution')
            candidate.pre_run()
            restored = mod.remove_blocks_compile(candidate)
            restored.pre_run()
            check(restored.callbacks == original_callbacks, 'restored_control_has_only_native_callbacks')
            check(restored.model_options['transformer_options']['patches_replace']['dit'] == original_routes,
                  'restored_control_has_original_routes')
            check(parent.callbacks == original_callbacks and ownership(parent) == original_ownership,
                  'parent_callbacks_and_registered_ownership_preserved')
            sibling.pre_run()
            route._call_native(numerical)
            check(len(calls) == 3, 'restoration_leaves_compiled_sibling_dispatch_intact')
            check(all(not isinstance(v, ModelPatcher) for v in vars(guard).values()),
                  'guard_stores_no_strong_patcher_reference')

            # Every validation still covers unselected registered blocks.
            primary = parent.model.diffusion_model._modules['_ltx_primary_blocks']
            saved_primary = primary[1]
            primary[1] = make_block()
            try:
                rejects(lambda: route({}, {}), 'unselected_registration_change_rejected')
            finally:
                primary[1] = saved_primary
            diffusion, routes, bindings = mod._routes(candidate, binding_indices=selection)
            check(tuple(bindings) == selection, 'all_selected_bindings_returned')
            check(len(mod._routes(candidate)) == 2, 'ordinary_routes_return_unchanged')
            check(len({id(routes[('double_block', i)]._lifecycle) for i in selection}) == 1,
                  'one_aggregate_lifecycle')
            for i in selection:
                selected = routes[('double_block', i)]
                check(selected.block is parent.model.diffusion_model.transformer_blocks[i],
                      'original_selected_block_identity_' + str(i))
            for invalid in ((), (1, 1), (True,), (-1,), (48,), ('24',)):
                rejects(lambda: mod.apply_blocks_compile(parent, invalid,
                        receipt_root=root / 'invalid', compiler=fake_compiler),
                        'invalid_selection_' + repr(invalid))
            sibling.pre_run()
            before_calls = len(calls)
            for i in selection:
                routes[('double_block', i)]._call_native(numerical)
            check(len(calls) == before_calls + len(selection), 'all_selected_routes_dispatch_after_restore')
            check(ownership(parent) == original_ownership, 'all_registered_parameters_still_original')
            rejects(lambda: mod.apply_blocks_compile(parent, selection,
                    receipt_root=root / 'graphs', compiler=fake_compiler),
                    'existing_graph_directories_rejected')
            sibling.pre_run()
            validations = []
            original_validate = mod.CompiledBlockRoute._validate
            def counted_validate(instance, **kw):
                validations.append(instance.index)
                return original_validate(instance, **kw)
            mod.CompiledBlockRoute._validate = counted_validate
            try:
                guard.validate_current_execution(route)
                check(validations == [21], 'dispatch_state_scan_only_current_selected_block')
                validations.clear()
                sibling.pre_run()
                check(validations == list(selection), 'pre_run_state_scans_every_selected_block')
            finally:
                mod.CompiledBlockRoute._validate = original_validate
            for i in selection:
                selected = routes[('double_block', i)]
                hook = selected.block.register_forward_pre_hook(lambda *a: None)
                try:
                    rejects(sibling.pre_run, 'selected_block_hook_pre_run_' + str(i))
                finally:
                    hook.remove()
                sibling.pre_run()
                hook = selected.block.register_forward_pre_hook(lambda *a: None)
                try:
                    rejects(lambda: selected._call_native(numerical),
                            'selected_block_late_hook_' + str(i))
                finally:
                    hook.remove()
            sibling.cleanup()
            report['compilation_executed'] = False
            report['lifecycle_metadata_capture_qualified'] = False
            report.update(passed=True, phase='completed')
        except Exception as error:
            report.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
            if 'counters' in locals():
                report['dynamo_counters'] = {k: dict(v) for k, v in counters.items()}
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
