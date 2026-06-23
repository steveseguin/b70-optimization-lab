# Plan (research-based): Qwen3.6-35B-A3B — parity fix + path to >150 tok/s

Date: 2026-06-20. Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`, 4× Arc Pro B70.
Goal: **>150 tok/s single-session decode, no quality loss.** Baseline: 93.55 tok/s.

This plan replaces the from-scratch GDN-spec-parity attempts (4+ failures:
prior author m18-m26, GPT-5.5, codex v1/v2) with a **port of proven upstream
code**, after researching how the open-source community already solved this.

---

## What the research found (the reframe)

**The bug we spent days on is already solved upstream.** vLLM ships **ReplaySSM**
(commit `3c85112`, files `fused_recurrent_replayssm.py` + `gdn_replayssm_spec_decode.py`;
ref impl `Johnny-Liou/ReplaySSM`; Dao AI Lab 2026). SGLang just ported it
(PR sgl-project/sglang#28695 + RFC #28511). It replaces the *exact* broken
abstraction we kept twisting — per-draft-token full `[V,K]` recurrent-state
snapshots (our `intermediate_ssm` / slot-copy) — with an **output-only ring
reconstruction** via the chunked delta-rule `(I+A)^{-1}` UT-transform, flushing
the full state only every L tokens. Lossless (GSM8K parity on Qwen3.5-35B-A3B).

**Our fork doesn't have it** (confirmed: no `*replayssm*` files). That single
gap is the parity bug. **Port it; stop reinventing.**

**Honest caveat on speed (from the SGLang RFC's own numbers):** ReplaySSM is a
**bandwidth/memory** optimization for **high-batch** serving — at batch ≥64 the
GDN verify is 70-79% peak HBM. At **batch 1 (single-request) the GDN decode is
only ~2% HBM (latency/launch-bound)**, and ReplaySSM is *slightly slower* there.
End-to-end on this exact model (Qwen3.5-35B-A3B, 128 concurrent): only **+2.3%
TPOT**. Why so small: the model is **MoE-heavy** — GDN linear layers are a small
fraction of decode cost, diluted by MoE + full-attention.

**Implication:** ReplaySSM unblocks *correctness* (so spec decode can finally be
quality-clean), but it does **not by itself** reach >150 single-request. The
single-request bottleneck is **MoE + per-step overhead**, which is why 93.55 is
poor for a ~3B-active model.

---

## Two distinct problems

1. **Correctness (the parity bug):** spec-decode verifier diverges from no-spec.
   → Fixed by porting ReplaySSM. This is now a *port*, not research.
2. **Speed (93.55 is poor / >150 goal):** single-request decode is
   overhead + MoE-kernel bound, not GDN-bound. Needs a different lever.

## Why >150 is still reachable (the mechanism)

Spec decode on a **MoE** model amortizes the memory-bound weight load: a forward
over `[target, drafts...]` costs ~the same HBM as a 1-token forward (weight
traffic dominates; activations are tiny) → near-(accepted+1)× forward speedup.
The only per-token-expensive part was the **GDN recurrent state per spec
position** — which is *exactly* what ReplaySSM makes cheap (output-only). So the
combination **ReplaySSM-correct-verify + lightweight high-acceptance draft** is
the real >150 lever. A draft is already validated at **60-74% acceptance** here
(MTP/EAGLE). Acceptance-length ~2.5-3 → plausible 2-3× single-request speedup.

---

## The plan

### Phase 1 — Port ReplaySSM spec-verify (fixes parity, the proven path)
- Source: upstream vLLM `3c85112` `gdn_replayssm_spec_decode.py` (spec-verify)
  and `fused_recurrent_replayssm.py` (decode). Adapt to this fork's XPU GDN
  layout (`gdn_linear_attn.py` + `_xpu_C.gdn_attention`).
- Replace the broken `_xpu_gdn_promote_running_state` / slot-copy / codex v1-v2
  paths with the ReplaySSM ring verify.
- **Port, don't write from scratch** — match upstream's `early-flush invariant`
  (`max_cache_len >= 2 * max_spec_len`) exactly (overflow → uninitialized logit
  → desync; this is the edge that bit codex v2).
- Gate behind `VLLM_XPU_GDN_REPLAYSSM_SPEC` (default off), like SGLang's
  `--enable-gdn-replayssm-spec`.
- Validate with the **endpoint canary** (not synthetic — synthetic lied in codex
  v1). Success = json 96/96 + color 96/96 vs no-spec, MTP k=1, TP4 PIECEWISE.
- This is the right task to delegate to codex: "port file X from upstream commit
  Y; do not reinvent."

### Phase 2 — Measure spec decode at single-request (does ReplaySSM + draft clear 150?)
- With parity fixed, run MTP k=1/3 and EAGLE (the 74%-acceptance draft) on TP4.
- Measure corrected tok/s. The MoE-amortization argument says it should jump.
- If ≥150 with canaries passing → **goal met** (run quality suite, promote).

### Phase 3 — If still <150: attack the MoE + overhead bottleneck
Two sub-levers, both via **porting upstream community perf**, not new kernels:
- **3a. Sync upstream vLLM GDN/MoE perf** that this fork lacks: FlashQLA backend
  (vLLM#45883), GDN_ATTN batch invariance (#45819), Qwen3.5 prefix caching
  (#45848), fused QK-RMSNorm+RoPE+KV-store (sglang#28700). The fork is behind
  upstream; some of the 93.55 gap is "stale fork," not hardware.
- **3b. Per-step overhead** (the ~5 ms non-forward slice of 10.69 ms/token):
  scheduler/sampler/dispatch overhead at batch 1. Profile and cut.
- **3c. TP layout:** the no-spec TP4 forced-comm lane is 93.55; check whether a
  TP2 / EP / DP split changes single-request decode (TP4 all-reduce may be
  overhead for 1 token). One empirical A/B.

### Phase 4 — Reduce risk of re-wedging device 3
- The repeated device-3 driver wedges (from device-lost capture crashes) cost a
  reboot each time. Add a preflight that aborts capture-unsafe configs before
  they crash, and keep the `SUDOPASSWORD.txt` recovery path (gitignored).

---

## Hard rules (the failure modes of the last 4+ attempts)
- **PORT, don't reinvent.** ReplaySSM exists upstream — use it. No more
  hand-rolled slot-copy / per-position Python loops / native-spec-table rewrites.
- **Validate with the endpoint canary, not synthetic tests** (synthetic passed in
  codex v1 while the endpoint failed).
- **Commit every green step.** No uncommitted "real fixes" (the v1 fix sat
  uncommitted last time).
- **No MoE kernel micro-knobs** proven dead (oneDNN sidecar, unchecked layerlet,
  fused-act-quant, etc.). The routed-GEMM1 B-layout fix is already committed.
- **One change per identity**; always set PIECEWISE+cg128 explicitly (the
  graph-NONE ~15 tok/s trap).

## Honest >150 feasibility read
- **Parity bug:** definitely fixable (port ReplaySSM — proven upstream).
- **>150 single-request:** plausible but **not guaranteed** by ReplaySSM alone.
  It depends on Phase 2's measurement (MoE-amortization vs per-spec-position
  cost). If spec doesn't clear 150, Phase 3 (upstream perf sync + overhead) is
  the fallback. The 93.55 baseline being poor for a 3B-active MoE is a real
  signal that headroom exists, but capturing it is more about syncing upstream
  efficiency than novel XPU kernel work.

## References (community solutions to lean on)
- ReplaySSM (Dao AI Lab) — https://dao-lab.ai/blog/2026/replayssm/
- Ref impl — https://github.com/Johnny-Liou/ReplaySSM
- Upstream vLLM kernels — commit `3c85112`: `fused_recurrent_replayssm.py`,
  `gdn_replayssm_spec_decode.py`
- SGLang ports — RFC sgl-project/sglang#28511; PRs #28451 (decode), #28695
  (spec-verify), #27658 (compact linear spec cache), #26520 (GDN MTP final-state
  recompute), #28010 (DFLASH reduced-cache replay)
- Upstream vLLM GDN perf — #45883 (FlashQLA), #45819 (batch invariance), #46048
  (Qwen3.5 prefix caching)
- DFLASH draft for this model — `z-lab/Qwen3.6-35B-A3B-DFlash` (use with
  method:dflash, not mtp — a prior attempt mis-used it)
