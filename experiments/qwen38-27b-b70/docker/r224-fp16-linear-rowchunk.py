# R224: batch-invariant FP16 linears on XPU. The oneDNN f16 GEMM used by every unquantized linear (lm_head, mtp.fc,
# in_proj_a/b) keeps row 0 bit-identical to the single-row result only for M <= 32 (2026-09-05 census); the sampled-row
# lm_head at c64 x depth 4 sees 320 rows. Run rows in <=CHUNK pieces inside a Dynamo-opaque custom op.
# env VLLM_XPU_FP16_LINEAR_ROWCHUNK (default 32; 0 disables).
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py"
s = open(p).read()
old = '''def default_unquantized_gemm(
    layer: torch.nn.Module,
    x: torch.Tensor,
    weight: torch.Tensor,
    bias: torch.Tensor | None = None,
):
    return torch.nn.functional.linear(x, weight, bias)
'''
new = '''_R224_CHUNK = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_ROWCHUNK", "32"))


def _xpu_fp16_linear_rowchunk_impl(
    x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor | None, chunk: int
) -> torch.Tensor:
    x2 = x.reshape(-1, x.shape[-1])
    m = x2.shape[0]
    if m <= chunk:
        out = torch.nn.functional.linear(x2, weight, bias)
    else:
        out = torch.cat(
            [torch.nn.functional.linear(x2[i:i + chunk], weight, bias) for i in range(0, m, chunk)], dim=0
        )
    return out.reshape(x.shape[:-1] + (weight.shape[0],))


def _xpu_fp16_linear_rowchunk_fake(
    x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor | None, chunk: int
) -> torch.Tensor:
    return torch.empty(x.shape[:-1] + (weight.shape[0],), dtype=x.dtype, device=x.device)


if _R224_CHUNK > 0:
    from vllm.utils.torch_utils import direct_register_custom_op as _r224_register

    _r224_register(
        op_name="xpu_fp16_linear_rowchunk",
        op_func=_xpu_fp16_linear_rowchunk_impl,
        mutates_args=[],
        fake_impl=_xpu_fp16_linear_rowchunk_fake,
    )


def default_unquantized_gemm(
    layer: torch.nn.Module,
    x: torch.Tensor,
    weight: torch.Tensor,
    bias: torch.Tensor | None = None,
):
    if _R224_CHUNK > 0 and x.device.type == "xpu" and x.dtype in (torch.float16, torch.bfloat16):
        return torch.ops.vllm.xpu_fp16_linear_rowchunk(x, weight, bias, _R224_CHUNK)
    return torch.nn.functional.linear(x, weight, bias)
'''
assert s.count(old) == 1, "anchor"
s = s.replace(old, new)
open(p, "w").write(s)
print("R224 fp16 linear row-chunk op inserted; utils.py sha256", hashlib.sha256(s.encode()).hexdigest())
