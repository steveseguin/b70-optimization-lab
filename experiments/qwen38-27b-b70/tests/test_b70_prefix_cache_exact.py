"""CPU check of b70_prefix_cache_exact against stand-ins shaped like the R314 engine classes. No vLLM, no GPU."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'exact', HERE / 'overlays/b70-prefix-cache-exact/b70_prefix_cache_exact.py')
exact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exact)

BLOCK = 832


def install(back='1'):
    """Stand-in modules: a coordinator base with two subclasses, one of which overrides cache_blocks, and a
    MambaManager whose reachable_block_mask is the R314 rule (segment ends plus the listed boundaries)."""
    calls = []

    class KVCacheCoordinator:
        def cache_blocks(self, request, num_computed_tokens):
            calls.append(('base', num_computed_tokens))

    class UnitaryKVCacheCoordinator(KVCacheCoordinator):
        pass

    class HybridKVCacheCoordinator(KVCacheCoordinator):
        def cache_blocks(self, request, num_computed_tokens):
            calls.append(('hybrid', num_computed_tokens))

    class MambaManager:
        @classmethod
        def reachable_block_mask(cls, start_block, end_block, alignment_tokens, kv_cache_spec, use_eagle,
                                 retention_interval=None, reachable_boundaries=()):
            if retention_interval is None or alignment_tokens is None:
                return None
            mask = [False] * (end_block - start_block)
            if retention_interval:
                per = retention_interval // BLOCK
                first = (start_block + per) // per * per - 1
                for i in range(first - start_block, len(mask), per):
                    mask[i] = True
            for boundary in reachable_boundaries:
                block = boundary // alignment_tokens * alignment_tokens // BLOCK - 1
                if start_block <= block < end_block:
                    mask[block - start_block] = True
            return mask

    coordinator = types.ModuleType('vllm.v1.core.kv_cache_coordinator')
    coordinator.KVCacheCoordinator = KVCacheCoordinator
    coordinator.UnitaryKVCacheCoordinator = UnitaryKVCacheCoordinator
    coordinator.HybridKVCacheCoordinator = HybridKVCacheCoordinator
    managers = types.ModuleType('vllm.v1.core.single_type_kv_cache_manager')
    managers.MambaManager = MambaManager
    logger = types.ModuleType('vllm.logger')
    logger.init_logger = lambda name: types.SimpleNamespace(warning=lambda *a, **k: None)
    core = types.ModuleType('vllm.v1.core')
    core.kv_cache_coordinator, core.single_type_kv_cache_manager = coordinator, managers
    for name, module in (('vllm', types.ModuleType('vllm')), ('vllm.v1', types.ModuleType('vllm.v1')),
                         ('vllm.v1.core', core), ('vllm.logger', logger),
                         ('vllm.v1.core.kv_cache_coordinator', coordinator),
                         ('vllm.v1.core.single_type_kv_cache_manager', managers)):
        sys.modules[name] = module
    os.environ['B70_PREFIX_CACHE_EXACT'] = '1'
    os.environ['B70_PREFIX_CACHE_EXACT_BACK'] = back
    exact.register()
    return coordinator, managers, calls


class PrefixCacheExact(unittest.TestCase):
    def tearDown(self):
        for name in [n for n in sys.modules if n == 'vllm' or n.startswith('vllm.')]:
            del sys.modules[name]
        os.environ.pop('B70_PREFIX_CACHE_EXACT', None)
        os.environ.pop('B70_PREFIX_CACHE_EXACT_BACK', None)

    def test_nothing_past_the_prompt_is_cached(self):
        coordinator, _, calls = install()
        request = types.SimpleNamespace(num_prompt_tokens=2000)
        for cls in (coordinator.UnitaryKVCacheCoordinator, coordinator.HybridKVCacheCoordinator):
            cls().cache_blocks(request, 1500)   # still reading the prompt: unchanged
            cls().cache_blocks(request, 2000)
            cls().cache_blocks(request, 2600)   # 600 tokens written: stops at the prompt
        self.assertEqual(calls, [('base', 1500), ('base', 2000), ('base', 2000),
                                 ('hybrid', 1500), ('hybrid', 2000), ('hybrid', 2000)])

    def test_state_kept_where_a_drafting_hit_lands(self):
        _, managers, _ = install()
        # a 8,400-token prompt: ten full blocks; the engine keeps the state of block 9 (ends at 8,320) only
        mask = managers.MambaManager.reachable_block_mask(0, 10, BLOCK, None, False, 0, [8399])
        self.assertEqual([i for i, keep in enumerate(mask) if keep], [8, 9])
        # with a periodic interval of four blocks as well
        mask = managers.MambaManager.reachable_block_mask(0, 10, BLOCK, None, False, 4 * BLOCK, [8399])
        self.assertEqual([i for i, keep in enumerate(mask) if keep], [3, 7, 8, 9])

    def test_dense_mode_and_short_prompts_unchanged(self):
        _, managers, _ = install()
        self.assertIsNone(managers.MambaManager.reachable_block_mask(0, 10, BLOCK, None, False, None, [8399]))
        mask = managers.MambaManager.reachable_block_mask(0, 1, BLOCK, None, False, 0, [900])
        self.assertEqual(mask, [True])          # one full block: nothing earlier to keep

    def test_back_zero_is_the_stock_rule(self):
        _, managers, _ = install(back='0')
        mask = managers.MambaManager.reachable_block_mask(0, 10, BLOCK, None, False, 0, [8399])
        self.assertEqual([i for i, keep in enumerate(mask) if keep], [9])

    def test_helpers(self):
        self.assertEqual(exact.cap_tokens(2600, 2000), 2000)
        self.assertEqual(exact.with_back_boundaries([8399], BLOCK, 1), [8399, 7488])
        self.assertEqual(exact.with_back_boundaries([8399, 4160], BLOCK, 1), [8399, 4160, 7488, 3328])
        self.assertEqual(exact.with_back_boundaries([900], BLOCK, 1), [900])
        self.assertEqual(exact.with_back_boundaries([8399], None, 1), [8399])


if __name__ == '__main__':
    unittest.main()
