# Packet77: refresh attribution for the wide64 record

CPU preparation is complete. The new screen measures packet70's actual record
selection: `1-draft-hc-batch` plus `experts=wide64`, placement 1, 24/24 layers
with the draft on rank 1. It keeps the target arithmetic, weights and BF16 KV.
No GPU, service, sudo, host-setting change or model payload access ran here.
No live queue was changed. Current class costs and the next-lever ranking remain
unmeasured until the coordinator runs the proposed lane-B job.

The [packet](../experiments/own-xpu-runtime/stage2/packet77-attribution/README.md)
runs an uninstrumented control and an instrumented arm in one load. It adds the
rank-1 head, final norm and argmax split to packet64's layer/draft attribution.
The report uses packet72's exact byte formulas and actual tensor types, then
ranks each rank's classes by remaining time above the 555 GB/s useful-read
reference times occurrences. It shows the instrumentation overhead separately.
Old packet64 expert rates are not presented as current wide64 rates; historical
packet69 events were used only to test report software in temporary fixtures.

The shared v4 wrapper is imported and hash-pinned, including admission repair
`d5b060769`. Only its workload-command hook selects the new paired worker.
The shared admission, supervision and release rules remain unchanged. Its
legacy 24/24 audit predicate requires a `packet64-record-bundle/selections`
directory name, so the audited selection uses that compatibility namespace
inside packet77. This is explicit in the packet README; no parent file or
placement predicate was edited. Reports run after the shared wrapper releases
both lane locks.

Both engine builds pass. The CPU reference, two fresh instrumented repeats and
one-load reset check match tokens, target fixtures and draft state. Full-shape
mock allocation passes through actual post-load setup and the real memory
admission predicate. Eleven packet checks and 69 focused shared-wrapper checks
pass. The worker imports in its closed environment; the real sealed selection
consumer, screen `--plan`, report rendering, and temporary queue plan pass.
The build uses about 135 MB of local artifacts; measured compiler child RSS
peaked at 726,656 KiB under a 6 GiB address-space cap. Compiles were serial.

[Final CPU evidence](../experiments/own-xpu-runtime/stage2/packet77-attribution/evidence/final-check.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet77-attribution/CPU-PREPARATION-CLOSEOUT.md),
[pending lever table](../experiments/own-xpu-runtime/stage2/packet77-attribution/LEVERS.md).

The coordinator's next step is the
[proposed lane-B line](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p77-B.txt),
already planned on a temporary queue copy. Expected device work is about seven
minutes; the cooperative watchdog is 3,600 seconds. The complete command,
fresh output path and CPU report recovery are in the
[handoff](../experiments/own-xpu-runtime/stage2/packet77-attribution/WINDOW.md).
This is an attribution screen, never a performance record or submission.

The requested opening `git pull --rebase` refused because packet75 had live
uncommitted work. Fetch showed HEAD already equal to remote main at that point.
Those edits were preserved; packet75 committed independently during this task.
Only packet77, this note, its proposed queue file and the current-state pointer
are included in this commit. No other process was stopped.

## Device result (coordinator, 2026-10-17 21:56–22:01 UTC, lane B via lane-queue)

The device screen passed (`window.json` passed; v4 released the lane before reporting, so there was no stale marker or latch). The paired report then failed with `KeyError 'binary_sha256'`: `report.py` globbed `*/*/receipt.json`, which also matched rank receipts. The coordinator restricted it to the `control`/`attribution` arm receipts and regenerated the report from the retained raw evidence: `screen/v4-lanes/evidence/packet77-attribution-B-a/run/attribution-summary.{json,md}`.

**Current line (packet 70: wide64), per half, headroom vs 555 GB/s:**

| Rank | Class | ms/half | Read GB/s | Headroom (ms) |
|---|---|---:|---:|---:|
| 0 | `expsgate` | 1.48 | 171 | 1.02 |
| 0 | `expsdown` | 1.25 | 177 | 0.85 |
| 0 | `gdn.recurrence` | 0.65 | 44 | 0.59 |
| 0 | `route` | 0.47 | 0.22 | 0.47 |
| 0 | `hc.f.gate` / `hc.a.gate` | 0.60 each | 149 | 0.44 each |
| 0 | `hc.a.norm` / `hc.f.norm` | 0.19 each | about 8 | 0.18 each |
| 0 | router | 0.53 | 423 | 0.13 |
| 1 | same pattern | — | — | — |
| 1 | `target_head` | 1.40 | 566 | at the limit |

**Next levers:**
- latency-bound small kernels (`route` top-k about 19.6 µs per layer; HC norms about 7.8 µs each per layer);
- `hc-wide` (packet 73, +0.98% on lane A) is pending lane-B confirmation;
- experts at about 31% of reference likely dequant-ALU bound (packet 73's experts2 variants lost).
