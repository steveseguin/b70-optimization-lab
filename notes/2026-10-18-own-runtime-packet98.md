# Packet 98 — one model load per screen bracket

CPU-only preparation, started October 18 UTC. The initial pull refused because
other work has tracked edits. A fetch confirmed local HEAD equals origin/main;
those edits were left untouched. Root had 15.6 GB free. This work has a 1 GB
build ceiling, 12 GB free-space floor, 8 GiB process limit and serial compiler
turns through packet94's helper.

V5 is a separate copy of v4. Earlier packet34 replay restrictions were read:
no arithmetic change, no synthetic/replay result as a benchmark, no retry of
failed native teardown. The existing native engine has no selection-switch
command; v5 therefore needs a native boundary command and CPU startup tests,
not merely a Python loop. Parent kernels remain frozen.

Planned milestones: native switch/reset and state-machine tests; full-shape CPU
startup/admission and seals; two-view A/A smoke and five-view A/B/A/B/A queue
proposals checked in a temporary copy. No GPU, service or model will run here.
Measured device wall-time savings are pending the coordinator's smoke; the
review14 timing figures are planning inputs, not new measurements.

## Native and reset milestone

Both native entry builds passed, using packet82b's unchanged kernel objects.
The production shape test ran five alternating views per rank through actual
load allocation, capture, draft construction, switch and reset, with only the
backend/payload mocked. It checked 5,320 reset extents on rank0 and 5,445 on rank1,
including recurrent spare banks and draft state. The control's captured arguments
matched fresh startup after returning from the candidate. Unsupported packed
head storage refused before mutation.

The real miniature CPU backend dirtied every mutable allocation, then checked
complete byte hashes against a clean reset. Both fresh repeats on each rank
passed: 2,990 allocation comparisons, with immutable weight bytes unchanged and
attempted weight writes refused. Real rank IPC also passed two fresh five-view
brackets and matched both the parent binary and v5 fresh-process token outputs.
These miniature inputs are diagnostic fixtures, not the packet49 model suite.

The 106 inherited Python checks and ten new bracket checks pass. New coverage
includes failure in every view, stale arena identity, layout/draft refusal, cold
receipts, one load/one drain after a view failure, memory refusal before lease,
and release after a prelaunch memory race. GPU use remains untested.

Retained evidence: `experiments/own-xpu-runtime/stage2/screen/v5-bracket/evidence/`.
CPU fixture wall times are recorded there; they are not model-load savings.
Device wall-time savings remain unmeasured because this task forbids device use.

## Final CPU seal and coordinator handoff

The final wrapper gate passed **119 tests**. Native and wrapper seals verify.
The two proposed lane-B jobs both pass the real queue planner in a temporary
copy. V4's 36 copied top-level file hashes still match (the exact count is in
`evidence/frozen-v4-check.json`). No live queue was changed. The build is
83,668,587 bytes, below the 1 GB ceiling; no new tracked artifact reaches 1 MiB.
The compiler receipt reports 730,400 KiB peak child RSS. Root free was above
18 GB at final verification.

Prepared proposals, relative to `experiments/own-xpu-runtime/`:

- `ops/lane-queue/proposed-p98-smoke-B.txt`: packet84 production versus itself,
  two views. All thirteen checks per view and at most 3% class-balanced timing
  difference are required.
- `ops/lane-queue/proposed-p98-bracket-B.txt`: packet91 control / route-fast plus
  rec-both-plus / control / candidate / control. The entry checks the successful
  same-wrapper/same-binary smoke before any device admission.

The report adapter preserves v4's request/summary fields, rechecks every oracle
token, and labels the shared lifetime. A failed CPU report happens after release
and cannot create a device-fault latch. Candidate comparisons include all three
controls, not just a favorable endpoint. The prior wrapper seal and its byte
fixtures/log are retained in `evidence/seal-attempt1/`; the final seal adds three
report-adapter tests (including inexact output and excessive A/A timing drift).

### Wall-time accounting

**Measured device wall-time savings: not measured.** This task permits CPU work
only, so neither proposed device job was run. The actual native CPU message-path
fixtures took 11.805 and 11.806 seconds for five views. Individual fresh miniature
references took about 2.36–2.40 seconds. These are tiny synthetic CPU diagnostics,
not the loaded model and not a measured model speedup. No saving is inferred from
them or from the review14 estimates. The future `bracket-summary.json` records
actual bracket wall time and leaves `device_wall_savings_seconds=null` until a
matched measured v4 wall reference exists. The structural saving is one target
and one draft load, and one teardown, for all views; its device time is pending.

[Implementation and commands](../experiments/own-xpu-runtime/stage2/screen/v5-bracket/README.md),
[CPU closeout](../experiments/own-xpu-runtime/stage2/screen/v5-bracket/CPU-PREPARATION-CLOSEOUT.md).
