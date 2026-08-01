# Laguna exact small-component portfolio

Date: 2026-08-01 America/Toronto

Status: **preregistered before composition, build, or device execution.**

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
