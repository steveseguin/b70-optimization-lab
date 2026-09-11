# R291: R290 with a verified census and persistent pad buffers.
#
# Chain 13 measured R290 on the server: the tax is gone above c16 and the strict gates pass, but MTP0
# exactness on one card is lost from c20 up (14% divergent at c24-c64; the stagger recipe 888/1280) and
# single-user throughput drops 12%. Offline the op is bit-exact for every shape the server logged, so the
# fault is in the census, not the arithmetic: it fingerprinted a class by row 0 of ONE random input, and on
# the server that merged rows 33-192 of the 2560x4096 out-projection into one class where offline they are
# two, and let 385-512 join it - the region where this shape's kernels are split-K and nondeterministic.
# Prefill chunks of several prompts land there, so the state after prefill differed between passes.
#
# Changes. (1) Classes are fingerprinted on three inputs and a class is CANONICAL-ELIGIBLE only if, at its
# first and last member and one in between, it is run-to-run deterministic, position-invariant (roll the
# rows, un-roll, same bits) and pad-invariant (zero-pad, same real rows). Rows outside every eligible class
# are padded to the next eligible size or split into eligible pieces; a shape with no eligible class beyond
# 1-32 falls back to R224's 32-row pieces. (2) Pad rows come from a persistent zeroed buffer per shape, so
# a padded call is one copy and one GEMM instead of an allocation, a cat and a slice; the 12% was that.
# (3) The verification result is logged per shape ("R291 classpad census ... eligible=... verdict=...").
# (4) VLLM_XPU_FP16_LINEAR_CLASSPAD_MIN_BYTES (default 0) restricts the mode to weights at least that
# large; smaller shapes keep R224 behaviour. Not used by default; it exists so the lm_head-only variant
# can be measured without another image.
import hashlib, pathlib
p = pathlib.Path("/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py")
s = p.read_text()

start = s.index("_R290_MAPS: dict = {}")
end = s.index("def _xpu_fp16_linear_rowchunk_impl(")
new_block = '''_R290_MAPS: dict = {}
_R291_MIN_BYTES = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_CLASSPAD_MIN_BYTES", "0"))
_R291_BUFS: dict = {}


def _r291_invariant(weight: torch.Tensor, x: torch.Tensor, m: int) -> bool:
    """Deterministic, position-invariant and pad-invariant at row count m."""
    lin = torch.nn.functional.linear
    o = lin(x[:m], weight)
    if not torch.equal(lin(x[:m], weight), o):
        return False
    perm = torch.roll(torch.arange(m, device=x.device), 3)
    if not torch.equal(lin(x[perm], weight)[torch.argsort(perm)], o):
        return False
    h = max(m // 2, 1)
    xp = torch.cat([x[:h], torch.zeros(m - h, x.shape[1], device=x.device, dtype=x.dtype)], dim=0)
    return bool(torch.equal(lin(xp, weight)[:h], o[:h]))


def _r290_census(weight: torch.Tensor) -> tuple:
    """Verified class map of F.linear at this weight shape for M in 1..MAXM."""
    import logging
    log = logging.getLogger("vllm")
    n, k = weight.shape
    gen = torch.Generator(device="cpu").manual_seed(291)
    xs = [(torch.randn(_R290_MAXM, k, generator=gen) * sc).to(device=weight.device, dtype=weight.dtype)
          for sc in (0.5, 1.0, 0.1)]
    lin = torch.nn.functional.linear
    refs: list = []
    cls: list = []
    for m in range(1, _R290_MAXM + 1):
        fp = tuple(lin(x[:m], weight)[:1] for x in xs)
        cid = None
        for i, r in enumerate(refs):
            if all(torch.equal(a, b) for a, b in zip(fp, r)):
                cid = i
                break
        if cid is None:
            refs.append(tuple(t.clone() for t in fp))
            cid = len(refs) - 1
        cls.append(cid)
    members: dict = {}
    for m, c in enumerate(cls, start=1):
        members.setdefault(c, []).append(m)
    eligible = set()
    for c, ms in members.items():
        probe = sorted({ms[0], ms[len(ms) // 2], ms[-1]})
        if all(_r291_invariant(weight, xs[0], m) for m in probe):
            eligible.add(c)
    # canonical: the eligible class with the most members that is not the single-row class (class of M=1),
    # unless nothing else is eligible - then fall back to R224 pieces (target None everywhere).
    single_cls = cls[0]
    cands = [c for c in eligible if c != single_cls]
    if cands:
        canonical = max(cands, key=lambda c: (len(members[c]), -c))
        target = [None] * (_R290_MAXM + 1)
        nxt = None
        for m in range(_R290_MAXM, 0, -1):
            if cls[m - 1] == canonical:
                nxt = m
            target[m] = nxt
        largest = members[canonical][-1]
        verdict = "classpad"
    else:
        canonical, target, largest, verdict = single_cls, None, 32, "fallback-r224-pieces"
    runs, st = [], 1
    for m in range(2, _R290_MAXM + 2):
        if m > _R290_MAXM or cls[m - 1] != cls[m - 2]:
            runs.append(f"{st}-{m - 1}:c{cls[m - 2]}")
            st = m
    log.info("R291 classpad census shape=%dx%d dtype=%s classes=%d eligible=%s canonical=c%d largest=%d "
             "verdict=%s map=%s", n, k, str(weight.dtype).replace("torch.", ""), len(refs),
             ",".join(f"c{c}" for c in sorted(eligible)), canonical, largest, verdict, " ".join(runs))
    return canonical, target, largest


def _r290_one(x2: torch.Tensor, weight: torch.Tensor, bias, target: list) -> torch.Tensor:
    m = x2.shape[0]
    t = target[m]
    if t == m:
        return torch.nn.functional.linear(x2, weight, bias)
    key = (t, x2.shape[1], x2.dtype, str(x2.device))
    buf = _R291_BUFS.get(key)
    if buf is None:
        buf = torch.zeros(t, x2.shape[1], device=x2.device, dtype=x2.dtype)
        _R291_BUFS[key] = buf
    buf[:m].copy_(x2)
    buf[m:].zero_()
    return torch.nn.functional.linear(buf, weight, bias)[:m]


def _r290_linear(x2: torch.Tensor, weight: torch.Tensor, bias) -> torch.Tensor:
    key = (tuple(weight.shape), weight.dtype, str(weight.device))
    entry = _R290_MAPS.get(key)
    if entry is None:
        if _R291_MIN_BYTES > 0 and weight.numel() * weight.element_size() < _R291_MIN_BYTES:
            entry = (None, None, 32)
        else:
            entry = _r290_census(weight)
        _R290_MAPS[key] = entry
    canonical, target, largest = entry
    m = x2.shape[0]
    if target is None:  # R224 behaviour: <=32-row pieces in the single-row class
        if m <= 32:
            return torch.nn.functional.linear(x2, weight, bias)
        return torch.cat([torch.nn.functional.linear(x2[i:i + 32], weight, bias) for i in range(0, m, 32)], dim=0)
    if m <= _R290_MAXM and target[m] is not None:
        return _r290_one(x2, weight, bias, target)
    return torch.cat([_r290_one(x2[i:i + largest], weight, bias, target) for i in range(0, m, largest)], dim=0)


'''
s = s[:start] + new_block + s[end:]
p.write_text(s)
print("R291 verified classpad inserted; utils.py sha256", hashlib.sha256(s.encode()).hexdigest())
