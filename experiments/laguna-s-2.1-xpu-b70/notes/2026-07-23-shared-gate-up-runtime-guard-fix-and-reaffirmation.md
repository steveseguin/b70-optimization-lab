# Laguna shared gate+up runtime-guard fix and preregistration reaffirmation

Date registered: 2026-07-23 America/Toronto

Status: source correction committed and independently audited before any valid
Stage-0 XPU execution or authorization packet. The treatment, exactness
standard, thresholds, and staged stop rules remain unchanged.

## Why the sealed source identity changed

During pair-specific Stage-0 tool integration, a cross-file audit found that
the implementation at vLLM
`144f77608b6596677a9f6653b63b315e573b38b6` did not fully implement its
claimed runtime fail-closed behavior:

- changing raw `VLLM_XPU_EXACT_SPEC_ATTN` to `0` after construction caused
  `ColumnParallelLinear.forward` to bypass the batched-M1 helper and call the
  generic quant method;
- changing raw `VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM` to `0` or unsetting it
  made the inner request predicate false and silently restored incumbent BMM;
  and
- after `vllm.envs` caching, cached selector values could hide later raw
  record-stack drift.

The frozen launch environment never performs those mutations, so this finding
does not invalidate an existing model result. It does invalidate the stronger
pre-GEMM rejection claim required by this experiment. No Stage-0 packet
existed, and no authorized device work had started, so the source was fixed
rather than weakening the gate.

## Corrected source seal

The corrected source is:

```text
503f7784cf9d1704109b1e4650427fb4f417d604
xpu: fail closed on Laguna pair runtime drift
```

Its parent remains the original pair implementation
`144f77608b6596677a9f6653b63b315e573b38b6`. XPU kernels remain unchanged at
`c59aaadbbfd350c2b5f4ad663e247c2811ae3181`.

The incremental patch is:

```text
patches/vllm-xpu-laguna-shared-gate-up-m8-runtime-guard-20260723.patch
sha256 d38d9e9a5e0d759cc4c63312559bb9ecc50ce9d562089c329b41e95d8d09da18
```

The correction makes a still-bound verifier-M8 pair enter the guarded helper
when ordinary exact admission is disabled, makes bound-pair admission
independent of the mutable pair selector, and checks every frozen runtime
selector as a raw literal before either native MM. The ordinary exact target
path short-circuits before the rescue marker/scope checks. Genuine unmarked
M8, prefill, M1 through M7, dense, draft, routed, and shared-down paths remain
incumbent.

CPU-only validation, with device tests explicitly disabled, passed:

```text
168 passed, 3 skipped, 14 warnings
```

The three skipped tests are the explicitly opt-in XPU tests. Ruff and
`git diff --check` passed. Cached-environment tests froze the valid values,
then mutated each selector class and proved that neither generic apply nor
incumbent BMM was reached. Two independent read-only audits found no remaining
source blocker. No XPU tensor, model, generation, timing, counter, endpoint,
payload, network, or submission action occurred while making this correction.

## Reaffirmed frozen identity

- approved LocalMaxxing record:
  `cmrx6p5dv001bo4017hb7sixz`;
- conservative approved throughput:
  `33.89498511171744 tok/s`;
- vLLM implementation:
  `503f7784cf9d1704109b1e4650427fb4f417d604`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- target and draft root:
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

## Unchanged treatment

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
unchanged. Merged N512, logical B16, concatenation, packing, custom fusion,
reorder, overlap, and shared-down MM remain forbidden.

## Unchanged Stage-0 and component gates

A pair-specific fixture, runner, analyzer, tests, and shell orchestrator must
be committed and independently audited before an execution packet is created.
A later auth-only child commit must freeze their hashes, corrected source
identity, runtime, physical card 0, exact command, one local-NVMe root, and
every downstream action false.

The first valid screen still uses 128 deterministic changing epochs and
requires raw little-endian BF16 plus `torch.equal` equality for separate gate
and up BMM-vs-MM outputs, both candidate repeats, gate SiLU, the actual frozen
SiLU/multiply operation, incumbent shared down, shared+routed add, and fixed
rank-order reduction boundaries. Dispatch proof must show the actual
`LagunaMLP.forward` gate-then-up pair, exactly two native pair MMs, every
named incumbent path, and all bound-pair, selector, and record-stack rejection
classes stopping before a GEMM.

Only a valid Stage-0 pass may authorize construction of the four-card component
tools. The component gate remains 47 distinct layer inputs, 94 distinct
gate/up weights, four 47-slot output rings, 20 warm-up cycles per arm, 31
A-B-B-A blocks, 64 complete cycles and 6,016 projection calls per arm, and a
128 MiB eviction touch before each arm. Every physical card must win at least
28/31 blocks and save at least `0.20 ms` at the median complete 47-layer
gate+up cycle. No cross-card mean may rescue a failed card.

A component pass may authorize only construction and audit of a fresh
cold-counter campaign. No model generation, endpoint, payload, record claim,
or LocalMaxxing submission is authorized here. Submission remains permitted
only if the lower valid fresh candidate start beats
`33.89498511171744 tok/s` under matching identity and every target greedy token
array is bitwise identical.

## Authority chain

Preserve the original implementation and incident notes as historical facts.
For future execution, the authority chain is:

1. `2026-07-23-shared-gate-up-native-m8-mm-preregistration.md`;
2. `2026-07-23-shared-gate-up-implementation-and-pytest-incident.md`;
3. `2026-07-23-shared-gate-up-post-incident-reaffirmation.md`; and
4. this corrected-source reaffirmation.

This note supersedes only the future-execution source identity. It does not
reinterpret the quarantined XPU tests or lower any gate.
