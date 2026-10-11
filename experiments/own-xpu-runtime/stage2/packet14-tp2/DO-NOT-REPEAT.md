# Packet 14 negative index

| Arm | Outcome | Evidence / revisit condition |
| --- | --- | --- |
| Sum experts locally by expert ID, then FP32 A+B | Rejected: deterministic reassociation changes the frozen serial slot sum | `host_tests.cpp` cancellation witness, `reference.hpp`, TWO-CARD-TP.md; require a proof preserving the existing tree |
| Treat one 10 KiB round trip as complete layer traffic | Rejected: downstream projections/routing depend on earlier gathers | `placement.json`, README; revisit after a dependency-correct fused gather design |
| Divide the tiny model's three GDN heads into equal halves | CPU localization found missed head/state | Fixed 1+2 complete-head partition, original mini-model all-buffer checks |
| Treat GGUF dimensions as already row-major in the coverage exporter | Metadata test rejected row alignment | Export original fastest-first dimensions; `read_directory` performs the only reversal |
