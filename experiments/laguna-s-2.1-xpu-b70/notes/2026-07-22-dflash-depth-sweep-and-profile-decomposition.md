# Laguna DFlash depth sweep and profile decomposition

Date: 2026-07-22 (local; final two rows completed after 00:00 UTC)

## Result first

Depth **7** remains the best exact setting. Its fresh sweep median was
**32.19059366549866 tok/s**, below the approved **33.43893 tok/s** record
`cmrwot89400gqnz014oodtlbp`. No candidate qualified for the two-fresh-start
record gate, so no new payload was staged and no LocalMaxxing submission was
made.

All measured requests were cold and reported `cached_tokens=0`. Depths 5, 6,
and 7 matched the canonical deterministic q=1 teacher 13/13. Depth 4 matched
12/13 and is invalid. Depths 8-10 matched 0/13 and are invalid; their verifier
widths exceed the current exact target path's M<=8 guards and bypass the record
fused route-interleave expert path.

| Depth | Verifier rows | Median tok/s 1-100 | Acceptance | Emitted/cycle | Teacher exact | Disposition |
|---:|---:|---:|---:|---:|---:|---|
| 4 | 5 | 29.751823 | 54.3897% | 3.178589 | 12/13 | invalid; row 6 diverged at token 0; cause unclassified |
| 5 | 6 | 31.002236 | 48.5237% | 3.423491 | 13/13 | exact, slower |
| 6 | 7 | 32.063512 | 42.8130% | 3.567659 | 13/13 | exact, slower |
| **7** | **8** | **32.190594** | **38.5856%** | **3.696335** | **13/13** | **best exact; incumbent depth; below record** |
| 8 | 9 | 6.112672 | 34.2947% | 3.731893 | 0/13 | invalid; generic target fallback |
| 9 | 10 | 5.340112 | 31.2034% | 3.791691 | 0/13 | invalid; generic target fallback |
| 10 | 11 | 4.938494 | 28.5877% | 3.839543 | 0/13 | invalid; generic target fallback |

Acceptance is accepted proposals divided by drafted proposals, using the
after-minus-before Prometheus counters for each suite. Emitted/cycle is actual
API completion tokens divided by `spec_decode_num_drafts_total`. This corrects
the earlier rough `~4.4` premise: the approved depth-7 full-512 record packet is
also about **3.696 emitted/cycle**; `~4.4` came from an earlier higher-acceptance
interval, not the strict full-512 record suite.

The depth-7 sweep row reproduces the record's exact acceptance counters exactly
(`4643/12033`) but landed in a slower endpoint window. It therefore cannot
replace or challenge the approved two-start record. Retrying until it produced
a favorable number would violate the no-flaky-numbers rule.

Machine-readable evidence is
`data/laguna-s-2.1-dflash-depth-sweep-20260722.json`.

## Depth support and exact-path boundary

The INT4 DFlash config declares `dflash_config.block_size=16`. DFlash constructs
one bonus/current-token query plus K proposal queries, so the checkpoint-trained
maximum is `num_speculative_tokens=15`. The local model card recommends 7 and
publishes benchmark results at 15. All requested depths 4-10 are therefore
checkpoint-supported.

The current XPU exact runtime is narrower than the checkpoint:

- exact speculative paged attention requires query rows `<=8`;
- exact batched-M1 linear/logits paths require rows `<=8`;
- Laguna batched-exact MoE and the fused expert transaction accept rows `<=8`.

Thus K=4-7 produces M=5-8 and can use the exact target implementation. K=8-10
produces M=9-11 and falls back to generic target arithmetic. Full output parity
confirmed that the fallback is not q=1 token-identical on this source. Extending
depth beyond 7 as an exact record lane requires widening or serializing all of
attention, linear/logits, and MoE verifier boundaries; a flag-only depth sweep
cannot promote it.

Depth 4 exposed an additional non-promotion result: despite M=5 remaining
inside the nominal guards, suite row 6 (`typescript-cancellation`) diverged at
output token 0. The cause is unclassified. The row remains 12/13 and is invalid;
it was not rerun into a favorable classification.

## Unnamed-bucket correction and decomposition

This profile predates route interleave: it used vLLM `6a570e70b` plus XPU
kernels `20cfa3aef35d1daa2c57f3dccaf7ce7d552f6751`. It re-profiled the fused-W1
and route-parallel-W2 record specifically to choose Candidate B; it is separate
from the depth sweep's installed `210a6eb60` kernel identity.

The published **13.409344 ms/cycle** `other_noncollective` value is a stale
classifier fallback, not a wholly unexplained residual. The reused DeepSeek
classifier placed Laguna's already-known W1 and W2 kernels in `other`:

```text
13.409344 classifier other
-6.488383 fused W1+SiLU
-3.330374 route-parallel W2
=3.590587 true residual
```

The raw trace retains nine steady q=8 target contexts per rank after dropping
the first, associates GPU events through submitted/appended/SYCL enqueue
records, excludes corrupted oneCCL device timestamps, and averages the four
rank means. The raw events account for the residual to about 0.036 ms/cycle.

| True target residual family | ms/cycle |
|---|---:|
| Attention non-GEMM | **1.415801** |
| Router/routed bookkeeping | **1.094606** |
| Integer and slot metadata | ~0.393645 |
| Shared-expert SiLU + multiply | 0.246532 |
| Fused residual-add RMSNorm | 0.222450 |
| Fixed-rank BF16 sums | 0.181520 |
| Unlisted tail | ~0.036035 |

Attention non-GEMM breaks down into fused XeFMHA QK/softmax/LSE/PV
`0.399565`, Q/K RMSNorm `0.264944`, RoPE `0.137574`, gate
casts/softplus/multiply `0.519914`, and KV write `0.093803` ms/cycle. QK, LSE,
and PV cannot be separated further because they are one
`XeFMHAFwdSplitKVKernel` event.

Router/routed bookkeeping includes `TopKGating` **0.560374**, router-logit
BF16-to-FP32 cast `0.272194`, route-output zero `0.074052`, routed scale
`0.083971`, and shared+routed add `0.104015` ms/cycle. Fixed `MoeGather` is
separately classified at `0.441856` ms/cycle; there is no explicit route-scatter
kernel on the persistent route-slot path.

The separately named dense-GEMM bucket is **4.526301 ms/cycle**. Its largest
still-unoptimized family is target BF16 attention QKV+O at **2.918838
ms/cycle**, followed by shared-expert/router GEMMs at `1.014246`. The profiler's
target annotation ends before sampling and draft proposal. Inter-context gaps
recover another **1.994284 ms/cycle** for DFlash plus sampling; the largest
draft family is its six-layer dense MLP GEMMs at **0.637397 ms/cycle**. Argmax
sampling is only about `0.058229`, and exact rejection is `0.002083` ms/cycle.

The next single named kernel lever inside the true residual is therefore
**TopKGating at 0.560374 ms/cycle**. The larger architectural target remains
**BF16 attention QKV+O at 2.918838 ms/cycle**, while the draft-side lever is
the **0.637397 ms/cycle** dense MLP family. No kernel change was implemented in
this run.

Profile aggregate and raw-trace sources:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/candidate-b-record-reprofile-6a570e70b-20cfa3a-20260722T1753Z/summary.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/candidate-b-record-reprofile-6a570e70b-20cfa3a-20260722T1753Z/trace/
```

The detailed operator-shape attribution and the 1.994284 ms/cycle DFlash plus
sampling value come from the four rank traces by measuring kernels in the gaps
between consecutive target annotations; they are not fields in `summary.json`.

## Runtime identity and evidence

- vLLM: `6a570e70b2c1ccce3a42f3396e1bd22b0a4a8191`, branch
  `experiment/laguna-s-2.1-xpu-bringup-20260721`;
- XPU kernels: `210a6eb604500c80bc5989d4b9fc59e75f1bb316`, branch
  `experiment/laguna-s-2.1-fwht-20260721`;
- record flags:
  `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1`,
  `VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1`, and
  `VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1`;
- eager, XPU graph off, `--no-async-scheduling`, BF16 KV, one active sequence;
- target `poolside/Laguna-S-2.1-INT4` revision
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft `poolside/Laguna-S-2.1-DFlash-INT4` revision
  `5e07c246915c86dc6920fead03d019989224f2ba`.

Measured run directories:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-depth4-m8-route-interleave-20260722T231335Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-depth5-m8-route-interleave-20260722T232119Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-depth6-m8-route-interleave-20260722T232843Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-depth7-m8-route-interleave-20260722T233559Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-depth8-m8-route-interleave-20260722T234307Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-depth9-m8-route-interleave-retry-20260723T000304Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-depth10-m8-route-interleave-20260723T002308Z
```

Two startup failures produced no measurements and are retained as operational
evidence: the first depth-4 attempt was killed during checkpoint load under
host page-cache pressure, and the first depth-9 attempt hit
`UR_RESULT_ERROR_DEVICE_LOST` during worker initialization. After the latter,
all four independent card allocation/compute probes passed before the measured
retry. No DeepSeek held-out pack or `/mnt/fast-ai` write was used. The
DeepSeek option4-decoder branch and all `preserve/*` tags were untouched.
