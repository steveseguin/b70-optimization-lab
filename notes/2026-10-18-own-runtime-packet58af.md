# Packet58af — one-card measurement job ready on CPU

Packet58af completes packet58ae's missing measurement code. The private copy
now measures resident and miss work separately for one rotating layer per
token. It records miss bytes, miss-kernel time, the delay before dependent
work can continue, and the resident-compute interval available to a future
transfer. The existing cache-publication split is retained.

The miss delay includes arithmetic and the gap between launches; it is not a
hardware counter for time waiting on memory. The overlap interval is an
available window, not proof that a transfer already overlaps. These meanings
and the exact rules for packet147 ranks 2, 4 and 5 are in the
[packet README](../experiments/own-xpu-runtime/stage2/packet58af-onecard-measure/README.md)
and [analyzer](../experiments/own-xpu-runtime/stage2/packet58af-onecard-measure/analyze.py).
M2 still needs a complete measured cycle with its draft and cache costs.

The combined job uses one model load and five views: off, publication on,
off, resident/miss measurement on, off. Each view uses twelve prompts with a
64-token cap and checks every token against packet49 `iq3-p49-split32-v1`.
Both on views must show less than 2% overhead against both warm off controls;
control drift above 2% invalidates the measurement. No device has established
that overhead result yet.

CPU validation passed: GNU and Intel/SYCL builds, exact parent binary relinks,
96 synthetic partition byte cases across compilers/repeats, production
subgroup coverage, two miniature five-view repeats, wrong-oracle refusal,
full-size synthetic startup and reset, two real native parser paths with
eight negative cases, all three intercepted queue-to-native paths, 21 analyzer
and readiness tests, and the shared `ops/rehearse_entry.py --report` check.
The temporary queue plan and pin guard also pass. Receipts are in the packet's
`evidence/` directory.

The launch rehearsal caught a missing inherited fault-pattern source and a
stale admission seal after copying paths. Both are fixed only in this copy.
The measured admission policy's numbers are unchanged; the relocation check
records that only literal packet paths changed. Historical parent hash maps
are retained under `lineage/`, separate from this packet's current build pins.

The [single proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58af-measure-A.txt)
remains unqueued. It requires card 0, lane A, the whole host and the existing
packet58ab hold. The active budget is at most 900 seconds, including K1 checks
and drain gaps. Expiry requests graceful termination; safe cleanup may extend
past that boundary. There is no hard kill or retry.

The [readiness marker](../experiments/own-xpu-runtime/stage2/packet58af-onecard-measure/READY-FOR-DEVICE.json)
is written last. It binds the build, proposal and successful temporary plan.
It means ready to measure on the device, not that device overhead, quality or
speed has passed. The 29.259764 one-card record is unchanged.

All preparation was CPU-only, nice19 on cores 8–15/24–31, with Python -B and
closed stdin for checks and compiler children. Every compiler/link turn used
`ops/compile_turn.py` and waited behind the live timing hold. No model or
full-shape payload was read. The retained build is 77.5 MB, below the 200 MB
cap; root stayed above 25 GB. Compile and test memory stayed below 4 GiB.
No GPU, service, sudo, host setting, existing packet, shared ops file or live
queue was changed. The only ops addition is the new proposal. Unrelated dirty
orchestration work is excluded from the commit.

The copied 12.2 MB source archive is intentional rebuild evidence, with its
original hash and restoration instructions retained. The new binaries remain
ignored. The next action is the coordinator's single proposed measurement
inside the existing hold, followed by its strict overhead and exact-output
decision; preparation itself starts no device job.
