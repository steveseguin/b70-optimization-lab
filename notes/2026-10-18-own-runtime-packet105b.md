# Packet105b / 106b: reset repair and suffix-heavy validation

CPU-only preparation, two-hour time box. No GPU, service, live queue, sudo or
host setting change is authorized. Builds use nice 19, CPUs 8–15/24–31,
closed stdin, an 8 GiB address-space cap and packet94's serial compiler turn.
The combined new build budget is 250 MB; frozen fixture inputs are linked.

The first `git pull --rebase` refused unrelated dirty orchestration files.
Fetch confirmed HEAD and origin/main both at `de42a7689`. Nothing was stashed,
reverted or staged from another task. All commits use explicit `--only` paths.

The new packet105b copies packet105 and restores rank0's private `active=1`
after importing the verified hidden state, before suffix submissions.
Packet106 already had that repair in both suffix services; packet106b copies
and preserves it. `copy-lineage.json` records the original source hashes.
Original packets, existing screens and existing ops files remain frozen.

Only scheduled views are gated: production and compute head split in 105b;
production, head split and combined head/draft split in 106b. BCS and draft-only
are outside this request. Every selected composition requires all 11 startup
windows, with an individual receipt written immediately after each window.

The suffix microbenchmark compiles and its new proposal passes the real queue
planner on a temporary queue. It runs 4,096 hidden vectors with full-vocabulary
production Q6 head and argmax kernels. At least 2,000 must have suffix winners;
256 cases have exact cross-boundary ties, 768 inject NaN/+Inf/-Inf rows, and
256 batch resets clear the private controls. A negative control must detect
the old skipped-suffix bug. Both complete logit bytes and finite winner payloads
must match; nonfinite rows must refuse output. Synthetic weights make these
stress cases reproducible: this is device operator validation, not a model
speed or quality claim. Device execution remains pending.

First deliverable: `ops/lane-queue/proposed-p105b-micro-B.txt`, under the
own-runtime experiment. Only the coordinator may execute it. Its existing
supervisor retains lane admission, fault review, memory/FD monitoring, graceful
stop and drain. No live queue was installed.

Both host and device binaries compile for 105b. GNU and Intel each pass two
fresh full-vocabulary byte checks and the reset regression (21 cases per run,
six old-code failures). Controller and actual-runtime loader/transfer mocks
pass. Startup found a frozen fixture copy without execute permission; the new
packet now links byte-identical executable frozen inputs, leaving both parents
unchanged. Every-window startup and the 12-prompt smoke proposal are next.

## Twelve-prompt smoke shipped

Both 105b views now pass every startup window (22/22), with individual,
source-bound resumable receipts under `build/startup97e/receipts/`. Production
and compute-head views are sealed. The candidate-only
`ops/lane-queue/proposed-p105b-smoke-B.txt` passes the actual planner on a
temporary queue. It requires the micro's completed zero-mismatch device receipt
before execution, then all twelve cold prompts at 64 tokens with a reset before
each. The known `architecture-tradeoff` token 31 must be 215495, and at least one
target suffix token must be selected. All prompts compare exactly to the oracle.

This milestone is shipped before the combined matrix. Packet106b byte and
controller gates pass; its remaining combined validation and proposals continue.
The new builds link frozen object and fixture inputs without changing their
bytes. This keeps the combined build footprint inside the 250 MB budget.

## Completed CPU handoff

Packet106b's unchanged production runtime passes fresh GNU/Intel byte checks,
the target reset regression, hit/miss controller and combined transfer/reset
mocks. All six rank allocation checks and all 33 startup windows pass. Together
the two copies retain 55 individual source-bound window receipts. The final
audit verifies every receipt and all five view seals. Only `p105_runtime.hpp`
differs among packet105's existing C++ runtime files; packet106's existing C++
runtime files are byte-identical in 106b.

The 106b mock initially tried the intentionally excluded draft-only view.
Its harness now checks the combined view that will actually run. The unused
draft-only selection was not materialized. The incremental build also found
that the parent's rebuilt helper objects were bound through its linked binary,
not listed individually as source inputs; the new receipt pins those immutable
input object bytes explicitly. Neither issue involved a device.

The actual smoke worker loop has CPU protocol tests for all twelve reset/request
pairs and for rejection of the old wrong token. Two tests pass in each packet.
Nine additional 106b tests cover views, memory deltas, changed proposals,
missing smoke, incomplete B evidence and a grid with no improving exact winner.
No final-gate or performance headline is claimed from these tests.

All five proposed files pass the real queue planner on private copies:

| Proposal under `experiments/own-xpu-runtime/ops/lane-queue/` | Jobs | Execution prerequisite |
| --- | ---: | --- |
| `proposed-p105b-micro-B.txt` | 1 | Normal coordinator device admission and fault review |
| `proposed-p105b-smoke-B.txt` | 1 | Exact completed, drained micro with zero mismatches |
| `proposed-p106b-smoke-B.txt` | 1 | Same micro; combined candidate, all twelve prompts and real draft suffix activity |
| `proposed-p105b-B-grid.txt` | 4 | Both complete twelve-prompt smokes and micro |
| `proposed-p105b-A-confirm.txt` | 3 | Both smokes plus complete same-boot exact B grid with a candidate faster than both controls |

The B grid uses 106b's production / head-split / head+draft-split / production.
A chooses the best qualified B winner before each fresh run. Packet105b's own
target-only smoke protects its distinct asynchronous transfer binary. The extra
106b combined smoke ensures that binary is validated before the grid as well.
Plan mode does not bypass these execution refusals.

Final combined new build footprint: **240,850,266 bytes**, below 250,000,000.
The two source/receipt archives are 4,313,023 and 4,591,353 bytes; all 261/269
members were independently re-hashed after archiving, with originals retained.
`RETENTION.md` explains why they are needed and how to restore missing generated
files. Frozen object/fixture inputs remain individually hash-bound links.

Final audits:
[105b](../experiments/own-xpu-runtime/stage2/packet105b-head-split/evidence/final-verification.json),
[106b](../experiments/own-xpu-runtime/stage2/packet106b-draft-split/evidence/final-verification.json).
The first copy/fix milestone is `5a7ca1e3b`; micro preparation shipped in
`857518118`, and the complete target smoke shipped in `369cf4627`, before the
combined matrix was finished. Each milestone was pushed immediately.

**Device micro, model smokes, grids, residency, repeats and speed are still
pending coordinator execution.** No GPU, service, sudo, live queue, existing
packet, existing screen, power/memory/swap/page-cache setting, or reboot was
used or changed by this task. No process was killed.
