# B70 Qwen3.6-27B Decode Speed — Prior Art & Missed Optimizations Research

**Date:** 2026-07-12
**Goal:** maximum single-B70 Qwen27 decode (tg tok/s)
**Method:** web search across localmaxxing.com, GitHub llama.cpp issues/PRs, community B70 repos, z-lab/dflash, OpenVINO.

## Headline takeaways (read these first)

1. **A merged upstream PR gives ~1.5-1.85x tg on K-quant Qwen27 — verify we are on it.** PR [#25063](https://github.com/ggml-org/llama.cpp/pull/25063) (Intel's `malsbat`) merged **2026-07-07**: sets `K_QUANTS_PER_ITERATION=1`, opens the DMMV reorder gate, and fixes the `bmg_g21` native-subgroup-size path. Reported **1.538x tg on Qwen3.5-27B-Q4_K_M** (13.27 → 20.41), **1.853x on Q5_K_M** (12.16 → 22.53), **1.353x on Q6_K** (10.97 → 14.84). This is the single biggest single-B70 Qwen27 dense-decode lever found.
2. **Two open XMX flash-attention PRs attack the prefill gap (not decode), both "merge ready":** [#25025](https://github.com/ggml-org/llama.cpp/pull/25025) (oneMKL GEMM FA, `johnkarlhill`) and [#25222](https://github.com/ggml-org/llama.cpp/pull/25222) (oneDNN SDPA FA, `hmscider`). Decode is bandwidth-bound so these do not directly help tg, but they're the path to closing vLLM's 15x prefill lead. Worth tracking for merged-context workloads.
3. **DFlash has a Qwen3.6-27B draft model (`z-lab/Qwen3.6-27B-DFlash`) — the single biggest untapped speculative-decoding lever.** It supports vLLM/SGLang/Transformers/MLX backends but **NOT llama.cpp/SYCL or Intel XPU**. No issue, no PR. This is a genuine gap to file.
4. **A confirmed MUL_MAT_ID prefill correctness bug on B70 produces garbage MoE output** — Issue [#25455](https://github.com/ggml-org/llama.cpp/issues/25455). 28/792 test cases fail. Affects Qwen3.6-35B-A3B (MoE), not Qwen3.6-27B dense, but critical to know if we ever swap models.
5. **`GGML_SYCL_DISABLE_OPT=1` is still required for MoE slot-init stability but costs ~5% on dense.** For pure Qwen27 dense, keep OPT **enabled** to get the reorder wins. Do NOT carry MoE env vars into the dense lane.
6. **A `Q8_0` reorder prefill regression (42% slower PP) is invisible in `llama-bench -p 512`** — Issue [#25203](https://github.com/ggml-org/llama.cpp/issues/25203). Author `hmscider` offers to write a fused s8xf16 matmul kernel. Relevant if we push Q8_0.

---

## 1. llama.cpp SYCL optimization (highest decode relevance)

### MERGED — PR #25063: `K_QUANTS_PER_ITERATION=1` + DMMV reorder gate (Intel)
- URL: https://github.com/ggml-org/llama.cpp/pull/25063
- Author: `malsbat` (Intel, `aicss-genai`), merged by `ggerganov` 2026-07-07.
- Mechanism: DMMV warp size 32→16 + reorder (AOS→SOA) + KQPI=1 raises work-group 16→32, reducing stalls. Also fixes `ggml_sycl_supports_reorder_dmmv` gate and `init_tensor` extra-field allocation for reorderable types.
- **B70 single-card numbers (from the PR):**
  - Qwen3.5-27B Q4_K_M: 13.27 → **20.41** tg (1.538x)
  - Qwen3.5-27B Q5_K_M: 12.16 → **22.53** tg (1.853x)
  - Qwen3.5-27B Q6_K: 10.97 → **14.84** tg (1.353x)
  - Qwen3.5-9B Q4_K_M: 41.14 → **60.57** tg (1.472x)
  - pp (prefill) unchanged (~+0.3%).
- Action: confirm our pinned build is at or after commit `d209086` (2026-07-07). If our known-good 93.45 tok/s Qwen35 baseline predates this, re-baseline — Q5_K_M/Q4_K_M should jump materially on dense.

### MERGED — PR #21527 / #21638: Q8_0 SYCL reorder (PMZFX)
- 3.13x Qwen27B Q8_0 tg (4.88 → 15.28). Already in our tree per PMZFX tracking.

### MERGED — PR #21580: BF16 DMMV kernel (PMZFX)
- 4.2x BF16 tg (29.7 → 124.0 on Qwen2.5-1.5B). Relevant for BF16 weight runs.

### OPEN (merge-ready) — PR #25089: SYCL graph capture for MoE decode
- URL: https://github.com/ggml-org/llama.cpp/pull/25089
- Author: `Captain-Tripps`. Reviewed/approved by `arthw` (Intel) + `NeoZhangJianyu`. Label `merge ready`, pending rebase.
- Lets `GGML_OP_CONCAT` (dim≠3) and the fused `MUL_MAT_ID` decode path (ne12==1) use SYCL command-graph replay instead of re-submitting every token. Reduces dispatch overhead and GuC queue pressure.
- Validated on B70 with Qwen3.6-35B-A3B: 207s clean sustained decode (was wedging 81-212s). Decode speed during clean runs ~17.7-19.4 tok/s.
- Decode-focused; primarily a stability + dispatch-overhead win for MoE, not dense Qwen27. Lower priority for our dense lane but important for MoE crossover.

### OPEN (merge-ready) — PR #25217: sycl fused top-k MoE
- URL: https://github.com/ggml-org/llama.cpp/pull/25217
- `merge ready` label. MoE-specific (fuses top-k expert selection). Not relevant to dense Qwen27; relevant to Qwen3.6-35B-A3B if we run it.

### OPEN (draft) — PR #25312: oneDNN SDPA FA for quantized KV caches
- URL: https://github.com/ggml-org/llama.cpp/pull/25312
- Extends XMX FA to Q8_0/Q4_0/K-quant KV. Draft, not ready. Watch.

### Open issue #25203: Q8_0 reorder degrades 42% prefill (hmscider)
- URL: https://github.com/ggml-org/llama.cpp/issues/25203
- After any decode (or `pp<=8`), Q8_0 weights reorder and the reordered dequant→f16xf16 matmul path is 42% slower than the interleaved path. Invisible in `llama-bench -p 512` because reorder gates on `ne[1]<=8`.
- **hmscider explicitly offers to contribute a fused s8xf16 matmul kernel** — a clear collaboration opportunity. If we run Q8_0 PP-heavy workloads, this matters.

### Hal9000 kit: 11 cherry-picks (community)
- URL: https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes
- Pinned on llama.cpp master `073bb2c20` (2026-04). 8 SYCL + 2 Vulkan + 1 experimental TLA stub. Relevant SYCL patches:
  1. BF16 GET_ROWS (Gemma BF16 +40% PP, +15% tg)
  2. fused MoE `mul_mat_vec_q` TG (+47% on MoE)
  3. K-quant native subgroup-16 DMMV (+20-25% tg) — **superseded by merged #25063**
  4. oneMKL small-matmul routing (-30ms TTFT)
  5. reorder OOM crash fix
  6. HOST_MEM_FALLBACK RAII
  7. Q8_0 reorder dequantize GEMM fix — **superseded by merged #21527/#21638**
  8. docs
- Critical runtime findings (NOT in any commit):
  - `GGML_SYCL_DISABLE_OPT=1` mandatory for MoE (SEGV otherwise). Dense models: keep OPT enabled.
  - **Never set `SYCL_CACHE_PERSISTENT=1`** — poisons cache on next boot SEGV on B70.
  - `UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1` for >4GB KV allocs (32K context on 30B).
  - Two SYCL servers on one B70 = 10x slowdown; one must go Vulkan.
  - SYCL+SYCL speculative decode on one card unstable (kernel-cache contention).
  - `-fa 0` for SYCL MoE (crash path); Vulkan FA fine.
  - `-t 1` (single thread dispatch) wins on GPU tiers.
  - Mesa 26+ for Vulkan BF16 coopmat (`kisak/kisak-mesa` PPA).
- Their headline: llama.cpp SYCL beats vLLM TP=1 by 4.3x on Qwen3-Coder-30B single B70 (59.6 vs 13.85 tok/s).

---

## 2. XMX Flash Attention for Xe2 (prefill, not decode)

Two parallel PRs targeting the same gap (the 15x vLLM prefill lead is entirely XMX/DPAS flash attention):

### PR #25222: oneDNN Graph SDPA on f16 KV (hmscider) — merge-ready but correctness work pending
- URL: https://github.com/ggml-org/llama.cpp/pull/25222
- Routes eligible prefill FA through oneDNN's fused SDPA (`sdp_primitive_kernel_t`, **XMX** kernel) via Graph API pattern matching. Fuses Matmul→Divide→Add(mask)→SoftMax→Matmul.
- Build flag: `GGML_SYCL_FA_ONEDNN=1`. Runtime kill-switch `GGML_SYCL_FA_ONEDNN=0`.
- **B70 Qwen3.6-27B-Q8_0 numbers (the PR itself):**
  - pp512: 814 → **949** (1.21x)
  - pp4096: 790 → **931** (1.18x)
  - pp32768: 638 → **843** (1.32x)
  - pp65536: 200 → **762** (3.80x)
  - pp80000: 171 → **730** (**4.26x**)
- Activation gate: f16 K/V, mask present, head_dim ∈ {40,64,72,80,96,112,128,256,512}, GQA divides evenly, single sequence, prefill (Q->ne[1]≥32).
- Third-party confirmation (WizardlyBump17, Qwen3.6-35B-A3B Q5_K_XL): 116k prompt **245 → 462 t/s**.
- **BUT: correctness issues blocking merge:**
  - Alchemist (DG2) UT failures (qnixsynapse) — only on B70/BMG it passes.
  - Gibberish output reported on dual-B70 + OpenCode/Pi agents with MTP (AshotN, saurabh-deochake). Single direct curl works. Likely multi-turn KV stride issue.
  - `johnkarlhill` already fixed the root cause in his own tree (commit `13f5032`): always copy F16 K/V to dense row-major buffers before GEMM. Multi-turn KV has different strides than fresh prefill.
- Currently f16 KV only; author plans quantized KV next.
- Decode unaffected (memory-bandwidth-bound).

### PR #25025: oneMKL GEMM FA for quantized KV (johnkarlhill) — merge-ready
- URL: https://github.com/ggml-org/llama.cpp/pull/25025
- Complementary to #25222: routes Q·Kᵀ and S·V through oneMKL GEMM (XMX) when KV is quantized (q8_0/q4_0/K-quant) — opposite KV coverage from #25222.
- Activation: FA on, quantized KV, K seq ≥ 1024, Q seq ≥ 32. Trigger via `--flash-attn on --cache-type-k q8_0 --batch-size 1024`.
- **B70 numbers (Qwen3.6-27B UD-Q5_K_XL, MTP, 32K context):**
  - f16 KV: 671 PP / 15 tg
  - q8_0 KV: 671 PP / 15 tg (within 1% of f16, using 1/2 the KV memory)
  - 110K q8_0 KV: 335 PP / 17 tg
  - TILE baseline q8_0: 330 PP → MKL **606 PP (1.84x)**
  - Gemma-4-26B q8_0: TILE 746 → MKL **1473 PP (1.97x)**
- Decode unaffected (±1 t/s).
- Bug found + fixed: dense head-major vs interleaved layout mismatch in normalize kernel (corrupted all models except Qwen3.6-27B GQA=6, which was sparse enough to hide it). Multi-turn coherence now validated on Qwen3.6-27B and Qwen3.6-35B-A3B.
- Reviewer `arthw` (Intel) approved. Env vars renamed: `GGML_SYCL_ENABLE_MKL_FA`, `GGML_SYCL_MKL_FA_DEBUG`, `GGML_SYCL_MKL_FA_DIAG`.

### PMZFX shelved XMX-via-ESIMD work (reference for dead-ends)
- Tried `joint_matrix`: broken on BMG. Tried `esimd::xmx::dpas`: prototype worked but hit IGC codegen bug → filed intel/llvm#21741. **Both approaches are dead-ends on current toolchain.** Use oneMKL/oneDNN routes instead.

### PMZFX engine-comparison finding (why XMX FA matters)
- vLLM XPU crushes llama.cpp prefill 2.4x-15x purely due to XMX flash attention + varlen batching. llama.cpp SYCL FA is currently scalar FP16, no XMX. The two PRs above are the fix.
- Decode is roughly tied (llama.cpp wins on quantized due to smaller weights; vLLM wins on FP16).

---

## 3. DFlash speculative decoding on Intel — GENUINE GAP

### z-lab/dflash
- URL: https://github.com/z-lab/dflash
- Paper: arxiv 2602.06036. 5.4k stars. Block-diffusion draft model for flash speculative decoding.
- **DFlash draft model for Qwen3.6-27B EXISTS: `z-lab/Qwen3.6-27B-DFlash`** (and Qwen3.5-27B, Qwen3.6-35B-A3B, etc.).
- **Supported backends:** Transformers, SGLang, **vLLM v0.20.1+**, MLX (Apple).
- **Intel/SYCL/llama.cpp/Level-Zero support: NONE.** Zero issues, zero PRs, zero mentions of `intel`, `sycl`, `xpu`, or `arc` in the issue tracker. Confirmed via issue search `intel OR sycl OR xpu OR arc` → only 1 closed issue (#3 Evaluation).
- This is the highest-leverage untapped speculative-decoding opportunity for our goal. vLLM XPU already supports DFlash via v0.20.1+, so a TP=2/TP=4 vLLM-XPU + DFlash path is the realistic Intel route (but only for Qwen3.5-27B — vLLM XPU can't run Qwen3.6's GDN attention yet; see §5).
- The `--speculative-config '{"method": "dflash", "model": "...", "num_speculative_tokens": 15}'` vLLM pattern gives the largest known speedups. For Qwen3.5-27B on vLLM XPU this is theoretically available.

### llama.cpp native speculative (`--spec-type draft-mtp`)
- Several B70 community results use `--spec-type draft-mtp --spec-draft-n-max 3` on Qwen3.6-27B-MTP GGUFs (SleepinDevil, saurabh-deochake, WizardlyBump17). This works today on SYCL. MTP drafts are small Qwen3.6-MTP heads shipped alongside the model.
- Our own b70-optimization-lab record (95.385 tok/s TP2 Qwen3.6-27B INT4 AutoRound) uses captured MTP draft + graph-safe FA + ReplaySSM transaction fusions. The steveseguin lab is the SOTA reference for this approach.

---

## 4. Qwen3.5/3.6 GDN (Gated Delta Net) SYCL kernel issues

### GDN does NOT run on vLLM XPU
- PMZFX engine-comparison.md Finding 1: Qwen3.5 (GDN attention) crashes on vLLM XPU with `RuntimeError: PyTorch was compiled without CUDA support` from `fla/ops/chunk.py` `chunk_gated_delta_rule`. GDN needs Triton/CUDA kernels unavailable on XPU.
- **Implication:** vLLM XPU + DFlash for Qwen3.5/3.6-27B is BLOCKED until someone ports GDN to SYCL/XPU. This makes llama.cpp SYCL the only viable engine for Qwen3.6-27B GDN on Intel today.
- This is a strategic advantage for our llama.cpp lane — we have no vLLM competition for GDN on Intel.

### GDN runs fine on llama.cpp SYCL
- PMZFX: 54.5 t/s tg Q4_K_M, 784 t/s pp128 on Qwen3.5-35B-A3B (single B70).
- No GDN-specific SYCL kernel issues found in the issue tracker beyond the general MoE MUL_MAT_ID bug (#25455, see below).

### Issue #25455: MUL_MAT_ID prefill garbage on B70 (MoE only)
- URL: https://github.com/ggml-org/llama.cpp/issues/25455
- 28/792 MUL_MAT_ID tests fail on B70 in the prefill/batched path (ne12>1). Large numerical errors (0.3-1.9 vs 0.0005 tol). Decode path (ne12==1) unaffected.
- Causes garbage output on Qwen3.6-35B-A3B (MoE). Vulkan backend on same GPU produces correct output.
- NOT related to OPT/VMM/FUSION/ASYNC_MEM_OP env vars. Root cause suspected in lower-level `ggml_sycl_op_mul_mat` when fed row-gathered shapes.
- **Does not affect Qwen3.6-27B dense** (no MUL_MAT_ID), but critical if we ever swap to the MoE sibling.

---

## 5. OpenVINO GenAI for Qwen3.6 on B70

- OpenVINO GenAI repo paths tried (`openvinogenai/openvino`, `openvinogenai/openvino.genai`) returned 404 — the org/repo structure changed recently and could not be confirmed via webfetch.
- **No public benchmark of Qwen3.5/3.6 + GDN attention on OpenVINO/B70 was found** in any search. The GDN attention pattern (delta-net linear attention) is novel enough that OpenVINO's model zoo support is unconfirmed.
- PMZFX explicitly does not test OpenVINO. Hal9000 kit does not test OpenVINO.
- The IGC `joint_matrix` codegen bug on BMG (intel/llvm#21741, filed by PMZFX) and the general Xe2 kernel maturity situation suggest OpenVINO would hit the same XMX/vLLM-style limitations until oneDNN Graph matures.
- **Lower priority than llama.cpp SYCL for our goal.** Worth a quick smoke test only if we exhaust the llama.cpp lane.

---

## 6. Community B70 benchmarks & references

### PMZFX/intel-arc-pro-b70-benchmarks (76 stars, third-party SOTA reference)
- URL: https://github.com/PMZFX/intel-arc-pro-b70-benchmarks
- Hardware: 2x B70 (BMG-G31, 32GB), Ryzen 5 9600X, 60GB DDR5, Ubuntu 26.04, kernel 7.0, `xe` driver, oneAPI DPC++ 2025.3.3.
- Pinned to llama.cpp `ec6f7a6a5c` (2026-04-21) with NDEBUG + F16 SYCL accumulation.
- **Single-B70 Qwen3.5-27B numbers (pre-#25063):**
  - Q4_K_M: 718 pp512 / **20.4 tg128** / 178W / 0.11 t/J
  - Q6_K: 785 pp512 / **15.1 tg128** / 179W / 0.08 t/J
  - Q8_0: 776 pp512 / **15.3 tg128** / 166W / 0.09 t/J (post-#21527 fix)
- Qwen3.6-35B-A3B UD-Q4_K_M single-card: 615 pp512 / **54.7 tg128** / 114W / 0.48 t/J (first public Qwen3.6 data).
- **Key Finding #1 (NDEBUG trap):** shipped `llama-cpp-daily` has empty `CMAKE_CXX_FLAGS_RELEASE`, so NDEBUG never reaches the compiler. `llama-bench` prints `warning: asserts enabled`. Fixing it gives +51-180% PP. Always check `llama-bench -p 0 -n 0 2>&1 | head` for the warning before trusting numbers.
- **Key Finding #6:** tg128 is context-invariant up to 64K (decode bandwidth-bound). No decode tax for long context.
- **Key Finding #7:** KV quant penalty is model-dependent: Qwen family ~2-4%, Gemma4 31B ~8-9%.
- Upstream PRs filed by PMZFX: #21527 (Q8_0 reorder, merged), #21580 (BF16 DMMV), #21597 (multi-GPU RAM fix), #21638 (Q8_0 GEMM fix, merged), #21700 (SYCL opt bundle).
- Shelved: XMX FA via ESIMD (IGC bug intel/llvm#21741), TurboQuant SYCL port.

### Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes (23 stars)
- 4x B70 box, Threadripper 1900X. 11 cherry-picks. See §1 for patch list.

### Hal9000AIML/arc-pro-b70-inference-setup-ubuntu-server
- Bootable Ubuntu 24.04 autoinstall ISO, BIOS/hardware guide, DDR4 tuning, GuC firmware 70.60.0. Reference for standing up a box from bare metal.

### Hal9000AIML/arc-pro-b70-inference-setup-windows
- vLLM XPU TP=4 via WSL2. 540 tok/s on Qwen3.5-27B BF16 TP=4 (4x B70). Windows path.

### intel/llm-scaler (official Intel vLLM XPU)
- B70 support landed in `vllm-0.14.0-b8.2` (2026-04-22). Canonical replacement for `intel/vllm:0.17.0-xpu`.
- Persistent zero-gap MoE GEMM kernel (2 SYCL groups per Battlemage XeCore, 80%+ HW efficiency) documented at 2.6x on Qwen3-30B-A3B vs legacy XPU path on B60. B70 numbers not yet published.

### steveseguin/b70-optimization-lab (our public mirror, 21 stars)
- URL: https://github.com/steveseguin/b70-optimization-lab (note: renamed from `llm-optimizations`)
- Our own Qwen3.6-27B INT4 AutoRound record: **95.385 tok/s TP2** (2x B70), strict fresh-response, graph-safe FA full target graph, ReplaySSM transaction fusions, pinned public oneCCL. LocalMaxxing submission `cmrh35ct50092mj01h7jgydqj`. Short-context-only.
- Gemma4-26B-A4B-Q8 single-B70: ~125 tok/s repro.

### ipex-llm (ARCHIVED — do not use)
- Intel archived `intel/ipex-llm` 2026-01-28 (security issues). Community fork `ipex-llm/ipex-llm` still ships Battlemage quickstart + portable zips.

---

## 7. hipfire-style / FWHT / lean-engine techniques on Intel

- **No public work found** on FWHT weight rotation (MQ4-style), fused projections in SYCL/ESIMD, or custom lean inference engines for Intel Xe2.
- PMZFX shelved TurboQuant SYCL port (identified scope, parked).
- PMZFX XMX-via-ESIMD prototype hit IGC bug (intel/llvm#21741) — the only documented ESIMD XMX attempt, and it's blocked on Intel.
- This is genuinely greenfield. Our `prototypes/` and `experiments/` lanes (ggml-backend-meta.cpp layer per Hal9000 note) are the deepest public attempts. Hal9000 explicitly calls out our negative-result writeups (small-F32 allreduce regression, oneCCL topology toggle, MiniMax MUL_MAT_ID mask path) as worth reading before retrying those directions.

---

## 8. Critical open B70 stability issues (must-know)

### Issue #24810: SYCL server hangs indefinitely on GPU device loss
- URL: https://github.com/ggml-org/llama.cpp/issues/24810
- SYCL backend never detects xe-driver "Timedout job"/"Engine reset" — busy-waits in `sched_yield()` forever, `/health` stays up but `/slots` + `/completions` hang. Only recoverable via SIGKILL.
- Vulkan correctly surfaces `VK_ERROR_DEVICE_LOST`.
- Root cause upstream of llama.cpp (drm/xe GuC firmware). Filed at gitlab.freedesktop.org drm/xe kernel work_items/8390.
- PR #25089 (graph capture for MoE) reduces GuC reset frequency from 81-212s to 207s+ clean, but does not fix the detection gap.
- **Operational implication:** run an external watchdog on `/slots` liveness for any SYCL B70 production server.

### Issue #25286: UR_RESULT_ERROR_DEVICE_LOST + OUT_OF_DEVICE_MEMORY on dual B70
- URL: https://github.com/ggml-org/llama.cpp/issues/25286 (open)

### Issue #25423: 20+ minute load times with SYCL tensor parallelism
- Closed as "not planned" — not a bug per the maintainers.

---

## 9. Priority-ordered action list for maximum single-B70 Qwen27 decode

1. **Confirm merged #25063 is in our pinned build.** If not, rebaseline Q4_K_M/Q5_K_M/Q6_K. Expected ~1.5-1.85x tg jump on dense K-quants. This is the single highest-ROI item.
2. **Verify our build has `-DCMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG"`** (PMZFX Finding #1). Check `llama-bench -p 0 -n 0 2>&1 | head` for the asserts warning.
3. **Do NOT carry `GGML_SYCL_DISABLE_OPT=1` into the dense Qwen27 lane.** That env var is MoE-only and costs ~5% on dense + blocks the reorder wins from #25063.
4. **Consider switching to Q5_K_M as the decode-optimal quant** given #25063's 1.853x specifically on Q5_K_M (22.53 tg baseline, higher with MTP).
5. **Layer in `--spec-type draft-mtp` with the Qwen3.6-27B-MTP GGUF** on SYCL if not already — our own lab record uses this to 95 tok/s TP2. Single-card should scale proportionally.
6. **File a z-lab/dflash feature request for Intel/SYCL/llama.cpp backend support.** No issue exists. The DFlash draft model for Qwen3.6-27B already exists; only the backend is missing. This is the largest speculative-decoding lever we are not using.
7. **Track #25222 and #25025 for merge** (XMX FA). Neither helps decode, but if we ever care about prefill/long-context, they close the 15x vLLM gap. #25025 (oneMKL, quantized KV) is safer; #25222 (oneDNN, f16 KV) has the multi-turn correctness bug already diagnosed by johnkarlhill.
8. **Engage hmscider on #25203** (Q8_0 reorder PP regression) if we push Q8_0 — he's offering to write the fused s8xf16 kernel.
9. **Run an external `/slots`-liveness watchdog** on any SYCL B70 server (#24810).
10. **Quick-test OpenVINO GenAI + Qwen3.6 GDN on B70** only if the llama.cpp lane is exhausted. Low expected value given GDN novelty + IGC XMX immaturity.

---

## Sources index

- llama.cpp SYCL PRs/issues: search `sycl b70 OR battlemage optimization` on github.com/ggml-org/llama.cpp
- PMZFX: https://github.com/PMZFX/intel-arc-pro-b70-benchmarks (FINDINGS.md, engine-comparison.md, upstream-contributions.md, llm-benchmarks.md)
- Hal9000: https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes
- DFlash: https://github.com/z-lab/dflash
- Our lab: https://github.com/steveseguin/b70-optimization-lab
- localmaxxing Qwen3.6-27B: https://localmaxxing.com/en/models/Qwen/Qwen3.6-27B (254.8 tok/s top speed cited; table JS-rendered, single-B70 rows not isolatable from fetch)
