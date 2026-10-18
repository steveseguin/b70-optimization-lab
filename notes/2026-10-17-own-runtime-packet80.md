# Packet80 combined bundle — October 17

The new packet composes packet75's chain with packet76 ordered host cleanup,
packet78 route/norm kernels and packet79 rank0 draft placement. Existing packet,
screen and ops trees are frozen. Work is CPU-only; no services, GPU execution,
host settings, sudo or reboot. The requested note is the sole file outside the
two new folders edited for this task; CURRENT.md stays untouched under that
scope restriction.

Initial git pull --rebase refused because active packet70/75 report files were
dirty. Fetch showed HEAD and origin/main identical (0/0), so nothing was stashed
or overwritten. Other active work is preserved. Root had22GB free. Builds run
nice19, affinity8-15,24-31, closed stdin, an8GiB address-space cap and serial
compilation. No model payload is read by full-shape mocks.

Milestone1: GNU host and Intel SYCL builds pass. Packet80 has16 independent
host/route/norm/HC configurations and four placements; experts=wide64 and
dense=production. Ordered retirement remains rank1-only. Rank0's draft uses
exactly91,392 expanded Q6 head rows. Target arithmetic and packet49 oracle are
unchanged. Exact operator checks, full-shape post-load memory census, native
reverse-handoff and selection-consumer checks are in progress. This is not yet
a ready chain or a speed claim.

Sources: [bundle](../experiments/own-xpu-runtime/stage2/packet80-record-bundle/README.md),
[preparation](../experiments/own-xpu-runtime/ops/packet80-orchestration/README.md).
The helper will select only each packet's own both-lane confirmed exact winner;
missing evidence leaves its choices at production. It prints a chain command,
never launches it. Submission notes disclose all choices and enforce2000 chars.

Milestone2: all16 numerical compositions pass2096 exact output/scratch cases,
twice per compiler under GNU and Intel (64 executions). All128 real full-shape
post-load allocation/capture mocks pass. The four placement censuses pass the
unchanged arena and physical-capacity gates; rank1 draft at23/25 has the
smallest arena margin,89,364,320 bytes. That is a mock allocation census, not a
claim about measured driver residency.

The native miniature engine matches packet75 in all64 configurations, twice
each: target tokens,96 target-state fixtures per run, draft proposals and draft
state all agree. Ordered retirement's error/refusal tests and20 reverse-handoff
protocol cases pass twice with both compilers. Chain tests pass197 tests plus
24 subtests, including the actual packet70 K2 archive replay, dispatch merge,
all64 submission configurations and pinned resumes. Nine orchestration tests
pass. Two copied archive tests described an older stopped packet rather than
packet80's fresh-chain policy; they now test the actual refusal rule. The
miniature harness initially refused before launch because OMP_NUM_THREADS=2
was absent; the corrected closed environment is used for all recorded runs.

A read-only audit found no C++ composition defect. It caught a missing binding
for the orchestration source files tested by the final dry run; those hashes
and the dry-run receipt itself are now required by readiness. Initial CPU seals
are retained in a byte-verified archive before refreshing the helper bindings.
The final128 shared-wrapper plans and704 chain-window plans are underway.
No GPU or service ran. Packet76 now has both-lane confirmation; the current
reader selects ordered host cleanup plus hc-wide. Packet78/79 remain production
until their own exact improving B confirmations are present.

The final read-only review found a stale packet70 schema assertion in the
copied resume preparation entry. Packet80 receipts now pass that entry, while
packet70/75 receipts are refused before any registration or subprocess call.
Three direct helper tests pass. The CPU-only plan process was interrupted
gracefully, its partial logs retained, and all seals and final plans are being
regenerated with the corrected helper. No GPU process was touched.

At 23:18 UTC, packet78's own comparison confirms small+hc-wide on both lanes,
with all 13 requests exact in each screen. It can now supply fast route and
fused norm alongside wide HC. Packet79's complete lane-A grid is exact, but
both rank-0 candidates are slower than production; its own best logic returns
no winner. The selection therefore keeps rank 1 at 24/24. These are component
screen decisions, not a measured speed for the combined binary.

Final CPU rehearsal passed all 128 shared-wrapper screen plans and all 704
chain-window plans. It also passed 200 chain tests, 24 subtests and 9
orchestration tests. The source-bound receipt records a 782,217,786-byte build,
below the 1.5 GB limit. The numerical, allocation, handoff, K2, dispatch and
submission checks are all retained in the new packet.

The one-shot preparation now writes ready=true for ordered host cleanup, fast
route, fused norm, hc-wide, rank1 at24/24, wide64 experts and production dense.
Its CPU, seal, input, storage, window-plan and queue-plan prechecks pass, and
verify_ready.py accepts the receipt. ready.json contains the exact chain
command. No chain, GPU job, service or external submission was launched.
Two consecutive one-shot runs selected the same configuration, passed every
precheck and passed the readiness verifier. The latest ready.json and check logs
are authoritative; ready-first-pass.json retains the earlier readiness snapshot.
