# Packet125 miss transport — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can an exact miss path beat packet58's zero-copy useful rate by at least 1.5×
on a B70? The target is the one-card Unsloth UD-IQ3_XXS quantized compressed
version, packet49 arithmetic and BF16 KV, target-only. October 18 CPU work
uses frozen packet58j kernels, packet58k receipts and packet100b accepted route
IDs. The proposed device micro uses lane B/card2, synthetic packed values and
simulated 18 GB position-end cache masks; it loads no model.

## Outcome

**Prepared, device decision pending.** Both fresh-job plans pass. Twelve CPU
policy tests pass; GNU and Intel each pass 24 arithmetic/layout checks twice,
with the same transcript digest. The device image compiles and the drain check
passes. No device bandwidth, overlap, packet49 full-model equality or speed
verdict is claimed. No engine copy or whole-host screen is prepared before the
same candidate clears the exact-byte and 1.5× gates in both processes.

## What worked

Original-byte receipts reproduce 33.0051 misses / 65.456571 MB per charged token.
All four external slot links report 16 GT/s ×16. The harness compares six exact
alternatives against the original host-pointer kernels, checks every delivered
copy byte and every expert output/status byte, and includes route readback in
copy-path wall time. All 384 cases, including zero-miss cases, remain charged.
The separate post-initial gate prevents initial-cache cases hiding a sparse
miss regression. Explicit copy dependencies permit DOWN copies to overlap
current-layer gate/up; unknown future routes are never guessed.

## What failed or remains uncertain

No path has qualified on a device. The old receipts did not save isolated
PCIe-read/compute times or one-card route IDs. Simulated masks on real accepted
routes cannot fill those evidence gaps. CPU preparation exposed and fixed
header-owner identity/include duplication before execution. Initial compile
success and later corrected code remain in focused Git commits; no GPU fault
occurred here. Real cache behavior, driver overhead, scheduling and host-memory
contention remain device questions. Kernel-time improvements cannot remove the
known host lookup page-fault cost by assumption.

## Evidence and patches

- [Accounting](evidence/accounting.json), [read-only PCIe path](evidence/pcie-links.json), [reproducer](accounting.py).
- [Native source](microbench.cpp), [frozen-kernel extraction](iq3_kernel.hpp), [preregistration](preregistration.json).
- [CPU byte gates](evidence/cpu-bytes.json), [policy tests](evidence/cpu-tests.json), [drain check](evidence/drain-check.json).
- [Build/source seal](evidence/microbench-build.json), [temporary plans](evidence/micro-queue-plan.json), [proposal](../../ops/lane-queue/proposed-p125-micro-B.txt).
- [Qualification](evidence/qualification.json) currently has zero measurements and forbids integration.

The sub-200 MB ignored build can be regenerated with the README commands.
Small route payloads and their hashes are tracked; raw packet58 receipts remain
in packet58n's hash-checked archives. No model bytes are copied or downloaded.

## When to revisit

The coordinator schedules both proposed B jobs with normal lane, memory,
fault and drain admission. A clean loss closes this transport arm without a
screen. A winning candidate permits a new copied 58j/58k engine, complete
one-card chain CPU gates and seals, then a separately proposed whole-host
card0 bracket. That bracket still needs about 118 GB host admission and one
model load per arm; no lane-B model window is substituted.
