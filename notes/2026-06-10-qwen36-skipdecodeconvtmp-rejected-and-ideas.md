# Qwen3.6 35B Quark W8A8: skip decode conv tmp rejected and idea intake

Date: 2026-06-10

## Current accepted target

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Runtime: vLLM XPU TP4, Quark W8A8 INT8, 32K context, no prefix caching, XPU graph piecewise capture.
- Accepted local optimization: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`.
- Accepted speed band for p512/n512 single request: about `99.3-99.8` corrected after-first-token tok/s.
- Quality baseline: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-frontdoor-quality-rerun32-20260610.json`.

## Candidate rejected: skip decode conv state temp allocation

Hypothesis:

During decode, the GDN causal conv path updates `conv_states` in-place and should not need `conv_states_tmp`, which is used by the prefill path. Avoiding one `torch::empty` per native GDN decode call looked like a no-math-change optimization.

Implementation tested:

- Added opt-in `VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP=1`.
- Changed `causal_conv1d.hpp` to allocate `conv_states_tmp` only if `num_prefills > 0` or the opt-in was disabled.
- Built and installed `_xpu_C.abi3.so` and `libgdn_attn_kernels_xe_2.so`.
- Startup reached `/health`; frontdoor exact-OK smoke passed.

Result:

- Artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-skipdecodeconvtmp-single-r4-20260611.json`
- Corrected after-first-token mean: `99.2681 tok/s`
- E2E output mean: `97.9341 tok/s`
- TTFT mean: `80.33 ms`

Decision:

Reject. It is slightly below the accepted `clone` controls and not worth quality/reliability validation.

Restore lesson:

The Python extension `_xpu_C.abi3.so` resolves helper libraries from `/home/steve/src/vllm-xpu-kernels/build/temp`, not only from `vllm_xpu_kernels/`. Restoring only the package `.so` files left stale experimental helper libs in `build/temp`, causing `_xpu_C` import segfaults and silent vLLM startup exits. Restore procedure must sync the package helper libs into `build/temp` or rebuild a clean accepted install before relaunching.

Restore control:

- Frontdoor exact-OK smoke passed after restoring the accepted binaries and launching with `scripts/launch-qwen36-quark-int8-accepted.sh`.
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-restore-after-skipdecodeconvtmp-single-r4-20260611.json`
- Corrected after-first-token mean: `99.0073 tok/s`
- E2E output mean: `97.6622 tok/s`
- TTFT mean: `81.31 ms`

Launcher lesson:

Serving should not source oneAPI `setvars.sh` by default. In this lab state, that pushed a SYCL-9 runtime into the serving process and triggered oneCCL/SYCL startup crashes. The accepted launcher puts the editable `vllm-xpu-kernels` package path and the venv/PyTorch libraries first, so serving resolves the stable helper libraries and SYCL-8 runtime that the accepted binaries were built and smoked with.

## External idea intake

Sources reviewed:

- vLLM Intel Arc Pro B-Series blog: https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
- vLLM issue on 30B+ B580 XPU arguments: https://github.com/vllm-project/vllm/issues/35638
- vLLM issue on dual B70 TP=2 FP8 GP fault: https://github.com/vllm-project/vllm/issues/41663
- B70 Ubuntu setup repo: https://github.com/Hal9000AIML/arc-pro-b70-inference-setup-ubuntu-server
- B70 speedup/tuning repo: https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes
- B70 benchmark repo: https://github.com/PMZFX/intel-arc-pro-b70-benchmarks
- Intel ai-containers vLLM XPU docs: https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md
- Intel llm-scaler issue on Qwen3.6-35B-A3B FP8 on 2x B70: https://github.com/intel/llm-scaler/issues/382
- vLLM XPU supported-model docs: https://docs.vllm.ai/en/v0.18.0/models/hardware_supported_models/xpu/
- Localmaxxing public API snapshots saved to `data/localmaxxing-b70-qwen36-like-filtered-20260611.json`.

Useful points:

- Intel's vLLM Arc Pro blog emphasizes MoE performance work around a persistent single-kernel loop, dynamic work-group balancing, and prepacked low-bit conversion. This strongly suggests the biggest remaining no-quality-loss speed path is MoE token-generation kernel efficiency, not Python-side allocation trimming.
- Intel's example environment targets a validated host stack rather than arbitrary Ubuntu/kernel/firmware mixes. The dual-B70 issue documents TP failures on Ubuntu 24.04 HWE 6.17 and notes Intel validation differs. A host-stack A/B remains a large opportunity.
- B70 community tuning emphasizes sysfs driver tuning: raise `job_timeout_ms`, raise `preempt_timeout_us`, pin GT min/max to `rp0_freq`, and force PCIe ASPM performance policy. We should audit our host instead of assuming it is already pinned.
- The B70 tuning repos repeatedly point at fused MoE token-generation work as high leverage. Llama.cpp reports large wins from fused MoE MMVQ/token-generation kernels; our model is MoE and our timing already shows forward-pass/GDN/MoE dominates.
- Localmaxxing has no exact rows for `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`. Filtered B70 + Qwen3.6-like rows are mostly lower than our accepted W8A8 result, but many are different quantization/engine/model variants. Do not publish until we have a clean stable r8 result, quality artifact, exact command snippet, and Localmaxxing dry-run validation.
- PMZFX's public B70 benchmark repo reports Qwen 3.6-35B-A3B UD-Q4_K_M at `54.7 t/s` on one B70 and Q8_0 at `36.5 t/s` on two B70s. That is not an apples-to-apples quality target, but it makes our current `~99 tok/s` TP4 W8A8 result plausible rather than obviously broken.
- Intel's public XPU vLLM docs advertise FP8 W8A16 as the supported hardware-accelerated quant path. Our current W8A8 INT8 path is local/patched, so the next performance win probably comes from kernel work or Intel's private/newer stack rather than a simple upstream flag.
- The llm-scaler Qwen3.6-35B FP8 issue is still open, which reinforces that Qwen3.6 35B on B70 is not a solved turnkey path even in Intel's own container stack.

## Future candidates to try

1. Audit XPU graph/driver state before every accepted run.
   - Explicitly set `VLLM_XPU_ENABLE_XPU_GRAPH=1`.
   - Add a preflight import test for `torch.xpu.is_available()` and `vllm_xpu_kernels._xpu_C`.
   - Add a restore helper that syncs helper libs into both package and `build/temp`.

2. Host tuning audit.
   - Snapshot `job_timeout_ms`, `preempt_timeout_us`, GT `min_freq/max_freq/rp0_freq`, ASPM policy, GuC firmware, kernel, KMD, oneAPI, oneCCL.
   - If not pinned, test pinning GT clocks and xe timeouts before further kernel work.
   - Compare the host against Intel's documented vLLM setup assumptions and the B70 community tuning repos before drawing conclusions from kernel experiments.

3. MoE decode kernel path.
   - Profile fused MoE token-generation kernels without synchronization-heavy timing.
   - Compare our vLLM/vllm-xpu-kernels tree with Intel's newest LLM-Scaler/vLLM XPU stack for persistent MoE and dynamic group scheduling.
   - Look for a native W8A8/FP8 fused grouped-GEMM path for XPU rather than per-token overhead reductions.
   - Specifically inspect whether our current INT8 MoE backend has the persistent-loop/dynamic-work-balancing properties described by Intel's Arc Pro vLLM work.

4. Exact greedy logits path.
   - Timing showed `compute_logits` plus local argmax is measurable. For greedy throughput runs, investigate a quality-preserving top-1-only path that avoids unnecessary logits materialization, with strict JSON/text parity checks.

5. Speculative/MTP only if verified.
   - Localmaxxing high Qwen3.6 results often use DFlash/MTP/speculative decoding. This can only be considered if acceptance/rejection is exact and the quality harness proves no degradation for our target workload.

6. Localmaxxing publishing path.
   - Query public comparables first.
   - Use `/api/benchmarks/dry-run` with the API key only after a stable quality-validated result.
   - Submit only if the result is accurate, reproducible, and worth publishing.
