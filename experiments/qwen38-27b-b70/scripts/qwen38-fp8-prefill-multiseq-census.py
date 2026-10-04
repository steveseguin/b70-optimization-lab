#!/usr/bin/env python3
"""Multi-sequence prefill census (2026-10-04, R310 image).

Operator diagnostic only; never a speed or quality claim.

Question: when ONE prompt-only step reads several NEW prompts together (each prompt whole, as a single chunk,
no prior state -- what B70_EXCLUSIVE_PREFILL_BATCH>1 in overlays/b70-exclusive-prefill does), does every
prefill kernel give each sequence the same bits, outputs AND the state it leaves behind, as when that
sequence is prefilled alone?  Screen of 2026-10-04: 64/64 identical with ~31-token prompts, 1/64 different
with two prompts of 1,645 and 2,434 tokens in one step.

How the R310 server makes these calls (site-packages, read 2026-10-04; prefix caching is off, cudagraph mode
NONE on the two-card lane, attention page 832 tokens, step budget 4,096 tokens):

 (a) Full-attention layers, vllm/v1/attention/backends/flash_attn.py.
     * KV write first, per token: reshape_and_cache_flash(key, value, key_cache, value_cache, slot_mapping,
       "auto", _k_scale, _v_scale) (:1317) -> torch.ops._C_cache_ops.reshape_and_cache_flash.  The cache is one
       [blocks, 832, kv_heads, 2*256] fp16 buffer; key = [..., :256], value = [..., 256:] (:1009, :1305).
     * ONE attention call for the whole step (:1235): flash_attn_varlen_func(q[:T], key_cache, value_cache,
       cu_seqlens_q=query_start_loc, max_seqlen_q=max L, seqused_k=seq_lens, max_seqlen_k=max L,
       causal=True, window_size=[-1,-1], block_table=[B, 40] int32, softcap=0, scheduler_metadata=None,
       fa_version=2, q_descale=None, k/v_descale=_k_scale.expand(B, kv_heads), num_splits=0).  No cascade
       (prefix caching off; it would also need >= 8 requests sharing >= 256 tokens).  The b70_fa_verify_rows
       overlay (B70_FA_VERIFY_ROWS=1) only rewrites ONE-request calls of 2..8 query rows with max_seqlen_k >
       1536, never a fresh prompt; VLLM_XPU_FA_SERIAL_SPEC_DECODE=0 (shipped) leaves the call alone.
     * vllm/_xpu_ops.py:1062 drops num_splits/scheduler_metadata and calls vllm_xpu_kernels
       flash_attn_interface.flash_attn_varlen_func (:403).  ROUTING THAT DEPENDS ON THE OTHER SEQUENCES (:511):
       if every sequence in the call has the same query length q and 1 < q <= VLLM_XPU_SPEC_DECODE_MAX_QLEN
       (default 16, not set in the lane env) the call goes to the split-K DECODE kernel (one pseudo-sequence per
       token); otherwise to _vllm_fa2_C.varlen_fwd with mix_batch=True -> chunk-prefill kernel (+ paged-decode
       kernel for 1-token sequences), csrc/flash_attn/flash_api.cpp:208-330.  So a 9-token prompt alone takes
       the decode kernel, the same prompt next to a 31-token prompt takes the chunk-prefill kernel.
 (b) GDN layers, vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py forward_xpu (:1040).
     * in_proj_ba (fp16, not FP8-quantised in this checkpoint): if the STEP has >= 17 tokens
       (_XPU_DETERMINISTIC_BA_MIN_TOKENS, :79) it runs _deterministic_xpu_ba_prefill (:83: F.linear on fixed
       256-row blocks of the whole step, zero-padded), else default_unquantized_gemm (layers/utils.py:246:
       VLLM_XPU_FP16_LINEAR_ROWCHUNK=32 row chunks).  The path and the 256-row block a row lands in depend on
       the other sequences.  Censused here as `gdn_ba_proj`.
     * gdn_attention_core_xpu -> vllm/_xpu_ops.py _gdn_attention_core_xpu_impl (:118).  A pure prompt step has
       num_spec_decodes=0, num_decodes=0, so neither VLLM_XPU_GDN_SPEC_GROUP nor VLLM_XPU_GDN_SPLIT_MIXED=1
       (:198, only steps that MIX prefill with decode/spec rows) applies: ONE torch.ops._xpu_C.gdn_attention call
       (:288) with num_prefills=B, has_initial_state=zeros(B) bool, non_spec_query_start_loc=query_start_loc
       int32, non_spec_token_indx=None, non_spec_state_indices_tensor=block_table[:, 0] int32, spec_*=None,
       num_accepted_tokens=None, num_actual_tokens=T, conv_bias=None, reorder_input=True
       (metadata: vllm/v1/attention/backends/gdn_attn.py:250-290).  The env switches VLLM_XPU_GDN_PREFILL_GROUP,
       VLLM_XPU_GDN_NATIVE_FALLBACK, VLLM_XPU_GDN_ISOLATE_*_PREFILL_REQUESTS, VLLM_XPU_GDN_ROW_STABLE_RMSNORM and
       VLLM_XPU_GDN_DETERMINISTIC_QKVZ_PREFILL are read nowhere in the R310 image (grep of /opt and /workspace).
     * Kernel (csrc/xpu/gdn_attn/gdn_attn_interface.cpp:430): conv1d+SiLU+l2norm into a "virtual" token layout
       where each sequence is padded to 64-token chunks (chunk_size_xe2=64); TILED conv kernel when the STEP
       has >= 8 tokens (conv1d_tile_size), untiled below; then chunk_gated_delta_rule_xe2 (prepare / A /
       inverse / WU / fwd-O kernels), chunk work distributed over all sub-groups across all sequences, fwd-O
       one work-group per (sequence, value head).  Conv state: last 3 input rows written to rows 0..2 of the
       sequence's [8, conv_dim] slot (3 + 5 spec rows, SD layout); SSM state [lv, 128, 128] fp16 per slot.
 (c) Everything else in a prefill step is per token or per row: mRoPE (positions per token), q/k head RMSNorm
     and the GDN gated RMSNorm (normalisation census), the FP8 body GEMMs (row-invariant, GEMM census), the
     attention output gate (elementwise).  Not repeated here.

What each case checks, per kernel, with deterministic random data of the real per-rank shapes:
  every sequence's output rows (FA: attention out; GDN: core out and z; BA: projection rows) and the state the
  call leaves for it (FA: its K/V tokens in the pages; GDN: its conv slot (all 8 rows) and SSM slot), bit for
  bit (int16/int32 views, NaN-safe) against the same sequence prefilled alone; the batch with the order
  permuted (and different page/slot placement); a repeat of the identical call.  Solo and batch use different
  physical pages / state slots; the stale content of pages/slots is the same pattern in both, and a separate
  control (`controls`) checks that a different stale pattern does not change a solo result.

Run on R310 (one card):

  docker run --rm --network none --workdir /tmp --device /dev/dri:/dev/dri \
    --group-add <render gid> --ipc=host --shm-size=2g --memory 10g --memory-swap 10g \
    --entrypoint python3 \
    --env-file /mnt/fast-ai/bench-results/fp8-census-r310-20261004/env.list \
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    -v $PWD/experiments/qwen38-27b-b70/scripts:/work:ro -v <out>:/out \
    sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04 \
    /work/qwen38-fp8-prefill-multiseq-census.py --out /out/prefill-multiseq-census.json

Quick first pass: add --only-short (lengths <= 256).  --tp 2,1 adds the one-card shapes.  --cpu-selftest runs the
bookkeeping against pure-PyTorch stand-ins on CPU (no GPU, no kernels) and must report all-equal, then
checks that an injected cross-sequence dependence is detected.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import time
import zlib
from pathlib import Path

import torch

I32 = torch.int32
STEP_BUDGET = 4096                       # --max-num-batched-tokens
EQUAL_LENS = [8, 16, 31, 32, 33, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1645, 2048, 2434]
SHORT_MAX = 256
BATCHES = [2, 3, 4, 8]
SHORT_EXTRA_BATCH = 16                   # only for L <= SHORT_MAX
MIXED_SETS = [(31, 17, 64, 40, 25, 52, 31, 9), (128, 200, 96, 250), (512, 300, 700), (1645, 2434), (2048, 2048)]
# Added: every prompt <= 16 tokens but unequal -> alone each takes the FA split-K decode route, together the
# chunk-prefill route (see (a)).
EXTRA_MIXED_SETS = [(16, 9, 12)]

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

    def __init__(self, tp: int, tiny: bool = False):
        self.tp = tp
        if tiny:   # CPU self-test only
            hq, hkv, self.hd, self.page, self.table_w = 4, 2, 16, 16, 8
            self.nk, self.nv, self.dk, self.dv, self.hidden = 2, 4, 8, 8, 32
        else:
            hq, hkv, self.hd, self.page, self.table_w = 24, 4, 256, 832, 40   # 40 = ceil(33024 / 832)
            self.nk, self.nv, self.dk, self.dv, self.hidden = 16, 48, 128, 128, 5120
        self.width, self.spec = 4, 5
        self.hq, self.hkv = hq // tp, hkv // tp
        self.lk, self.lv = self.nk // tp, self.nv // tp
        self.qkvz_w = self.lk * (2 * self.dk + 2 * self.dv * self.nv // self.nk)
        self.conv_dim = self.lk * (2 * self.dk + self.dv * self.nv // self.nk)
        self.ba_w = 2 * self.lv
        self.conv_rows = self.width - 1 + self.spec          # SD layout, MTP depth 5

    def as_dict(self):
        return {k: v for k, v in vars(self).items()}


# ----------------------------------------------------------------------------------------------- ops
class RealOps:
    """The R310 entry points the server uses."""
    name = "r310"

    def __init__(self):
        import vllm  # noqa: F401
        import vllm._xpu_ops  # noqa: F401
        import vllm_xpu_kernels._xpu_C  # noqa: F401
        from vllm import _custom_ops as ops
        from vllm.v1.attention.backends.fa_utils import flash_attn_varlen_func, get_flash_attn_version
        import vllm_xpu_kernels.flash_attn_interface as fai
        self.fa_fn, self.fa_version = flash_attn_varlen_func, get_flash_attn_version()
        self.cache_fn = ops.reshape_and_cache_flash
        self.spec_max = int(getattr(fai, "_SPEC_DECODE_MAX_QLEN", 16))
        self.ba_source = "vllm (qwen_gdn_linear_attn + layers.utils)"
        try:
            from vllm.model_executor.layers.mamba.gdn import qwen_gdn_linear_attn as g
            from vllm.model_executor.layers.utils import default_unquantized_gemm
            self._ba_big, self.ba_min = g._deterministic_xpu_ba_prefill, int(g._XPU_DETERMINISTIC_BA_MIN_TOKENS)
            self._ba_small = lambda x, w: default_unquantized_gemm(None, x, w, None)
        except Exception as exc:  # noqa: BLE001  -- local mirror of the same code
            self.ba_source = f"local mirror ({exc!r})"[:200]
            self._ba_big, self.ba_min = mirror_ba_padded, 17
            self._ba_small = mirror_rowchunk

    def cache_write(self, key, value, kc, vc, slot_mapping):
        one = torch.ones((), dtype=torch.float32, device=DEV)
        self.cache_fn(key, value, kc, vc, slot_mapping, "auto", one, one)

    def fa(self, sh, q, kc, vc, out, cu, max_q, used, max_k, table):
        desc = torch.ones((), dtype=torch.float32, device=DEV).expand(used.shape[0], sh.hkv)
        self.fa_fn(q=q, k=kc, v=vc, out=out, cu_seqlens_q=cu, max_seqlen_q=max_q, seqused_k=used,
                   max_seqlen_k=max_k, softmax_scale=sh.hd ** -0.5, causal=True, alibi_slopes=None,
                   window_size=[-1, -1], block_table=table, softcap=0, scheduler_metadata=None,
                   fa_version=self.fa_version, q_descale=None, k_descale=desc, v_descale=desc,
                   dynamic_causal=None, num_splits=0, s_aux=None, mask_mod=None, aux_tensors=None)

    def gdn(self, sh, prm, out, z, qkvz, ba, conv, ssm, cu, slots, total):
        b = slots.shape[0]
        torch.ops._xpu_C.gdn_attention(
            out, z, qkvz, ba, sh.nk, sh.nv, sh.dk, sh.dv,
            conv_state=conv, ssm_state=ssm, conv_weights=prm["cw"], conv_bias=None, activation="silu",
            A_log=prm["a_log"], dt_bias=prm["dt_bias"], num_prefills=b, num_decodes=0, num_spec_decodes=0,
            has_initial_state=torch.zeros(b, dtype=torch.bool, device=DEV), non_spec_query_start_loc=cu,
            non_spec_token_indx=None, non_spec_state_indices_tensor=slots, spec_query_start_loc=None,
            spec_token_indx=None, spec_state_indices_tensor=None, num_accepted_tokens=None,
            num_actual_tokens=total, tp_size=sh.tp, reorder_input=True)

    def ba(self, x, w):
        return self._ba_big(x, w) if x.shape[0] >= self.ba_min else self._ba_small(x, w)


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


class EmulOps:
    """Pure-PyTorch stand-ins with the same bookkeeping (CPU self-test).  `leak` injects a dependence on the
    step's total token count so the census must flag it."""
    name = "cpu-emulation"

    def __init__(self, leak: bool = False):
        self.leak, self.spec_max, self.ba_min, self.ba_source = leak, 16, 17, "local mirror"

    def cache_write(self, key, value, kc, vc, slot_mapping):
        page = kc.shape[1]
        blk, off = slot_mapping // page, slot_mapping % page
        kc[blk, off] = key
        vc[blk, off] = value

    def fa(self, sh, q, kc, vc, out, cu, max_q, used, max_k, table):
        rep = sh.hq // sh.hkv
        for i in range(used.shape[0]):
            r0, r1, n = int(cu[i]), int(cu[i + 1]), int(used[i])
            pos = torch.arange(n)
            k = kc[table[i, pos // sh.page].long(), pos % sh.page].float().repeat_interleave(rep, 1)
            v = vc[table[i, pos // sh.page].long(), pos % sh.page].float().repeat_interleave(rep, 1)
            s = torch.einsum("qhd,khd->hqk", q[r0:r1].float(), k) * sh.hd ** -0.5
            s = s.masked_fill(torch.ones(r1 - r0, n, dtype=torch.bool).triu(n - (r1 - r0) + 1), float("-inf"))
            o = torch.einsum("hqk,khd->qhd", s.softmax(-1), v)
            if self.leak:
                o = o + 1e-3 * max_q
            out[r0:r1] = o.to(out.dtype)

    def gdn(self, sh, prm, out, z, qkvz, ba, conv, ssm, cu, slots, total):
        nv = sh.lv * sh.dv
        for i in range(slots.shape[0]):
            r0, r1, s = int(cu[i]), int(cu[i + 1]), int(slots[i])
            x = qkvz[r0:r1].float()
            o = x[:, :nv].cumsum(0) * prm["cw"].float().mean() + ba[r0:r1].float().sum(1, keepdim=True)
            if self.leak:
                o = o + 1e-3 * total
            out[r0:r1] = o.view(-1, sh.lv, sh.dv).to(out.dtype)
            z[r0:r1] = x[:, -nv:].view(-1, sh.lv, sh.dv).to(z.dtype)
            tail = x[max(0, r1 - r0 - (sh.width - 1)):, :sh.conv_dim]
            conv[s, :sh.width - 1] = 0
            conv[s, sh.width - 1 - tail.shape[0]:sh.width - 1] = tail.to(conv.dtype)
            ssm[s] = o[-1].view(sh.lv, sh.dv, 1).expand(sh.lv, sh.dv, sh.dk).to(ssm.dtype)

    def ba(self, x, w):
        return mirror_ba_padded(x, w) if x.shape[0] >= self.ba_min else mirror_rowchunk(x, w)


# ----------------------------------------------------------------------------------------------- kernels
class Kernel:
    """One kernel under census: data per sequence, one call for a list of sequences, per-sequence results."""
    name = ""
    parts: tuple = ()

    def __init__(self, sh, ops, seed, n_pool):
        self.sh, self.ops, self.seed = sh, ops, seed

    def data(self, L, idx):
        raise NotImplementedError

    def run(self, items, place, stale=0):
        raise NotImplementedError

    def paths(self, lens):
        return {}


class FaPrefill(Kernel):
    name = "fa_prefill"
    parts = ("out", "k_pages", "v_pages")

    def __init__(self, sh, ops, seed, n_pool):
        super().__init__(sh, ops, seed, n_pool)
        self.n_pool = n_pool
        self.storage = torch.empty((n_pool, sh.page, sh.hkv, 2 * sh.hd), dtype=DT, device=DEV)
        self.kc, self.vc = self.storage[..., :sh.hd], self.storage[..., sh.hd:]
        self.stale = [rand((sh.page, sh.hkv, 2 * sh.hd), 1.0, gen_for(seed, "fa-stale", s)) for s in (0, 1)]

    def data(self, L, idx):
        g, sh = gen_for(self.seed, self.name, self.sh.tp, L, idx), self.sh
        return {"L": L, "q": rand((L, sh.hq, sh.hd), 0.5, g), "k": rand((L, sh.hkv, sh.hd), 0.5, g),
                "v": rand((L, sh.hkv, sh.hd), 0.5, g)}

    def run(self, items, place, stale=0):
        sh = self.sh
        self.storage.copy_(self.stale[stale].unsqueeze(0).expand_as(self.storage))
        lens = [it["L"] for it in items]
        need = [math.ceil(L / sh.page) for L in lens]
        assert sum(need) <= self.n_pool and max(need) <= sh.table_w
        order = torch.randperm(self.n_pool, generator=gen_for(self.seed, "pages", place)).tolist()
        table = torch.zeros((len(items), sh.table_w), dtype=I32)
        slots, used = [], 0
        for i, (L, n) in enumerate(zip(lens, need)):
            table[i, :n] = torch.tensor(order[used:used + n], dtype=I32)
            used += n
            pos = torch.arange(L)
            slots.append(table[i, pos // sh.page].long() * sh.page + pos % sh.page)
        cu = torch.tensor([0] + list(_cumsum(lens)), dtype=I32, device=DEV)
        slot_mapping = torch.cat(slots).to(DEV)
        q = torch.cat([it["q"] for it in items])
        out = torch.zeros_like(q)
        self.ops.cache_write(torch.cat([it["k"] for it in items]), torch.cat([it["v"] for it in items]),
                             self.kc, self.vc, slot_mapping)
        self.ops.fa(sh, q, self.kc, self.vc, out, cu, max(lens),
                    torch.tensor(lens, dtype=I32, device=DEV), max(lens), table.to(DEV))
        sync()
        res, r0 = [], 0
        for L, sl in zip(lens, slots):
            blk, off = (sl // sh.page).to(DEV), (sl % sh.page).to(DEV)
            res.append({"out": out[r0:r0 + L].clone(), "k_pages": self.kc[blk, off].clone(),
                        "v_pages": self.vc[blk, off].clone()})
            r0 += L
        return res

    def route(self, lens):
        uniform = len(set(lens)) == 1
        if uniform and 1 < lens[0] <= self.ops.spec_max:
            return "splitk_decode_fastpath"
        return "chunk_prefill" if max(lens) > 1 else "paged_decode"

    def paths(self, lens):
        return {"batch": self.route(lens), "solo": sorted({self.route([L]) for L in lens})}


class GdnPrefill(Kernel):
    name = "gdn_prefill"
    parts = ("out", "z", "conv_slot", "ssm_slot")

    def __init__(self, sh, ops, seed, n_pool):
        super().__init__(sh, ops, seed, n_pool)
        self.n_pool = n_pool
        g = gen_for(seed, "gdn-params", sh.tp)
        self.prm = {"cw": rand((sh.conv_dim, sh.width), 0.2, g),          # conv1d.weight.view(C, W), no bias
                    "a_log": rand((sh.lv,), 1.0, g, torch.float32),
                    "dt_bias": rand((sh.lv,), 1.0, g)}
        self.conv = torch.empty((n_pool, sh.conv_rows, sh.conv_dim), dtype=DT, device=DEV)
        self.ssm = torch.empty((n_pool, sh.lv, sh.dv, sh.dk), dtype=DT, device=DEV)
        self.stale = [(rand((sh.conv_rows, sh.conv_dim), 1.0, gen_for(seed, "conv-stale", s)),
                       rand((sh.lv, sh.dv, sh.dk), 0.1, gen_for(seed, "ssm-stale", s))) for s in (0, 1)]

    def data(self, L, idx):
        g, sh = gen_for(self.seed, self.name, self.sh.tp, L, idx), self.sh
        return {"L": L, "qkvz": rand((L, sh.qkvz_w), 1.0, g), "ba": rand((L, sh.ba_w), 1.0, g)}

    def run(self, items, place, stale=0):
        sh = self.sh
        self.conv.copy_(self.stale[stale][0].unsqueeze(0).expand_as(self.conv))
        self.ssm.copy_(self.stale[stale][1].unsqueeze(0).expand_as(self.ssm))
        lens = [it["L"] for it in items]
        slots = torch.randperm(self.n_pool, generator=gen_for(self.seed, "slots", place))[:len(items)]
        total = sum(lens)
        out = torch.zeros((total, sh.lv, sh.dv), dtype=DT, device=DEV)
        z = torch.empty_like(out)
        cu = torch.tensor([0] + list(_cumsum(lens)), dtype=I32, device=DEV)
        self.ops.gdn(sh, self.prm, out, z, torch.cat([it["qkvz"] for it in items]).contiguous(),
                     torch.cat([it["ba"] for it in items]).contiguous(), self.conv, self.ssm, cu,
                     slots.to(I32).to(DEV), total)
        sync()
        res, r0 = [], 0
        for L, s in zip(lens, slots.tolist()):
            res.append({"out": out[r0:r0 + L].clone(), "z": z[r0:r0 + L].clone(),
                        "conv_slot": self.conv[s].clone(), "ssm_slot": self.ssm[s].clone()})
            r0 += L
        return res

    def paths(self, lens):
        conv = lambda t: "tiled" if t >= 8 else "untiled"   # noqa: E731  conv1d_tile_size
        return {"batch_conv": conv(sum(lens)), "solo_conv": sorted({conv(L) for L in lens}),
                "virtual_chunks": [math.ceil(L / 64) for L in lens]}


class GdnBaProj(Kernel):
    name = "gdn_ba_proj"
    parts = ("ba",)

    def __init__(self, sh, ops, seed, n_pool):
        super().__init__(sh, ops, seed, n_pool)
        self.w = rand((sh.ba_w, sh.hidden), 0.02, gen_for(seed, "ba-w", sh.tp))

    def data(self, L, idx):
        return {"L": L, "x": rand((L, self.sh.hidden), 1.0, gen_for(self.seed, self.name, self.sh.tp, L, idx))}

    def run(self, items, place, stale=0):
        y = self.ops.ba(torch.cat([it["x"] for it in items]).contiguous(), self.w)
        sync()
        res, r0 = [], 0
        for it in items:
            res.append({"ba": y[r0:r0 + it["L"]].clone()})
            r0 += it["L"]
        return res

    def paths(self, lens):
        p = lambda m: "padded256" if m >= self.ops.ba_min else "rowchunk"   # noqa: E731
        return {"batch": p(sum(lens)), "solo": sorted({p(L) for L in lens})}


def _cumsum(xs):
    s = 0
    for x in xs:
        s += x
        yield s


# ----------------------------------------------------------------------------------------------- census
def compare(kernel, got, ref):
    """got/ref: per-sequence result dicts in the same sequence order."""
    bad, first = [], None
    for j, (a, b) in enumerate(zip(got, ref)):
        parts = [p for p in kernel.parts if not beq(a[p], b[p])]
        if parts:
            bad.append(j)
            if first is None:
                main = kernel.parts[0]
                row = None
                if main in parts:
                    ne = (bits(a[main]) != bits(b[main])).reshape(a[main].shape[0], -1).any(1)
                    row = int(ne.nonzero()[0].item())
                first = {"seq": j, "parts": parts, "first_row": row}
    m = max((max_abs(a[kernel.parts[0]], b[kernel.parts[0]]) for a, b in zip(got, ref)), default=0.0)
    return bad, first, m


def build_cases(only_short: bool, lens_override):
    lens_list = lens_override or EQUAL_LENS
    cases = []
    for L in lens_list:
        if only_short and L > SHORT_MAX:
            continue
        group = []
        for b in BATCHES + ([SHORT_EXTRA_BATCH] if L <= SHORT_MAX else []):
            if b * L <= STEP_BUDGET:
                group.append(tuple([L] * b))
        if group:
            cases.append((f"equal_L{L}", group))
    for st in MIXED_SETS + EXTRA_MIXED_SETS:
        if (only_short and max(st) > SHORT_MAX) or sum(st) > STEP_BUDGET:
            continue
        if lens_override and max(st) > max(lens_override):
            continue
        cases.append((f"mixed_{'-'.join(map(str, st))}", [tuple(st)]))
    return cases


def census_kernel(kernel, cases, seed, out_cb):
    rows, controls = [], []
    for gname, group in cases:
        solo_cache = {}

        def solo(L, idx):
            if (L, idx) not in solo_cache:
                solo_cache[(L, idx)] = kernel.run([kernel.data(L, idx)], ("solo", L, idx))[0]
            return solo_cache[(L, idx)]

        # Controls on the group's first sequence: solo repeat, solo with other placement and stale content.
        L0 = group[0][0]
        it0 = kernel.data(L0, 0)
        base = solo(L0, 0)
        rep = kernel.run([it0], ("solo", L0, 0))[0]
        other = kernel.run([it0], ("solo-other", L0, 0), stale=1)[0]
        # The conv slot keeps its 5 spec rows (3..7) untouched by a prefill, so only rows 0..2 are compared
        # across different stale content; everything else must match in full.
        view = lambda p, t: t[:kernel.sh.width - 1] if p == "conv_slot" else t   # noqa: E731
        ctl = {"group": gname, "L": L0,
               "solo_repeat_equal": all(beq(rep[p], base[p]) for p in kernel.parts),
               "solo_other_placement_and_stale_equal": all(beq(view(p, other[p]), view(p, base[p]))
                                                           for p in kernel.parts if not p.endswith("_slot")),
               "solo_other_placement_and_stale_state_equal": all(
                   beq(view(p, other[p]), view(p, base[p])) for p in kernel.parts if p.endswith("_slot"))}
        controls.append(ctl)
        for lens in group:
            t0 = time.perf_counter()
            entry = {"kernel": kernel.name, "tp": kernel.sh.tp, "group": gname, "B": len(lens),
                     "lens": list(lens), "total_tokens": sum(lens), "paths": kernel.paths(list(lens))}
            try:
                items = [kernel.data(L, j) for j, L in enumerate(lens)]
                ref = [solo(L, j) for j, L in enumerate(lens)]
                got = kernel.run(items, ("batch", gname, lens))
                again = kernel.run(items, ("batch", gname, lens))
                perm = torch.randperm(len(lens), generator=gen_for(seed, "perm", gname, lens)).tolist()
                if perm == sorted(perm):
                    perm = perm[::-1]
                gp = kernel.run([items[p] for p in perm], ("perm", gname, lens))
                gperm = [None] * len(lens)
                for k, p in enumerate(perm):
                    gperm[p] = gp[k]
                bad, first, m = compare(kernel, got, ref)
                bad_p, _, m_p = compare(kernel, gperm, ref)
                bad_r, _, _ = compare(kernel, again, got)
                entry.update({
                    "equal_to_solo": not bad, "seqs_differing": len(bad),
                    "first_differing_seq": first["seq"] if first else None,
                    "first_differing_len": lens[first["seq"]] if first else None,
                    "first_differing_parts": first["parts"] if first else None,
                    "first_differing_row": first["first_row"] if first else None,
                    "max_abs": m, "permuted_equal_to_solo": not bad_p, "permuted_seqs_differing": len(bad_p),
                    "permuted_max_abs": m_p, "permutation": perm, "repeat_equal": not bad_r})
                entry["pass"] = entry["equal_to_solo"] and entry["permuted_equal_to_solo"] and entry["repeat_equal"]
            except Exception as exc:  # noqa: BLE001
                entry.update({"status": "unavailable", "error": repr(exc)[:400], "pass": None})
            entry["seconds"] = round(time.perf_counter() - t0, 3)
            rows.append(entry)
            ls = ",".join(map(str, lens)) if len(set(lens)) > 1 else f"{lens[0]}x{len(lens)}"
            if entry.get("status") == "unavailable":
                print(f"CENSUS {kernel.name} tp={kernel.sh.tp} B={len(lens)} lens=({ls}) status=unavailable "
                      f"{entry['error']}"[:300], flush=True)
            else:
                print(f"CENSUS {kernel.name} tp={kernel.sh.tp} B={len(lens)} lens=({ls})"
                      f" equal_to_solo={entry['equal_to_solo']} first_differing_seq={entry['first_differing_seq']}"
                      f" parts={entry['first_differing_parts']} row={entry['first_differing_row']}"
                      f" max_abs={entry['max_abs']:.3g} permuted_equal={entry['permuted_equal_to_solo']}"
                      f" repeat={entry['repeat_equal']} path={entry['paths']}", flush=True)
        out_cb(rows, controls)
        del solo_cache
        if DEV.type == "xpu":
            torch.xpu.empty_cache()
    return rows, controls


def summarize(kernel_name, rows, controls, spec_max):
    done = [r for r in rows if r.get("pass") is not None]
    fails = [r for r in done if not r["pass"]]

    def limit(fail_rows):
        if not fail_rows:
            return max((max(r["lens"]) for r in done), default=None)
        worst = min(max(r["lens"]) for r in fail_rows)
        ok = [max(r["lens"]) for r in done if max(r["lens"]) < worst]
        return max(ok) if ok else None

    s = {"cases": len(rows), "cases_run": len(done), "cases_failing": len(fails),
         "all_equal": bool(done) and not fails and len(done) == len(rows),
         "largest_length_all_sets_identical": limit(fails),
         "smallest_max_length_of_a_failing_set": min((max(r["lens"]) for r in fails), default=None),
         "failing_sets": [{"B": r["B"], "lens": r["lens"], "first_differing_seq": r.get("first_differing_seq"),
                           "parts": r.get("first_differing_parts"), "repeat_equal": r.get("repeat_equal")}
                          for r in fails],
         "nondeterministic_sets": [r["lens"] for r in done if not r["repeat_equal"]],
         "controls_all_equal": all(c["solo_repeat_equal"] and c["solo_other_placement_and_stale_equal"]
                                   and c["solo_other_placement_and_stale_state_equal"] for c in controls)}
    if kernel_name == "fa_prefill":
        # Sets that mix a <= spec_max prompt with unequal lengths change FA kernel route; separate them.
        routed = [r for r in fails if len(set(r["lens"])) > 1 and min(r["lens"]) <= spec_max]
        s["failing_sets_with_short_route_change"] = len(routed)
        s["largest_length_all_sets_identical_ignoring_short_route_change"] = limit(
            [r for r in fails if r not in routed])
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description="multi-sequence prefill census (R310)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--tp", default="2", help="per-rank shapes, e.g. 2 or 2,1")
    ap.add_argument("--skip-fa", action="store_true")
    ap.add_argument("--skip-gdn", action="store_true", help="skips gdn_prefill and gdn_ba_proj")
    ap.add_argument("--skip-ba", action="store_true")
    ap.add_argument("--only-short", action="store_true", help=f"lengths <= {SHORT_MAX} only")
    ap.add_argument("--lens", default="", help="override the equal-length list, e.g. 31,1645")
    ap.add_argument("--cpu-selftest", action="store_true", help="bookkeeping check on CPU with stand-in ops")
    a = ap.parse_args()
    lens_override = [int(x) for x in a.lens.split(",") if x]

    if a.cpu_selftest:
        return selftest(a)
    if not torch.xpu.is_available():
        raise SystemExit("XPU is required (or use --cpu-selftest)")
    ops = RealOps()
    props = torch.xpu.get_device_properties(0)
    report = {
        "schema": "neural.download.qwen38-fp8-prefill-multiseq-census.v1",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": props.name, "torch": torch.__version__, "python": platform.python_version(),
            "seed": a.seed, "ops": ops.name, "fa_version": ops.fa_version, "fa_splitk_decode_max_qlen": ops.spec_max,
            "ba_min_tokens": ops.ba_min, "ba_source": ops.ba_source,
            "env": {k: os.environ.get(k) for k in ("VLLM_XPU_SPEC_DECODE_MAX_QLEN", "VLLM_XPU_GDN_SPLIT_MIXED",
                                                   "VLLM_XPU_GDN_SPEC_GROUP", "VLLM_XPU_FP16_LINEAR_ROWCHUNK",
                                                   "VLLM_XPU_FP16_LINEAR_CLASSPAD", "VLLM_XPU_FA_SERIAL_SPEC_DECODE",
                                                   "B70_FA_VERIFY_ROWS", "VLLM_BATCH_INVARIANT")},
            "gdn_schema": str(torch.ops._xpu_C.gdn_attention.default._schema)},
        "step_budget": STEP_BUDGET, "only_short": a.only_short, "by_kernel": {}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cases = build_cases(a.only_short, lens_override)
    for tp in [int(x) for x in a.tp.split(",") if x]:
        sh = Shapes(tp)
        kinds = ([] if a.skip_fa else [FaPrefill]) + ([] if a.skip_gdn else [GdnPrefill]) \
            + ([] if (a.skip_gdn or a.skip_ba) else [GdnBaProj])
        for K in kinds:
            pool = pool_size(K, sh, cases)
            kernel = K(sh, ops, a.seed, pool)
            sec = report["by_kernel"].setdefault(K.name, {})
            key = f"tp{tp}"
            sec[key] = {"shapes": sh.as_dict(), "pool": pool}

            def save(rows, controls, sec=sec, key=key):
                sec[key]["cases"], sec[key]["controls"] = rows, controls
                a.out.write_text(json.dumps(report, indent=1))

            t0 = time.perf_counter()
            rows, controls = census_kernel(kernel, cases, a.seed, save)
            sec[key]["summary"] = summarize(K.name, rows, controls, ops.spec_max)
            sec[key]["seconds"] = round(time.perf_counter() - t0, 1)
            a.out.write_text(json.dumps(report, indent=1))
            del kernel
            torch.xpu.empty_cache()
    report["summary"] = {f"{k} {t}": v["summary"] for k, d in report["by_kernel"].items() for t, v in d.items()}
    a.out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: {x: v[x] for x in ("all_equal", "largest_length_all_sets_identical",
                                            "smallest_max_length_of_a_failing_set", "cases_failing",
                                            "controls_all_equal")}
                      for k, v in report["summary"].items()}, indent=1))
    return 0


def pool_size(K, sh, cases):
    sets = [s for _, g in cases for s in g]
    if K is FaPrefill:
        return max(sum(math.ceil(L / sh.page) for L in s) for s in sets) + 8
    return max(len(s) for s in sets) + 8


def selftest(a) -> int:
    """CPU, float32, tiny shapes, stand-in ops: the census must call everything identical, then must catch a
    dependence on the step's total tokens."""
    global DEV, DT
    DEV, DT = torch.device("cpu"), torch.float32
    global STEP_BUDGET
    STEP_BUDGET = 512
    cases = build_cases(True, [8, 16, 31, 33, 64])
    cases = [(n, [s for s in g if sum(s) <= STEP_BUDGET]) for n, g in cases]
    cases = [(n, g) for n, g in cases if g]
    result = {}
    for leak in (False, True):
        ops = EmulOps(leak)
        for tp in (2, 1):
            sh = Shapes(tp, tiny=True)
            for K in (FaPrefill, GdnPrefill, GdnBaProj):
                kernel = K(sh, ops, a.seed, pool_size(K, sh, cases))
                rows, controls = census_kernel(kernel, cases, a.seed, lambda r, c: None)
                s = summarize(K.name, rows, controls, ops.spec_max)
                result[f"leak={leak} {K.name} tp{tp}"] = {k: s[k] for k in ("all_equal", "cases_failing",
                                                                            "controls_all_equal")}
    print(json.dumps(result, indent=1))
    ok = all(v["all_equal"] and v["controls_all_equal"] for k, v in result.items() if "leak=False" in k)
    caught = all(not v["all_equal"] for k, v in result.items() if "leak=True" in k and "ba_proj" not in k)
    print(f"SELFTEST clean_all_equal={ok} injected_leak_detected={caught}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"selftest": result, "clean_all_equal": ok, "leak_detected": caught}, indent=1))
    return 0 if ok and caught else 1


if __name__ == "__main__":
    raise SystemExit(main())
