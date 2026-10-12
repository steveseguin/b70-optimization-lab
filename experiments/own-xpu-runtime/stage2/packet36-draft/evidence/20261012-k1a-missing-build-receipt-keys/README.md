# K1a rejected after a correct run: two build-receipt keys were missing (2026-10-12 04:20–04:21 UTC)

K0 passed (04:14 UTC). K1a ran on card 0: 111 fixtures, 2,604 GEMV and 2,851 adapter
checks, native receipt `passed: true`, clean teardown, clean kernel log. Its output hash
`5e3409d3…` equals this packet's own sealed host fixture gate (`fixture-gates.json`) and
the K1 output of packets 29, 32 and 35. The wrapper nevertheless reported "K1 bytes
differ from host fixtures": the inherited gate compares against
`build-receipt.json["nongemv_fixture_host_sha256"]`, and this packet's restructured
build receipt no longer wrote that key (nor `cpu_tests_sha256`, read a few lines later).

Fix by the coordinator: both keys added to `build-receipt.json` from this packet's own
sealed gate files (checked against `gate_receipts`), recorded there under
`coordinator_amendments`. No binary, source or gate changed. Because K0 binds the
receipt hash, the whole chain is rerun under the suffix `r36b`.

**Latch.** The wrapper's failure path wrote `build/FAULT.json` for this boot. It is kept
here as `FAULT-retired.json`. Coordinator decision, 2026-10-12 04:28 UTC: retired; the
failure was a wrapper receipt gate after a correct, cleanly torn-down fixture run; no
GPU fault line, no retained process.
