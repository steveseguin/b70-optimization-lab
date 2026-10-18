# Packet117: move independent HC sigmoid work onto existing lanes

CPU preparation on `steve-b70s`, beginning 2026-10-18 09:41 UTC; two-hour
budget. `git pull --rebase` refused unrelated dirty orchestration files;
`git fetch origin` confirmed both HEAD and origin/main at `141e207cebc0`.
No GPU, service, live queue, sudo, host setting or other process is changed.
The compiler turn respects the coordinator's whole-host hold.

## What the 31% number actually includes

[Packet110's table](../experiments/own-xpu-runtime/stage2/packet110-class-roofline/ROOFLINE.md)
is synthetic full-layer attribution, not physical DRAM bandwidth or a model
benchmark. Its HC gate event includes the Q8 GEMV **and four sigmoid products
and an ordered mix**. The useful-byte count cannot separate those costs.
There are **10,240 gate outputs, not 6,400**: four streams × 2,560 hidden
positions, with K=320. The 25,600 output bytes are 20,480 gate bytes plus
5,120 mix bytes.

Source: `packet110-class-roofline/p60_submit.cpp`, `p73_hc.hpp`,
`p60_math.hpp`, `p49d_small.hpp`, `byte_model.py`, and
`packet17-detmath/detmath.hpp` (local paths under `experiments/own-xpu-runtime/stage2`).
The selection's `hc_gate=wide` dispatches `p73hc`, not the old single-row kernel.

* Weights originate as Q8_0. The runtime has already expanded each row to
  320 signed code bytes, ten FP32 scales and twenty metadata bytes: 380-byte
  row pitch. The gate reads 360 useful weight bytes/row, plus 640 input and
  20,480 norm bytes: 3,707,520 read bytes. It does not convert FP16 scales in
  the hot loop. Four neighboring logical lanes reuse each scale field.
* Each existing subgroup handles two neighboring rows, sharing its eight-wide
  BF16 input load. Each logical lane reads two contiguous 32-bit code words
  per row, converts eight signed codes to float, multiplies by the scale,
  multiplies by the BF16 input widened through bits, then adds in order.
  Lanes 0–7 do a second eight-element chunk; lanes 8–31 do only one. The
  second iteration therefore has only 25% of lanes active.
* The exact per-output tree is still 32 leaves, distances 1,2,4,8,16, with
  the left operand retained. There are 640 WG256 groups, eight SG32 groups
  per workgroup, sixteen gate rows/four mixed outputs per workgroup, one
  local barrier and 32 bytes of local gate scratch in production.
* After that barrier, only work-items 0–3 run the mix. Each runs **four
  serial calls to the software FP32 exponential** inside sigmoid. This
  exponential uses paired-float polynomial arithmetic and explicit FMAs,
  not a hardware native-exp instruction. All useful sigmoid work sits in
  one subgroup while seven have finished their row sums. That serial work
  and the short K are concrete reasons the event is not comparable to a
  pure long GEMV's byte rate. Their exact timing share is unmeasured.
* `hc.*.low` has K=10,240 and Split4, 324 WG128 groups (320 low rows plus
  four inject rows); much longer streaming work amortizes its reduction and
  epilogue. `small.ffn.q6` is a four-member router/shared-gate/shared-up/scalar
  tuple, not one gate. It uses expanded Q6 signed bytes and FP32 scales,
  K=2,560, Split4 and V4 independent rows. Its reported 92% includes a
  different output count, arithmetic and epilogue. Similar useful bytes do
  not imply similar instruction or occupancy cost.

Register/spill and occupancy conclusions await linked offline compiler
metadata. No hardware occupancy or bandwidth counter is claimed.

## Distinct mechanism and exactness contract

A repository-wide `rg -i '\bhc\b|hc[._ -]|hyper' --glob '*DO-NOT-REPEAT*'`
preceded implementation. Relevant exclusions include packets 51, 52, 53b,
67, 69, 73, 90, 94, 99, 101, 102 and 104. Packet104's HC tile16 arm was
1.006565× control; virtualization and four-stream subgroup geometry are
closed. Packet90 H1 expanded weight cache and packet94 norm-consumer fusion
are not reopened. Packet86's conversion-bound attribution does not establish
that this fused event's serial software sigmoid is free.

[Candidate](../experiments/own-xpu-runtime/stage2/packet117-hc-gate/hc_gate.hpp):
keep `p73hc::chains`, its two-row pairing, original weight layout, SG32 tree,
WG256 geometry and one launch. Broadcast the two already-reduced FP32 roots
to existing lanes 0 and 1. Each computes one unchanged BF16-rounded gate,
sigmoid and multiplication. Store sixteen independent FP32 products in
64 bytes of local memory, then retain the same barrier and original
`(((0+p0)+p1)+p2)+p3`, divide-by-four, BF16 mix. Thus the longest serial
sigmoid sequence becomes one call instead of four. No integer dot, changed
scale, new sum tree, weight cache, transposition, or large-GRF experiment.

The expected value is enough to justify one micro: the supplied gate event
has about 15 microseconds above its byte floor; the required 30% reduction
would save roughly 6.6 microseconds/call, about 0.32 ms per half across both
HC sites. This is an opportunity calculation, **not a predicted or measured
model speedup**. Fail the mechanism if either fresh process misses the gate.

## Prepared checks and coordinator handoff

The micro copies packet110's complete-layer harness, using its deterministic
synthetic weights and changing layer inputs. It compares all producer outputs
and mutable state and directly challenges HC inactive/error/capacity/NaN/Inf/
subnormal cases. Both QSA and GDN run at occupied context 128, ten warmups and
forty measured pairs, alternating arm order. Every per-site/order/layer median
must be <=0.70× production in **each of two fresh processes**. It is an
operator diagnostic, never a realistic model benchmark or quality promotion.

GNU and Intel CPU gates compare full 25,600-byte HC outputs and raw FP32
chains in two fresh processes each. The one-load v5 copy is prepared in
parallel from packet111 after 111r, with `hc_gate=production|p117`. Its launcher
must recompute the sealed two-process micro qualification before admission.
Native exactness, startup, reset, selection and pre-exec limit gates remain
separate. No measured speed or device exactness is claimed during preparation.

Commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B ... </dev/null`.
CPU-only entry processes set the 8 GiB cap; imports do not. One compiler at a
time uses packet94's compile-turn lock. Root free must stay >=25 GB and the
whole packet build <=250 MB. Binaries and temporary mirrors are ignored;
compact receipts, patches and source are retained.

Status: implementation and queue receipts in progress; GNU initial checks
passed. Intel and native compilation wait for the coordinator's whole-host
hold to release. The initial waiting CPU build was stopped by its exact PID
and restarted after the final device-only scheduling refinement; no GPU child
existed. No queue proposal is ready until it compiles, seals and temp-plans.
