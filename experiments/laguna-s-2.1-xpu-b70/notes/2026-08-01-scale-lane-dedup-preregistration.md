# Laguna INT4 scale-lane deduplication screen

Date: 2026-08-01 America/Toronto

Status: **static ISA gate passed; isolated production build in progress.**

## Motivation

The protected exact BF16-KV record is `125.4619731637751 tok/s`; 130 requires
about 3.62% more throughput at unchanged acceptance. In the incumbent INT4
mainloop, `channel_num=2` and `x_idx=sg_local_id/2`. For each N slot, adjacent
SIMD lanes therefore load the same checkpoint scale twice:

- channel 0 sees `S0,S0,S1,S1,...,S7,S7`;
- channel 1 sees `S8,S8,S9,S9,...,S15,S15`.

The existing implementation retains both copies in FP32 scale registers. Xe
regioning can instead load one unique FP32-widened BF16 scale per lane and
broadcast each lane pair at the multiply. This can halve scale loads and live
scale state without changing the multiply's source type or rounding.

## Frozen treatment

Start from protected kernel commit `99886d783` in a fresh source worktree.
For the existing exact `w4a16_policy_m_8`, group-32, BF16 activation/scale,
INT4-weight, `ScaleVec=true`, `DequantMad=false`, `TransposedScales=true`,
BMG-128-GRF path only:

1. Load `Scales[..., n * 16 + sg_local_id]` once per N slot and keep its exact
   BF16-to-FP32 widening.
2. In the existing paired scale operation, present channel 0 as the repeated
   lower eight lanes (`<1;2,0>`) and channel 1 as the repeated upper eight
   lanes (`<1;2,0>` from element 8).
3. Retain the same two SIMD16 `BF16 * FP32 -> BF16` operations, the same source
   values per output lane, the same BF16 rounding points, and the same two DPAS
   instructions and accumulation order.

Add compile-time assertions for subgroup width 16, `channel_num==2`, and the
already required adjacent channel-pair fragment layout. Do not combine this
first arm with BF16 scale operands, SIMD32, dequant-MAD, or accumulator scale
folding, so any ISA result has one cause.

## Gates and stop rules

1. Extend the minimal IGC probe with an isolated compile-time treatment. Under
   BMG 128-GRF generation require two DPAS instructions, 32 BF16 scale
   multiplies, no spill/scratch markers, and identical multiply topology. The
   treatment must remove at least one scale memory send, at least eight final
   BMG instructions, or materially reduce allocated GRFs. Otherwise stop
   before a production extension build or GPU work.
2. If static code generation passes, implement a separate default-off,
   fail-closed production selector in the fresh worktree. Inspect the exact
   source diff and linked ELF before device execution.
3. Use distinct per-column scales in the deterministic changed-input component
   gate so a lane permutation cannot hide. Require raw BF16 equality for W13
   (`M=120,N=2048,K=3072`) and W2 (`M=120,N=3072,K=1024`) and at least 3%
   improvement in their summed stable median using 200 warmups plus 15 samples
   of 40 launches. A smaller result stops before model integration.
4. A component pass authorizes a separate endpoint preregistration only; it is
   not a throughput claim.

No target/draft/KV precision change, model or teacher change, prompt change,
warmed score, retry selection, metric substitution, reset, reboot, driver
reload, or privileged recovery is authorized by this screen.

## Static gate result

Source branch `experiment/laguna-scale-lane-dedup-20260801` at candidate
commit `1ed3b0b` was compiled with oneAPI 2025.3 for BMG in 128-GRF mode.
Artifact root:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-scale-lane-dedup-candidate-20260801T1505Z`.

| Final BMG metric | exact transposed control | lane dedup |
|---|---:|---:|
| instructions | 396 | **382** |
| BF16 scale multiplies | 32 | 32 |
| DPAS | 2 | 2 |
| scale `load.ugm.d16u32.a64` | 3 | **2** |
| `sync.allrd` | 6 | **0** |
| total `shl` | 22 | **20** |
| total `shr` | 18 | **17** |
| configured GRFs | 128 | 128 |

The apparent text matches for `spill`/`scratch` are declarations and compiler
options common to both arms, not spill traffic. The candidate clears the
preregistered eight-instruction threshold by six additional instructions,
removes one scale load, and preserves the arithmetic/DPAS topology. This
authorizes the isolated production build and component correctness gate; it is
not yet a performance or correctness result.
