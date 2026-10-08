"""CPU-only application/guard/module-import tests; never import real torch."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply_overlay


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = load_file('screen1b_guard_cpu_test', HERE / 'overlay/vllm/screen1b_guard.py')


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = apply_overlay.verify_package(HERE)
        cls.base = {}
        for rel, pin in cls.manifest['replacements'].items():
            if pin['base_sha256'] is not None:
                out = subprocess.run(['git', 'show', cls.manifest['upstream'] + ':' + rel],
                                     cwd=cls.manifest['source_tree'], capture_output=True, check=True)
                cls.base[rel] = out.stdout

    def base_tree(self, root):
        for rel, payload in self.base.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)

    def test_apply_full_v30_tree_hashes_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base_tree(root)
            first = apply_overlay.apply_overlay(root)
            self.assertGreater(first['changed'], 30)
            for rel, digest in self.manifest['files'].items():
                self.assertEqual(apply_overlay.digest(root / rel), digest)
            self.assertEqual(apply_overlay.apply_overlay(root)['changed'], 0)

    def test_base_drift_refuses_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base_tree(root)
            rel = next(reversed(self.base))
            (root / rel).write_text('unexpected upstream drift')
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*.py')}
            with self.assertRaisesRegex(RuntimeError, 'base drift'):
                apply_overlay.apply_overlay(root)
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*.py')})

    def test_output_drift_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.base_tree(root)
            apply_overlay.apply_overlay(root)
            (root / 'vllm/screen1b_guard.py').write_text('drift')
            with self.assertRaisesRegex(RuntimeError, 'base drift'):
                apply_overlay.apply_overlay(root)

    def test_path_escape_refuses(self):
        for value in ('../escape', '/absolute', 'a/../../escape'):
            with self.assertRaises(RuntimeError):
                apply_overlay.safe_relative(value)

    def test_symlink_destination_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'tree'
            root.mkdir()
            self.base_tree(root)
            p = root / next(iter(self.base))
            p.unlink()
            p.symlink_to(Path(temp) / 'escape')
            with self.assertRaisesRegex(RuntimeError, 'unsafe overlay destination'):
                apply_overlay.apply_overlay(root)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'B70_SCREEN1B': '1', 'B70_SCREEN1B_STATE_DIR': self.tmp.name})
        self.env.start()
        guard._cancelled = False
        guard._loading = False
        guard._tables.clear()
        guard._signalled_pids.clear()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_import_is_stdlib_only(self):
        # It has no top-level torch import/device discovery.
        with patch.dict(sys.modules, {'torch': None}):
            fresh = load_file('screen1b_guard_import_smoke', HERE / 'overlay/vllm/screen1b_guard.py')
            self.assertEqual(fresh.COPY_LIMIT, 256 * 2**20)

    def test_next_allocation_pressure_and_available_boundaries(self):
        total = 128 * 2**30
        with patch.object(guard, 'memory', return_value={'MemTotal': total, 'MemAvailable': total - 79_000_000_000}):
            guard.check_admission(999_999_999)
            with self.assertRaises(guard.LoadCancelled):
                guard.check_admission(1_000_000_000)
        self.assertTrue((Path(self.tmp.name) / 'STOP').exists())

    def test_available_boundary_independent_of_pressure(self):
        with patch.object(guard, 'memory', return_value={'MemTotal': 64 * 2**30, 'MemAvailable': 33 * 2**30}):
            with self.assertRaises(guard.LoadCancelled):
                guard.check_admission(2**30)

    def test_stop_latch_refuses_new_admission(self):
        guard.request_stop('test')
        with self.assertRaises(guard.LoadCancelled):
            with guard.admission('test'):
                self.fail('admitted after STOP')

    def test_receipt_failure_does_not_abort_shutdown(self):
        with patch.object(Path, 'open', side_effect=OSError('full')):
            guard.wait_processes([])
        self.assertTrue(guard._cancelled)

    def test_signal_exit_race_does_not_skip_other_child_drain(self):
        class Proc:
            pid = 42
            def is_alive(self):
                return self.live
            def join(self, timeout):
                self.live = False
        p = Proc(); p.live = True
        with patch.object(guard.os, 'kill', side_effect=ProcessLookupError(3, 'gone')):
            guard.wait_processes([p], signal_once=True)
        self.assertFalse(p.live)

    def test_filter_and_global_index_cover_all_shards(self):
        class Module:
            split_ngram_parts = 4
            def screen1b_expected_shards(self):
                return {1, 2}
        guard.register_ple('model.layers.1.ple_embedding', Module())
        names = [f'model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_{i}.weight' for i in range(4)]
        self.assertEqual([guard.filter_ple_weight(n) for n in names], [True, False, False, True])
        index = Path(self.tmp.name) / 'model.safetensors.index.json'
        index.write_text(json.dumps({'weight_map': {n: 'test.safetensors' for n in names}}))
        guard.validate_ple_index(self.tmp.name)
        index.write_text(json.dumps({'weight_map': {n: 'test.safetensors' for n in names[:-1]}}))
        with self.assertRaisesRegex(RuntimeError, 'global PLE index coverage mismatch'):
            guard.validate_ple_index(self.tmp.name)

    def test_filter_rejects_unexpected_shard(self):
        module = types.SimpleNamespace(split_ngram_parts=4, screen1b_expected_shards=lambda: {0})
        guard.register_ple('model.layers.1.ple_embedding', module)
        with self.assertRaisesRegex(RuntimeError, 'unexpected PLE shard'):
            guard.filter_ple_weight('model.layers.1.ple.ngram_embedding.shard_4.weight')


class Tensor:
    """Shape-only CPU test tensor; copy receipts expose bounds, never bytes/GPU."""
    copies = []
    def __init__(self, shape, element=1, device='cpu'):
        self.shape = tuple(shape); self.ndim = len(shape); self.element = element
        self.device = types.SimpleNamespace(type=device)
        self.dtype = 'fp8'
        self.data = self
    def is_pinned(self):
        return True
    def numel(self):
        import math
        return math.prod(self.shape)
    def element_size(self):
        return self.element
    def __getitem__(self, key):
        if isinstance(key, int):
            return Tensor(self.shape[1:], self.element)
        start, stop, step = key.indices(self.shape[0])
        return Tensor((len(range(start, stop, step)), *self.shape[1:]), self.element)
    def narrow(self, axis, start, count):
        assert axis == 0
        return Tensor((count, *self.shape[1:]), self.element)
    def copy_(self, source, **kwargs):
        self.copies.append((self.shape, source.shape, self.numel() * (self.element + source.element), kwargs))
        return self
    def expand_as(self, other):
        return Tensor(other.shape, self.element)


class ModuleImportSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'B70_SCREEN1B': '1', 'B70_SCREEN1B_STATE_DIR': self.tmp.name})
        self.env.start()
        Tensor.copies.clear()
        guard._cancelled = False
        guard._loading = False
        torch = types.ModuleType('torch')
        torch.Tensor = Tensor
        torch.no_grad = contextlib.nullcontext
        torch.nn = types.ModuleType('torch.nn')
        torch.nn.Module = type('Module', (), {})
        torch.nn.Parameter = Tensor
        torch.device = lambda name: types.SimpleNamespace(type=name)
        torch.empty_like = lambda tensor, **kw: Tensor(tensor.shape, tensor.element)
        torch.accelerator = types.SimpleNamespace(synchronize=lambda: None)
        func = types.ModuleType('torch.func'); func.functional_call = lambda *a, **k: None
        vllm = types.ModuleType('vllm');vllm.screen1b_guard = guard
        logger = types.ModuleType('vllm.logger');logger.init_logger = lambda name: types.SimpleNamespace(info=lambda *a:None)
        envs = types.ModuleType('vllm.envs');envs.VLLM_WEIGHT_OFFLOADING_DISABLE_UVA = False
        base = types.ModuleType('vllm.model_executor.offloader.base')
        base.BaseOffloader = type('BaseOffloader', (), {});base.should_pin_memory=lambda:True
        vocab = types.ModuleType('vllm.model_executor.layers.vocab_parallel_embedding')
        vocab.VocabParallelEmbedding = type('VocabParallelEmbedding', (), {})
        self.modules = {'torch':torch,'torch.nn':torch.nn,'torch.func':func,'vllm':vllm,'vllm.envs':envs,
                        'vllm.logger':logger,'vllm.model_executor.offloader.base':base,
                        'vllm.model_executor.layers.vocab_parallel_embedding':vocab}
        for name, attrs in {
            'vllm.utils.gpu_sync_debug':{'gpu_sync_allowed':contextlib.nullcontext},
            'vllm.utils.mem_utils':{'format_gib':str},
            'vllm.utils.platform_utils':{'is_uva_available':lambda:True},
            'vllm.utils.torch_utils':{'get_accelerator_view_from_cpu_tensor':lambda p:p},
        }.items():
            module=types.ModuleType(name);module.__dict__.update(attrs);self.modules[name]=module
        self.stubs = patch.dict(sys.modules, self.modules);self.stubs.start()
        self.memory = patch.object(guard, 'memory', return_value={'MemTotal':128*2**30,'MemAvailable':110*2**30})
        self.memory.start()

    def tearDown(self):
        self.memory.stop();self.stubs.stop();self.env.stop();self.tmp.cleanup()

    def import_ngram(self):
        import ast
        name = 'vllm.models.qwen4_exp.nvidia.ngram_embedding'
        path = HERE / 'overlay/vllm/models/qwen4_exp/nvidia/ngram_embedding.py'
        extra = {}
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.ImportFrom) or not (node.module or '').startswith('vllm.'):
                continue
            if node.module in sys.modules:
                continue
            module = types.ModuleType(node.module)
            for alias in node.names:
                setattr(module, alias.name, type(alias.name, (), {}))
            extra[node.module] = module
        # Supply import interfaces only. No tensor operation or device call is
        # performed while importing the actual complete ngram module.
        extra['vllm.compilation.breakable_cudagraph'].eager_break_during_capture = lambda fn: fn
        extra['vllm.triton_utils'].triton = types.SimpleNamespace(jit=lambda fn: fn)
        extra['vllm.triton_utils'].tl = types.SimpleNamespace(constexpr=object)
        ple = types.ModuleType('vllm.models.qwen4_exp.nvidia.ops.ple')
        ple.ple_ngram_ids = lambda *a, **k: None
        extra[ple.__name__] = ple
        functional = types.ModuleType('torch.nn.functional')
        extra[functional.__name__] = functional
        self.modules['torch'].nn.functional = functional
        self.modules['torch'].dtype = type('dtype', (), {})
        for dtype in ('float8_e4m3fn','bfloat16','float16','float32','float64',
                      'int64','int32','int16','int8','uint8','bool'):
            setattr(self.modules['torch'], dtype, dtype)
        # Parent package stubs make relative imports resolve without touching
        # vLLM's eager model registry or a real runtime installation.
        for full in list(extra) + [name, 'vllm.models.qwen4_exp.common.ple']:
            parts = full.split('.')
            for count in range(2, len(parts)):
                parent = '.'.join(parts[:count])
                if parent not in extra and parent not in sys.modules:
                    package = types.ModuleType(parent);package.__path__=[]
                    extra[parent]=package
        with patch.dict(sys.modules, extra):
            common = load_file('vllm.models.qwen4_exp.common.ple', HERE / 'overlay/vllm/models/qwen4_exp/common/ple.py')
            return load_file(name, path)

    def test_full_ngram_module_import_and_fragmented_owned_coverage(self):
        ngram = self.import_ngram()
        module = ngram.Qwen4ExpNGramEmbedding.__new__(ngram.Qwen4ExpNGramEmbedding)
        module.split_ngram_parts = 4
        module.ngram_embedding = types.SimpleNamespace(
            org_vocab_size=16, embedding_dim=2,
            shard_indices=types.SimpleNamespace(org_vocab_start_index=4, org_vocab_end_index=12))
        module.begin_checkpoint_shard_coverage()
        self.assertEqual(module.screen1b_expected_shards(), {1, 2})
        with self.assertRaisesRegex(RuntimeError, 'missing='):
            module.validate_checkpoint_shard_coverage()
        module.layer_multipliers = Tensor((1,))
        module.ngram_heads_offsets = Tensor((1,))
        module.ngram_heads_vocab_sizes = Tensor((1,))
        table = Tensor((8, 2))
        copied = []
        table.weight_loader = lambda destination, source, **kw: copied.append((source.shape, kw['checkpoint_start']))
        module.ngram_embedding.weight = table
        module.load_weights([('ngram_embedding.shard_1.weight', Tensor((4, 2)))])
        with self.assertRaisesRegex(RuntimeError, 'missing='):
            module.validate_checkpoint_shard_coverage()
        module.load_weights([('ngram_embedding.shard_2.weight', Tensor((4, 2)))])
        module.validate_checkpoint_shard_coverage()
        self.assertEqual(copied, [((4, 2), 4), ((4, 2), 8)])
        with self.assertRaisesRegex(ValueError, 'Duplicate PLE'):
            module.load_weights([('ngram_embedding.shard_2.weight', Tensor((4, 2)))])
        module.begin_checkpoint_shard_coverage()
        other_dtype = Tensor((4, 2));other_dtype.dtype = 'bf16'
        with self.assertRaisesRegex(RuntimeError, 'no requantization'):
            module.load_weights([('ngram_embedding.shard_1.weight', other_dtype)])

    def test_common_ple_module_import_and_overlap_copy(self):
        common = load_file('screen1b_common_smoke', HERE / 'overlay/vllm/models/qwen4_exp/common/ple.py')
        rows=common.copy_ple_embedding_shard_(Tensor((4,2)),Tensor((4,2)),checkpoint_start=0,tp_start=2,tp_end=6)
        self.assertEqual(rows, 2)
        self.assertEqual(Tensor.copies[0][:2],((2,2),(2,2)))

    def test_uva_module_import_no_discard_for_ordinary_weights(self):
        uva = load_file('screen1b_uva_smoke', HERE / 'overlay/vllm/model_executor/offloader/uva.py')
        offloader=uva.UVAOffloader(1024, {'ple_embedding.ngram_embedding.weight'})
        ordinary=Tensor((8,4));offloader._make_cpu_data(ordinary)
        self.assertEqual(len(Tensor.copies),1)
        ordinary._vllm_offload_discard_initial_data=True
        offloader._make_cpu_data(ordinary)
        self.assertEqual(len(Tensor.copies),1)

    def test_bounded_copy_serializes_chunks_no_conversion(self):
        # Huge shape-only tensor verifies chunk arithmetic without allocating it.
        guard.bounded_copy(Tensor((400_000_000, 1)), Tensor((400_000_000, 1)))
        self.assertGreater(len(Tensor.copies), 1)
        self.assertTrue(all(c[2] <= guard.COPY_LIMIT for c in Tensor.copies))
        self.assertEqual(sum(c[0][0] for c in Tensor.copies),400_000_000)
        self.assertTrue(all(c[3]['non_blocking'] is False for c in Tensor.copies))

    def test_broadcast_scale_copy_preserves_torch_contract(self):
        guard.bounded_copy(Tensor((4,)),Tensor(()))
        self.assertEqual(Tensor.copies[0][:2],((4,),(4,)))


if __name__ == '__main__':
    unittest.main()
