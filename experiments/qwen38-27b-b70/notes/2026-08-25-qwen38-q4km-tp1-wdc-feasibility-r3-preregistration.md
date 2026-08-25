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

## Outcome

The matched control completed at `24.392443 tok/s` (B1) and
`94.607864 tok/s` (B64). Although the command requested context `24576`, the
tool reported `n_kv_max=32768`; this attempt therefore does not establish a
smaller allocation. The candidate failed before its first row while the broad
force-reorder hook copied the 1.27-billion-element q6_K output tensor.

R3 closes the flag-only approach. The next candidate must be a source-level
Q4_K-only reorder door that leaves q6_K untouched. The complete
[control](../data/qwen38-q4km-tp1-wdc-feasibility-20260825-r3-control-attempt1/summary.json)
and [candidate failure](../data/qwen38-q4km-tp1-wdc-feasibility-20260825-r3-candidate-attempt1/raw.log)
are retained; the candidate produced no speed row.
