# Reproducing the 06:23 hang (registered 12:17 EDT, 2026-10-17, before any run)

## What is known

Campaign 28e, 06:11-06:23 EDT (`notes/2026-10-17-context-lane-public-remeasure.md`, evidence
`data/2026-10-17-context-campaign28/c28e-*`): the context-lane server (R314, TP2, depth 5, exact cache with the
tail switch, one-launch verify) finished a request at about 06:22:19, sat idle, and when the next request arrived at
06:23:00 the TP0 worker's wait on the previous step's `num_accepted_tokens_event` and the output thread's
`async_copy_ready_event` both died with DEVICE_LOST. So the GPU work that never finished is the last step issued
before the idle, the step async scheduling issues one ahead, whose results are dropped because the request had
already finished. Card 03:00.0's dump: compute context ccs15, job seqno 82 never signalled, the command streamer
parked on STATE_COMPUTE_MODE (IPEHR 0x61050001) behind a kernel still running on all 32 rows (ROW_INSTDONE 0), no
command error, no page fault. Card e3:00.0: engine reset and a copy-engine CAT error at 06:23:02, and its copy
engine was still held by that server's context in MI_SEMAPHORE_WAIT at 10:31. A kernel spinning on one card while
the other card's copy engine waits for it: a cross-card exchange that one side never completed fits; a data-dependent
endless kernel on card 03 fits as well. One hang in about 2,000 requests of agent traffic today.

## Run

The step-floor runner (`scripts/run-20261017-step-floor.sh`) in stress mode: arm L (the context-lane server as in
campaign 27/28: pieces of 832, exact cache with the tail switch, spec-resume-accepted, exclusive prefill, one-launch
verify, plus `b70-step-breadcrumbs` and the host step clock), then `scripts/stress-request-endings.py` for 60 minutes:
six synthetic agent-like conversations whose history grows each turn (prefix-cache hits with short new tails, up to
30K tokens), greedy answers of 8-300 tokens (30 % stopped by a stop string), 3 % of requests followed by a 5-45 s
pause. On the first failed request the runner copies the device coredumps, the kernel log, the breadcrumb blocks and
the server log end before stopping the server.

## Prediction and decision

- **Prediction:** about 1,000-2,000 request endings in the hour. With one hang per about 2,000 agent requests, a
  hang in this hour is about an even chance.
- **If it hangs:** the breadcrumbs name the last step each card was given (shape, the scheduler's and each card's
  token counts, one-launch flag). The fix follows the step: an endless kernel on a dropped step points at its inputs
  (the next run checks them before launch and skips work for finished requests); a step the two cards were given
  differently points at the per-card state.
- **If it does not hang in the hour:** a second hour with one-launch verify off is not informative by itself (no
  hang in an hour proves little); instead the next run doubles the ending rate (shorter answers, more
  conversations), and the dropped-step inputs are checked offline from the breadcrumbs of normal endings.
