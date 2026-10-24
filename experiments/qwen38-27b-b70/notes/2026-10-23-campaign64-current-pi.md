# Campaign 64: return to the full pi repair task on current ctxkeeper

Registered while campaign 63 runs, before any campaign-64 model call. Campaigns 60–63 diagnose
a recorded failure, but replay corrections do not prove that a real agent completes its work.
Run the full task now with the current keeper and the owner's retained notes-thinking-on setting.
This is a practical baseline, not promotion of any experimental reviewer.

## Identity and scope

The original pi 1.2.0 image remains available with the exact campaign-20b image ID:
`sha256:015ded922b7f05212e76d8cc0053e5d8411c8ac1bf39e1389ab43b2f6fd808be`.
Use the unchanged repair-n40-s2x task, instruction, tools, tests and grader. Original history and
sampling behavior remain as shipped; no agent-side compaction or “keep going” intervention.

Current ctxkeeper 1.3.0, `--recipe qwen --notes-thinking on`, fresh state. The on override is explicit:
the public qwen recipe itself defaults notes thinking off. Medium effort, 32K live window, 15K in-place
cuts, normal archive recall. No neutral reviewer, reasoning projection or query planner from campaigns
61–63 enters this task. Production recipe defaults remain unchanged.

One fresh c59-identity two-card Qwen3.8-27B FP8 server, full-precision KV, MTP5, two sequences,
piece 832, exact prefix cache/tail and single-launch verification. Campaign 20b used older keeper
1.0.1, notes thinking off and older server scheduling settings. Its 39 fixed/39 clean/0-of-7 audit is
historical context, not a same-input causal control or a speed baseline for this run. Filesystem time
is not retrospectively normalized; retain actual model-visible inputs.

## Predictions and decisions

Hypothesis: current pi reaches all 44 tickets and preserves the requested seven-line audit file.
The standing full-task gate remains **40/40 fixed, 40/40 rule-clean, 7/7 audit**, with nonvoid grading,
whole-history client checks and no proxy restart. Record every lower score and its source cause.
Inspect all NOTES cuts, particularly whether a completed artifact is later denied or removed.

Expected 30–45 minutes of agent work (prediction), 60-minute agent cap, outer check-client cap
70 minutes for grading and cleanup. Record notes cost/fallbacks, task calls, total wall, rules and
memory; no model speed claim. A passing practical baseline does not retroactively pass the replay
failures or qualify the experimental reviewer. A failure is localized to original observations,
notes, subsequent actions and grader evidence before another lever is chosen.

## Operation constraints

Use the current campaign lifecycle runner with a pi check-client wrapper, **not** its existing
`repair` queue branch (that branch runs PlainAgent). Base task runner:
`tools/agentbench/run-agent-job.sh`; task directory:
`/mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2/tasks/repair-n40-s2x`.

Before GPU launch, verify the exact existing agent image, unused output/container/proxy paths and
completed clean campaign-63 shutdown. Do not enter the task runner's automatic image-build fallback.
At client launch require enough MemAvailable for the 1.6 GiB server guard, the full 768 MiB task cap
and 300 MiB buffer. Container memory and memory-plus-swap both 768 MiB; no GPU devices, no external
network, only the established local Unix-socket bridge. Capture full requests and unchanged grader
outputs. Job exit zero alone is not success: inspect agent exit, grading and whole-history receipts.

The wrapper owns one fresh proxy, stops it in cleanup, and leaves the existing runner to stop its
server gracefully. No automatic server retry or resident restore. Freeze scripts/config/task identity,
run CPU wiring checks and independent review before launch. No agents/tests/builds alongside the run.
Parent remains active through completion and audit.

The derived task driver makes four explicit plumbing substitutions: absolute original helper directory,
fixed image digest, refusal instead of automatic image building, and deferred history-log checking.
The original task runner and agent image are unchanged. Its large TAP log checker otherwise loads
the entire file in RAM; invoke that unchanged checker only after confirmed GPU shutdown. Preserve the
original agentbench receipt (whose history field is pending), then record the final history verdict
separately. Client completion, final receipt completeness and quality pass are separate fields.
Implementation: [client](../scripts/context/current_pi_probe.py),
[runner](../scripts/context/run_campaign64.py), [ten CPU tests](../scripts/context/test_current_pi_probe.py).
The tests pass, including failed service inspection, wrong image, low memory, fresh paths, receipt
failures, proxy cleanup and deferred original history checking.
[Independent source review](../data/2026-10-23-campaign64-preflight/review.json) binds both executable
sources. [Read-only preflight](../data/2026-10-23-campaign64-preflight/prelaunch.json) confirms the
existing exact image, unused paths, original task hashes and exact four-line driver diff. The runner
repeats preflight before starting its server; every client/finalize stage verifies these frozen pins.
