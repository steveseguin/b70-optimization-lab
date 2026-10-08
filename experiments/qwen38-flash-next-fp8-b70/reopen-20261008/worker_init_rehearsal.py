"""CPU-only construction rehearsal for the V30 overlay; no installed files changed."""
import argparse
import contextlib
import importlib
import importlib.abc
import importlib.util
import json
import hashlib
import tempfile
import os
from pathlib import Path
import sys
import types

HERE = Path(__file__).resolve().parent
SOURCE = Path('/home/steve/src/lumnus-20261008/vllm')
DEPENDENCIES = Path('/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages')


def package(name, paths):
    module = types.ModuleType(name)
    module.__path__ = [str(p) for p in paths]
    module.__package__ = name
    sys.modules[name] = module
    return module


class OverlayFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith('vllm.'):
            return None
        relative = Path(*fullname.split('.'))
        for base in (HERE / 'overlay', SOURCE):
            init = base / relative / '__init__.py'
            if init.is_file():
                return importlib.util.spec_from_file_location(fullname, init, submodule_search_locations=[
                    str(HERE / 'overlay' / relative), str(SOURCE / relative)])
            file = base / relative.with_suffix('.py')
            if file.is_file():
                return importlib.util.spec_from_file_location(fullname, file)
        return None


def cpu_transport(torch, rank):
    """Emulate device allocation/transport with real CPU tensor storage only.

    Logical device labels let production placement and staging branches execute.
    Every dispatched ATen operation is unwrapped onto CPU; no fake/meta math.
    """
    from torch.utils._python_dispatch import TorchDispatchMode
    from torch.overrides import TorchFunctionMode
    from torch.utils._pytree import tree_map, tree_flatten
    pinned = set()

    class DeviceTensor(torch.Tensor):
        @staticmethod
        def __new__(cls, elem):
            out = torch.Tensor._make_wrapper_subclass(
                cls, elem.shape, strides=elem.stride(), storage_offset=elem.storage_offset(),
                dtype=elem.dtype, layout=elem.layout, device='cpu', requires_grad=False)
            out.elem = elem
            return out

        @property
        def device(self):
            return torch.device(f'xpu:{rank}')

        def data_ptr(self):
            return self.elem.data_ptr()

        def untyped_storage(self):
            return self.elem.untyped_storage()

        def tolist(self):
            return self.elem.tolist()

        @classmethod
        def __torch_dispatch__(cls, func, types, args=(), kwargs=None):
            return dispatch(func, args, kwargs or {})

    def dispatch(func, args, kwargs):
        leaves = tree_flatten((args, kwargs))[0]
        wrapped = any(isinstance(x, DeviceTensor) for x in leaves)
        target = kwargs.get('device')
        logical = (torch.device(target).type == 'xpu' if target is not None else wrapped)
        kw = dict(kwargs)
        pin = kw.pop('pin_memory', False)
        if target is not None:
            assert torch.device(target).type in ('cpu', 'meta', 'xpu')
            if torch.device(target).type == 'xpu':
                kw['device'] = torch.device('cpu')
        unwrap = lambda x: x.elem if isinstance(x, DeviceTensor) else x
        result = func(*tree_map(unwrap, args), **tree_map(unwrap, kw))
        def wrap(x):
            if not isinstance(x, torch.Tensor):
                return x
            assert x.device.type in ('cpu', 'meta')
            if pin:
                pinned.add(x.untyped_storage().data_ptr())
            if logical and x.device.type != 'meta':
                return DeviceTensor(x)
            return x
        return tree_map(wrap, result)

    class Transport(TorchDispatchMode):
        def __torch_dispatch__(self, func, types, args=(), kwargs=None):
            return dispatch(func, args, kwargs or {})

    class Factories(TorchFunctionMode):
        def __torch_function__(self, func, types, args=(), kwargs=None):
            kw = dict(kwargs or {})
            if isinstance(func, torch._ops.OpOverload):
                return func(*args, **kw)
            if func is torch.Tensor.to and len(args) > 1 and isinstance(args[1], (str, torch.device)):
                kw['device'] = args[1]
                args = (args[0], *args[2:])
            target = kw.get('device')
            logical = target is not None and torch.device(target).type == 'xpu'
            if logical and func is torch.Tensor.to:
                if len(args) > 1:
                    kw['dtype'] = args[1]
                return torch.ops.aten._to_copy.default(args[0], **kw)
            if logical:
                kw['device'] = torch.device('cpu')
            pin = kw.pop('pin_memory', False)
            result = func(*args, **kw)
            def wrap(x):
                if isinstance(x, torch.Tensor):
                    if (logical or pin) and not isinstance(x, DeviceTensor) and x.numel() and x.is_contiguous():
                        # CPU malloc need only align to 64 bytes; UVA offsets
                        # require the device allocator's 256-byte alignment.
                        slab = torch.empty(x.numel() + 256, dtype=x.dtype, device='cpu')
                        offset = (-slab.data_ptr() % 256) // x.element_size()
                        aligned = slab[offset:offset+x.numel()].view(x.shape)
                        aligned.copy_(x)
                        x = aligned
                    if pin:
                        pinned.add(x.untyped_storage().data_ptr())
                    if logical and not isinstance(x, DeviceTensor):
                        return DeviceTensor(x)
                return x
            return tree_map(wrap, result)

    @contextlib.contextmanager
    def transport():
        with Transport(), Factories():
            yield
    return transport, DeviceTensor, pinned


def bootstrap(rank=0, guard_source=None):
    # Read-only fallback for already installed Python dependencies. No .pth
    # execution: in particular, do not activate the old editable vLLM runtime.
    sys.path.append(str(DEPENDENCIES))
    import torch
    torch.set_num_threads(1)
    import torch._dynamo
    def forbidden(*a, **kw):
        raise AssertionError('rehearsal attempted an accelerator operation')
    for api in (torch.xpu, torch.cuda):
        for name in ('_lazy_init', 'init', 'is_available', 'device_count',
                     'current_device', 'synchronize', 'get_device_properties', 'set_device'):
            if hasattr(api, name):
                setattr(api, name, forbidden)
        api.is_available = lambda: False
        api.device_count = lambda: 0
    package('vllm', [HERE / 'overlay/vllm', SOURCE / 'vllm'])
    sys.meta_path.insert(0, OverlayFinder())
    if guard_source is not None:
        spec = importlib.util.spec_from_file_location('vllm.screen1b_guard', guard_source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    platforms = package('vllm.platforms', [SOURCE / 'vllm/platforms'])
    from vllm.platforms.interface import Platform, PlatformEnum, CpuArchEnum
    class RehearsalPlatform(Platform):
        _enum = PlatformEnum.XPU
        device_type = 'xpu'
        device_name = 'xpu'
        dispatch_key = 'XPU'
        dist_backend = 'xccl'
        @classmethod
        def get_device_capability(cls, device_id=0):
            return None
        @classmethod
        def current_device(cls):
            return torch.device(f'xpu:{rank}')
        @classmethod
        def get_vit_attn_backend(cls, *args, **kwargs):
            from vllm.v1.attention.backends.registry import AttentionBackendEnum
            return AttentionBackendEnum.FLASH_ATTN
        @classmethod
        def supports_fp8(cls):
            return True
        @classmethod
        def is_pin_memory_available(cls):
            return True
    platforms.current_platform = RehearsalPlatform()
    platforms.Platform = Platform
    platforms.PlatformEnum = PlatformEnum
    platforms.CpuArchEnum = CpuArchEnum
    kernels = types.ModuleType('vllm._xpu_ops')
    class KernelBoundary:
        def __getattr__(self, name):
            return forbidden
    kernels.xpu_ops = KernelBoundary()
    sys.modules[kernels.__name__] = kernels
    from vllm.models.qwen4_exp import Qwen4ExpForConditionalGeneration
    for ns in ('_C', '_xpu_C', '_moe_C', '_C_cache_ops'):
        setattr(torch.ops, ns, KernelBoundary())
    from vllm.config import set_current_vllm_config, VllmConfig, ModelConfig, ParallelConfig, CompilationConfig, CacheConfig
    from vllm.model_executor.models import ModelRegistry
    ModelRegistry.register_model('Qwen4ExpForConditionalGeneration', Qwen4ExpForConditionalGeneration)
    mc = ModelConfig(model='/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8',
                     dtype='bfloat16', max_model_len=4352, enforce_eager=True,
                     language_model_only=False)
    vc = VllmConfig(model_config=mc, parallel_config=ParallelConfig(tensor_parallel_size=4, enable_expert_parallel=True),
                    compilation_config=CompilationConfig(mode=0),
                    cache_config=CacheConfig(cache_dtype='bfloat16', mamba_cache_mode='align'))
    vc.kernel_config.moe_backend = 'triton'
    from vllm.distributed import parallel_state as ps
    group = types.SimpleNamespace(rank_in_group=rank, world_size=4, is_first_rank=True,
                                  is_last_rank=True, ranks=list(range(4)), device_group=types.SimpleNamespace(size=lambda: 4, rank=lambda: rank))
    ps._TP = ps._EP = ps._ETP = group
    ps._PP = ps._DP = ps._PCP = ps._DCP = types.SimpleNamespace(
        rank_in_group=0, world_size=1, is_first_rank=True, is_last_rank=True)
    vision = mc.hf_config.vision_config
    for k, v in dict(depth=1, hidden_size=128, intermediate_size=256, num_heads=4,
                     num_position_embeddings=16, out_hidden_size=128).items():
        setattr(vision, k, v)
    tc = mc.hf_text_config
    for k, v in dict(hidden_size=128, hc_lowrank=16, vocab_size=256,
                     num_hidden_layers=4, layer_types=tc.layer_types[:4],
                     moe_intermediate_size=128, shared_expert_intermediate_size=128,
                     num_attention_heads=4, num_key_value_heads=2,
                     linear_num_key_heads=4, linear_num_value_heads=4,
                     ngram_vocab_size_base=128, split_ngram_parts=4,
                     max_position_embeddings=8192).items():
        setattr(tc, k, v)
    vc.scheduler_config.max_num_batched_tokens = 32
    from vllm.model_executor.model_loader.default_loader import DefaultModelLoader
    from vllm.utils.torch_utils import set_default_torch_dtype
    import tempfile
    from unittest.mock import patch
    from vllm import screen1b_guard as guard, screen1b_ple as ple
    from vllm.model_executor.offloader import set_offloader, UVAOffloader
    import vllm.utils.torch_utils as tu
    import vllm.model_executor.offloader.uva as uva_module
    Transport, DeviceTensor, pinned = cpu_transport(torch, rank)
    with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
        root = Path(temp)
        placement = {str(r): {str(i): [0, 2, 127] for i in range(4)} for r in range(4)}
        (root / 'placement.json').write_text(json.dumps(placement))
        stack.enter_context(patch.dict(os.environ, {
            'B70_SCREEN1B': '1', 'B70_SCREEN1B_STATE_DIR': temp,
            'Q38_EXPERT_HOST_PLACEMENT': str(root / 'placement.json')}))
        stack.enter_context(patch.object(guard, 'synchronize', lambda: None))
        stack.enter_context(patch.object(guard, 'COPY_LIMIT', 1 << 20))
        stack.enter_context(patch.object(torch.xpu, 'device', lambda d: contextlib.nullcontext()))
        stack.enter_context(patch.object(torch.Tensor, 'is_pinned', lambda x: x.untyped_storage().data_ptr() in pinned))
        stack.enter_context(patch.object(tu, 'get_accelerator_view_from_cpu_tensor', DeviceTensor))
        stack.enter_context(patch.object(uva_module, 'get_accelerator_view_from_cpu_tensor', DeviceTensor))
        stack.enter_context(patch.object(uva_module, 'is_uva_available', lambda: True))
        from vllm.models.qwen4_exp.nvidia.ngram_embedding import Qwen4ExpNGramEmbedding
        _, _, total_rows = Qwen4ExpNGramEmbedding._make_vocab_layout(
            ngram_vocab_size_base=128, ngram_heads=16, ple_dense_layer_id=0)
        total_rows = (total_rows + 127) // 128 * 128
        contract = dict(schema='screen1b.cpu-rehearsal-contract.v1', fixture_only=True,
                        ple_rows=total_rows, ple_row_bytes=160, ple_cache_bytes_per_rank=5120,
                        max_total_tokens=32, ngram_heads=16)
        (root / 'contract.json').write_text(json.dumps(contract))
        original_open = Path.open
        def local_contract(path, *args, **kwargs):
            if str(path) == '/screen-package/memory-contract.json':
                path = root / 'contract.json'
            return original_open(path, *args, **kwargs)
        stack.enter_context(patch.object(Path, 'open', local_contract))
        stack.enter_context(patch.object(ple, 'CACHE_PER_RANK', 5120))
        set_offloader(UVAOffloader(1 << 30, {'embed_tokens', 'ple_embedding'}))
        from safetensors.torch import save_file
        checkpoint = root / 'checkpoint'
        checkpoint.mkdir()
        prefix = 'model.language_model.layers.1.ple.ple_embedding.ngram_embedding'
        weights = {}
        raw_rows = torch.arange(total_rows * 160, dtype=torch.int64, device='cpu').to(torch.uint8).reshape(total_rows, 160)
        for i in range(4):
            weights[f'{prefix}.shard_{i}.weight'] = raw_rows.chunk(4)[i].view(torch.float8_e4m3fn).contiguous()
        weights[f'{prefix}.weight_scale'] = torch.tensor([0.5], dtype=torch.float32, device='cpu')
        weights['model.language_model.embed_tokens.weight'] = torch.ones((256,128), dtype=torch.bfloat16, device='cpu')
        for expert in (rank*128, rank*128+1, rank*128+127):
            for projection in ('gate_proj', 'up_proj', 'down_proj'):
                name = f'model.language_model.layers.0.mlp.experts.{expert}.{projection}.weight'
                weights[name] = torch.full((128,128), 1.0, dtype=torch.float32, device='cpu').to(torch.float8_e4m3fn)
        save_file(weights, str(checkpoint / 'model.safetensors'))
        (checkpoint / 'model.safetensors.index.json').write_text(json.dumps({
            'weight_map': {name: 'model.safetensors' for name in weights}}))
        mc.model = str(checkpoint)
        vc.load_config.safetensors_load_strategy = 'lazy'
        vc.device_config.device = torch.device(f'xpu:{rank}')
        stack.enter_context(patch.object(torch.accelerator, 'max_memory_allocated', lambda: 0))
        def construct():
            return DefaultModelLoader(vc.load_config).load_model(vc, mc)
        with set_current_vllm_config(vc), set_default_torch_dtype(torch.bfloat16), Transport(), torch.device(f'xpu:{rank}'):
            model = construct()
            from vllm import q38_expert_placement as placement_module
            layers = model.language_model.model.layers
            assert len(layers) == 4 and layers[1].ple is not None
            assert layers[3].self_attn.rotary_emb.cos_sin_cache.dtype == torch.bfloat16
            expert_weights = [p for p in model.parameters() if hasattr(p, '_q38_row_map')]
            assert len(expert_weights) == 8
            for p in expert_weights:
                assert p.shape[0] == 125 and p._q38_host_cpu.shape[0] == 3
            for name in ('w13_weight', 'w2_weight'):
                p = getattr(layers[0].mlp.experts.routed_experts, name)
                for logical_row in (0, 1, 127):
                    row = placement_module.row_view(p, logical_row)
                    actual = row.elem if isinstance(row, DeviceTensor) else row
                    assert torch.equal(actual.float(), torch.ones_like(actual, dtype=torch.float32))
            owner = layers[1].ple.ple_embedding
            embedding = owner.ngram_embedding
            assert embedding.weight.numel() == 0
            inputs = dict(input_ids=torch.tensor([1, 2, 3, 4], device=f'xpu:{rank}'),
                          query_start_loc=torch.tensor([0, 4], device=f'xpu:{rank}'),
                          ngram_context=torch.tensor([[248044,248044]], device=f'xpu:{rank}'))
            ple.pre_forward(inputs)
            ids = owner.compute_ngram_ids(**inputs)
            actual = ple.gather_prepared(embedding, ids).elem.view(torch.uint8)
            expected = torch.zeros_like(actual, device='cpu')
            store = embedding._screen1b_cache.store
            for i, row_id in enumerate(ids.elem.flatten().tolist()):
                if store.start <= row_id < store.end:
                    expected.view(-1,160)[i].copy_(raw_rows[row_id])
            assert torch.equal(actual, expected)
            # A second pre-forward must overwrite changed IDs, not reuse a step.
            inputs['input_ids'].fill_(5)
            ple.pre_forward(inputs)
            changed_ids = owner.compute_ngram_ids(**inputs)
            changed = ple.gather_prepared(embedding, changed_ids).elem.view(torch.uint8)
            expected.zero_()
            for i, row_id in enumerate(changed_ids.elem.flatten().tolist()):
                if store.start <= row_id < store.end:
                    expected.view(-1,160)[i].copy_(raw_rows[row_id])
            assert torch.equal(changed, expected)
            owner.validate_checkpoint_shard_coverage()
            guard.allocation_snapshot(model, phase='rehearsal_complete')
        import gc
        gc.collect()
        ledger = json.loads((root / 'staging-live.json').read_text())
        assert not ledger['live'] and ledger['peak_bytes'] <= 1 << 20
        assert not (root / 'STOP').exists()
        allocation = json.loads((root / f'allocations-rank{rank}.json').read_text())
        assert allocation['groups']['experts']['pinned_bytes'] > 0
        assert allocation['groups']['PLE_cache']['pinned_bytes'] >= 5120
        events = [json.loads(line) for line in (root / f'loader-{os.getpid()}.jsonl').read_text().splitlines()]
        event_names = {e['event'] for e in events}
        assert {'load_begin', 'load_drained', 'v5_allocated', 'PLE_mmap_bound',
                'PLE_index_complete', 'PLE_coverage_complete', 'allocation_snapshot'} <= event_names
        imported = {}
        for name, module in list(sys.modules.items()):
            file = getattr(module, '__file__', None)
            if name.startswith('vllm.') and file and Path(file).is_file():
                imported[str(file)] = hashlib.sha256(Path(file).read_bytes()).hexdigest()
        receipt = dict(schema='screen1b.cpu-worker-init-rehearsal.v1', passed=True, rank=rank,
                       torch=torch.__version__, source=str(SOURCE),
                       config_sha256=hashlib.sha256(Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/config.json').read_bytes()).hexdigest(),
                       imported_source_sha256=imported,
                       allocation=allocation, staging=ledger,
                       text_geometry={k: getattr(tc,k) for k in (
                           'hidden_size', 'hc_lowrank', 'vocab_size', 'num_hidden_layers',
                           'num_experts', 'moe_intermediate_size', 'max_position_embeddings',
                           'ple_embed_dim', 'ngram_vocab_size_base', 'split_ngram_parts')},
                       vision_depth=vision.depth,
                       rope_cache_shape=list(layers[3].self_attn.rotary_emb.cos_sin_cache.shape),
                       v5_parameters=len(expert_weights), fixture_checkpoint_weights=len(weights),
                       event_counts={name: sum(e['event']==name for e in events) for name in sorted(event_names)},
                       devices='CPU storage only; logical XPU labels are emulated',
                       limits=['tiny dimensions and partial synthetic checkpoint', 'no MTP draft construction',
                               'no native kernels, CCL, graph replay, worker multiprocessing, full-size memory or output parity'])
        embedding._screen1b_cache.close()
        return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rank', type=int, choices=range(4), default=0)
    parser.add_argument('--guard-source', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='screen1b-cpu-imports-') as cache:
        for name in ('HF_HOME', 'TRITON_CACHE_DIR', 'VLLM_CACHE_ROOT', 'XDG_CACHE_HOME'):
            os.environ[name] = cache
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                          HF_DATASETS_OFFLINE='1', VLLM_LOGGING_LEVEL='ERROR')
        result = bootstrap(args.rank, args.guard_source)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('passed', 'rank', 'v5_parameters', 'staging')}))
