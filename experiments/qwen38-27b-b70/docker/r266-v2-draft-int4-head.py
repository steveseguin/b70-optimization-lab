# R266: draft-only INT4 lm_head for vLLM's V2 model runner (VLLM_USE_V2_MODEL_RUNNER=1). The V2 speculator loads the MTP
# draft through v1/worker/gpu/spec_decode/eagle/utils.py::load_eagle_model, which shares the target's FP16 lm_head with the
# draft; the R62/R256 draft-only INT4 head lives in the V1 proposer and never runs under V2. Mirror it here: when
# VLLM_XPU_DRAFT_LM_HEAD_INT4 is on, install a draft-only INT4 copy (group-128 RTN, _xpu_C.int4_gemm_w4a16 under the fixed-K
# library) on eagle_model.lm_head and every MTP layer's shared_head.head; the target verifier head stays FP16, so outputs
# are unchanged (same construction as R256, which passed 12/12 vs the MTP0 oracle).
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu/spec_decode/eagle/utils.py"
s = open(p).read()
old = '''    target_lm_head = get_target_lm_head(target_model, target_language_model)
    draft_lm_head = getattr(eagle_model, "lm_head", None)
    if target_lm_head is not None and _should_share(
        eagle_model, "has_own_lm_head", draft_lm_head, target_lm_head
    ):
        if draft_lm_head is not None:
            del eagle_model.lm_head
        eagle_model.lm_head = target_lm_head
'''
new = '''    target_lm_head = get_target_lm_head(target_model, target_language_model)
    draft_lm_head = getattr(eagle_model, "lm_head", None)
    if target_lm_head is not None and _should_share(
        eagle_model, "has_own_lm_head", draft_lm_head, target_lm_head
    ):
        # R266: draft-only INT4 head (see V1 proposer R62/R256); the target head stays FP16.
        import os as _r266_os
        if _r266_os.environ.get("VLLM_XPU_DRAFT_LM_HEAD_INT4", "0").strip().lower() in {"1", "true", "yes", "on"}:
            import torch as _r266_torch
            from vllm.logger import init_logger as _r266_init_logger
            _r266_logger = _r266_init_logger(__name__)
            _prepare = getattr(getattr(target_lm_head, "quant_method", None), "make_xpu_int4_draft_copy", None)
            if not callable(_prepare):
                from vllm.model_executor.layers.vocab_parallel_embedding import (
                    UnquantizedEmbeddingMethod as _R266Emb,
                )
                _w = getattr(target_lm_head, "weight", None)
                if _w is not None and _w.dtype in (_r266_torch.float16, _r266_torch.bfloat16):
                    _prepare = getattr(_R266Emb(), "make_xpu_int4_draft_copy", None)
            if not callable(_prepare):
                raise RuntimeError("R266: draft INT4 requested but no draft-only head can be prepared")
            _draft_head = _prepare(target_lm_head)
            if _draft_head is None:
                raise RuntimeError("R266: draft INT4 requested but no draft-only head was prepared")
            _r266_logger.info("R266: V2 speculator uses a draft-only INT4 lm_head; the target verifier head stays FP16")
            target_lm_head = _draft_head
        if draft_lm_head is not None:
            del eagle_model.lm_head
        eagle_model.lm_head = target_lm_head
'''
assert s.count(old) == 1, "anchor"
s = s.replace(old, new)
open(p, "w").write(s)
print("R266 V2 draft INT4 head inserted; sha256", hashlib.sha256(s.encode()).hexdigest())
