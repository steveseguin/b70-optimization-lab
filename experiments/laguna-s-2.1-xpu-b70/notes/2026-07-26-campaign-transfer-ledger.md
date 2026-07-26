# Laguna S 2.1 B70 campaign transfer ledger

Date: 2026-07-26 America/Toronto

Status: **campaign closeout and reusable-learning index.** The approved record
remains `102.971435596` tok/s; no new run was performed for this note.

## Why this file exists

The chronological notes preserve each experiment, but they are too numerous
to be the first read for a future model. This ledger separates:

- changes that moved the complete endpoint;
- plausible changes that failed;
- correctness and harness failures that must not recur;
- rules that transfer to other models and runtimes.

The authoritative record identity and resume point remain
[`../RESUME.md`](../RESUME.md). The record note is
[the width-12 DFlash W8A16 result](2026-07-26-width12-dflash-fp8-w8a16-record.md).

## Result progression and what actually worked

| Stage | Valid tok/s | What moved the endpoint | Transferable lesson |
| --- | ---: | --- | --- |
| First exact DFlash | `33.086` | Batched verifier with M=1 numerical lanes, deterministic direct MoE, fixed-rank BF16 reductions | Speculation is useful only after target verification is numerically equivalent to the declared teacher |
| Expert launch/occupancy stack | `33.268` then `33.439` | Fused W1+SiLU, route-parallel W2, route/N-tile interleave | Fewer launches can lose occupancy; preserve parallelism while fusing |
| Exact fusion stack | `33.895` | Shared-elementwise plus Q/K RMSNorm/RoPE stack | Small exact fusions can compose even when a standalone endpoint is noisy or negative |
| Breakable PIECEWISE graph | `92.164` | Audited 146-graph/145-break target topology | Removing Python/launch/synchronization boundaries can dwarf kernel micro-tuning |
| Persistent attention metadata | `94.920` | Fixed-address metadata refreshed in place | Allocation and metadata churn can be a real graph-path cost |
| Width 12 / depth 11 | `100.525` | More target-verified tokens per cycle at almost unchanged cycle time | Sweep verifier width and acceptance together; the best depth is where marginal acceptance no longer pays for verifier cost |
| Draft W8A16 projections | **`102.971`** | 31 DFlash dense projections converted to E4M3FN W8A16 plus exact auxiliary workspace | Quantize the disposable drafter before the canonical target; require execution logs and unchanged target verification |

The biggest step was graph coverage, not a GEMM tile. The final 3% came from
several distinct, measured mechanisms. Future campaigns should profile the
whole decode cycle before assuming the largest matrix is the largest
opportunity.

## Model- and speculation-specific lessons

### Match the draft to the target's numerical basis

The plain BF16 Laguna DFlash checkpoint accepted `0/8,449` proposals against
the INT4 target because the target's Hadamard-rotated auxiliary states did not
match the plain draft. The quantization-matched
`Laguna-S-2.1-DFlash-INT4` immediately restored acceptance. Similar model names
are not proof of compatible hidden-state bases.

### A verifier is only safe when its inputs are live

Draft graph capture reported `198.703` tok/s and 95.91% acceptance but matched
the teacher `0/13`. Replay had made proposed-token buffers stale or aliased, so
the accept path effectively rubber-stamped drafts. Target verification is not
an abstract guarantee; every token, cache, metadata, and buffer dependency
feeding it must be current on every replay.

The nearly flat acceptance survival row (`847` to `818`) was a strong failure
signature. Valid depth-7 acceptance decayed (`1272` to `300`). Preserve
per-position acceptance histograms as correctness telemetry, not just
performance telemetry.

### Numerical width is a contract, not just a tensor shape

Width 12 was exact and optimal. Width 14 was slower and `12/13`; width 16 was
slower and `0/13`. One-prompt drift is easy to miss in throughput-only tests.
When widening a verifier, audit every shape guard, collective slot, fixed
buffer, reduction order, and row-wise numerical lane.

### Empirical acceptance must match the exact workload

The first rank-2 tree probe used raw prompts while the benchmark used chat
templates, changing every prompt length and every generated hash. Its 43.71%
rescue rate was directional, not benchmark-matched. After the projection was
recomputed on consistent empirical counters, the one- and two-alternate trees
projected only `101.79` and `101.83` tok/s at zero overhead, below the goal.
See [the correction](2026-07-26-rank2-probe-correction.md).

Do not mix counters from different prompt construction, sampling, commit,
template, or request APIs in one projection.

### Separate target, draft, and KV precision

The final FP8 treatment applies to DFlash projection weights, not the target
and not the KV cache. Target-verified speculation made lossy draft
quantization safe after the 13/13 gate. KV quantization changes target
attention state and is a separate quality lane. See
[the KV precision decision](2026-07-26-kv-cache-precision-decision.md).

## Performance lessons from rejected routes

| Candidate | Measurement | What it teaches |
| --- | --- | --- |
| Explicit FP8 KV | 2x cache capacity, `4.132%` slower in the early matched-DFlash short-context A/B, outputs differed | Lower KV bytes are primarily a capacity lever until a native attention path proves a long-context speed gain |
| Remote-route zeroing | Removed 95 fills/cycle, regressed to `32.591` | Launch count alone is not a cost model; replacement work and occupancy matter |
| Fused persistent expert transaction | 282 to 94 launches, slower lower start | Fusion that serializes expert slots can lose more occupancy than it saves |
| Native BF16 attention MM | Component exact, endpoint slower | A custom GEMM is not automatically better than the runtime-selected small-GEMM path |
| QKNorm/RoPE standalone | 144 to 48 isolated launches, lower endpoint start missed record | Component wins need causal endpoint crossover evidence |
| Shared-elementwise at width 12 | Exact, `100.525` to `99.567` | A kernel widened beyond its original hot shape can erase its fusion benefit |
| Width 14 / 16 | `97.226` at `12/13`; `87.899` at `0/13` | Max draft depth is not max throughput; acceptance tails and verifier cost must be co-optimized |
| Local draft argmax | 4.82 MB/cycle less traffic, `100.525` to `97.937`, `12/13` | At these PCIe TP4 message sizes the boundary was latency/work-count bound, not payload-bandwidth bound |
| Draft graph capture | `198.703`, `0/13` | A spectacular number plus abnormal acceptance is usually corruption, not an optimization |
| Moving lazy capture outside the scored request | Would remove a 10+ second cold cost | Relocating required work outside the metric is benchmark manipulation unless the benchmark contract explicitly changes |

For the local-argmax result, reducing bytes did not remove a round trip. The
next useful collective hypothesis would remove or combine boundaries, not
send the same number of smaller messages. That remains a direction, not a
measured Laguna win, and any topology change must define a new audited graph
count.

## Graph and topology lessons

### Graph implementation matters more than the word "graph"

The deterministic non-Breakable graph lane was slow and inexact; the guarded
Breakable PIECEWISE design produced a 2.72x valid step change. Never classify
an optimization class as open or closed from one implementation.

### Preserve a structural oracle

The valid target topology is 146 graph segments and 145 eager breaks per rank.
A failed width-12 attempt expanded to 685/684 because `(M-1)` extra per-row
boundaries appeared across 49 layer/embedding sites. The count made the
serialization visible before throughput interpretation.

Graph capture now needs a hard segment ceiling before allocating many
segments. A topology assertion is a safety mechanism: the explosion exhausted
device resources and destabilized later work.

### Fixed-address state needs stable ownership, not merely stable shapes

Persistent exact-attention metadata won only after object, base-pointer,
active-view, offset, and owner signatures were guarded. Per-slot collective
buffers also had to preserve fixed address, non-aliasing, deterministic order,
and stable shape after first use. Treat graph-visible buffer ownership as part
of run identity.

## Harness, recovery, and evidence lessons

### A flag in `identity.txt` is not proof that code ran

Seven recorded selector variables had no reader. The intended draft FP8 LM
head also lacked its required runtime preparation marker, so the final record
does not attribute gain to it. For every experimental feature require:

1. a static call-site/read audit;
2. a runtime entry marker or counter;
3. a postcondition that proves the intended shapes/counts were treated;
4. fail-closed analysis when any marker is absent.

### An edit command reporting success is not proof the file changed

Several probe fixes claimed success without reaching disk. Inspect the exact
file and diff before any expensive launch. Syntax checks validate the file
that exists; they do not validate an imagined edit.

### A missing probe result means unknown, not failure

The XCCL wrapper invoked a nonexistent scratch-local Python file. Summary
`0/4` counters were read as collective failures even though Python never
entered. Driver reload, four FLRs, and shared-memory cleanup were then
incorrectly justified from non-results.

Every diagnostic wrapper should:

- resolve and validate its source before creating an artifact root;
- write anchored stage markers per rank;
- distinguish pre-launch, import, allocation, collective, verification, and
  teardown failure;
- emit one unambiguous final result marker;
- preserve rank logs;
- authorize no privileged recovery by itself.

Never escalate hardware recovery until the probe proves it executed and names
the boundary that failed.

### Cold costs remain cold costs

Lazy graph capture occurred inside prompt 0 and created a 10+ second first
inter-token gap. It is a real service-latency issue even though it affects only
one request. Moving it outside the scored window was correctly rejected.
Maintain separate first-request latency, steady decode, and suite-median
metrics rather than hiding initialization.

## Reusable experiment protocol

For the next model:

1. Pin target, draft, tokenizer, KV dtype, source commits, binaries, graph
   mode, prompt construction, metric, and quality promise before tuning.
2. Inspect publisher config separately for weight, activation, router, and KV
   precision; never infer one from another.
3. Establish a canonical target-only teacher and target-verified speculation
   gate before optimizing the draft.
4. Profile the complete cycle and set a minimum component saving before
   endpoint work.
5. Use default-off, narrowly shaped selectors with static and runtime
   execution proof.
6. Preserve graph topology/work-count assertions and a capture segment ceiling.
7. Run the first valid preregistered cold result once; do not retry for a
   favorable number.
8. Record accepted tokens/cycle and per-position acceptance alongside tok/s.
9. Treat component wins, projections, capacity wins, and endpoint throughput
   as four different evidence classes.
10. Preserve every meaningful negative with its identity and failure signature.
11. Inspect raw files and per-rank logs before believing a summary.
12. Submit only after independent identity, correctness, cache-zero, metric,
    teardown, and API-response checks.

The cross-model form of these rules is indexed in
[the research workflow playbook](../../../docs/research-workflow-playbook.md#cross-model-patterns-worth-reusing).

## Durable record pointers

- [record resume](../RESUME.md)
- [record note](2026-07-26-width12-dflash-fp8-w8a16-record.md)
- [KV-cache decision](2026-07-26-kv-cache-precision-decision.md)
- [source snapshot index](../../../patches/laguna-s-2.1-xpu-b70/README.md)
- [structured record packet](../../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json)
- sealed run:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-width12-dflash-fp8-e596ef154-20260726T214259Z`
