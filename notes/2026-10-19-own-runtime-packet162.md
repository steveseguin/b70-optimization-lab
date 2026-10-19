# Packet162 — IQ2 lookup CPU research

The current two-card gate/up path reads one grid entry for every eight weights.
That is two 32-bit words in one dependent load message, not two serial loads
for every weight. Signs are already stored inline, and the selected E1 scale
cache does not remove this dependency.

Two new exact integer decoders were tested. The first replaces the lookup with
Boolean logic but needs 1,288 nodes. The second expands a grid index from ten
to eleven bits, then reconstructs the magnitudes using integer combinations.
It adds only 40 bytes per row: **629 MB per rank**, leaving **157 MB** below
rank 1's modeled arena limit. That is a useful memory-fit result, not proof
that startup or the device compiler is ready.

Both reproduce all 1,024 grid entries. GNU and Intel pass the finite full-size
checks and the actual native host kernel's output/status tests, including
invalid routes. Separate tests of intermediate chains and reduction trees
find different NaN payload bytes. Those failures remain in the evidence;
passing final native bytes does not clear the whole strict gate. The compiler
context behind the differences is still unproven. No model output change was
measured, and neither design is called lossless-qualified.

Both also take more CPU time. The smaller encoding takes roughly four to five
times the control in this diagnostic. CPU speed does not predict the GPU gate.
There is no measured device ratio and no supported qualifying speed claim.

**These implementations are closed before device preparation.** A full-shape
CPU harness and a conditional five-minute lane-B micro plan are retained. The
plan requires exact bytes and ≤0.85× device kernel time before a build brief,
25 GB root free space for device work, a real CPU preparation-path probe and
READY written last. It is not a runnable proposal: no READY or ops job was
created, and nothing was queued. A shorter decoder with complete byte parity
is the condition for revisiting the retained eleven-bit representation.

[Packet and source-line analysis](../experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/README.md),
[closeout](../experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/CLOSEOUT.md),
[negative index](../experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/DO-NOT-REPEAT.md),
[CPU evidence](../experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/evidence/cpu-proof.json),
[audit](../experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/evidence/decision.json).

CPU only on steve-b70s, nice 19, CPUs 8–15/24–31, Python `-B`, stdin closed,
4 GiB limit; compilation and synthetic full-shape execution held the shared
ops compiler turn. Peak reported child RSS was 283,036 KiB; six audit tests
pass while correctly retaining the failed candidate gate. No GGUF/full model reads, GPU, services, sudo, settings,
live queue or existing packet/screen/ops edits. Main was fetched; after the
configured pull refused, explicit main fetch confirmed HEAD == origin/main
at `64eb64aae72c1cc2411fbf53f22caab9f49b9175`. Other workers continued committing
on main; their work and existing dirty files were preserved.

## Packet162b — device-speed micro prepared, shared report adapter pending

The owner asked to measure device speed before spending more time on NaNs.
The small diagnostic now builds. It compares the actual production gate/up
kernel with the eleven-bit decoder, using real rows from ten fixed experts
in each of two layers. Candidate rows use about 11 MB per test, with 0.512 MB
extra over the original rows. It records 200 alternating pairs per finite
input case and compares output and status bytes. NaN inputs are reported
separately. It runs no model.

The one-card census ended before any GGUF reads. About 21 MB was then read
on CPU, checking before every expert read that no packet58 unit was active.
Both builds pass. All final CPU bytes match on synthetic and real rows,
including invalid routes and NaN inputs; the old auxiliary NaN failures
remain unresolved. Seven analyzer/report tests and six parser/refusal cases
pass. The analyzer refuses incomplete streams and CPU timing as device proof.

The proposal is fresh, uses card 2 on lane B, keeps the 25 GB disk floor,
and allows a 20-minute cooperative watchdog for an expected five-minute
experiment. The exact binary's preparation probe and temporary-copy queue
plan pass. Shared entry checks pass, with zero gate-identity refusals.

**The required shared report rehearsal cannot accept a standalone micro.**
Its unchanged code supports model-screen and one-card model reports only.
The micro's actual report path passes its own tests, but the shared tool's
failed report result is preserved. Those shared tools are frozen in this
brief, so they were not edited and READY remains false. A shared micro-report
adapter is the remaining handoff requirement. Nothing was queued or run on
a GPU. No speed verdict or final DO-NOT-REPEAT row was invented.

[Micro contract, receipts and reproduction](../experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/MICRO162B.md).
