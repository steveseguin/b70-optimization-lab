# Pre-registration: INT4 AutoRound tensors on the plain-GPTQ XPU kernel, R212 (unpadded) and R213 (determinism pad)

Written 2026-09-04 before either campaign ran. Directive: make the INT4 lane deterministic and lossless first, then run
the full spectrum, then optimize.

## Identity
- Tensors: devan-carlin/Qwen3.8-27B-int4-AutoRound bce40cac, unchanged (hard-linked (same filesystem; symlinks are invisible inside the container) into
  `/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel`; manifest
  `repro/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json`, verified O_DIRECT).
- Config relabelled to plain gptq so vLLM selects `XPUwNa16LinearKernel` (`_xpu_C.int4_gemm_w4a16`) instead of INC/ARK.
- Stack: the R187 whole-graph deterministic profile (splitting_ops=[], deterministic inductor, no autotune), TP2, MTP0
  oracle pair then MTP depth 4 pairs, then the ladders; runner r152 via `scripts/run-20260904-qwen38-int4-gptq-relabel-r212-full.sh`
  (r156 image 173660ec) and `...-r213-detpad-full.sh` (r213 image 3f34e5d5).

## Predictions
1. R213 G1 (same-config MTP0 repeat pair): 12/12. The only known nondeterminism of this kernel is the 128 < M < 512
   band, which the pad removes; everything else in the R187 stack was repeat-exact on FP8.
2. R212 G1 (no pad): may fail only if a strict prompt's prefill chunk lands in the dirty band; it is run first as the
   control that localizes any failure to that band. If R212 passes 12/12 the pad is still kept for the ladders (2K-32K
   prompts produce in-band chunks).
3. G3 (MTP depth 4 vs MTP0 oracle): 12/12 lossless, because the kernel is row-invariant for M <= 8 (verify rows =
   depth+1 = 5) and the rest of the R187 stack is already batch-invariant on FP8. This is the prediction that matters;
   ARK could never satisfy it.
4. Rate: MTP0 at or above the ARK 32.8 tok/s only if the idle-GPU M=1 cost of int4_gemm_w4a16 is at or below ARK's
   GEMV; the contaminated R212 timings suggest it is slower at M=1 but flat to M=8, so MTP depth 4 should scale far
   better than on ARK (community single-card GPTQ: 32.9 -> 83.7 tok/s at depth 4).

## Disconfirmation
- If R213 G1 fails, the fault is outside the GEMM (compare per-prompt divergence indices against the R209 pattern).
- If G3 fails with G1 passing, the row-variance is elsewhere (GDN/attention kernels at M=5) and the FP8 lane's
  batch-invariant settings need porting to this path.
