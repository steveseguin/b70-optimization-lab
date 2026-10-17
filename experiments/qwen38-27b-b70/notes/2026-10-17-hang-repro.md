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

## Hour result (12:20-13:20 EDT): no hang in 1,792 requests

1,792 requests in 60.0 min, none failed (`data/2026-10-17-hang-repro/stress-L.jsonl`): every one a new request's
first step after a prefix-cache hit (95 % of prompt tokens cached, prompts up to 41,888 tokens), 46 pauses of 5-45 s,
slowest request 3.6 s, no request slower than 1.03 x its expected time, no breadcrumb stall, kernel log clean, cards
left empty. At one hang in ~2,000 requests the hour expected ~0.9 hangs; seeing none has a probability of ~0.4, so the
hour says little by itself, as predicted. What it does add: the synthetic stream at this rate does not hang often, so a
hang needs ~2,000 first steps or something the agent stream has and this one lacks (chat template with tool calls and
the reasoning parser, notes requests, the exact-cache tail switch extending drafting hits, which needs model-written
tokens in the reused history).

Correction to the 06:23 reading (`ROW_INSTDONE`): on the live healthy server every engine snapshot reads
`ROW_INSTDONE` 0 on all rows, idle or busy, so "a kernel still running on all 32 rows" was not shown by that register.
What the dump does show is `RING_INSTDONE` 0xffdefffe with the command streamer on STATE_COMPUTE_MODE; healthy busy
snapshots read 0xffdeffff/0xffdfffff with that instruction and 0xffdefffe only while on a semaphore wait (60
snapshots, 13:15-13:17). So at 06:23 the compute pipeline had unfinished work, without saying which kind.

The replay of c28e started at 13:20:57 as registered (12:40).

## Replay result (13:24-13:34 EDT) and amendment 13:38 EDT: the hung step was a first step; next run packs first steps

**Replay c28r: no hang in 199 calls** (9 min 51 s, `data/2026-10-17-hang-replay/`): no failed call, no breadcrumb
stall, kernel log clean, cards left empty. It was not an exact replay: it matched c28e for 18 calls and diverged at
call 18 (a notes request writing 417 vs 452 tokens), because the agent's tool output contains measured test times
(1.595 / 1.639 / 1.568 s), so the conversations differ from there on. As registered, the call-132 check is void; the
replay counts as 199 more agent calls with breadcrumbs 0.2.0 on.

**Ring-restart lead withdrawn.** On the replay's compute queues (card 03 guc 15: 77 kernel-driver jobs, card e3
guc 14: 80, in 10 minutes) only 2 of 76 main calls were followed within 50 ms by a new compute job on both cards.
The user-mode ring is restarted at other times, not at a request's first step.

**History.** Since the 2026-10-03 boot the kernel log has one live compute timeout ("Timedout job" on a ccs queue),
06:23 today. Every other compute engine reset (10-09 02:11, 10-12 19:56, 10-14 09:59, 10-17 05:59) came at a
container stop (work in flight when a server is killed). Requests served since 10-16 by server folder: about 6,150
TP2 agent calls before one-launch verify, then about 2,050 agent calls plus the 1,792-request stress hour with it.
One-launch verify is not what hung, though: it only takes calls with 2-8 query rows, and the hung step had none.

**The hung step, from the engine's own dump at 06:23:01.** A new request (4,603 prompt tokens, 4,160 cached, 443
scheduled), no draft tokens, one new attention block to zero (425). Only the TP0 worker (card 03) raised: its output
thread on that step's copy event and its next `execute_model` on that step's accepted-count event. The TP1 worker
(card e3) wrote nothing until shutdown, so it was blocked without an error. In agent traffic a request's first step
is about 5 % of GPU time (one prompt step against 50-200 drafting steps of 38 ms), so a race that can hit any step
would land in a first step about 1 time in 20. The one hang we have is in a first step, which points at something in
that step: the prompt-step kernels after a cache hit (GDN prompt kernel from a cached state, prompt attention over
cached keys, the block zeroing), or collectives at prompt size (4.5 MB each instead of 61 KB).

**Next run, registered now (13:38): first steps packed.** About 10,000 first steps have run on this stack with one
hang, so a test needs about 10,000 first steps per hour, not 1,800. The step-floor runner, arm L as in the hour
(current overlays, breadcrumbs 0.2.0 with collective counts, host step clock), `STRESS_MIN=120`, client options
`--answers 1,2,4,8,16 --tail-words 20,700 --gap 0.05,0.3 --pause-share 0`: tiny answers so nearly every step is a
prompt step after a cache hit, new tails of 30-1,000 tokens, and the agent's 0.05-0.3 s idle before every request.
Host samplers beside it as in the hour (xe job trace, engine-register ring, power states). Evidence:
`data/2026-10-17-hang-repro2/`.

- **Prediction:** about 8,000-12,000 requests an hour. At one hang in about 10,000 first steps, at least one hang in
  the two hours is 80-90 % likely.
- **If it hangs:** both ranks' last steps and collective counts (`scripts/analyze-hang-evidence.py`), the
  engine snapshots and the dumps name the step and whether the two cards were in the same collective; the fix
  follows from that.
- **If not (16,000+ first steps clean):** this synthetic stream's first-step hang rate is below about 1 in 8,000. Then
  the cause needs something only the agent stream has (chat template with tools, notes requests), and the next run
  replays agent queues with breadcrumbs. In parallel the context lane gets fast detection and automatic recovery
  (a stalled step noticed in seconds, the server restarted, the keeper retrying the call), because a hang at one in
  ~10,000 requests must not end a long task.

## Amendment 13:46 EDT (packed stress running, no result read): its rate, stack capture, and the exchange alone next

**Rate below the prediction.** The first 95 requests ran at about 4,400 an hour (median 0.58 s per request plus the
idle before it; the prompt tails reach two 832-token pieces), not 8,000-12,000. Two hours give about 8,800 first
steps, so at one hang in ~10,000 the chance of seeing one is about 55-60 %, not 80-90 %. The run is left as started.

**Stack capture added beside it (host only).** A watcher (scratchpad `stallcap.sh`, run as root) takes, if the stress
log stops growing for 15 s (normal worst case ~4 s), two captures 10 s apart into `data/2026-10-17-hang-repro2/stall-*`:
py-spy 0.4.0 Python stacks (non-blocking, 0.01 s, 9 MB) of the engine core and both workers, and every thread's
kernel state (wait channel, syscall, kernel stack). At 06:23 the hang ran 42 s before the desktop's redraw exposed
it and the TP1 worker printed nothing; this shows where each worker, and oneCCL's own threads, were waiting.

**Next run, registered now: the exchange alone** (`scripts/run-20261017-xccl-stress.sh`, starts when the packed
stress ends and only if the kernel log is clean since 13:39). Why: the only work in a step known to wait on something
outside the card is the two-card all-gather (134 per step plus the vocabulary gather), and the server's environment
sends prompt-size gathers (> 1 MiB per rank; the 06:23 step's are 4.5 MB) down oneCCL's "simple" path, which oneCCL's
default uses only up to 1 MiB (we set 4 GiB because the non-simple kernels need peer memory access, which faulted
both cards on 2026-09-17). `scripts/stress-xccl-allgather.py`, R314 image, the server's CCL_*/FI_* environment, no
model, 60 min: server-like steps of 134 fp16 [rows, 5120] gathers, each after a [rows, 5120] x [5120, 5120] matmul,
plus a [1-6, 124160] gather and a host wait per step; half the steps prompt-size (30-832 rows), half decode-size
(1-6); each card adds its own random extra matmuls before a quarter of the gathers, so the two cards reach a gather
at different times; 10 % of steps followed by a 0.05-0.3 s idle. Watchdog: no step for 10 s prints STALL and both
ranks' Python stacks, and the runner saves thread states, engine registers and, on a fault, the coredumps.

- **Prediction:** on the order of 15,000+ prompt-size steps in the hour (2M+ prompt-size gathers), more than all
  first steps served so far (~10,000, one hang). If the hang is the exchange alone at those sizes, at least one hang
  in the hour is likely (~85 %).
- **If it hangs:** the cause is in oneCCL's simple path or below it (runtime, driver), and it reproduces without the
  model. Then lossless fixes, one at a time on the same stress: the allgather's simple threshold back to oneCCL's
  default of 1 MiB (all-gather moves bytes, no arithmetic, so any algorithm gives the same result; it must not
  reach the peer-access kernels that faulted, which is checked first), or prompt-size gathers split into pieces of
  at most 1 MiB in b70-allgather-allreduce.
- **If not:** the exchange alone is cleared at that rate; the hang needs the model's own prompt-step kernels, and the
  next test runs those (GDN prompt kernel from a cached state, prompt attention over cached keys) at high rate.

## Amendment 13:55 EDT (no result read): what oneCCL's "simple" all-gather is on these cards

Read from oneCCL's source (uxlfoundation/oneCCL master, `src/coll/algorithms/allgatherv/sycl/allgatherv_sycl.cpp`,
`allgatherv_pcie.cpp`, `src/common/env/env.cpp`; the image's oneCCL 2022.0.0 exports the same `allgatherv_ll_ring`):
on Arc-family devices a message up to `CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD` (default 1 MiB) goes to
`allgatherv_ll_ring`, a PCIe ring kernel. Up to `CCL_SYCL_ALLGATHERV_LL_THRESHOLD` (default 2 KB) it uses the small
"LL" ring, above it the "LL256" ring; above `CCL_SYCL_ALLGATHERV_CHUNKING_THRESHOLD` (default 0, off) it would be
split into several calls. Bigger messages go to `allgatherv_large`. So the earlier reading "the simple path is
host-staged" (2026-09-19 note) was wrong for all-gather: it is a device kernel whose receiving side waits on flags
the peer card writes into the ring buffer.

What that means for the 06:23 hang: with the threshold at 4 GiB, every prompt-step gather (4.5 MB per card at 443
rows, up to 8.5 MB at 832) runs through the LL256 ring kernel at sizes oneCCL's default never sends there. A ring
kernel that misses or misorders a peer's flag waits forever with no page fault, and compute queues have no job
timeout. That fits the 06:23 card-03 dump and a hang inside a prompt step. Decode steps' hidden-size gathers (61 KB)
are inside the default range. This is a mechanism, not a result; the exchange stress (registered 13:46) tests it
directly, and both its step kinds use these sizes.

Lossless fix candidates if the stress hangs, each tested on the same stress first (an all-gather only moves bytes, so
the algorithm cannot change any value): (1) `CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD` back to 1 MiB, so big gathers take
`allgatherv_large`, checked first for the peer-access faults of 2026-09-17; (2) oneCCL's own chunking at 1 MiB
(`CCL_SYCL_ALLGATHERV_CHUNKING_THRESHOLD=1048576`), keeping every LL256 call inside the default range; (3) the same
split done in b70-allgather-allreduce. The prompt-reading speed of each goes next to the result: (2) and (3) add
per-call overhead to 134 gathers per prompt step.

## Amendment 14:00 EDT (no result read): the exchange stress gets a card-03 load arm; two corrections

**Corrections.** (1) The "simple" ring writes into the other card's ring buffer (`remote_ptrs` from oneCCL's IPC
exchange), so "the simple path never issues a peer access" (2026-09-19 note) is wrong too; what the 4 GiB pin avoids
is oneCCL's other kernels (`allgatherv_large`, the small/medium kernels), whose peer access faulted on 2026-09-17.
DO-NOT-REPEAT forbids lifting the pin, so fix candidate (1) of 13:55 (threshold back to 1 MiB) is dropped. (2) From
the protocol source (`proto_rt64_128.hpp`, `ring_transmit.hpp`, `allgatherv_pcie.hpp`): the receiver spins until
a slot's flag equals the expected value exactly (no timeout); the ring has 4 slots; for all-gather there is no
per-slot check that the receiver has read a slot before the sender reuses it; the launch is capped at
`maxSS` work-groups of 64 threads (20 for Arc B-series, 32 for Arc A), and a message longer than one pass over the
ring loops inside the kernel. Whether a lagging receiver can be overtaken depends on code these excerpts do not show
(a sub-group that sends and receives in lockstep cannot be); the experiment decides, not the reading.

**Why a load arm.** Only card 03 shares its execution units with another client, the desktop; a receiver that
falls behind is most likely there, and 06:23's stuck context was card 03's. The runner
(`scripts/run-20261017-xccl-stress.sh`, rewritten before it ever ran; its queued unit was stopped while still
waiting) now runs arms of 20 minutes each, stopping at the first hang:

- **A:** the exchange alone (as registered at 13:46, shortened from 60 to 20 minutes).
- **B:** the same while `scripts/load-card-bursts.py` loads card 03 in bursts (1-20 ms of matmuls, 2-50 ms idle),
  a stand-in for the desktop's work on that card.
- **C (only if B hangs, started by hand):** B plus `CCL_SYCL_ALLGATHERV_CHUNKING_THRESHOLD=1048576`, so every LL256
  ring call stays within oneCCL's 1 MiB default while the pin stays.

- **Prediction:** A clean. If the mechanism is a lagging card being overtaken in a ring call longer than the ring, B
  hangs within minutes and C does not; if B is also clean, the exchange, with or without a competing load, is
  cleared at that rate, and the model's prompt-step kernels are next.
- **Fix, if B hangs and C is clean:** the server takes the chunking threshold (lossless: an all-gather only moves
  bytes), after the packed stress and a prompt-reading speed check on the context-lane server.

**14:00 EDT: the packed stress is cut to 60 minutes** (ends 14:42 instead of 15:42) so the exchange arms get the
cards sooner: arm B tests the leading mechanism directly, and another hour of the packed stress would add only
~4,000 first steps (~35 % chance of a hang at one in ~10,000). The stop is mine: at 14:42 I end the stress client
(pid 3187238) with SIGTERM, so the runner's "stress client stopped with a failed request" line at that time is that
stop, not a failure; the result is read from `stress-L.jsonl` (every request it logs completed).

**14:02 EDT, counter-evidence to the size reading (server folders since the 2026-10-03 boot, TP2, allgather overlay,
4 GiB pin):** 119 runs with 832-token steps (91,536 requests; the context lane, the one hang) and 124 runs with
4,096-token steps (24,721 requests, about 58M prompt tokens summed from the servers' throughput lines, mostly
without prefix caching, so roughly 14,000 prompt steps whose gathers are about 42 MB per card), with no hang. If ring
calls longer than the ring were the trigger, the package's five-times-larger gathers should have hung at least as
often. So the size reading is not favoured by history; the arms still run as registered (they are cheap and cover
the 832-token sizes, the load arm adds the one thing the package runs may have lacked: a lagging card mid-gather),
and a clean A and B moves the search to what only the context lane has (prefix-cache hits in align mode with the
exact-cache overlays, one sequence, 262,144 window).

## Packed stress result (13:41-14:42 EDT): no hang in 4,158 first steps

4,158 requests in 60.5 min (4,127 an hour), none failed (`data/2026-10-17-hang-repro2/stress-L.jsonl`); 4,053 with a
cache hit (93.7 % of prompt tokens cached, new tokens per request median 1,309, prompts up to 41,196 tokens); answers
of 1/2/4/8/16 tokens about 820 each; no breadcrumb stall, kernel log clean, server stopped cleanly, cards left empty.
The runner's "stress client stopped with a failed request" at 14:42:14 is my SIGTERM (registered 14:00). One stall
capture fired at 14:36:54 and was a false alarm: request 3,795 found nothing cached (its conversation had been
evicted) and read 33,598 tokens in 13.1 s (2,550 tokens/s, normal); its stacks are kept as a baseline
(`stall-143654/`): rank 0's main thread waits in `_prepare_inputs` (`gpu_model_runner.py:2132`, the accepted-count
event) during a long prompt step, which is where the 06:23 traceback ended, so that line alone says nothing.
With the hour at 12:20 this makes about 5,950 synthetic first steps with no hang. At one hang in ~10,000 first steps
that is a ~45 % chance of a clean result, so it says little; it does not clear the first step.

## Exchange stress started 14:46:40 after three setup errors of mine (no GPU work ran in them)

`attempt1-rendezvous/` (14:42): with `--network none` the two processes could not resolve the container's hostname
and waited in torch's rendezvous; stopped. `attempt2-no-network/` (14:44): with the hostname added, oneCCL's
key-value store found no non-loopback interface ("can't find interface to get host IP"). `attempt3-no-ptrace/`
(14:45): on the bridge network, oneCCL failed opening `/dev/dri` handles ("opendir failed"); the server container has
`--cap-add SYS_PTRACE`, which the pidfd handle exchange needs. The runner now starts the stress like the server
(bridge network, SYS_PTRACE, `label=disable`, 8 GB shm, rendezvous at 127.0.0.1). First minute of arm A: 887 steps
(445 prompt-size), 119,745 gathers, byte checks all equal: about 9,000 prompt-size steps per 20-minute arm, half
the context lane's prompt steps since 2026-10-03 in each arm.

## Arm A result (14:46:40-15:06:44 EDT) and amendment 15:10 EDT: clean through 17,518 steps; the end stall was my bug

Arm A ran 17,518 steps (about 8,750 prompt-size, 30-832 rows), about 2.35 million gathers, 274 byte checks, all
equal, kernel log clean. At 15:06:44, four seconds after the arm's 20 minutes were up, both watchdogs reported a
stall, and the stacks show why: rank 0's main thread was in the final `dist.barrier()` (`stress-xccl-allgather.py`
line 116), rank 1's was in step 17,519's `torch.xpu.synchronize()` (line 102). Each rank compared its own clock
with its own end time, so rank 0 stopped after step 17,518 while rank 1 began one more step; a barrier against a
gather never completes. That is my stop condition, not a reproduction (`attempt4-stop-mismatch/`). Both cards'
`gt0/hw_engines` showed no context left on any engine afterwards. Fixed: every 64th step both ranks exchange a
"keep going" flag and stop together when either says stop.

What A says: at the context lane's own rate (one hang in roughly 18,000 prompt steps since 2026-10-03), 8,750
prompt-size exchange steps had about a 60 % chance of being clean anyway, so A alone clears little. **Arm B runs
next, 40 minutes** (about 17,000 prompt-size steps with card 03 under bursty load), A is not rerun.

- **Prediction (unchanged mechanism reading):** if a lagging card 03 being overtaken in a long ring call is the
  cause, B hangs within minutes; C (chunking at 1 MiB) is then run by hand.
- **If B is clean:** A and B together are about 26,000 prompt-size steps, so the exchange, with or without a load
  on card 03, would have a roughly 25 % chance of being clean at the lane's rate. That is not proof but moves the
  search to what only the context lane has (one sequence with prefix-cache hits in align mode, the exact-cache
  overlays, a 262,144-token window), and `scripts/hang-capture.sh` runs beside every context-lane server from now on
  so the next hang leaves stacks from both ranks.

**15:12 EDT, correction to "What is known": ROW_INSTDONE says nothing on these cards.** The 06:23 reading "a kernel
still running on all 32 rows (ROW_INSTDONE 0)" is wrong. The engine-register sampler's 60 snapshots taken during arm
B (both cards, `gt0/hw_engines`) show `ROW_INSTDONE[0..31] = 0x00000000` in every one of them, including the 12 taken
while no context was loaded on the compute engine at all (`CURRENT_LRCA 0`), and the arm A mismatch at 15:06 (both
cards inside spinning oneCCL kernels) reads the same. What still stands from 06:23: job seqno 82 never signalled, no
command error, no page fault, IPEHR at STATE_COMPUTE_MODE (0x61050001), which is where the command streamer sits in
7 of 30 normal busy snapshots on card 03, i.e. just past a kernel launch. So the dump cannot say whether the stuck
kernel was a collective or a model kernel, and no register in it tells the 20-work-group ring kernel apart from a
full-card one. MI_SEMAPHORE_WAIT (IPEHR 0x0e009003) is the most common normal state on both cards (the runtime's
user-mode ring waiting for work).

## Amendment 15:27 EDT (arm B running, 8,220 steps clean at 15:23; no result read): a slot-overwrite reading, and device marks

**oneCCL history.** The public repository (`uxlfoundation/oneCCL`) has the "simple" ring code up to the 2022.0.0
release candidate (`master`, 2026-05-04; the 2022.0.0 tag itself carries only 98 files, no SYCL kernels). Release
2021.15.7 (Arc branch) lists "fixes for LL flag overflow, which may happen to a long running workload (stress test)":
the shared step counter used to grow by every pass of every call and had no wrap handling; since then it grows by
ceil(passes / 4) per call, 31 bits, and a wrap zeroes both ring buffers. At our rates (about 3,500 decode-size calls a
second, a few per call) the 31-bit counter wraps after about a week, not in a 12-minute server life, so overflow is
not the 06:23 cause.

**A cross-call slot overwrite the code allows (reading, not a result).** For two cards, `runAllgather` (ring
transmit, `master`) does, per wire and pass t: write this pass's data with flag `seqNo + t/4` into the peer's slot
`(seqNo + t) % 4`, then spin until its own slot holds the peer's data with exactly that flag (`!=` test, no timeout).
Within a call a card can be at most one pass ahead, so the 4 slots never collide. Between calls nothing holds the
faster card back: once it has the slower card's last pass it can finish, run the next layer, and write the next call's
first pass into slot `(seqNo + ceil(N/4)) % 4`. If that is the slot the slower card has not read yet (its last pass,
`(seqNo + N - 1) % 4`, or `N - 2` for wires idle in the last pass), the slower card then sees a newer flag, spins for
ever, and the faster card spins waiting for it: both cards stuck in a collective, no fault, which is what 06:23 looked
like. With the source constants (20 work-groups of 64 wires, 240 bytes per wire per pass: 307,200 bytes per pass) a
hidden-size gather of r rows takes N = ceil(r / 30) passes, and the slots coincide for N = 2, 7, 12, 13, 18, 23, 28, 29
(31-60, 181-210, 331-390, 511-540, 661-690, 811-870 rows). Against it: (1) the 06:23 step was 443 rows, N = 15, which
does not coincide; (2) every full 832-row prompt step (N = 28) coincides, the context lane runs thousands of them, and
the package's 4,096-row steps (N = 137) coincide for most wires, all without a hang; (3) the slower card would have to
stall for tens of microseconds between its last write and its last read, and preemption by the desktop could not
supply that at 06:23 (the desktop first needed the engine 42 s after the hang began, and then could not preempt it). So
this reading is recorded, not favoured; it would be favoured only if a hang lands on a coinciding size.

**What the next hang must show: device progress marks.** The breadcrumbs say what each card's host issued, not what
each card's GPU finished. `stress-xccl-allgather.py --marks` now has each card's queue, after every gather, copy that
gather's running number into pinned host memory (an 8-byte copy ordered after the gather); on a stall the host reads
the last gather each card completed without touching the stuck queue. Two readings it separates: the overwrite above
(one card has completed exactly one gather more than the other, and the slower card's stuck call has a coinciding N)
and a stuck model kernel (both cards completed the same gathers, nothing collective in flight).
`scripts/run-20261017-xccl-marks.sh` (unit ctx-xccl-marks, queued behind arm B, cancelled if B hangs):

- **M1**, 2 minutes with marks: steps per second against arm A's first two minutes (same seed, same steps).
  Prediction: within 5 %.
- **M2**, marks plus `--mismatch-test` (rank 1 runs one step rank 0 never joins, the arm A end-stall on purpose):
  prediction: rank 0's marks show every issued gather completed; rank 1's show the same completed count as rank 0 and
  the whole extra step issued but not completed; afterwards no context left on either card, kernel log clean.
- **If both hold:** the marks go into `b70-step-breadcrumbs` 0.3.0 behind its own switch
  (`B70_STEP_BREADCRUMBS_DEVICE_MARKS=1`, off by default), with CPU tests, a speed check on the context-lane server,
  and then on in every context-lane run beside `scripts/hang-capture.sh`.
