# Batched prompt reading: feasibility and first exact step

CPU source/design study, 2026-10-19. No batched-prefill implementation or speed
measurement is claimed here. The target remains `iq3-p49-split32-v1`, with its
unchanged quantized weights, arithmetic and BF16 state/KV. This is a widened
prompt-reading objective, not a reopening of the discarded-sibling decoder.

## Prior work checked first

The repository-wide `rg -n -i 'prefill|batch' --glob '*DO-NOT-REPEAT*'` scan
returned 52 matching lines, retained in
[the scan](evidence/do-not-repeat-prefill-batch.txt). Relevant boundaries:

- [Packet49b](../packet49b-gemv/DO-NOT-REPEAT.md) and
  [packet66](../packet66-mtp-depth2-probe/DO-NOT-REPEAT.md): an M=2 operator
  does not establish an integrated batched verifier or safe rollback.
- [Packet68b](../packet68b-batched-rows/DO-NOT-REPEAT.md): do not rebuild the
  sealed generic batching identity. Start from production arithmetic instead.
- [Packet151](../packet151-sibling-cost/DO-NOT-REPEAT.md): the discarded second
  candidate cost 9.21 ms extra device time in the measured rank-0 half
  (11.44 to 20.65 ms); the sibling-policy reopening bound was 1.952 ms.
  That policy stays closed. Its partial pair kernels are mechanism evidence,
  not evidence of fast prefill. Its own prefill `fixture=0` must remain excluded.
- [Qwen's census rule](../../../qwen38-27b-b70/DO-NOT-REPEAT.md): establish
  row/batch invariance at every operator shape before endpoint token bisection.
  Do not switch to arbitrary GEMM/oneDNN reduction geometry and call it exact.
- [Packet58am](../packet58am-demand-transfer/DO-NOT-REPEAT.md): preserve slow
  first-request evidence and never enforce data arrival with a wall-clock proof
  deadline. Packet165 keeps that request as `incident-retrospective`; it is not dropped.

## Prompt processing today

The frozen packet163 two-card source is easy to follow in
[`lineage/native_controller.hpp`](../packet163-full-gate/two-card/lineage/native_controller.hpp),
lines 63–94. It advances one prompt position at a time. Rank 0 for position
`p+1` may overlap rank 1 for `p`; this is pipeline overlap, not an M>1 matrix.
[`lineage/rank.hpp`](../packet163-full-gate/two-card/lineage/rank.hpp),
lines 124–157, admits one position, prepares one token and runs its launch list.
Line 154 skips final norm/logits/argmax on ordinary prefill positions. The last
prompt position produces the first generated token. The serial loop retained in
[`lineage/main.cpp`](../packet163-full-gate/two-card/lineage/main.cpp),
lines 1868–1870, explicitly calls `step` for each input token. The current
one-card entry's equivalent loop is in its
[native main](../packet163-full-gate/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native/main.cpp),
after the request/reset and `step` definition beginning at lines 1975–1990.

Consequently, prefill repeatedly reads dense weights and submits small
operations. A chunk scheduler could share those reads and submissions across
known prompt tokens. It must also preserve causality and recurrence; merely
setting matrix M to 2 cannot do that.

## Available kernels and remaining gaps

| Component | Existing M>1 building block | Limitation |
| --- | --- | --- |
| Dense projections | [production_rows.hpp](../packet151-sibling-cost/production_rows.hpp), lines 9–40 and 52–79: shared weight load with two independent ordered accumulators and original split/SG32 trees. Lines 124–139 admit Q6 K=2560, Q8 K=2560/640/320, F32 K=10240; attention output Q6 K=6144/split4. | Selected production shapes only; this is not general GEMM. |
| Routed experts | [batched_experts.hpp](../packet151-sibling-cost/batched_experts.hpp), lines 9–24, 28–41, 63–70: stable route union, IQ2 gate/up K=2560 and IQ4 down K=640, original route slots and BF16 output. | Exceptional IQ3 expert shapes are not admitted by this production pair dispatcher. Pairing ten routes is not automatically weight reuse. |
| Packed GEMV | [p49b_gemv.hpp](../packet49b-gemv/p49b_gemv.hpp), lines 67–85 and 121–135: IQ2/IQ3/IQ4/Q8 (+Q6) decoding and `lanes2`, two ordered FP32 chains sharing a decoded tile. | [Integration notes](../packet49b-gemv/INTEGRATION.md), lines 8–20, distinguish primitive support from active dispatch and engine scheduling. |
| Verifier attention | [p49_qsa_submit.cpp](../packet151-sibling-cost/p49_qsa_submit.cpp), lines 35–48: M=1/M=2 admission with the original three-stage split32 bridge. | There is no complete causal M=2 engine verifier to enable. KV visibility and each row's selected indices still need scheduler integration. |
| GDN recurrence | [p82b_recurrence.hpp](../packet151-sibling-cost/p82b_recurrence.hpp), lines 53–107: sequential token loop within independent head/row workgroups. | [p49d_recurrence.hpp](../packet151-sibling-cost/p49d_recurrence.hpp), line 197, uses the default single-token shape. Multi-token binding/state plumbing is missing. |

[batch_probe.hpp](../packet151-sibling-cost/batch_probe.hpp), lines 49–65,
leaves HC, small tuples, shared-down and non-matrix work serial.
[The sibling rank path](../packet151-sibling-cost/v5/native-src/rank.hpp),
line 135, explicitly requires `fixture>0`; it is not already batched prefill.

## Exactness contract

For every chunk, compare **each token's intermediates, output and persistent
state** with the original sequential M=1 path. A final greedy-token match alone
is too weak. Keep each row's original multiply/add order, split tree, rounding
points, BF16 stores, route-slot order and error behavior. No compressed KV,
prompt reuse, changed weights, tolerance gate or associative recurrence scan.

Attention must expose token 0 to itself and prior context, then token 1 to that
same context plus token 0. Preserve the original selected-index order, padding
and split32 reductions. See
[p49_qsa_reference.hpp](../packet151-sibling-cost/p49_qsa_reference.hpp),
lines 19–23, 55–79 and 97–98: future KV is excluded using `position+row`, and
row 0 of the M=2 case has the shorter causal extent. A triangular mask alone
does not prove equal selection or summation order.

GDN remains sequential across tokens and parallel across independent heads.
[p82b_recurrence.hpp](../packet151-sibling-cost/p82b_recurrence.hpp),
lines 90–107, reads the previous rounded state, writes BF16 after each row and
requires the inter-token barrier. Carrying FP32 between rows changes results.
Convolution, token history, PLE and any pooled-attention history must advance in
the same original order. Keep the attention/GDN state once per sequence; do not
mistake two independent decoder snapshots for a causal prompt chunk.

## Priced conditional ceiling

The brief's **90 tok/s** is an estimate from roughly 80-token warm requests,
not a measured 512-token rate. Packet165 will replace that two-card planning input.
Packet163's 7.84/7.85 native-loop rates include first-use work and cannot price
the warmed chunk scheduler. Token-mode `rank_trace.gpu_ms=0` is not a measured
device floor, and host `busy_ms` is not device time.

Let `f` be the as-yet **unmeasured** fraction of warm request time that can be
reduced ideally by batching M tokens. Assume zero extra dispatch, routing,
buffer, pipeline or attention overhead. The conditional ceiling is
`S(M) = 90 / ((1-f) + f/M)` tok/s. These are analytical planning calculations,
not measurements, predicted benchmark points, or physical hardware limits.
[The arithmetic](evidence/prefill-ceiling.json) is generated by
[`prefill_ceiling.py`](prefill_ceiling.py).

| Chunk | f=50% | f=75% | f=90% | All work scales (f=100%) |
| --- | ---: | ---: | ---: | ---: |
| M=2 | 120.00 | 144.00 | 163.64 | 180.00 tok/s |
| M=8 | 160.00 | 261.82 | 423.53 | 720.00 tok/s |

At M=2 and f=75%, the conditional 512-token TTFT is 3.56 seconds instead of
5.69 seconds at the provisional 90 tok/s. Even the ideal M=2 bound is only
180 tok/s. A doubled row count does not imply doubled performance.

Expert traffic is the main caution. The pair kernel has ten routes out of 512
experts. Under an explicitly hypothetical independent uniform routing model,
the expected union is `512*(1-(1-10/512)^M)` experts and shared-weight reuse is
`10*M / union`: only **1.0099× at M=2**, **1.0704× at M=8** and **1.3354× at
M=32**. Actual prompt routes may correlate; measure their union before assuming
reuse. Dense projection reuse and launch reduction are the first credible
savings. Packet151's costly extra row warns against pricing all expert work
as halved. It is not a prefill speed prediction.

The cost to earn the next step is one additional activation row, output/scratch
row and causal scheduling metadata, plus an operator census. Exact buffer bytes
must come from the production allocation plan; do not duplicate the model or
all recurrent state for every prompt token. No new model download is needed.

## Staged build plan

1. Finish two fresh warmed-reset 512-token measurements for the unchanged
   one- and two-card identities. Report TTFT-based rates, native-loop wall time
   separately, and device time as unavailable unless genuinely measured.
2. Build a CPU miniature of **one layer, two rows, one Q8 projection pair**.
   Leave everything else on original sequential operations. Census every
   production type/K/split, row position, permutations, repeats, error/inactive
   masks and NaN bytes against two M=1 calls before a device endpoint. Reuse
   exact production arithmetic; do not sweep new geometries.
3. Build the causal two-token layer scheduler. Project the pair, then commit
   QSA KV/selection in original position order and GDN/conv/history with the
   sequential BF16 recurrence. Compare both rows and complete state at context
   boundaries 31/32/33, odd final chunks and reset transitions. Repeat through
   all 48 layers; leave subsequent decode unchanged.
4. Add the production IQ2 gate/up and IQ4 down pairs individually. Keep IQ3
   exceptional routes, HC, small tuples and shared-down serial until their own
   exact operator gates pass. Record route overlap and bytes to price each
   addition; do not reopen packet151's discarded-sibling policy.
5. After exact endpoint parity and fresh-process determinism, measure the
   complete warmed 512-token request on at least two fresh owners. Profiling
   is a separate diagnostic. Move to M=4/M=8 only if measured savings justify
   the larger scheduler, scratch and attention admission (currently at most 2).

The decision is to start with the exact two-row Q8 projection and causal
scheduler after the warm baseline, not to build a generic large-M GEMM runtime.
No runtime change or batched-prefill device proposal is made by this study.
