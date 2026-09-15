"""Draft-only FP16 shortlist lm_head for MTP drafting, with no quantization (research overlay).

Enabled only with B70_DRAFT_FP16_SHORTLIST=<token id file>. The image's R294 path
builds the draft head as an INT4 copy of the shortlisted rows. This overlay
replaces that construction with an exact FP16 copy of the same rows (the target
lm_head weights, unchanged) and scores draft positions with the ordinary FP16
linear kernel, scattering into a full-vocabulary row of -inf. The target
verifier keeps its own full FP16 head, so outputs cannot change; only draft
proposals (and therefore speed) are affected. It hooks the draft-copy call that
vLLM makes when VLLM_XPU_DRAFT_LM_HEAD_INT4=1, so the launcher sets that variable
as the trigger; no INT4 buffers are created.
"""
import copy
import os


def register():
    path = os.environ.get('B70_DRAFT_FP16_SHORTLIST', '').strip()
    if not path:
        return
    import torch
    from vllm.logger import init_logger
    from vllm.model_executor.layers import vocab_parallel_embedding as vpe

    method = vpe.UnquantizedEmbeddingMethod
    if getattr(method, '_b70_draft_fp16', False):
        return
    logger = init_logger('b70_draft_fp16_shortlist')
    original_apply = method.apply

    def make_draft_copy(self, layer):
        weight = getattr(layer, 'weight', None)
        if weight is None or weight.device.type != 'xpu' or weight.dtype not in (torch.float16, torch.bfloat16):
            raise RuntimeError('draft FP16 shortlist requires an XPU FP16/BF16 lm_head weight')
        ids = sorted({int(t) for t in open(path).read().split() if t.strip()})
        indices = getattr(layer, 'shard_indices', None)
        start = getattr(indices, 'org_vocab_start_index', 0) if indices is not None else 0
        end = getattr(indices, 'org_vocab_end_index', weight.shape[0]) if indices is not None else weight.shape[0]
        local = [t - start for t in ids if start <= t < end] or [0]
        local_t = torch.tensor(local, dtype=torch.long, device=weight.device)
        with torch.no_grad():
            subset = weight.index_select(0, local_t).contiguous()
        draft = copy.copy(layer)
        draft._parameters = layer._parameters.copy()
        draft._buffers = layer._buffers.copy()
        draft._modules = layer._modules.copy()
        draft._non_persistent_buffers_set = layer._non_persistent_buffers_set.copy()
        draft.register_buffer('_b70_draft_fp16_weight', subset, persistent=False)
        draft.register_buffer('_b70_draft_fp16_local', local_t, persistent=False)
        draft._b70_draft_fp16_full_rows = weight.shape[0]
        draft._b70_draft_fp16_enabled = True
        logger.warning('b70_draft_fp16_shortlist: draft-only FP16 head with %d of %d rows (%.3f GiB); '
                       'target verifier head unchanged', len(local), weight.shape[0],
                       subset.numel() * subset.element_size() / 2 ** 30)
        return draft

    def apply(self, layer, x, bias=None):
        if getattr(layer, '_b70_draft_fp16_enabled', False) and bias is None:
            flat = x.reshape(-1, x.shape[-1])
            logits = vpe.dispatch_unquantized_gemm()(layer, flat, layer._b70_draft_fp16_weight, None)
            full = torch.full((logits.shape[0], layer._b70_draft_fp16_full_rows), float('-inf'),
                              dtype=logits.dtype, device=logits.device)
            full.index_copy_(1, layer._b70_draft_fp16_local, logits)
            return full.reshape(x.shape[:-1] + (layer._b70_draft_fp16_full_rows,))
        return original_apply(self, layer, x, bias)

    method.make_xpu_int4_draft_copy = make_draft_copy
    method.apply = apply
    method._b70_draft_fp16 = True
    logger.warning('b70_draft_fp16_shortlist: enabled with %s', path)
