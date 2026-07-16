# MTP1 M=2 MXFP4 Small-N Policy Closure

Date: **2026-07-16**

Status: **bitwise exact; isolated positive; not promoted**

## Decision

Keep the promoted MXFP4 N64 policy. N32 is a measured regression. N128 is
bitwise exact and consistently faster in the isolated four-card M=2 hardware
gate, but two strict candidate suites do not robustly exceed the existing
63.349928 tok/s record. No LocalMaxxing submission was made.

This is not a model, topology, speculative-depth, cache, or prompt-policy
change. The frozen K160 TP4+EP, one-active-generation, target-verified MTP1
identity was retained throughout.

## Why this lane was reopened

The exact eager-cycle profile attributes **4.1511 ms per MTP1 cycle** to the
routed MXFP4 verifier family. Earlier N32/N128 work had tested M=1 and exposed
a graph-replay correctness race: workgroup 0 reset a global scheduler counter
while other workgroups could already increment it. That history did not answer
the M=2 verifier question.

XPU-kernel experiment commit
`351a06a4426b77eed12f555d01da8ea186d0dc7b` moves the N32/N128 reset to an
ordered queue fill before launch. The experiment is preserved on branch
`codex/deepseek-v4-m2-mxfp4-policy`; the promoted source remains
`d15ce87d07376be53ea2d6f7ae0262ab79f7cb7b` on
`codex/deepseek-v4-m2-router-norm`.

## Four-card hardware gate

The reusable probe is `../scripts/probe-mxfp4-m2-policy.py`; tracked raw
summaries are under
`../../../data/deepseek-v4-reap-mxfp4-m2-policy-20260716/`.

N32 passed all tested changed-route and graph-replay cases but regressed by
6.68-6.98 us per layer on the two sampled B70s, projecting a
0.287-0.300 ms loss across 43 MXFP4 calls. It was closed immediately.

N128 passed **48/48 bitwise-exact cases on every B70** across same-route,
disjoint-route, cross-row-overlap, and adversarial route patterns. Against N64:

| Physical B70 | N64 median us | N128 median us | Projected ms saved / 43 |
| --- | ---: | ---: | ---: |
| 0 | 219.902 | 213.342 | 0.2821 |
| 1 | 220.198 | 213.613 | 0.2831 |
| 2 | 219.136 | 213.403 | 0.2465 |
| 3 | 220.291 | 214.537 | 0.2474 |
| **Mean** | **219.882** | **213.724** | **0.2648** |

The isolated speedup is real and repeatable, but it clears only 53% of the
0.50 ms whole-cycle integration gate. It was integrated once because the
profile identified MXFP4 as the largest genuinely open verifier family and the
change was already graph-exact.

## Strict service evidence

N128 candidate evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-mxfp4-n128-candidate-20260716T0630Z`

Same-binary N64 control evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-mxfp4-n64-control-20260716T0645Z`

| Policy/run | Median tok/s | p10 tok/s | Mean tok/s |
| --- | ---: | ---: | ---: |
| N128 screen | 62.649706 | 59.577779 | 62.727082 |
| N128 confirmation | 63.628477 | 59.481507 | 62.986086 |
| N64 control 1 | 61.205692 | 58.893436 | 62.067179 |
| N64 control 2 | 63.101865 | 58.749330 | 62.641414 |

All 48 requests are fresh, cached-zero, and pass the fixed realistic-suite
gate. The two N128 medians average 63.139091 tok/s; the two N64 controls average
62.153779 tok/s. However, the N64 control span is 1.896 tok/s and the N128
screen is below both the 63.349928 record and its 62.882999 support suite. The
single 63.628477 row is therefore insufficient to establish a new record.

Running more suites until one exceeds the record would be benchmark shopping.
The correct classification is an exact small isolated improvement whose
end-to-end effect remains inside observed service variance.

## Dense-profile implication

The apparent 6.5803 ms dense-GEMM bucket is now decomposed by exact shape. Its
largest pieces are already optimized or have a preserved negative result:

- 1.4094 ms: `wo_a` BF16 BMM; the earlier FP8 replacement lost end to end;
- 0.9129 ms: WQ_B W8A16, already selected;
- 0.8183 ms: WO_B W8A16, already selected;
- 0.6960 ms: C4 compressor BMM, already row-exact and batched;
- 0.6305 ms: fused WQA/WKV W8A16, already selected;
- 0.5919 ms: shared-down W8A8, with fused activation/quant production;
- 0.4940 ms: shared gate/up W8A16, already selected.

This means the next useful lane is not another dense flag or small-N tile
sweep. It must change the **M=2 grouped-MXFP4 architecture** enough to remove at
least 0.50 ms per verifier cycle, for example by reducing scheduler/gather
traffic or specializing the two-row route structure. It must first pass a
four-card real-shape upper-bound gate before another TP4 service load.
