# Hourly time-efficiency review log

Owner mandate 2026-10-17 ("WE NEED TO MOVE WITH URGENCY"). Brief: `HOURLY-TIME-REVIEW.md`; helper: `gpu_time_review.py`. Trigger: hourly at :47 (session cron) plus one immediate run.

Baseline before the first review, **corrected 14:35 UTC**: the first helper version wrongly counted the p56/p55 chain drivers as pure waiters and dropped units that started before its window. Corrected, for the last 12 h (02:34-14:34): 78% in flight, **41% strictly**, excluding model queues waiting on the CPU oracle. Last 2 h: 77%. The reviewer estimates cards 0+1 about 85% busy and cards 2+3 about 12%.


## Review 1, 14:28 UTC: **ACT**

Recommendations and actions taken, 14:30-14:35 UTC:
1. **Controller spin before the futex sleep, packet 56w.**
   - Evidence: packet 57's instrumented arm beat its control on 12/12 prompts by +2.6-4.3%. The miss cycle fell from 33.05 to 30.83 ms. Rank 0 slept about 10 times per token in token mode but once per token instrumented.
   - Action: Codex packet 56w launched, with a 45 min time box. It will be screened A/B against packet 56.
2. **Packet 58b Codex job stuck on stdin since 14:19.** Killed (CPU-only, my own job). Relaunched through a standard launcher (`fn-run/codex-launch.sh`) with stdin from /dev/null and cores 8-15,24-31. Rule: check that the log grows within 2 min.
3. **Screen run conditions and second lane.** Codex screen v2 launched:
   - lane A: cards 0+1, nice 0, cores 0-3,16-19;
   - lane B: cards 2+3, cores 4-7,20-23;
   - a simultaneous A/B helper;
   - timing-mode pass-through;
   - a fault-count-checked review boundary.
4. **HC chain fusion, exact order, packet 60.** Codex launched with a 2 h time box. Expected +4-8%.
5. **INT8 draft-head arm.** Queued as packet 59b once packet 59 lands (packet 59 is still building; do not interrupt it).

STOP-doing items applied:
- the helper's waiter list and window pairing are fixed;
- the screen note no longer claims the owner was asked;
- single-run rankings are replaced by two-lane A/B;
- all Codex launches go through the stdin-safe launcher.

## Review 2, 15:07 UTC: **ACT**

Evidence: in the last 60 min, cards 0+1 were busy about 33 min and cards 2+3 about 6 min. Lane A's 15:01 v1 screen was refused because lane B's rank processes open all four cards. The two lanes agree within 0.1% (packet 56: A 46.79/46.80, B 46.75). Packet 56w measured 48.83 (+4.4%).

Actions, 15:10-15:16 UTC:
1. **Fill idle cards with paired screens.** Not possible as recommended: v2 refuses lean/selected lineages (it needs `suite.py`/`pipeline.py`), and the reviewer's admission assumption was wrong.
   - Fix: Codex **screen v3**, with v1 lineage handling, v2 lanes and nice 0, and **per-lane device masking**, so the lanes run independently.
   - Meanwhile lane A keeps running v1 screens: packet 60, then the 4 packet 59c selections.
2. **Packet 56x:** removes the 1 ms `sleep_for` polling in `SyclDevice::wait()` and similar waits. Built on packet 56w, two variants. Codex launched.
3. **Base for new candidates:** packet 56w (or 56x) from now on. Packet 59c and packet 60 winners will be rebuilt on it before any chain.
4. **Draft-relocation line closed:** no new v2 memory profile for packet 59b. Packet 59c is limited to its 4 screens. Draft micro-kernels close unless one selection beats packet 56 by more than 1%. Codex time goes to the rank-0 out-of-layer gaps and the miss path next.
5. **Disk cleanup:** a Codex job is freeing at least 10 GB from closed packets' regenerable scratch before the record chain.

STOP-doing items applied:
- the helper's commit count is fixed (exact `--since` timestamp; it showed 28 for 2 h, matching git);
- no single-lane v1 screens while the other lane runs (v3 replaces this);
- packet 58b waits for a no-compile window;
- K0-KD reuse for host-only changes is noted for the chain tooling.

## Review 3, 16:08 UTC: **ACT**

Key finding: after packet 61, **rank 1 is the bottleneck**. Its half is 15.2-15.5 ms against rank 0's speculative 13.7 ms; the hit cycle is rank 1's half plus the draft (about 1.9 ms on rank 1). Placement options were ranked on outdated packet 56 timings.

Actions, 16:08-16:15 UTC:
1. **Placement screens (draft rank / target split) as sealed plan fields in screen v3.** Codex job `placement` is preparing four placements of packet 61x, two lanes each: 1-split23 (control), 0-split23, 0, 1. Packet 63's 22/26 premise was wrong-way; it will measure and report, and its draft-HC option still stands.
2. **Lane-aware chain admission:** the whole-host hold is kept only for speed windows. Codex job `laneadmit` is building it for the next chains.
3. **Packet 62 kept minimal:** `control` vs `batch`, once per lane, queued for after the chain. Close the line if the gain is under 0.5%.
4. **Chain time used for CPU work:**
   - three Codex jobs running (placement, laneadmit, p63);
   - helper DEVICE regex fixed (`p\d+\S*`);
   - a post-chain driver (`fn-run/post-p61x-chain.sh`) runs packet 61x submission prep and both dry-runs automatically, then restarts both lanes.
5. **Packet 58b:** gets a planned whole-host slot with no compiles: the boundary before the next chain, or tonight.

STOP-doing items applied:
- re-rank levers from the newest receipts after each win;
- cleanups only with `check_inputs.py` and exact directories;
- `--plan` every job line before queuing;
- bundle placement and packet 62 into the next chain;
- compare within a lane only;
- no record chains on lane B.

## Review 4, 17:05 UTC: **ACT**

Evidence: 83% device-in-flight over 2 h. Cards 2+3 were busy only about 12 of the last 60 min. No Codex job had been running since 16:57, and nothing was queued after packet 64. The 305 s cooldowns outlast the 3-min windows.

Actions, 17:06-17:15 UTC:
1. **Two Codex jobs started:**
   - **packet 65**, routed-expert class occupancy. Experts run at about 150 GB/s against 555 GB/s dense, so likely bytes in flight. Order-preserving, with an in-engine bar of 30% faster, worth about +6% if met.
   - **packet64-attribution**, in-engine event recording on the current line, runnable as a lane-B screen.
2. **Cooldown 305 → 90 s:** deferred to the chain after packet 64, so packet 64 isn't resealed under time pressure.
3. **Packet 64 orchestration:** Codex job `p64orch` (new folder `ops/packet64-orchestration/`) handles screens, the preregistered selection rule (beat `1-production-control` on both lanes, 13/13 exact), fast reseal, all chain pre-checks and the chain. It runs a protocol-correct lane-B companion during the chain (23/25 control and a second 24/24 sample), and every exit path is logged.
4. **Lane driver:** `fn-run/v3-lane3.sh` was replaced (new file, then mv). It logs a sub-10 s pre-device refusal as REFUSED-fast and continues; only a device-stage failure or a fault change stops the lane. A watcher alerts if the lanes haven't started 5 min after the packet 61x post-chain job ends.
5. **Packet 58b one-card:** whole-host block tonight after packet 64's chain, on a driver. A K1 smoke on card 2 only if its plan accepts the lane protocol.

STOP-doing items applied:
- frozen trees are named in every brief;
- the Codex count does not drop to 0 during chains;
- lanes are compared within a lane only;
- no silent driver exits.

## Review 5, 18:07 UTC: **ACT**

Evidence:
- 95% device-in-flight over 2 h; both lanes back to back since 17:22; fault count 2.
- Risks ahead:
  - `/` at 14 GB free (99%), with two Codex builds compiling;
  - both lanes run out of queued work around 19:00-19:20 UTC;
  - 305 s W-window gaps take about 25 min of each about-70-min chain;
  - a CPU-side report failure after drain left a lane-B marker and a screen/v3 latch, blocking packets 66 and 65 at 17:56/17:57 until they were archived;
  - a driver logged `rc=0` for a failed unit.

Actions, 18:05-18:12 UTC:
1. **Disk:** Codex `clean3` archives exactly `packet45-merged3/build` (6.2 GB), `packet38-integrated/build` (3.1 GB) and `packet44-context/build` (3.1 GB) to `/mnt/raid-models/own-xpu-runtime-archive/`.
   - Order: reference check (no active or queued reader), tar and verify (file count + sha256 read back), exact-path remove, `build-ARCHIVED.md`.
   - No wildcards.
   - New Codex builds wait for 20 GB free (`codex-p69-gated`).
2. **Depth-2 MTP:** packet 66's device probe measured a2 = 0.718, class-balanced (`07dd19f3a`); projection +11% (56.6 tok/s). Codex **packet 68** started at 18:06:
   - design note comparing a deeper speculative pipeline with a batched M=3 verify;
   - a device cost probe for the chosen design, as a lane-B screen, committed early;
   - then a lossless prototype with bit-identical per-row target arithmetic.
3. **Rank 1 outside-layer critical path** (target head, draft head prefix, draft attention): Codex **packet 69**, gated on disk ≥ 20 GB. It measures first (diagnostic head site, lane-B screen), then order-preserving target-head and free draft-side candidates.
4. **Multi-improvement chain with 90 s gaps:** Codex **packet 70 record bundle**, on packet 65's executable with packet 64's selection preset:
   - expert choice set by fast reseal from the packet 65 quick screens on both lanes;
   - 90 s gaps for all windows;
   - a resume-capable submission tool;
   - an orchestration that prepares but does not launch the chain.
   - Chain only when the combined screen gain is about 3% or more, or at an overnight boundary.
5. **Lease-release fix:** packets 69 and 70's own screen copies release the lane lease after confirmed drain, before CPU reporting (frozen trees untouched).
   - The coordinator's own drivers capture `rc=$?` immediately after `systemd-run --wait`. The bug: `$(date ...)` in the same echo reset `$?`.
   - A watcher Monitor flags a stale `active-lane-B.json` whose owner pid is dead.

STOP-doing items applied:
- no Codex builds under 20 GB free;
- no single-~1% chains;
- queue work ahead of lane gaps;
- check the unit result rather than the end line.

Addendum, 18:15 UTC: packet 68's design note (`a474a23e2`) showed the following:
- the current engine harvests the depth-1 draft by **pipelining** the two halves;
- packet 66's +11% proxy is unreliable;
- with serial target rows, depth 2 projects about 50 tok/s, no gain.

The coordinator stopped packet 68 before it built that no-gain design (c), and kept its sealed discarded-row cost probe. That probe is queued on lane B after the packet 65 quick screens.

Codex **packet 68b** now builds batched two-row target kernels (weights read once, each row's arithmetic bit-identical to M=1) and an in-engine H(2)/H(1) probe. That ratio decides every depth-2 design: about 1.3 means go, about 1.9 means dead. This is the reviewer's recommendation 2 as written.

## Review 6, 19:08 UTC: **ACT**

Evidence:
- 99% device-in-flight over 2 h (83% over 6 h; no gap over 9 min); fault count 2.
- wide64 wins on both lanes: +5.4% on A, +4.8% on B. The packet 70 chain is due at about 19:35.
- Risks:
  - the queue is mostly duplicate 1–2% screens;
  - only one Codex job was running;
  - disk is under 20 GB;
  - nobody is building the depth-2 engine;
  - there were 4 driver, environment or marker refusals in 70 min.

Actions, 19:08-19:15 UTC:
1. **Disk:** Codex `clean4` archives exactly `packet17-detmath/build/wa-reference` (14 GB of old test vectors), using clean3's procedure: reference check, verified tar, exact-path removal.
2. **Depth-2 engine:** Codex **packet 71** started in parallel with packet 68c:
   - pipelined two-card design with dependent batched verify rows;
   - per-class M=2 or serial-M=1 kernel table;
   - lossless restore;
   - smoke and screen plans.
   - The analyzer constants are updated to 52.90 / 16.45 / 28.37, with go/no-go at +8% over the current record (break-even about H(2)/H(1) ≤ 1.45). Experts come first in packet 68c.
3. **Packet 67 lane A:** `fn-run/p67-stop-rule.sh` runs packet 67's `compare.py` when lane B finishes. If no lane-B candidate is ≥ +1.5%, it writes `packet67-roofline/screen/evidence/STOP`; the runner checks STOP before any lease.
4. **Driver churn:** Codex `lanequeue` builds `ops/lane-queue/`. It is one robust per-lane queue that:
   - re-reads its job file at boundaries;
   - keeps a closed env, with extra variables passed only via `--setenv`;
   - captures rc and the unit Result immediately;
   - stops on REFUSED-fast, stale markers, latches or fault changes;
   - supports PAUSE/STOP files;
   - has a plan mode.

   The packet 68c probe jumps lane B's queue now via `fn-run/laneB-p68c.sh`, which runs right after packet 67 lane B, then packet 69.
5. **Packet 58b one-card:** a one-shot whole-host slot is booked at about 21:55 UTC (cron).

STOP-doing items applied:
- no new hand-written drivers once lane-queue lands;
- full candidate grids are no longer forced on the second lane (packet 67 lane A gated);
- the decisive probe goes first;
- 3+ Codex jobs;
- the packet 70 launch is watched at about 19:35 (`lanes-v3.log` "packet70 decision").

## Review 7, 20:07 UTC: **ACT**

**Evidence:**
- The helper's "100% in flight" was wrong. Lane B had done no device work since 19:28.
- **Cause:** p67 B-6 finished its suite. Its teardown was then refused at 19:33 by the packet 70 K2 window's undrained `teardown-state.json`, before `transport.stop()`. Its ranks sat idle on cards 2+3 holding the lane-B lease.
- The packet 70 chain's W2m (whole host) had been waiting since 20:05. It would have failed at about 20:30, either on its deadline or on the stale marker.
- No Codex job had run since 19:40. Fault count 2.

**Actions, 20:08–20:13 UTC:**
1. **Recovery, in the order the reviewer gave:**
   - **(a)** Stopped the CPU-only lane-B waiters (lanes-v3 bash pids by pid, `laneB-p68c`, `lanequeue-B`). The screen unit was untouched.
   - **(b)** Archived `active-lane-B.json` (pid 474623) to `coordination/reviewed/` before stopping, so W2m would not refuse after the flock released.
   - **(c)** Wrote `!` into the worker's stop pipe (`/proc/474650/fd/5`; both ranks' fd 3 is the same pipe). `pipeline_cancel_check` gives a cooperative rank stop.
   - **(d)** Screen, worker and ranks exited within 7 s. The screen/v3 latch was archived after review: fault lines 2, no render-node holders.
   - **(e)** **W2m was admitted at 20:09** and the chain proceeds. Lane B restarted under a single owner, `lanequeue-B2`: the p68c probe first (via `fn-run/p68c-probe-wrap.sh`), then p71 smoke, control, candidate and control-repeat. p69 lane-B jobs were dropped from the queue (rec 4).
2. **Root-cause fix:** Codex `screenv4` builds `stage2/screen/v4-lanes/`:
   - a refused teardown gate still stops and drains the worker's own ranks under `teardown.lock`;
   - CPU post-processing comes after drain and lease release;
   - tests;
   - a chain-side patch template that marks drained once owners exit, before CPU post-processing.
   
   Frozen and queued trees are untouched.
3. **Stuck-screen Monitor:** flags an active `screen-*` unit whose output has `failure.json` or `drain-error.json`, or no file written for 8 min.
4. **Queues:**
   - **p67 closed:** all four candidates slower on lane B (−6% to −22%); lane A stopped by rule. Closeout and DO-NOT-REPEAT row written (`1864eb9f9`).
   - **p69:** all 8 screens on lane A via `lanequeue-A`, armed on `packet70-chain-k2fix` finishing. Lane B will run only control, best lane-A candidate, control.
   - **58b:** PAUSE both queues at 21:40 (cron), slot at 21:55.
5. **Next lever:** Codex **packet 72**:
   - an in-engine achieved-bandwidth table first (from `sites.jsonl` and real tensor types);
   - then wide64-style occupancy only for classes ≥ 0.3 ms per half below roofline;
   - lane A full grid; lane B control/best/control.

**STOP-doing items applied:**
- one owner per lane (lane-queue);
- before archiving a stale record, check every active screen for a `failure.json` it caused;
- "unit active" ≠ "cards busy";
- no full grids on both lanes;
- no kernel rewrites without in-engine bandwidth evidence;
- Codex count above 0 during chains.

## Review 8, 21:07 UTC: **ACT**

**Evidence:**
- Device in flight 90% over 2 h (91% over 6 h).
- **Since 19:00, 10 of 17 device units plus 4 REFUSED-fast starts failed before or at rank startup.** All were software or packaging bugs (fault count stayed 2):

| Packets | Failure |
|---|---|
| p72, p73, p74 | lane-A window policy |
| p69 | head row stride |
| p71, p71b | packaging, router config |
| p58b | GPUActive accounting |
| p58c | allocation lifetime |
| p70 | K2 validator |

- Only one Codex job was running, with about 2 h of screens queued.
- The p69 grid was queued on both lanes.

**Actions, 21:07–21:12 UTC:**
1. **Packet 75 record bundle:** Codex `p75`. One binary from packet 70 sources with the packet 74 packed-dense views and packet 73 HC/experts views as independent choices. Orchestration reads both lanes' receipts, selects exact both-lane winners, fast reseals with 90 s gaps and writes `ready.json`. Uses the shared, pinned v4 wrapper and a full-shape dry run.
2. **Queue A trimmed** to p74, p73, p72-r2. The `p69-quick-A-r3` duplicate grid was removed; lane B runs the p69 r3 grid, and a ≥ 1.5% winner gets a control/best/control confirmation on A.
3. **Rank-1 host residual (1.61 ms per half, about 11%):** Codex `p76`. Attribution first (device idle / cross-card transfer wait / host issue), then a scheduling-only fix (device-side waits, recorded command lists or moved syncs), screenable with v4.
4. **One-card:** Codex `p58d` (running) fixes the allocation lifetime bug. The follow-up for 90 s gaps, starting at lane boundaries only, and measured-memory concurrency for the exactness windows is deferred to the next 58 brief, after p58d's evidence. p71b is deprioritized behind p74/p73/p75 (marginal at about 1.43 vs 1.45 break-even).
5. **Brief rules** (memory note `cpu-plans-must-exercise-device-startup-paths`):
   - a shared, pinned v4 wrapper, never per-packet modified copies;
   - a full-shape CPU dry run through real admission, imports, allocation and config paths;
   - selection-key consumer tests;
   - a device smoke for new engine paths.

**STOP-doing items applied:**
- no duplicate full grids on both lanes;
- 2+ Codex jobs while screens are queued (now p58d, p75, p76);
- 90 s gaps in new chains;
- p71b deferred;
- lane-B best jobs only after lane-A results (`laneB-followups`).

## Review 9, 22:03 UTC: **ACT**

**Evidence:**
- Device busy 89% over 2 h and 95% over 6 h. Since 21:07, only 1 of 4 device jobs failed, and that was its report step (packet 77, `KeyError 'binary_sha256'`; the device run passed).
- Lane B idle 21:44–21:56 with packet 77 ready.
- **Lever weakness:** every result since 21:07 is under 1%:
  - p74: −0.8% to −2.9%;
  - p69 r3: +0.82%;
  - p73 `hc-wide`: +0.98% on A;
  - p73 experts2: slower.
- **Packet 77's control arm** shows the hit cycle = draft 1.72 ms + rank-1 half 14.18 ms, serialized on rank 1. Rank 0 (13.61 ms) idles about 2.3 ms per hit, and rank 1 finishes last in 97 of 108 cycles.

**Actions, 22:03–22:10 UTC:**
1. **Draft on rank 0:** Codex **packet 79** on packet 75's bundle sources (composes with `hc-wide`):
   - existing reverse handoff;
   - prefix head kept on rank 0;
   - placements `0-split23`, `0` and control `1`, with the real per-card memory census;
   - a full-shape dry run including the handoff state machine;
   - screens lane A grid, lane B best.
   - Projection: about +5% at 23/25 dr0.
2. **Record path:**
   - `packet72-quick-A-r2` removed from queue A (lowest expected value).
   - Packet 73's lane-B `hc-wide` confirmation is running. When it ends, the waiter runs packet 75's orchestration. If `hc-wide` confirms (≥ +0.5% over both B controls), the coordinator launches the packet 75 chain on lane A after packet 76-A (about 22:28) for about 54.6.
   - Any packet 76 winner goes to the next bundle with packet 79.
3. **Lane-queue REPORT-FAILED:** Codex `lqreport` adds a non-blocking outcome when the device passed, the lease was released, faults and latches are unchanged, and only the report failed. Packet 77's `report.py` was already fixed by the coordinator (`b6037a838`); its lever table is in `attribution-summary.md`.
4. **Next kernel lever:** packet 78 (`route` top-k about 19.6 µs per layer; HC norms) is building. An exact-order expert-throughput packet follows after packet 78; experts are still about 31% of reference (1.88 ms per half of headroom).
5. **One-card:** skip the 58d run (58e replaces it). Packet 58e's first windows go into queue A after the packet 75 chain, under its measured admission.

**STOP-doing items applied:**
- report-only failures no longer block (once `lqreport` lands);
- marginal levers (p72-r2) removed;
- p71c is lane-B filler only;
- placements re-ranked from current timings (packet 79);
- 3 Codex jobs (p58e, p78, p79) plus `lqreport`.

## Review 10, 23:09 UTC: **ACT**

**Evidence:**
- 98% device-in-flight over 2 h; fault count 2.
- Depth 2 closed (p71c: 28.17 vs 52.90 control).
- **p79 (draft on rank 0) lost on A:** 23/25 −2.3%, 24/24 −1.3%; misses +2.1 ms. Packet 45 had already measured this. The projection ignored the draft's dependency on rank 1's final state.
- The p58f waiter (lane-A queue only) would have raced the p80 record chain at about 23:45.

**Actions, 23:10–23:15 UTC:**
1. **Chain before 58f:**
   - The p58f waiter was stopped; it was CPU-only and had not paused lane A.
   - `fn-run/p80-prep.sh` waits for p81-A and Codex p80, writes PAUSE-A, runs p80's one-shot orchestration and `verify_ready.py`, and reports.
   - The coordinator launches the p80 chain, then 58f after the chain exits.
2. **Lane B work:** `laneB-followup-p81` auto-appends p81's lane-B best job after p81-A is DONE. Future packets (p83) must ship full-grid job files for both lanes.
3. **norm-fused stays out of p80:** at launch, the coordinator reseals with `--norm production` (p80's `fast_reseal.py` supports it), whatever p78-B's composite result is. route-fast goes in only if it is confirmed alone.
4. **route-fast standalone lane-B confirmation skipped:** p78's B job builder would collide with the running p78-B outputs, and it is only +0.54% on A. It stays out unless confirmed.
5. **p79 closed** (note + DO-NOT-REPEAT, `00af674d8`). Codex **p83** works on draft bytes: a census first, then preregistered candidates (a lower-bit draft head prefix, or a smaller prefix N from independent text), with acceptance measured and full-grid job files for both lanes.

**STOP-doing items applied:**
- waiters must see chain and packet58 units;
- no composite confirmations that include a known-negative part;
- check dependencies and the ledger before opening a lever (memory updated);
- no hand-appended lane-B follow-ups.

## Review 11, 00:05 UTC (2026-10-18): **ACT**

**Evidence:**
- 98% combined in-flight. But lane B was idle 23:16–23:37 (21 min), and both queues are nearly dry.
- Packet 85's ranked lever list (23:52) had not been acted on. Only one Codex job was running.
- Packet 83 closed (all negative); packet 81 neutral; packet 79 lost.
- p84's brief still composes closed levers (p81 experts, p83 draft heads).

**Actions, 00:06–00:12 UTC:**
1. **Codex packet 86: a DIAGNOSTIC-ONLY limiter screen** for the experts (2.73 / 2.75 ms per half) and the rank-1 HC gates (1.198 ms).
   - Views: `exp-nodeq`, `exp-constgrid`, `exp-onecached`, `hc-nodeq`, `hc-constscale`.
   - Labelled non-exact, guarded out of every bundle, chain and submission path, with every safety check intact.
   - Lane B. This supplies packet 85's required ALU/latency explanation before any more expert or HC builds.
2. **Codex packet 87 (CPU, 30 min):** a model check of splitting the target-head vocabulary rows, or the draft prefix head on hits only, into rank 0's 0.544 ms hit slack, with handoff costs. Seal a design only if ≥ +0.5%; otherwise close.
3. **p84 narrowed at orchestration:** pin `experts=wide64` and the draft head to production (p81 and p83 closed). Validate p80 + `rec-parallel` (± route-fast) with one lane-B control/candidate/control screen before any p84 chain; chain only at ≥ +0.5% on lane B.
4. **Lane-A work for after 58f:** p86's lane-A grid or p84's chain, queued as soon as either is ready (`p80-launch.sh` unpauses lane A after 58f).
5. **≥ 2 Codex lever jobs:** p84, p86 and p87 are running. The obsolete `laneB-followups-generic` waiter was stopped; it keyed on non-existent p83 file names.

**STOP-doing items applied:**
- no closed levers in bundles;
- no more draft-bytes, relocation or expert load-count packets;
- waiters keyed on the real job names;
- per-lane idle accounting (gpu_time_review per-lane: TODO);
- act on lever rankings within minutes.

## Review 12, 01:08 UTC (2026-10-18): **ACT**

**Evidence:**
- 58f-b's KD window failed at 01:04 at the native `p28 extent/alignment` check after the full 48-layer load. It left `screen/v3/teardown-state.json` undrained and a stale lane-A marker.
- That undrained record made `p84s-B-3-control` refuse at its teardown step ("previous teardown incomplete; coordinator required") and stopped lane B. Both lanes idle from 01:04; 0 Codex jobs (p82b had finished at 00:54).
- No new GPU fault lines (count 2). Prior 2 h: 100% combined, lane A 94%, lane B 73%.
- Root disk 14.8 GB free; the p84 chain needs 14.32 GB at admission.

**Actions, 01:05–01:12 UTC:**
1. Reviewed and archived the 58f teardown record, both stale lane markers and the lane-B screen latch to `coordination/reviewed/` (owner pids gone, no render holders, fault lines 2). Removed PAUSE-A; started `lanequeue-B5`. Both lanes running p86 views from 01:06.
2. Moved the refused B-3 evidence to `p84s-B-3-control-refused-58f-undrained` and requeued the closing control at the head of lane B (it runs after `packet86-production-B`). Queued `packet82b-grid-A` on lane A as filler after the p86 lane-A views.
3. Disk: archiving packet 45's closed GPU window trees (≈6 GB) to `/mnt/raid-models/own-xpu-runtime-archive/packet45-merged3/` with a per-file SHA manifest, full content verification, then deleting them; the one file later packets reference (`speed6-…-cards01-gpu/K2/run0/dispatch-measured.json`) stays on root.
4. Codex `p58g` (fix the one-card p28 refusal from the real arena rows; full-shape check of every submit-time extent check; refused-before-compute children drain their record; lane-A cores) and `p90` (preregister exact expert/HC candidates per possible p86 verdict; build the top two).
5. Watcher re-armed: all lane events, stale markers, latches, undrained teardown, fault lines, Codex exits.

**STOP-doing items applied:** state from `ps`/event files, not memory; one-card chains only after a full-shape check of the real submit-time checks; a lane-A failure must not hold the shared teardown record; p82b runs only as filler; check root free space against the next chain before builds.

## Review 13, 02:05 UTC (2026-10-18): **ACT**

**Evidence:**
- Last 2 h: 98% combined device use (lane A 95%, lane B 84%; one 7-min lane-B gap). Fault count 2; root 18 GB free.
- The compile-turn guard in packets 90/92/93/94 matched any `python3` under `/packet58g-onecard/` as a "foreign compiler". Once 58g's device run started (after the p84 chain), p93 and p94 compiles would have waited out the whole 58g chain and hit their 3600 s deadline.
- p86 `exp-nodeq` (lane A) bounds expert dequantization at about 1.14 ms per half on rank 1 (≈3 tok/s ceiling); `hc-nodeq` about 0.36 ms; `hc-constscale` about 0. p90 E1 `exp-halfcache` screened +0.25%. The remaining p86 views decide the next expert design but sat behind 60–75 min of p91/p92 screens.
- Three record chains used about 47% of lane A in 6 h for sub-1% increments.

**Actions, 02:06–02:10 UTC:**
1. Patched `compile_turn.py` in p93 and p94: dropped the packet58g path match; the guard now also waits while `hold-lane-B` or a whole-host lane marker exists. The running waiter script was not edited.
2. Lane B reordered: p90 grid, then the four p86 views, then the p91 grid and p92 grid.
3. Codex p95: E3 grid-prefetch and E2 scale-cache (with an arena-fit proof), optional E5, sealed with single-candidate and full grids for both lanes, ready for the p86 verdict.
4. Lane A: queued the p91 A grid behind 58g. A new `laneA-release-after-58g` waiter removes PAUSE-A after any clean end (fault count 2, no marker, drained, no latch), not only rc=0; otherwise it alerts.
5. Chain policy: the next record chain only when a composed lane-B screen beats the record line by at least 1.5%, or two or more confirmed levers are ready (p91 plus any p90/p92/p93/p94/p95 winner).

**STOP-doing items applied:** no packet-path substring matches in lock/turn checks; no rc=0-only lane hand-backs; diagnostics that choose the next big lever go before composition screens; no record chain per sub-1% increment; no second-lane copy of a diagnostic whose signal is far above control drift.

## Review 14, 03:10 UTC (2026-10-18): **ACT**

**Evidence:**
- Last 2 h: 98% combined (lane A 92%, lane B 72%). The lane-B gap 02:27–02:49 was a 6-min stale-marker refusal plus a 15-min host-memory hold for one-card 58g. Fault count 2.
- Lane A was about to run dry after `packet91-A-grid-4` (about 03:15) while lane B held about 1 h 45 min of serial work.
- p93 `head-transpose` B grid +0.86%; its microbenchmark saving (−0.384 ms) became −0.177 ms per rank-1 step in the engine (about 47% transfer).
- p91 lane A: route-fast +0.21%, rec-both-plus +0.05%, combined +0.65%.
- p97 chain storage was 3.06 GB short.
- Records this hour: 2-card 55.687 (p84), first 1-card 24.339 (p58g).

**Actions, 03:11–03:13 UTC:**
1. Queues rebalanced:
   - Lane A: p91-A-grid-4 → p93-A-confirm-B2 → p94-A-grid → p92-A-grid.
   - Lane B: p95 E3 grid (running) → four p86 views → **p91 3-view B confirm** (the combined view is +0.65%, so it replaces the 5-job B grid).
   - Removed the p91/p92/p94 B grids. Both lanes plan clean.
2. Codex p97b: the composite screen on both lanes is the two-lane confirmation; sources qualify on one exact first-lane win vs both controls (acceptance unchanged); leave-one-out generator; explain p91's "rejected" status.
3. p86 diagnostics now run right after p95 on lane B; the next expert mechanism will be briefed from their result.
4. Disk: the record-chain trees in `own-xpu-runtime-results` are referenced by later packets and by the shared screen wrapper (directory-level paths), so they were **not** blindly archived. Codex `disk` job: reclaim ≥ 6 GB of verified-unreferenced bulk with the packet-45 procedure and re-plan every queue afterwards.
5. Codex p98: screen/v5-bracket, one model load per bracket (A/B/A/B, full state reset, per-view incident64 + 13/13, memory admission before the lease). 2-view smoke first.

**STOP-doing items applied:** no second-lane standalone grids under +0.5%; no lane running dry while the other holds > 30 min; diagnostics before composition; no edits to sealed files after a chain. p94's grid still contains the closed `hc-normfuse+weightcache` view (sealed; about 5 min cost, accepted).

## Review 15, 04:08 UTC (2026-10-18): **ACT**

**Evidence:**
- Last 2 h: 99% in flight (lane A 85%, lane B 71%); no new fault lines; all jobs clean.
- Root margin over the p97 chain requirement was about 0.12–0.3 GB and shrinking (about 108 MB per screen).
- Without-93 (p91 + E1) composite: lane A 55.913 vs 55.505 / 55.532 (+0.69%), lane B 56.065 vs 55.652 (closing control done 04:08).
- The earlier full composite (with p93) froze a source set while p93's lane-A confirmation was failing (−2.8%), which cost about 18 min plus a leave-one-out bracket.

**Actions, 04:05–04:12 UTC:**
1. **Disk:** archived regenerable bulk of closed screens (p76/p78 driver caches and input bundles, packet86 non-JSON files) to `/mnt/raid-models/own-xpu-runtime-archive/screen-bulk-20261018/`, with full verification before deletion; every JSON/JSONL receipt kept. Codex `opsclean` is writing a standing post-screen cleanup tool (closed packets only, plan/run modes).
2. **Record path:**
   - new p97 decision `f1e5d7f47fc0fe54` pinned `head=production` (route fast, rec-both-plus, wide64+halfcache);
   - its composite brackets run first on both lanes;
   - `p97-launch` evaluates that exact decision when both finish, then holds lane A, runs `verify_ready` and launches `packet97-chain` only if ready;
   - p94/p92 grids moved to lane B (single lane each) after the p98 smoke.
3. **p99:** its single-card microbenchmark ran first: every IQ2 table relocation/compaction is slower (1.24–1.78×), so p99 is closed with no screens. p100 (down locality) continues.
4. **p101:** re-test of packet 69's shelved draft-geometry win (+0.82%) under the one-lane qualification rule.
5. **opsclean:** also amends the p97 rule so a completed exact loss on lane A excludes a source; sources are re-checked at decision time.

**STOP-doing items applied:** no source set frozen while its record-lane result is pending or negative; no p93x follow-up (head=production for the record line); chain launch requires the storage check to pass; cleanups become standing, not emergencies; device microbenchmarks before long CPU programs for kernel ideas.

## Review 16, 05:05 UTC (2026-10-18): **ACT**

**Evidence:**
- Last 2 h: 97% in use (A 75%, B 79%); 6 h 99%. Fault count 2. Root 18.8 GB.
- Lane B runs dry at about 05:14; no sealed work behind the p101 B bracket until Codex finishes (p100b about 05:54, p102 about 06:54, p98c about 07:15).
- The record path lost about 29 min at 04:24–04:53: the launcher's rule refused twice before Codex p97d changed it.
- p101 pinned packet 97's mutable `selection.json` and needed a reseal. p99/p100 pin `packet97-record-bundle/evidence/object-identity.json` (still matching).
- In-engine gaps between kernels are about zero, so launch-count fusions do not pay (p94 −23%).

**Actions, 05:05–05:08 UTC:**
1. `p102-micro-waiter` and `p87t-micro-waiter` (60-min deadlines) queue the p102 / p87t microbenchmarks on lane B the moment their job files exist and plan cleanly on a temp copy. The watcher now alerts on an unpaused lane with an empty queue for 2 min.
2. Codex p87t: device microbenchmark of the head-split transfer legs (5,120-byte final-mix D2H/H2D, best-index return, ordered waits, overlap with compute), then re-run packet 87's model. It proceeds only at ≥ +0.5% (the model says +1.08% head / +0.77% draft prefix before transfer costs).
3. **Next decision rule check:** before arming the next chain launcher (p101/p102 winners), run `orchestrate.py` on the CPU against the evidence present, including the lane-B drift case.
4. **Pin audit:** after p97-post finishes, rerun `audit_parent_pins.py` before queuing p100/p102 screens. Briefs now forbid pinning another packet's orchestration outputs.

**STOP-doing items applied:**
- no queueing jobs their own packet marks as blocked (p100's grid needed its real-route microbenchmark);
- no evaluator-gated launchers armed without a CPU dry evaluation;
- no pins on mutable parent files;
- no launch-count-only fusions;
- microbenchmarks before full gates for kernel ideas.

## Review 17, 06:05 UTC (2026-10-18): **ACT**

**Evidence:**
- Last 2 h: 98% in flight (A 71%, B 76%); 6 h 98%. Fault count 2. Root 18 GB.
- Lane A lost 12 min at 05:26: the p100 A-confirm was queued before the lane-B grid it reads had finished.
- One p97 chain needed five launcher attempts (rule refusals, KD failure, frozen-folder pointer).
- Lane B idle since 05:58 with p104's micro still being edited (correctly held).
- p103's startup sweep finishes about 06:38 and the p97 chain about 06:52.
- Two Codex commits swept other jobs' staged files (944963d2c, 6fbb16b9d).

**Actions, 06:06–06:09 UTC:**
1. **`p103-handoff` waiter:**
   - after Codex p103 exits, it queues p103's lane-B composite at lane B's head once it plans clean;
   - when `packet97-chain-b` ends cleanly (fault count 2, no marker, drained, no latch), it queues p103's lane-A composite (if available) and removes PAUSE-A, without waiting for CPU-only post-chain work.
2. **p105 head split:** its first device run will be a small smoke (one prompt, 64 tokens), not the grid. The coordinator will add or request it when p105 lands.
3. **Codex p106 (draft split, +0.77% modeled):** copies p105's transfer code after p105's byte gates commit; smoke first, then one combined lane-B grid.
4. **Ordering and launcher rules:**
   - jobs that read another lane's result are queued only by a waiter on that result;
   - chain launchers take the folder from the newest `ready.json`;
   - the lane-B hand-off from p103 is pre-armed.
5. **Codex p58j:** ports down-tile16, route-fast, rec-both-plus and E1 (if the layout admits it) to the one-card line, with a one-card bracket and a fresh-folder chain plan for a whole-host gap after the 2-card chain.

**STOP-doing items applied:**
- no cross-lane-dependent confirms queued directly;
- no hard-coded chain folders;
- no lane hand-offs waiting on CPU-only work;
- no new cross-card path at full grid size first;
- briefs require `git commit --only -- <paths>`.

## Review 18, 07:05 UTC (2026-10-18): **ACT**

**Evidence:**
- Last 2 h: 99% in flight (A 76%, B 59%). Lane A idle since the p105 failure at 06:55.
- p103r is re-running its full 512 × 11 startup gate (about 07:32), so its composite lands about 07:50.
- p103's storage check needs 19.00 GB and failed at 18.98 GB; root is 16.9 GB.
- p105x found the head-split bug: a request reset zeroes rank 0's `active` flag, so the suffix argmax is skipped. The 12-prompt suite has only one suffix-winning token.
- Fault count 2.

**Actions, 07:05–07:09 UTC:**
1. `p104b-confirm-waiter` queues p104b's lane-A confirm only after the B grid ends with a winner. The B grid showed no real gain (+0.01% at best; p104b closed). The confirm had started before it could be pulled and is allowed to finish (no GPU-process kills); the waiter rule now requires ≥ +0.5%.
2. **Disk:** archived closed screens (p76/78/79/81/83/84s/86) and the submitted p80/p84 chain folders, with full verification. Codex `disk4` reclaims ≥ 4 GB from old closed build trees (pinned files kept).
3. **Codex p105b:** the reset fix for p105 and p106, a device split-argmax microbenchmark with forced suffix winners, ties and NaN, then an all-12-prompt × 64-token smoke, then the grids. Gate receipts per composition so dead sessions resume.
4. **Codex p58k:** a one-card single-launch screen (one load per arm, about 10–12 min each) so the one-card port fits a real gap.
5. **Codex p107:** the first specialised per-layer subgraph experiment (one GDN and one QSA layer, exact, microbenchmark-gated at 80–160 µs per layer).

**STOP-doing items applied:**
- no exhaustive startup sweeps before screens: gate the views that will run first;
- per-composition gate receipts;
- 12-prompt short smokes instead of one-prompt smokes;
- every confirm has a waiter;
- storage checks before chains.

## Review 19 (2026-10-18 ~08:07 UTC): ACT

Lanes stopped since 08:02 (p103 composite A-0 "mmap failed" latch blocked both); last 2 h lane A 67%, lane B 36%; p104b, p107, p108, p58k all closed this hour with no gain.

Actions:
1. Lanes back (08:04): reviewed and archived the latch and dead marker (owner dead, no render holders, locks free, teardown drained, fault count 2), pulled all six p103 composite jobs, restarted drivers `lanequeue-A11`/`-B8`; the p106b B grid started 08:04. Root cause is not FUSE storage: `read_screens.py` sets `RLIMIT_AS=8 GiB` at import and `composite_jobs.validate()` imports it in the device-launching process. Codex **p103x** (40 min) fixes it, adds a getrlimit gate at the exec point, reseals minimally and emits fresh-suffix composite proposals.
2. Record path: a launch waiter (orchestrate → ready → PAUSE-A → verify_ready → chain_command) will be re-armed for the p103x names; the B composite is queued first and the A composite only after B-0 has finished model load (smoke-first). The p106b A-confirm waits behind PAUSE-A while the chain holds cards 0+1.
3. p109 not re-briefed: at review time it had already finished the census (636/628 launches per half, 72 removed per half), passed GNU+Intel byte gates including nonfinite inputs, and is sealing a v5 one-load in-engine bracket, which is a stronger kill gate than a micro.
4. Codex **p110**: fresh per-class roofline table from the p107 QSA device table plus a new current-mode GDN-layer timing micro (lane B), re-ranked levers.
5. Lean next bundle (p103 + p106b winner, two compositions, device load smoke first) is briefed when the p106b B grid reports (~08:25).
Also Codex **opslatch**: a software latch with an unchanged kernel fault count stops only its own lane (lanequeue.py only; new fault lines still stop both).
Lane A's 08:25–08:45 idle gap (waiting for p103x) runs the p58n one-card tile16-only screen (whole host, ~35 min); this delays the p103 composites by ~20 min but uses otherwise idle time.
STOP DOING acknowledged: long CPU qualification before a first device load, sealing all 512 compositions, optional extras in handoffs, kernel briefs from historical class tables without a kill gate, cross-lane halts on software failures, lane B dry while waiting for Codex.

## Review 20 (2026-10-18 ~09:11 UTC): ACT

2 h: lane A busy 46%, lane B 49%; the packet 103 composite beat its controls by ~+3% on both lanes (A 57.55 vs 55.61/55.76; B 57.29 vs 55.74/55.59, all exact).

Actions:
1. Chain first: nothing queued ahead of the packet 103 chain on lane A; `p103x-handoff2` runs orchestrate → ready → PAUSE-A → verify_ready → chain_command; `p103-post` prepares the submission with packet 103's own tools and both dry-runs, then the coordinator submits. Future handoff templates will run orchestrate's CPU tests during the last bracket arm (noted; the running waiter is not edited).
2. Codex **p115**: expert gate/down kernels in their own SYCL device image with the module-wide large-GRF AOT option; revive p95 E3, p99 IQ4 SLM, p102 V4 batch2/shared and implement E5; gates: zero-spill report, ≤0.85× micro in both orders, v5 bracket prepared in parallel.
3. v5 one-load brackets are the default in new kernel-only briefs (p114, p115).
4. Codex **p113i** (v5 integration prepared while the micro ran) was launched, then stopped at 09:15 when the p113 micro showed 1.5× slower (closed). Bundle 6's lane-B composite (`p111r`, candidate fusion + head split) fills lane B during the chain.
5. Codex **disk5**: one pass to ≥ 40 GB root free via verified RAID archives of exactly named, unreferenced closed data. Before it: old Codex sessions 2026-05..08 moved to RAID (verified, root 20 → 31 GB).
STOP DOING acknowledged. Also fixed: a failed transient `screen-<job>.service` blocks re-running the same job name (REFUSED-fast with no journal line); reset-failed before re-queueing (memory updated). The smoke-first gate will key on `drm-memory-after_load.txt`, and handoffs that set PAUSE-A will raise an ALERT and remove it on refusal, in the next template.

## Review 21 (2026-10-18 ~10:08 UTC): ACT

2 h: at least one pair busy 96%; lane A 54%, lane B 65%. `packet103-chain-a` failed at WS 09:53 (drain-cooldown negative sleep, triggered by a lane-B teardown 24 s earlier; no device work, faults 2); fresh `packet103-chain-b` launched 10:04:41 with PAUSE-B held so no cross-lane teardown lands inside a window's cooldown.

Actions:
1. Lane B queued behind the pause: packet116 micros (×2) queued at 10:04; `p117-queue` waiter appends packet117's micros as soon as its Codex job exits (outputs are queued only after the producer exits). v5 brackets are queued by the coordinator when each micro's qualification passes. Packet118's smoke/composites go to lane B's head when they land.
2. No separate bundle 6 (packet111r) chain: its lane-A composite still runs after chain-b as fallback evidence; bundle 7 (packet118 = bundle 6 + packet114 prefix, with the drain fix) is the next chain candidate (≥ +1.0% vs bundle 5 on both lanes).
3. Packet118's brief already moves orchestrate's CPU tests into preparation; a follow-up will pre-register a second fresh chain folder so a failed chain restarts in a minute.
4. Next kernel brief targets the routed experts (1.76 ms per half above floor) with a mechanism distinct from packets 95/99/102/104/115, once packets 116/117 report.
5. Codex **opsdrain**: `lanequeue.py` waits until 61 s after the latest shared teardown before starting any job, so the frozen wrappers never enter the buggy cooldown loop (chain runners are still protected by pausing the other lane).
STOP DOING acknowledged (no full orchestrate re-run on idle cards when only the folder changes is noted for the next chain; Codex v5 prep stops as soon as its micro fails).

## Review 22 (2026-10-18 ~11:08 UTC): ACT

2 h: at least one lane busy 99%; lane A 79%, lane B 43% (lane B paused for chain-b 10:04–10:55). Record 57.55 submitted 10:57 (`cmvdpmbbo0022rf017ynt8i35`). Bundle 6 lane-A candidate 58.225 vs 57.570 (+1.14%).

Actions:
1. `p118-chain` waiter armed: after both bundle 7 composites → `orchestrate.py --evidence-only` → ready → waits (≤ 75 min) for lane B's sealed queue to drain → PAUSE-A+PAUSE-B (packet 118's `drain_gate.py` still lacks the fix) → ≥ 61 s after the last teardown → `verify_ready.py` → chain_command; then releases the pauses when clean and runs packet 118's own `prepare_submission.py` + `submission.py` dry-run/server-dry-run (no real submit). On a verify refusal it removes the pauses and alerts.
2. Codex p121 stopped and closed (its own top lever ~0.017 ms per step, ceiling ~0.66%).
3. Codex **p123**: move only layer 24's mixer or FFN to rank 0 (slack recomputed first on the bundle 7 line; v4 grid, drain fix required). The routed-expert lever p119 (L2 warming) is already queued; a second expert mechanism waits for its micro.
4. Codex **drainguard**: `scripts/check_drain_fix.py` + policy: every new bundle must pass it before chain readiness, so its chain does not need the other lane paused; read-only report over all packets.
STOP DOING acknowledged: no briefs for levers whose own budget projects < 0.3%; no chains of unfixed bundles without the pause; no fallback composites for bundles that will not chain; next-chain launches are waiter-driven.

## Review 23 (2026-10-18 ~12:05 UTC): ACT

2 h: lane A 85%, lane B 39%; ten exact levers closed with none ≥ +0.5% (p116 0.936×, p117 0.98×, p119 1.079×, p120 −3.9%, p121 ~0.1%, p122 ~0.1%, p125 1.27× vs 1.5× gate, p123/p126 inconclusive). Bundle 7 qualified (+1.48% A / +1.40% B, exact) but `packet124-chain-a` died at K2 (leaked `other_fusion` into K2's exact-key selection), cascading into a lane-B refusal; coordinator archived markers/latch/undrained teardown and restarted both lanes.

Actions:
1. `p124b-chain` waiter armed: packet 124b (K2 fix + drain fix; all-window argument gate passes: 11 windows, 31 launch argument sets; original K2 code fails) → waits for packet 58n's one-card arms to clear lane A → PAUSE-A only (no lane-B pause) → ≥ 61 s drain spacing → pre-launch hook (`argument_gate.py --verify` + `check_drain_fix.py`, both pass) → `verify_ready.py` → chain; post-chain prep with packet 124b's own tools.
2. Codex **teardownfix**: shared copy-forward helper so a window that raises after its device children are gone still records a drained teardown and releases its marker (no cross-lane cascade); plus a checker.
3. Codex **p128**: fresh in-engine per-class attribution of the bundle 7 line on both ranks, hits and misses, every layer, one lane-B load; levers re-ranked by ms on the critical path with a ≥ +0.5% projected bar.
4. One-card: packet 58n's tile16-only screen runs now in the 124b gap; packet 58p (one-card chain for that view, gated ≥ +0.5%) is prepared to run after bundle 7's chain.
STOP DOING acknowledged: startup-window passes are not chain readiness without the full argument gate; chain launches are pre-armed when the Codex job starts; no briefs below +0.5% projected in-engine gain; no lane-B pause for drain-fixed bundles.

## Review 24 (2026-10-18 ~13:05 UTC): ACT

2 h: lane A 89%, lane B 42% (lane B idle during the one-card whole-host holds 11:56–12:22 and since 12:46). Bundle 7 waited ~2.5 h through two chain failures (K2 exact-key selection; flattened oracle symlink); packet 124c (both fixed, extended gate covers the queue runner's between-window checks) is armed after the one-card chain. Packet 128's attribution ran but at 0.72 overhead ratio and its analysis failed ("overlapping queues").

Actions:
1. Codex **p128b**: sampled-token attribution (overhead target ≥ 0.90) + per-queue analysis fix; `autoq-p128b` queues it on lane B when Codex exits and runs `analyze.py` right after the job.
2. Codex **p129** (2-card lever): draft acceptance via a more faithful draft-expert format, acceptance-first diagnostic on independent calibration text (kill gate +1.5 points), v5 bracket only after; `autoq-p129` queues the diagnostic on lane B when Codex exits. Both run on lane B during the packet124c chain (no lane-B pause for that bundle).
3. One-card: packet 58r's one-load bracket and packet 58t's resident-lookup screen will run back to back in a single whole-host hold after the packet124c chain (no separate holds; never ahead of a ready 2-card chain).
4. Launch environment: the packet58p first launch died on a caller-supplied `LD_LIBRARY_PATH`; future WINDOW/ready commands must embed the recorded oneAPI path, and every pre-launch hook runs the closed-environment + argument + queue/oracle gates (packet124c's hook does the latter two).
STOP DOING acknowledged: all-Codex-on-one-card while lane B is empty; per-question whole-host holds; unanalysed diagnostics; every-token event recording; caller-environment launch commands.

## Review 24b (2026-10-18 ~14:05 UTC): ACT

Cards 0+1 had no device process 13:37–14:03: packet124c's whole-host W2m window waited for admission behind packet129's lane-B diagnostic (autoq started it 13:32); W2m got in ~4 min before its 1800 s admission timeout. p130/p131 compiles stalled on the same hold. Packet129 closed (+0.08 pt acceptance; draft format is not the limit).

Actions:
1. PAUSE-B set through the rest of the packet124c chain (lane B queue was empty). Rule: during a lane-A chain, a lane-B job may start only if it finishes before the chain's next whole-host window; otherwise lane B is paused from KD to the chain's end.
2. `p58rt` stopped; `p58rt2` keys on `packet124c-chain-a` ending (markers clear, not the CPU post-chain prep), releases lane B for p130/p131 smokes, waits ≤ 20 min for both packets' proposals, then runs the one-card hold (58r + 58t). `autoq2-p130` / `autoq2-p131` insert each packet's lane-B proposals (smoke first) at the head of lane B when its Codex job exits.
3. Packet129 closed with a DO-NOT-REPEAT note; diagnostics stop at the primary gate.
4. Codex **p132**: CPU-only study of a confidence-gated two-candidate speculative half (independent text; kill gate +3% projected net).
5. Codex **opsmon** (gpu_time_review counts admission waits as idle; ops-level compile_turn that blocks only during started whole-host windows) and **disk6** (verified archive pass to ≥ 40 GB free).
STOP DOING acknowledged: lane-B screens > ~15 min once a chain is past K2; secondary diagnostic passes after a decided primary; hand-offs keyed on post-chain CPU prep; further draft-format variants.

## Review 25 (2026-10-18 ~15:05 UTC): ACT

Both lanes stopped since 15:03 by refusals that came before any model load: packet58r host admission (115.48 vs 118.31 GB, parallel Codex CPU workers) and packet131's smoke ("unsafe identity path": the readiness map pinned the packet49 oracle results through the restored symlink; `run131 --plan` skipped `verify_map`). 2 h utilisation 51% (A 14%, B 45%). Faults 2.

Actions:
1. One-card hold now: refused evidence archived, 58r re-queued ahead of 58t on lane A, PAUSE-B, drivers restarted after archiving the failed done records (A started 15:06:38); `p58release2` releases lane B when 58t ends.
2. Lane B cleaned: the five stale packet131 grid rows removed; Codex **p131b** fixes the oracle-path pin (with a plan-mode gate that runs the real ready gate) and `autoq2-p131b` queues its smoke + grid after the hold.
3. Codex **opsrefusal**: lanequeue waits for host admission (≤ 20 min) and survives refusals proven pre-device (drops the job and its dependants, alerts, keeps the driver running); any possible device contact, fault line, latch or undrained teardown still stops the lane.
4. Codex **p58u**: one-card admission bound derived from measured peaks (58g/58k/58n/58p, 58t's +29.3 GB) for future one-card packets.
5. Packets 132 (+2.25% projected < +3%) and 134 (rank-0 gaps are draft waits, not enqueue) closed; Codex **p135** synthesises the full critical path of the 58.22 line and names the top levers ≥ +0.5% (or the practical ceiling).
STOP DOING acknowledged: whole-host windows while Codex runs parallel CPU workers (new briefs cap Codex at ≤ 4 GB during holds); plan modes that skip the real gates; grid rows left queued after a refused smoke; v4 five-load grids for sub-2% runtime-switchable levers.

## Review 26 (2026-10-18 ~16:05 UTC): ACT

Lane B ran continuously from 15:36 (p131b smoke + grid: **+0.81% strict, drift 0.11%, exact**, acceptance unchanged). Lane A had no device work after 15:35. Its confirm was held behind lane B's last grid row, and then the confirm smoke was refused before any device work: `confirm136.py` adds `PYTHONDONTWRITEBYTECODE` to the closed environment. p136 had no chain waiter armed. Fault count is still 2.

Actions:
1. Packet136 confirm fixed via Codex **p136b** (30 min): closed environment, confirm/chain entry probes through `masked_environment`/`closed_environment`, minimal reseal, `READY-FOR-DEVICE.json` as the last write. Stale `active-lane-A.json` (dead pid 1494247) archived after review: render nodes and locks free, fault count 2. The five broken grid rows were pulled, done-A archived, and the driver restarted (A20).
   - `autoqA-p136b` queues the fixed confirm when p136b exits.
   - `p136-chain2-waiter` then runs `orchestrate --evidence-only`, ready check, `argument_gate --verify`, `check_drain_fix`, PAUSE-A/B, drain spacing, `verify_ready`, the chain command, and post-chain prep with dry-run and server dry-run (no real submit). It is keyed on new lane events only.
2. `p58v-hold` armed: after Codex p58v exits with smoke + v5 proposals and no packet136 chain is pending or running, one whole-host hold on lane A (PAUSE-B), released when the last job ends.
3. New brief rule: every brief's first device milestone is the smoke proposal (≤ 75 min). `READY-FOR-DEVICE.json` is written after seals and gates are committed, and nothing in the packet changes afterwards. Waiters trigger on that file plus a clean temporary-queue plan, not on Codex exiting. This applies from p136b onward; p137 predates it.
4. New readiness rule for bundle 9 and later, set before any bundle 9 data exists: one lane's grid (≥ +0.5%, drift ≤ 1%, exact) plus a composed 12×64 smoke on the other lane, then the chain. Packet136 keeps its sealed both-lane rule.
5. Codex **opsreview2**: `gpu_time_review.py` counts lanequeue whole-host jobs (both lanes), chain K and whole-host windows, and takes the union of intervals.

STOP DOING acknowledged:
- making an idle lane wait for the other lane's last row or a Codex exit;
- finishing a bundle without arming its chain waiter;
- five-load second-lane confirm grids from bundle 9 on;
- device proposals as the last deliverable of long briefs.

## Review 27 (2026-10-18 ~17:05 UTC): ACT

Over 2 h, utilization was 60% (lane A 41%, lane B 41%). Lane B had no device work from 16:06 UTC. Its ready jobs (the packet138 capture from 16:44, packet137 smoke and bracket from 17:04) were held by a lane-B pause covering the whole packet136 chain. `p136-chain2.sh` set that pause on the stale assumption that lane B had nothing queued. The chain was at K2 at 17:05. Fault count 2.

Actions:
1. 17:07:28 UTC: lane B reordered so the packet138 capture runs first. Packet137's smoke and bracket were parked in `fn-run/held-p137-B.txt`, and PAUSE-B was lifted. The capture started at 17:07:29 during the chain's lane-A-only windows, and `repauseB-after-p138` restored PAUSE-B at 17:07:41. W2m keeps its exclusive admission (1800 s budget), and the drain fix is verified in this bundle.
2. Codex **p140**: the next 2-card target-body lever. It first commits a ranked table of in-engine time against the byte reference, checked against every closed attempt. It proceeds only on a new exact mechanism projected at ≥ +3%, in a copy of packet136 as a runtime dimension, and goes straight to a lane-B smoke plus a one-load v5 bracket.
3. Rule from bundle 9 on: launch a record chain only when the confirmed gains together are ≥ +2% over the current record, or when neither lane has a ready screen (e.g. overnight). The chain's own readiness gates are unchanged.
4. Chain-waiter rule (restated a third time, now in memory): decide the lane-B pause when the chain launches, from the live queue. For drain-fixed bundles, pause lane B only from KD to the end, and only if the next lane-B job's upper expected time does not fit before the first whole-host window.
5. Packet137: one smoke and one lane-B bracket, after the packet58v one-card hold (`requeue-p137` puts them back when `p58v-hold2` ends). Close it on that bracket if it is under +0.5% or not exact; no repair copy, no second grid.

STOP DOING acknowledged:
- whole-chain lane-B pauses for drain-fixed bundles;
- queue assumptions baked into waiters when they are written;
- sub-1% chains while a several-times-larger ready lever waits;
- more than 75 min of Codex on levers projected under ~1%;
- a single Codex job preparing the next candidate.

## Review 28 (2026-10-18 ~18:05 UTC): ACT

Over 2 h, utilization was 60% (lane A 54%, lane B 28%). Lane B had no device work 17:11–18:06 (packet136 chain, then the packet58v one-card hold). The 58.80 record was submitted at 17:50. Packets 138 and 140 closed cheaply at their CPU kill gates. Only one Codex job (p58x) was preparing device work while both queues were about to run dry.

Meanwhile packet58v's bracket landed: overlap 28.116 / 28.153 vs warm serial 26.053 / 26.079 (+7.8%), all exact. The first view (empty device cache) ran at 22.731, so packet58w's sealed drift rule refused the chain. Codex **p58wb** amends the rule before any chain: the first one-card bracket view is a cache warm-up, as in packet58t's precedent, and the amendment is disclosed. `p58w-chain2-waiter` reruns seal and readiness and then launches the hash-checked chain.

Actions:
1. Codex **p141**: a 2-card transfer-gap probe. One load compares the cold, in-order real half-kernel sequence against warm repeated micros, with a preregistered kill gate (≤ 1.15× close; ≥ 1.3× on a ≥ 0.5 ms/half class → layout/order brief). Device proposal due within 60 min; `autoq-ready-p141` queues it on lane B.
2. Codex **p58y**: one-card attribution on the packet58v overlap engine with a +3% kill gate, to run in the same whole-host hold as packet58x's smoke and bracket.
3. Packet139's lane-A composed smoke queued via `autoq-ready-p139` (18:06:56) to use idle lane-A time, so bundle 9 needs no extra preparation if both lanes go idle.
4. Rule: the +2% chain threshold also applies to the one-card line. Packet58w (+7.8%) chains; packet58x (+2.2% projected) gets no chain of its own and stacks with the next one-card gain.
5. Rule: every brief rehearses its own `prepare_submission` on a copy of the previous record chain's evidence before READY-FOR-DEVICE.

STOP DOING acknowledged:
- a single Codex job when both queues end within the hour;
- a separate whole-host hold per one-card question;
- separate one-card chains for gains under 2%;
- re-deriving sub-3% body projections from the untested 20% transfer figure (p141 measures it).

## Review 29 (2026-10-18 ~19:05 UTC): ACT

Only card 0 did real work in the last hour (~25% of card-minutes): the packet58v bracket, packet58w chain a (WS128 25.773, not submitted; WS128x 28.08), the lost packet58x/58y hold, and since 18:43 chain b (the preregistered single quiet-host rerun; WS128x 28.20, WS128 running at review time). Both queues were empty; packet141, the only 2-card preparation, sat behind compile turns and the freeze. Packet58x's smoke died at its own build gate because it pinned `packet58w-onecard-record/verify_ready.py`, which Codex p58wc edited while the smoke ran. This is the third sealed-sibling-edit incident today. Faults 2.

Actions:
1. Order: after chain b, packet141's compile turn and lane-B probe (`autoq-ready-p141`) come before the packet58x+58y hold. No hold waiter is armed until packet141's probe has finished. If chain b's WS128 beats the record, the rehearsed submission prep runs at once (CPU).
2. Codex **opsguard** (starts after chain b):
   - a lane-queue pin guard checks at plan, enqueue and job start, and refuses pins outside the job's packet except an immutable allowlist, plus any pinned-hash drift;
   - a frozen-path generator for briefs;
   - `gpu_time_review.py` reads one-card evidence windows and adds card-minutes.
   Packet58xc (starts after chain b) vendors packet58x's reader and removes its sibling pins.
3. Rule: for one-card chains and brackets, freeze Codex and block compiles only from WS (or bracket start) to the end. During K1a–W2m, compiles and tests may run, but there are no model or full-shape reads. Chain b keeps its preregistered whole-chain freeze.
4. Codex **p142** (starts after chain b): the packet141-positive branch is prepared ahead in a vendored packet136 copy. It adds a `class_layout` runtime dimension for the top three in-engine classes, with exact load-time variants (and states how any gate/up variant differs from 104b). Smoke and one-load v5 are sealed. Only the class packet141 flags gets queued.
5. Folded into opsguard: the review-tool evidence-window fix.

STOP DOING acknowledged:
- editing a sealed packet's files while anything queued, ready or running pins them;
- starting a one-card whole-host hold while the main line's only preparation is mid-compile;
- freezing all Codex across a one-card chain's non-timing windows;
- both queues empty with a single 2-card diagnostic in preparation.

## Review 30 (2026-10-18 ~20:05 UTC): ACT

No new 2-card device data since 18:10. Cards 2+3 had about 8.5 min of real work and card 1 was idle. The 1-card record moved to 28.04 at 19:09.

Lost time:
- packet141b waited 24.5 min behind a stale `hold-lane-B` left by the failed 58x smoke-c (a coordinator cleanup miss), which also blocked every compile on the host;
- packet141b then failed on "stale prepared launch";
- packet58x smoke-d refused on the packet-local latch.

Faults 2.

Actions:
1. **p142 no longer waits on p141:** `autoq-p142-smokes` queues all three class smokes (attention, expert-gate-up, hc-gate-low order600) on lane B when p142's READY lands. Exact smokes go to one-load v5 brackets. packet141's probe runs only if p141c lands, as attribution, not a gate. No p141d.
2. **Selective freeze:** during onecard-hold7's 58x bracket and 58y, `thaw-critical` thaws every Codex unit except disk7 (2-card critical path keeps running; compile_turn still blocks compiles during whole-host holds; briefs forbid model reads).
3. **Stale-artifact sweep:** `fn-run/stale-sweep2.sh` (systemd `stale-sweep2`) archives dead-owner `active-lane-*`, `hold-lane-B`, an undrained teardown record, screen latches and recent untracked packet-local `fault-<boot>.json` latches within about 2 min. It requires the owner dead for 60 s or more, fault count == 2, the lane lock free and the lane's render nodes idle; any fault-count change halts it. A first version's glob also matched old closed-packet latches; it was stopped before archiving anything and restricted.
4. Codex **opsreview4**: `gpu_time_review.py` counts START → first device evidence as admission wait, not busy.
5. Also opsreview4: shared `ops/launch_env.py` (one oneAPI library path plus an `ldd` check) and `ops/rehearse_entry.py`, a device-entry rehearsal under the exact unit environment. Every READY-FOR-DEVICE needs it plus a CPU run of the real arm sequence.

STOP DOING acknowledged:
- holding prepared variants behind a twice-failed diagnostic;
- dead-owner artifacts left more than 5 min;
- freezing 2-card critical-path Codex for one-card brackets;
- unit lifetime as busy time;
- first device run as the environment and arm-sequence test.

## Review 31 (2026-10-18 ~21:05 UTC): ACT

Cards were assigned work only 13.7% of card-minutes over 2 h. The last 2-card speed screen of a new lever was packet131b (ended 16:06); since then the 2-card line has run only diagnostics and smokes. One-card whole-host holds took 128 min in 6 h and left 3 cards idle each time. Packet58z (21.55 GB cache record chain) was running. Faults 2.

Actions:
1. **Ruled-out smokes pulled:** the queued packet142c expert-gate-up and hc-gate-low smokes are out of lane B, and `autoq-p142-v5c` is stopped. packet141's preregistered rule rules out both classes (1.22× and 1.10×), and the expert variant covers one layer per rank. The attention bracket stays at the head of lane B.
2. **Codex p145** (launched after packet58z's timing windows): a vendored packet142 copy adding exact `router-order600` (1.86×) and `gdnz-order600` (1.30×) variants. It supports both lanes; the router lane-A smoke proposal comes first (≤ 40 min, queued by `autoq-ready-p145-router-A`).
3. **Rule:** no new one-card whole-host holds after packet58z unless both 2-card queues are empty (e.g. overnight) or a 2-card body win is being ported. Batch one-card jobs into one hold.
4. **Codex opsreview5** (after packet58z): `ops/rehearse_entry.py --report` runs each job's report step through the real import path on synthetic evidence, plus a duplicate-module-name check. READY-FOR-DEVICE requires it.
5. **Generic waiter:** `fn-run/onecard-chain.sh <packet> <orchestration> [--check]` replaces the hand-copied waiters. It derives the unit, output and fault-review path from the packet's own READY/ready/WINDOW.md, validates them in `--check` before any pause, and freezes Codex only once `WS.log` exists. The 20:52 p58z-chain start failed on a copied fault-review filename and froze Codex 2 s after launch; the relaunch at 20:52:43 used the correct path.

STOP DOING acknowledged:
- queuing screens for attribution-ruled-out classes or single-layer candidates;
- lane-B-only screen tooling;
- one-card holds ahead of ready 2-card speed screens;
- growing p143 beyond what brackets select;
- dropping a brief without re-issuing its scope (p142b's lane-A scope moves to p145).

## Review 32 (2026-10-18 ~22:05 UTC): ACT

All four cards were idle from 21:52 UTC with nothing queued. The class-layout line had closed (attention, router and gdn.z order600 all null, exact). packet58ac and packet58aa closed on CPU estimates for lack of separated device costs. packet148 was a CPU-only 2-card study while lane B was dark. Over 2 h, 25.9% of card-minutes were assigned. Faults 2. The 1-card record moved to 29.26 at 21:18.

Actions:
1. **Codex p149 (2-card, lane B):** a vendored packet136 probe with `probe=xchg`. It adds the real per-layer exchange payloads a shared (both-rank) miss correction would need during corrected first halves, output-neutral, measured in a one-load v5. It also fixes the bracket report reader (the missing `p105-transfers.jsonl`), with a regression test on real retained packet145 bracket evidence. `stv5-p149` queues the smoke, then the v5, after p149 exits with a fresh READY.
2. **Codex p58ad:** the one-card record chain for `hc=p60fusion`, prepared ahead and bound to packet58ab's build by hash. Readiness requires packet58ab's v5 under the warm-up rule and ≥ +2% over 29.260, and it must pass `fn-run/onecard-chain.sh --check`. `onecard-hold-p58ab2` now fires on a **stable** packet58ab READY (fresh, and no file in the packet changed for 3 min, or its Codex exited). In one hold it runs smoke → v5 (freezing only disk-heavy Codex) → the packet58ad chain if ready (its own gates) → the packet58ae arms.
3. Bracket report-gate fix: in p149's copy; the report-only exit code stays as is because the v4 wrappers are frozen.
4. **Codex p58ae:** two light, output-neutral one-card measurement arms (cache-publication split; per-layer miss-stall/overlap windows), proving under 2% overhead in-load, with preregistered decision rules. They run in the same hold.

STOP DOING acknowledged:
- CPU-only 2-card studies while lane B is dark;
- closing levers for lack of evidence without queuing the probe that would provide it;
- brackets from a lineage whose report step just failed;
- holds gated on Codex exit instead of a stable READY;
- further weight-layout variants.

## Review 33 (2026-10-18 ~23:05 UTC): ACT

Device occupancy over 2 h was 51% of wall time (21.7% of card-minutes); about 94 min over 6 h had nothing running on any card. One-card lever choice worked: packet58ab HC fusion +3.21% exact, and the packet58ad chain posted 30.396 (submitted, `cmvefq3ep009orf0186k21lba`).

At 23:06 `onecard-hold-p58ab3` queued `packet58ae-combined-A` although its READY said `ready_for_device: false`. The lane-A driver exited on that row's fresh fault review, and the hold then waited, with no deadline, holding PAUSE-B. Fault count 2.

Actions:
1. **Deadlock cleared (23:07, before the verdict arrived):** hold3 stopped, the p58ae row removed, PAUSE-B removed, lane-A driver A29 started. packet149's lane-B smoke started at 23:07:32. Lesson in memory: waiters check READY contents.
2. **Codex p150 (2-card):**
   - (b) a vendored packet136 one-load skip/zero-input differencing probe splitting rank 0's out-of-layer time on the **current** build. It is device-ready ≤ 90 min with a separate READY, and `autoq-p150-split` queues it on lane B only when `ready_for_device` is true and stable.
   - (a) if packet149's measured exchange cost is ≤ ~1 ms/miss, a shared-correction prototype that splits whole routed-expert output rows across the ranks, exact by construction, under its own seal.
3. **Rule:** cap CPU feasibility at ~45 min. Candidates with a ≥ 3% ceiling and a build under 3 h go to a smoke plus a five-view one-load bracket. Forecasts miss in both directions; HC fusion measured +3.21% vs a 2.40–3.17% forecast.
4. **Codex opswaiters:** `lanequeue.py` turns pre-START check failures into `REFUSED-PREDEVICE` and continues, instead of the driver exiting. A new `ops/coord_wait.py` provides `ready()` (`ready_for_device` true), deadline-bounded `wait_event`, a `hold` context that always removes its own PAUSE and thaws, and `driver_alive` alerts.

STOP DOING acknowledged:
- queuing packets whose READY says false;
- unbounded waits holding PAUSE or freezes;
- the Codex prep queue at 0–1 jobs when GPU work ends within 1 h;
- CPU-only closures without a 15–20 min device test;
- more class-layout/cold-gap micro levers.

## Review 34 — 2026-10-19 ~00:08 UTC — VERDICT: ACT

**Finding:** in the last 2 h, a device unit was running 56% of wall time, but only 16.5% of available card-minutes were busy. Lane B did ~12 min of real work and spent 55.6 min held for one-card runs. Over 6 h: ~48 min of lane-B device work against 140 min of one-card holds. The two-card record has not moved since 17:50 (58.798). The fault count is still 2.

**Actions (coordinator, 00:09–00:13 UTC):**
1. **packet150 ran before the packet58ah chain.**
   - Root was raised to 32.16 GB before release (HF models archived to RAID and verified, disabled snap revisions and old Codex daemon releases removed; commit 935e79717).
   - `packet150-split-bracket-B` started at 00:09:47 when the p58ag hold released.
   - The packet58ah chain waiter (launched 00:09:58, ready True) holds both lanes but waits for lane B to drain, so p150 finishes first.
2. **Disk over-reservation.**
   - Codex `opsdisk`: lanequeue storage admission before START, storage-floor refusals classed REFUSED-PREDEVICE so the lane continues, and a disk line in `gpu_time_review.py`.
   - New briefs size planned writes at ≤ 3× measured (~250 MB/view); the 25 GB floor is unchanged.
3. **packet151 re-scoped.**
   - The draft-confidence census brief reopened packet132 (closed in its DO-NOT-REPEAT) without meeting its reopen condition. The Codex job was stopped at 00:11.
   - It was relaunched as `p151b`: a packet149-style one-load v5 that computes and discards a second rank-0 sibling row (output-neutral) to measure the extra cost directly.
   - Preregistered: ≤ 1.952 ms reopens packet132 (calibration only on packet114's independent text); > 1.952 ms closes it.
4. **Codex `p152`:** one design per packet150 segment (token_prep, capture_snapshot, suffix_head, merge_handoff_waits, draft_wait), plus ready-to-launch build briefs for the two likeliest, mapped to each possible verdict.
5. **First-minute data proof** is now required in p151b's smoke. packet58ai (already in progress) gets it as a follow-up before it is queued.

**Also this hour:** packet58ag one-card ports **passed** (B 31.63/31.62 vs controls 30.59/30.51, +3.38% min gain, drift 0.24%, 60/60 exact). The packet58ah record chain is armed.

STOP DOING acknowledged:
- one-card whole-host holds while a two-card job is device-ready;
- briefing levers closed in a DO-NOT-REPEAT without their reopen condition;
- benchmark-tuned gate thresholds;
- Codex cleanup as the disk fix while reservations are 14× real writes;
- diagnostics without a first-window analyzer-input check;
- queuing into a lane with no live driver.

## Review 35 — 2026-10-19 ~01:10 UTC — VERDICT: ACT

**Finding:** 18.4% of card-minutes were busy over 2 h. Lane B did ~19 min of real work and held the host for one-card runs for 50.5 min. The one-card chains (58ah a and b) blocked both two-card prep jobs for ~50 of 60 min. The two-card record has not moved since 17:50. GPU fault count is 2.

**Actions (coordinator, 01:06–01:12 UTC):**
1. **Ordering.** p58ai (one-card miss census) is not dispatched until p153 and p151 have each had their lane-B smoke and v5. After that it is batched into the next one-card hold.
2. **p151 as an upper bound.** `fn-run/post-58ahb-launch.sh` stops p151b at the chain-b thaw and launches **p151c**. p151c finishes the current partial M=2 build (dense/expert batched; HC, small tuples and shared-down serial) as a labelled upper bound:
   - ≤ 1.952 ms reopens packet132;
   - above that is inconclusive, not a closure.
   - It also fixes the empty-timing report fixture and uses freeze-safe limits.
3. **One-card paging fixed in the engine.** Codex **p58aj**, launched at the thaw: packet58ah + packet58t resident lookup copies (29.3 GB anonymous, every row, no cache advice or mlock), admitted through packet58u accounting. Smoke + v5 + chain handoff, prepared and not queued. Chain b of 58ah stays the preregistered last rerun; **no third rerun** of 58ah.
4. **Freeze-safe limits and waiter deadlines.**
   - The deadline path in `fn-run/onecard-chain.sh` and the new `fn-run/onecard-chain-quiet2.sh` now thaws Codex and keeps PAUSE-A/B. The running quiet waiter was not edited (editing a running bash script corrupts it).
   - New briefs forbid wall-clock timeouts that count frozen time.
   - p153 is checked for false timeouts at the thaw.
5. **Third two-card candidate.** Codex **p154**, launched at the thaw: a rank-1 split, i.e. a vendored packet150 harness with rank-1 scopes to attribute the 1.54 ms `remote_reply_wait`. It chooses between p152's draft and merge briefs and is queued behind p153.

STOP DOING acknowledged:
- quiet-host reruns as a paging fix (no best-of-N);
- one-card diagnostics while a two-card candidate is < 45 min from READY;
- growing a measurement's scope when a one-sided bound decides;
- wall-clock limits in freezable Codex units;
- waiter deadlines that leave Codex frozen.

## Review 36 — 2026-10-19 ~02:06 UTC — VERDICT: ACT

**Finding:** 18.7% of card-minutes were busy over 2 h, and all four cards were idle 47% of the time. Lane A had been idle since 01:16. Two device-ready two-card jobs were serialized on lane B. Three of the last six lane-B launches failed for packaging reasons:
- p153: a 60 s data-proof deadline;
- p151: an op that bypassed the preparation registry;
- p154: a 30 GB device floor.

The Codex two-card prep queue was empty, and root was at 29.6 GB and falling.

**Actions (coordinator, 02:06–02:10 UTC):**
1. **p151 v5 to lane A.** It was re-planned, rehearsed and queued on lane A, but it **refused pre-device**: `readiness.py` asserts "registered lane-B probe only". The row went back on lane B behind p154's split, the A driver was restarted (`lanequeue-A34`), and a lesson was recorded: CPU plan and rehearsal do not run a packet's readiness lane assertion.
2. **p58ai ordering.** It will run last in the next one-card session, only if root ≥ 31.2 GB: its `window.py:41` has a 30 GB device floor and it is not resealed. p58aj runs first.
3. **Codex opsreview7:** `rehearse_entry.py` gains checks for storage-floor literals ≠ 25 GB (with a 25.5 GB + planned-writes admission replay), device-path wall deadlines < 2× the measured phase (cold TTFT 60 s; no deadline on data proofs), and a preparation-path probe (or a WARN when none is declared). Tests replay tonight's three pre-fix files.
4. **Two-card prep refilled from p154's smoke** (02:03–02:07):
   - rank 0 waits 1.546 ms/interval on rank 1, of which **1.227 ms is rank 1's draft** (B half 0.171, transport 0.051, merge 0.020);
   - this meets packet126's reopen condition (measured recoverable wait);
   - Codex **p156** runs p152's prepared draft_wait brief: hidden-only draft work in rank 1's suffix slack, proposals for both lanes, no wall-clock data proofs, preparation-path probe;
   - p151's smoke already showed an upper bound far above 1.952 ms (interval 40.1 ms vs 17.0, half A 34.0 ms). Its v5 runs for a clean closure; no full-M=2 brief.
5. **Disk.** disk10 freed only 27 MB, because most candidates are protected or referenced. Codex **disk11** archives the untracked bulk `run/` evidence of closed diagnostics to the RAID with sha256 manifests, keeping the summary JSONs, until root ≥ 33 GB.

STOP DOING acknowledged:
- lane-B-only two-card proposals;
- per-packet disk floor literals;
- READY without device-path deadline checks;
- an empty two-card Codex queue with verdicts < 1 h away.

## Review 37 — 2026-10-19 ~03:05 UTC — VERDICT: ACT

**Finding:** 23.5% of card-minutes were busy over 2 h (21.2% over 6 h), and the host was fully idle for ~37 min. Both lane-A runs this hour failed after the engine was running:
- p58aj: a 60 s first-prefill wait;
- p157: a 0.02 ms absolute analyzer tolerance.

Five of the last ~8 first device runs were lost to harness code. The two-card record has been flat for ~9 h; the GPU fault count is 2.

**Actions (coordinator, 03:05–03:12 UTC):**
1. **Queue p58aj without an idle gap.** `fn-run/hold-onecard4.sh` (armed 03:05) runs p58aj smoke → v5 (all Codex frozen) → p58ai census right after p157's lane-A sequence. p58aj is a whole-host job, so it cannot overlap p157. The session started at 03:08:36.
2. **Analyzers never stop exact runs.** Future briefs require in-run checks for stream presence/format and oracle exactness only; numeric consistency is checked after the run with relative tolerances; CPU inputs must include real cold-path rows from parent evidence. This is in the p58al/p160 briefs and in memory (`first-smokes-fail-on-packaging`).
3. **Draft line closed.** The p157b smoke failed a third time ("invalid device interval") and was not repaired. On p158's roofline, the draft kernels total ≈ 1.38 ms with ≈ 0.48 ms of positive gap, ≤ +2.3% at full closure and ≈ +0.45% at 20% transfer. p158 was stopped. The DO-NOT-REPEAT row and closure note are committed (686b2aae1).
4. **p58ai was already resealed** to the 25 GB floor (60a56785a, 02:35) and is in this session. Codex **p58al** prepares the rank-4 (post-router demand transfer) build mapped to p58ai's verdict.
5. **Freed Codex slot:** **p160**, a two-card critical-path mechanism study. It covers structural changes to the B-half → draft → next-A chain (split draft across ranks, provisional early start, within-layer expert parallel) and briefs only a candidate with a ≥ 3% supported ceiling.

STOP DOING acknowledged:
- ready packets left unqueued;
- absolute numeric in-run checks;
- further draft diagnostics or builds;
- archiving disk to satisfy a packet literal.

## Review 38 — 2026-10-19 ~04:08 UTC — VERDICT: ACT

**Finding:** the last hour was well used (one whole-host one-card session from 03:08: the 58ajb screen, then the record chain started 7 min later). The risk was the hand-off at the end of the chain (~04:12), with both queues empty. The p58ai five-view census was not prepared, the p58am build was serialized behind it, and lane B had been idle since 02:43.

**Actions (coordinator, 04:10–04:18 UTC):**
1. **Zero-gap hand-off.** `fn-run/hold-p58ai.sh` waited for the chain to end clean, held the host, and queued `packet58ai-census-c-smoke-A`, which started at 04:16:15. In parallel the coordinator submitted the 58aj record. **New 1-card record 31.966820** (`cmveqsmsl00ebrf014yvrsosx`, chain WS128 0 major faults; b6849b4eb).
2. **Parallel one-card prep at the thaw** (`fn-run/thaw-launch-r38.sh`, 04:15:51):
   - Codex **p58ai5** prepares the five-view census, ready only on the census-c smoke passing exact;
   - Codex **p58am** builds `bcs-demand-retained32x2` now, with READY false until the census bound is ≥ 1.000 ms/token (DECISION.md unchanged).
3. **Two-card:** p161 (early argmax) keeps priority on the helper cores. Codex **p162** studies cutting the IQ2 gate/up grid-lookup dependency: 1.456 ms/half cold, ≈ 0.57 ms/half removable bound, priced ≈ 3.4%; closed mechanisms are excluded; the gate is bit-exact at ≤ 0.85× in a device micro.
4. **opsreview8:** a gate-identity check (literal job/unit names, lane assertions) in `ops/rehearse_entry.py`, tested on the pre-fix p58ai and p151 gates.

STOP DOING acknowledged:
- CPU builds serialized behind unprepared device diagnostics;
- one two-card study at a time while lane B idles;
- levers picked from packet57's old outside-layer numbers;
- hard-coded names/lanes in gates.

## Review 39 — 2026-10-19 ~05:05 UTC — VERDICT: ACT

**Finding:** 13.1% of card-minutes were busy over 2 h. Both lanes had been idle since 04:36. Three census smokes were lost to harness code. Five two-card ≥ 3% studies closed in ~5 h. The two-card record has been flat ~11 h.

**Actions (coordinator, 05:05–05:12 UTC):**
1. **Bundle-9 chain** `packet155-chain-a` launched at 05:05:19 (`fn-run/chain-p155.sh`: verify_ready, both lanes held, drain spacing, Codex frozen from WS). It runs under the idle-lane rule; a submission needs WS128 > 58.798109 and exact.
2. **p58am unblocked.** p58amc was stopped: the binary lacks `--lookups`. Codex **p58an** (compile allowed) ports `--lookups resident`, reruns the byte gates and builds real lanequeue rows, with a fallback to a same-parent screen.
3. **Zero-gap hand-off.** `fn-run/hold-p58am.sh` waits for the chain to end clean and for the p58an READY, then runs p58am smoke → v5 (all Codex frozen). The monitor is now `monitor-loop4.sh`, with a 5-min EMPTY-QUEUE alert.
4. **Brief-template rules** added and applied to the p58an/p58ao briefs and the heartbeat:
   - real lanequeue rows;
   - check every flag against `--help` before no-compile requirements;
   - audit inherited in-run checks;
   - push gate supersessions promptly.
5. **Effort moves to the one-card line.** Codex **p58ao** prepares the next one-card lever on the compute-tail bucket behind p58am. There will be no new two-card ≥ 3% single-lever studies on bundle 8. Disk is watched: root 29.5 GB before the chain.

STOP DOING acknowledged:
- leaving ready device work unqueued;
- no-compile briefs needing native changes;
- raw-argv proposals;
- re-running diagnostics after a second packaging failure when a direct measurement supersedes them;
- in-run consistency analyzers (inherited ones too);
- new two-card single-lever ≥ 3% studies on bundle 8.

## Review 40 — 2026-10-19 ~06:04 UTC — VERDICT: ACT

**Finding:** 13.3% of card-minutes were busy over 2 h. Four of five device runs since 04:00 died on harness/packaging:
- census-c and census-d;
- p155 W0p (`shared extent`, a window its bracket never exercised);
- p58amd checked1 (pinned-progress sensor refusal after a reset).

The p58am checked2 row was READY but blocked by a deeper packet latch (`screen/fault-*.json`, outside stale-sweep's glob) and by p163 on lane B. Only one Codex job was running, with nothing prepared after p58am. The two-card record has been flat ~12 h.

**Actions (coordinator, 06:04–06:06 UTC):**
1. **checked1 latch archived** (sensor refusal, owner dead, faults 2, card-0 idle) to `coordination/chain-lanes-v1/reviewed/`. p163 B-b had already started (06:04:08), so it was not removed. Meanwhile **p58amd found the root cause without checked2**: a wrong-layout kernel capture (240 vs 236 commands). It rebuilt with a regression test, and checked2 is moot. `fn-run/after-p58amd.sh` → `hold-p58am3.sh` runs the sequential smoke → v5 when p58amd's fresh READY lands. It waits out B-b; the one-card p163 rows stay unqueued until then.
2. **Codex p58ap** pre-seals the p58am record chain (58aj chain structure, p58am binary by hash). READY is gated on the v5 passing (≥ +0.5% over every warm control, exact, drift ≤ 3%). Submission requires WS128 > 31.966820.
3. **Codex p164**, a layer-body lever: split route's 0.79 ms/half (packet141 events) and price an exact router-epilogue route fusion (ties included). Packet73 deferred it and it was never revisited. A one-card screen brief follows if the ceiling is ≥ +2%.
4. **Rule for every row, diagnostic ones included:** a CPU real-arm-sequence gate (real sensors on synthetic streams through every reset path). Chain briefs must CPU-execute every window's native argv (W0p/W0-prefill included). This is in the p58ap brief and the heartbeat. stale-sweep will be widened to packet `screen/fault-*.json` latches in a new copy; the running script stays untouched.
5. **p163 is gap filler:** its remaining loads run only when no speed row is READY. The first two-card full512 run (B-a) passed the realistic final gate at 58.61 tok/s.

STOP DOING acknowledged:
- widening loads ahead of READY speed diagnostics;
- diagnostic rows without the CPU real-arm-sequence gate;
- harness-only latches left while READY rows wait;
- a single Codex job with an empty pipeline;
- schedule/protocol levers over the layer body (~85% of each interval).

## Review 41 — 2026-10-19 ~07:03 UTC — VERDICT: ACT

**Finding:** device units were in flight 41% of 2 h, and card-minute occupancy was 14.7%. The host was fully idle 05:19–05:56. **Zero decode Codex jobs** were running: the two-card record has been flat 13 h, and the one-card's only lever (p58am) closed at −52.6% with nothing behind it. 3 of 6 runs failed on non-speed issues.

**Actions (coordinator, 07:05–07:10 UTC):**
1. **Two decode Codex jobs, each aimed at a READY one-load screen:**
   - **p58aq:** a one-card device diagnostic (skip/zero-input arms in one load on the 58aj line) splitting the 1.231 ms/token publication boundary (+3.74% ceiling) and the 20.9 ms host-wait envelope;
   - **p166:** a causal M=2 layer micro on lane B, a full GDN + QSA layer with every op paired, exact vs two M=1 calls, reporting M2/M1. The decision rule is ≤ 1.5× → exact M=2 prefill stage 1.
2. **Gap fill / root cause.** The p163 one-card refusal was **not** the marker race: its native receipt says `ionice -c3 required for model reads`; the dead-owner marker was its own leftover. p165's one-card rows have the same defect. Codex **p165c** adds the `ionice -c3` launch to both packets, with a CPU check of the native ioprio. After it lands, the one-card full-gate/warm-prefill rows run one at a time in a whole-host hold.
3. **Marker race:** new hold copies will wait (≤ 3 min) for no dead-owner active-lane marker before enqueueing. A REFUSED-fast pre-device row is re-queued once by hand. Running scripts stay unedited.
4. **Kill test first:** mechanisms that add copy-engine traffic, barriers or extra rows get a minimal one-load v5 kill test before porting or chain pre-sealing (p58am cost ~3.7 h and six jobs to learn −52.6%).
5. **Warm prefill measured (p165 B-a): 75.97 tok/s** for 512 tokens on two cards (TTFT 6.74 s, warm runtime, cold prompt, `cached_tokens=0`). Decode 58.63 tok/s with the full gate passed.

STOP DOING acknowledged:
- CPU closures on "unmeasured device quantities" while the host idles;
- a drained decode pipeline;
- pre-sealing chains without device speed evidence;
- appending rows while a dead-owner marker is unarchived;
- packaging-repair loops of more than two jobs before a first speed number.

## Review 42 — 2026-10-19 08:0x UTC — VERDICT: ACT

The reviewer found 62% device-in-flight and 23.2% card-busy over 2 h, up from 41% / 14.7%. When the p58aq split ends (~08:12) the decode pipeline would drain again: no READY decode row on either lane, two cards flat at 58.798 for about 14 h, and p166/p167 frozen since 07:58.

Actions taken (08:05–08:15):
1. **Briefs ready before the thaw.**
   - Launch: `fn-run/after-p58aq-codex.sh` starts Codex **p168** and **p169** as soon as run-p58aq thaws Codex, then **p166b** when p166 exits.
   - One-card follow-up: `p58ar` (build the exact replacement p58aq's analyzer qualifies, then a one-load kill-test v5, no smoke) is pre-written for the ≥ 0.67 ms/token outcome. Otherwise p58aq closes on its own DO-NOT-REPEAT, and the next one-card lever comes from p166b's MTP projection.
2. **p168: measured two-card body census on bundle 8** (lane B, one load). It uses skip/zero-input differencing arms with snapshot restore + repair, mirroring p58aq U0/S0, with exact controls at start/middle/end. Output: a ranked class → ms/token table, replacing CPU pricing from packet110 synthetic numbers or an assumed 20% transfer.
3. **p166b:** qualify p166 with a packet-private report adapter and keep the failed shared receipt (the p58aq precedent). It also adds the one-card MTP decode projection (packet147 §5: cycle = D + V2 + (1−a)R, a = 0.787, D = 1.79 ms) to the analyzer's decision rule. **p169 (ops):** generalize the shared standalone-micro / one-card window report rehearsal, with a seal-safety check first; if any READY packet pins `rehearse_entry.py` bytes, a new module is used instead.
4. **No optional smokes** before diagnostics that open with K1a/K1b plus an exact control (written into the p168 and p58ar briefs).
5. **Selective Codex freeze:** `fn-run/codex-freeze-heavy.sh <stop-file>` freezes only units that read model files, compile, or exceed 4 GB, re-checking every 20 s. It is for device-bound screens. Record chains and host-wait diagnostics (p58aq) keep the full freeze.

Also on record:
- p167 closed on CPU: the two-card bundle-8 streams show no recurring lookup-table major faults, so there is nothing to port from p58aj.
- The 07:46 p58aq pin-guard refusal (`records[].pins = {passed: true}`) was fixed in 436389c0a. Briefs now forbid pin-guard map keys outside path → SHA256 maps.

STOP DOING acknowledged: no READY decode row at window end; briefs whose gate needs a frozen path changed; pricing two-card levers from synthetic or failed-gate numbers; optional smokes before K1-opening diagnostics; publication rows ahead of decode rows; pin-guard key names in evidence JSON.
