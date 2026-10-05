#!/usr/bin/env python3
"""Verify-path census (2026-10-04, R310/R313 images): is each speculative VERIFY row bit-identical to the same token
decoded alone, for the two verify-path kernels that had no such census yet?

Operator diagnostic only; never a speed or quality claim.

The lab rule: speculation is exact by construction only if every kernel a verify step uses gives each verify row the
bits that row gets when its token is decoded alone (one row per step). Already censused: FP8 body GEMMs, the
normalisation layers, the FP16 output layer, and (R313) the GDN speculative kernel. This script covers:

(a) FULL ATTENTION, verify call vs decode call (vLLM 0.29 site-packages of the image, read 2026-10-04).
    * Both come from vllm/v1/attention/backends/flash_attn.py FlashAttentionImpl.forward, the non-cascade branch
      (:1039-1259): ONE call flash_attn_varlen_func(q=query[:T], k=key_cache, v=value_cache, out=..., cu_seqlens_q=
      query_start_loc, max_seqlen_q=max_query_len, seqused_k=seq_lens, max_seqlen_k=max_seq_len, softmax_scale,
      causal=True, alibi_slopes=None, window_size=None, block_table=[B, ceil(max_model_len/page)] int32, softcap,
      scheduler_metadata=None, fa_version=2, q_descale=None, k/v_descale=_k_scale.expand(B, kv_heads),
      dynamic_causal=None, num_splits=0, s_aux=None, mask_mod=None, aux_tensors=None).  K/V of the step's tokens are
      written to the paged cache first (reshape_and_cache_flash).  Cache [blocks, page, kv_heads, 2*256] fp16, key =
      [..., :256], value = [..., 256:]; page 832 tokens (896 from 10 verify slots).  VLLM_XPU_FA_SERIAL_SPEC_DECODE=0
      in the lane env, so the per-token loop at :1163-1233 is off.
    * One user, decode step: q = 1 row, max_seqlen_q = 1, seqused_k = [n], max_seqlen_k = n.
      One user, verify step: q rows (shipped recipe 6; copy drafts up to 10 or 17), cu_seqlens_q = [0, q],
      max_seqlen_q = q, seqused_k = [L], max_seqlen_k = L.  Row r is the token at position L - q + r and attends
      to keys [0, L - q + r].
    * flash_attn_varlen_func on XPU is vllm/_xpu_ops.py xpu_ops.flash_attn_varlen_func (:1059-1138, via
      v1/attention/backends/fa_utils.py:35); it DROPS num_splits and scheduler_metadata and calls
      vllm_xpu_kernels/flash_attn_interface.py flash_attn_varlen_func (:403) with num_splits_kv=None,
      is_mix_batch=True, host_kv_lens=None.
    * Routing there (:511-538): paged, causal, uniform query length and 1 < max_seqlen_q <= _SPEC_DECODE_MAX_QLEN
      (env VLLM_XPU_SPEC_DECODE_MAX_QLEN, default 16, not set in the lane env) -> _spec_decode_varlen_fwd (:58): ONE
      varlen_fwd launch with q pseudo-sequences of one query each, seqused_k = L - (q - 1 - r) per row,
      block table repeated per row, max_seqlen_q = 1, max_seqlen_k = L (NOT shortened per row), causal=False,
      num_splits=None, is_mix_batch=False.  A decode call (q = 1) goes to varlen_fwd directly (:565) with
      max_seqlen_q = 1, max_seqlen_k = n, causal=True, is_mix_batch=True.  Both reach the paged split-K DECODE
      kernel (csrc/flash_attn/flash_api.cpp:333-416, branch max_seqlen_q == 1).  q = 17 > 16 goes to the
      chunk-prefill kernel instead (flash_api.cpp:251-276, mix-batch branch), a different kernel.
    * In the decode kernel the only per-call difference is the split count, num_splits = get_num_splits(batch,
      heads_q, heads_kv, max_seqlen_k, page) (flash_api.cpp:11-94, :361): batch = 1 and max_seqlen_k = position for
      decode; batch = q and max_seqlen_k = L for the verify call.  The kernel itself splits each row's own key range
      (paged_decode_kernel.hpp:362-392) but runs a row as ONE split whenever its key blocks (64 tokens) are fewer
      than 32 (is_single_split, :375-377) and the reduce then passes it through unchanged (:711-723,
      chunk_prefill_epilogue.hpp:562-587).  So a verify row can differ from decode only above 31 * 64 = 1,984 keys
      and only when the two split counts differ.  The census prints the predicted counts next to the measurement.
    * Package overlay b70_fa_verify_rows (packages/qwen38-27b-fp8-tp2-b70/overlays, B70_FA_VERIFY_ROWS=1 in the
      package env): wraps flash_attn.flash_attn_varlen_func; a ONE-request call with 2 <= q <=
      B70_FA_VERIFY_ROWS_MAX_Q (default 8; the copy-draft runs set 10) and max_seqlen_k > B70_FA_VERIFY_ROWS_MIN_K
      (default 1536) is replaced by q single-query calls with exactly the decode arguments (seqused_k and
      max_seqlen_k shortened per row, max_seqlen_q = 1, cu = [0, 1]).  Everything else passes through.
    The census compares, per key length L and verify width q, every verify row with the single-query decode call
    for its position, for the raw call (overlay off) and, where the overlay applies, for the overlay's call; then
    states what the SERVER AS SHIPPED does for each (L, q) (overlay MAX_Q 8, and 10 as in the copy-draft runs).

(b) GDN in_proj_ba (FP16, K = 5120, N = 2 * 48 / tp), qwen_gdn_linear_attn.py forward_xpu (:1055-1064): if the
    STEP has >= 17 tokens (_XPU_DETERMINISTIC_BA_MIN_TOKENS) -> _deterministic_xpu_ba_prefill (F.linear on zero-
    padded 256-row blocks), else in_proj_ba -> default_unquantized_gemm (layers/utils.py:246-253) ->
    xpu_fp16_linear_rowchunk (F.linear on <= VLLM_XPU_FP16_LINEAR_ROWCHUNK = 32 rows; class pad off).  A decode step
    is M = 1 (row-chunk path); a 6-row verify is M = 6; a 17-row verify (or a step mixing users) takes the padded
    path.  Per M the census compares each row with the same row computed alone, for the server's path choice and
    for each path on its own.
    CORRECTION 2026-10-04 (late): that Python branch is evaluated ONCE, when Dynamo traces the model at the warm-up
    size (4,096 tokens), and vLLM drops the guard (dynamic_shapes_config evaluate_guards=False, one compile range
    1-4096, splitting_ops=[] in both FP8 packages).  The compiled server therefore runs the padded 256-row path for
    EVERY step, a one-row decode included: the run caches' computation_graph.py hold 48 calls of
    torch.ops.vllm.qwen_gdn_ba_prefill_xpu and no row-chunk call for in_proj_ba (e.g. /mnt/fast-ai/bench-results/
    fp8-r314-mtp5-s4-20261004/tp2-pure-faseq-mtp5-s4/cache/torch_compile_cache/*/rank_0_0/backbone/).
    --ba-server-path compiled (the default) models that; --ba-server-path eager models the Python branch (only an
    --enforce-eager launch takes it).

Method, as in the other census scripts: deterministic per-case seeds (crc32 of the case key), comparison of bit
patterns (int16 views for fp16, int32 for fp32; NaN-safe max_abs), every call repeated to check determinism, one
`CENSUS ...` line per case, JSON to --out with summaries, a few tens of MB of device memory.

Run on one card (R313; R310 the same way):

  docker run --rm --network none --workdir /tmp --device /dev/dri:/dev/dri --group-add <render gid> \\
    --ipc=host --shm-size=2g --memory 10g --memory-swap 10g --entrypoint python3 \\
    --env-file /mnt/fast-ai/bench-results/fp8-census-r310-20261004/env.list \\
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 \\
    -v $PWD/experiments/qwen38-27b-b70/scripts:/work:ro \\
    -v $PWD/packages/qwen38-27b-fp8-tp2-b70/overlays:/overlay:ro -v <out>:/out \\
    neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r313-spec-exact \\
    /work/qwen38-fp8-verify-path-census.py --out /out/verify-path-census.json

Options: --tp 2,1 adds the one-card shapes; --page 896 the block size of launches with 10+ verify slots;
--skip-fa / --skip-ba; --schema-only (no GPU: imports the real entry points, prints op schemas and the routing
constants); --cpu-selftest (no GPU, no kernels: pure-PyTorch stand-ins, also drives the REAL overlay module through
fake vllm modules; must report all-equal, then must catch an injected one-ulp dependence on the row count).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
import types
import zlib
from pathlib import Path

import torch

L_LIST = [8, 17, 31, 64, 96, 128, 229, 230, 256, 384, 512, 768, 832, 833, 1024, 1280, 1536, 1537, 1645, 2048,
          3300, 6524]
Q_LIST = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 17]
M_LIST = list(range(1, 17)) + [17, 18, 24, 32, 33, 64, 128, 256, 257, 512]
Q_BOUNDS = (6, 10, 17)
SHIPPED_MAX_Q = (8, 10)
_HERE = Path(__file__).resolve()
OVERLAY_DIRS = ("/overlay",) + tuple(str(p / "packages/qwen38-27b-fp8-tp2-b70/overlays") for p in _HERE.parents[2:3])
I32 = torch.int32
DEV = torch.device("xpu:0")
DT = torch.float16


def sync():
    if DEV.type == "xpu":
        torch.xpu.synchronize()


def bits(t: torch.Tensor) -> torch.Tensor:
    t = t.detach().contiguous()
    return t.view(torch.int16) if t.element_size() == 2 else t.view(torch.int32)


def beq(a: torch.Tensor, b: torch.Tensor) -> bool:
    return a.shape == b.shape and bool(torch.equal(bits(a), bits(b)))


def max_abs(a: torch.Tensor, b: torch.Tensor) -> float:
    if a.numel() == 0 or a.shape != b.shape:
        return 0.0
    d = (a.float() - b.float()).abs()
    return float(torch.nan_to_num(d, nan=float("inf")).max().item())


def gen_for(*key) -> torch.Generator:
    return torch.Generator(device="cpu").manual_seed(zlib.crc32("/".join(map(str, key)).encode()))


def rand(shape, scale, g, dtype=None):
    return (torch.randn(shape, generator=g) * scale).to(dtype or DT).to(DEV).contiguous()


# ----------------------------------------------------------------------------------------------- shapes
class Shapes:
    """Per-rank shapes (config.json of /mnt/fast-ai/llm-models/qwen3.8-27b-fp8)."""

    def __init__(self, tp: int, page: int = 832, max_model_len: int = 33024, tiny: bool = False):
        self.tp = tp
        if tiny:   # CPU self-test only
            hq, hkv, self.hd, self.page, self.hidden, nv = 4, 2, 16, 16, 32, 4
            self.table_w = 8
        else:
            hq, hkv, self.hd, self.page, self.hidden, nv = 24, 4, 256, page, 5120, 48
            self.table_w = math.ceil(max_model_len / page)          # 40 at 832, 37 at 896
        self.hq, self.hkv = hq // tp, hkv // tp
        self.ba_w = 2 * nv // tp

    def as_dict(self):
        return dict(vars(self))


# ----------------------------------------------------------------------------------------------- split-K model
def predicted_splits(batch, hq, hkv, max_k, page, xe_cores):
    """Python mirror of flash_api.cpp get_num_splits (:11-94)."""
    if page == 16:
        kv_tile, sg_per_wg, cap = 16, 1, 16
    elif page == 32:
        kv_tile, sg_per_wg, cap = 32, 2, 32
    else:
        kv_tile, sg_per_wg, cap = 64, 4, 64
    tiles = -(-max_k // kv_tile)
    if tiles < 16:
        return 1
    slots = xe_cores * 4 // sg_per_wg
    wgs = batch * hkv
    if wgs >= slots and tiles < 64:
        return 1
    s = max(max(1, -(-4 * slots // wgs)), max(1, tiles // 12))
    s = min(s, max(2, 128 * xe_cores // max(1, batch * hq)))
    return max(1, min(s, max(1, tiles // 4), 32, cap))


def effective_splits(splits, seq_len, tile=64):
    """paged_decode_kernel.hpp:375-377: fewer than 32 key blocks -> one split, passed through unchanged."""
    return 1 if splits <= 1 or -(-seq_len // tile) < 32 else splits


# ----------------------------------------------------------------------------------------------- ops
def load_overlay(overlay_dir, max_q):
    """Import the package overlay and register it on the already imported flash_attn backend module.  The overlay
    reads its env at register(); MAX_Q is set wide so its path can be measured for every q; the shipped settings
    are applied in the summary."""
    for d in ([overlay_dir] if overlay_dir else list(OVERLAY_DIRS)):
        if d and (Path(d) / "b70_fa_verify_rows.py").is_file():
            sys.path.insert(0, d)
            break
    else:
        return None, "b70_fa_verify_rows.py not found (mount the package overlays at /overlay)"
    os.environ["B70_FA_VERIFY_ROWS"] = "1"
    os.environ["B70_FA_VERIFY_ROWS_MAX_Q"] = str(max_q)
    import b70_fa_verify_rows  # noqa: E402
    b70_fa_verify_rows.register()
    return b70_fa_verify_rows, None


class RealOps:
    name = "image"

    def __init__(self, overlay_dir, overlay_max_q):
        import vllm  # noqa: F401
        import vllm._xpu_ops  # noqa: F401
        import vllm_xpu_kernels._xpu_C  # noqa: F401
        import vllm_xpu_kernels.flash_attn_interface as fai
        from vllm.v1.attention.backends import flash_attn as fa
        from vllm.v1.attention.backends.fa_utils import get_flash_attn_version
        self.fai, self.fa_mod = fai, fa
        self.fa_version = get_flash_attn_version()
        self.raw = fa.flash_attn_varlen_func                     # = xpu_ops.flash_attn_varlen_func
        self.spec_max = int(getattr(fai, "_SPEC_DECODE_MAX_QLEN", 16))
        try:
            self.xe_cores = int(fai._infer_num_xe_cores(DEV))
        except Exception:  # noqa: BLE001
            self.xe_cores = None
        self.overlay_mod, self.overlay_error = load_overlay(overlay_dir, overlay_max_q)
        self.overlay_measured_max_q = overlay_max_q
        self.overlay = fa.flash_attn_varlen_func if fa.flash_attn_varlen_func is not self.raw else None
        if self.overlay is None and self.overlay_error is None:
            self.overlay_error = "register() did not wrap flash_attn_varlen_func"
        self.overlay_min_k = int(os.environ.get("B70_FA_VERIFY_ROWS_MIN_K", "1536"))
        self.ba_source = "vllm (qwen_gdn_linear_attn + layers.utils)"
        try:
            from vllm.model_executor.layers.mamba.gdn import qwen_gdn_linear_attn as g
            from vllm.model_executor.layers.utils import default_unquantized_gemm
            self.ba_padded, self.ba_min = g._deterministic_xpu_ba_prefill, int(g._XPU_DETERMINISTIC_BA_MIN_TOKENS)
            self.ba_rowchunk = lambda x, w: default_unquantized_gemm(None, x, w, None)
        except Exception as exc:  # noqa: BLE001  -- local mirror of the same code
            self.ba_source = f"local mirror ({exc!r})"[:200]
            self.ba_padded, self.ba_min, self.ba_rowchunk = mirror_ba_padded, 17, mirror_rowchunk

    def descale(self, sh, b):
        return torch.ones((), dtype=torch.float32, device=DEV).expand(b, sh.hkv)


def fa_kwargs(ops, sh, q, kc, vc, out, q_len, used, max_k, table):
    """The keyword arguments of flash_attn.py:1235-1259 for one request."""
    desc = ops.descale(sh, 1)
    return dict(q=q, k=kc, v=vc, out=out,
                cu_seqlens_q=torch.tensor([0, q_len], dtype=I32, device=DEV), max_seqlen_q=q_len,
                seqused_k=torch.tensor([used], dtype=I32, device=DEV), max_seqlen_k=int(max_k),
                softmax_scale=sh.hd ** -0.5, causal=True, alibi_slopes=None, window_size=None, block_table=table,
                softcap=0, scheduler_metadata=None, fa_version=ops.fa_version, q_descale=None, k_descale=desc,
                v_descale=desc, dynamic_causal=None, num_splits=0, s_aux=None, mask_mod=None, aux_tensors=None)


def mirror_ba_padded(x, w, pad=256):
    pieces = []
    for s in range(0, x.shape[0], pad):
        blk = torch.zeros((pad, x.shape[1]), dtype=x.dtype, device=x.device)
        n = min(pad, x.shape[0] - s)
        blk[:n].copy_(x[s:s + n])
        pieces.append(torch.nn.functional.linear(blk, w)[:n])
    return torch.cat(pieces)


def mirror_rowchunk(x, w):
    chunk = int(os.environ.get("VLLM_XPU_FP16_LINEAR_ROWCHUNK", "32"))
    if chunk <= 0 or x.shape[0] <= chunk:
        return torch.nn.functional.linear(x, w)
    return torch.cat([torch.nn.functional.linear(x[i:i + chunk], w) for i in range(0, x.shape[0], chunk)])


# ----------------------------------------------------------------------------------------------- CPU stand-ins
def _nudge(t, leak, row_count):
    """Injected dependence on the call's row count: one ulp in row 1 when the call has more than one row."""
    if leak and row_count > 1 and t.shape[0] > 1:
        flat = t[1].reshape(-1)
        flat[0] = torch.nextafter(flat[0], torch.tensor(float("inf"), dtype=flat.dtype))


def emul_fa_factory(sh, leak):
    """flash_attn_varlen_func stand-in: exact per-row causal attention (float64, cast at the end)."""
    rep = sh.hq // sh.hkv

    def fa(**kw):
        q, kc, vc, out, cu, used, table = (kw[x] for x in ("q", "k", "v", "out", "cu_seqlens_q", "seqused_k",
                                                            "block_table"))
        for i in range(used.shape[0]):
            r0, r1, n = int(cu[i]), int(cu[i + 1]), int(used[i])
            for r in range(r0, r1):
                m = n - (r1 - 1 - r)
                pos = torch.arange(m)
                k = kc[table[i, pos // sh.page].long(), pos % sh.page].double().repeat_interleave(rep, 1)
                v = vc[table[i, pos // sh.page].long(), pos % sh.page].double().repeat_interleave(rep, 1)
                s = torch.einsum("hd,khd->hk", q[r].double(), k) * kw["softmax_scale"]
                out[r] = torch.einsum("hk,khd->hd", s.softmax(-1), v).to(out.dtype)
        _nudge(out[int(cu[0]):int(cu[-1])], leak, kw["max_seqlen_q"])
        return out
    return fa


class EmulOps:
    name = "cpu-emulation"

    def __init__(self, sh, leak, overlay_dir):
        self.leak, self.spec_max, self.xe_cores, self.fa_version = leak, 16, 32, 2
        self.raw = emul_fa_factory(sh, leak)
        self.overlay_min_k = 20                   # tiny shapes: exercise the overlay from L = 21
        self.overlay_measured_max_q = max(Q_LIST)
        self.overlay_mod, self.overlay_error, self.overlay = None, None, None
        self.ba_min, self.ba_source = 17, "cpu stand-in"
        saved = {k: v for k, v in sys.modules.items() if k == "vllm" or k.startswith("vllm.")}
        fake = fake_vllm_modules(self.raw)
        sys.modules.update(fake)
        old_env = {k: os.environ.get(k) for k in ("B70_FA_VERIFY_ROWS", "B70_FA_VERIFY_ROWS_MAX_Q",
                                                  "B70_FA_VERIFY_ROWS_MIN_K")}
        os.environ["B70_FA_VERIFY_ROWS_MIN_K"] = str(self.overlay_min_k)
        try:
            sys.modules.pop("b70_fa_verify_rows", None)
            self.overlay_mod, self.overlay_error = load_overlay(overlay_dir, max(Q_LIST))
            fa = fake["vllm.v1.attention.backends.flash_attn"]
            self.overlay = fa.flash_attn_varlen_func if fa.flash_attn_varlen_func is not self.raw else None
        finally:
            for k in fake:
                sys.modules.pop(k, None)
            sys.modules.update(saved)
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def descale(self, sh, b):
        return torch.ones((), dtype=torch.float32, device=DEV).expand(b, sh.hkv)

    def ba_rowchunk(self, x, w):
        y = torch.stack([(x[i].double() @ w.double().T).to(x.dtype) for i in range(x.shape[0])])
        _nudge(y, self.leak, x.shape[0])
        return y

    def ba_padded(self, x, w):
        return torch.stack([(x[i].double() @ w.double().T).to(x.dtype) for i in range(x.shape[0])])


def fake_vllm_modules(fa_fn):
    import logging
    names = ["vllm", "vllm.logger", "vllm.v1", "vllm.v1.attention", "vllm.v1.attention.backends",
             "vllm.v1.attention.backends.flash_attn"]
    mods = {n: types.ModuleType(n) for n in names}
    mods["vllm.logger"].init_logger = logging.getLogger
    mods["vllm"].logger, mods["vllm"].v1 = mods["vllm.logger"], mods["vllm.v1"]
    mods["vllm.v1"].attention = mods["vllm.v1.attention"]
    mods["vllm.v1.attention"].backends = mods["vllm.v1.attention.backends"]
    mods["vllm.v1.attention.backends"].flash_attn = mods["vllm.v1.attention.backends.flash_attn"]
    mods["vllm.v1.attention.backends.flash_attn"].flash_attn_varlen_func = fa_fn
    return mods


# ----------------------------------------------------------------------------------------------- (a) attention
def fa_route(ops, q):
    return "splitk_decode" if 1 < q <= ops.spec_max else ("chunk_prefill" if q > 1 else "decode")


def overlay_applies(ops, L, q, max_q):
    return ops.overlay is not None and 2 <= q <= max_q and L > ops.overlay_min_k


def census_fa(sh, ops, seed, l_list, q_list, out_cb):
    max_l = max(l_list)
    pool = math.ceil(max_l / sh.page) + 4
    g = gen_for(seed, "fa-cache", sh.tp, sh.page)
    storage = rand((pool, sh.page, sh.hkv, 2 * sh.hd), 0.5, g)
    kc, vc = storage[..., :sh.hd], storage[..., sh.hd:]
    order = torch.randperm(pool, generator=gen_for(seed, "fa-pages", sh.tp)).tolist()
    table = torch.zeros((1, sh.table_w), dtype=I32)
    used_pages = min(pool, sh.table_w)
    table[0, :used_pages] = torch.tensor(order[:used_pages], dtype=I32)
    table = table.to(DEV)
    qmax = max(q_list)
    rows_out = []

    def call(fn, qrows, used, max_k):
        out = torch.zeros_like(qrows)
        fn(**fa_kwargs(ops, sh, qrows, kc, vc, out, qrows.shape[0], used, max_k, table))
        sync()
        return out

    for L in l_list:
        nq = min(L, qmax)
        qbank = rand((nq, sh.hq, sh.hd), 0.5, gen_for(seed, "fa-q", sh.tp, L))      # positions L - nq .. L - 1
        dec, dec_rep = {}, True
        for i in range(nq):
            p = L - nq + i
            a = call(ops.raw, qbank[i:i + 1], p + 1, p + 1)
            dec_rep &= beq(a, call(ops.raw, qbank[i:i + 1], p + 1, p + 1))
            dec[p] = a
        for q in q_list:
            t0 = time.perf_counter()
            e = {"tp": sh.tp, "L": L, "q": q}
            if q > L:
                e.update({"applicable": False})
                rows_out.append(e)
                continue
            try:
                qrows = qbank[nq - q:].contiguous()
                raw = call(ops.raw, qrows, L, L)
                raw_rep = beq(raw, call(ops.raw, qrows, L, L))
                diff = [r for r in range(q) if not beq(raw[r:r + 1], dec[L - q + r])]
                e.update({"applicable": True, "route": fa_route(ops, q), "raw_equal": not diff,
                          "raw_rows_differing": diff, "raw_first_row": diff[0] if diff else None,
                          "raw_max_abs": max((max_abs(raw[r:r + 1], dec[L - q + r]) for r in diff), default=0.0),
                          "raw_repeat_equal": raw_rep, "decode_repeat_equal": dec_rep})
                if ops.xe_cores and e["route"] == "splitk_decode":
                    sv = predicted_splits(q, sh.hq, sh.hkv, L, sh.page, ops.xe_cores)
                    sd = [predicted_splits(1, sh.hq, sh.hkv, L - (q - 1 - r), sh.page, ops.xe_cores) for r in range(q)]
                    e["predicted_splits_verify"], e["predicted_splits_decode_rows"] = sv, sd
                    e["predicted_equal"] = all(effective_splits(sv, L - (q - 1 - r)) ==
                                               effective_splits(sd[r], L - (q - 1 - r)) for r in range(q))
                if overlay_applies(ops, L, q, ops.overlay_measured_max_q):
                    ov = call(ops.overlay, qrows, L, L)
                    ov_rep = beq(ov, call(ops.overlay, qrows, L, L))
                    odiff = [r for r in range(q) if not beq(ov[r:r + 1], dec[L - q + r])]
                    e.update({"overlay_equal": not odiff, "overlay_first_row": odiff[0] if odiff else None,
                              "overlay_max_abs": max((max_abs(ov[r:r + 1], dec[L - q + r]) for r in odiff),
                                                     default=0.0),
                              "overlay_repeat_equal": ov_rep})
                for mq in SHIPPED_MAX_Q:
                    via = overlay_applies(ops, L, q, mq)
                    e[f"shipped_maxq{mq}_path"] = "overlay" if via else "raw"
                    e[f"shipped_maxq{mq}_equal"] = e["overlay_equal"] if via else e["raw_equal"]
                e["pass"] = e["raw_equal"] and e["raw_repeat_equal"] and dec_rep
            except Exception as exc:  # noqa: BLE001
                e.update({"applicable": True, "status": "unavailable", "error": repr(exc)[:400], "pass": None})
            e["seconds"] = round(time.perf_counter() - t0, 3)
            rows_out.append(e)
            if e.get("status") == "unavailable":
                print(f"CENSUS fa_verify tp={sh.tp} L={L} q={q} status=unavailable {e['error']}"[:300], flush=True)
            else:
                ovs = ("n/a" if "overlay_equal" not in e else
                       f"{e['overlay_equal']}(row={e['overlay_first_row']},rep={e['overlay_repeat_equal']})")
                pred = (f" pred_splits={e['predicted_splits_verify']}/{sorted(set(e['predicted_splits_decode_rows']))}"
                        f" pred_equal={e['predicted_equal']}" if "predicted_equal" in e else "")
                print(f"CENSUS fa_verify tp={sh.tp} page={sh.page} L={L} q={q} route={e['route']}"
                      f" raw_equal={e['raw_equal']} first_row={e['raw_first_row']} rows_differing={len(diff)}"
                      f" max_abs={e['raw_max_abs']:.3g} repeat={e['raw_repeat_equal']} decode_repeat={dec_rep}"
                      f" overlay={ovs} shipped8={e['shipped_maxq8_equal']} shipped10={e['shipped_maxq10_equal']}"
                      f"{pred}", flush=True)
        out_cb(rows_out)
    return rows_out


def largest_prefix_l(rows, l_list, ok):
    """Largest L such that ok(row) for every applicable row with L' <= L (None if the first L already fails)."""
    best = None
    for L in sorted(l_list):
        sel = [r for r in rows if r["L"] == L and r.get("applicable")]
        if not sel:
            continue
        if any(r.get("pass") is None for r in sel) or not all(ok(r) for r in sel):
            return best
        best = L
    return best


def summarize_fa(rows, l_list, q_list):
    done = [r for r in rows if r.get("applicable") and r.get("pass") is not None]
    s = {"cases": len([r for r in rows if r.get("applicable")]), "cases_run": len(done),
         "nondeterministic": [(r["L"], r["q"]) for r in done
                              if not (r["raw_repeat_equal"] and r["decode_repeat_equal"]
                                      and r.get("overlay_repeat_equal", True))],
         "raw_failing": [(r["L"], r["q"], r["raw_first_row"]) for r in done if not r["raw_equal"]],
         "overlay_failing": [(r["L"], r["q"], r["overlay_first_row"]) for r in done
                             if r.get("overlay_equal") is False],
         "prediction_mismatches": [(r["L"], r["q"]) for r in done
                                   if "predicted_equal" in r and r["predicted_equal"] != r["raw_equal"]]}
    for b in Q_BOUNDS:
        sel = [r for r in rows if r["q"] <= b]
        s[f"raw_largest_L_all_identical_q_le_{b}"] = largest_prefix_l(sel, l_list, lambda r: r["raw_equal"])
        for mq in SHIPPED_MAX_Q:
            s[f"shipped_maxq{mq}_largest_L_all_identical_q_le_{b}"] = largest_prefix_l(
                sel, l_list, lambda r, mq=mq: r[f"shipped_maxq{mq}_equal"])
    for mq in SHIPPED_MAX_Q:
        s[f"shipped_maxq{mq}_failing"] = [(r["L"], r["q"]) for r in done if not r[f"shipped_maxq{mq}_equal"]]
    s["per_q_largest_L_raw_identical"] = {q: largest_prefix_l([r for r in rows if r["q"] == q], l_list,
                                                              lambda r: r["raw_equal"]) for q in q_list}
    return s


# ----------------------------------------------------------------------------------------------- (b) in_proj_ba
BA_SERVER_PATH = "compiled"   # see the 2026-10-04 correction in the module docstring


def ba_server_padded(m, ba_min):
    """Does the server run the padded 256-row path for a step of m rows?  Compiled: always; eager: m >= 17."""
    return True if BA_SERVER_PATH == "compiled" else m >= ba_min


def census_ba(sh, ops, seed, m_list, out_cb):
    w = rand((sh.ba_w, sh.hidden), 0.02, gen_for(seed, "ba-w", sh.tp))
    x = rand((max(m_list), sh.hidden), 1.0, gen_for(seed, "ba-x", sh.tp))

    def server(xm):
        return ops.ba_padded(xm, w) if ba_server_padded(xm.shape[0], ops.ba_min) else ops.ba_rowchunk(xm, w)

    def run(fn, xm):
        y = fn(xm.contiguous())
        sync()
        return y

    alone = {p: [run(f, x[i:i + 1]) for i in range(max(m_list))]
             for p, f in (("rowchunk", lambda xm: ops.ba_rowchunk(xm, w)),
                          ("padded256", lambda xm: ops.ba_padded(xm, w)))}
    alone["server"] = alone["padded256"] if ba_server_padded(1, ops.ba_min) else alone["rowchunk"]
    rows = []
    for m in m_list:
        t0 = time.perf_counter()
        e = {"tp": sh.tp, "M": m, "server_path": "padded256" if ba_server_padded(m, ops.ba_min) else "rowchunk",
             "ba_server_model": BA_SERVER_PATH}
        try:
            for p, f in (("server", server), ("rowchunk", lambda xm: ops.ba_rowchunk(xm, w)),
                         ("padded256", lambda xm: ops.ba_padded(xm, w))):
                y = run(f, x[:m])
                rep = beq(y, run(f, x[:m]))
                diff = [i for i in range(m) if not beq(y[i:i + 1], alone[p][i])]
                e[p] = {"equal": not diff, "rows_differing": len(diff), "first_row": diff[0] if diff else None,
                        "max_abs": max((max_abs(y[i:i + 1], alone[p][i]) for i in diff), default=0.0),
                        "repeat_equal": rep}
                if p == "padded256":   # a padded-path row against the decode step's row (M = 1, row-chunk path)
                    d2 = [i for i in range(m) if not beq(y[i:i + 1], alone["server"][i])]
                    e["padded256_vs_decode_row"] = {"equal": not d2, "first_row": d2[0] if d2 else None,
                                                    "max_abs": max((max_abs(y[i:i + 1], alone["server"][i])
                                                                    for i in d2), default=0.0)}
            e["pass"] = e["server"]["equal"] and e["server"]["repeat_equal"]
        except Exception as exc:  # noqa: BLE001
            e.update({"status": "unavailable", "error": repr(exc)[:400], "pass": None})
        e["seconds"] = round(time.perf_counter() - t0, 3)
        rows.append(e)
        if e.get("status") == "unavailable":
            print(f"CENSUS ba_proj tp={sh.tp} M={m} status=unavailable {e['error']}"[:300], flush=True)
        else:
            sv = e["server"]
            print(f"CENSUS ba_proj tp={sh.tp} M={m} path={e['server_path']} equal_to_alone={sv['equal']}"
                  f" first_row={sv['first_row']} rows_differing={sv['rows_differing']} max_abs={sv['max_abs']:.3g}"
                  f" repeat={sv['repeat_equal']} rowchunk_path={e['rowchunk']['equal']}"
                  f" padded_path={e['padded256']['equal']}"
                  f" padded_vs_decode_row={e['padded256_vs_decode_row']['equal']}", flush=True)
        out_cb(rows)
    return rows


def summarize_ba(rows, m_list):
    done = [r for r in rows if r.get("pass") is not None]

    def largest(key):
        best = None
        for m in sorted(m_list):
            r = next((x for x in done if x["M"] == m), None)
            if r is None or not r[key]["equal"]:
                return best
            best = m
        return best

    s = {"cases": len(rows), "cases_run": len(done),
         "largest_M_all_rows_identical_server": largest("server"),
         "largest_M_all_rows_identical_rowchunk_path": largest("rowchunk"),
         "largest_M_all_rows_identical_padded256_path": largest("padded256"),
         "largest_M_padded256_rows_equal_decode_row": largest("padded256_vs_decode_row"),
         "failing_M_server": [r["M"] for r in done if not r["server"]["equal"]],
         "failing_M_rowchunk_path": [r["M"] for r in done if not r["rowchunk"]["equal"]],
         "failing_M_padded256_path": [r["M"] for r in done if not r["padded256"]["equal"]],
         "nondeterministic_M": [r["M"] for r in done
                                if not all(r[p]["repeat_equal"] for p in ("server", "rowchunk", "padded256"))]}
    for b in (6, 10, 16, 17):
        sel = [r for r in done if r["M"] <= b]
        s[f"server_all_identical_M_le_{b}"] = bool(sel) and all(r["server"]["equal"] for r in sel)
    return s


# ----------------------------------------------------------------------------------------------- main
def environment(ops):
    env = {k: os.environ.get(k) for k in ("VLLM_XPU_SPEC_DECODE_MAX_QLEN", "VLLM_XPU_FA_SERIAL_SPEC_DECODE",
                                          "B70_FA_VERIFY_ROWS", "B70_FA_VERIFY_ROWS_MAX_Q",
                                          "B70_FA_VERIFY_ROWS_MIN_K", "VLLM_XPU_FP16_LINEAR_ROWCHUNK",
                                          "VLLM_XPU_FP16_LINEAR_CLASSPAD", "VLLM_BATCH_INVARIANT")}
    out = {"torch": torch.__version__, "python": platform.python_version(), "ops": ops.name,
           "fa_version": ops.fa_version, "spec_decode_max_qlen": ops.spec_max, "xe_cores": ops.xe_cores,
           "overlay_loaded": ops.overlay is not None, "overlay_error": ops.overlay_error,
           "overlay_min_k": ops.overlay_min_k, "overlay_measured_max_q": ops.overlay_measured_max_q,
           "shipped_max_q_settings": list(SHIPPED_MAX_Q), "ba_min_tokens": ops.ba_min, "ba_source": ops.ba_source,
           "ba_server_path": BA_SERVER_PATH,
           "env": env}
    if DEV.type == "xpu":
        out["device"] = torch.xpu.get_device_properties(0).name
        try:
            out["varlen_fwd_schema"] = str(torch.ops._vllm_fa2_C.varlen_fwd.default._schema)
        except Exception as exc:  # noqa: BLE001
            out["varlen_fwd_schema"] = repr(exc)[:200]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="verify-path census: verify rows vs one-token decode")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--tp", default="2", help="per-rank shapes, e.g. 2 or 2,1")
    ap.add_argument("--page", type=int, default=832, help="attention block size (896 from 10 verify slots)")
    ap.add_argument("--max-model-len", type=int, default=33024)
    ap.add_argument("--overlay-dir", default="", help="directory holding b70_fa_verify_rows.py (default /overlay)")
    ap.add_argument("--lens", default="", help="override the key lengths, e.g. 64,2048")
    ap.add_argument("--qs", default="", help="override the verify widths, e.g. 6,10")
    ap.add_argument("--skip-fa", action="store_true")
    ap.add_argument("--skip-ba", action="store_true")
    ap.add_argument("--ba-server-path", choices=("compiled", "eager"), default="compiled",
                    help="which in_proj_ba path the server takes: compiled = padded for every step (the FP8 packages)")
    ap.add_argument("--schema-only", action="store_true", help="no GPU: import entry points, print schemas")
    ap.add_argument("--cpu-selftest", action="store_true", help="bookkeeping check on CPU with stand-in ops")
    a = ap.parse_args()
    global BA_SERVER_PATH
    BA_SERVER_PATH = a.ba_server_path
    l_list = [int(x) for x in a.lens.split(",") if x] or L_LIST
    q_list = [int(x) for x in a.qs.split(",") if x] or Q_LIST
    if a.cpu_selftest:
        return selftest(a)
    if a.schema_only:
        return schema_only(a)
    if not torch.xpu.is_available():
        raise SystemExit("XPU is required (or use --cpu-selftest / --schema-only)")
    ops = RealOps(a.overlay_dir, max(q_list))
    report = {"schema": "neural.download.qwen38-fp8-verify-path-census.v1",
              "classification": "operator-diagnostic-only", "environment": environment(ops),
              "lists": {"L": l_list, "q": q_list, "M": M_LIST}, "by_kernel": {}}
    a.out.parent.mkdir(parents=True, exist_ok=True)

    def save():
        a.out.write_text(json.dumps(report, indent=1))

    for tp in [int(x) for x in a.tp.split(",") if x]:
        sh = Shapes(tp, a.page, a.max_model_len)
        if not a.skip_fa:
            sec = report["by_kernel"].setdefault("fa_verify", {}).setdefault(f"tp{tp}", {"shapes": sh.as_dict()})
            t0 = time.perf_counter()
            rows = census_fa(sh, ops, a.seed, l_list, q_list, lambda r, sec=sec: (sec.update(cases=r), save()))
            sec.update(cases=rows, summary=summarize_fa(rows, l_list, q_list),
                       seconds=round(time.perf_counter() - t0, 1))
            save()
            torch.xpu.empty_cache()
        if not a.skip_ba:
            sec = report["by_kernel"].setdefault("ba_proj", {}).setdefault(f"tp{tp}", {"shapes": sh.as_dict()})
            t0 = time.perf_counter()
            rows = census_ba(sh, ops, a.seed, M_LIST, lambda r, sec=sec: (sec.update(cases=r), save()))
            sec.update(cases=rows, summary=summarize_ba(rows, M_LIST), seconds=round(time.perf_counter() - t0, 1))
            save()
            torch.xpu.empty_cache()
    report["summary"] = {f"{k} {t}": v["summary"] for k, d in report["by_kernel"].items() for t, v in d.items()}
    save()
    print(json.dumps(report["summary"], indent=1, default=str))
    return 0


def schema_only(a) -> int:
    """No device work: the entry points the census uses exist, with the expected signatures and constants."""
    import inspect
    global DEV
    DEV = torch.device("cpu")
    info = {}
    if not torch.xpu.is_available():
        # No card in this container: let vLLM resolve the XPU platform anyway (platforms/__init__.py:158) so the
        # same modules are wired as in the server.  Imports only; nothing is launched.
        torch.xpu.is_available = lambda: True
        info["xpu_platform_forced"] = True
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels.flash_attn_interface as fai
    from vllm.v1.attention.backends import flash_attn as fa
    info["fa_backend_fn"] = f"{fa.flash_attn_varlen_func.__module__}.{fa.flash_attn_varlen_func.__qualname__}"
    info["fa_backend_params"] = list(inspect.signature(fa.flash_attn_varlen_func).parameters)
    info["kernel_interface_params"] = list(inspect.signature(fai.flash_attn_varlen_func).parameters)
    info["spec_decode_max_qlen"] = getattr(fai, "_SPEC_DECODE_MAX_QLEN", None)
    info["has_spec_decode_fastpath"] = hasattr(fai, "_spec_decode_varlen_fwd")
    try:
        import vllm_xpu_kernels._vllm_fa2_C  # noqa: F401
        info["varlen_fwd_schema"] = str(torch.ops._vllm_fa2_C.varlen_fwd.default._schema)
    except Exception as exc:  # noqa: BLE001
        info["varlen_fwd_schema"] = repr(exc)[:300]
    from vllm.model_executor.layers.mamba.gdn import qwen_gdn_linear_attn as g
    from vllm.model_executor.layers import utils as lu
    info["ba_min_tokens"] = g._XPU_DETERMINISTIC_BA_MIN_TOKENS
    info["ba_pad_tokens"] = g._XPU_DETERMINISTIC_BA_PAD_TOKENS
    info["fp16_rowchunk"] = getattr(lu, "_R224_CHUNK", None)
    info["fp16_classpad"] = getattr(lu, "_R290_CLASSPAD", None)
    info["rowchunk_op_registered"] = hasattr(torch.ops.vllm, "xpu_fp16_linear_rowchunk")
    mod, err = load_overlay(a.overlay_dir, max(Q_LIST))
    info["overlay"] = err or ("wrapped" if fa.flash_attn_varlen_func is not getattr(
        sys.modules.get("vllm._xpu_ops"), "xpu_ops").flash_attn_varlen_func else "not wrapped")
    print(json.dumps(info, indent=1, default=str))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"schema_only": info}, indent=1, default=str))
    ok = info["has_spec_decode_fastpath"] and info["fa_backend_params"] and info["overlay"] == "wrapped"
    return 0 if ok else 1


def selftest(a) -> int:
    """CPU, float32, tiny shapes, stand-in ops (the real overlay module is driven through fake vllm modules):
    the census must call everything identical, then must catch a one-ulp dependence on the call's row count."""
    global DEV, DT, BA_SERVER_PATH
    DEV, DT = torch.device("cpu"), torch.float32
    BA_SERVER_PATH = "eager"      # the injected leak below lives in the row-chunk path, which only eager reaches
    l_list, q_list, m_list = [8, 17, 21, 40], [2, 3, 6, 9, 17], [1, 2, 6, 16, 17, 18, 33]
    result = {}
    for leak in (False, True):
        for tp in (2, 1):
            sh = Shapes(tp, tiny=True)
            ops = EmulOps(sh, leak, a.overlay_dir)
            fa_rows = census_fa(sh, ops, a.seed, l_list, q_list, lambda r: None)
            fs = summarize_fa(fa_rows, l_list, q_list)
            ba_rows = census_ba(sh, ops, a.seed, m_list, lambda r: None)
            bs = summarize_ba(ba_rows, m_list)
            result[f"leak={leak} tp{tp}"] = {
                "overlay_loaded": ops.overlay is not None, "overlay_error": ops.overlay_error,
                "fa_raw_failing": len(fs["raw_failing"]), "fa_overlay_failing": len(fs["overlay_failing"]),
                "fa_overlay_cases": sum(1 for r in fa_rows if "overlay_equal" in r),
                "fa_shipped8_failing": len(fs["shipped_maxq8_failing"]),
                "fa_nondeterministic": len(fs["nondeterministic"]),
                "fa_raw_largest_L_q_le_6": fs["raw_largest_L_all_identical_q_le_6"],
                "ba_failing_server": bs["failing_M_server"], "ba_largest_M": bs["largest_M_all_rows_identical_server"]}
    print(json.dumps(result, indent=1))
    clean = [v for k, v in result.items() if "leak=False" in k]
    dirty = [v for k, v in result.items() if "leak=True" in k]
    ok = all(v["overlay_loaded"] and v["fa_overlay_cases"] > 0 and v["fa_raw_failing"] == 0
             and v["fa_overlay_failing"] == 0 and v["fa_nondeterministic"] == 0 and not v["ba_failing_server"]
             and v["fa_raw_largest_L_q_le_6"] == max(l_list) and v["ba_largest_M"] == max(m_list) for v in clean)
    # injected: every raw verify call (q >= 2) differs in row 1; overlay rows are one-query calls and stay equal;
    # BA row-chunk calls with M >= 2 differ, the padded path (M >= 17) does not.
    caught = all(v["fa_raw_failing"] > 0 and v["fa_overlay_failing"] == 0 and v["fa_raw_largest_L_q_le_6"] is None
                 and v["ba_failing_server"] == [2, 6, 16] and v["ba_largest_M"] == 1 for v in dirty)
    print(f"SELFTEST clean_all_equal={ok} injected_leak_detected={caught}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"selftest": result, "clean_all_equal": ok, "leak_detected": caught}, indent=1))
    return 0 if ok and caught else 1


if __name__ == "__main__":
    raise SystemExit(main())
