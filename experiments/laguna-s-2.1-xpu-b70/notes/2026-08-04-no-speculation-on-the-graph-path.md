# No speculation, warm, on the graph path: 12.1-12.3 tok/s and flat

Date: 2026-08-04 America/Toronto

Status: **retracted 2026-08-06. This arm captured zero breakable graphs and
exited through the runner audit with status 2. Its throughput rows are eager-
path diagnostics, not graph-path evidence. The corrected M=1 graph result is
in `2026-08-06-the-no-spec-arm-was-forced-eager-on-every-step.md`.**

## What was blocking it

The M8 breakable-graph contract has three drafting terms:

```
not_dflash             speculative_config is None or not use_dflash()
draft_not_greedy       speculative_config is None or draft_sample_method != "greedy"
rejection_not_standard speculative_config is None or rejection_sample_method != "standard"
```

Each is written to fail when `speculative_config is None`, so **absent
speculation trips all three** and the no-drafter arm could never use the graph
path at all. But those terms constrain how draft tokens are produced and
verified: with no speculative config there are no draft tokens and no rejection
sampling, so what they guarantee holds vacuously while the capture stays
target-only.

`VLLM_XPU_LAGUNA_ALLOW_NO_SPEC` (default off) waives exactly those three, and
only when speculation is absent entirely. A drafter that is present but
differently configured remains a violation, because that is a real exactness
risk rather than a vacuous one.

## The measurement

qdepth depth 0, `LAGUNA_NOSPEC_GRAPH=1`, M=1, width-1 capture, warm server,
cold prefix cache on every row:

| case | prompt | conv99 tok/s | prefill tok/s | retrieval | cached | draft tokens |
| :--- | ---: | ---: | ---: | :--- | ---: | ---: |
| 8,192 middle | 8,192 | **12.260** | 2,808.4 | pass | 0 | 0 |
| 32,640 early | 32,640 | **12.213** | 7,505.2 | pass | 0 | 0 |
| 256 sentinel | 256 | **12.128** | -- | pass | 0 | 0 |

**Flat to within 1% across a 128x context range**, with zero draft tokens and
zero cached tokens on every row. That is 1 token per step at ~82 ms per step.

## Reading it

Two things follow, and one does not.

- **Graph capture alone is not the no-speculation lever.** The arm now runs the
  same 291-segment, 145-break structure as the verifier and lands at 82 ms per
  step. Flatness across context is the same signature seen everywhere else this
  session: the step is paid in fixed per-boundary host cost, not in work.
- **The 85 tok/s no-speculation target needs an ~11.7 ms step.** Against 82 ms
  measured, and against a 145-break structure whose boundaries alone are
  ~14 ms of host submission, no arrangement of today's topology reaches it.
  It requires the boundary count to fall by roughly an order of magnitude.
- **It does not follow that no-speculation is inherently this slow.** See the
  caveat.

## Caveat, and it is a large one

The `qdepth` profile **deliberately disables most of the incumbent's optimised
selectors** so that draft depth is the only arm-to-arm variable: BF16 router
top-k, the DFlash context-KV workspace, FP8 W8A16, the segmented and inline
drafter graphs, M12 shared elementwise, mapped gather/scale/add, exact prefill
chunks, wide-prefill QKNorm+RoPE, decode GRF128, and transposed decode scales.
Every one of those is off here.

So **12.1-12.3 is a de-optimised floor for no-speculation, not the best this
stack can do without a drafter.** The q12 profile cannot be used for the
comparison because several of its selectors are contract-pinned to depth 11 and
width 12, which a no-drafter arm does not have. Quoting this number against a
q12 figure would repeat the cold-versus-warm error in a new disguise.

The honest statement is: **on the only profile a no-drafter arm can currently
run, no-speculation decode is 12.1-12.3 tok/s and flat in context.**

## Boundaries

Warm server, cold prefix cache on all rows, TP4, util 0.80, EP4, no async
scheduling. All retrieval field checks passed on all three rows. No
quantisation change, no caching or speculation setting used to inflate any
number -- the arm has no speculation at all, which is the point. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
