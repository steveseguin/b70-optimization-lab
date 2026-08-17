# Qwen3.8 27B do-not-repeat index

Last audited: 2026-08-17

This is the first stop before creating another Qwen3.8 27B optimization arm.
Do not rerun a closed experiment unchanged. A retry needs a materially different
model revision, compiler/runtime, kernel implementation, execution shape, or a
specific explanation of why the earlier result no longer applies.

For a clean-clone reproduction and cross-machine coordination protocol, use
the [multi-host handoff](MULTI-HOST-HANDOFF.md).

## Qwen3.8-specific work

| Experiment | Outcome | Durable record |
| --- | --- | --- |
| Exact 11-bit reordered-Q8 scale dictionary, compile-time 10-bit encoder maps | Closed: prompt+decode safety gate passed and removed the runtime-USM failure, but the position-balanced screen regressed `5.360%` (`35.028804` versus `37.012538 tok/s`). Bit unpack/table decode cost exceeded the 1.838% traffic saving; no quality or endpoint promotion | [result](notes/2026-08-17-q8-exact-scale-dictionary-static-map-active.md), [data](data/2026-08-17-q8-exact-scale-dictionary-static-map-negative.json), [increment](patches/q8-exact-scale-dict11-static-map-negative-20260817.diff) |
| Exact 11-bit reordered-Q8 scale dictionary | Closed: the slow revision passed only a one-token smoke but had multi-minute setup; direct lookup revisions failed with SIGSEGV and then `UR_RESULT_ERROR_INVALID_MEM_OBJECT`. GPUs remained normal, but no quality/performance promotion is permitted | [result](notes/2026-08-17-q8-exact-scale-dictionary-active.md), [data](data/2026-08-17-q8-exact-scale-dictionary-negative.json), [slow patch](patches/q8-exact-scale-dict11-slow-smoke-20260817.diff), [unsafe patch](patches/q8-exact-scale-dict11-direct-lookup-unsafe-20260817.diff) |
| Clean oneAPI 2026.1.1 AOT compiler refresh | Closed: fixed completion was byte-exact, but the position-balanced result was performance-neutral (`+0.0042%`) versus 2026.1.0 | [result](notes/2026-08-16-q8-oneapi-2026.1.1-refresh-active.md), [data](data/2026-08-16-q8-oneapi-2026.1.1-refresh-neutral.json) |
| Upstream gated-delta-net state-writeback fusion (`3d9388535`) | Closed during audit: the accepted repro already enables a stricter direct persistent-state I/O fusion that removes both GET_ROWS and CPY; no build was needed | [audit](notes/2026-08-16-q8-upstream-gdn-cache-fusion-active.md) |
| TP2 queue-0 local-ready event elision | Closed: normal output was exact and poison proved the branch live, but the symmetric decode screen was performance-neutral (`+0.0247%`) | [result](notes/2026-08-16-q8-local-ready-elision-active.md), [data](data/2026-08-16-q8-local-ready-elision-neutral.json), [patch](patches/q8-local-ready-elision-neutral-20260816.diff) |
| Exact Q8 compile-time FFN projection shapes | Closed: pair/down specializations were live on both devices, normal output was exact and poison proved reachability, but the symmetric screen was performance-null (`-0.0088%`) | [result](notes/2026-08-16-q8-fixed-shape-mmvq-active.md), [data](data/2026-08-16-q8-fixed-shape-mmvq-neutral.json), [patch](patches/q8-fixed-shape-mmvq-neutral-20260816.diff) |
| Exact Q8 compile-time recurrent GDN quad shape | Closed: live/poison proofs passed and long `p64/n512` decode repeated at `+0.741%`, but a matched 12-prompt same-binary service gate was neutral/slightly negative (`-0.0664%` conventional). All output hashes, semantic canaries, eight repeats and the 3,829-token needle were exact; do not promote or repeat unchanged | [result](notes/2026-08-17-q8-recurrent-quad-fixed-shape-active.md), [data](data/2026-08-17-q8-recurrent-quad-fixed-shape-service-neutral.json), [patch](patches/q8-recurrent-quad-fixed-shape-service-neutral-20260817.diff) |
| Shape-scoped SG16 workgroup for the recurrent GDN quad | **Accepted**: both opposite-order realistic pairs favored SG16; pooled `+0.257%` primary median, `+0.481%` full median and `+0.413%` full mean. All endpoint/semantic/repeat/3,829-token hashes exact; clean accepted-source replay passed | [result](notes/2026-08-17-q8-recurrent-quad-subgroups-active.md), [data](data/2026-08-17-q8-recurrent-quad-sg16-accepted.json), [patch](../../patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff) |
| Shape-scoped SG32 workgroup for the recurrent GDN quad | Closed: first order's apparent `+1.664%` reversed to `-2.096%` under fully complementary positions; unbiased 16-run combination was `-0.233%` versus accepted SG16 | [result](notes/2026-08-17-q8-recurrent-quad-sg32-active.md), [data](data/2026-08-17-q8-recurrent-quad-sg32-negative.json), [patch](patches/q8-recurrent-quad-sg32-negative-20260817.diff) |
| Shape-scoped SG24 workgroup for the recurrent GDN quad | **Active on the reference ASRock host**: midpoint between accepted SG16/256 and rejected SG32/512 work-item packing | [claim](notes/2026-08-17-q8-recurrent-quad-sg24-active.md) |
| Shape-scoped SG4 for Q8 FFN pair/down | Closed: both doors were live with zero verification mismatches. The first four-arm screen's apparent both-door `+1.252%` was a run-position artifact; an odd/even-balanced eight-process confirmation measured `-0.272%`, with blocks disagreeing (`+0.096%`, `-0.635%`) | [result](notes/2026-08-17-q8-ffn-shape-scoped-subgroups-active.md), [data](data/2026-08-17-q8-ffn-shape-scoped-sg4-negative.json), [patch](patches/q8-ffn-shape-scoped-sg4-negative-20260817.diff) |
| Register-direct collective tail WG256/WG512 | Closed: WG256 smoke was safe with zero verification mismatches, but the mirrored screen decisively favored accepted WG1024 (`37.171867 tok/s`): WG512 was `-3.102%` and WG256 `-5.019%` | [result](notes/2026-08-17-q8-collective-tail-workgroup-active.md), [data](data/2026-08-17-q8-collective-tail-workgroup-negative.json), [patch](patches/q8-collective-tail-workgroup-negative-20260817.diff) |
| Exact Q8 direct ESIMD SIMD16 DP4A row body | Closed: standalone/pair/triple were live and a poison control proved reachability; normal output was exact, but the position-balanced TP2 screen regressed `0.699%` | [result](notes/2026-08-16-q8-esimd-dp4a-active.md), [data](data/2026-08-16-q8-direct-esimd-dp4a-negative.json), [patch](patches/q8-direct-esimd-dp4a-negative-20260816.diff) |
| Peer-mapped vec4 collective cache hints | Closed: streaming was performance-null (`+0.011%`) and uncached was slightly negative (`-0.027%`) in a symmetric same-binary screen | [note](notes/2026-08-16-q8-peer-collective-cache-hints-active.md), [data](data/2026-08-16-q8-peer-collective-cache-hints-neutral.json), [patch](patches/q8-peer-collective-cache-hints-20260816.diff) |
| Q8 quant-value lossless repacking | Closed: practical sentinel formats expanded the 32 Q values; theoretical value-stream entropy headroom was only about 3.7%. This does not cover the separately claimed exact scale-plane dictionary arm | [structural audit](notes/2026-08-16-q8-structural-feasibility-and-sampling.md) |
| Q8 two-chain DP4A (`DP4A2`) transfer | Quality-exact, but no repeatable Qwen3.8 endpoint gain; the promoted snapshot intentionally retains one-chain DP4A | [note](notes/2026-08-16-q8-dp4a2-transfer-no-win.md) |
| Early Qwen3.8 direct-Q8 reproduction packet | Superseded provenance error: it omitted three source increments that the launcher enabled and the headline result used. Use the corrected one-chain full-stack packet | [correction](notes/2026-08-16-q8-repro-provenance-correction.md), [data](data/2026-08-16-q8-repro-provenance-correction.json) |
| Reordered-Q8 dynamic loop unroll by two | Exact TP2 smoke; neutral across complementary brackets (`+0.076%` overall), so not promoted | [note](notes/2026-08-16-q8-mmvq-loop-unroll2-neutral.md), [data](data/2026-08-16-q8-mmvq-loop-unroll2-neutral.json), [patch](patches/q8-mmvq-loop-unroll2-neutral-20260816.diff) |
| Fused-pair Q8 two-iteration operand preload | Closed: treatment live on both devices but endpoint-neutral at `+0.045%`; paired deltas crossed direction, so do not extend unchanged to triple/quad | [note](notes/2026-08-16-q8-fused-pair-block-preload-active.md), [data](data/2026-08-16-q8-fused-pair-block-preload-neutral.json), [patch](patches/q8-fused-pair-block-preload-neutral-20260816.diff) |
| Fused-pair row-chunk interleave (`32`–`512`) | Closed: apparent middle-position screen gain (`+1.331%` at chunk 32) reversed to `-1.669%` in the position-balanced `B-A-A-B` `n512` bracket; process-position artifact, no promotion | [note](notes/2026-08-16-q8-fused-pair-chunk-interleave-position-artifact.md), [data](data/2026-08-16-q8-fused-pair-chunk-interleave-position-artifact.json), [patch](patches/q8-fused-pair-chunk-interleave-position-artifact-20260816.diff) |
| Register-direct 5,120-element RMS loop unroll by five | Mechanism-clean, but endpoint-neutral at `+0.039%`; runtime loop overhead is below resolution | [note](notes/2026-08-16-q8-collective-rms-unroll5-neutral.md), [data](data/2026-08-16-q8-collective-rms-unroll5-neutral.json), [patch](patches/q8-collective-rms-unroll5-neutral-20260816.diff) |
| Selective 256-GRF on hot reordered-Q8 MMVQ launches | Safe and exact at the smoke gate, but decisively slower (`-2.789%`) because the larger register allocation reduced effective occupancy | [note](notes/2026-08-16-q8-selective-grf256-negative.md), [data](data/2026-08-16-q8-selective-grf256-negative.json), [patch](patches/q8-selective-grf256-negative-20260816.diff) |
| Reordered-Q8 VDR2 at concurrency two | Rejected: `-2.981%` aggregate and one prompt diverged between sequential and simultaneous execution because the FP32 reduction grouping changed | [note](notes/2026-08-16-q8-vdr2-c2-negative.md), [data](data/2026-08-16-q8-vdr2-c2-negative.json), [patch](patches/q8-vdr2-c2-negative-20260816.diff.gz.b64) |
| Accepted-stack copy/requantize census | Closed: zero residual copy launches and only eight Q8 quantize launches across 516 graph computes; the assumed generic intermediate round trip does not exist | [census](notes/2026-08-16-q8-accepted-kernel-census.md) |
| TP2 collective census | 128 already-fused boundaries/token; synchronization, not transferred bytes, is the target | [structural audit](notes/2026-08-16-q8-structural-feasibility-and-sampling.md) |
| Tensor-split backend sampling | Closed: llama.cpp fell back to CPU, so no GPU treatment was executed | [structural audit](notes/2026-08-16-q8-structural-feasibility-and-sampling.md) |
| Fused Q8 MMVQ + SwiGLU | Rejected performance regression | [note](notes/2026-08-16-q8-fused-mmvq-swiglu-negative.md), [data](data/2026-08-16-q8-fused-mmvq-swiglu-negative.json), [patch](patches/q8-fused-mmvq-swiglu-v2-negative-20260816.diff.gz.b64) |
| Concurrency-2 cache-row fusion | Exact mechanism, endpoint-neutral; not promoted | [note](notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md), [data](data/2026-08-16-q8-c2-cache-row-fusion-neutral.json), [patch](patches/q8-c2-cache-row-fusion-neutral-20260816.diff.gz.b64) |
| Accepted binary at c3/c4 | High aggregate diagnostics (`77.212` / `91.895 tok/s`) but rejected: true p3 was 0/3 exact and p4 was 2/4 exact against fixed-slot sequential oracles | [note](notes/2026-08-16-q8-c3-c4-quality-rejected.md), [data](data/2026-08-16-q8-c3-c4-quality-rejected.json) |
| c2 batch/ubatch sweep (`1024/256` through `8192/2048`) | No repeatable speed gain; `2048/512` was exact on prompt pair 0/1 twice but diverged 0/2 on the disjoint pair 2/3, so large batching is not a general quality fix | [note](notes/2026-08-16-q8-c2-batch-shape-audit.md), [data](data/2026-08-16-q8-c2-batch-shape-audit.json) |
| Q8 c2 split into two single-row MMVQ launches | Rejected: about `+2%` aggregate, but the disjoint pair still differed 0/2 from sequential oracles; two-column Q8 MMVQ is not the sole schedule-sensitive arithmetic | [note](notes/2026-08-16-q8-c2-row-exact-mmvq-negative.md), [data](data/2026-08-16-q8-c2-row-exact-mmvq-negative.json), [patch](patches/q8-c2-row-exact-mmvq-quality-negative-20260816.diff) |
| c2 recurrent/GDN and attention/QK fusion-family ablations | Neither targeted family repaired the disjoint 0/2 quality result; global fusion-off plus Q8 row split also failed and changed one sequential output | [note](notes/2026-08-16-q8-c2-quality-isolation-and-dual-process.md), [data](data/2026-08-16-q8-c2-quality-isolation-and-dual-process.json) |
| Two independent accepted TP2 server processes | Quality-exact and memory-feasible, but catastrophic shared-device contention: only `14.890992 tok/s` aggregate versus about `35.9 tok/s` for either process alone | [note](notes/2026-08-16-q8-c2-quality-isolation-and-dual-process.md), [data](data/2026-08-16-q8-c2-quality-isolation-and-dual-process.json), [harness](scripts/capture-target-only-dual-process.py) |
| Distributed greedy argmax | Exact but primary throughput neutral and TTFT worse; not promoted | [note](notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md), [data](data/2026-08-16-q8-distributed-greedy-argmax-neutral.json), [patch](patches/q8-distributed-greedy-argmax-neutral-20260816.diff.gz.b64) |
| Level Zero v2 selector | Already the runtime default; explicit pin is reproducibility-only. Legacy was 3.375% slower | [note](notes/2026-08-16-q8-level-zero-v2-adapter-audit.md), [data](data/2026-08-16-q8-level-zero-v2-adapter-audit.json) |
| UR signal barriers and device-scope events | Corrected source audit: signal barriers are already the unset default; unset vs explicit `1` was identical at the endpoint, while explicit `0` regressed `2.621%`. Device-scope modes lost to the neighboring control | [note](notes/2026-08-16-q8-ur-event-controls-neutral.md), [data](data/2026-08-16-q8-ur-event-controls-neutral.json) |
| UR immediate-command-list mode 2 (`PerThreadPerQueue`) | Rejected: `36.000691` versus `36.887491 tok/s` for accepted mode 1 (`PerQueue`), a `-2.404%` regression | [note](notes/2026-08-16-q8-ur-immediate-mode2-negative.md), [data](data/2026-08-16-q8-ur-immediate-mode2-negative.json) |
| Exclusive scheduler / hardware clock control | Closed: exclusive mode was unsupported; the active 1000 us timeslice could not be safely A/B tested because the CLI only accepted >=5000 us; minimum-clock pinning was restored after a `-0.487%` A/B/B/A result | [note](notes/2026-08-16-q8-hardware-scheduler-audit.md), [data](data/2026-08-16-q8-hardware-scheduler-audit.json) |
| Peer-pair cross-device output writes, mode 3 | **Unsafe: device-lost/reset storm. Never retry on this stack** | [note](notes/2026-08-16-q8-peer-pair-collective-unsafe.md), [data](data/2026-08-16-q8-peer-pair-collective-unsafe.json), [quarantined patch](patches/q8-peer-pair-collective-device-lost-unsafe-20260816.diff.gz.b64) |
| Root-fused per-owner handoff, mode 4 | Safe and exact at the benchmark gate, but rejected: `-3.388%` decode because the longer root critical path serialized device 1 | [result](notes/2026-08-16-q8-root-fused-candidate-negative.md), [data](data/2026-08-16-q8-root-fused-candidate-staged.json), [patch](patches/q8-root-fused-collective-untested-20260816.diff.gz.b64) |
| Public GPTQ INT4 + native MTP | Performance reproduced, but GPTQ target failed a deterministic semantic canary; not the no-loss lane | [community decision](../../community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md) |
| Official FP8 with old Intel vLLM `0.21.0-b3.1` | Superseded negative: bounded TP2 initialization failed after model load; do not retry this image unchanged | [bring-up](notes/2026-08-15-bringup-checkpoint.md) |
| Official FP8 with vLLM/XPU `0.27.2rc1.dev77`, eager | Working exact-gated control at `17.097358 tok/s`; graph c1 is `26.97%` faster | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 graph c1, `CCL_TOPO_P2P_ACCESS=1` | Neutral at `21.706164 tok/s` (`-0.011%`); retain the default `0` | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 `FULL_DECODE_ONLY` graph c1 | Quality-clean but `1.618%` slower (`21.357193 tok/s`) than PIECEWISE; retain PIECEWISE | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 2026-08-16 nightly (`8efa13b70`, XPU kernels `0.1.13.2`) | Quality-clean but noise-level `+0.070%` (`21.723631 tok/s`); do not churn the pinned runtime | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 XPU Q/K RMSNorm+RoPE compiler fusion | Mechanism verified and quality-clean, but repeat medians bracketed control (`+0.150%`, `-0.083%`); leave disabled | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 native BF16 activation/KV arithmetic | Full oracle passed, but decode was identical (`21.708409 tok/s`, `-0.0006%`) and TTFT was slower; not a speed lane | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 `max_num_seqs=1` | Exact output and cache-zero, but neutral at `21.717535 tok/s` (`+0.041%`); retain the more useful captured capacity of 4 | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 greedy requests without a per-request seed | Exact output and cache-zero, but `21.659428 tok/s`, `-0.268%` versus the same loaded seeded server; retain explicit seeds | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |
| Official FP8 cached graph restart in an 8 GiB host cgroup | OOM-killed one worker while reloading AOT artifacts; use the validated 9/12 GiB bounds | [result](notes/2026-08-16-official-fp8-vllm-graph-tp2.md) |

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
