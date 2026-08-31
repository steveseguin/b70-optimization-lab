# Qwen3.8 INT4 M=1→2 determinism repair D33 preregistration

Date: 2026-08-31

Status: **preregistered before the D33 candidate build or model requests**

## Frozen repair

Apply patch SHA-256
`1ffbdc4b0e1220011dfa77d859c2c625d5d4896117c0fe221a5f163bc2ba044e`
to vLLM XPU kernels commit
`1e90ffa672ba02f17a909da11838a4c55b199783`. It preserves the existing
M=129..511→512 repair and additionally pads only INT4 M=1 to M=2 with one
zero row, returning row 0.

Build from immutable base image
`sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b`
using oneAPI 2026.1.1, one compiler job, and the hash-gated reproduction
script. The candidate tag is
`neural-download/vllm-openai-xpu:qwen38-autoround-m1pad2-deterministic-r1`;
its resulting image ID must be recorded after the build.

## Required gates

1. Repeat the production layer-0 call-2 boundary across four fresh processes;
   hidden input, normalized projection input, and `out_proj` must be bit-exact.
2. Run the full strict varied-prompt determinism/quality suite with no prefix,
   prompt, response, or n-gram caching and compare against the independent
   unoptimized expected-output attestation.
3. Measure the strict cold realistic-suite decode rate and compare against the
   frozen current-image control using class-balanced medians. Do not publish a
   fixture, warm-continuation, or single-prompt number.
4. Measure operator and server overhead. A deterministic candidate that passes
   quality but materially regresses decode should be optimized before
   promotion.

No speed or correctness claim is authorized until all applicable gates pass.
