# Patch Record: BF16 MUL_MAT_ID multi-token fast path (negative)

Status: reverted after crash; not promoted.

Tried source patch in `/home/steve/src/llama.cpp-gemma-record-repro-c926`:

- env gate: `LLAMA_SYCL_MUL_MAT_ID_BF16_MULTI_TOKEN_FAST=1`;
- direct BF16 multi-token `MUL_MAT_ID` SYCL kernel for Gemma final-layer
  verifier MoE gate/up;
- graph eligibility hook for BF16 `MUL_MAT_ID`.

Validation:

- A/B stamp: `20260628T023623Z`;
- controls passed at `95.0-98.1` median tok/s;
- both BF16 lanes aborted before readiness with
  `stream->memcpy(ids_host.data(), ids_dev, ids_nbytes)` failure in
  `ggml_sycl_mul_mat_id`;
- filtered and graph-off smoke diagnostics also aborted.

Artifacts:

- Experiment note:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0236-bf16-mulmatid-fast-crash.md`
- Failed run dirs:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bf16fastA-n3-nmin2-p00475-ub1024-20260628T023623Z/`,
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bf16fastB-n3-nmin2-p00475-ub1024-20260628T023623Z/`.

Reason to keep record:

This was a plausible hotspot from the strict node profile, but it is not safe
as a full-server patch. Future attempts should isolate BF16 `MUL_MAT_ID`
correctness outside the server or add immediate kernel error synchronization
before trying record-gate benchmarks.
