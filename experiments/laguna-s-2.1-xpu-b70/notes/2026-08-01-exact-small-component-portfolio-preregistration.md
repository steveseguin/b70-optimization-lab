# Laguna exact small-component portfolio

Date: 2026-08-01 America/Toronto

Status: **component gate passed; vLLM integration and one non-scored smoke are
authorized.**

## Motivation

The protected BF16-KV record is `125.4619731637751 tok/s` conventionally.
Three independent treatments were rejected alone by conservative absolute
component floors, but each is raw-BF16 exact and removes distinct work:

| treatment | measured saving per 48-layer cycle |
| --- | ---: |
| M12 mapped gather/scale/add, 192x16 geometry | `0.249288 ms` |
| M12 grouped-GEMM K-loop barrier removal | `0.094176 ms` |
| exact INT4 scale-lane deduplication | `0.030000 ms` |
| optimistic isolated projection | **`0.373464 ms`** |

At the record's approximate `32.326922 ms` verifier cycle this is `1.1553%`,
projecting about `126.928 tok/s` at unchanged acceptance. The two grouped-GEMM
deltas are not assumed additive: they modify one kernel and can interact in
code generation or scheduling. Only direct both-on timing may contribute to
the gate. This cannot reach 130 alone, but it is large enough to test only as a
combined portfolio. The projection is not a measured endpoint result.

## Frozen composition

Create a fresh XPU-kernel worktree from protected commit
`99886d783372e621941228250091dc8ebdc1595d` and combine only:

1. mapped-tail commits `defec37d` plus `4174a07`;
2. no-K-loop-barrier commits `5d77d83` plus `9aa4754`;
3. scale-lane-dedup commit `1ed3b0b`.

The two grouped-GEMM treatments must compose in one separately named exact
M12 GRF128/transposed-scale kernel. Each selector remains literal, default
off, and fail-closed; enabling both must not silently select only one. The
mapped-tail op remains a separate `_moe_C` symbol and requires a new default-
off vLLM call-site selector. Selector off must preserve the protected path.

No arithmetic, BF16 rounding boundary, route order, DPAS order, output layout,
model/checkpoint value, KV precision, speculative width/depth, teacher,
sampling, cache policy, graph/scoring window, or benchmark metric may change.

## Gates

1. Inspect the combined source and final ISA. Require GRF128, two DPAS in the
   same order, no spill/scratch traffic, scale-lane-dedup's reduced scale load/
   synchronization structure, and omission of only the proven K-loop barrier
   instructions. The combined selector path must be reachable at real M12 W13
   and W2 shapes.
2. Build `_moe_C` and `libgrouped_gemm_xe_2.so` with oneAPI 2025.3. Record
   source commit, DSOs, hashes, ABI, wall time, peak RSS, and selector-off/on
   symbol evidence.
3. Reuse the existing changed-input corpora and compare same-DSO selector-off
   versus both-grouped-selectors-on, plus generic-tail versus fused-tail.
   Require raw-BF16 equality for all six W13/W2 cases and all six mapped-tail
   cases, input immutability, and no component regression greater than 1%.
4. Require at least `0.30 ms/cycle` under the direct joint formula
   `48 * ((tail_control-tail_fused) + (W13_control+W2_control-
   W13_both_on-W2_both_on))`. Do not sum the isolated grouped-GEMM deltas. A
   smaller result stops before vLLM/model integration.
5. A component pass authorizes a separately recorded vLLM integration, focused
   tests, and one non-scored TP4 2x400 exact/cache/topology smoke. Only a smoke
   pass authorizes a first-result cold 13-prompt endpoint leg.
6. Any model endpoint must keep target `146/145`, draft `14/13`, 13/13 teacher
   exactness, cache zero, one active generation, source/runtime identity, and
   strict teardown. The first valid result stands; no best-of-N selection.

No reboot, reset, FLR, driver reload, shared-memory cleanup, retry, or
privileged recovery is authorized.

## Component result

The frozen composition produced XPU-kernel source
`662b223d9fa8b3f3aa77e4df2409a78c3389470f`. The oneAPI 2025.3 grouped DSO
build completed in `17:57.61`, peaked at `107095588 KiB` RSS, used zero swaps,
and produced SHA-256
`5d2d29e63f40c62d31b61808d74a0ef7ba71f2c6a62754c3220ed4d0c8281d4b`.
The `_moe_C.abi3.so` build completed in `5:44.34`, peaked at `1265952 KiB`,
used zero swaps, and produced SHA-256
`51a1f2b02fc8a21e420edfff79c30ff0f2170d4bab0b6b1efb25d1f79b1f8a66`.
Its spill warnings were limited to the unchanged generic TopK-gating kernels;
the mapped-tail treatment emitted no spill warning.

The original minimal ISA probe had become stale when `SkipKLoopBarriers` was
inserted before `ScaleLaneDedup`: its old final Boolean selected barrier
removal rather than lane dedup. The probe was corrected before its output was
used. The corrected both-on GRF128 arm has 378 instructions versus 396 for the
transposed-scale control, retains two DPAS in order and 32 BF16 multiplies,
reduces the scale-address `shr` count from two to one, and omits the K-loop
barrier signal/wait pair. Zeinfo reports 128 GRFs and SIMD16 with no
scratch/private/spill allocation. The combined assembly SHA-256 is
`d75d9185c75d91ceb4d247f278067afd2d6f3a5a8248dc52d62ed0e0fb8dd540`.

One initial strict-idle wrapper call timed out while communicating with
`xpu-smi ps`; it is preserved as a failed preflight. A bounded read-only check
then returned normally, and exactly one fresh strict snapshot passed with only
the four self-observer rows. No candidate kernel had run before that pass. The
post-component strict snapshot also passed; no recovery action occurred.

The real W13/W2 same-DSO gate passed all six changed-input raw-BF16
comparisons. Direct both-on timing was:

| shape | control | both on | speedup |
| --- | ---: | ---: | ---: |
| W13 | `0.321015 ms` | `0.320476 ms` | `1.001684x` |
| W2 | `0.183516 ms` | `0.182993 ms` | `1.002855x` |

The mapped-tail gate passed all six raw-BF16 comparisons with immutable
inputs. Its third corpus contained 33 remote `-1` entries and 15 repeated
local entries. It measured `0.0145743 -> 0.0092144 ms`, or
`0.2572752 ms/cycle` over 48 layers.

Using only the preregistered direct formula, not the isolated projections:

```text
grouped both-on saving = 0.0509772 ms/cycle
mapped-tail saving     = 0.2572752 ms/cycle
joint saving           = 0.3082524 ms/cycle
threshold              = 0.3000000 ms/cycle
margin                 = 0.0082524 ms/cycle
```

The component gate therefore passes narrowly. This is authorization for a
separately recorded vLLM integration and one non-scored TP4 smoke only; it is
not an endpoint throughput claim.

Raw evidence:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/exact-small-portfolio-component-20260801T2228Z`.
Structured summary: `data/laguna-exact-small-portfolio-component-20260801.json`.

## Integration checkpoint

The candidate-only integration is committed as vLLM
`0c9dea8cfefdcf4b293cddc9a4f47d56a11ecf4b` and XPU kernels
`46a6393fc188c11661ddab9cf1320d2f3de45087`. The promoted checkpoint uses
`CompressedTensorsWNA16MarlinMoEMethod`; the integration therefore enters
through that method rather than an unreachable AutoGPTQ-only adapter. Shared
expert output is consumed exactly once and passed synchronously through a
separately named method chain to the existing mapped-gather site. The fused
result bypasses the replaced late scale/add, while the final EP4 fixed-rank
all-reduce remains unchanged.

Six kernel/source contract tests and three focused vLLM tests pass. The latter
cover M12-selector dependency, one-time shared-output consumption, and the
actual compressed-tensors XPU adapter. The candidate runtime lock is
`data/laguna-exact-small-portfolio-runtime-lock-20260801.json` with SHA-256
`e0697c3ce6c3b76821f3f2144c746a5e47596d9c110d4035b1967872218feddd`.
This is still an integration checkpoint, not endpoint evidence; the
preregistered non-scored TP4 smoke remains the next gate.
