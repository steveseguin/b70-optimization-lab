"""Diagnostic overlay: SHA-256 of module outputs for one prefill size (never for serving).

Enabled only with B70_LAYER_HASH_TOKENS=N (and meant for --enforce-eager). After
weights load, forward hooks on every module whose name matches
B70_LAYER_HASH_PATTERN hash each floating-point output tensor whose leading
dimension is N, synchronously and before any later in-place update. A pre-hook on
the first matching decoder layer starts a new call group. Records go to
$B70_LAYER_HASH_DIR/hash-<pid>.jsonl; comparing two identical requests shows the
first module whose output differs. Values are never modified.
"""
import hashlib
import json
import os
import re

_STATE = {'group': -1, 'index': 0}


def register():
    tokens = int(os.environ.get('B70_LAYER_HASH_TOKENS', '0') or 0)
    if tokens <= 0:
        return
    import torch
    from vllm.logger import init_logger
    from vllm.model_executor.model_loader import base_loader
    from vllm.model_executor.model_loader import utils as loader_utils

    logger = init_logger('b70_layer_hash')
    if getattr(loader_utils, '_b70_layer_hash', False):
        return
    pattern = re.compile(os.environ.get(
        'B70_LAYER_HASH_PATTERN',
        r'(^|\.)layers\.\d+(\.(input_layernorm|post_attention_layernorm|linear_attn|self_attn|mlp)'
        r'(\.(in_proj_qkvz|in_proj_ba|conv1d|norm|out_proj|qkv_proj|qkqv_proj|o_proj|gate_up_proj|down_proj|q_norm|k_norm|attn))?)?$'
        r'|(^|\.)norm$|(^|\.)embed_tokens$'))
    input_pattern = re.compile(os.environ.get('B70_LAYER_HASH_INPUT_PATTERN', r'(out_proj|o_proj|down_proj|gate_up_proj)$'))
    out_dir = os.environ.get('B70_LAYER_HASH_DIR', '/hash')
    path = os.path.join(out_dir, f'hash-{os.getpid()}.jsonl')

    def tensors(value):
        if isinstance(value, torch.Tensor):
            yield value
        elif isinstance(value, (tuple, list)):
            for item in value:
                yield from tensors(item)

    def hook_for(name, io='out'):
        def hook(module, inputs, output=None):
            if _STATE['group'] < 0:
                return
            value = inputs if io == 'in' else output
            found = [t for t in tensors(value) if t.is_floating_point() and t.dim() >= 1 and t.shape[0] == tokens]
            if not found:
                return
            torch.xpu.synchronize()
            records = []
            for slot, t in enumerate(found):
                data = t.detach().contiguous().to('cpu')
                digest = hashlib.sha256(data.view(torch.uint8).numpy().tobytes()).hexdigest()
                records.append(dict(group=_STATE['group'], index=_STATE['index'], name=name, io=io, slot=slot,
                                    shape=list(t.shape), dtype=str(t.dtype), sha256=digest,
                                    ptr_mod_64=t.data_ptr() % 64, storage_offset=t.storage_offset(),
                                    stride=list(t.stride()), contiguous=t.is_contiguous()))
                _STATE['index'] += 1
            with open(path, 'a') as log:
                for record in records:
                    log.write(json.dumps(record) + '\n')
        return hook

    def start_group(module, args, kwargs):
        found = [t for t in tensors(list(args) + list(kwargs.values())) if t.dim() >= 1 and t.shape[0] == tokens]
        if found:
            _STATE['group'] += 1
            _STATE['index'] = 0

    original = loader_utils.process_weights_after_loading

    def process_weights_after_loading(model, model_config, target_device):
        original(model, model_config, target_device)
        if getattr(model, '_b70_layer_hash_done', False):
            return
        os.makedirs(out_dir, exist_ok=True)
        hooked, first_layer = 0, None
        for name, module in model.named_modules():
            if name and input_pattern.search(name) and pattern.search(name):
                module.register_forward_pre_hook(hook_for(name, 'in'))
            if name and pattern.search(name):
                module.register_forward_hook(hook_for(name))
                hooked += 1
                if first_layer is None and re.search(r'(^|\.)(embed_tokens|layers\.0)$', name):
                    first_layer = module
        if first_layer is not None and hooked:
            first_layer.register_forward_pre_hook(start_group, with_kwargs=True)
            model._b70_layer_hash_done = True
            logger.warning('b70_layer_hash: %d modules hooked for %d-token calls -> %s', hooked, tokens, path)

    loader_utils.process_weights_after_loading = process_weights_after_loading
    base_loader.process_weights_after_loading = process_weights_after_loading
    loader_utils._b70_layer_hash = True
