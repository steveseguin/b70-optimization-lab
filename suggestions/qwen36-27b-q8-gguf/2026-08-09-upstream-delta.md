# Upstream delta scan — 2026-08-09

This is research intake, not local performance evidence. Reported upstream
rates and mechanisms become local claims only after the lane's exactness and
endpoint gates pass.

## Highest-value new discriminators

1. **SYCL flash-attention decode selector.** Open, approved
   [llama.cpp PR #26689](https://github.com/ggml-org/llama.cpp/pull/26689)
   adds `GGML_SYCL_FA_DECODE_KERNEL=0/1/2`. Its default policy chiefly changes
   quantized KV, but forced VEC versus TILE also provides a cheap F16-KV
   long-context discriminator. Screen one isolated 32K c1 exact A/B first;
   promote to c2 only if outputs and turnover canaries remain exact.
2. **Q/K preparation fusion.** Merged
   [llama.cpp PR #26767](https://github.com/ggml-org/llama.cpp/pull/26767)
   fuses RMSNorm, multiplication, and RoPE in CUDA. Qwen3.6 applies related Q/K
   work in every full-attention layer. This is a transfer lead, not a SYCL win:
   profile the complete boundary and port only if its critical-path share can
   support a material endpoint gain.
3. **Gate/up/GLU fusion as a Q8 research lead.** Draft
   [llama.cpp PR #26779](https://github.com/ggml-org/llama.cpp/pull/26779)
   shares activation quantization and avoids intermediates, but currently
   rejects weight types other than Q4_K. Measure the target Q8_0 M=1/M=2
   gate/up/GLU boundary before considering a Q8 trait or kernel extension.

## Useful methodology and lower-priority screens

- Merged [vLLM PR #51458](https://github.com/vllm-project/vllm/pull/51458)
  used an error-on-synchronization audit to find per-forward host/device waits.
  Apply the method to a retained SYCL trace; do not assume its concrete changes
  transfer to this llama.cpp text path.
- Open [vLLM PR #51526](https://github.com/vllm-project/vllm/pull/51526)
  removes a full-vocabulary softmax from one sampler formulation. Revisit only
  if sealed profiles show sampling/logit processing is material and prove
  same-noise token identity first.
- Open [llama.cpp PR #26789](https://github.com/ggml-org/llama.cpp/pull/26789)
  adds optional SYCL host-pinned buffers. The fully offloaded steady-state lane
  should not prioritize it unless profiling finds unexpected bulk pageable
  transfers after readiness.

No post-cutoff Intel compute-runtime, IGC, Intel LLVM/SYCL, Level Zero,
oneDNN, or llm-scaler change supplied evidence for changing the pinned driver
or toolchain. Keep runtime upgrades separate from the first source comparisons.

## Screened out in this scan

- vLLM's KDA prefill synchronization change says GDN already uses its host-side
  metadata path.
- NVIDIA activation-quantization fusion is not a direct match for this
  weight-only GGUF Q8 identity.
- Direct GDN writeback PR #26643 had no new status or code delta.

Next delta scan should start from these PR states rather than repeating a full
search.
