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
