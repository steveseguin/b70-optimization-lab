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
