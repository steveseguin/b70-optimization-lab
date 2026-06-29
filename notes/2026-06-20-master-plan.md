# Master Plan: >150 tok/s on Qwen3.6-35B-A3B / 4× Arc Pro B70

Date: 2026-06-20. Goal: **>150 tok/s single-session decode (prefer >200), no quality loss.**
Current baseline: 93.55 tok/s (TP4 PIECEWISE forced-comm, Quark W8A8 INT8).

## Core Strategy Shift

We spent days deep in the spec-decode/ReplaySSM cascade (parity cracked but
integration issues remain). The research reveals the **baseline itself is
improvable by 10-30%** through proven upstream work we simply don't have synced.

**New priority: maximize the no-spec baseline FIRST (lower risk, ports proven
code), THEN layer spec decode on the improved floor.**

Evidence the baseline has headroom:
- Our LocalMaxxing public row: 99.43 tok/s (same model, same hardware) — so ~99
  is achievable without spec decode.
- Upstream vLLM v0.1.10 (released June 17) includes GDN prefill optimization,
  fused RMSNorm/SiLU-gate + MXFP8/MXFP4, FP8/MXFP8 GEMM consolidation, rotary,
  and PyTorch 2.12 work. Local fork is on 0.1.9.dev27.
- Multiple narrow upstream PRs target exactly our bottlenecks: GDN `in_proj_ba`
  fusion (PR 41457), tensor-descriptor chunk-cumsum stores (PR 45816, 5-7%
  device-time reduction), MoE reusable workspace (PR 392), invalid-row MoE
  guard (PR 401), GDN graph-padded metadata narrowing (jasonboukheir fork).
- LocalMaxxing shows XPUGraph is the giant B70 lever: eager-only ~11 tok/s,
  graph-captured ~102 tok/s. Our PIECEWISE work is aligned but may be missing
  upstream graph improvements.

---

## Phase 1 — Upstream kernel package delta bakeoff (HIGHEST EV, LOWEST RISK)

**Goal:** determine how much speed the local fork leaves on the table vs upstream
v0.1.10 + narrow PRs.

**Steps:**
1. Create a clean comparison branch in `vllm-xpu-kernels` (NOT in-place upgrade).
2. Record the current baseline with exact identity (93.55 reference).
3. Upgrade to upstream v0.1.10 on the branch; rebuild; run same-identity canary
   + speed test. Record delta.
4. Cherry-pick narrow PRs one at a time (canary gate each):
   - PR 41457: fuse GDN `in_proj_ba` → one projection (not two GEMMs).
   - PR 45816: tensor-descriptor store for `_chunk_cumsum_fwd_kernel` (5-7% off).
   - PR 401: skip invalid MoE activation rows (no `.item()` sync).
   - PR 392: reusable MoE workspace (no per-call scratch alloc).
   - jasonboukheir commit: narrow cudagraph-padded GDN metadata to active size.
5. Also check: PR 411 (GDN shared-local-memory race fix for >=32K context).
6. Promote any canary-clean speed win to the working lane.

**Validation:** json 96/96 + color 96/96 + same benchmark identity. Record exact
package versions in the summary.

**Expected gain:** 10-30% over 93.55 → ~103-122 tok/s baseline.

## Phase 2 — TP layout empirical (TP2 vs TP4 for single-request)

**Goal:** determine whether TP4 is actually optimal for single-session decode.

**Why:** LocalMaxxing B70 llama.cpp multi-card data shows 4×B70 with direct
allreduce can REGRESS to 31 tok/s vs 3× at 41 tok/s. TP4 adds per-layer sync
that may hurt c1 latency. The model is only ~3B active — it might fit on fewer
cards with less communication overhead.

**Steps:**
1. Run same-identity TP2 (devices 0,1) PIECEWISE forced-comm benchmark.
2. Run same-identity TP4 benchmark (current baseline).
3. Compare single-request corrected tok/s.
4. If TP2 > TP4 for c1, investigate expert-parallel or data-parallel layouts.

**Validation:** same canaries, same identity (except TP size).

## Phase 3 — Per-step overhead reduction (the ~5 ms non-forward slice)

**Goal:** reduce the 5.16 ms non-forward overhead (48% of decode time).

**Why:** at 10.69 ms/token, ~5.53 ms is forward, ~5.16 ms is overhead (scheduler,
sampler, host-device, output materialization). This is where the 93.55 vs 99+
gap likely lives.

**Steps:**
1. Profile the decode step with `VLLM_XPU_DECODE_TIMING` to get per-region
   breakdown (already instrumented locally).
2. Target the biggest overhead regions:
   - `bookkeeping_to_list` (output materialization — LocalMaxxing notes showed
     this is comparable to forward time on TP2 no-async).
   - Sampler host-device round-trip.
   - Scheduler Python overhead.
3. Port upstream async scheduling fix (local notes: "async scheduling was a
   separate correctness poison" — but the CORRECT fix is to fix the async +
   PIECEWISE graph replay correctness issue, not avoid async).
4. Overlap sampled-token output materialization with the next forward (item 5
   in the suggestions).

**Validation:** canary 96/96 + same identity + per-region timing before/after.

## Phase 4 — Runtime/driver controlled bakeoff

**Goal:** determine whether a newer runtime stack improves speed or stability.

**Why:** current `26.18.38308.1`; PPA offers `26.18.38308.4`; PR #424 stages
`26.22.38646.4` + IGC `2.36.3`. Multiple reports tie newer runtime to multi-
device context and P2P fixes.

**Steps:**
1. Build a stack inventory script (kernel, xe, compute-runtime, IGC, GMM, oneAPI,
   PyTorch, Triton-XPU, vLLM, vllm-xpu-kernels versions).
2. Run a P2P checksum test for every B70 pair.
3. Bake off current vs `26.18.38308.4` vs `26.22.38646.4` on a clean branch.
4. Promote only if canary-clean AND faster.

**Risk:** stack changes can break things. Controlled branch only.

## Phase 5 — Spec decode on the improved baseline

**Goal:** layer spec decode (ReplaySSM + MTP/EAGLE/DFlash draft) on top of the
improved baseline from Phases 1-4.

**Why:** spec decode is the only path to >200. But it should be built on the best
possible no-spec floor. If Phase 1-4 raises the baseline to ~120-130, then even
a modest spec speedup (1.3-1.5×) reaches >150.

**Steps:**
1. Continue the ReplaySSM port (the algorithm is cracked; the integration
   cascade needs resolution — state lifecycle, capture, warmup).
2. Once ReplaySSM passes canary, test with:
   - MTP hybrid (60-88% acceptance validated).
   - DFlash (`z-lab/Qwen3.6-35B-A3B-DFlash` — purpose-built for this model).
   - EAGLE-1 (74% acceptance in GPT-5.5's offline tests).
3. Sweep `num_speculative_tokens` (k=1,3,5) for max speed at canary-safe quality.

**Validation:** canary 96/96 + quality suite baseline_match + corrected tok/s.

---

## What We Keep From The Current Session (committed assets)

- **TP4 restored** (device 3 wedge fixed, XCCL healthy).
- **ReplaySSM algorithm cracked** (`ff4cf370f` → `9557d9108`): the GDN parity
  bug is solved algorithmically (drafts accept at 100%, fused kernels fast).
  The remaining work is XPU integration (state lifecycle, capture, warmup) —
  deferred to Phase 5.
- **Real bug fixes committed:** routed-GEMM1 B-layout correctness fix, the
  `VLLM_XPU_GRAPH_NO_EMPTY_CACHE` capture fix, identity recorder.
- **EAGLE-1 draft trained** (74% acceptance offline).
- **DFlash draft available** (`z-lab/Qwen3.6-35B-A3B-DFlash`, 905M).
- **Comprehensive research** in `suggestions/findings/` (750+ lines of sourced
  options, fork audits, upstream PR tracking).

## What We Stop Doing

- Grinding the ReplaySSM XPU integration cascade layer-by-layer (defer to
  Phase 5, after the baseline is raised).
- MoE micro-kernel tuning (proven exhausted: 20+ branches, all "exact but
  small" — the routed-GEMM1 B-layout fix is the only promotable win, already
  committed).
- Endless device-3 resets (add a preflight guard against crash-prone configs).

## Execution Order

1. **Phase 1** (upstream delta) — start NOW. Highest EV, lowest risk, ports
   proven work.
2. **Phase 2** (TP layout) — quick A/B, parallel with Phase 1.
3. **Phase 3** (overhead) — after Phase 1 establishes the new floor.
4. **Phase 4** (runtime) — controlled, separate branch.
5. **Phase 5** (spec decode) — on the improved baseline.
