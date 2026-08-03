# Laguna wide-prefill occupancy variant and worker-proof pin repair

Date: 2026-08-03 America/Toronto

Status: **offline only; a measurement-only 4-head long-row companion is added to
the component matrix and a two-commit-stale integrity pin is repaired. No XPU,
model, endpoint, or benchmark work was performed.**

## Why

A review of the incumbent wide-prefill successor (vLLM `505b59cb9`, XPU kernels
`13cd7e0`) confirmed its central premise but found three defects. The scheduler
contract itself is sound: `max_num_scheduled_tokens` is derived, not set, as
`max_num_batched_tokens - (num_speculative_tokens - 1) * max_num_seqs`
= `8192 - 10 = 8182`, and `token_budget` clamping in
`vllm/v1/core/sched/scheduler.py` produces exactly
`8182 + 8182 + 8182 + 8094 = 32640`. That is unchanged by this work.

## 1. Stale worker-proof integrity pin

`tools/test_laguna_worker_proof_measurement_leg.py` pinned
`validate_laguna_worker_selector_evidence.py` at
`b7bb4e5ee439262b2db0e01a26ae7da29f71fb011320a2907f154d534457b500`, its content
at `453c8d13d`. Commit `f79ea0943` changed that file and `ec54c38c9` changed it
again, neither re-pinning, so the pin had been broken across two commits.

This mattered more than an ordinary red test. The pin is not only a test
constant: `run_laguna_worker_proof_measurement_leg.sh` carries the same value in
`readonly expected_worker_selector_validator=` and `check_hash`es the validator
at runtime, before the A/B. A silently rotted pin is a fail-closed guarantee
that is not actually closed.

Both validator changes were legitimate and purely additive — the v1 constants
including `SELECTOR_CONTRACT_SHA256` are untouched, which is why the separate
contract-hash test kept passing — so the repair is to re-pin, not to revert. The
pin now reads `744554c9599091966b8cba0af1ae744d816b5ba599689dbb2c80c3ff6563210f`
in the shell leg, the test, and this lane's component-hash record. The leg and
test hashes recorded in
`2026-08-02-exact-small-worker-proof-successor-preregistration.md` were
recomputed to close the self-referential chain.

## 2. Stale upstream identities in RESUME.md

`RESUME.md` still recorded upstream `68ca6fd02` and packer branch `3ab3e1927`.
Commit `b8a2b258a` refreshed `CURRENT.md` and three notes but missed the lane
resume document, which is the first file a resuming agent reads. Corrected to
upstream `5df9999fc`, fast-forwarded from `68ca6fd02`, packer branch
`b23676262`, matching `2026-08-03-e2e-latency-upstream-sync.md` and the actual
community worktrees.

## 3. A 4-head long-row geometry was excluded by an arbitrary whitelist

The 8,094/8,182 rows cannot reuse the short-row 8-head work-group geometry
because `8182 x 14` and `8094 x 14` are both `4 (mod 8)`. The successor
therefore dropped to two heads per work-group, and the geometry `static_assert`
admitted only `{2, 8, 16}`.

Four also divides every registered row/head product:

```text
8094 x 14 = 113316    8094 x 20 = 161880
8182 x 14 = 114548    8182 x 20 = 163640      all divisible by 4
```

TP4 per-rank physical Q+K head counts are 12+2 = 14 for the 12 full-attention
layers and 18+2 = 20 for the 36 sliding layers, confirmed against the checkpoint
config and against the kernel's own paired width gate (`q.size(1)` 1536/2304).

Four heads per work-group halves the dispatch: 8,182 x 14 heads is 57,274
work-groups of 32 lanes at two heads per group, and 28,637 of 64 lanes at four.
Because the component gate requires at least 25 ms projected saving per rank and
the candidate's entire value rests on clearing that bar, leaving a 2x occupancy
option unmeasured was a live risk to the gate.

The geometry choice only repacks heads into work-groups. Each head keeps its own
independent 16-lane reduction, both BF16 rounding boundaries, and disjoint
global writes, so the two variants must agree bit-for-bit and differ only in
occupancy.

### Source shape

XPU kernels now expose a measurement-only companion
`laguna_incumbent_wide_prefill_qk_norm_rope_wg4_out`. Both entry points run one
shared `laguna_incumbent_wide_prefill_qk_norm_rope_check`, so neither symbol can
relax a contract the other enforces, and they differ only in the
`LONG_HEADS_PER_WG` template argument of the shared launcher. The short rows
retain eight heads per work-group in both variants; measuring them twice would
compare a shape against itself.

Nothing in the model path reaches the companion. vLLM is unchanged: it still
calls `..._out` only, the startup probe still tests for `..._out`, and the sealed
q12 startup contract is untouched.

### Matrix shape

The component matrix grows from 16 runs to 24: four ranks x four rows, plus the
two long rows again at `wg4`. `gate_laguna_qknorm_rope.py` takes `--geometry`
and records it. The aggregator keys runs by rank/rows/geometry, requires all 24,
scores each geometry over a full row set, and promotes whichever projects the
larger saving — but only after requiring that the two geometries produced
identical output hashes for every rank, row, and layer case. A bitwise
disagreement means the reduction is not head-independent and neither variant is
promotable.

## Validation

Host and static only:

- lab component contract and aggregator: 11 tests, up from 5, covering the
  24-run matrix, cross-geometry bit equality, an out-of-matrix geometry, and
  contract drift now parameterized over both geometries;
- worker-proof measurement leg: 10 tests and 57 subtests pass, previously 1
  failing;
- XPU kernel static source contract: 6 tests, up from 5;
- brace/paren balance and single-definition checks on the restructured kernel
  translation unit;
- Ruff clean on every changed lab file; the kernel test file loses one
  pre-existing long-line error and adds none.

No SYCL toolchain is present in this environment, so the kernel translation unit
is **not compile-verified**. It must be built before any device use.

## Boundaries and required next steps

The NVMe/device quarantine remains controlling. Nothing here authorizes a model
load, endpoint, XPU probe, component run, benchmark, reset, or recovery. The
candidate remains default-off and unmeasured, and no performance number is
claimed.

Two preconditions for a valid measurement are **not** enforced by the sealed q12
startup contract and were deliberately left alone because changing that contract
requires its own preregistration:

1. `enable_prefix_caching` — the long-context launcher passes
   `--no-enable-prefix-caching`, but the contract does not require it. With
   prefix caching on, a repeated 32,640-token prompt reuses all but the last
   token, so the first chunk stops being a registered row and the fused path
   silently disables from the second iteration onward. A looped benchmark would
   measure a null result and blame the kernel.
2. `max_num_partial_prefills` — if it ever exceeds one,
   `long_prefill_token_threshold` becomes `int(max_model_len * 0.04)` and
   shreds the four-chunk partition entirely.

Both should be added to the startup contract under a fresh preregistration
before the component window, and the DSO must be rebuilt from this tree because
the committed `13cd7e0` binary does not export the companion symbol.
