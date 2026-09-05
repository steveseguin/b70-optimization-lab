# R213: Python-level determinism pad for the plain-GPTQ XPU W4A16 path (XPUwNa16LinearKernel.apply_weights ->
# torch.ops._xpu_C.int4_gemm_w4a16). The August 2026 finding (notes/2026-08-20-autoround-int4-runtime-nondeterminism-
# found-and-pad-fix.md) and the R212 census both place the kernel's nondeterministic band strictly between 128 and 512
# rows; the C++ pad of that patch never reached this image's _xpu_C. Zero-padding the rows to 512 (and 512<M<1024 to
# 1024, optional) is bit-identical run to run and to the natural 512-row result. Rows M<=128 (decode, MTP verify) untouched.
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
        m = reshaped_x.shape[0]
        pad_to = 0
        if _R213_PAD and _R213_LOW < m < 512:
            pad_to = 512
        elif _R213_PAD and _R213_PAD_HIGH and 512 < m < 1024:
            pad_to = 1024
        if pad_to:
            xp = torch.zeros(pad_to, reshaped_x.shape[1], dtype=reshaped_x.dtype, device=reshaped_x.device)
            xp[:m].copy_(reshaped_x)
            out = torch.ops._xpu_C.int4_gemm_w4a16(xp, w_q.t(), bias if bias is not None else None, w_s, w_zp, self.config.group_size, w_gidx)
            return out[:m]
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
hdr = ("import os as _r213_os\n"
       "_R213_PAD = _r213_os.environ.get(\"VLLM_XPU_W4A16_DETERMINISM_PAD\", \"1\") == \"1\"\n"
       "_R213_LOW = int(_r213_os.environ.get(\"VLLM_XPU_W4A16_DETERMINISM_PAD_LOW\", \"128\"))\n"
       "_R213_PAD_HIGH = _r213_os.environ.get(\"VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH\", \"1\") == \"1\"\n")
s = s.replace("import torch\n", "import torch\n" + hdr, 1)
assert s.count("_R213_PAD") >= 3
open(p, "w").write(s)
print("R213 W4A16 determinism pad inserted; xpu.py sha256", hashlib.sha256(s.encode()).hexdigest())
