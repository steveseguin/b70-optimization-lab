# Xe2 full187 M=9/M=16 row-tile verifier assessment

Date: 2026-07-13

Status: isolated M=9/M=16 tile experiment passed correctness; runtime source
not changed

## Decision

Generalizing the packed full187 verifier to M=9 and M=16 has a materially
higher favorable-workload ceiling than integrating the small
SwiGLU/Q8/down boundary. Keep the direct canonical-SoA producer from that
experiment as a prerequisite, and prototype wider verification first.

This is not a claim that simply raising DFlash block length improves the strict
mixed suite. Current mixed-prompt acceptance nearly saturates before width 9.
Wider verification is a high-ceiling/favorable-route and future-better-draft
investment.

## Row ownership tested

The existing comparator already loads one packed `N16 x K32` weight tile and
uses it for all rows:

- M=9: one repeat-8 DPAS call for rows 0-7 and one repeat-1 call for row 8;
- M=16: one repeat-8 call for rows 0-7 and one repeat-8 call for rows 8-15.

The weight tile remains in an ESIMD register across both calls. It is not read
again for the second row tile.

The new experiment parameterized the number of adjacent N16 output tiles owned
by one workgroup:

- `J=2`, the original design, accumulates two N16 tiles at once;
- `J=1` halves accumulator and SLM footprint while preserving weight reuse
  across rows. It does not reuse weights across N tiles because adjacent N
  tiles contain different weights.

Changes are isolated to:

- `../xe2-verifier/production-comparator-v3.cpp`;
- `../xe2-verifier/build-production-comparator-slm-v3.sh`.

Reproduction:

```bash
ZE_AFFINITY_MASK=2 XE2_WIDTHS="9 16" XE2_JOINTS="2 1" \
  XE2_ITERS=100 \
  experiments/qwen27-dflash-sycl-b70/xe2-verifier/build-production-comparator-slm-v3.sh
```

Retained log outside Git:

`/mnt/fast-ai/bench-results/qwen27-xe2-verifier/m9-m16-joint1-joint2-20260713-gpu2-100x2.log`

## Result

All M=9/M=16 shapes had exact Q8 values and metadata. Candidate-versus-
production maximum output deltas were only `1.5e-5` to `5.4e-5`, including
the `K=17408` down shape. The earlier approximately `0.066` down discrepancy is
not present after the canonical correction semantics now used by the current
source and comparator.

`J=1` is the correct next runtime ownership for M=9/M=16:

| Width/shape | J=2 candidate kernel | J=1 candidate kernel | J=1 effect |
|---|---:|---:|---:|
| M9 5120x5120 | `47.7 us` stable repeat | `34.6 us` | `27.5%` faster |
| M9 5120x17408 | `151.9-200.7 us` | `103.9-104.9 us` | large, stable J=1 time |
| M9 17408x5120 | `127.8-127.9 us` | `120.0-120.1 us` | `6.1%` faster |
| M16 5120x5120 | `114.0 us` | `98.8 us` | `13.3%` faster |
| M16 5120x17408 | `236.0-237.4 us` | `162.5-229.2 us` | directionally better, clock-sensitive |
| M16 17408x5120 | `232.2 us` | `206.9-207.1 us` | `10.9%` faster |

Production-control timing varied with device clock during the long alternating
run, so candidate absolute medians and paired repeated direction are stronger
evidence than any single reported ratio. M=9 J=1 was about `1.89-2.08x` faster
than exact production total on all three shapes. M=16 J=1 was only about
`1.30x` on square/down and `1.49-1.65x` on up. J=1 reduces, but does not remove,
the width-16 cliff.

## Concrete runtime prototype

### Kernel templates

In `ggml-sycl/mmvq.cpp`:

1. Replace hard-coded `m=6` internals with guarded specializations
   `<M, JointN>` for `{6,2}`, `{9,1}`, and `{16,1}`. Do not make arbitrary M a
   dynamic loop.
2. Add a row-tile helper that loads `bv` once per K block/N16 tile, then calls
   DPAS on `av[0:8]` and, when `M>8`, `av[8:M]`.
3. For M=16 keep separate `acc_lo` and `acc_hi` vectors rather than one
   `M*JointN*16` aggregate. Consume each DPAS result immediately so both dot
   vectors are not simultaneously live.
4. Use eight strided K workers and one SLM barrier as the first control.
   Then sweep K splits `{4,8}` only for M=16; this is a register/occupancy
   experiment, not a new numerical order.
5. Use the direct canonical-exact SoA quantizer with volatile 16-bit half
   materialization. Scratch sizes for K=17408 are `195840` bytes at M=9 and
   `348160` bytes at M=16. The packed-weight ABI remains v2 and unchanged.
6. Generalize both single and dual gate/up entry points. The same 8.73 GiB of
   187 packed mirrors serves every width; no new weight copy is needed.

### Dispatch and matcher

In `ggml-sycl/ggml-sycl.cpp`:

1. Select only exact verifier widths from `src1->ne[1]`: M=6, M=9, or M=16.
2. Preserve all current BMG, Q4_0, contiguous-layout, pack-ABI, graph-off, and
   tensor-family guards.
3. Extend the adjacent gate/up matcher and down matcher without changing graph
   skip semantics. M=9/M=16 use the same tensor names and packed slots as M=6.
4. Emit separate counters for each width and projection family. A width miss
   must visibly fall back to production.
5. Keep graph capture disabled until scratch moves from a function-local pool
   allocation to fixed per-execution-slot ownership.

### Optimization gates

1. BMG AOT only for promotion evidence.
2. Real first/middle/final gate, up, and down shadows at each width.
3. Require exact canonical Q8 bytes/metadata, candidate max error within the
   already-cleared real projection bound, and no all-zero scales.
4. Require `>=1.5x` exact-production total on all M=9 shapes before runtime
   integration. This gate is already met in the isolated J=1 repeats.
5. Do not integrate M=16 full187 until square and down reach at least `1.5x`,
   or an end-to-end favorable lane proves a material cycle win despite the
   microkernel miss.
6. Validate n_max=8 and n_max=15 independently with cycle timing, acceptance,
   output quality, and fixed cold-cache identity.

## Acceptance ceiling: strict mixed suite

The strict GDN-record evidence has `968` accepted draft tokens from `2715`
proposals over `1536` emitted tokens, approximately `568` cycles and only
`2.704` emitted tokens/cycle at DFlash5.

A geometric fit with `p ~= 0.661` gives:

- n_max=7: `2.843` emitted/cycle;
- n_max=8: `2.879`;
- n_max=15: `2.947`;
- infinite block: about `2.95`.

At the current `64.559 ms` cycle, even a free width increase would move the
strict ceiling only from roughly `41.9` to `45.7 tok/s`. In reality M=9/M=16
cost more, so they lose unless the draft becomes substantially more accurate.
At present acceptance, 100 tok/s still requires about a `29.5 ms` cycle even
at n_max=15; 200 tok/s requires about `14.7 ms`.

Therefore do not replace strict DFlash5 globally with DFlash8/15. Route wider
blocks only after rolling acceptance predicts a favorable prompt, or after a
better/adapted draft changes the measured acceptance distribution.

## Favorable-workload ceiling

The prior favorable code trace measured:

| Width | Target | Draft | Feature/process | Emitted/cycle |
|---:|---:|---:|---:|---:|
| M9 | `107.626 ms` | `66.467 ms` | `2.301 ms` | `8.35` |
| M16 | `138.877 ms` | `69.085 ms` | `2.758 ms` | `12.85` |

For 100 tok/s those acceptances permit cycles of `83.5 ms` and `128.5 ms`;
for 200 tok/s they permit `41.75 ms` and `64.25 ms`.

If full187 M16 target verification could be made as flat as the measured M6
target (`58.189 ms`) while leaving today's draft and feature phases unchanged,
the favorable ceiling would be about:

`12.85 / (58.189 + 69.085 + 2.758) ms = 98.8 tok/s`.

Thus target generalization alone can plausibly approach the single-card
100 tok/s favorable objective, but not 200. With a near-zero or separately
drastically optimized draft phase, the same favorable M16 acceptance and an
M6-like target would be about `211 tok/s`. That is the theoretical reason to
retain the lane for the 200 tok/s objective, but it requires both near-flat
M16 target execution and a roughly 69 ms draft-phase removal; current kernels
do not provide either claim yet.

For the strict mixed suite, this ceiling does not apply because emitted tokens
per cycle remain below three.

## Next experiment order

1. Promote direct canonical SoA plus M=9 J=1 into a disabled runtime prototype
   using existing packs; run shadows and a favorable n_max=8 cycle trace.
2. Sweep only M=16 J=1 K splits 4/8 and separate low/high accumulator lifetime.
   Integrate only after square/down clear the gate.
3. Optimize the five-layer Q8 DFlash draft independently. Wider target rows
   cannot compensate for a 66-69 ms draft phase.
4. Add rolling-acceptance routing: DFlash5 remains the strict default; M9/M16
   are selected only when the measured expected emitted-token gain exceeds the
   measured wider cycle cost.
