# Laguna separate shared gate+up native-M8 MM preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: treatment, exactness boundary, staged stop rules, and
component threshold frozen before implementation, new XPU execution, counter
capture, endpoint service, model generation, payload creation, or submission.
Two independent read-only audits selected the same lane.

## Decision and prior evidence

The standalone shared-gate native-M8 screen is terminal. On physical card 0
it was bitwise exact over 128 pre-timing and 32 post-timing changing epochs and
won all 31 ABBA timing blocks, but saved only
`0.12085622656249995 ms` at the median complete 47-layer cycle. That missed
its frozen `0.150 ms` component threshold, so cards 1 through 3, counters, and
the endpoint did not run. The packet will not be retried and its threshold
will not move.

The shared gate and up projections have the same physical geometry:

```text
gate: [8,3072] @ [3072,256] -> [8,256]
up:   [8,3072] @ [3072,256] -> [8,256]
```

The incumbent executes them as two separate stride-zero B=8/M=1 BF16 BMMs in
the fixed order gate then up. This experiment replaces each one independently
with its own native M=8 BF16 MM while preserving the two calls, their order,
their separate weights and outputs, and every following rounding boundary.
The gate result supplies a concrete mechanism rather than a post-hoc rescue:
removing batched-M1 bookkeeping from two identical K-heavy narrow-N
projections should produce roughly twice the isolated saving.

An up-only campaign is deliberately not run. The most likely result is another
exact but approximately `0.12 ms` standalone signal below the existing
component bar. Measuring the ordered pair is the smallest materially stronger
occupancy treatment.

This is not the rejected merged gate/up experiment. The following remain
forbidden:

- one N=512 projection;
- logical B=16 projection;
- concatenated inputs, weights, or outputs;
- packed or transformed shared weights;
- a custom fused gate/up GEMM;
- projection reordering or overlap; and
- shared-down native MM.

The prior merged N=512 form was exact in only 24/64 changing epochs and the
logical-B16 form in only 18/64. Neither implementation nor result may be
reused.

## Frozen starting identity

- approved LocalMaxxing record:
  `cmrx6p5dv001bo4017hb7sixz`;
- conservative approved throughput:
  `33.89498511171744 tok/s`;
- main repository before this note:
  `2d396f0e2f753eff627c2229583aa8cca1bc125b`;
- vLLM:
  `3dae2ce383a009624bc6ff3e8660851fab5c12e0`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- local target and draft root:
  `/mnt/fast-ai/llm-models/laguna-s-2.1`;
- checkpoint config SHA-256:
  `9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6`;
- boot ID:
  `0b7f98a5-e50a-46a5-81ea-15938b55317a`; and
- approved runtime shape: eager exact target, DFlash depth 7, BF16 KV,
  TP4/EP4/DP1/PP1, one active request, literal routed-W1 N64.

The current source trees contain default-off closed candidates. Their presence
does not authorize stacking. The shared-down MM, BF16 router, BF16 attention
MM, graph, auxiliary stream, remote-zero, expert transaction, and W1 N128
selectors remain off.

All new fixtures, caches, temporary files, logs, run roots, and evidence must
use local NVMe/ext4 under `/mnt/fast-ai`. The external Corsair USB is
backup-only.

## Single treatment

Add one default-off selector:

```text
VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=1
```

The standalone gate selector must be literal `0` whenever this selector is
enabled. Ambiguous or simultaneous selection must raise.

Control:

```text
gate = stride-zero B=8, M=1, K=3072, N=256 BF16 BMM
up   = stride-zero B=8, M=1, K=3072, N=256 BF16 BMM
```

Candidate:

```text
gate = native M=8, K=3072, N=256 BF16 MM
up   = native M=8, K=3072, N=256 BF16 MM
```

Both arms retain the exact incumbent:

- separate gate and up modules and parameter tensors;
- gate-then-up execution order;
- BF16 gate and up outputs;
- shared SiLU BF16 rounding, BF16 multiply, and shared down BMM;
- routed experts, W1 N64, route-parallel W2, and fixed gather;
- shared+routed elementwise bundle and Q/K RMSNorm+RoPE bundle;
- fixed-rank BF16 reduction;
- attention, KV writes, collectives, DFlash, and sampling; and
- eager execution with every graph selector off.

No native XPU kernel or binary change is expected. The two candidate calls use
the existing eager `torch.mm` primitive under two strict vLLM markers.

## Fail-closed runtime scope

Only `LagunaMoE.shared_expert.gate_proj` and
`LagunaMoE.shared_expert.up_proj` in the exact target verifier may receive the
new markers. Each marker must identify its own projection. Dispatch requires:

- Intel XPU eager execution outside a compiler;
- exactly eight contiguous BF16 rows `[8,3072]`;
- `UnquantizedLinearMethod`;
- one contiguous BF16 weight `[256,3072]` on the same device;
- no bias;
- the exact approved shared-elementwise plus QKNorm/RoPE record stack;
- literal routed-W1 N64;
- DFlash depth 7 with TP4/EP4/DP1/PP1 and one active request; and
- both gate and up markers present on the expected shared expert only.

An enabled matching M=8 call that violates dtype, shape, layout, method,
device, bias, source stack, projection identity, or execution mode must raise
rather than silently fall back. M=1 decode, M=2..7 verifier tails, prefill,
draft, dense MLPs, routed linears, unmarked M=8, and shared down retain the
literal incumbent path.

The actual checkpoint-selected forward proof must observe exactly two native
MM calls in the required gate-then-up order and zero native-MM calls on
unmarked linears. Bad layout for either marked projection must raise before a
primitive is called.

## Stage zero: one-card exactness kill screen

Before any new tensor-bearing command, build and independently audit a
hash-frozen Stage-0 fixture, runner, analyzer, tests, and tracked authorization
packet. Imports and packet validation must remain pre-tensor. The packet must
freeze source/tool/fixture/runtime/binary/model hashes, physical card 0, the
exact command and local-NVMe output root, and all downstream actions false.

Run exactly one valid physical-card-0 screen with 128 deterministic changing
epochs. Change the `[8,3072]` BF16 input and both independent `[256,3072]`
weights. Include finite random values, signed zeros, subnormals, large finite
values, cancellation-heavy values, and rank-boundary patterns. For every
epoch require raw `uint16` equality and `torch.equal` at:

- literal BMM versus native MM gate output;
- literal BMM versus native MM up output;
- candidate repeat for both projections;
- shared SiLU BF16 intermediate;
- shared BF16 multiply output;
- incumbent shared-down output;
- shared+routed add; and
- simulated fixed-rank reduction.

Input and both weight hashes must remain unchanged, and fixture/output hashes
must be unique across epochs rather than replaying a hot tensor. The dispatch
proof must cover marked gate/up M=8, marked M=1..7, unmarked M=8, prefill,
dense, draft, shared down, bad row layout, bad weight layout, and a missing or
mismatched projection marker.

One raw mismatch, missing dispatch, wrong call order, unexpected native call,
mutation, nondeterministic repeat, or missing rejection classifies
`stage0_exactness_failed_stop` and closes the treatment before component
timing. A pre-tensor/tooling failure may use a new root only after preserving
the terminal evidence and changing solely the diagnosed tooling defect.

## Four-card component gate

Only a complete Stage-0 pass authorizes construction and independent audit of
the four-card component tooling. A later tracked execution packet must freeze
one fresh local-NVMe root, exact source/tool/fixture/runtime hashes, four
physical mappings, and all downstream actions false.

Each card independently repeats all 128 pre-timing exactness epochs, then 32
post-timing epochs. Timing measures the ordered gate+up pair only:

- 47 distinct input tensors, one per logical layer; gate and up share the
  layer's input, and both arms replay only the same immutable ordered
  47-tensor tuple;
- 47 distinct gate weights and 47 distinct up weights, with unique raw BF16
  hashes and pairwise-nonaliasing storage across all 94 tensors;
- four separate 47-slot output rings for gate-control, gate-candidate,
  up-control, and up-candidate, pairwise nonaliasing across all 188 outputs;
- unchanged raw input and weight hashes before and after timing;
- 20 untimed complete cycles per arm;
- 31 A-B-B-A blocks;
- 64 complete 47-layer paired-projection cycles per arm, exactly
  `64 * 47 * 2 = 6,016` projection calls in declared gate-then-up order;
- one 128 MiB eviction touch before each arm; and
- synchronization only at arm boundaries, with raw nanosecond arm timings
  preserved for independent recomputation.

Fixture creation, allocation, copies, hashes, dispatch proof, elementwise work,
shared down, routed work, collectives, and CPU work remain outside timed arms.

On every card, the candidate must:

- win at least 28 of 31 paired blocks; and
- save at least `0.20 ms` at the median complete 47-layer gate+up cycle.

The `0.20 ms` threshold is frozen before implementation. It is stricter than
the rejected standalone gate's observed `0.120856 ms` and requires the pair to
be materially stronger; it is not a lowered rescue threshold. A cross-card
mean cannot hide one failed physical card.

Any exactness, dispatch, protocol, inventory, hash, win-count, or median-saving
failure stops the campaign before counters. The first valid component
campaign is terminal.

## Counter and endpoint boundary

A four-card component pass authorizes only construction and independent audit
of a fresh cold-counter campaign. It does not authorize counter execution.
Counter execution requires a separate tracked packet and must use sequential
per-card A1/B1/B2/A2 arms, exact outputs, matched pairs, per-card timing,
occupancy/activity/stall/bandwidth guardrails, and no global-mean rescue.

The shared-down treatment proved why this stage is mandatory: it saved
0.598-0.647 ms in its four-card component test, yet later failed four of eight
matched counter pairs and every card's complete frozen guardrail set.

Only a passing frozen counter campaign may authorize construction of a
separate cold endpoint preregistration. Endpoint execution, model generation,
payload creation, record claims, and LocalMaxxing submission remain false
until that later packet exists and passes its own fresh-service exactness,
cache-zero, long-next, rollover, A-B-B-A, target-cycle, and conservative
two-candidate-start gates.

No result from this lane may be submitted unless its lower valid fresh
candidate start beats `33.89498511171744 tok/s` under the matching identity and
all target greedy token arrays remain bitwise identical.
