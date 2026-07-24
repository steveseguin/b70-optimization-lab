# Laguna exact M=8 routed-gather finalize fusion preregistration

Date registered: 2026-07-24 America/Toronto

Status at registration: design and gates frozen before implementation, native
build, XPU execution, model load, endpoint generation, network access, payload
creation, or submission. Two independent read-only source audits selected and
reviewed this lane. The main agent then traced the current modular-MoE dataflow
and corrected the launch accounting against the actual record stack.

## Question and bounded treatment

Can one exact M=8 Laguna target-verifier kernel replace only:

```text
incumbent fixed-slot-order MoeGather
  -> existing laguna_m8_scale_add
```

while preserving every protected arithmetic boundary and leaving the
route-parallel W2 kernel unchanged?

The current record already fuses routed scale with shared add. Therefore the
control is **two launches per layer**, not three:

```text
accum_fp32 = fixed slot-0..9 FP32 weighted sum of BF16 W2 route rows
routed_bf16 = BF16(accum_fp32)
scaled_bf16 = BF16(float(routed_bf16) * 2.5)
final_bf16 = BF16(float(shared_bf16) + float(scaled_bf16))
```

The candidate performs that literal sequence in one kernel. It must contain
explicit BF16 `routed_bf16` and `scaled_bf16` values. It must not fold `2.5`
into router weights, scale the FP32 accumulator, add shared output before the
routed BF16 boundary, reassociate the ten-slot sum, use a fused final FP32
expression, or move the later fixed-rank reduction.

The default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=1
```

The treatment is materially different from the rejected full expert
transaction. That experiment serialized W2 expert slots and reduced W2
parallelism from 3,840 to 384 workgroups per card. This experiment retains the
incumbent route-parallel W2 call, geometry, route interleave, remote-route
zeroing semantics, INT4 dequantization, DPAS order, and BF16 route-row stores.
Only the already separate post-W2 gather/finalize tail changes.

## Budget and non-claim

The retained profile attributes `0.441856 ms` per 47-layer target cycle to
`MoeGather`. The current exact `laguna_m8_scale_add` component measured about
`0.224-0.234 ms/cycle`, for a present two-kernel scope of roughly
`0.666-0.676 ms/cycle`.

That total is an upper bound on the scope, not a predicted saving: the
candidate retains all gather work and adds a shared load plus two BF16
rounding operations to the gather kernel. The certain structural change is
exactly:

```text
94 control launches/cycle -> 47 candidate launches/cycle
```

No endpoint gain is claimed by this preregistration.

## Frozen starting identity

Implementation starts from clean, tracked sources:

- vLLM:
  `503f7784cf9d1704109b1e4650427fb4f417d604`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`; and
- current approved record:
  vLLM `8936aac144929190c1e53f8b8624ca397ce16f5b`,
  XPU kernels `b6076ce1249ffee0e30bee528f4cd15c3bffb234`,
  LocalMaxxing `cmrx6p5dv001bo4017hb7sixz`, and
  `33.89498511171744 tok/s`.

The two later source commits contain only default-off native shared-GEMM and
W1-N128 experiments. Their selectors must remain off in this lane. A future
component packet must freeze the post-implementation commits, installed
native-library hashes and paths, compiler/runtime/driver identity, physical
card mapping, boot ID, scripts, fixtures, and expected native schema before
the first XPU process.

## Runtime and output-ownership contract

The selector may dispatch only when all of the following are true:

- Intel XPU, eager execution, and no graph, AOT, or compilation;
- Poolside Laguna target execution, never the DFlash draft;
- the explicit exact target-verifier marker is present;
- exactly M=8, hidden size 3,072, top-k 10, 256 global experts, 64 local
  experts, TP4/EP4/DP1/PP1, and one shared expert;
- contiguous BF16 route rows `[80,3072]`, shared output `[8,3072]`, and final
  output `[8,3072]`, plus contiguous FP32 top-k weights `[8,10]` and int32
  flattened route map `[80]` (logical `[8,10]`, indexed
  `token * 10 + slot`);
- routed scale is exactly `2.5`, there is no routed-output transform, the
  routed output is not already reduced, sequence parallelism and DBO are off,
  and final all-reduce is not skipped;
- exact batched MoE, fused-W1/route-parallel-W2, N64 W1, route interleave,
  shared elementwise, and exact fixed-rank reduction are enabled;
- the default-off remote-route-zero optimization, native shared gate/up/down,
  router cast-skip, W1-N128, full fused transaction, and auxiliary-stream
  candidates are disabled, while the incumbent route-parallel W2 zero-filled
  remote rows remain unchanged; and
- the new native symbol and explicit combined-output plumbing are present.

M=1, verifier tails M=2..7, prefill, draft, non-Laguna models, LoRA, graph
paths, and unrelated shapes retain the literal incumbent path. If the
selector is enabled and a candidate-shaped M=8 call violates any predicate,
it must raise before launching a primitive; it must never silently fall back.

The existing shared output is currently owned by `SharedExperts`, while the
route rows are owned inside `XpuFusedMoe`. Implementation must use an explicit
candidate-only API and an explicit `output_includes_shared` result. Only a
successful native combined dispatch may consume the shared output, suppress
the later `laguna_m8_scale_add`, and pass the combined BF16 tensor to the
unchanged final reduction. Mutable or stale implicit state, tensor-shape
inference, and a dummy-output convention are forbidden.

## Stage 0: implementation and CPU/static gate

This note authorizes source implementation and CPU-only validation. It does
not authorize an XPU import/allocation, native primitive execution, profiler,
model load, endpoint, or generation.

The minimal source plan is:

1. Add a strict `TOPK=10`, BF16, M=8 gather-finalize implementation beside
   the incumbent `MoeGather` in `csrc/moe/moe_gather.cpp`, with its own
   `_moe_C` binding and hard input/alias checks.
2. Preserve the incumbent `MoeGather<BF16,10,8>` workgroup geometry and exact
   slot loop. Add only the explicit routed BF16 cast, scaled BF16 cast, shared
   load, final BF16 add, and final store.
3. Add a candidate-only explicit API through the modular XPU expert path. It
   passes the already-produced shared tensor to `XpuFusedMoe` and returns both
   the final tensor and a positive combined-output signal. The generic path
   and all non-XPU expert implementations remain unchanged.
4. In `MoERunner`, suppress the ordinary shared/routed combine only after
   receiving that positive signal, then call the unchanged final fixed-rank
   all-reduce.
5. Add default-off environment/cache identity, fake/meta registration only
   where required for import tests, fail-closed construction/runtime guards,
   dispatch observability, and focused unit tests.

Before any device packet may be written, require:

- Python AST/compile, Ruff, C++ formatting, whitespace, and clean-tree checks;
- CPU guard tests for matching dispatch and every one-field corruption;
- tests proving M=1..7, draft, prefill, non-Laguna, graph/compile, missing
  symbol, wrong dtype/shape/layout/scale/parallelism, and double-combine cannot
  execute the treatment;
- static checks that W1/W2 calls, arguments, N64 geometry, and route-interleave
  code are byte-identical outside the new finalization branch;
- a host oracle that encodes the ten FP32 additions and both BF16 rounding
  boundaries independently; and
- two independent read-only audits, with all findings corrected before
  freezing implementation commits.

Device tests must be explicitly opt-in and deselected from every CPU test
command. An accidental XPU primitive before the later packet invalidates
Stage 0 evidence.

## Four-card component gate

Only a separate tracked packet committed after implementation freeze may
authorize one component campaign. Run each physical B70 independently with
one visible Level Zero device. One failed card stops the lane.

For every card, compare:

```text
A: incumbent moe_gather -> incumbent laguna_m8_scale_add
B: candidate laguna_m8_gather_finalize
```

against identical preallocated inputs. Require raw `uint16` and
`torch.equal` equality for:

- the final local BF16 result;
- a diagnostic candidate path exposing the same helper's routed-BF16 and
  scaled-BF16 boundaries, compared with the two literal incumbent
  intermediates;
- the unchanged fixed-rank four-input BF16 sum; and
- the next residual/norm component boundary.

The correctness corpus must include all finite BF16 values at the routed and
shared boundaries, signed zero, subnormals, infinities and NaNs classified
separately, FP32 zero/subnormal/near-one routing weights, exact midpoint cases,
all-local/all-remote/mixed routes, `-1` route entries, duplicate/permuted
entries, every one of ten slot positions, at least 256 changing random full
fixtures, candidate-repeat determinism, unchanged input hashes, and a complete
post-timing replay. Production integration must additionally prove the W2
kernel identity, arguments, 13-call test count, and 3,840 workgroups per
call/card are unchanged.

Time only the two-op control and one-op candidate. Exclude W2, fixture
construction, allocation, hashing, reset, reductions, synchronization inside
an arm, and CPU work. Reuse buffers and rotate a prebuilt changing fixture
outside timed arms:

- 20 untimed 47-layer cycles per arm;
- 31 A-B-B-A blocks;
- 64 complete 47-call cycles per timed arm; and
- one full exact replay after timing.

Every card must independently satisfy:

- candidate wins at least 28/31 paired blocks;
- paired median saving is at least `0.15 ms` per 47-layer cycle;
- control/candidate selected launches are exactly `94/47`;
- no compiler spills or profiler invalidity;
- GPU-memory/LSC read traffic does not rise by more than 2%;
- occupancy and XVE-active do not fall by more than 0.5 percentage point;
- XVE-stall does not rise by more than 0.5 percentage point; and
- all pre/post timing and downstream exactness gates pass.

No global average may rescue a failed card, pair family, exactness check, or
guardrail. A component or profiler-schema failure is terminal for this source
candidate; preserve it as a measured negative.

## Endpoint boundary

No endpoint is authorized here. A full four-card component pass authorizes
only construction and audit of a separate cold endpoint preregistration. That
future protocol must compare against the exact approved record stack with new
cold services, the fixed 13-prompt suite, canonical q=1 teacher, returned
token IDs, cache-zero proof, long-next and rollover checks, fresh private NVMe
roots, strict device idle, and a sequential early-stop A-B-B-A design.

This lane never authorizes a fifth rescue run, prompt reuse, prefix/history
cache, result selection, quality tolerance, parser repair after capture, or a
LocalMaxxing claim without a conservative matching-identity improvement.

## Explicit exclusions

Until separately authorized, do not:

- start a service or endpoint;
- load either model, generate a token, or send a prompt;
- use the external Corsair USB for live reads/writes;
- access the network, create a payload, or submit to LocalMaxxing;
- reboot, change drivers/runtimes, or perform recovery work;
- alter W1, W2, routing, projections, collectives, reductions, DFlash depth,
  graph behavior, packed weights, or model files; or
- rerun or reinterpret the closed shared gate/up counter campaign.
