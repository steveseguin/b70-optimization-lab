# Laguna M12 packed N-major grouped-MoE scheduler screen

Date: 2026-08-01 America/Toronto

Status: **preregistered before source implementation or device execution. No
endpoint score is authorized.**

## Evidence and hypothesis

The protected exact BF16-KV record is `125.4619731637751 tok/s`. At unchanged
acceptance, 130 requires about `1.128 ms` from the roughly `32.327 ms` verifier
cycle. The exact M12 target executes one grouped W13 and one grouped W2 per
layer; their stable summed component is about `0.504 ms/layer`, or roughly
`24.2 ms` across 48 layers.

The protected persistent scheduler numbers tasks M-tile-major. With the
observed 51--57 active local experts and one M8 tile for nearly every active
expert, it exhausts all 32 W13 or 48 W2 N tiles for one expert before exposing
the next experts. Laguna's earlier exact M8 routed interleave changed only task
enumeration to N-major and improved its routed component by `4.237%` (W1
`3.669%`, W2 `2.934%`) while preserving raw outputs; its endpoint effect was
positive. Applying that ordering to the dominant expert-grouped M12 GEMMs is
the strongest remaining evidence-backed scheduling candidate.

A prior M12 persistent worklist (`efe33d2d3`) is not this treatment. It kept
M-major order and loaded four int32 metadata fields per task; it regressed the
summed component by `1.232%`. Fixed grids and atomic chunking were also
measured losses. This screen must therefore combine the ordering change with a
single packed descriptor, while preserving the incumbent one-task atomic
acquisition and cross-row weight reuse.

## Frozen treatment

Start from protected XPU-kernel commit
`99886d783372e621941228250091dc8ebdc1595d` in a fresh worktree.

1. Add one compile-time/default-off persistent-scheduler specialization named
   by literal selector
   `VLLM_XPU_LAGUNA_DECODE_NMAJOR_PACKED_WORKLIST`.
2. Retain the exact expert-grouped `w4a16_policy_m_8` arithmetic, K32 order,
   FP32 accumulator, BF16 store, 256-workgroup persistent pool, and one-task
   atomic acquisition. Change only logical task mapping from M-major to:
   `m_tile_slot = task % tile_count`, `n_tile = task / tile_count`.
3. Supply `tile_count` and one uint32 descriptor per logical M tile after the
   64 count entries. Pack expert id, packed-row start, expert row count, and
   expert-local M8 tile id into one load. Validate every field and descriptor
   count before launch; do not reuse the four-int worklist.
4. For the initial component screen, construct the descriptor tail in the
   existing Python gate. This adds no model launch and isolates scheduler
   value. Only after a component pass may the production remap path be changed
   so its existing kernel emits the same tail; no extra device launch is
   permitted.
5. Fail closed unless the full protected route matches: BF16 A/S/D, packed
   INT4 B with C layout, non-tile-major, group 32, total M 120, 64 local
   experts, physical transposed scales, scale-vector on, dequant-MAD and scale
   fold off, GRF128, and exactly W13 `(N=2048,K=3072)` or W2
   `(N=3072,K=1024)`.

Selector off, prefill, draft, M8-only fused experts, other widths, shapes,
dtypes, layouts, group sizes, policies, and the protected record trees remain
unchanged.

## Gates and stop rules

1. **Source/static gate.** Require one owner for every
   `(expert,M8 tile,N tile)`, descriptor coverage with no omissions or
   duplicates, the same call into `xe_gemm_4bits`, the same K32/DPAS/load/store
   body and GRF128 mode, and no new scratch/spill. Stop on layout ambiguity or
   arithmetic change.
2. **Synthetic descriptor gate.** On one idle B70, compare selector off/on
   from the same ABI-8 DSO using identical changed-input W13/W2 corpora,
   physical transposed scales, descriptor coverage checks, sentinel-filled
   outputs, and `6/6` raw-BF16 equality. Use 200 warmups and 15 samples of 40
   launches. No shape may regress more than 1%; require at least `3%` summed
   improvement to justify production metadata integration. Approximately
   `4.7%` is required to cover the full current 130-tok/s gap by itself.
3. **No-launch integration gate.** If and only if the synthetic gate passes,
   extend the existing remap workspace and existing remap kernel to emit the
   descriptor tail. Prove tail coverage and raw equality independently. An
   extra kernel launch, CPU readback, graph-address instability, or change to
   W1/W2 descriptor identity stops integration.
4. **Four-rank non-scored smoke.** Require selector evidence on all ranks,
   target topology `146/145`, draft topology `14/13`, cached tokens zero,
   unchanged acceptance bookkeeping, exact canonical response, and clean
   teardown. A score-bearing endpoint run requires a separate cold,
   first-result crossover preregistration.

The protected record already includes both exact M12 router flags and the
persistent DFlash context-KV workspace; those gains may not be added again.
No target/draft/KV precision change, teacher change, prompt change, retry,
warmup generation, metric substitution, reset, reboot, driver operation, or
privileged recovery is authorized by this screen. Preserve every source,
binary, log, and result whether positive or negative.
