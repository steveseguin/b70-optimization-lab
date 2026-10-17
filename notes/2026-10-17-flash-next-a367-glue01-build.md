# A367 glue01 CPU build — October 17, 2026

The separate control/candidate packet is built and sealed. All **606 CPU tests
pass**, plus **144 actual-method byte-mock cases**, with zero mismatches across
five seals. No GPU, health probe, model-weight read, unitrace, XPU-SMI, service,
sudo or host-setting change ran. No owner window or launch claim was created.
Device ownership stays with the coordinator; neither arm was launched.

[Packet](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01/README.md),
[coordinator commands](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01/LAUNCH-RUNBOOK.md),
[build receipt](../data/2026-10-17-flash-next-a367-glue01-build/receipt.json).

## Identity and source export

- Preregistration SHA256: `a38e2d41f6d4a7b4a952574c6366614e1e853eb8451c447b3ededd026eede8a0`.
- Seal SHA256: `2b7f8c767b554d37d9607f87534e6fe9f9ddaef0d64667e0896936248e77f736`; 127 pinned repository members.
- Source: census commit `7a5176c5dd9ab4bad6597653d07cf8a95078edca` and the unchanged
  replay packet. The prior replay reproduced 12/12 at 47.110 tok/s; the certified
  A367 authority remains 46.854250 tok/s. Neither number is a new measurement.
- Candidate export: `/home/steve/src/vllm-flashnext-a367-glue01-20261017`.
- Patch01 SHA256: `9a31076b55f5e6298226c9caa8c2ddf34a0ed479508512ad70be7de089c1c912`.
- Patched communicator SHA256: `535aece99342e578a9785beb63e4bbe86dcc737269da6a7335061bf0b83bb5e2`.
- All 6,814 export members were compared. Only the communicator changed. The clean
  export stayed byte-identical and all 2,305 certified Python pins passed.
- Candidate manifest SHA256: `18640c9928bf710c11e03dc562299b23cbd30a58902c173a16d9d8c4db60ed2f`.

The [full export manifest](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01/source-export.json)
is retained to verify every member, including non-Python files, and restore/check
the export using `build_export.py` plus the pinned clean export and patch01.
The copy uses about 165 MiB; no model data was copied. Interrupted receipt writing
was recovered by a read-only reverse-patch check; the patch was not applied twice.
Control command/environment match the sealed replay. Candidate enables only
`Q38_M2_GLUE_ROW_COPY=1`, plus separate source/entry/receipt plumbing for its gate.
GEMM, weights, placement, full-precision KV, exact GDN and CCL settings are frozen.

## Exactness, reporting and lifecycle

Both clients run the full twelve-prompt timed suite first, cold, at the original
512-token cap. Every token array, UTF-8 output, prompt/stop pin and the unchanged
checker must match. Later battery requests retain the canary, seven quality
outputs (including the inherited code-execution miss), 16/16 repeats, needle,
short diagnostics, and two repetitions each of p2048/o128 and p4096/o128 at
capacity 4352. The exact depth pins are `afffd211…` and `1d833e5f…`, with fixture
`c44fccba…`; no oracle is regenerated. Tokenizer files use the freshly verified
USB launch tree. No historical wrapper runs.

The 144-case CPU operator gate proves Python copy/control behavior only. Before
its timed suite, the candidate server must produce four complete passing operator
receipts from 72 cases per rank: eager M1/M2, changed-input graph replay and repeat
replay, exact row bytes, unchanged inputs, fresh output, signed zero/cancellation/
subnormal/NaN payloads, fixed shape/stride/group and row-1 offset. It uses the
existing communicator during warmup, without tracing or another device job.
Native behavior remains unqualified until that future gate passes. CCL algorithm
settings are pinned; internal algorithm selection is not separately profiled.

The report recomputes class-balanced 99-interval and all-prompt medians, TTFT,
full-response wall time and available acceptance counters. Flushed M1/M2 graph
dispatch counts are labeled whole-window, including the battery. Missing device
cycle/target/rank timing remains unavailable. Speed never gates exactness and
one pair cannot establish fresh-candidate determinism or a new record.

The census sampler's timed path does no RAID I/O; attribution and the local writer
run separately, with worker cmdline caching. The supervisor retains the reserve,
one graceful API-PID SIGINT, all-session exit and full 305-second watch. Control
failure blocks candidate. Seal-scoped claims prevent retry through another
campaign path. Candidate gets a new health check after control's full gap, its own
payload and owner window, and its own complete post-exit watch. No service restore.
Budgets remain 1800s loading, 2700s client and at most 3600s authorization; expiry
can prevent completion and never authorizes extension or retry.

## One resolved current-boot fault

At 01:09:16 UTC on boot `2cba7160-054a-4ffe-b4c4-e252eb956f5f`, the traced
communicator feasibility test produced one incident with two GPU fault lines on
card `0000:47:00.0`: BCS Fault response and engine reset. The retained bounded
01:09:46–01:09:51 probe passed all four cards with zero during-probe faults.
These are supplied incident receipts, not device work performed by this build.

The [sealed resolution](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01/resolved-fault.json)
contains both full lines, per-line and set SHA256/count, original log hash, probe
path/hash/start/end and the owner's standing-rule citation. Every admission must
find exactly that multiset, with both lines before the successful probe; no other
fault may exist. Fresh launch health may report two prior lines only in this case.
The watcher excludes exactly those two occurrences. Any added/duplicated/changed
line or lost journal history fails; the next incident on this boot requires the
owner's reboot decision. Current-boot FAULT.json latches remain refused. No old
packet or driver gate was relaxed.

Eighteen resolution tests include the five required cases: exact acceptance,
third line refusal, altered line refusal, fault after probe refusal and missing
probe refusal. Additional cases cover duplicate lines, corrupt/failed probes,
wrong boot, absent resolution, launch count and live watcher latching.

## CPU validation

| Suite | Tests |
| --- | ---: |
| glue01 | 148 |
| census | 206 |
| replay | 84 |
| calibration | 75 |
| driver | 59 |
| payload | 6 |
| tree | 9 |
| feasibility | 19 |

The new 148 tests comprise 32 admission/identity, 34 battery/comparison, 42
lifecycle/sampler, 18 operator, 18 resolution and four writer tests. All eight
suites, two plans, Python/shell syntax checks, whole-export comparison and five
seal checks passed. Independent review found no remaining blocking issue after
fixing the missing arm argument, log ownership collision, candidate health
freshness and metrics artifact binding. Logs and the review are retained beside
the receipt. Existing calibration/replay/census/driver files remain unchanged. Repository hygiene
passes without warnings. All 127 sealed dependencies are present byte-for-byte
in the Git index. The original hash-bound kernel log deliberately retains its
one trailing-space line; source and documentation whitespace checks pass.

## Approval sentence and next actions

The coordinator records this sentence under the owner's standing instruction;
the pending template is not a live authorization and no window was filled here:

> I authorize the A367 glue01 row-copy screen on steve-b70s: one control then one candidate, each once on a fresh server, with a MemAvailable start floor of 114840824 KiB, a 0.5-second watchdog and the 12000000 KiB live reserve, under preregistration SHA256 a38e2d41f6d4a7b4a952574c6366614e1e853eb8451c447b3ededd026eede8a0 and seal SHA256 2b7f8c767b554d37d9607f87534e6fe9f9ddaef0d64667e0896936248e77f736. The coordinator records this approval under the owner standing instruction. Each arm requires its own fresh health receipt, owner window and 305-second gap. This accepts unmeasured generation-memory risk, does not lower the packet-4 fixture floor and permits only the single hash-bound resolved fault.

Follow the [script-file runbook](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01/LAUNCH-RUNBOOK.md):
control prepare → audit → payload → health → pending → fill → launch → completed
305s watch → check; then the same sequence for candidate with a new health check
and window; then compare. Fresh storage, ownership, payload, health and memory
admission remain launch-time checks. The build makes no device or speed claim.
