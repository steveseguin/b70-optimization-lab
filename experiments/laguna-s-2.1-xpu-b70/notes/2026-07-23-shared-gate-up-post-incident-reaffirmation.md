# Laguna shared gate+up post-incident preregistration reaffirmation

Date registered: 2026-07-23 America/Toronto

Status: unchanged treatment, exactness requirements, thresholds, and staged
stop rules reaffirmed after the unpacketized pytest incident and before
Stage-0 tool construction, a valid Stage-0 run, component timing, counters,
model generation, endpoint work, payload creation, or submission.

## Why this reaffirmation exists

The original preregistration at
`2026-07-23-shared-gate-up-native-m8-mm-preregistration.md` froze the lane
before implementation. During CPU-test construction, three XPU primitive
tests accidentally ran because their `skipif` conditions did not require an
explicit device authorization. They produced no admissible arithmetic or
performance evidence and are quarantined in
`2026-07-23-shared-gate-up-implementation-and-pytest-incident.md`.

This note does not rescue, reinterpret, or lower any gate. It restates the
original treatment and numbers without change so that all future execution
has a clean, incident-aware authority chain.

## Frozen identity

- approved LocalMaxxing record:
  `cmrx6p5dv001bo4017hb7sixz`;
- conservative approved throughput:
  `33.89498511171744 tok/s`;
- vLLM implementation:
  `144f77608b6596677a9f6653b63b315e573b38b6`;
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
- exact eager target, DFlash depth 7, BF16 KV, TP4/EP4/DP1/PP1,
  one active request, and literal routed-W1 N64.

All active model, fixture, cache, temporary, log, run, and evidence paths use
local NVMe/ext4 under `/mnt/fast-ai`. The external Corsair USB remains
backup-only.

## Unchanged single treatment

Enable only:

```text
VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=1
VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0
VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0
```

Control remains two separate stride-zero B=8/M=1 BF16 BMMs. Candidate remains
two separate native M=8 BF16 MMs in gate-then-up order. Separate modules,
weights, outputs, BF16 boundaries, SiLU/multiply, shared down, routed work,
fixed reduction, attention, KV, collectives, DFlash, and sampling remain
unchanged.

Merged N512, logical B16, concatenated inputs or weights, packing, custom
fusion, reorder, overlap, and shared-down MM remain forbidden.

## Unchanged Stage-0 kill screen

A new pair-specific fixture, runner, analyzer, tests, and shell orchestrator
must be committed and independently audited before an execution packet is
created. A later auth-only commit must freeze their hashes, source/runtime
identity, physical card 0, exact command, one local-NVMe root, and every
downstream action false. Merely having this note does not authorize an XPU
command.

The first valid screen uses 128 deterministic changing epochs with one
`[8,3072]` BF16 input and independent `[256,3072]` BF16 gate/up weights per
epoch. It must require raw little-endian BF16 equality and `torch.equal`
between literal BMM and native MM for gate and up, repeat determinism, then
gate/up-dependent SiLU, multiply, incumbent shared down, shared+routed add,
and simulated fixed-rank reduction boundaries.

Dispatch proof must show exactly two native MMs in gate-then-up order for the
marked M8 pair and incumbent BMM for M1 through M7, prefill, draft, dense,
routed, shared down, and genuinely unmarked M8. A previously bound projection
with a missing marker, a mismatched role/scope, either bad layout, pair
corruption, record-stack drift, or selector ambiguity must raise before a
native MM. Mutation, replayed fixtures, missing hashes, nondeterminism, or one
raw mismatch classifies `stage0_exactness_failed_stop`.

A tooling-only failure may use a new root after preserving evidence and
changing only the diagnosed tooling defect. A valid Stage-0 run is terminal
for that packet and authorizes only component-tool construction.

## Unchanged four-card component gate

Only a valid Stage-0 pass may authorize a later four-card component packet.
Each card independently repeats 128 pre-timing and 32 post-timing exactness
epochs. Timing retains:

- 47 distinct layer inputs, shared only by that layer's gate/up pair;
- 47 distinct gate plus 47 distinct up raw-BF16 weights, all 94 pairwise
  nonaliasing;
- four independent 47-slot output rings, all 188 outputs pairwise
  nonaliasing;
- 20 untimed cycles per arm;
- 31 A-B-B-A blocks;
- 64 complete cycles and exactly `64 * 47 * 2 = 6,016` gate-then-up
  projection calls per arm;
- one 128 MiB eviction touch before every arm; and
- raw nanosecond arm timings with only arm-boundary synchronization.

Every physical card must win at least 28 of 31 blocks and save at least
`0.20 ms` at the median complete 47-layer gate+up cycle. The threshold is
unchanged. No cross-card mean may rescue one failed card. The first valid
four-card component campaign is terminal.

## Unchanged downstream boundary

A component pass may authorize only construction and independent audit of a
fresh cold-counter campaign. It does not authorize counter execution. Only a
later passing counter packet may authorize construction of a cold endpoint
campaign.

No model generation, endpoint, payload, record claim, or LocalMaxxing
submission is authorized by this note. A result may be submitted only if its
lower valid fresh candidate start beats `33.89498511171744 tok/s` under the
matching identity and every target greedy token array remains bitwise
identical.
