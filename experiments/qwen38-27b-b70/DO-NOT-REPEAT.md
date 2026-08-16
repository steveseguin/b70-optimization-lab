# Qwen3.8 27B do-not-repeat index

Last audited: 2026-08-16

This is the first stop before creating another Qwen3.8 27B optimization arm.
Do not rerun a closed experiment unchanged. A retry needs a materially different
model revision, compiler/runtime, kernel implementation, execution shape, or a
specific explanation of why the earlier result no longer applies.

For a clean-clone reproduction and cross-machine coordination protocol, use
the [multi-host handoff](MULTI-HOST-HANDOFF.md).

## Qwen3.8-specific work

| Experiment | Outcome | Durable record |
| --- | --- | --- |
| Q8 lossless repacking | Closed: practical sentinel formats expanded the weights; theoretical entropy headroom was only about 3.7% | [structural audit](notes/2026-08-16-q8-structural-feasibility-and-sampling.md) |
| Q8 two-chain DP4A (`DP4A2`) transfer | Quality-exact, but no repeatable Qwen3.8 endpoint gain; the promoted snapshot intentionally retains one-chain DP4A | [note](notes/2026-08-16-q8-dp4a2-transfer-no-win.md) |
| TP2 collective census | 128 already-fused boundaries/token; synchronization, not transferred bytes, is the target | [structural audit](notes/2026-08-16-q8-structural-feasibility-and-sampling.md) |
| Tensor-split backend sampling | Closed: llama.cpp fell back to CPU, so no GPU treatment was executed | [structural audit](notes/2026-08-16-q8-structural-feasibility-and-sampling.md) |
| Fused Q8 MMVQ + SwiGLU | Rejected performance regression | [note](notes/2026-08-16-q8-fused-mmvq-swiglu-negative.md), [data](data/2026-08-16-q8-fused-mmvq-swiglu-negative.json), [patch](patches/q8-fused-mmvq-swiglu-v2-negative-20260816.diff.gz.b64) |
| Concurrency-2 cache-row fusion | Exact mechanism, endpoint-neutral; not promoted | [note](notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md), [data](data/2026-08-16-q8-c2-cache-row-fusion-neutral.json), [patch](patches/q8-c2-cache-row-fusion-neutral-20260816.diff.gz.b64) |
| Distributed greedy argmax | Exact but primary throughput neutral and TTFT worse; not promoted | [note](notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md), [data](data/2026-08-16-q8-distributed-greedy-argmax-neutral.json), [patch](patches/q8-distributed-greedy-argmax-neutral-20260816.diff.gz.b64) |
| Level Zero v2 selector | Already the runtime default; explicit pin is reproducibility-only. Legacy was 3.375% slower | [note](notes/2026-08-16-q8-level-zero-v2-adapter-audit.md), [data](data/2026-08-16-q8-level-zero-v2-adapter-audit.json) |
| Peer-pair cross-device output writes, mode 3 | **Unsafe: device-lost/reset storm. Never retry on this stack** | [note](notes/2026-08-16-q8-peer-pair-collective-unsafe.md), [data](data/2026-08-16-q8-peer-pair-collective-unsafe.json), [quarantined patch](patches/q8-peer-pair-collective-device-lost-unsafe-20260816.diff.gz.b64) |
| Root-fused per-owner handoff, mode 4 | Safe and exact at the benchmark gate, but rejected: `-3.388%` decode because the longer root critical path serialized device 1 | [result](notes/2026-08-16-q8-root-fused-candidate-negative.md), [data](data/2026-08-16-q8-root-fused-candidate-staged.json), [patch](patches/q8-root-fused-collective-untested-20260816.diff.gz.b64) |
| Public GPTQ INT4 + native MTP | Performance reproduced, but GPTQ target failed a deterministic semantic canary; not the no-loss lane | [community decision](../../community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md) |

## Transferred Q8 search history

Qwen3.8 inherited the accepted Qwen3.6 Q8/SYCL source stack. Its exhaustive
pre-transfer search is preserved in two chronological notebooks:

- [pass 1](../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md): topology,
  runtime/Level Zero knobs, split ratios, subgroup layouts, root scheduling,
  large-batch reorder settings, attention, GDN, SSM, and the original direct-Q8
  quality boundary;
- [pass 2](../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass2.md): 70+ bounded
  source/runtime experiments covering direct Q8, root vectors, V-cache writes,
  Q/K RoPE/RMS fusions, compiler versions, output head, graph/queue paths,
  memory/cache policies, DP4A schedules, and the accepted exact stack.

Those notebooks record the hypothesis, command/configuration, measurements,
quality result, raw-artifact path, and disposition. Promoted mechanisms were
rolled into the public Qwen3.8 patch; rejected mechanisms remain closed unless
the retry rule at the top is satisfied.

## Local source-tree alias map

Some retained `/mnt/fast-ai/src/llama.cpp-*` directories use short names. They
are not undocumented experiments; map them to these notebook sections:

| Local alias | Recorded experiment and disposition |
| --- | --- |
| `q8-tp2-compiler2025` | pass 2: oneAPI 2025.3 compiler arm; rejected because the BMG matrix path was unavailable |
| `q8-tp2-counters-off` | pass 2: diagnostic Q8 census atomics; performance-null |
| `q8-tp2-counters-off-incomplete-20260815` | incomplete filesystem copy, not a benchmark result; never use as source |
| `q8-tp2-directq8-clean` | pass 2: clean-source promotion replay |
| `q8-tp2-fattn-nt96` | pass 2: D=256/GQA6 TILE workgroup 96; rejected |
| `q8-tp2-graph-record-queue` | pass 2: isolated-queue SYCL graph; dependency repaired but unusable |
| `q8-tp2-outputhead-sg32` | pass 2: shape-scoped output-head SG32; exact and performance-null |
| `q8-tp2-reduce-vec2-exp` | pass 2: two-float TP root vector; neutral |
| `q8-tp2-vcache-fused` | pass 2: direct V-cache write; quality-exact and rejected for performance |
| `q8-tp2-virtualn5` | pass 2: allocation-free virtual-n5 MMVQ; rejected |
| `q8-tp2-dp4a2` | pass 2: accepted for Qwen3.6; exact but not faster in two Qwen3.8 cold suites, so not promoted there |
| `q8-tp2-dp4a4` | pass 2: four-chain DP4A ILP; performance-null |
| `q8-tp2-dp4a-adj` | pass 2: adjacent-pair DP4A schedule; rejected |
| `q8-tp2-rows2` | pass 2: two Q8 output rows per SG16; performance-null |
| `q8-tp2-scale-early` | pass 2: early Q8 scale materialization; regression |
| `q8-tp2-qknormrope-wg16` | pass 2: single-subgroup Q/K RMS+scale+RoPE; short-gate positive and incorporated into later accepted testing |
| `q8-tp2-reduce-vec4` | pass 2: vectorized TP root reduction; promoted after clean replay |
| `q8-tp2-vcache` | pass 2: direct attention V projection-to-cache write; exact but rejected |

## Evidence retention boundary

The repository contains durable decisions, structured summaries, hashes, and
the exact Qwen3.8-specific source patches—including the unsafe patch so its
design can be recognized. Large raw logs and many historical build trees remain
under `/mnt/fast-ai`; not every raw byte or rejected historical build artifact
is duplicated in Git. The notebook paths and SHA-256 values are the audit trail.
