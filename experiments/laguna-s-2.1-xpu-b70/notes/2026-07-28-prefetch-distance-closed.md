# Prefetch distance is closed; its control binary is the open question

Date: 2026-07-28 America/Toronto

## Prefetch distance: no improvement

`VLLM_XPU_LAGUNA_PREFETCH_DIST` made the INT4 mainloop prefetch distance
selectable at runtime (kernel `3cb7b67`). It cannot change arithmetic: the
value has four uses, all feeding `prefetch()`, and the scales the MMA consumes
load from `group_idx`. All legs below are 13/13 exact with `cached_tokens=0`.

Interleaved control/candidate so drift during the sequence hits both arms:

| order | dist | legacy | conventional |
| --- | ---: | ---: | ---: |
| 1 | 6 (control) | 102.534006 | 101.508665 |
| 2 | 12 | 102.269602 | 101.246906 |
| 3 | 6 (control) | 102.266315 | 101.243652 |
| 4 | 12 | 101.407946 | 100.393866 |
| earlier | 12 | 102.078224 | 101.057442 |
| earlier | 3 | 101.339257 | 100.325865 |

Control median 101.376; distance-12 median 101.057; distance 3 lower still.
**The control equals or beats every candidate.** The single promising 101.057
was noise, and the hypothesis that motivated the sweep -- that W2's 19% K-loop
warm-up at 32 tiles was costing time -- is not supported. Closed; do not sweep
further distances.

## The unintended finding

Both control legs sit above **every** leg measured on the incumbent binary:

| binary | conventional |
| --- | ---: |
| prefetch build, control (n=2) | 101.508665, 101.243652 |
| incumbent, record packet | 100.439886 |
| incumbent, session legs (n=3) | 99.378217, 100.074233, 100.995948 |

The only difference is codegen, not arithmetic: the warm-up loop previously had
a compile-time bound of 6 and fully unrolled; a runtime bound emits a
dynamically-bounded loop, and the text section grew about 7.2%.

That is **not established** -- two legs against a 1.63% spread, and the gap to
the record packet is 1.0%. It is recorded because it is the only positive
signal this session produced and because it would be lost otherwise.

## The 3v3 confirmation, run

All legs 13/13 exact with `cached_tokens=0`, both arms at prefetch distance 6.

| binary | conventional legs, sorted | median | n |
| --- | --- | ---: | ---: |
| prefetch build | 100.403894, 100.955219, 101.243652, 101.330567, 101.508665 | 101.243652 | 5 |
| incumbent | 99.250171, 99.378217, 100.074233, 100.293100, 100.439886, 100.995948, 101.171141 | 100.293100 | 7 |

Separation is **+0.95%** at the median. Every prefetch leg lands at or above
the incumbent's fifth-highest, but the ranges overlap -- prefetch's minimum
100.404 sits below the incumbent's maximum 101.171 -- and 0.95% is inside this
host's 1.63% spread.

**Verdict: suggestive, not established.** The direction is consistent across
five legs and the mechanism is plausible (instruction scheduling only; the
arithmetic is provably unchanged), but the effect is smaller than the noise it
must be separated from. It is not banked, and no record may rest on it.

Best single leg measured anywhere this session: **101.508665 conventional**,
prefetch build, 13/13 exact -- 0.491 short of 102.

## To confirm or kill it

Three more control legs on the prefetch binary and three on the incumbent,
interleaved, same harness and seed. If the separation holds at n=5 per arm it
is worth roughly 1% and is exactness-preserving by construction. If it
collapses, the prefetch work reduces to a negative result and the binary should
be reverted to the incumbent.

Provenance: kernel `/home/steve/src/laguna-xpu-kernels-tile12-20260728` at
`3cb7b67`, `libgrouped_gemm_xe_2.so` =
`12e358dee715074ab82c39a78ad724ff0b55d3e0e1cad54ef7ea5ac7b77eff88`, built with
oneAPI DPC++ 2025.3.3. Its runtime lock is
`experiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-prefetch.json`; the sealed
packet's lock was copied, never edited.
