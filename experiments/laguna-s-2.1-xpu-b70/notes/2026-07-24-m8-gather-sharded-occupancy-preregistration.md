# Laguna exact M=8 standalone gather sharded-occupancy preregistration

Date registered: 2026-07-24 America/Toronto

Status at registration: treatment, fixed geometry, and gates frozen before
source implementation, native build, XPU import or allocation, model load,
endpoint generation, network access, payload creation, or submission.

## Question

Can the standalone fixed-order Laguna M=8 `MoeGather` be accelerated by
supplying more independent workgroups while preserving its literal arithmetic
and every surrounding operation?

The incumbent BF16 specialization covers hidden size 3,072 with one
256-work-item group per token and eight BF16 elements per work-item:

```text
stride = 256 * 8 = 2048 columns
groups = 8 tokens * 1 = 8
subgroups = 8 groups * 8 SIMD32 subgroups = 64
loop_count = ceil(3072 / 2048) = 2
```

Its second loop pass uses only the first 128 work-items. The candidate divides
each token's hidden dimension into six independent 512-column shards:

```text
tokens = 8
shards_per_token = 6
work_items_per_shard = 64
elements_per_work_item = 8
columns_per_shard = 64 * 8 = 512
hidden_size = 6 * 512 = 3072
groups = 8 * 6 = 48
subgroups = 48 groups * 2 SIMD32 subgroups = 96
loop_count = 1
```

For each output scalar, both implementations must execute the same ordered
operation:

```text
accum_fp32 = 0.0f
for slot in 0..9:
    accum_fp32 += float(route_bf16[token * 10 + slot, hidden]) \
                  * weight_fp32[token, slot]
output_bf16[token, hidden] = BF16(accum_fp32)
```

There is no cross-thread reduction. Each output scalar remains owned by one
work-item, the slot order remains 0 through 9, and the only output conversion
remains the final FP32-to-BF16 store.

The default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=1
```

## Material distinction from the terminal gather-finalize lane

The 2026-07-24 gather-finalize candidate is terminal and unmeasured after its
one authorized Phase-A coordinator failed before native import. It must not be
rerun, repacketed, rescued, or interpreted.

This new treatment is not that fusion:

- it starts from the approved record source identities, before the
  gather-finalize implementation;
- it changes only the standalone gather workgroup enumeration;
- it retains the ordinary separate `laguna_m8_scale_add` launch;
- it does not read shared-expert output;
- it does not calculate routed scaling or shared addition;
- it does not remove a launch; and
- it does not use the terminal candidate binary, symbol, packet, fixture, or
  result root.

The structural comparison is exactly 47 control gather launches versus 47
candidate gather launches per 47-layer target cycle. Any claim of a 94-to-47
launch reduction belongs only to the closed gather-finalize design and is
forbidden here.

## Historical novelty

A full Laguna note/data/patch and Git-history audit found no prior standalone
M=8 gather split-token, hidden-shard, or workgroup-retile measurement. The
route-interleave and W1-N128 experiments explicitly kept
`MoeGather<BF16,10,8>` byte-identical. The terminal gather-finalize design also
froze the incumbent gather geometry rather than sharding it.

No Laguna two-, three-, four-, six-, or other hidden-shard gather geometry has
been measured. This lane is therefore materially new.

## Frozen source identity

Implementation must use clean worktrees rooted directly at the approved record:

- vLLM:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- model:
  Poolside Laguna S 2.1 INT4 target plus the quantization-matched Laguna
  S 2.1 DFlash INT4 draft on internal NVMe; and
- current approved LocalMaxxing record:
  `cmrx6p5dv001bo4017hb7sixz` at
  `33.89498511171744 tok/s`.

The active model root is
`/mnt/fast-ai/llm-models/laguna-s-2.1`. Active build caches, temporary files,
logs, fixtures, and result roots must be on internal NVMe/ext4. The external
Corsair drive is backup-only and must not be mounted or used by this lane.

## Frozen native treatment

Add a separate Laguna-only native gather symbol beside the unchanged generic
`MoeGather`. Its compile-time invariants are:

```text
kNumTokens == 8
kTopK == 10
kHiddenSize == 3072
kShardsPerToken == 6
kGroupWorkItems == 64
kElementsPerItem == 8
kSubgroupSize == 32
kShardWidth == 512
6 * 64 * 8 == 3072
64 % 32 == 0
48 workgroups per launch
96 SIMD32 subgroups per launch
```

The candidate computes:

```text
token = group_id / 6
shard = group_id % 6
hidden_base = shard * 512 + local_id * 8
```

It then copies the incumbent literal slot-0-through-9 FP32 accumulation and
BF16 store. It may not add local memory, barriers, atomics, subgroup
broadcasts, vector-width changes, route compaction, weight folding, fused
scale/add, shared-output access, or another arithmetic transformation.
The control and candidate must use the same compiler, flags, floating-point
contraction policy, and source-language multiply/add expression. Fast-math,
`ffp-contract`, explicit-FMA, or other floating-point flag changes are
forbidden. Static device-IR inspection must show the same multiply/add
instruction family and ordered ten-slot dependency chain in both kernels;
raw device equality remains the final authority.

The exact record path always uses the canonical contiguous route map
`arange(80).view(8,10)` and zero-filled W2 rows for remote routes. The
candidate accepts no route-map tensor and resolves only
`token * 10 + slot`. This avoids a host-unverifiable device-map contract and
is identical to the record path. Candidate dispatch must be reached only from
the existing branch that internally constructs and owns that canonical map;
tests and static proof must bind the omitted map to that provenance. An
external or noncanonical map may not reach the candidate. Noncanonical calls
retain the generic gather.

The generic `MoeGather`, W1, SiLU, W2, route interleave, shared-expert path,
`laguna_m8_scale_add`, fixed-rank reduction, attention, DFlash, and sampler
source must remain byte-identical to the record base outside the narrow
candidate dispatch. The terminal gather-finalize source must not be copied
into the new worktree.

## Fail-closed dispatch contract

The selector may dispatch only for:

- Intel XPU eager execution, with graph, AOT, and compilation disabled;
- the Poolside Laguna target verifier, never the DFlash draft;
- exactly M=8, hidden size 3,072, top-k 10, 256 global experts, 64 local
  experts, TP4/EP4/DP1/PP1, and one active generation;
- contiguous BF16 route input `[80,3072]` and output `[8,3072]`;
- contiguous FP32 top-k weights `[8,10]`;
- canonical route-row ownership `token * 10 + slot`;
- exact batched MoE, fused-W1/route-parallel-W2, route interleave, W1 N64,
  shared elementwise, Q/K RMSNorm plus RoPE, and fixed-rank reduction;
- the approved DFlash depth 7 policy; and
- every rejected or unrelated Laguna experiment explicitly off, including
  remote-zero, full fused transaction, BF16 router/top-k, native shared
  gate/up/down, auxiliary stream, deterministic graph, BF16 attention MM,
  W1 N128, and gather-finalize.

M=1, verifier tails M=2 through M=7, prefill, draft, non-Laguna models,
noncanonical route maps, other dtypes or shapes, LoRA, graph paths, and
unrelated calls retain the literal incumbent path. If the selector is enabled
and a candidate-shaped target call violates any predicate, construction or
dispatch must raise before a native primitive. Silent fallback is forbidden
for a candidate-shaped call.

The native binding must additionally require one XPU device, exact dtype,
shape, contiguity, 16-byte alignment, and output/input non-overlap before
launch.

## Stage 0: authorized work

This registration authorizes:

1. creation of clean, separate worktrees from the record commits;
2. the minimal default-off native specialization and Python dispatch;
3. CPU-only guard, schema, host-oracle, and anti-corruption tests;
4. a native build whose output is not imported before its later packet;
5. static and binary inspection; and
6. independent read-only audits.

Before any XPU action, require:

- Python AST/compile, Ruff, C++ formatting, whitespace, and clean-tree checks;
- CPU tests for every matching predicate and one-field corruption;
- static proof that generic gather and all surrounding kernels are unchanged;
- a host oracle encoding ten ordered FP32 multiply/add expression steps and
  the final BF16 cast, plus device-IR proof that the candidate preserves the
  incumbent contraction policy;
- a sealed candidate binary hash and exact source commits;
- at least two independent read-only audits with all blockers corrected; and
- explicit opt-in guards preventing CPU test commands from importing Torch
  XPU or executing a device primitive.

An accidental native import, XPU tensor allocation, or primitive before the
later authorization invalidates Stage 0 evidence.

## Operational preflight rule

The previous lane failed because a frozen mock-only idle parser did not match
the installed `xpu-smi ps -j` schema. This lane must validate operational
plumbing before committing its candidate campaign packet.

A separate read-only operational preflight may enumerate devices and invoke
`xpu-smi ps -j`, but it must not import the candidate/native module, import
Torch XPU, allocate a device tensor, execute a primitive, or observe candidate
performance. Its idle checker must retain the spawned `xpu-smi` child PID,
accept only rows bound to that exact PID and executable, and reject every
other device process. It must accept both a genuinely empty process list and
the installed schema's self-observer rows. Executable comparison must
normalize the reported path with the resolved launched executable and also
validate the exact retained child PID; a basename-only match is insufficient.
The parser must first pass against a retained sanitized capture containing the
installed top-level field names and self-row field/value semantics.

Operational-preflight bugs may be corrected and the read-only preflight
repeated because no treatment or performance result exists at that stage.
Every failure and correction must be recorded. Once the component packet is
committed, candidate execution receives no such repair or retry allowance.

## Frozen component gate

Only separately tracked Phase-A and Phase-B packets committed together after
Stage 0 and the operational preflight, but before any candidate execution, may
authorize one bounded two-phase component program. Phase A is exactly one
four-card exactness/timing campaign. Only if Phase A passes may its already
committed conditional Phase-B packet authorize exactly one four-card mandatory
counter campaign. Both use the same source commits, native-library hashes,
fixture manifest, physical-card order, one-visible-device mapping, arm
treatments, and logical 47-call cycle. There are at most these two
candidate-bearing campaigns; neither phase may be repeated, replaced, or
selected among. Cards run sequentially and any card failure stops the lane.

For every card compare:

```text
A: unchanged generic MoeGather<BF16,10,8> with canonical arange(80) map
B: dedicated Laguna M8 six-shard gather
```

Both arms use identical preallocated inputs. Raw BF16 bits are the primary
correctness predicate. Require exact equality for:

- gather output;
- candidate repeat output;
- the unchanged subsequent `laguna_m8_scale_add` output;
- the unchanged fixed-rank four-input BF16 sum;
- a following residual/norm replay;
- input hashes before and after execution; and
- same-fixture output digests across all four cards.

The changing corpus must cover:

- all 65,536 BF16 input bit patterns across deterministic route tensors;
- signed zero, subnormals, normals, infinities, and NaNs;
- FP32 zero, signed zero, subnormal, near-one, large, infinity, and NaN
  weights;
- all-local, all-remote-zero, and mixed zero-filled route-row patterns;
- each of the ten slot positions independently active;
- cancellation and BF16 midpoint cases;
- at least 256 deterministic changing full-shape epochs before timing;
- repeated candidate determinism; and
- at least 32 changing full-shape epochs after timing.

Before Phase A, a canonical coverage manifest must enumerate every fixture,
class, slot probe, route-zero pattern, and expected hash. Its independently
recomputed coverage must prove all 65,536 BF16 bit patterns, every registered
FP32 edge class, all ten slots, and all registered remote/local patterns are
present. The packet binds the manifest and fixture hashes; prose claims are
not evidence.

NaN-containing cases still require identical raw BF16 bits and identical
classification; `torch.equal` is not a valid NaN predicate.

Time only the gather calls. Exclude fixture creation, allocation, hashing,
buffer reset, scale/add, reduction, synchronization inside an arm, and CPU
work. Use:

- 20 untimed 47-call cycles per arm;
- 31 A-B-B-A timing blocks;
- 64 complete 47-call cycles per timed arm; and
- changing prebuilt fixture rotation outside timed arms.

Every physical card must independently pass:

- all exactness, repeat, immutability, post-timing, and downstream gates;
- candidate wins at least 28 of 31 paired blocks;
- paired median saving of at least `0.08 ms` per 47-layer cycle;
- exactly 47 selected gather launches in both control and candidate cycles;
- control geometry of 8 workgroups/64 subgroups per launch;
- candidate geometry of 48 workgroups/96 subgroups per launch;
- no compiler spill or profiler invalidity;
- no more than 2% increase in GPU-memory or LSC bytes;
- no more than 0.5 percentage-point decline in XVE active or thread
  occupancy; and
- no more than 0.5 percentage-point increase in XVE stall.

No global mean can rescue a failed card or predicate. Timing and mandatory
counters use separate immutable packets so profiler instrumentation cannot
contaminate timing. A timing pass is only
`component_timing_pass_pending_mandatory_counters`; it does not authorize an
endpoint. The counter packet must bind byte-for-byte to the Phase-A
control/candidate binaries, source commits, fixture and coverage hashes, arm
order, logical 47-call cycle, and card mapping. Its own profiler-specific
warmup and repetition counts must be committed before Phase A and may not be
changed afterward. It may not add unregistered candidate work, select
fixtures, or substitute a rebuilt binary after observing Phase A. Both packets
must pass for this component to enter the exact-win bank.

## Promotion boundary

This registration authorizes no model load, endpoint, prompt, generation,
payload, or LocalMaxxing submission.

A four-card component pass banks only the conservative per-card minimum
saving. Because the entire retained gather scope is only `0.441856 ms` per
47-layer cycle and service variance is larger than a small isolated gain, the
component does not receive a standalone endpoint. It may enter a future,
separately preregistered portfolio only when compatible non-overlapping exact
component savings reach at least `0.30 ms` per target cycle on every card.

Any future endpoint must start new cold services, use each fixed prompt once,
prove `cached_tokens=0`, match the canonical q=1 teacher bitwise, pass
long-next and rollover gates, retain one active TP4/EP4 generation, and use
private internal-NVMe roots. Only the conservative lower candidate result may
be submitted, and only if it beats the matching approved record.

## Explicit exclusions

Until separately authorized, do not:

- start a Laguna endpoint or load either model;
- generate a token or send a prompt;
- mount or use the external Corsair drive;
- access the network, create a payload, or submit to LocalMaxxing;
- reboot, change drivers/runtimes, or perform recovery work;
- tune or sweep shard count, workgroup size, vector width, or thresholds after
  seeing a candidate result;
- fuse gather with scale/add or revive the terminal gather-finalize path; or
- alter model files, W1, W2, routing, attention, collectives, reductions,
  DFlash policy, or the approved record source.
