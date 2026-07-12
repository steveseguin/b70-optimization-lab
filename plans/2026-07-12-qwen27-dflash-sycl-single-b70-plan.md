# Qwen27 DFlash + SYCL Single-B70 Optimization Plan

Created: 2026-07-12

Status: superseded as a controlling plan by
[`2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md`](2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md).
Keep this file as the initial exploratory plan and historical record. Follow
the newer plan wherever they differ, especially for the fixed TP1 mandate,
four-worker workflow, persistent cache/model-pack architecture, measured graph
status, high-impact kill rules, fusion order, and DPAS/DFlash execution path.

## Goal

Maximum single-B70 decode tok/s for Qwen3.6-27B, apples-to-apples with
hipfire's 213 tok/s (single R9700, MQ4 + DFlash + Q8 KV). Use GGUF +
llama.cpp/SYCL + DFlash speculative decoding. No Python in the hot path.

## Context: What Changed Since The Last GGUF Attempt

The prior `experiments/qwen36-27b-mtp-gguf-q4-b70` lane closed at 30.8 tok/s
MTP3 on 2026-07-05 and concluded "far below vLLM." Three things have changed:

1. **PR #25063 merged 2026-07-07** (Intel `malsbat`): `K_QUANTS_PER_ITERATION=1`
   + DMMV reorder gate fix. Reported **1.538x on Q4_K_M, 1.853x on Q5_K_M**
   single-B70 Qwen3.5-27B decode. Our pinned build at `fdb1db877` (2026-07-03)
   **predates this**. A rebuild should jump no-spec from ~23.7 to ~36+ tok/s.

2. **DFlash was never tested.** The prior lane only swept MTP3/4/5/7/9 with
   p_min. DFlash (`--spec-type draft-dflash`) is now in llama.cpp master
   (PR #22105). DFlash accepts 5-9 tokens per step on code/math prompts vs
   MTP3's ~2.7. A DFlash draft GGUF exists:
   `Alittlehammmer/Qwen3.6-27B-DFlash-GGUF-llama.cpp` (Q4_K_M, 1.03 GB).

3. **The NDEBUG build trap was identified** (PMZFX Finding #1): shipped
   `llama-cpp-daily` and some custom builds ship with asserts enabled,
   suppressing prefill 51-180%. Need to verify `-DNDEBUG` reaches the compiler.

## Hardware

- 4x Intel Arc Pro B70 (32 GB, 608 GB/s, Xe2/Battlemage, `xe` driver)
- AMD Threadripper PRO 5955WX (16 cores), 128 GB DDR4
- oneAPI 2026.0 + 2025.3, Level Zero 1.28.2, NEO 26.18.38308.1

## Quantization Choice: Q4_0

**Decision: Q4_0 as primary target.** Rationale:

1. **Fastest decode quant on B70.** PMZFX measured Q4_0 at 23.67 tg vs Q4_K_M
   at 20.56 tg (15% faster) on Qwen3.5-27B. Q4_0 has simpler dequantization
   (one scale multiply per 32-element block vs Q4_K's super-block with 6-bit
   d-scale + 4-bit d-min + per-group scales), yielding 57% bandwidth
   utilization vs 53% for Q4_K_M.

2. **Closest to hipfire's MQ4.** MQ4 is a uniform 4-bit format with FWHT
   rotation. Q4_0 is also uniform 4-bit. Q4_K is mixed-precision super-blocks.
   For apples-to-apples comparison, Q4_0 is the match.

3. **PR #25063 does NOT help Q4_0.** The K_QUANTS_PER_ITERATION fix only
   affects K-quants (Q4_K, Q5_K, Q6_K). Q4_0 was already on the fast
   reordered DMMV path before the PR. Post-rebuild, Q4_0 stays at ~23.7 tg
   while Q4_K_M jumps from ~13 to ~20.4. Q4_0 is still faster.

4. **Same file size as Q4_K_S** (both 16.1 GB in the MTP GGUF), so the
   bandwidth budget is identical. Q4_0 wins on kernel efficiency.

5. **Available with MTP** from `unsloth/Qwen3.6-27B-MTP-GGUF:Q4_0` (16.1 GB).

**Secondary: Q4_K_S** — same file size, slightly better quality, and if
post-#25063 K-quant reorder improvements push it past Q4_0, we switch. Test
both in Phase 1 on different GPUs to settle it definitively on our hardware.

**Avoid: Q4_K_M** (17.1 GB, 13% slower than Q4_0), **Q5_K_M** (19.8 GB, 42%
slower), **IQ4_XS** (broken SYCL kernel path, 26% slower).

## Comparison Reference

| Engine | Config | tok/s | Card |
|--------|--------|-------|------|
| hipfire DFlash | Qwen27 MQ4 + DFlash b16 + Q8 KV | 213 (code) | 1x R9700 (~640 GB/s) |
| hipfire MTP | Qwen27 MQ4 + MTP3 + Q8 KV | 78.8 | 1x R9700 |
| llama.cpp MTP3 | Qwen27 UD-Q4_K_XL + MTP3 | 30.8 | 1x B70 (608 GB/s) |
| llama.cpp no-spec | Qwen27 UD-Q4_K_XL | 23.7 | 1x B70 |
| vLLM MTP3 | Qwen27 AutoRound INT4 + MTP3 | 68.0 | 1x B70 |
| PMZFX no-spec | Qwen3.5-27B **Q4_0** | **23.67** | 1x B70 |
| PMZFX no-spec | Qwen3.5-27B Q4_K_M | 20.56 | 1x B70 |

Our B70 has comparable bandwidth to the R9700 (608 vs ~640 GB/s) and 2x VRAM
(32 vs 16 GB). The gap to close is kernel efficiency + DFlash acceptance.

## Theoretical Speed Ceilings (single B70, 608 GB/s)

Weight read per forward (Q4_K_M ~17 GB, Q5_K_M ~19.5 GB):

| Config | No-spec floor | With DFlash code (9 accepted) | With DFlash chat (5.5 accepted) |
|--------|:---:|:---:|:---:|
| Q4_K_M post-#25063 (~36 tok/s no-spec) | 36 | ~130 | ~85 |
| Q4_K_M fully optimized (~43 tok/s no-spec) | 43 | ~170 | ~105 |
| Q5_K_M post-#25063 (~33 tok/s no-spec) | 33 | ~120 | ~78 |

DFlash cycle: 2 target forwards + 1 draft forward (~5 ms for 1 GB draft).

## Phase 0 — Rebuild And Verify (hours)

**Goal**: get the #25063 speedup and verify build health.

1. Fast-forward `/home/steve/src/llama.cpp` to latest master (post-`d209086`).
2. Rebuild SYCL with:
   - `GGML_SYCL_DEVICE_ARCH=bmg-g31`
   - `CMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG"` (verify no asserts warning)
   - `GGML_SYCL_F16=ON`, `GGML_SYCL_DNNL=ON`
   - Do NOT set `GGML_SYCL_DISABLE_OPT` (dense model)
3. Verify: `llama-bench -p 0 -n 0 2>&1 | head` shows no asserts warning.
4. Quick smoke: single-token generation on the existing UD-Q4_K_XL GGUF.

**Gate**: build compiles, asserts are off, no-spec decode speed >= 30 tok/s.

## Phase 1 — Baseline Matrix On 4 GPUs (1 day)

**Goal**: establish the post-#25063 baseline across quants and spec methods.

Run four experiments in parallel, one per B70:

| GPU | Model | Spec | KV | Purpose |
|:---:|-------|------|:--:|---------|
| 0 | **Q4_0** MTP GGUF | no-spec | f16 | pure decode baseline (fastest quant) |
| 1 | **Q4_0** MTP GGUF | draft-mtp n_max=3 | q8_0 | MTP baseline on Q4_0 |
| 2 | **Q4_0** MTP GGUF | draft-dflash n_max=15 | q8_0 | **DFlash test on Q4_0** |
| 3 | Q4_K_S MTP GGUF | no-spec | q8_0 | Q4_K_S comparison (same size, #25063 benefit) |

Each run uses the strict cold realistic suite with `cache_prompt=false`,
`--cache-ram 0`, one prompt per request, `cached_tokens=0` verified.

**Downloads needed**:
- `unsloth/Qwen3.6-27B-MTP-GGUF:Q4_0` (16.1 GB, primary target)
- `unsloth/Qwen3.6-27B-MTP-GGUF:Q4_K_S` (16.1 GB, comparison)
- `Alittlehammmer/Qwen3.6-27B-DFlash-GGUF-llama.cpp:Q4_K_M` (new, ~1 GB, draft model)

**Anti-poisoning**: each GPU gets its own fresh server process. No warm-up
loops. No repeated prompts. No n-gram history. First response is the measured
response. DFlash acceptance is reported per-prompt, not just aggregate.

**Gate**: all four rows pass the cold realistic gate. Record median tok/s,
p10, mean, TTFT, acceptance rate, and prompt/output hashes.

## Phase 2 — DFlash Acceptance Deep-Dive (1-2 days)

**Goal**: understand DFlash's genre-conditional behavior on our prompts.

If Phase 1 GPU 2 shows DFlash working:

1. Run the same DFlash config on all 4 GPUs with different prompt suites:
   - GPU 0: code-heavy prompts (HumanEval-style)
   - GPU 1: math/reasoning prompts
   - GPU 2: general chat/instruction (our realistic suite)
   - GPU 3: mixed/creative writing

2. Measure accepted tokens per step per genre.

3. Also test Qwen3.5-27B + Qwen3.5-27B-DFlash (the mature, benchmarked
   draft) as an alternative if Qwen3.6 DFlash acceptance is poor (the
   Qwen3.6 DFlash model card says "still under training").

**Anti-poisoning**: DFlash is genre-conditional. Do NOT report a single
aggregate tok/s. Report per-genre or use a fixed mixed suite that reflects
the real target workload. The hipfire methodology notes that one stray
newline can swing acceptance by 17%.

**Gate**: DFlash produces target-verified output (not garbage). Acceptance
rate is recorded per-prompt. Quality gate (exact JSON, color sequence)
passes on at least the general-chat suite.

## Phase 3 — Kernel Optimization (weeks, if needed)

**Goal**: close the bandwidth utilization gap from ~56% to >85%.

Transferable techniques from hipfire and prior B70 work:

1. **Fused 3-way QKV projection**: read activation once, write Q+K+V in one
   kernel launch instead of three. hipfire's biggest fusion win.
2. **Fused RMSNorm + rotate + GEMM pipeline**: eliminate intermediate global
   memory writes between norm and projection.
3. **MQ4-style FWHT weight rotation**: offline-rotate weights to reduce INT4
   quantization error (proven for Qwen3.5+ DeltaNet weight distributions).
   Runtime rotation fuses into RMSNorm at ~zero cost.
4. **Sub-group dp4a inner loop**: prior B70 prototypes show this beats ESIMD
   float on Q4 shapes. Ensure the K-quant DMMV path uses it.
5. **Q8 KV with fused dequant in attention**: never materialize full-precision
   KV cache; dequantize K/V tiles on-the-fly inside the attention kernel.
6. **oneMKL GEMM flash attention** (PR #25025): helps prefill, not decode,
   but matters for long-context TTFT.

**Risk**: ESIMD DPAS has a known correctness bug in large SYCL builds (Intel
LLVM #21741). Use sub-group dp4a first; reach for XMX/DPAS only with
validated standalone+integrated canaries. PMZFX's ESIMD XMX attempt is
blocked on this bug.

**Gate**: any kernel change must pass the same cold realistic gate. Record
before/after bandwidth utilization, not just tok/s.

## Phase 4 — Custom Lean Engine (months, only if llama.cpp hits a ceiling)

If llama.cpp's framework overhead becomes the bottleneck after Phase 3:

1. Fork ggml-sycl kernels + Qwen3.5 graph into a standalone binary.
2. Direct Level Zero memory management, zero Python, zero PyTorch.
3. Maximum kernel fusion, persistent command buffers.
4. Consider Rust + SYCL bindings if they mature.

This is the "build our own hipfire for Intel" path. Only start after proving
the bottleneck is framework overhead, not kernel quality.

## 4-GPU Parallel Testing Strategy

We have 4 independent B70s. Use them for:

1. **Parallel config screens**: 4 quants or 4 spec methods simultaneously.
2. **Crossover A/B**: same config on different GPUs to measure variance.
3. **Draft model comparison**: Qwen3.6-DFlash vs Qwen3.5-DFlash vs MTP vs
   no-spec, all at once.
4. **Kernel A/B**: optimized kernel on GPU 0/2, baseline on GPU 1/3, same
   prompts, same cold start.

**Port assignment**: GPU 0 → port 19430, GPU 1 → 19431, GPU 2 → 19432,
GPU 3 → 19433. Use `ONEAPI_DEVICE_SELECTOR=level_zero:*` +
`ZE_AFFINITY_MASK=$GPU_INDEX`.

## Critical Risks And Known Issues

1. **SYCL GDN kernel S_v limitation**: `gated_delta_net.cpp:203-251` only
   handles S_v in {16, 32, 64, 128}. If Qwen3.5 27B's head_v_dim differs,
   runtime abort with no fallback. Check first.
2. **DFlash on llama.cpp is community-converted**, not upstream z-lab.
   `sm = tensor` crashes; `sm = layer` works (per Alittlehammmer's card).
3. **Qwen3.6-DFlash draft is still training** (per z-lab model card).
   Qwen3.5-27B-DFlash is the mature, benchmarked alternative.
4. **SYCL server hang on device loss** (Issue #24810): run a `/slots`
   liveness watchdog on every server process.
5. **Never set `SYCL_CACHE_PERSISTENT=1`** on B70 (Hal9000: poisons cache,
   SEGV on next boot).
6. **DFlash genre-conditional**: can be a net loss on prose. Do not enable
   globally for production without per-genre benchmarking.

## Lessons From Past Experiments

- **Gemma one-graph warm-up folding**: the Gemma MTP drafter folded warm-up
  into the drafting loop as a single GPU graph. This optimization is specific
  to Q-only, KV-shared, no-cross-position drafters. DFlash's block-diffusion
  draft has cross-position attention, so this technique does NOT directly
  apply. However, the principle (minimize host round-trips in the draft
  cycle) is universal.
- **Speculative decode can poison benchmarks**: warm/predictable conditions
  inflate acceptance. All headline results must be cold-start. The Gemma
  record moved from synthetic to realistic-suite gating for exactly this
  reason.
- **Previous GGUF sweeps exhausted config-only knobs**: ubatch, VMM,
  FlashAttention, immediate command lists, Q8 KV, p_min were all swept.
  Do not repeat these. The new levers are: #25063 rebuild, DFlash, and
  source-level kernel work.
- **vLLM XPU cannot run GDN** (PMZFX confirmed): `fla/ops/chunk.py` crashes.
  llama.cpp/SYCL is the only Intel engine for Qwen3.6-27B GDN.

## Links

- Prior-art audit: `notes/2026-07-12-b70-qwen27-prior-art-research.md`
- Existing GGUF experiment: `experiments/qwen36-27b-mtp-gguf-q4-b70/`
- vLLM experiment: `experiments/qwen36-27b-autoround-int4-b70/`
- DFlash research: DFlash section in conversation history
- hipfire: `https://github.com/Kaden-Schutt/hipfire`
- PR #25063: `https://github.com/ggml-org/llama.cpp/pull/25063`
- PR #22105 (DFlash in llama.cpp): merged, `--spec-type draft-dflash`
- DFlash paper: `arXiv:2602.06036`
- Lucebox DFlash blog: `https://www.lucebox.com/blog/dflash27b`
- PMZFX B70 benchmarks: `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`
- Hal9000 B70 kit: `https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes`
