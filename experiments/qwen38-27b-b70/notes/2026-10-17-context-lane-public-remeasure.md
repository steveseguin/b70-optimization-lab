# Context lane: today's server against the public figures (2026-10-17)

The public context pages (skindeep `context-use.html`, the working-view table; ctxkeeper README) quote times measured
before two of today's changes, both bit-identical: one-launch verify (`2026-10-17-fp8-writing-attention.md`) and the
exact cache's tail switch (`2026-10-17-fp8-cache-tail-block.md`).

## Already measured on the same task (campaign 27, the 240K-token question stream, seed 0)

| Working view | public | today (c27a) |
| --- | --- | --- |
| 32K | 39/39; 9 min | 39/39; 6 min 58 s |
| 64K | 39/39; 10 min | 39/39; 7 min 24 s |

## Repair task re-measure (registered 05:51 EDT, before the run): campaign 28d

The public "32K repair: 40/40, 7/7; 16 min" is XR4 on `repair-n40-s2x` from campaign 17 (2026-10-13, 15 min 38 s;
`2026-10-10-context-16k-baseline.md`). Today's runner (`longrun-campaign28.sh`, kind `repair`: notes thinking off,
effort medium, in-place notes, recite on tickets) on c27a's server (depth 5, one launch, tail), queue line
`K32 repair 2x 3600`.

- **Prediction:** 40/40 fixed, 40/40 clean, 7/7; 10-13 min. The keeper and server have changed since campaign 17, so
  the transcript is not expected to match it; this is a re-measure of what the current stack does, not an A/B.
- **Use:** the figures go to the owner as a proposal for the public pages (owner's call); nothing public changes here.

## 28d result: void, the server was killed by my own command (05:59 EDT)

The server was ready at 05:58:19 and had answered five agent calls when, at 05:59:04, I ran a Python one-liner
beside it that read this session's 380 MB transcript into memory to search it. Host memory fell from 2.25 to
1.40 GiB within half a second (`c28d-memory-guard-last20s.jsonl`; driver-held memory unchanged), the memory guard
(floor 1.6 GiB) killed the server mid-step at 05:59:05 (`c28d-MEMORY-GUARD.json`), and the kill left a compute-engine
reset on card e3:00.0 (`FAULT-20261017-c28d.json`; no page-fault or CAT lines; the same signature as the guard kill of
2026-10-12 19:56). Not a card, server or overlay fault. The runner did not restore Gemma, by design; restarting it is
the owner's call. Runner log lost: it was written into this folder, and the `git pull --rebase` at 05:56 replaced the
file under the running job (live logs now go under `/mnt/fast-ai/bench-results` and are copied after).

06:06: one bounded health probe (`scripts/check-qwen36-xpu-xccl-health.sh`: both cards' compute smoke and the XCCL
all-reduce) passed and the kernel log has no line after the reset, so per AGENTS.md rule 3 the work carries on
(my first reading, that the restart was the owner's call, was wrong: that was the 2026-10-12 practice without sudo).
The re-measure runs again unchanged as **campaign 28e** (same queue line, runner, flags and prediction; new run name
because the c28d output folders exist), log under `/mnt/fast-ai/bench-results/context-longrun-20261016/c28e.log`.

## 28e result: void, a real second GPU fault on this boot (06:23 EDT); GPU work stopped, reboot needed

Server ready 06:11:13 (2,977 MiB free), the repair task ran normally for 12 min (126 model calls, prefix-cache hit
rate 89 %, acceptance ~5.1), the server idle from 06:22:20, then the first step of a new 4,603-token request
(06:23:00) never finished: card 03:00.0 `Timedout job ... in python3 [2864707]` (the TP0 worker), engine reset and a
device coredump; two seconds later card e3:00.0 engine reset, `Fault response: Unsuccessful -EINVAL` and a copy-engine
`CAT error`. The worker died with `UR_RESULT_ERROR_DEVICE_LOST`; the agent got a 502 and the trial ended
(`ended_by=EXC:BadGatewayError`, does not count). No memory-guard event this time (no `MEMORY-GUARD.json`;
2.7 GiB free at the start of the task). The `page allocation failure: order:9` line is the coredump failing to get
2 MB for the GuC log snapshot, a consequence, not a cause.

Evidence (`data/2026-10-17-context-campaign28/`): `c28e-kernel-fault-lines.txt`, `c28e-devcoredump-03.00.0.txt`
(copied before anything could clear it; also under `/mnt/fast-ai/bench-results/context-longrun-20261016/
fault-20261017-0623/` with the full kernel log from 05:50), `c28e-server-log-end.txt`, `c28e-server-state.json`,
`FAULT-20261017-c28e.json`, `c28e.log`, `c28e-K32-repair.summary.txt`.

Not known: whether the 05:59 kill-induced reset left a card in a state that made this hang likely (the 06:06 health
probe passed), or whether this is an independent hang. This server configuration ran campaigns 26-28c today
(about 2 h of agent traffic) without a fault line.

**Decision (AGENTS.md rule 3): a second fault followed on the same boot, so all GPU work stops and the owner is told
that a reboot is needed.** No further launches, no driver reload, no probe loop. After the reboot: the boot's first
GPU job is the bounded health probe, then campaign 28e again unchanged.
