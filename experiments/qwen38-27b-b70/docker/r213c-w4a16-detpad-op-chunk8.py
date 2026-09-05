# R213c: adds the opt-in VLLM_XPU_W4A16_ROW_CHUNK8 strict batch-invariant mode (R217 class map).
# R213b: the R213 determinism pad for the plain-GPTQ XPU W4A16 path, moved into an opaque custom op so torch.compile /
# Dynamo never sees the Python branch on the row count (R213's in-graph branch raised ConstraintViolationError under the
# ladder batch limits). Band: 128 < M < 512 -> 512 (VLLM_XPU_W4A16_DETERMINISM_PAD, LOW, HIGH as in R213).
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/mixed_precision/xpu.py"
s = open(p).read()
old = '''        reshaped_x = x.reshape(-1, x.shape[-1])
        w_q, w_s, w_zp, w_gidx = self._get_weight_params(layer)
        out = torch.ops._xpu_C.int4_gemm_w4a16(
            reshaped_x,
            w_q.t(),
            bias if bias is not None else None,
            w_s,
            w_zp,
            self.config.group_size,
            w_gidx,
        )
        return out
'''
new = '''        reshaped_x = x.reshape(-1, x.shape[-1])
        w_q, w_s, w_zp, w_gidx = self._get_weight_params(layer)
        if _R213_PAD:
            return torch.ops.vllm.xpu_w4a16_detpad_gemm(
                reshaped_x, w_q.t(), bias if bias is not None else None, w_s, w_zp, self.config.group_size, w_gidx)
        out = torch.ops._xpu_C.int4_gemm_w4a16(
            reshaped_x,
            w_q.t(),
            bias if bias is not None else None,
            w_s,
            w_zp,
            self.config.group_size,
            w_gidx,
        )
        return out
'''
assert s.count(old) == 1, "anchor"
s = s.replace(old, new)
hdr = '''import os as _r213_os
from vllm.utils.torch_utils import direct_register_custom_op as _r213_register
_R213_PAD = _r213_os.environ.get("VLLM_XPU_W4A16_DETERMINISM_PAD", "1") == "1"
_R213_LOW = int(_r213_os.environ.get("VLLM_XPU_W4A16_DETERMINISM_PAD_LOW", "128"))
_R213_PAD_HIGH = _r213_os.environ.get("VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH", "1") == "1"
_R213_CHUNK8 = _r213_os.environ.get("VLLM_XPU_W4A16_ROW_CHUNK8", "0") == "1"


def _xpu_w4a16_detpad_gemm_impl(
    x: torch.Tensor,
    w_q_t: torch.Tensor,
    bias: torch.Tensor | None,
    w_s: torch.Tensor,
    w_zp: torch.Tensor,
    group_size: int,
    w_gidx: torch.Tensor | None,
) -> torch.Tensor:
    m = x.shape[0]
    if _R213_CHUNK8 and m > 8:
        # strict batch-invariant mode: every row computed in the kernel's <=8-row class (bit-identical to the
        # single-request result at any concurrency); several times slower for prefill and for M>8 decode batches.
        return torch.cat([
            torch.ops._xpu_C.int4_gemm_w4a16(x[i:i + 8], w_q_t, bias, w_s, w_zp, group_size, w_gidx)
            for i in range(0, m, 8)
        ], dim=0)
    pad_to = 0
    if _R213_LOW < m < 512:
        pad_to = 512
    elif _R213_PAD_HIGH and 512 < m < 1024:
        pad_to = 1024
    if pad_to:
        xp = torch.zeros(pad_to, x.shape[1], dtype=x.dtype, device=x.device)
        xp[:m].copy_(x)
        return torch.ops._xpu_C.int4_gemm_w4a16(xp, w_q_t, bias, w_s, w_zp, group_size, w_gidx)[:m]
    return torch.ops._xpu_C.int4_gemm_w4a16(x, w_q_t, bias, w_s, w_zp, group_size, w_gidx)


def _xpu_w4a16_detpad_gemm_fake(
    x: torch.Tensor,
    w_q_t: torch.Tensor,
    bias: torch.Tensor | None,
    w_s: torch.Tensor,
    w_zp: torch.Tensor,
    group_size: int,
    w_gidx: torch.Tensor | None,
) -> torch.Tensor:
    return torch.empty((x.shape[0], w_s.shape[1]), dtype=x.dtype, device=x.device)


_r213_register(
    op_name="xpu_w4a16_detpad_gemm",
    op_func=_xpu_w4a16_detpad_gemm_impl,
    mutates_args=[],
    fake_impl=_xpu_w4a16_detpad_gemm_fake,
)
'''
s = s.replace("import torch\n", "import torch\n" + hdr, 1)
assert s.count("_R213_PAD") >= 2
open(p, "w").write(s)
print("R213b W4A16 determinism pad custom op inserted; xpu.py sha256", hashlib.sha256(s.encode()).hexdigest())
