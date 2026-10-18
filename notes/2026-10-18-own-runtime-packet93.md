# Packet93: new packed target-head unpack mechanisms

## Diagnosis milestone

Packet74 already removed staging barriers. Its remaining costs include repeated
code-plane loads, repair of alternating two-byte block alignment, runtime scale
conversion and scalar extraction. Production dispatch is p33 WG32, whereas
packet74 used WG256. Register pressure and occupancy are hypotheses until an
offline dump or device evidence measures them. Its retained microbenchmark
receipt is build-only, not measured timing.

[Source diagnosis](../experiments/own-xpu-runtime/stage2/packet93-packed-head2/DIAGNOSIS.md)
preregisters word-parallel extraction and a reversible 210-byte plane layout.
Both keep production FP32 products, additions and SG32 reduction order. The
production expanded path remains the default. Device work is proposed only;
a candidate must take at most 85% of production kernel time in the full-shape
alternating microbenchmark before either screen direction may run.

Preparation is CPU-only on steve-b70s, nice19, cores8-15,24-31, stdin closed,
8 GiB process address-space ceiling, one compiler using the shared turn lock.
Root started at18 GB free; stop below12 GB; packet build limit1 GB. Existing
packets, screen wrappers and live operations are frozen. The required pull
refused unrelated dirty running-chain files; fetch found HEAD=origin/main, so
nothing was stashed or reset. No GPU, service, sudo or host settings changed.

The packed target saves317,849,600 allocated bytes, but the unchanged draft
needs a new308,904,960-byte expanded prefix (production shares its target).
Net rank1 allocation saving is8,944,640 bytes; rank0 is unchanged. Traffic
savings and allocation savings are distinct. All speed estimates are unmeasured.

## CPU preparation complete

Two selectable head paths plus production are built and sealed from copied
packet84 sources. The plane path extracts four code bytes per word operation.
The transposed path reversibly rearranges the same 210-byte blocks into separate
planes, eliminating duplicate per-lane code reads and alternating block repair.
The default remains expanded production; draft format/arithmetic stay expanded.

Offline BMG-G31 assembly counts production/packet74/plane/transpose at
234/381/366/314 static instructions and 8/11/11/9 load sites. All use 128 configured
GRFs without observed scratch messages. Those are compiler observations, not
measured bandwidth, occupancy or speed. [Assembly evidence](../experiments/own-xpu-runtime/stage2/packet93-packed-head2/evidence/offline/report.json).

GNU and Intel each pass two fresh runs of all three views, 32 cases per run:
multiple rows, both raw alignment phases, FP32 decoded values, every lane sum
and reduction level, BF16 logits, argmax and reversible storage. A 4100-block
fixture covers the 4096-block loader scatter boundary and remainder. All six
full-size startup/admission paths pass, including actual target allocation
and bound kernel, separate draft prefix, six allocation refusals, five bad
selection refusals and fourteen unsupported-mode refusals. The unchanged
30 GiB arena leaves 954,036,534 bytes on candidate rank1. Device residency remains
unmeasured. [CPU evidence](../experiments/own-xpu-runtime/stage2/packet93-packed-head2/README.md).

Review fixed an inherited draft-memory receipt that incorrectly called the
packed target shared with the draft. The corrected predicate is verified by
full-size startup. Initial CPU preparation also corrected a test-only demangled
template name and the standalone microbenchmark's copied owner ABI/helper.
The coordinator updated the shared compiler-turn scheduling policy during work;
the build and byte fixtures were rerun against that retained policy before
resealing. No frozen runtime source was changed by packet93.

Both engine builds, the actual-operation microbenchmark build, 102 Python tests,
three seals, all four direction/lane screen plans and five temporary queue
plans pass. Build logical size is 141,911,162 bytes; maximum compiler child RSS
is 732,556 KiB. Fixture run scratch was removed after retaining its raw proof.
Root remained above the 12 GiB floor (about 17.8 GB free at final review).

The new micro proposal opens only physical card 2 on lane B. It compares the
full 248,320×2,560 head with 40 alternating pairs per candidate and per-kernel
event timing. Candidate median time and both order medians must be ≤85% of
production. A clean, drained, hash-bound window is required. Only qualifiers
can enter B-grid/A-confirm or its reverse; every engine screen uses the original
pinned shared v4 wrapper and its first-prompt exactness smoke. Legacy record
and submission consumers refuse the new head selections.

[Coordinator handoff and all five proposed files](../experiments/own-xpu-runtime/stage2/packet93-packed-head2/WINDOW.md).
No GPU, service, sudo, live queue or host settings were touched. Device quality
and speed are pending; no candidate is adopted and no performance is promoted.
