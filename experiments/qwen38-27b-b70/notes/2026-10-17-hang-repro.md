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

## Amendment 12:29 EDT (run in progress, no result read yet): the hung step is probably the new request's first step

Re-reading the 06:23 evidence against the vLLM 0.29 code changes which step is suspected. On the main stream a step
records `num_accepted_tokens_event` in `sample_tokens` (after the sampler and the GDN align bookkeeping), then runs the
drafter, then the output copy stream waits on the main stream and copies the sampled tokens (`async_copy_ready_event`).
The request that ended at about 06:22:19 got its 200 OK, so that step's copy finished and with it everything before it
on the main stream, including its accepted-count event. When nothing is left to schedule, the engine core blocks on the
oldest step in its batch queue (`step_with_batch_queue`), so it could only have sent TP0 a new `execute_model` after the
dropped step's output came back. TP0 died inside `execute_model` -> `_prepare_inputs` waiting on an accepted-count
event (`b70_spec_resume_accepted.py:315` -> `gpu_model_runner.py:2132`) while its output thread waited on a step's
copy. The consistent reading: the dropped step finished; the next request arrived after about 40 s idle; its first step
M was issued and never finished; TP0 was already in step M+1 waiting for M.

The detection time fits that. The exec queue in the dump has no job timeout (`Timeout: 0 (ms)`), so a spinning kernel
is only caught when the GuC has to switch it out; the engine reset came 0.65 s after 06:23:00 with the preempt
timeout set to 640 ms. The job number fits as well: job 82 after 12 minutes of serving (thousands of steps) means the
user-mode driver submits through a ring of its own and starts a new kernel-driver job only after an idle; step M is the
first work in a newly started job (`Start seqno: 82`).

Agent traffic between requests is idle 0.1-0.3 s (calls logs of c28a/c28c/c28f, 941 calls, longest gap 1.7 s); the gap
before the 06:23 request, about 40 s, was unusual. What a long idle can change: the user-mode ring is stopped and
restarted, the cards could runtime-suspend (both have `power/control=auto`, autosuspend delay 1 s, `d3cold_allowed=1`),
clocks and power states drop.

Changes to the plan, not to the running hour: the hour continues as registered (it has 3 % pauses of 5-45 s, so about
30 restarts after idle, and every request is a new request's first step). A power-state sampler
(`runtime_status`/`runtime_suspended_time` of both cards every 0.5 s) runs beside it, host only. If the hour does not
hang, the next run is not "double the endings" but **idle before every request**: the same client with a pause before
each request drawn from 0.5-60 s, so that every request is a first step after an idle. If the cards are seen to
runtime-suspend while the server holds them, that is fixed first (`power/control=on` for the run) and recorded.

## Amendment 12:40 EDT (hour still running, no result read): no idle before the hang; a replay of c28e is next

**The 40 s idle did not happen.** The keeper's own call log for c28e
(`/mnt/fast-ai/bench-results/context-longrun-20261016/proxy-state/c28e-K32-repair-s2x/5693d81e7626fa3b/calls.jsonl`)
has the last good call ending at 06:22:18.363 and the next one sent at 06:22:18.571, 0.2 s later, failing after
42.6 s. So the server was hung, not idle, from 06:22:18.6: the first step of that request (443 new tokens after a
4,160-token hit, per the engine's dump) started and never finished. Nothing noticed for 42 s because the exec queue
has no job timeout; the engine reset at 06:23:00.65 is 0.65 s after the minute changed, which fits the desktop clock on
card 03:00.0 being redrawn at 06:23:00 (gnome-shell renders on card 03; its jobs are in the xe trace below) and the
GuC failing to switch the spinning context out within the 640 ms preempt timeout. The desktop detected the hang; it
started 42 s before. The 12:29 reading (first step of the new request, not the dropped step) stands; the idle part
of it is withdrawn, so "idle before every request" is dropped from the plan.

**Observed beside the hour (host only):** both cards stay `active` through 20-44 s pauses (no runtime suspend while
the server holds them); the xe tracepoints (`xe_sched_job_*`, exec-queue and runtime-PM events, scratchpad trace)
show the user-mode driver restarting each card's compute ring about every 2 s during requests (new kernel jobs on
ccs guc_id 15 / 14, the same ids as at 06:23), a copy-engine job per step on each card, and gnome-shell's render and
bind jobs on card 03 only.

**Next run, registered now: replay of c28e** (`scripts/run-20261017-hang-replay.sh`, starts after the hour's unit
ends and only if the kernel log is clean). The same runner, queue line, flags and server as c28e, with the
exact-cache overlay at 0.2.0 as c28e ran it (frozen copy `overlays/b70-prefix-cache-exact-020`, byte-identical to
c28e's stage copy) and b70-step-breadcrumbs 0.2.0 (now also counting each worker's torch.distributed calls per step,
to show a cross-card exchange one card never joined). c28d (same server, killed by the memory guard at call 6) made
the same first 6 calls as c28e, so the call sequence is reproducible from a fresh server.

- **Prediction (stated before the run):** the replay makes the same calls as c28e (`scripts/compare-call-sequences.py`
  against c28e's call log) up to call 132; I expect it does **not** hang there (one hang in ~2,000 requests and no
  data-dependent loop found suggest a race, not the inputs).
- **If it hangs at call 132:** the hang follows from the inputs; the breadcrumbs and the saved request make it a
  deterministic case to bisect offline (overlays off one at a time on that one request).
- **If it passes call 132 with the same sequence:** the inputs alone do not cause it; the evidence for a race
  (cross-card exchange, ring restart, driver) is what the breadcrumbs and xe trace of the next real hang must
  separate, and the stress continues with them on.
- **If the sequence diverges before call 132:** the replay is not exact; it still counts as agent traffic with
  breadcrumbs on, and the 132 check is void.
