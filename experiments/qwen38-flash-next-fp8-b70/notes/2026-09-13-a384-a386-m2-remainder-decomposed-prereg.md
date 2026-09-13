# Preregistration: A384-A386 - the remaining 11.2 ms of the two-row step, by block

## Question

On the exact-mode MTP1 line the two-row verify step is 33.69 ms (A369). The four zeroing arms
(A370-A373) attributed 21.0 ms (MoE GEMMs 14.2, QSA 4.7, GDN 2.1, HC ~0) and A378 attributed 1.5 ms to
the row-wise all-reduce, leaving 11.2 ms unattributed at two rows against 6.5 ms at one row. Which
blocks hold it, and which of them scale with the row count?

## Arms

MTP1 diag head `97e90c89` (= `f1d5cd88` + three zeroing switches, timing only, outputs garbage),
stage v2, exact-mode exports, step timing over three exact-2K rows; control A369.

- A384 `Q38_DIAG_SKIP=ple` (port 20001): the per-layer embedding gather and add is not run. The PLE
  tables live in host memory behind UVA; every row gathers its rows over PCIe in every PLE layer, so
  this is the leading candidate for a term that scales with rows.
- A385 `Q38_DIAG_SKIP=mlp_all` (port 20002): the whole MoE block is replaced by zeros: routing, sort
  and alignment, activation quantisation, the grouped GEMMs, the shared expert, the final sum and the
  block's all-reduce. Against A370 (GEMMs only) this prices the MoE glue plus collectives.
- A386 `Q38_DIAG_SKIP=lm_head` (port 20003): zero logits instead of the vocabulary GEMM (and its
  vocab-parallel gather), at two rows.

## Predictions

The three arms recover a total near 11 ms if the remainder is in these blocks; whatever they leave is
replay glue and norms. If the PLE gather is 3 ms or more at two rows, a device-side PLE row prefetch
for the draft position (bit-exact: same bytes, earlier) is the next lever; if MoE glue is the largest,
fusing the alignment/quantisation glue for M=2 is next; the LM head is expected near 1.5 ms and
row-invariant (bandwidth-bound).

## Stop rules

Server fails health; rows fail. Timing arms only; nothing is promoted from them.
