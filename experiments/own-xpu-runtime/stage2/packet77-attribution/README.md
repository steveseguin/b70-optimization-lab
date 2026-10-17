# Packet 77: attribute the packet 70 record selection

CPU preparation complete. **No packet77 device measurements yet.** This measures
the record's exact selection: packet64 `1-draft-hc-batch`, packet65
`experts=wide64`, placement 1 (24/24 target layers, draft on rank 1), unchanged
target arithmetic `iq3-p49-split32-v1` and full BF16 KV. The 54.162 tok/s record
is historical packet70 evidence, not a result of this diagnostic screen.

One loaded pair runs incident64, twelve 128-token uninstrumented controls,
then the same twelve instrumented requests. Every request resets numerical
state and checks every emitted token against packet49. RESET token 1 disables
event recording; token 0 enables it. This repeated suite is diagnostic only.
Both arms use one binary and the same selection and weights.

The recorder follows packet64, with packet69's rank-1 final norm, full target
head and argmax labels. It observes generated indices 9–16, representative
layers 22/23 on rank 0 and 24/27 on rank 1, draft work, transfers, and first/last
layer endpoints. It adds no kernels or synchronization barriers. The
[source delta](instrumentation.patch) replaces packet70's expert-only recorder;
all numerical kernel objects are reused from packet65 by hash. Both incremental
builds and the CPU reference/repeat/reset gates pass. Small transfers with equal
start/end timestamps are accepted; zero-duration compute events are rejected.

## Shared wrapper and placement

[run_screen.py](run_screen.py) imports the original, hash-pinned
[`screen/v4-lanes`](../screen/v4-lanes/README.md), including the admission repair
at `d5b060769`. No shared source or private wrapper copy was edited. Its sole
adapter hook supplies [worker.py](worker.py) instead of the default single-suite
worker. The shared wrapper retains its real lane predicate, placement and memory
checks, closed environment, fault supervision, holds, teardown, and lease release.
The paired worker follows v4's drain/refusal handling and stages both arms before
draining. Reports run after both lane locks are released. A reporting failure is
recorded separately and never creates a device-fault latch.

Shared v4 recognizes audited 24/24 views only inside a directory named
`packet64-record-bundle/selections`. Therefore the new view uses the explicit
packet-local compatibility namespace
[`compat/packet64-record-bundle/selections/1-draft-hc-batch-wide64`](compat/packet64-record-bundle/selections/1-draft-hc-batch-wide64).
It is packet77, not a replacement for any packet64 files. The full placement
audit binds this binary, dispatch and engine sources. The unmodified shared
predicate admits it; no placement check is overridden. The actual worker
recomputes and verifies the same sealed identity before load.

## CPU evidence

- [Build](build-device-receipt.json): GNU host and Intel device-target builds;
  only `entry-main.o` rebuilt in each. No device binary executed. Maximum
  reported compiler child RSS: 726,656 KiB; address-space limit: 6 GiB.
- [Tiny reference and repeats](evidence/cpu-gates.json): 96 target fixtures,
  24 tokens, draft proposals and final state match the packet65 parent binary
  under packet70's exact selection. Control plus two fresh attribution runs.
- [One-load reset gate](evidence/reset-gate.json): control / attribution /
  control preserve all 96 target fixtures and 24 tokens per request.
- [Full production shape](evidence/fullshape.json): real allocation,
  preparation, snapshot, draft post-load and teardown code with a mock backend;
  no weights or model computation. Rank 0 prepares 677 commands; rank 1 prepares
  670, then allocates 104 draft objects. Host backing is approximately 4.2 MB
  per rank. [Real memory admission](evidence/fullshape-admission.json) passes.
- [Eleven packet checks](evidence/python-tests.log), including closed-environment
  worker imports, selection constraints, true lane-B admission, 25-request
  fake-transport flow, multi-event aggregation and zero-duration transfer rules.
- [69 shared v4 checks](evidence/shared-v4-tests.log): admission, worker,
  cancellation/drain, release-before-report and reporting failures.
- [Report software replay](evidence/report-fixture.json): full table rendering
  using historical packet69 events and temporary synthetic receipt identities.
  No fixture timing is retained as a packet77 measurement; original files stay
  unchanged. Mismatched binary identity is refused.
- [Screen plan](evidence/screen-plan.json) and
  [temporary queue plan](evidence/queue-plan.json): real lane-B `screen`,
  supported placement 1, 3,600-second watchdog, no device or service started.

## Reports and next levers

[report.py](report.py) validates the complete paired suite and current selection/
binary before generating JSON and Markdown. It sums all events in each site
call before taking its median. [Packet72's byte formulas](byte_formulas.py) are
retained verbatim and checked by AST equality. The pinned header census supplies
actual tensor types: Q6_K/Q8_0 expanded code/scale bytes, packed expert bytes,
and distinct activation/state/scratch reads. Writes remain separate.

For each rank, the table reports class time per half, effective read GB/s,
and headroom versus 555 GB/s. The ranking is
`occurrences × (measured call µs − useful read bytes / 555000)`. Common sites
combine 18 GDN and 6 QSA occurrences once. These are sample-based half estimates,
not measurements of all layers or promised model speedups. Rank 0 corrected
work is miss-conditioned. Ranks and speculative work are not added together.
Raw instrumentation timings feed the rates; paired overhead ratios are shown
separately. Effective reads are not physical DRAM counters, and 555 GB/s is a
reference, not a guaranteed compute floor.

Rank 1's head, final norm/merge, argmax, transfers and signed residual are split
within each complete half command. Residual includes host submission, waits,
gaps and unsampled work; it is not GPU idle and gets no bandwidth number.
The [pending lever table](LEVERS.md) deliberately contains no packet77 timings.

[Coordinator handoff](WINDOW.md), [retention/rebuild](RETENTION.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md).
