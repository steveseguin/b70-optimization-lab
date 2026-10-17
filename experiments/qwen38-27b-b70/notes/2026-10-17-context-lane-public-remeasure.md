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

Reading of the coredump (03:00.0): the hung context is the worker's compute queue (`ccs15`, job seqno 82 never
signalled, ring head 680 of tail 840); `ROW_INSTDONE` is 0 on all 32 rows and `RING_ESR` 0, i.e. a compute kernel
still running on every Xe core with no command error and no page fault on this card: a kernel that ran or spun far too
long (a wait on the other card inside a collective would look the same), not a bad address. The scheduler dump puts
it at the first step of a new request (4,603 prompt tokens, one request running, 5.7 % of the KV cache), i.e. a
prompt-reading step after 40 s of idle, not a verify step (the one-launch verify path only runs on drafting steps
past 1,536 keys). The engine's dump of that step (`c28e-server-log-end.txt`): the request had a cache hit of 4,160
tokens (five whole blocks; the recurrent-state groups list four null blocks and then the kept state, the layout the
tail switch builds, though the stock path builds the same one) and the step read the remaining 443 tokens. Every agent
call of the day made a step of this kind (a hit, then a short last piece), so the step itself is ordinary; what the
dump cannot say is whether the hit was one the tail switch had extended.

Correction to the timing: the worker's error came from `_prepare_inputs` waiting on the previous step's
`num_accepted_tokens_event` (the engine schedules one step ahead), and an engine reset is reported when the card has to
switch to new work and the running work cannot be preempted within 640 ms. So the hung work may have started at the end
of the previous request (about 06:22:20, the last step before the 40 s idle, which could be a drafting verify step on
the one-launch path, new today) and only been noticed when the new request arrived. Neither the one-launch kernel nor
the prompt path can be excluded from this evidence. If a hang recurs after the reboot, the next run turns
`B70_FA_VERIFY_ROWS_ONE_LAUNCH` off first (it is the newest GPU code in the stack; ~2 h of traffic today without a
fault before this).

A read-only Codex review of the one-launch path against the kernel sources (vllm-xpu-kernels 2dd55f3; saved as
`data/2026-10-17-context-campaign28/codex-review-one-launch-hang.md`) found **no infinite loop or split-reduction wait
for valid inputs**: the host split count is 1-32, empty splits are skipped, the reduction is a separate launch with no
cross-work-group polling. Only malformed inputs (a key count far above the block table's reach) would give long loops
or reads past the table, and nothing shows such an input. Also noted: the path is chosen for any one-request call of
2-8 rows past 1,536 keys (so a 2-8-token last prompt piece too, the same in a cold and a cached read, as in 0.1.0).
The hang stays unexplained.

Not known: whether the 05:59 kill-induced reset left a card in a state that made this hang likely (the 06:06 health
probe passed), or whether this is an independent hang. This server configuration ran campaigns 26-28c today
(about 2 h of agent traffic) without a fault line.

**Decision (AGENTS.md rule 3): a second fault followed on the same boot, so all GPU work stops and the owner is told
that a reboot is needed.** No further launches, no driver reload, no probe loop. After the reboot: the boot's first
GPU job is the bounded health probe, then campaign 28e again unchanged.

## 10:29-10:36 EDT: same-boot recovery on the owner's rule; the 06:23 leftover was a stuck copy engine

The owner, 10:29: a fault our own software caused is fixed and the work goes on; stop only when the card itself is
faulty and cannot be fixed (AGENTS.md rule 3, new bullet). No fault line between 06:23:03 and 10:31.

- **10:31 health probe failed:** both cards passed their one-card smoke test; the two-card XCCL all-reduce hung after
  topology setup until the probe's own timeout ended it (90 s). Ending it logged, on e3:00.0, `Schedule disable failed
  to respond` (guc_id 11), a device coredump (copied before anything else: `/mnt/fast-ai/bench-results/
  context-longrun-20261016/fault-20261017-1033/`, with the kernel log from 05:50 and the probe log) and a full GT
  reset (`reset done`).
- **The dump:** the probe's copy-engine context on e3 (bcs11) never ran a single command (seqno at its start value,
  LRC head 0 of tail 120). The physical copy engine was occupied by a different context (`CURRENT_LRCA` 0x026d0001)
  executing `MI_SEMAPHORE_WAIT` (IPEHR 0x0e009003). The probe's processes were the only GPU users, so that context is a
  leftover: most likely the 06:23 server's TP1 copy queue, waiting on a peer flag from card 03:00.0 when 03:00.0
  reset (the e3 copy-engine CAT error at 06:23:02 is the same engine). An engine reset had not cleared it; the GT reset
  did. Not a card defect: compute on both cards was fine throughout.
- **After the GT reset** both cards' copy and compute engines read idle with no context loaded (debugfs
  `gt0/hw_engines`, read-only), and the **10:35 probe passed** (both smoke tests, all-reduce 2.0 on both ranks), with
  no new kernel line. Cards usable on the same boot; no reboot needed.
- **What a repeat of 06:23 needs:** `overlays/b70-step-breadcrumbs` 0.1.0 (host only, no device call; 3 CPU tests)
  keeps each card's last 32 steps (shape, the scheduler's and the card's own token counts, accepted count, one-launch
  flag, event record/wait times) and writes them to the server log on a stall over 20 s or a failure. It is in 28f and
  every step-floor arm. It answers which step each card was given last and whether both were given the same one.
  The preregistered response stands: if the hang recurs, the next run turns `B70_FA_VERIFY_ROWS_ONE_LAUNCH` off first.
- **If a TP2 server dies mid-collective again:** expect the peer's copy engine to be stuck the same way; the bounded
  probe detects it (all-reduce hang), and its timeout kill led to the GT reset that cleared it.
- Runner fixes: the start script, the chain and the step-floor runner count fault lines from a start time instead of
  the whole boot (and no longer refuse boot 66541315); all four fault filters now include `failed to respond`, which
  the 10:33 line would otherwise have slipped past.

## Proposal for the owner (public pages; nothing is changed until the owner says)

The skindeep `context-use.html` working-view table compares view sizes measured on one server state (campaigns
21-24, 2026-10-15/16). Since then two exact changes made the server faster without changing any answer (every
call of the 240K stream equal to the earlier runs, server totals equal; notes `2026-10-17-fp8-writing-attention.md`,
`2026-10-17-fp8-cache-tail-block.md`).

- **Option A (recommended): keep the table, add one sentence under it.** "Since these runs the server got faster
  without changing a single answer: the 32K question stream now takes 7 minutes (was 9) and the 64K one 7.4 (was 10)."
  Plus the repair task's figure once campaign 28e has run after the reboot. Cheap, honest, and the table keeps
  comparing like with like.
- **Option B: re-run the whole table on today's server** (7 view sizes x two tasks, about 13 runs, 2.5-3 GPU hours
  in one unattended runner), then replace it. Worth it only if the owner wants the table itself current; the
  ranking of the view sizes is not expected to change (a bigger view is slower because more is read each turn).
- The open-source agents table (12 agents, campaign 20) stays as measured: its times are dominated by how each agent
  works, and it is dated.
