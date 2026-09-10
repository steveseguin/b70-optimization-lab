# R290: class-consistent FP16 linears. Extends the R224 row-chunk op with a mode that keeps every call of a
# given weight shape inside ONE oneDNN M-class instead of the single-row class.
#
# Why. The oneDNN fp16 GEMM behind every unquantized XPU linear (lm_head, mtp.fc) selects its kernel by the
# row count M, and different kernels round differently. At the Qwen3.5-4B vocabulary shape (248320 x 2560)
# the classes are M 1..32, 33..128, 129..320, 321..512; within a class every row's value is independent of
# M, of its position and of the other rows (measured 2026-09-09, bit-exact, deterministic). R224 keeps every
# call in the single-row class by running <=32-row pieces, which is exact but re-reads the 1.2 GB weight
# once per piece: eight pieces at c64 depth 3 cost ~18 ms per step against ~3 ms for one call, a 25-54%
# throughput tax above 32 rows. This mode instead measures the class map for each weight shape on first
# use, picks the most populous class as canonical, and pads or splits every call so all of its pieces land
# in that class. Row values then agree bit-for-bit between one user and sixty-four, at the cost of the
# canonical class's minimum size (33 rows here) on single-row calls: ~0.2 ms per step.
#
# env: VLLM_XPU_FP16_LINEAR_CLASSPAD=1 enables it (default 0: R224 behaviour, VLLM_XPU_FP16_LINEAR_ROWCHUNK
# unchanged). VLLM_XPU_FP16_LINEAR_CLASSPAD_MAXM (default 512) bounds the census and the largest piece.
# The measured map is logged once per shape as "R290 classpad census ..." so a container record shows it.
import hashlib, pathlib
p = pathlib.Path("/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py")
s = p.read_text()

old_env = '''_R224_CHUNK = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_ROWCHUNK", "32"))
'''
new_env = '''_R224_CHUNK = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_ROWCHUNK", "32"))
_R290_CLASSPAD = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_CLASSPAD", "0"))
_R290_MAXM = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_CLASSPAD_MAXM", "512"))
_R290_MAPS: dict = {}


def _r290_census(weight: torch.Tensor) -> tuple:
    """Class map of F.linear at this weight shape: class id of row 0 for every M in 1..MAXM."""
    import logging
    n, k = weight.shape
    gen = torch.Generator(device="cpu").manual_seed(290)
    x = (torch.randn(_R290_MAXM, k, generator=gen) * 0.5).to(device=weight.device, dtype=weight.dtype)
    refs: list = []
    cls: list = []
    for m in range(1, _R290_MAXM + 1):
        row0 = torch.nn.functional.linear(x[:m], weight)[:1]
        cid = None
        for i, r in enumerate(refs):
            if torch.equal(row0, r):
                cid = i
                break
        if cid is None:
            refs.append(row0.clone())
            cid = len(refs) - 1
        cls.append(cid)
    counts: dict = {}
    for c in cls:
        counts[c] = counts.get(c, 0) + 1
    canonical = max(counts, key=lambda c: (counts[c], -c))
    target = [None] * (_R290_MAXM + 1)
    nxt = None
    for m in range(_R290_MAXM, 0, -1):
        if cls[m - 1] == canonical:
            nxt = m
        target[m] = nxt
    largest = max(m for m in range(1, _R290_MAXM + 1) if cls[m - 1] == canonical)
    runs, start = [], 1
    for m in range(2, _R290_MAXM + 2):
        if m > _R290_MAXM or cls[m - 1] != cls[m - 2]:
            runs.append(f"{start}-{m - 1}:c{cls[m - 2]}")
            start = m
    logging.getLogger("vllm").info(
        "R290 classpad census shape=%dx%d dtype=%s classes=%d canonical=c%d largest=%d map=%s",
        n, k, str(weight.dtype).replace("torch.", ""), len(refs), canonical, largest, " ".join(runs))
    return canonical, target, largest


def _r290_one(x2: torch.Tensor, weight: torch.Tensor, bias, target: list) -> torch.Tensor:
    m = x2.shape[0]
    t = target[m]
    if t == m:
        return torch.nn.functional.linear(x2, weight, bias)
    pad = torch.zeros(t - m, x2.shape[1], device=x2.device, dtype=x2.dtype)
    return torch.nn.functional.linear(torch.cat([x2, pad], dim=0), weight, bias)[:m]


def _r290_linear(x2: torch.Tensor, weight: torch.Tensor, bias) -> torch.Tensor:
    key = (tuple(weight.shape), weight.dtype, str(weight.device))
    entry = _R290_MAPS.get(key)
    if entry is None:
        entry = _r290_census(weight)
        _R290_MAPS[key] = entry
    canonical, target, largest = entry
    m = x2.shape[0]
    if m <= _R290_MAXM and target[m] is not None:
        return _r290_one(x2, weight, bias, target)
    # No canonical size at or above m within the census: split into pieces no larger than the largest
    # canonical size; every piece then has a target (target[largest] == largest).
    return torch.cat([_r290_one(x2[i:i + largest], weight, bias, target) for i in range(0, m, largest)], dim=0)
'''
assert s.count(old_env) == 1, "env anchor"
s = s.replace(old_env, new_env)

old_impl = '''    x2 = x.reshape(-1, x.shape[-1])
    m = x2.shape[0]
    if m <= chunk:
        out = torch.nn.functional.linear(x2, weight, bias)
'''
new_impl = '''    x2 = x.reshape(-1, x.shape[-1])
    m = x2.shape[0]
    if _R290_CLASSPAD > 0:
        out = _r290_linear(x2, weight, bias)
    elif m <= chunk:
        out = torch.nn.functional.linear(x2, weight, bias)
'''
assert s.count(old_impl) == 1, "impl anchor"
s = s.replace(old_impl, new_impl)

old_reg = "if _R224_CHUNK > 0:\n    from vllm.utils.torch_utils import direct_register_custom_op as _r224_register"
new_reg = "if _R224_CHUNK > 0 or _R290_CLASSPAD > 0:\n    from vllm.utils.torch_utils import direct_register_custom_op as _r224_register"
assert s.count(old_reg) == 1, "register anchor"
s = s.replace(old_reg, new_reg)

old_call = '''    if _R224_CHUNK > 0 and x.device.type == "xpu" and x.dtype in (torch.float16, torch.bfloat16):
        return torch.ops.vllm.xpu_fp16_linear_rowchunk(x, weight, bias, _R224_CHUNK)
'''
new_call = '''    if (_R224_CHUNK > 0 or _R290_CLASSPAD > 0) and x.device.type == "xpu" and x.dtype in (torch.float16, torch.bfloat16):
        return torch.ops.vllm.xpu_fp16_linear_rowchunk(x, weight, bias, _R224_CHUNK)
'''
assert s.count(old_call) == 1, "call anchor"
s = s.replace(old_call, new_call)
p.write_text(s)
print("R290 classpad mode inserted; utils.py sha256", hashlib.sha256(s.encode()).hexdigest())
