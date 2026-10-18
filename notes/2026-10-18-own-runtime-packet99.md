# Packet99: exact IQ2 grid lookup

CPU-only preparation from packet97. The initial `git pull --rebase` was refused
because coordinator-owned tracked files are dirty. `git fetch origin main`
confirmed HEAD already matched origin/main; those files were left untouched.

The source inspection found one dependent IQ2 grid lookup per eight weights,
not a second sign-table lookup. Signs are eight inline bits in the weight code.
Down is IQ4_NL and already uses register constants for its sixteen levels.

[Preregistered candidates and gates](../experiments/own-xpu-runtime/stage2/packet99-iq2-grid/PREREGISTRATION.md):
full and compact SLM grids, compact constant grid, and an IQ4 byte-pair SLM
table. No device, service, live queue, memory-block fence or host setting has
been touched. Existing dirty files and all frozen packet trees remain intact.

## Result

Three IQ2 mechanisms and their half-cache forms pass exact bytes under GNU and
Intel, twice each. All six have zero spills in linked offline BMG assembly.
The full-table SLM path changes the actual dependent reads from global d32x2
to SLM d32x2; compact SLM uses d32. Compact global retains the global address
space while shrinking the table from 8 KiB to 2 KiB. No FP32 sum moves.

Production and all seven built candidates pass 28 cases per run, including
118,784 raw FP32 chain checks and 3,456 tree checks. The full-size engine test
passes all 16 view/rank initializations, actual arena admission, 32 deliberately
bad extents/alignments and five malformed selections. The tightest tested arena
headroom is 630,519,094 bytes on rank1 with half-cache; the independent 1.5 GB
VRAM margin rule also passes. This is numerical device-allocation admission,
not a host allocation of the model.

The down alternative is exact but fails the no-spill gate: 1,664 spill bytes
and 52 scratch messages. It is retained and closed, with no micro or screen
entry. Its production format is IQ4_NL, whose level bank is already in register
constants. [Detailed diagnosis and addressing](../experiments/own-xpu-runtime/stage2/packet99-iq2-grid/DIAGNOSIS.md).

The review also corrected the historical interpretation: packet52 already used
a 2 KiB compact grid, despite an old note saying 8 KiB. Packet99 tests a different
exact schedule and packed-word layout against packet86's new latency evidence;
it does not claim a new encoding or more output rows per table fill.

## Prepared next step

Seven views are sealed. The single-card microbenchmark uses actual full-size
gate/up operations and a 512-expert bank. Outputs/status are poisoned before
correctness checks. Forty alternating pairs must show at least 15% less kernel
time overall and in both orders. Only qualified candidates can enter separate
B control/candidate/control brackets, then A confirmations with unchanged
acceptance and exact packet49 outputs. **A decides; records run on A.**

All 13 proposals passed planning on a temporary queue. An initial invalid `+`
in a systemd job name was corrected and its failed planning record retained.
No live entry was added. The build is about 165 MB, below 500 MB; fixture scratch
was archived and removed after each gate. The shared wrapper's 80 tests and 20
focused tests pass. [Coordinator commands and proposals](../experiments/own-xpu-runtime/stage2/packet99-iq2-grid/WINDOW.md).

Device parity, kernel speed and whole-model speed remain unmeasured. The supplied
0.58 ms limiter difference is diagnostic evidence, not a promoted saving.
