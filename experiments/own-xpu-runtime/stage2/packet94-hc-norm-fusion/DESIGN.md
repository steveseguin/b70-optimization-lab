# Packet94: exact HC norm into low/injection

Source: packet84 bundle, copied before edits; parent hashes in
`parent-source-manifest.json`. Control: hc-wide, wide64, ordered,
rec-parallel, production route/norm/dense, draft-HC, batch rollback, 24/24.

## Chain and live values

Each target layer has attention HC then FFN HC. Each reads `streams`, four
BF16 streams of 2,560 elements (10,240 total). `hc.*.norm` computes each
stream independently: FP32 x*x, 80 aligned adjacent 32-leaf addition trees,
48 positive-zero roots padding to 128, four adjacent 32-root trees, then
(root0+root1)+(root2+root3). Keep `detmath::rsqrt(total/2560.f+1e-6f)` and
`BF16((widen(x)*inv)*(gain+0.f))`. Gain is FP32. Scratch[stream*80+chunk]
retains all 320 FP32 partials.

Low consumes all 10,240 BF16 norms through expanded Q8_0, producing 320
BF16 outputs. Injection consumes the same norms through F32 weights, producing
four BF16 outputs. Each dot has four original split ranges, 32 ordered logical
chains per split, adjacent tree32, and (p0+p1)+(p2+p3). Low's BF16 store is
followed by `BF16(detmath::silu_div4(widen(low)))` in the 320-element act buffer.
Injection retains workspace[row*8+0..3]; slots 4..7 remain untouched.

Packet73 gate reads act and expanded Q8_0 up weights; its two adjacent output
rows share raw reads but preserve each row's 32 logical chains. It stores all
10,240 BF16 gates. Mix widens those gates, applies the original sigmoid, then
adds sigmoid(gate[s])*widen(norm[s,k]) for s=0,1,2,3 in order and stores
BF16(sum/4). Its 2,560 BF16 outputs feed the branch. BF16 injection controls
later branch-to-residual combination; that writes BF16 streams before FFN HC
or the next layer. Final HC and draft HC remain unchanged.

Norm readers are low, injection and mix; gate reads act, not norm. Therefore
**retain norm** and its scratch for mix, snapshots, and diagnostics. Remove
only the separate norm compute launch. All sixteen p60 bindings stay live,
disjoint and checked. No grid barrier or global spin is introduced.

## Candidate

A dedicated low/injection workgroup recomputes the four RMS values with the
original trees. It applies gain and BF16 rounding inline on each input load.
Only workgroup zero writes the retained global norm and scratch. Other groups
never read that tensor while enabled; they use residual/gain and their own
identical RMS factors. The later gate/mix waits for the whole fused launch.
Inactive, sticky-error and invalid-position paths retain original norm bytes
and still perform low/injection from those bytes, matching production.

Stage 0 captures no compute; stage 1 captures the fused kernel; stage 2 retains
packet73. Full-shape mocks must prove stage0 absence and fused stage1 presence
on both HC sides and both ranks, including alternate banks and draft startup.
CPU fixtures compare every norm/low/act/inject/gate/mix byte, scratch/workspace
and controls over consecutive tokens under GNU and Intel. No NaN tolerance.

Packet90 HC weightcache is downstream and can compose without a norm change:
copy its exact gate/loader delta only; retain expert wide64. Include the combined
view only if all byte, memory and startup gates pass.

## Expected value and boundaries

Packet77 reports 0.19 ms per norm class per half (not each layer launch).
The ideal removed budget is 0.38 ms/rank/half; recomputation costs are unmeasured.
Packet85 estimates +0.293 tok/s per 0.1 ms on rank1, +0.062 on rank0 misses.
These are motivation, never a speed result. Packet78 only changed norm geometry
and lost; this candidate removes the launch into its consumer. Do not change
reduction order, packet60 BF16 boundaries, or packet73 gate/mix semantics.

CPU-only preparation, 2.5-hour budget, at most 8 GiB per process, one compiler
using /tmp/own-xpu-runtime-cpu-compile.lock. Build below 1 GB; refuse work if
root free space falls below 12 GB. Shared v4 stays frozen; both queue directions
are proposals planned only in temporary directories. GPU gates remain pending.
