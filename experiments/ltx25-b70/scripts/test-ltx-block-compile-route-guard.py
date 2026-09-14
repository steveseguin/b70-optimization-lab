#!/usr/bin/env python3
"""Additive CPU guard gate, reusing the preserved route test without editing it."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import types

LANE = Path(__file__).resolve().parents[1]
BASE = LANE / 'scripts/test-ltx-block-compile-route.py'
ADAPTER = LANE / 'scripts/ltx_block_compile.py'
PATCH = LANE / 'patches/ltx-block-compile-ownership-guard.patch'


GUARD_TESTS = '''
            report['phase'] = 'additive_admission_and_stale_state_guards'
            for field in ('weight_wrapper_patches', 'injections', 'callbacks', 'wrappers'):
                prior = getattr(patcher, field)
                setattr(patcher, field, {'foreign': object()})
                try:
                    rejects(lambda: compiler_adapter.apply_block_compile(patcher), 'reject_foreign_' + field)
                finally:
                    setattr(patcher, field, prior)
            options = patcher.model_options['transformer_options']
            for field in ('callbacks', 'wrappers', 'patches'):
                options[field] = {'foreign': object()}
                try:
                    rejects(lambda: compiler_adapter.apply_block_compile(patcher), 'reject_inline_' + field)
                finally:
                    del options[field]
            selected = compiled_callbacks[('double_block', 24)]
            diffusion = patcher.model.diffusion_model
            owner, = patcher.get_additional_models_with_key(KEY)
            container = owner.model.blocks
            saved_block = container[0]
            container[0] = make_block()
            try:
                rejects(lambda: selected({}, {}), 'reject_changed_registered_slot_before_routing')
                rejects(lambda: compiler_adapter.apply_block_compile(patcher), 'reject_disagreeing_registration_at_admission')
            finally:
                container[0] = saved_block
            saved_tuple = diffusion.transformer_blocks
            object.__setattr__(diffusion, 'transformer_blocks', (saved_tuple[24],) + saved_tuple[1:24] + (saved_tuple[0],) + saved_tuple[25:])
            try:
                rejects(lambda: selected({}, {}), 'reject_changed_transformer_tuple')
            finally:
                object.__setattr__(diffusion, 'transformer_blocks', saved_tuple)
            owner.model.blocks = nn.ModuleList(list(container))
            try:
                rejects(lambda: selected({}, {}), 'reject_replaced_registered_container')
            finally:
                owner.model.blocks = container
            for field, changed in [('device', torch.device('meta')), ('primary', torch.device('meta')), ('last', True)]:
                saved = getattr(selected.original_route, field)
                setattr(selected.original_route, field, changed)
                try:
                    rejects(lambda: selected({}, {}), 'reject_mutated_route_' + field)
                finally:
                    setattr(selected.original_route, field, saved)
            handle = selected.block.register_forward_pre_hook(lambda m, a: None)
            try:
                rejects(lambda: selected({}, {}), 'reject_hook_added_after_installation')
            finally:
                handle.remove()
            handle = torch.nn.modules.module.register_module_forward_hook(lambda m, a, b: b)
            try:
                rejects(lambda: selected({}, {}), 'reject_global_module_hook')
            finally:
                handle.remove()
            selected.block.to(dtype=torch.float32)
            try:
                rejects(lambda: selected({}, {}), 'reject_non_bf16_after_installation')
            finally:
                selected.block.to(dtype=torch.bfloat16)
            selected.block.register_buffer('_unit_wrong_device', torch.ones(1, dtype=torch.bfloat16, device='meta'))
            try:
                rejects(lambda: selected._call_native({}), 'reject_block_state_wrong_device_before_compiler')
            finally:
                del selected.block._buffers['_unit_wrong_device']
            rejects(lambda: selected._call_native({'img': (torch.empty(1, device='meta'),)}),
                    'reject_routed_numerical_input_wrong_device')
            with torch.inference_mode():
                for warn_only in (False, True):
                    torch.use_deterministic_algorithms(warn_only, warn_only=warn_only)
                    try:
                        rejects(lambda: compiler_adapter.apply_block_compile(patcher),
                                'reject_nonstrict_determinism_warn_' + str(warn_only))
                    finally:
                        torch.use_deterministic_algorithms(True, warn_only=False)
            check(ownership(patcher) == before, 'guard_failures_leave_registered_ownership_unchanged')
            report['restoration_scope'] = 'dispatch-only; clone.parent can retain compiler state; no cache-memory release claimed'
'''


def main():
    base_text = BASE.read_text()
    base_receipt = __import__('json').loads((LANE / 'data/ltx-block-compile-route-cpu-01.json').read_text())
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != base_receipt['sha256s'][str(BASE)]:
        raise RuntimeError('Preserved base test changed')
    if hashlib.sha256(ADAPTER.read_bytes()).hexdigest() != base_receipt['sha256s'][str(ADAPTER)]:
        raise RuntimeError('Preserved base adapter changed')
    with tempfile.TemporaryDirectory(prefix='ltx-ownership-patch-') as staging:
        stage = Path(staging)
        (stage / 'scripts').mkdir()
        target = stage / 'scripts/ltx_block_compile.py'
        target.write_bytes(ADAPTER.read_bytes())
        subprocess.run(['git', 'apply', '--check', str(PATCH)], cwd=stage, check=True, timeout=30)
        subprocess.run(['git', 'apply', str(PATCH)], cwd=stage, check=True, timeout=30)
        candidate = target.read_text()

    def load_candidate_adapter():
        module = types.ModuleType('ltx_block_compile')
        module.__file__ = str(ADAPTER)
        sys.modules[module.__name__] = module
        exec(compile(candidate, str(PATCH) + ':applied', 'exec'), module.__dict__)
        return module

    edits = {
        '            import ltx_block_compile as compiler_adapter':
            '            compiler_adapter = load_candidate_adapter()',
        "            report['options'] = compiler_adapter.OPTIONS":
            "            report['options'] = compiler_adapter.OPTIONS\n            report.update(GUARD_IDENTITY)",
        "            report['phase'] = 'forward_cache_lifetime'":
            GUARD_TESTS + "\n            report['phase'] = 'forward_cache_lifetime'",
        "{('double_block', i): original_route for i in range(48)}":
            "{('double_block', i): (route if i == 0 else original_route) for i in range(48)}",
    }
    for old, new in edits.items():
        if base_text.count(old) != 1:
            raise RuntimeError('Base test injection point changed: ' + old)
        base_text = base_text.replace(old, new)
    namespace = {'__name__': 'ltx_guard_route_driver', '__file__': str(BASE),
        'load_candidate_adapter': load_candidate_adapter,
        'GUARD_IDENTITY': {'ownership_guard_patch_sha256': hashlib.sha256(PATCH.read_bytes()).hexdigest(),
            'guard_driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'effective_adapter_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
            'effective_test_sha256': hashlib.sha256(base_text.encode()).hexdigest(),
            'callback_registry_contains_compiler_route': True}}
    exec(compile(base_text, str(BASE) + ':guard-fixture', 'exec'), namespace)
    return namespace['main']()


if __name__ == '__main__':
    raise SystemExit(main())
