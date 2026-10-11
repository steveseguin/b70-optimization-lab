# Round 4 CPU preparation closeout

<!-- campaign-closeout -->

Question: can a specialized routed expert launch with within-group split-K
and ordered weighted reduction improve the IQ3 expert path? Identity:
Unsloth UD-IQ3_XXS, pinned census and round2/3 receipts in [dispatch.json](dispatch.json).

CPU preparation passes, including a SYCL build, CPU oracle comparisons and
negative timing-protocol tests. Device outcomes remain pending. No device
binary, server or unit ran in this task. [README](README.md) records corrected
shapes/counts, group counts, prediction assumptions and the two device commands.

Retained mechanism: gate/up share a device route table and activation;
four subgroups reduce locally with the fixed two-level tree, avoiding a global
reduction pass. Down and the ordered BF16-down/FP32-weight epilogue are separate
owned launches. The timing protocol requires all three stages and two fresh
owners per representative whole-layer shape, including a full head.

Uncertainty: earlier kernels already had thousands of work-groups. More groups
alone need not improve occupancy. The old global split4 expert candidates were
slower; this local-reduction variant needs direct evidence. Arithmetic matches
its registered tree, not yet the full target model. SiLU/product, recurrence,
attention and host lookup mapping remain outside this GEMV-only packet.

Evidence: [source](kernels.cpp), [reference](reference.hpp),
[build receipt](build-receipt.json), [analysis](analysis.json),
[device gate](tests/device_window.py), [timing](tests/device_timing.py).
All CPU scratch is reproducible and removed by default. Old packets and
siblings' modifications are preserved. No model download occurred.

Next: coordinator exactness, then both fresh-owner timing passes. Compare whole
expert blocks and full layer spans, preserve regressions, and only then choose
between the unsplit and split4 candidate. A packet-level speed gain never
substitutes for full-model output and realistic-suite gates.
