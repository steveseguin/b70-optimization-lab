"""Lossless host placement of the input embedding for one-B70 official FP8 (research overlay).

Enabled only with B70_CPU_EMBED=1. After weights load, each input embedding
table (not lm_head) moves to host memory; lookups gather exactly the same rows
on the CPU and copy them to the XPU, so every value is unchanged. For
Qwen3.8-27B that frees about 2.37 GiB of GPU memory. The lookup is a registered
custom op, so torch.compile treats it as opaque. Plugins load once per process.

One card only: the replacement lookup has no vocabulary-shard masking, so it
refuses tensor parallelism, LoRA and XPU graph capture (a captured graph would
replay a stale host lookup). Tables are held weakly: the MTP draft loads its own
copy, which vLLM then replaces with the target's shared table, and that dead
copy must not stay alive in host memory (2.37 GiB).
"""
import os
import types
import weakref

_WEIGHTS = weakref.WeakValueDictionary()


def register():
    if os.environ.get('B70_CPU_EMBED') != '1':
        return
    import torch
    from vllm.logger import init_logger
    from vllm.model_executor.layers import vocab_parallel_embedding as vpe
    from vllm.model_executor.model_loader import base_loader
    from vllm.model_executor.model_loader import utils as loader_utils
    from vllm.utils.torch_utils import direct_register_custom_op

    logger = init_logger('b70_cpu_embed')
    if getattr(loader_utils, '_b70_cpu_embed', False):
        return
    if os.environ.get('VLLM_XPU_ENABLE_XPU_GRAPH', '0') != '0':
        raise RuntimeError('b70_cpu_embed requires VLLM_XPU_ENABLE_XPU_GRAPH=0')

    def b70_cpu_embedding(input_ids: torch.Tensor, key: str) -> torch.Tensor:
        rows = torch.nn.functional.embedding(input_ids.to('cpu'), _WEIGHTS[key])
        return rows.to(input_ids.device)

    def b70_cpu_embedding_fake(input_ids: torch.Tensor, key: str) -> torch.Tensor:
        weight = _WEIGHTS[key]
        return torch.empty((*input_ids.shape, weight.shape[1]), dtype=weight.dtype, device=input_ids.device)

    direct_register_custom_op('b70_cpu_embedding', b70_cpu_embedding, fake_impl=b70_cpu_embedding_fake)

    def forward(self, input_):
        return torch.ops.vllm.b70_cpu_embedding(input_.long(), self._b70_cpu_key)

    original = loader_utils.process_weights_after_loading

    def process_weights_after_loading(model, model_config, target_device):
        original(model, model_config, target_device)
        moved = 0
        for name, module in model.named_modules():
            if (isinstance(module, vpe.VocabParallelEmbedding) and not isinstance(module, vpe.ParallelLMHead)
                    and module.weight.device.type != 'cpu'):
                if module.tp_size != 1 or module.num_embeddings_padded != module.org_vocab_size:
                    raise RuntimeError(f'b70_cpu_embed supports one unsharded, unpadded table only: {name}')
                key = f'{id(model)}:{name}'
                module.weight = torch.nn.Parameter(module.weight.data.to('cpu'), requires_grad=False)
                _WEIGHTS[key] = module.weight
                module._b70_cpu_key = key
                module.forward = types.MethodType(forward, module)
                moved += module.weight.numel() * module.weight.element_size()
                logger.warning('b70_cpu_embed: %s (%s, %s) moved to host memory', name,
                               tuple(module.weight.shape), module.weight.dtype)
        if moved:
            torch.xpu.empty_cache()
            logger.warning('b70_cpu_embed: %.3f GiB of input embeddings now on host memory', moved / 2 ** 30)

    loader_utils.process_weights_after_loading = process_weights_after_loading
    base_loader.process_weights_after_loading = process_weights_after_loading
    loader_utils._b70_cpu_embed = True
