# Focused CPU proof result

Root executed the frozen strict-FP GNU proof once. Receipt `evidence/cpu-proof.json` SHA256 `2693d6e3c0c5fd29fb4780a7fcd79c5f274ede0d5f80999e78e0c49ec6a78777` reports PASS:223,685 exact checks,42 refusals,116 site admissions and three safe Host owners. The build binds37 dependencies and retains5,056,973 bytes.

The proof checks the decoder/loop change against the original scalar implementation, including independently varied exceptional block scale/minimum halves, ordered FP32 lanes, the adjacent SG32 tree, final BF16 bytes, and actual Host capture/live bindings. Host events are simulated. There is no native qualification or performance result yet. The historical source-preparation README remains unchanged; this additive result records the later execution.
