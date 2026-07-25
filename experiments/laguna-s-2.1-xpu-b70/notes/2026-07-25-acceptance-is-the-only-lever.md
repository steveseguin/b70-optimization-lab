# Laguna — throughput is acceptance; the path to 100 tok/s is width, not depth

Date: 2026-07-25 America/Toronto

Status: analysis of a measured benchmark leg. No record claim, no submission.

Source: `runs/laguna-confirm-record-20260725T191935Z`, one candidate leg of the
record configuration. 13 real cold prompts, 512 tokens, 13/13 `cached_tokens=0`,
`all_exact: True` against the canonical q=1 teacher. Measured **93.990 tok/s**
scored (median tokens 1-100 after TTFT) against the approved record 94.920.

## Throughput is acceptance, with r = 0.999

Per-prompt scored rate against emitted tokens per cycle, derived from streaming
token arrival bursts (each burst is one speculative cycle; burst size is
accepted + 1):

| prompt | tok/s | emit/cycle | acceptance |
| ---: | ---: | ---: | ---: |
| 12 | 63.2 | 2.041 | 14.9% |
| 5 | 72.9 | 2.273 | 18.2% |
| 11 | 84.2 | 2.632 | 23.3% |
| 3 | 88.4 | 2.778 | 25.4% |
| **9** | **94.0 (median)** | **2.941** | **27.7%** |
| 2 | 114.0 | 3.571 | 36.7% |
| 8 | 122.5 | 3.846 | 40.7% |
| 1 | 155.6 | 4.762 | 53.7% |
| 10 | 196.2 | 5.882 | 69.7% |

Correlation of emit/cycle against tok/s, excluding the stalled first prompt, is
**r = 0.999**. Cycle time derived independently per prompt is constant at
**29.98-32.29 ms** while acceptance varies **4.7x**. Throughput variation in
this suite is acceptance variation and nothing else.

## The gap to 100, exactly

The scored metric is the median of 13, currently prompt 9 at 94.0. Six prompts
already exceed 100, so one more crossing moves the median.

Prompt 9 needs emit/cycle **2.941 -> 3.129**, i.e. mean accepted
**1.941 -> 2.129**, i.e. **+9.7% accepted tokens per cycle**, i.e. acceptance
**27.7% -> 30.4%**, a gain of **2.7 percentage points**.

For comparison, buying the same 6.4% from cycle time would require 2 ms, which
is four times the entire context-KV lever measured in Phase 0 (0.480 ms).

## The acceptance chain does not decay — the failure is at position 1

Conditional acceptance across all 13 prompts, 418 cycles in the scored window:

| position | P(reached) | P(accept given reached) |
| ---: | ---: | ---: |
| 1 | 100.0% | 67.5% |
| 2 | 67.5% | 66.3% |
| 3 | 44.7% | 72.7% |
| 4 | 32.5% | 75.7% |
| 5 | 24.6% | 71.8% |
| 6 | 17.7% | 82.4% |
| 7 | 14.6% | 63.9% |

Conditional acceptance is **flat between 63.9% and 82.4% at every depth**. It
does not decay. **32.5% of cycles accept zero tokens** and waste all seven
proposals; **9.3% accept all seven**.

The draft either locks on or misses immediately. Depth is therefore not the
constraint, which also explains why the depth sweep found 7 optimal and deeper
useless: extending a chain that does not decay adds little, while the 32.5%
of cycles that die at position 1 are untouched by any amount of depth.

## Consequence: spend the M=8 budget on width, not depth

The current allocation is one linear chain of depth 7. Given a flat conditional
chain and a 32.5% position-1 failure rate, that is the wrong shape. Width at the
front converts zero-accept cycles into productive ones; depth cannot.

**Threshold, stated precisely:** if the tail chain is unchanged, the median
prompt clears 100 tok/s when `P(accept >= 1)` rises from **67.6% to 74.1%**.
That is exactly the question of whether the target's argmax lies in the draft's
**top-2** rather than its top-1, for 74.1% of cycles. A top-1 to top-2 coverage
gain of 6.5 points is small; such gaps are typically 10-15 points.

The M=8 verifier budget is unchanged by this, so the exact verification path,
the Breakable graph, and the persistent metadata all remain valid.

## Next measurement

Capture, per cycle, the draft's top-2 proposals at position 1 and the target's
verified argmax, then compute `P(target argmax in draft top-k)` for k = 1 and 2.
If top-2 coverage is at or above 74.1%, a width-2 tree clears 100 tok/s and the
tree implementation is justified. This is a bounded diagnostic and makes no
throughput claim.

## Corrections to earlier claims in this campaign

- The 11.494 s first-request stall on prompt 0 is real — lazy M=8 graph capture
  plus five Triton JIT compilations firing on the first decode step, which
  vLLM's own JIT monitor warns about — but removing it changes the scored median
  by **0.000 tok/s**, because the median is robust to that outlier. It is a
  latency bug, not a throughput lever.
- The context-KV workspace lever, whose exactness gate passed today, has a
  measured ceiling near 1.5% and attacks cycle time, which this analysis shows
  is not the binding constraint.
