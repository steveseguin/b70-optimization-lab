# Resolution reference 101c namespace

CPU-only successor after 101b's reference-gate tag-convention refusal. The
original plan folder and sealed 101/101b packets are unchanged. This plan
repeats the same finite experiment under fresh names and indices; it does not
reuse failed-run artifacts as qualification.

The generator differs from the original in exactly two constants: prefix
`resolution-ref101c-20261007` and index base `99901000`. The full canonical plan
is independently reconstructed by the original generator with only those two
values substituted. Fixtures, prompts, seeds, dimensions, all numerical graph
options, ordering, limits and qualification identity are unchanged.

All seven setup names also use the new prefix; setup capture index is
`99901030`. The 32 request names and 26 indexed submissions are disjoint from
both sealed 101 and 101b namespaces. This bounded comparison does not replace
the client's actual output-path collision checks.

`namespace-validation.json` records hashes, full names/indices and prior sealed
packet bindings. `test_plan_reference.py` checks exact reconstruction; runtime
`test_schedule.py` checks all setup/request collisions against both sealed
packets. No runtime packet was built or server/endpoint used during preparation.

Plan SHA: `3281a1eb45d210ac75f2a07c415cf2f99b2b9308651456587aa483e2596d65e2`.
Setup schedule SHA: `9f79ee01c507d46c106f9e0037eda772a20a717a49d3de03a2aca06785517441`.
