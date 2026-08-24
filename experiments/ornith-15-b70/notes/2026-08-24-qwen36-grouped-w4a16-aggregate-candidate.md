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
They ran together at B4, which was not one of this candidate's explicitly
captured shapes. This is only a gross quality smoke, not validation of the B64
capture and not the lab's promotion-quality suite. The harness now exercises
literal canaries at every declared capture size for subsequent candidates.

The repeat harness initially varied the seed by repeat; that was corrected
before this run. With a genuinely fixed seed, some model outputs still changed
between otherwise identical repeats. Batch 1 and batch 4 were fully stable,
while batch 64 matched only 27/64 request-level token-sequence hashes. This
candidate therefore remains unpromoted and its throughput must retain the
determinism disclosure.

There is a separate batch-shape effect: for several prompts, greedy output
changed when the same request moved between B2/B4/B8/B16/B32/B64. That effect
was already present in the grouped eager sweep, so it cannot be attributed
only to graph replay. Request 0 happened to remain identical at every eager
batch size, which is why a single-request-only digest check would have missed
the broader behavior. Batch-shape dependence and same-shape repeat stability
must be reported as different properties.

The grouped W4A16 operator itself was then tested with fixed inputs, routing,
weights, and scales for 25 calls at every batch size from 1 through 64. Every
row was bit-identical with zero maximum drift. That negative diagnostic rules
out simple standalone nondeterminism in the newly enabled grouped kernel; it
does not prove the kernel is uninvolved in a larger graph interaction.

The fixed-seed eager discriminator then measured B1 twice at 24.575 / 24.500
tok/s and B64 twice at 948.999 / 950.303 tok/s. B1 was 1/1 identical, while
B64 was only 31/64 request-sequence hashes identical. The variation therefore
persists when graph capture is disabled: graph replay is not its root cause.
This eager treatment is still above the requested 875 tok/s aggregate target,
but below the graph candidate's 1,039.408 tok/s mean.

Three exact-dimension component probes further narrowed the boundary:

- grouped W4A16 under graph replay was bit-identical 25/25 at every B1-B64
  test shape;
- GDN prefill output and recurrent state were bit-identical 25/25 at B1, B4,
  and B64;
- the captured GDN convolution plus packed recurrent decode segment produced
  bit-identical output, convolution state, and recurrent state 25/25 at B1,
  B4, and B64.

These negative diagnostics protect the measured throughput work from being
mischaracterized as a demonstrated bug in one of the three patches. They do
not establish end-to-end determinism; another full-model path or interaction
remains open.

The subsequent combined-runtime treatment added explicit oneDNN producer and
consumer dependencies, the previously measured determinism pad, and the GDN
state fix in a single BMG-G31 build. Before loading the model, grouped W4A16
graph replay and both GDN probes remained bit-identical 25/25, and the oneDNN
producer-to-INT4-to-consumer chain was bit-identical 100/100 both with and
without the guards. The full model then passed 100/100 literal canaries across
the B1, B32, and B64 capture shapes.

That treatment was a **speed positive but determinism negative**. B1 measured
90.885 / 90.934 tok/s (mean **90.909**) and was 1/1 identical. B64 measured
1,051.000 / 1,054.741 tok/s (mean **1,052.870**), but only 29/64 request token
sequences matched between repeats. This is worse than the eager discriminator's
31/64 and does not repair the end-to-end variation. The speed measurement is
valid and directly observed; the guard must not be promoted as a determinism
fix.

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
- Fixed-seed eager discriminator:
  `../data/2026-08-24-qwen36-grouped-eager-fixed-seed-discriminator.json`
- Grouped-operator graph stability:
  `../data/2026-08-24-qwen36-grouped-w4a16-graph-repeat-stability.json`
- GDN prefill stability:
  `../data/2026-08-24-qwen36-gdn-prefill-repeat-stability.json`
- GDN decode graph stability:
  `../data/2026-08-24-qwen36-gdn-decode-graph-repeat-stability.json`
- Combined-runtime component gates:
  `../data/2026-08-24-qwen36-combined-runtime-grouped-w4a16-graph-stability.json`,
  `../data/2026-08-24-qwen36-combined-runtime-gdn-prefill-stability.json`,
  `../data/2026-08-24-qwen36-combined-runtime-gdn-decode-stability.json`,
  `../data/2026-08-24-qwen36-combined-runtime-onednn-control.json`, and
  `../data/2026-08-24-qwen36-combined-runtime-onednn-treatment.json`
- Full guarded-runtime treatment:
  `../../../data/qwen36-35b-ar-tp1/persistent-grouped-graph-guards-b1-b64-repeat2-fixedseed-p128o1024-r16.json`
- Exact source overlay:
  `../patches/vllm-qwen35moe-xpu-grouped-w4a16-gdn-state-20260824.patch`
- Combined kernel-runtime treatment source:
  `../patches/vllm-xpu-kernels-qwen36-combined-runtime-guards-20260824.patch`
- Persistent sweep harness:
  `../scripts/vllm-persistent-decode-sweep.py`

## Next gate

The cross-runtime dependency treatment is closed as a determinism negative.
Next, screen the checkpoint's MTP1 layer for single-request speed while
requiring aggregate throughput to remain above the requested 875 tok/s floor,
then run the full realistic quality battery and repeat any surviving candidate
in a clean process. Only then should it become a user-facing recipe or feed a
public measured chart.
