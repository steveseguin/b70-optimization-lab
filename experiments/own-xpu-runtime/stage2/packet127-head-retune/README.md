# Packet127: exact target-head split retune

CPU preparation is complete. Three sealed views keep the same 24/24 bundle7
line and use rank0 suffixes of **46,080, 81,920 and 122,880** rows. GNU and
Intel pass repeated exact-byte and reset tests; both ranks fit; all 33 startup
windows pass. Device equality and speed remain unmeasured for the new points.

The only runtime dimension is row ownership. Each view selects registered
bounds before allocation and command preparation. Every vocabulary row keeps
its arithmetic, BF16 rounding, lowest-index tie rule and nonfinite refusal.
The fixed 80,128-row draft prefix and BF16 KV stay unchanged. Copied lifecycle
code clamps both drain waits, including the shared wrapper import paths.

## Coordinator handoff

These are proposals only; this task installed no live queue or waiter.

| Proposal | Work | Planning budget |
| --- | --- | --- |
| [Micro 81,920](../../ops/lane-queue/proposed-p127-micro-81920-B.txt) | 4,096 vectors, forced suffix winners, ties, nonfinite rows and resets | 100 seconds; 1,200-second watchdog |
| [Micro 122,880](../../ops/lane-queue/proposed-p127-micro-122880-B.txt) | Same cases in a separate fresh process | 100 seconds; 1,200-second watchdog |
| [Lane B grid](../../ops/lane-queue/proposed-p127-B.txt) | 46,080 / 81,920 / 122,880 / 46,080 | 4 × 450 seconds |
| [Conditional lane A](../../ops/lane-queue/proposed-p127-A.txt) | 46,080 / B winner / 46,080 | 3 × 450 seconds |

Both micros must pass, drain and release before B starts. B runs twelve cold
prompts × 128 exact tokens in each fresh rank pair. Its legacy 64-token gate
comes from the first response, with no extra or warmed request. Both controls
must be beaten by at least **0.5%**, with unchanged acceptance and exact oracle
tokens. Highest qualifying class-balanced rate wins; a tie chooses fewer
suffix rows. A's proposal resolves that winner from the complete, hash-checked
B receipts before each launch. The coordinator waiter should keep A pending
until `bracket_report.py --lane B` returns `passed: true`; a missing result or
no qualifying candidate is not launch permission. A must clear both of its
own controls at the same threshold. Normal fault, admission and drain gates
remain binding. No retry or restart loop is supplied.

Budget estimates allow for the old micro's roughly 53-second lifecycle and
packet120's roughly 204–292-second completed screens, plus margin. Shared
reservation/drain waits can extend wall time. Each screen watchdog is 3,600
seconds. The [temporary plans](evidence/queue-plans.json) check every proposal;
A's CPU plan checks both possible winners without choosing one.

## Evidence and limits

The old packet87/87t model favors the existing 46,080-row point. New points
probe whether bundle7 moved the best split; they are not forecast winners.
[Original bundle7 trace accounting](evidence/bundle7-traces.json) still cannot
separate rank0 head work from its apparent spare time. The extra historical
head-row cost estimates are 0.203 and 0.434 ms; the latter deliberately probes
near the loose 0.440 ms upper bound before existing suffix work is deducted.
Packet120's completed 25/23 candidate trails its first control; its trailing
control's lifecycle did not complete successfully. This is provisional
context, not a completed placement-bracket verdict or measured idle budget.

- [Exact CPU bytes](evidence/cpu-byte-identity.json), [reset regression](evidence/reset-regression.json).
- [All-window startup](startup103.json), [real allocation census](evidence/full-shape.json).
- [Six rank exec interceptions and cap refusal](evidence/launch-limits.json).
- [Policy and cold-worker checks](evidence/protocol-tests.json), [drain scan](evidence/drain-check.json).
- [Micro build](evidence/microbench-build.json), [job seal](screen-jobs-seal.json).
- [Focused runtime patch](integration.patch), [retention/reproduction](RETENTION.md).
- [Work note](../../../../notes/2026-10-18-own-runtime-packet127.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).

Run `final_verify.py` under nice19, CPUs8–15/24–31, Python -B and closed stdin
for read-only handoff validation. No GPU job, service, live queue, host setting,
model download or external submission was performed here.
