# Qwen3.8 27B B70 bring-up checkpoint

Date: 2026-08-15

This note coordinates the initial Qwen3.8 27B bring-up on the two-card ASRock
Arc Pro B70 host. It is not a promoted benchmark result.

## Source artifacts

- Official model: `Qwen/Qwen3.8-27B`, revision
  `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Official FP8 model: `Qwen/Qwen3.8-27B-FP8`, revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`.
- Source-pinned GGUF conversion: `ggml-org/Qwen3.8-27B-GGUF`, revision
  `0669b98607d47046c7c2b3f801011d54a08cfccf`.
- GGUF target Q8 SHA-256:
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`.
- GGUF MTP Q8 SHA-256:
  `cbf60a0c48b431bb61f1d49b8948dc88ac29c398d6dbdbbb2e6e89ef77eacc9a`.
- GGUF target Q4_K_M SHA-256:
  `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`.
- GGUF MTP Q4_0 SHA-256:
  `051a1764cff8c4f3ee6ae8b00593a0364c7539c67fa50ffc58f3f96509fca38e`.

The model continues to identify as `Qwen3_5ForConditionalGeneration` /
`qwen3_5`. Its text core retains the 64-layer, three Gated DeltaNet layers to
one full-attention layer layout and one native MTP layer. This makes the
Qwen3.6 work a direct portability candidate, but every carried patch still
requires output-token/hash validation.

No Qwen3.8 DFlash checkpoint was present in the Hugging Face index at this
checkpoint. Do not substitute a differently trained community draft and call
it a Qwen3.8 DFlash result.

## Local artifact paths

- GGUF downloads:
  `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf`
- Official FP8 download:
  `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8`

Downloads are revision-pinned. Record final byte sizes and SHA-256 values
before any benchmark promotion.

## Host/runtime audit

- two ASRock Arc Pro B70 cards, both healthy and bound to `xe`;
- kernel `7.0.0-28-generic` is the current Ubuntu HWE candidate;
- `intel-omix` / `intel-omix-dev` `0.3.0-9` are current in the configured OMIX
  0.3 repository;
- compute runtime `26.22.38646.7-9`, Level Zero loader `1.28.6`, and
  `linux-firmware` Ubuntu revision `.29` are installed candidates;
- oneAPI compiler `2026.1` is installed, but it is an ABI-breaking SYCL
  release. Never mix binaries built against older SYCL runtimes in the same
  process.

Do not replace the validated OMIX package set with generic PPA packages merely
because a component has a numerically newer version.

## Transfer plan

1. Run an unmodified accepted Qwen3.6 TP2 binary against Qwen3.8 Q8 as a
   compatibility/control measurement.
2. Build current upstream llama.cpp in a fresh tree. Since the prior pinned
   upstream base, relevant additions include Q4_K dense FFN fusion, GDN state
   writeback fusion, SYCL unary-plus-multiply fusion, broader quantized concat,
   and MTP assistant auto-detection.
3. Port the accepted Qwen3.6 target-only patch stack by subsystem, not as a
   blind monolithic patch: TP2 recurrent anchoring and collectives first, then
   recurrent/attention fusions, then the two-chain DP4A Q8 MMVQ kernel.
4. Use Qwen3.8 native MTP only as a separately labeled lane. The target-only
   goal remains 40 tok/s; MTP results cannot be used to claim that goal.
5. Evaluate the official FP8 checkpoint with a pinned vLLM/XPU stack. Upstream
   vLLM `v0.27.1` and `vllm-xpu-kernels v0.1.13` are current, while Intel's
   currently documented B70 Qwen3.5/3.6 image remains
   `intel/llm-scaler-vllm:0.14.0-b8.3.1`. Treat Qwen3.8 support as unvalidated
   until a local correctness gate passes.

## Safety and validity

This host has 15 GiB RAM. Never overlap compilation and a loaded model. Keep
builds at `-j2` under the existing 6/8 GiB memory scope and workloads under the
existing 8/10 GiB scope. Every promoted comparison must use cache-zero cold
requests, exact token/output gates, and the same conventional timing definition
as the Qwen3.6 model board.
