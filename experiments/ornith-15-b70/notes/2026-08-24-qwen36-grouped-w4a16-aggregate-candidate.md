# Qwen35MoE grouped-W4A16 aggregate candidate

Date: 2026-08-24  
Status: **throughput target met; quality smoke passed; determinism pending**

## Scope

This is a measured one-B70 vLLM experiment on
`abhinand/Qwen3.6-35B-A3B-int4-AutoRound`. It shares the Qwen35MoE
architecture family with Ornith 1.5 35B-A3B, but it is not the Ornith GGUF
checkpoint, quantization, or runtime. These rates must not be published as an
Ornith headline or compared as a like-for-like boost to the llama.cpp packet.

The requested aggregate objective was 875 tok/s, with 1,000 tok/s as the
stretch objective. Both were exceeded by direct observation.

## Measured result

All rows use a persistent engine, 128 input tokens per request, 1,024 forced
output tokens per request, greedy decoding, no prefix cache, one B70, and TP1.
The candidate used oneDNN dense W4A16, the Xe2 grouped W4A16 routed-MoE path,
the GDN state-memory reductions in the patch packet, and piecewise XPU Graph
captures at batch sizes 1, 32, and 64. No row is interpolated or extrapolated.

| concurrent requests | eager baseline aggregate tok/s | graph candidate mean | candidate repeats | fixed-seed identical requests |
| ---: | ---: | ---: | --- | ---: |
| 1 | 20.732 | **87.638** | 87.598 / 87.679 | 1/1 |
| 2 | 40.869 | **77.186** | 77.130 / 77.243 | 1/2 |
| 4 | 81.712 | **149.484** | 149.440 / 149.527 | 4/4 |
| 8 | 162.001 | **276.766** | 276.888 / 276.643 | 7/8 |
| 16 | 306.317 | **488.647** | 482.815 / 494.480 | 13/16 |
| 32 | 390.286 | **823.151** | 824.566 / 821.735 | 29/32 |
| 64 | 399.679 | **1,039.408** | 1,041.722 / 1,037.094 | 27/64 |

At batch 64 the candidate is 160.06% above the matched eager starting point.
The two end-to-end output rates, including prefill, were 1,039.105 and
1,036.026 tok/s. At batch 1, the candidate improved the measured rate from
20.732 to 87.638 tok/s. That is substantial single-request progress, although
it does not yet match the separately optimized Ornith llama.cpp packet.

## Correctness and stability boundary

The arithmetic, prime, capital, and compact-JSON literal canaries passed 4/4.
This is only a gross quality smoke, not the lab's promotion-quality suite.

The repeat harness initially varied the seed by repeat; that was corrected
before this run. With a genuinely fixed seed, some model outputs still changed
between otherwise identical repeats. Batch 1 and batch 4 were fully stable,
while batch 64 matched only 27/64 request-level token-sequence hashes. This
candidate therefore remains unpromoted and its throughput must retain the
determinism disclosure.

The grouped W4A16 operator itself was then tested with fixed inputs, routing,
weights, and scales for 25 calls at every batch size from 1 through 64. Every
row was bit-identical with zero maximum drift. That negative diagnostic rules
out simple standalone nondeterminism in the newly enabled grouped kernel; it
does not prove the kernel is uninvolved in a larger graph interaction.

## Graph constraints and preserved negatives

- Capturing all seven batch sizes failed after three graphs with Level Zero
  `UR_RESULT_ERROR_OUT_OF_RESOURCES`.
- Capturing only 1 and 64 at 95% memory completed capture but left
  insufficient runtime workspace and failed with the same resource error.
- Reducing GPU memory utilization to 0.90 left 8.87 GiB for KV, or 249,856
  tokens, and allowed three captures (1/32/64) using 1.29 GiB.
- The first graph attempt also exposed an unrelated automatically enabled MLA
  fusion-pass `NameError`; the harness now disables that irrelevant pass
  explicitly for this non-MLA model.

These failed attempts remain in the raw run directory as infrastructure
evidence and are not performance rows.

## Artifacts

- Compact result:
  `../data/2026-08-24-qwen36-35b-autoround-grouped-graph-aggregate-candidate.json`
- Baseline summary:
  `../data/2026-08-24-qwen36-35b-autoround-eager-aggregate-baseline.json`
- Exact-shape backend comparison:
  `../data/2026-08-24-qwen36-w4a16-moe-backend-exact-shape.json`
- Grouped-operator repeat stability:
  `../data/2026-08-24-qwen36-grouped-w4a16-repeat-stability.json`
- Exact source overlay:
  `../patches/vllm-qwen35moe-xpu-grouped-w4a16-gdn-state-20260824.patch`
- Persistent sweep harness:
  `../scripts/vllm-persistent-decode-sweep.py`

## Next gate

Localize the fixed-seed model variation before promotion. Once stable, run the
full realistic quality battery and a clean-process repeat. Only then should the
candidate become a user-facing recipe or feed a public measured chart.
