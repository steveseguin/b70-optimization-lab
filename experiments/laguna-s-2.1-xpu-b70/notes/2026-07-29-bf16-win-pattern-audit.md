# Laguna BF16-KV win-pattern audit and next-work ranking

Date: 2026-07-29 America/Toronto

Status: **read-only synthesis.** No runtime, kernel, benchmark, or service
change was made for this note. A four-arm prefetch-distance campaign was active
while this audit was written, so this note was committed in a separate
documentation worktree. Its interim results are not used to promote or reject
that candidate.

## Decision

Keep **BF16 KV** as the decode-performance lane.

The strongest verified BF16 configuration is width 12 / DFlash depth 11 with
`VLLM_XPU_LAGUNA_SCALE_VEC=1` and
`VLLM_XPU_LAGUNA_DEQUANT_MAD=0`:

| statistic | conventional tok/s |
| --- | ---: |
| median, 13 exact legs | **102.134914** |
| mean | 101.946829 |
| min / max | 100.597067 / 102.764821 |
| legs at or above 102 | 8 / 13 |
| matched selector-off median | 100.048816 |

Every leg was 13/13 bitwise exact against the canonical q=1 teacher,
cache-zero, and text-hash equal. Kernel commit `46a88e0`; grouped-GEMM binary
SHA-256:

```text
53f3d2941ce322bcdff1b0463ec6fe72387036ea54d3f602a08d690744b3459f
```

The best verified FP8-KV starts were `95.019301665` and `95.818681878`
conventional tok/s. FP8 KV remains a capacity and long-context lane, not the
short-context decode-performance lane. On the current realistic suite, BF16 KV
is about 6.6% faster than the better FP8-KV start.

## Audit scope and evidence classes

The audit covered the 184 chronological Laguna notes under `notes/`, the 84
structured Laguna data packets present when the audit began, the qualified
result packet, the standalone reproduction, the 2026-07-26 campaign transfer
ledger, and the 2026-07-28 kernel-loop evidence.

Claims are separated into four classes:

1. **Verified endpoint win:** exact complete-endpoint evidence with a matched
   identity and a reproducible mechanism.
2. **Verified component result:** real evidence, but not permission to claim an
   endpoint gain.
3. **Unverified or invalid apparent win:** projection, mismatched workload,
   inexact output, dead selector, bad probe, or a single noisy signal.
4. **Closed loss:** exact matched evidence did not beat the incumbent, or the
   mechanism failed a prerequisite before GPU measurement.

This separation matters because several of the largest Laguna numbers were in
class 3.

## What actually won

| change | endpoint effect | mechanism that transferred |
| --- | ---: | --- |
| Batched-exact verifier foundation | first exact DFlash at 33.086 legacy tok/s | Preserve q=1 arithmetic using M=1 numerical lanes, deterministic MoE, and fixed-rank BF16 reductions |
| W1/SiLU fusion plus route-parallel W2 and route/N-tile interleave | 33.086 -> 33.439 | Remove work without serializing expert parallelism; schedule workgroups to retain occupancy |
| Shared-elementwise plus Q/K RMSNorm/RoPE stack | 33.439 -> 33.895 | Small exact fusions can compose even when a standalone endpoint is noisy |
| Breakable PIECEWISE verifier graph | 33.895 -> 92.164 | Remove Python, launch, and synchronization boundaries while retaining a 146/145 structural oracle |
| Persistent exact-attention metadata | 92.164 -> 94.920 | Refresh fixed-address graph-visible state in place; treat ownership and identity as part of correctness |
| Width 12 / DFlash depth 11 | 94.920 -> 100.525 | Emit 6.9% more target-verified tokens per cycle at nearly unchanged cycle time |
| E4M3FN W8A16 for 31 disposable DFlash projections | 100.525 -> 101.942 conventional in the sealed row | Quantize the recoverable drafter, not the canonical target or KV state |
| `SCALE_VEC` exact operand-marshalling removal | matched 100.049 -> **102.135 median** | Delete 32 hot-loop `mov` instructions without changing values, order, precision, DPAS count, or rounding |

The strongest repeated pattern is:

> Wins remove a boundary or unavoidable instruction while preserving the
> numerical and parallel-execution contract.

The progression was not driven by KV bandwidth. The two largest wins were
graph coverage and acceptance per verifier cycle. The newest verified win came
from compiler operand constraints, not changed arithmetic.

## What did not win, and why

### Lower bytes did not help when the boundary remained

- FP8 KV doubled cache capacity but was slower on this decode workload.
- Local argmax moved 4.82 MB less data per cycle but kept the collective round
  trip and regressed to 97.937 tok/s with only 12/13 exactness.
- Context-KV work was measured at roughly 0.48 ms per cycle, too small to
  explain the drafter's cost.

Payload size is not a useful proxy when PCIe collective latency, kernel launch
latency, or conversion overhead remains.

### Fewer launches lost when they serialized useful work

- A persistent expert transaction reduced launches from 282 to 94 but
  serialized expert slots and lost occupancy.
- Remote-route zeroing removed fills but added replacement work and regressed.
- Native BF16 attention MM was component-exact and endpoint-slower.
- Inline attention removed all 48 attention breaks and lost about 11%.

Count removal must be paired with a critical-path and occupancy model.

### Arithmetic transformations were fast or elegant but disqualified

- Folding scale into the FP32 accumulator was about 8% faster and **0/13
  exact**. It changed the rounding boundary.
- Fusing `add(-136)` plus `mul` into `mad` was bitwise-exact over 1,044,480
  component cases but about 1% slower at the endpoint: float-pipe work fell,
  integer-pipe work rose, and the integer pipe was binding.
- Width 14 was slower and 12/13 exact; width 16 was slower and 0/13.

An instruction reduction is valuable only when it removes work from the
binding pipeline and preserves the declared arithmetic.

### Generic selector sweeps mostly measured dead or exhausted spaces

- The generic N-tile 32 and 128 alternatives were exact but both below the
  default 64. That knob is closed.
- Seven recorded selector variables had no reader.
- The earlier prefetch-distance sweep is not reliable evidence for width-12
  decode: the launcher did not read the selector on that path. The active
  2026-07-29 campaign exists to measure a genuinely reachable implementation.
- IGC had already hoisted nearly all proposed scale reload work; the remaining
  opportunity was below the screen threshold.

Require a static reader/call-site audit, runtime entry proof, and postcondition
before spending a leg.

### Apparent large wins were correctness failures

Draft graph capture produced 198.7, 537.4, and 550.9 tok/s, all at 0/13 exact.
Capture ran without real attention metadata, then replay used a launch
specialized to the warmup sequence length. Token id 0 propagated through both
sides of verification and produced flat 96-100% acceptance.

A valid DFlash acceptance curve decays with position. A flat curve is a
correctness alarm, not a performance result.

### Projections and single draws were mistaken for achieved results

There is no qualified measured Laguna result around 105 tok/s in the audited
artifacts. The `105.5` depth-15 chain and `105.9` tree were projections. The
tree model later failed workload matching and empirical-cost checks; corrected
zero-overhead projections were only 101.79-101.83.

The sealed `101.941721` conventional row was a favourable single draw. The
same old configuration later had an eleven-leg median near 100.440. The
current `SCALE_VEC` configuration did not regress to 100: its stored 13-leg
median is 102.135, even though individual fresh legs can land near 100.6.

Report median, mean, range, and `n`. Do not promote the maximum of a campaign.

## Where time is actually going

The best available verifier attribution is relative because event profiling
inflates absolute time:

| segment | count | relative share |
| --- | ---: | ---: |
| graph segments, including grouped expert GEMM | 146 | 69.2% |
| collectives | 97 | 22.1% |
| attention | 48 | 8.7% |

At width 12, twelve rows reach the generic grouped expert kernel in one call.
The generic selector computes `A_avg_M` by integer-dividing roughly 120 routes
over 64 experts, then selects the same `8x64x32` policy. Actual per-expert M is
small and the M dimension is poorly occupied. Expert weight streaming reaches
roughly 350-427 GB/s against a 521 GB/s achievable ceiling, while compute is
barely used. The gap is therefore in dequantization, dispatch, scheduling, and
small-M occupancy around the stream—not simply in raw DRAM bandwidth.

Separately, the DFlash drafter runs eager at roughly 9.0 ms of an approximately
30.5 ms decode cycle while accounting for only about 3% of cycle weight
traffic. It is the largest disproportionate single item.

## Ranked continuation

### 1. Finish the active prefetch campaign; specialize only a repeatable winner

The campaign interleaves `old`, `new-pd6`, `new-pd12`, and `new-pd3`, five
rounds each. All round-one arms were exact. The first `pd3` leg was 0.78% above
the first old leg, inside the measured 1.63% host spread; it is not yet a win.

The runtime-plumbed candidate adds a prologue and mainloop dependency tax. If a
distance wins at `n=5`, rebuild only that distance as a compile-time constant,
removing the experiment plumbing, then repeat against the frozen incumbent. If
no new arm beats old at the median, close the route.

### 2. Build length-generic, prebuilt DFlash attention metadata and graph the drafter

This is the highest-upside direction and repeats the two strongest proven
patterns: graph coverage and persistent fixed-address metadata.

The existing attempt already fixed outer-tensor address drift and retained
`enforce_static_inputs=True`. The remaining defect is concrete:
FlashAttention's launch is chosen from capture-time `max_seq_len`; warmup
captured a length-12 launch and replayed it at hundreds of tokens.

The next experiment must:

1. make the drafter's attention launch valid across the declared sequence
   range, using prebuilt persistent metadata or explicit length buckets;
2. preserve stable object, base-pointer, view, offset, and owner signatures;
3. compare eager and graph DFlash drafted ids/logits at several lengths before
   an endpoint run;
4. require a decaying per-position acceptance curve;
5. require 13/13 q=1 identity, cache-zero, and unchanged target topology;
6. fail closed on absent metadata or any static-input drift.

Do not re-enable the old graph flag without those component gates.

### 3. Continue exact hot-loop deletion in the generic INT4 grouped GEMM

`SCALE_VEC` proved this class can clear the host noise floor. Search the
dequantization path for more unnecessary copies, address recomputation, or
operand constraints while keeping operations, values, types, and order
identical. The `bfn`/shift/bias/scale sequence feeding DPAS is the main static
mass.

Screen every candidate in this order:

1. ISA delta and pipeline attribution;
2. no new spills or reduced occupancy;
3. exhaustive bitwise component comparison, including negative zero,
   subnormals, and extreme BF16 scales;
4. interleaved exact endpoint A/B at `n >= 5`;
5. extend a positive arm to `n >= 13`.

Do not repeat scale folding or arithmetic reassociation.

### 4. Add M-aware policies for the actual width-12 routed-expert distribution

The generic 32/64/128 N-tile knob is closed, but the policy-selection premise is
not. It chooses from an integer average that hides the real distribution. A
new candidate should first record the per-expert row-count histogram, then
choose or add a policy based on `max(rows_per_expert)` or small-M buckets.

This follows the earlier route-interleave win: improve workgroup occupancy
without serializing expert work. Component benchmarking should precede a full
build because one generic instantiation already peaks near 116.7 GB on this
125 GB host.

### 5. Consider actual collective-boundary removal only after the above

Collectives are about a fifth of profiled verifier time. Reducing payload while
keeping 97 boundaries failed. A useful change must combine or remove round
trips. It is lower priority because it changes the audited graph topology and
has a history of structural regressions.

## Routes not to reopen without new evidence

- FP8 KV for this short-context decode score;
- verifier width above 12;
- generic N-tile 32/128;
- local argmax payload reduction;
- context-KV micro-optimization;
- the existing inline-attention or attention-subgraph implementations;
- scale folding or other rounding-boundary changes;
- moving graph capture outside the scored request;
- tree speculation based on the corrected rescue evidence;
- selectors without a reader and runtime execution proof;
- hardware recovery based on a wrapper that did not prove its probe executed.

## Operating rule for the next campaign

Prefer a candidate when it satisfies all four:

1. it attacks a measured dominant or disproportionate cost;
2. it removes a boundary or instruction on the critical path;
3. its exactness is structural rather than merely observed;
4. it can be screened cheaply before occupying four GPUs.

This rule favours drafter metadata/graph work, exact INT4 instruction deletion,
and M-aware occupancy. It rejects most broad flag sweeps, byte-count
optimizations, and arithmetic rewrites before they consume a campaign.

## Durable pointers

- [campaign transfer ledger](2026-07-26-campaign-transfer-ledger.md)
- [qualified BF16 record](2026-07-26-width12-dflash-fp8-w8a16-record.md)
- [BF16/FP8 KV decision](2026-07-26-kv-cache-precision-decision.md)
- [cycle attribution and generic tile closure](2026-07-28-cycle-attribution-and-w1-tile.md)
- [draft graph root cause](2026-07-28-draft-graph-capture-root-cause.md)
- [confirmed scale-vector win](2026-07-28-scale-vec-result.md)
- [running INT4 kernel loop](2026-07-28-kernel-loop-ledger.md)
- [retracted row-count claim and corrected measurement](2026-07-28-moe-runs-one-row-at-a-time.md)
- [standalone reproduction](../../../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md)

