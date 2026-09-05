#!/usr/bin/env python3
"""R220 screen: is _xpu_C.int4_gemm_w4a16 row-invariant across the token-row count under a pinned oneDNN strategy?

One process per candidate: set QWEN38_W4A16_GEMM_STRATEGY (and QWEN38_GEMM_DUMP=1 to see what oneDNN selected) before
launching. Shapes cover every INT4 GEMM of Qwen3.8-27B AutoRound at TP1 and TP2 (vLLM merges q/k/v and gate/up).
Random u4 weights (shape decides the kernel, not the values). Reports per shape: run-to-run identity, row-0 class map
across M (vs M=1), permutation invariance at M=200, padded-vs-direct at 168/200, and timings.
"""
import argparse, hashlib, json, os, statistics, sys, time
import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401

SHAPES = {  # name: (K, N); N = out features
    "tp1_qkv": (5120, 14336), "tp1_gate_up": (5120, 34816), "tp1_down": (17408, 5120), "tp1_o": (6144, 5120),
    "tp1_in_qkv": (5120, 10240), "tp1_in_z": (5120, 6144), "tp1_out": (6144, 5120),
    "tp2_qkv": (5120, 7168), "tp2_gate_up": (5120, 17408), "tp2_down": (8704, 5120), "tp2_o": (3072, 5120),
    "tp2_in_qkv": (5120, 5120), "tp2_in_z": (5120, 3072), "tp2_out": (3072, 5120),
}
DEFAULT_MS = [1, 2, 4, 5, 8, 9, 12, 16, 17, 24, 32, 33, 48, 64, 65, 96, 128, 129, 168, 200, 256, 257, 384, 512, 513, 768, 1024]
TIMED_MS = [1, 5, 8, 32, 128, 512, 1024]


def digest(t):
    return hashlib.sha256(t.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()).hexdigest()[:16]


def make_layer(k, n, gen, dev):
    qweight = torch.randint(0, 2**31 - 1, (k // 8, n), generator=gen, dtype=torch.int32)  # packed u4 [K/8, N]
    scales = (torch.rand((k // 128, n), generator=gen) * 0.02 + 0.005).to(torch.float16)
    w_q = qweight.t().contiguous().to(dev)  # XPUwNa16 stores [N, K/8] and passes w_q.t()
    w_s = scales.contiguous().to(dev)
    w_zp = torch.Tensor([8]).to(torch.int8).to(dev)
    return lambda x: torch.ops._xpu_C.int4_gemm_w4a16(x, w_q.t(), None, w_s, w_zp, 128, None)


def time_us(fn, warm=5, iters=30, reps=3):
    for _ in range(warm):
        fn()
    torch.xpu.synchronize(); vals = []
    for _ in range(reps):
        torch.xpu.synchronize(); t = time.perf_counter()
        for _ in range(iters):
            fn()
        torch.xpu.synchronize(); vals.append((time.perf_counter() - t) / iters * 1e6)
    return round(statistics.median(vals), 1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--shapes", default="all")
    ap.add_argument("--ms", default=",".join(map(str, DEFAULT_MS))); ap.add_argument("--skip-timing", action="store_true")
    a = ap.parse_args()
    ms = [int(v) for v in a.ms.split(",")]; dev = torch.device("xpu:0")
    names = sorted(SHAPES) if a.shapes == "all" else a.shapes.split(",")
    gen = torch.Generator(device="cpu").manual_seed(20260905)
    report = {"schema": "neural.download.qwen38-int4-w4a16-strategy-screen.v1", "strategy": os.environ.get("QWEN38_W4A16_GEMM_STRATEGY"),
              "maxn": os.environ.get("QWEN38_W4A16_GEMM_MAXN"), "device": torch.xpu.get_device_name(0), "ms": ms, "shapes": {}}
    all_invariant = True
    for name in names:
        k, n = SHAPES[name]; f = make_layer(k, n, gen, dev)
        x = torch.randn((max(ms), k), generator=gen).to(torch.float16).to(dev)
        outs = {m: f(x[:m]) for m in ms}; torch.xpu.synchronize()
        ref1 = digest(outs[1][0])
        classes = {}
        for m in ms:
            classes.setdefault(digest(outs[m][0]), []).append(m)
        r2r = all(digest(f(x[:m])) == digest(outs[m]) for m in (1, 5, 32, 200, 512, 1024) if m in outs)
        prefix_exact = {m: bool(torch.equal(outs[m], outs[max(ms)][:m])) for m in ms}
        perm = torch.randperm(200, generator=gen).to(dev)
        permuted = f(x[:200][perm])[torch.argsort(perm)]; perm_ok = torch.equal(permuted, outs[200]) if 200 in outs else None
        pad = torch.zeros((200, k), dtype=torch.float16, device=dev); pad[:168].copy_(x[:168])
        pad_ok = torch.equal(f(pad)[:168], f(x[:168]))
        invariant = len(classes) == 1 and r2r and bool(perm_ok) and pad_ok
        all_invariant &= invariant
        tim = {} if a.skip_timing else {str(m): time_us(lambda m=m: f(x[:m])) for m in TIMED_MS if m <= max(ms)}
        report["shapes"][name] = {"K": k, "N": n, "run_to_run": r2r, "row0_classes": {c: v for c, v in classes.items()},
                                  "row0_class_count": len(classes), "row0_eq_m1_for_all_M": len(classes) == 1,
                                  "prefix_exact_vs_largest": prefix_exact, "row0_digest_by_m": {str(m): digest(outs[m][0]) for m in ms}, "full_digest_by_m": {str(m): digest(outs[m]) for m in ms}, "perm200_invariant": perm_ok, "pad168to200_exact": pad_ok,
                                  "invariant": invariant, "us": tim}
        print(f"{name:12s} K={k:5d} N={n:5d} classes={len(classes)} r2r={r2r} perm={perm_ok} pad={pad_ok} INVARIANT={invariant} us={tim}", flush=True)
    report["all_shapes_invariant"] = all_invariant
    json.dump(report, open(a.out, "w"), indent=1); print("ALL_INVARIANT", all_invariant)
    return 0


if __name__ == "__main__":
    sys.exit(main())
