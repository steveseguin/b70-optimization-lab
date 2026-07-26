# Laguna width-12 inline-attention graph candidate

Date: 2026-07-26 America/Toronto

Status: **preregistered before implementation or device execution**.

## Evidence and hypothesis

The graph-safe paged-decode repair made the exact width-12 attention body
recordable. Capturing each of the 48 attention boundaries as a separate nested
graph was exact and improved the median rate ratio by `0.529%` across the
twelve rows shared with its matched control, but scored only `97.659756 tok/s`.
That treatment retains one Python replay call and one separately scheduled
graph for every attention layer.

The audited target topology consists of 97 collective boundaries and 48
attention boundaries. Attention no longer needs to terminate the current outer
capture segment. Recording it inline should retire exactly those 48 boundaries
while keeping every collective boundary and its order unchanged:

```text
incumbent: 146 outer graphs / 145 eager breaks
candidate:  98 outer graphs /  97 eager breaks
```

The target is still 102 tok/s. The candidate must win through lower target-cycle
latency; emitted tokens per cycle and the generated token stream must remain
equivalent to the standing exact width-12 result.

## Candidate contract

- width 12, DFlash depth 11, TP4/EP4, batch one;
- persistent exact-attention metadata on;
- shared-elementwise and QKNorm/RoPE fusion selectors off;
- draft graph and local argmax off;
- nested attention subgraphs off;
- new default-off inline-attention selector on;
- graph-safe FA2 binary hashes fixed and recorded;
- no prefix/history cache, warmup request, retry, prompt repetition, or scored
  window change.

Inline mode is mutually exclusive with nested attention graphs, diagnostic
evidence/profile modes, KV-transfer hooks, and persistent KV-cache views. It
requires the guarded Breakable graph, exact speculative attention, and
persistent exact-attention metadata.

## Gates

1. Unit tests must prove that an attention boundary executes inside the open
   outer capture without ending/reopening it or incrementing eager counts.
2. Runtime validation must reject selector combinations outside the contract.
3. Every rank must capture and replay exactly `98/97`; any other count rejects
   the candidate.
4. The fixed realistic suite must remain cache-zero, one request at a time,
   and bitwise exact `13/13` against the frozen q=1 teacher.
5. Service shutdown, worker cleanup, port release, and post-run device idle
   must all pass.
6. Promote only if the honest scored median is at least `102 tok/s`. A faster
   diagnostic, invalid output, or different scoring window is not a result.
