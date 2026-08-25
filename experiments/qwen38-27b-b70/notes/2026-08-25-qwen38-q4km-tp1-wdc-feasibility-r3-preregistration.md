# Qwen3.8 27B Q4_K_M TP1 WDC feasibility r3

Date: 2026-08-25

Status: **preregistered; diagnostic only.**

R1 exhausted VRAM while forcing all reordered types. R2 isolated the Q4_K WDC
door but proved `REORDER_IN_GEMM=1` is still width-gated and therefore vacuous
in this harness. R3 answers one question before source authoring: can the
intended Q4_K WDC planes and B64 workload fit on a 32 GiB B70 at all?

The [manifest](../data/2026-08-25-qwen38-q4km-tp1-wdc-feasibility-r3.json)
freezes matched DNN-off control and diagnostic forced-reorder arms at context
`24576`, exactly `64 * (128 prompt + 256 generated)` tokens. This context is
derived from the measured matrix rather than tuned after seeing a speed row.
The candidate explicitly disables default q8_0 WDC and enables only Q4_K WDC.

The forced-reorder arm cannot ship. It only authorizes a production,
type-scoped source fix if it completes, emits an engaged non-mutant Q4_K WDC
census, gains at least 5% at B64, and retains at least 95% of B1. Even then,
endpoint sequential-oracle validation remains mandatory.
