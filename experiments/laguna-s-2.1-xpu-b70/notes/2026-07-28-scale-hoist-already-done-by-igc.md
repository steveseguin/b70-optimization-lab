# Scale-reload hoist: IGC already did it. Dead at stage 0/1

Date: 2026-07-28 America/Toronto

Status: **closed at stage 0/1.** No code written, no build, no GPU. The repo
never left `46a88e09` and `libgrouped_gemm_xe_2.so` is still
`53f3d2941ce322bcdff1b0463ec6fe72387036ea54d3f602a08d690744b3459f`.

## The proposal

Ranked target #1: the "53 non-arithmetic instructions in the k-loop body". The
scale-reload branch and its prefetch-address recomputation were said to run on
every k-tile although the scale changes only on group boundaries, with
`group_size % tile_k == 0` already asserted. Estimated ~10 instructions per
k-tile, and bitwise-neutral by construction.

## All three factual claims are false on the decode path

`k_tile * tile_k % group_size == 0` at `gemm_xe2.hpp:908` is **not**
if-converted. IGC emits a real uniform branch and strength-reduces the whole
predicate — a `*32` and a `%128` — into a single `and`:

```text
(W) and  (1|M0)          r4.10<1>:d  r3.15<0;1,0>:d  3:w   // int; $260
(W) cmp  (16|M0) (eq)f1.0 null<1>:d  r4.10<0;1,0>:d  0:w   // int; $261
(W&~f1.0) jmpi           _0_064                            // int; $262
```

Per-basic-block at `G=128, SCALE_VEC=1`, the measurement baseline:

| block | role | n | float | int | other |
| --- | --- | ---: | ---: | ---: | ---: |
| B023 | header: barrier, A/B copy, reload guard (3) | 14 | 1 | 9 | 4 |
| **B024** | **scale reload — GUARDED, 1 k-tile in 4** | 13 | 0 | 11 | 2 |
| **B025** | **scale prefetch-address recompute — GUARDED** | 8 | 0 | 7 | 1 |
| B026 | A/B prefetch guard | 2 | 0 | 2 | 0 |
| B027 | A/B prefetch | 8 | 0 | 4 | 4 |
| B028 | dequant + scale + 2x dpas | 106 | 64 | 36 | 6 |
| B029 | back-edge | 2 | 0 | 1 | 1 |

- "Executes on EVERY k-tile" — **false.** B024+B025, 21 instructions, sit
  behind `(W&~f1.0) jmpi` and run once per group.
- "Prefetch-address recomputation is on the fast path" — **false.** All 8 of
  those instructions are inside the guarded B025. The one shared value,
  `shl r4.9 = k_tile << 5`, is needed unconditionally by the A-copy descriptor
  anyway, and B024 already reuses it through `add r4.12, r4.9, 768`. IGC had
  already CSE'd `(group_idx+6)*group_size` against it.
- "IGC may not have hoisted this" — **it has**, and more aggressively than the
  proposal. At `group_size == tile_k` (G=32) it deletes the predicate outright:
  no `and`, no guard `cmp`, no guard `jmpi` anywhere, with the reload folded
  into the loop header.

The "53 non-arithmetic" figure was a **static listing** count: 153 total minus
98 arithmetic = 55. Dynamically it is 39.25, because 21 of those 55 are
guarded. Counting a listing is not counting an execution.

## What was actually available, measured against a floor

Dynamic per k-tile at G=128, VEC=1, MAD=0: **137.25** instructions (float 65.0,
int 56.5, other 15.75), 2 dpas, 0 spills.

Rather than estimate the ceiling, a floor probe deleted the entire
scale-reload mechanism from the loop — numerically wrong, but a hard lower
bound on any correct scheme. Floor body: **128.0** per k-tile.

Of the 9.25 difference, **5.25 is the reload itself**, which any correct scheme
must still perform once per group. Only **4.00 is removable**: `and`, `cmp`,
`jmpi`, and one `mov r57.5, r4.9` that exists only because the guarded block
shares the address.

- 4 / 137.25 = **2.9% of the body**; all four on the int pipe, 7.1% of it.
- Net after a nest adds outer-loop control (~1.1/k-tile at G=128): **~2.1%**.
- A peel instead multiplies B028's 106 instructions by `group_size/tile_k`:
  424 instructions at G=128, 848 at G=256. Far worse.
- Across instantiated group sizes: G=32 gives **0** removable (predicate
  already gone), G=64 gives 4, G=128 gives 4, G=256 gives 3.

**2.1–2.9% is below the ~5%-of-body stop threshold, and below this host's 1.63%
noise floor once netted. Stopped at stage 1.**

## The finding that matters more than the target

**`VLLM_XPU_LAGUNA_PREFETCH_DIST` is unreachable on 12-row decode.**

`MoEGEMMLauncher` (`grouped_gemm_xe2_interface.hpp:331`) reads
`laguna_int4_scale_fold()`, `laguna_int4_scale_vec()` and
`laguna_int4_dequant_mad()` and never calls `laguna_int4_prefetch_dist()`. Its
only three call sites — lines 502, 585, 668 — are the M8 launchers, which
`num_rows=12` never reaches. `XE_GEMM_4BITS_FOLD_DISPATCH` passes 7 arguments,
so `prefetch_dist_override` (`gemm_xe2.hpp:631`) keeps its default 6, and the
ISA confirms it is constant-folded: `add r4.12, r4.9, 768`, with 768 = 6*128.
Verified independently by the orchestrator before acceptance.

**This retires the recorded closure "prefetch distance 3 and 12 vs 6" as
evidence.** Those legs could not have varied anything on the decode path; the
arms were the same machine code. The conclusion "do not re-sweep the runtime
knob" still stands, but the measurement behind it was measuring nothing, and
the companion screen's stated mechanism — a runtime value threaded as a
function argument — described the M8 path, not decode. On decode the value is
a compile-time constant.

That makes reachability itself the next candidate, and it is a different class
of change: prefetch distance is a memory-timing lever, not an instruction-count
one, so the stage-1 instruction gate cannot screen it and only a leg can size
it. It is bitwise-neutral by construction because Xe2 block prefetch is a
null-destination send.

## Honest defects in the analysis

- The shipped `.so` was never disassembled. The installed `ocloc` IGA cannot
  decode this Xe2 encoding (*"GED reports invalid value for field
  Src0RegFile"*), and recompiling the real translation unit produced no dump
  because **IGC runs at link time for `spir64_gen`, not per-`.o`** — a
  35-minute compile wasted, and the 117.1 GB RSS peak this session came from
  it. All evidence is from a harness TU, cross-validated by reproducing the
  known SCALE_VEC 422->389 delta. Sound, but one inference step from the binary.
- The floor probe computes deliberately wrong results and was never run on
  GPU. It is a bound, not a candidate.

## Lesson

The premise assumed a compiler had not done an obvious optimization. It had —
and at one group size it had done something strictly stronger than the
proposal. Before hoisting anything out of a loop by hand, check whether LICM
already moved it. Counting instructions in a static listing rather than
weighting them by execution frequency inflated a 39-instruction dynamic cost
into a 53-instruction static one, and inflated a 2.9% opportunity into an
apparent 10-instruction win.
