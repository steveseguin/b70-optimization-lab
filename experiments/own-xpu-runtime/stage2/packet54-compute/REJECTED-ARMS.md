# Rejected preparation arms

These are CPU observations, not device speed results. All candidate code stays
in `hc_ffn.hpp`; original helper tests are in `rejected_hc_ffn_test.hpp`.
No rejected arm appears in the eligible manifest or decision parser.

## FFN combine-vector4

`evidence-cpu/full-diagnostic-2/receipt.json` records eleven ordinary passes
followed by the actual compiled-production mismatch at output byte0: production
`0xc0`, candidate `0xc1` (BF16 `0x7fc0` versus `0x7fc1`).
To reproduce the failing fixture in a separate unsealed diagnostic: build the
packet's normal layer4 fixture, restore snapshot0, then set the first four
residuals in each 2560-element stream to alternating `0x7fc1`/`0xffc5` and
all branch and injection BF16 inputs to `0x7fc3`. Snapshot that state. Execute
the unchanged `ffn.combine` production submission; restore the poisoned
snapshot and execute `p54hc::submit_combine`. Compare all output/control bytes.
The scalar noinline fallback is the failed candidate version retained here.

## Norm-subgroup128 and norm-mix-vector4

`evidence-cpu/full-diagnostic-3/receipt.json` records ten ordinary passes then
an actual compiled-production mismatch at norm output byte4098: production
`0xc1`, candidate `0xc5` (BF16 `0x7fc1` versus `0x7fc5`).
Use the normal layer4 snapshot0, isolate `hc.a.norm`, set BF16 input33 to
`0x7fc1` and input2049 to `0xffc5`, and snapshot. Execute actual production;
restore that snapshot and execute `p54hc::submit_norm`. Compare output,
1280-byte partial buffer and all three controls. The uniform nonfinite
fallback to the specialised stage1 body is already in this failed version.
Both HC proposals include that norm change, so both are closed. The final
`mix-vector4` arm keeps production norm and inject and has its own successful
actual-submission exceptional check.

Identical source expressions are insufficient to prove compiled NaN operand
selection. No value repair, canonicalization, approximate comparison or
revised model oracle was used to accept these arms.
