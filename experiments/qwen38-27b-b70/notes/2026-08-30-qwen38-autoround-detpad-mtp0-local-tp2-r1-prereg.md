# Qwen3.8-27B AutoRound INT4 deterministic MTP0 local TP2 r1 preregistration

Date: 2026-08-30
Status: frozen before the first model request

## Question

Does the oneDNN W4A16 determinism-padding fix, combined with the already frozen
GDN, oneCCL, recurrent-state, and deterministic-Inductor treatments, make the
local two-B70 AutoRound INT4 MTP0 parent repeat exactly without changing the
eager target output?

This is correctness recovery before renewed optimization. It is not an MTP
result, aggregate-throughput result, record attempt, or permission to publish a
speed. The historical 101.17 tok/s MTP5 research row remains separate.

## Frozen identity

- host `steve-TURIND8-2L2T`, physical GPUs 0 and 1, TP2;
- local ext4 model directory
  `/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround`;
- model manifest
  `../../../repro/qwen38-27b-autoround-int4-b70/manifests/model.json`, SHA-256
  `731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8`;
- image
  `neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1`,
  ID `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- base image ID
  `sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b`;
- XPU-kernels source `1e90ffa672ba02f17a909da11838a4c55b199783`;
- determinism patch SHA-256
  `8237fd2a5f11c772269275598bc005d7a146f86de741cef753fc0ec74cb1a408`;
- wheel SHA-256
  `823615350c5344532f63dde8652b291d7b9d6815a209121c97f2fcfac09474c5`;
- `_xpu_C.abi3.so` SHA-256
  `c5e9c9a505f64e0e4be819191ef091c09bfb2af153c6c7c341c80e8ebed2e620`;
- paired GDN library SHA-256
  `2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355`;
- dense Xe2 feature surface: GDN, MQA, and MHC; no unused MoE grouped GEMM;
- AutoRound/INC W4A16, FP16 activation and KV, MTP0, XPU Graph off,
  `cudagraph_mode=NONE`, deterministic Inductor on, prefix caching off,
  temperature 0, seed 42, one sequence;
- realistic 12-prompt/six-class suite SHA-256
  `df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`,
  each prompt exactly once, natural EOS required, token IDs returned, cached
  tokens required to be zero.

Before preregistration, the final image passed the operator-only gate recorded
in `../data/2026-08-30-qwen38-autoround-detpad-operator-r3.json`: 0/200
mismatches at each M in 6, 8, 16, 32, 64, 128, 256, 341, 512, and 1024;
the independent M341-to-M512 pad test had row independence and 0/500 unstable
runs. Those results authorize this model campaign but are not model evidence.

## Ordered campaign

1. Fresh eager MTP0 oracle, with new compile-cache and evidence roots.
2. Only if eager passes every workload and canary gate, fresh compiled MTP0 A.
3. Only if A is 12/12 token-array exact to eager, fresh compiled MTP0 B.
4. Compare complete token arrays. Qualification requires compiled A and B to
   be 12/12 exact to eager and exactly equal to each other.

Every arm must independently pass direct model verification, image and binary
identity gates, INC quantization detection, both TP workers, no graph capture,
all 12 strict rows, median-of-class-medians over intervals 1--100 after TTFT,
zero cached tokens, natural EOS, the independent canary battery, bounded
cleanup, and no new GPU/kernel/OOM fault. A fixture, prompt reuse, response
reuse, prefix caching, early-EOS exception, incomplete row, or one good repeat
cannot pass.

On any failure the campaign stops and preserves evidence. A complete pass
qualifies only this deterministic MTP0 parent. MTP1+, concurrency, long context,
and public performance each require separate preregistration and gates.

Executables:

- `../scripts/run-20260830-qwen38-autoround-detpad-mtp0-local-tp2-r1.sh`
- `../scripts/run-qwen38-autoround-deterministic-mtp0-campaign.sh`
- `../scripts/run-20260828-qwen38-autoround-deterministic-mtp0-strict-attempt.sh`
- `../../../repro/qwen38-27b-autoround-int4-b70/scripts/run-current-deterministic-mtp0-server.sh`

## Pre-execution exclusions

No model request has run with this image. Earlier work in this build root
failed before image creation due to an incomplete feature build, two bounded
compiler OOMs, and a marker-pipeline finalization bug. A first operator probe
then failed before kernel execution because its harness used an obsolete
eight-argument ABI. These are build/harness failures, not benchmark attempts.
The corrected seven-argument operator probe and final image passed as recorded
above.
