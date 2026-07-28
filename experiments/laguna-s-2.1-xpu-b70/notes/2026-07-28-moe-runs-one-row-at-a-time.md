# The Laguna MoE runs one row at a time at width 12

Date: 2026-07-28 America/Toronto

Status: **structural finding, no throughput claim.** Scored baseline unchanged
at **100.074 tok/s conventional**; sealed record `101.94172124017027`.

## Observation

Logging the row count at every fused-expert invocation, across a full
13-prompt run that passed **13/13 exact**:

```text
LAGUNA_MOE_ROWS num_rows=1 seen=[1]
```

One is the only value ever observed. The verifier runs twelve rows per cycle,
so the expert GEMM is invoked **once per row**: roughly `12 x 48 = 576`
single-row expert-GEMM launches per cycle instead of about 48 batched ones.

Artifact:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/moerows2-d1a72ff78-20260728T043222Z`

The log sits immediately before `laguna_m8_fused_expert_interface`, and
`num_rows` is `hidden_states.shape[0]`, so this is the count handed to the
kernel and not a setup-time value.

## Why this matters

Per-segment event profiling on the same stack puts **69.2%** of a verifier
forward inside the graph segments that hold this GEMM, against 22.1% in the 97
collectives and 8.7% in attention. Against 532 GB/s achievable, the 5.6 GB/rank
of weight traffic floors at 11.5 ms versus a ~30.5 ms cycle: about **38% of the
bandwidth roofline**, with compute near 1% utilised.

`M=1` explains that shape of result. Every launch is a GEMV, the worst
arithmetic intensity available, and two tokens routed to the same expert in the
same cycle cannot share that expert's weight read. At twelve rows and top-10
routing, roughly 96 distinct experts are touched per layer while 120 expert
reads are issued.

It also explains why the W1 N-tile could not be swept: the tuned `N32` and
`N128` policies require **exactly eight rows**. At one row they are structurally
unreachable, which is what the Python guard was encoding.

And it explains the shape of this campaign's results. Width, fusions, KV format,
boundary count, embedding replication and local argmax all moved the number by
about +/-2% because they all act outside the 69%.

## What is not yet known

**Whether per-row execution is deliberate.** The selector is named
`VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE` and this lane's entire contract is bitwise
equality with the q=1 teacher. Executing one row at a time is a way to
guarantee a fixed reduction order, so this may be a considered exactness
tradeoff rather than an oversight. That question must be answered before any
batching change is attempted, because the contract is not negotiable.

The kernel itself accepts `1..8` rows, so twelve rows cannot become a single
launch. Eight plus four would be two launches instead of twelve, and the
eight-row group would additionally make the existing `N32`/`N128` policies
reachable with no new kernel code.

## Next

1. Determine why the batched path emits one row: read the caller that splits
   the verifier's twelve rows, and establish whether the split exists for
   fixed-order determinism or by accident.
2. If determinism is the reason, find whether an eight-row group can preserve
   the same reduction order. If it can, the change is a call-pattern change
   rather than a kernel rewrite.
3. Only then consider new `M=12` tile policies and a rebuild.

Any candidate must clear 13/13 bitwise exactness, and this host's run-to-run
spread was **1.63%** across three identical-config legs, so nothing under about
1.5% is detectable without repeats.
