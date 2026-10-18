# Packet137 — exact token-input path

## Preparation, October 18

The new copy uses packet124c bundle7. Packet136 was present but uncommitted at
entry, so it was not used. Pull refused because unrelated orchestration files
were dirty; fetch confirmed HEAD and origin/main both at
`871fd06e209b0ab09081ef3443e557b5626a8c92`. Root had 38.7 GB free.

All 182 parent symlinks are retained verbatim. The parent and other live work
are untouched. A read-only helper audited the original draft arithmetic and
launch gates while the host was busy.

At the first milestone, implementation was in progress. The new runtime has a full-vocabulary read-only
projection table path, bounded pinned draft row, and fixed target lookup buffers.
The original draft path uses the unmodified norm tree and 32-lane projection
sum. Target decoding hoists block setup without moving a rounding boundary.
Existing history and device rollback remain authoritative.

The table builder streams 5,120 bytes per vocabulary ID, checks target decode
bytes, then replays the original chain with the other compiler. A 32-row pilot
was submitted to the shared compiler turn. The whole-host marker was active;
no bypass is allowed. No successful table/build/runtime test is claimed yet.

CPU-only rules: nice19, CPUs 8–15/24–31, Python -B, stdin closed, CPU entry
address-space cap 4 GiB. Root must remain above 25 GB; builds below 300 MB.
Table budget is 1,271,398,400 bytes, outside Git. No GPU, service, sudo, host
setting, power setting, reboot, live queue or unrelated file changed.

## Full table and CPU parity milestone

Both GNU and Intel completed all 248,320 vocabulary rows with identical
bytes. The file is read-only at
`/home/steve/own-xpu-runtime-results/packet137-token-input/draft-embedding.bf16`.
Its SHA-256 is
`72260c77f4fec1174caead915453e0647e7b18d487255a114a8f96ae1e2709c9`
and its size is exactly 1,271,398,400 bytes. Generation streamed to disk;
maximum child RSS was 287,220 KiB. The complete receipt is
`experiments/own-xpu-runtime/stage2/packet137-token-input/evidence/table.json`.
The builder replays the original normalization/projection primitives and
checks raw embedding decode bytes. Intel verifies every GNU output row.

The target decoder passed all 65,536 FP16 scale bit patterns for both Q6_K
and IQ4_NL, including nonfinite values, under both compilers and fresh
repeats. The signed PLE/EOS/history test passed 4,096 cases per run.
The miniature native IPC replay preserved exact draft proposals, target
tokens and final state against the frozen parent and both compilers through
five views and fresh repeats. Full production-shape startup and reset
checks passed; these CPU mocks do not qualify device output or speed.

The initial GNU/Intel pilot exposed a missing Intel OpenMP runtime path;
the builder now embeds the library rpath. Its earlier failure log remains
in `evidence/table-pilot-intel-runtime-failure.log`. An unchanged legacy K2 numerical fixture exceeded
the mandatory 4 GiB CPU cap. The cap was not raised. Its failure receipt is
retained, and the all-window gate uses the real K2 argument path and the
frozen measurement-validator replay. K0/K1a/K1b ran locally. K2 is explicitly
not claimed as a new successful numerical run.

The native review removed repeated mode lookups from the per-kernel loop
and restored transfer-time accounting for the direct staged row upload.
The numerical qualification was rerun after those changes. Device proposals
will require the 32-row original-device-chain check before readiness, exact
target output, identical per-prompt proposal sequences and acceptance across
the bracket, and the original oracle binding. No GPU was used.

## Stack with packet136

Packet136 committed as `3dfcff0ca` while this task was running. Before final
qualification, packet137 adopted that parent: fixed `miss=banks-batch` in all
four selections, its unchanged arithmetic objects and memory plan, and its
two native source deltas. `parent136-binding.json` pins the exact inputs.
The original 182 symlinks still match both parents. The table proof remains
applicable because neither checkpoint nor embedding arithmetic changed.

The bank layout never switches within the bracket. At each boundary the
runtime validates the next selection, retains and clears the completed state
under its old physical roles, then restores active/spare roles 0/1 and
rebuilds all six existing captures. It allocates no new banks. The full-shape
gate hashes all six captured argument sequences, and byte-reset regression
starts from all six pairings. The 491-case inherited cancellation/redo test
passed under GNU and Intel for original/both. Only obsolete host
`lookup_ids` staging is omitted from that test's cross-mode serialization;
all model, device and host-history bytes remain compared.

The bank reserve replaces an equal-size snapshot region: net device arena
change is zero (29,601,792 bytes move from backup to reserve). The extra
host admission is the 1,271,398,400-byte table, 5,120-byte pinned staging and
a conservative 32,768-byte target-buffer reserve above the inherited 97 GiB.
The plan exposes the exact total to the queue's admission parser.

## Final numerical and wrapper checks

All four 491-case cancellation/redo runs passed: GNU and Intel, original and
both. Each covers 43 position classes, a 98-step live sequence and three
corruption controls. The compressed transcripts have identical SHA-256
`b1e3349b148cc71e9473ce2920ee87c6702f76e48cbdfd15b432cff2c88535d0`.
Maximum child RSS for that gate was 967,368 KiB. The tests ran serially.
Full-shape startup checks all six captured bank pairs; reset tests start from
all six pairings and verify five host/device history rollbacks per rank0 run.

The first launch-argument rehearsal intercepted the real oracle subprocess
as if it were a native GPU launch. The corrected harness permits only the
exact original `shared_oracle.py --require-complete` command, executes it,
and still intercepts both native launches. The original refusal is retained
in `evidence/argument-oracle-interception-failure.log`.

The inherited queue rehearsal then found 1.811 GB in an older packet's local
build against its 1.2 GB allowance after redirecting queue output to scratch.
That refusal is retained in `evidence/inherited-queue-storage-refusal.log`;
no older build was deleted and no old allowance changed. A packet137-local
copy of that probe checks our actual 300 MB build budget separately and uses
the disposable directory for both queue output and its storage accounting.
The real storage check, input checks, oracle subprocesses, queue loop and
malformed-receipt refusals still run. This is a synthetic scheduling test,
not admission of the older chain or a claim that its build now fits.

The first real proposal plan also refused two unchanged K2 fixture symlinks
that resolve outside the repository. They are now an explicit external-binary
proof with exactly two allowed logical paths, literal link targets, resolved
paths and SHA-256 hashes, verified during both planning and final readiness.
They are excluded from repository source maps. Their frozen startup archive
still supplies their expected bytes; oracle authority remains separate.
The initial plan refusal is retained in
`evidence/queue-plan-legacy-path-refusal.log`.

## CPU handoff complete, 17:02 UTC

The final CPU seal and extended qualification pass. All 44 token-input/window
constructions, eleven real legacy queue windows, twelve input preflights and
six complete-oracle checks pass. Both real worker launch paths, all 78
synthetic worker requests, corrupted-output abort, drain and unchanged native
resource-limit checks pass. Temporary queue tests cover success and failed
children for both registered jobs, with no retry or service execution.

The three new proposals pass the real planner on disposable queue copies:

- `ops/lane-queue/proposed-p137-smoke-B.txt`: twelve 64-token requests with both.
- `ops/lane-queue/proposed-p137-v5-B.txt`: one-load original/both/original/both/original.
- `ops/lane-queue/proposed-p137-v5-A.txt`: the same bracket, unqueued on lane A.

Paths above are relative to `experiments/own-xpu-runtime/`. All three remain
unqueued. Each bracket view has twelve 128-token requests and the separate
incident64 sanity check. Smoke is expected to take 240–360 seconds and the
bracket 720–1,200 seconds; the 4,800-second watchdog meets the four-times rule.
Host admission requires 105,424,393,216 available bytes. The final build uses
150,459,412 bytes; root had 35.54 GB free. The table remains mode 0444 outside
Git. All 182 original symlink targets remain intact.

The bracket requires the exact lane-B device smoke, including 32 original-path
table samples before readiness, and coordinator live admission. No GPU or
service was started, no live queue was edited, and no host settings changed.
Device output/proposal identity and speed remain pending; no record or
promotion changed. The preparation finished within the 2.5-hour time box.

[CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet137-token-input/CPU-PREPARATION-CLOSEOUT.md)
links the retained proofs and the conditions for continuing.

## Packet137b — report import repair, October 18

The smoke finished its device work and exact checks, then failed while writing
the report. Its original receipts, including the report failure and the
recorded fault count of two, remain untouched. No v5 bracket result is claimed.

The cause was `v5/cpu_seal.py:oracle()`: it left the packet root first in
`sys.path`. The later `from compare import finish_bracket` therefore imported
the historical root `compare.py`, which has no such function. The oracle
helper now restores the path on both success and failure. The active report
module is uniquely named `packet137_report.py`. The shared CPU report step
dispatches smoke directly to `finish_smoke`; only a five-view bracket calls
`finish_bracket`. The bracket's smoke prerequisite now names the fresh 137b
smoke output.

The report gate passes both complete report paths using synthetic evidence
through the real `screen.report_step` entry. It reproduces the exact import
failure in both old-code paths from commit `981a673c8`, even with the wrong
`compare` already cached. It refuses corrupted target tokens and asserts that
smoke cannot enter bracket finishing. Fifteen policy/timing tests also pass;
their process peaked at 32,612 KiB RSS. This work used nice 19, CPUs
8–15/24–31, Python `-B`, closed stdin and a 2 GiB address-space limit.
No model data, GPU, service, sudo or host setting was used.

The whole packet Python tree was scanned. Nine other duplicate module names
remain: `protocol_gate`, `build_engine`, `chain_devices`, `queue_plan`,
`drain_gate`, `placement`, `lane_admission`, `full_shape` and `exec_limits`.
The detailed import census is retained in
`v5/evidence/report137b-collision-audit.json`. Restoring the oracle helper's
search path removes the identified cause for late imports; historical entries
remain historical. The active report no longer uses an ambiguous module name.

The minimal reseal retains all original affected receipts in a verified
compressed snapshot. It changes report dependencies only; no native binary,
table, numerical result or device receipt was rebuilt or replaced. The old
queue test's stale shared-source pin now points to an exact local snapshot
from `981a673c8`, verified against its original SHA-256. No shared file was
edited or repinned to new bytes.

Fresh B proposals name `packet137b-smoke-B` / `device-smoke-137b-B` and
`packet137b-bracket-B` / `device-v5-137b-B`. The latter depends on the former.
Both packet plan paths pass in a model-free rehearsal: full-table rehashing
and complete-oracle payload admission use retained receipts in that rehearsal
only. Actual device admission still performs the original checks.

**The current real queue planner refuses both proposals.** Its new pin guard
finds 4,578 inherited pin errors, including mutable sources in other packet
trees. Full refusal receipts are compressed under `v5/evidence/`; the compact
planning report is `v5/evidence/report137b-plans.json`. This was not bypassed
or relabeled as a queue pass. Repairing that inherited closure would exceed
the authorized minimal report reseal. Overall qualification and the final
`READY-FOR-DEVICE.json` explicitly remain false, while report repair is marked
passed. The two proposals were rewritten only after the temporary-copy
rehearsal and remain unqueued. The live queue and all other packet trees are
untouched.

Packet137 stays deferred. Reopen only stacked with another measured two-card
gain of at least 1.5%, after resolving the inherited pin closure and passing
the current queue guard. No speed gain or new device qualification is claimed.

Pull refused because unrelated orchestration files were dirty; fetch confirmed
HEAD equaled origin/main at `4918800df49f7ff3cadcc7f8975e5758903351bd` before
editing. Only the packet137 repair, two allowed proposals and this note are
included in the focused commit.
