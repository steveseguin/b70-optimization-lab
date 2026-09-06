# R256: let the draft-only INT4 lm_head work on lanes whose target head carries a quantization method without
# make_xpu_int4_draft_copy (the gptq relabel: lm_head is FP16/unquantized but its quant_method object comes from the
# AutoGPTQ config). Fall back to the generic embedding method's implementation, which only needs the FP16 head weight
# and _xpu_C.int4_gemm_w4a16 (batch-invariant under the R221 fixed-K library). The target verifier head stays FP16.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/spec_decode/llm_base_proposer.py"
s = open(p).read()
old = '''                quant_method = getattr(lm_head_to_share, "quant_method", None)
                prepare = getattr(quant_method, "make_xpu_int4_draft_copy", None)
                if not callable(prepare):
'''
new = '''                quant_method = getattr(lm_head_to_share, "quant_method", None)
                prepare = getattr(quant_method, "make_xpu_int4_draft_copy", None)
                if not callable(prepare):
                    # R256: unquantized FP16 head under a non-embedding quant method (gptq relabel)
                    from vllm.model_executor.layers.vocab_parallel_embedding import (
                        UnquantizedEmbeddingMethod as _R256Emb,
                    )
                    _weight = getattr(lm_head_to_share, "weight", None)
                    if _weight is not None and _weight.dtype in (torch.float16, torch.bfloat16):
                        _emb = _R256Emb()
                        prepare = getattr(_emb, "make_xpu_int4_draft_copy", None)
                        logger.info("R256: draft-only INT4 head via UnquantizedEmbeddingMethod fallback")
                if not callable(prepare):
'''
assert s.count(old) == 1, "anchor"
s = s.replace(old, new)
assert "import torch" in s
open(p, "w").write(s)
print("R256 draft head fallback inserted; sha256", hashlib.sha256(s.encode()).hexdigest())
