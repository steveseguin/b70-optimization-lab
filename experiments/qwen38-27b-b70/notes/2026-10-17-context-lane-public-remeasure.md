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
