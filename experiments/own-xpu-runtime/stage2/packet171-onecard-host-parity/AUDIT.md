# Packet171: one-card host-runtime parity audit vs two-card bundle 8

CPU only. No GPU, service or setting was touched. The audit compares host-runtime **mechanisms**, not file names, between:

- **P**: two-card bundle 8, `stage2/packet136-record-bundle/`. Device link per `engine-commands.json`; `P56X_SLEEP20=0` in `lineage-inputs/parent-c3b164f0….json`.
- **O**: one-card spin line, `stage2/packet58as-onecard-spinwait/` at **HEAD** (committed state). The working tree only adds a `--wait-policy` CLI option (another agent); line numbers below are from `git show HEAD:`. `main` = `native/generated/main.cpp`, `sd` = `native/generated/single_device.cpp`.

One-card prices come from the retained packet58as v5 streams (A = 1 ms poll, B = spin, 1,524 decode tokens per view) and packet58aq's segments. They are recomputed by `measure_58as_host.py` into `measured.json`. The spin line is 28.80 ms/token mean (34.57 tok/s class-balanced). The brief threshold is **0.6 ms/token, about +2%**.

Labels: **measured** = read from a device run; **transferred** = a two-card device gain applied to one card; **assumed** = an estimate with no direct device measurement.

## Measured one-card spin-line token anatomy (B0/B1 means, ms/token)

| Segment | Spin (B) | Poll (A) | Source |
| --- | ---: | ---: | --- |
| wall | 28.80 | 31.21–31.27 | `timings.jsonl` |
| enqueue loop, 1,118 submissions (overlaps the device) | 5.13 | 5.25–5.38 | same |
| wait (compute drain, route-log drains) | 20.52 | 21.10–21.45 | same |
| token/error readback (`transfer_wall_ms`) | 1.19 (median 0.16) | 1.75–1.93 | same |
| other: position start, publication, token put, fill submission | 1.88 (median 1.25) | 2.41–2.77 | wall minus the rest |
| host waits per token | 6 | 6 | same |
| copies per token | 3 H2D, 50 D2H | same | same |
| cache publication (construction + submission + drain) | **0.200 per position** | 1.25 | `cache.jsonl` deltas |
| owner-thread voluntary context switches | 275 | 21 | `timings.jsonl` |

**Readback is bimodal under spin, and the slow mode is tied to cache maintenance:**
- 40.5% of tokens take **2.63 ms** to read back 8 bytes; the rest take **0.20 ms**.
- Slow tokens also wait **+2.33 ms** longer.
- Cache fills land on 49.4% of positions, at 72.9 MB each.
- A slow readback follows a token with high pre-enqueue host time (the fill-submission position) with **P = 0.94**. It coincides with that same token with P = 0.04.
- Mean excess: **0.99 ms/token** in readback (measured), plus **0.95 ms/token** in wait on those tokens (measured, not attributed).
- **A second, independent run shows the same coupling.** This is packet58v's poll-era serial-vs-overlap bracket (`packet58v-async-cache/evidence/card0-async-a/overlap/WSCREEN/run/run`, `cache.jsonl` sha256 `0f9f7659…2088`):
  - mean readback is **0.46 ms/token** in the warm serial-maintenance views (A1/A2);
  - it is **2.13–2.18 ms/token** in the overlap views (B0/B1);
  - p90 rises from 1.2 to 4.9–5.5 ms.
  - Overlap still won overall (35.3 vs 38.0 ms/token wall), but it put about 1.7 ms/token of readback delay on the token boundary. The excess therefore arrived with asynchronous fills on the second BCS list.

## Mechanism table

| # | Mechanism | Bundle 8 (P) | One card (O, HEAD) | Two-card measured gain | One-card price on the spin line | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Foreground copies on the single in-order compute queue** | Every foreground copy is `queue_->memcpy` on the in-order compute queue (`single_device.cpp:83-84,101`). One queue sync (`:122`). | Foreground copies go on a separate BCS immediate list plus a compute-queue barrier per copy (`sd:108-113`). `foreground_sync` waits on both queues (`sd:187-188`). Maintenance fills use a second BCS list on the same copy ordinal (`sd:88,169-175`). | None isolated: the two-card line always had one queue and has no cache fills. | **0.99 ms/token** readback excess, measured. Up to **+0.95** wait excess, measured but not attributed. Causal link to the shared copy ordinal is **assumed**. | **MISSING. Top item.** |
| 2 | Non-blocking token input | Rank 1 stages token and streams asynchronously when `async_half_ready` (`rank.hpp:300` → `mtp.hpp:281-287`: pinned memcpy plus an ordered copy, no wait). Otherwise it uses a blocking `put` (`rank.hpp:133`). The p137 device token input (bundle-9 candidate): exact smoke, **no speed number**. | Synchronous `put` (`main:2006`): drain, memcpy, BCS copy, barrier, wait and retire (`main:888-902`). Host `prepare_token` (`main:1210`) needs the token on the host. | None: p137 never produced a bracket. | **0.05–0.3 ms/token, assumed.** It sits inside the measured "other" median of 1.25 ms. | PARTIAL in P, MISSING in O |
| 3 | Pure spin (`sleep20=0`) | `host_spin.hpp:28` with `P56X_SLEEP20=0` | 250 µs spin, then 20 µs sleeps (`spin_wait.hpp:29-30`) | Not isolated. 56x has no device result. The 61x record gain of +8.67% is pure spin vs 1 ms poll plus HC fusion. | 275 switches/token gives about 75 µs per sleep cycle and about 37 µs detection latency per long wait. With 1.4–2 long waits per token, **0.05–0.08 ms/token** (measured counts, **assumed** latency model). | PARTIAL |
| 4 | Ordered (non-blocking) cache publication, the packet58ar design | Not applicable: no expert cache | `publish_cache_table` always drains (`main:977`), reached via `cache_boundary` (`main:630,635`) | Not applicable | Spin total **0.200 ms/position, measured**. Construction plus submission is 0.183 (58aq, policy-independent). Drain **≤ 0.018 ms/token**. The poll-era 1.108 ms no longer applies. | MISSING but **DEAD under spin** |
| 5 | Reply-first | `reply_first.hpp` is wired (`rank.hpp:183,210`) but bundle 8 runs `ordered`, so it is disabled (`main.cpp:730`) | Token emitted after `cache_after_position` (`main:2046`) and the timing row (`main:2074-2107`) | **−0.004%** (p92, lane A v4; `notes/2026-10-18-own-runtime-p92-p94-results.md`) | **≤ 0.3 ms/token, assumed.** The route-log drains are not isolated from wait. | MISSING. Transfers 0. |
| 6 | Ordered retirement | `ordered_queue.hpp`, `owner_retire.cpp:27-43`, `host:"ordered"` | `ordered_retirement.hpp`, `owner_retire.cpp:16-27`, `--retirement ordered-foreground` | +1.05% / +0.41% (packet85 `MODEL.md:207-218`) | — | PRESENT (parity) |
| 7 | Prepared submission and argument blocks | `prepared_submission.hpp:41-61`, `owner.cpp:185-200` | Same frozen header; issue sites `main:1561,1618`; `sd:132-139` | Not measured. Closed as already present (p134 DNR). | — | PRESENT (parity) |
| 8 | Controller/mailbox, p105 head split | `native_controller.hpp`, `p105_runtime.hpp`, `p105_submit.cpp` | Unreachable: `main:270` requires `rank==-1` | p105b +0.36% (lane B) / +0.38% (lane A) | — | Two-card-specific (two ranks). Excluded by 58ag `AUDIT.md:14`. |
| 9 | p134 / p135 / p138 submission-stall and critical-path work | Attribution only. p135 host token path is 0.102 ms. | — | None. Projections only. | — | No runtime mechanism to port. p138 is a one-card simulation that failed its gate. |
| 10 | Host issue batching (graph replay) | Missing, except the p105 suffix replay | Missing; one per-site loop (`main:1618`) | None. Projections 0 to +0.8%. p109 fusion +0.32%. | 5.13 ms enqueue overlaps the device | Shared gap, not a parity item |
| 11 | Profiling-enabled queues in the hot path | Rank-0 profiling stays on (`main.cpp:1013`) | Off in record runs (`main:1111`). Every run row records `"timing":"token","profiling":false`. | Not isolated (56w) | 0 | Parity, nothing to remove |
| 12 | Remaining sleeps, yields and condition variables | Condition variables only on faults (`owner.cpp:118`) | 1 ms sleep only on the barrier-failure path (`sd:120`). The poll `sleep_for(1ms)` (`sd:165`) runs only in A controls. The yield loop (`main:872`) is MTP-only. Condition variables only on faults. | — | 0 on the spin path, apart from row 3 | Parity |

## Ranking (one-card critical path)

1. **Foreground copies on the compute queue (row 1).** 0.99 ms/token measured readback excess, up to 1.94 ms with the wait excess. Clears 0.6 ms/token. The mechanism attribution is assumed and needs a kill test.
2. **Non-blocking token input (row 2).** 0.05–0.3 ms/token, assumed.
3. **Reply-first (row 5).** ≤ 0.3 ms/token, assumed. The two-card measurement was −0.004%.
4. **Pure spin (row 3).** 0.05–0.08 ms/token, assumed from measured switch counts.
5. **Ordered publication (row 4).** ≤ 0.018 ms/token drain, measured-derived. Dead under spin.

## DO-NOT-REPEAT cross-check (`dnr-scan.txt`, 2,826 lines)

- **packet56x:** "Do not reintroduce millisecond polling." Packet58as complies; its spin keeps the sleep20 tail (row 3). It has not been closed on one card.
- **packet92:** reply-first lost on two cards because housekeeping left the critical path once `ordered` retirement landed. That closure is **two-card-specific**: one card still emits after the route-log drains. It is still below threshold.
- **packet134:** "Implement already-present prepared arguments or pure-spin waits." That closure covers the two-card 124c lineage. On one card, prepared arguments are present but pure spin is not.
- **packet58v:** "Separate copy queue alone proves overlap: False." A copy queue is not another physical copy engine (packet58al/58am DNR). That is consistent with row 1's hypothesis that foreground readbacks share the copy ordinal with fills.
- **packet58am:** the BCS demand-transfer path is closed at −52.6%. Row 1 does **not** reopen it: it moves 8-byte foreground readbacks and uploads **off** BCS and onto the compute queue, as on two cards, and leaves fills untouched.
- **packet58aq/58ar:** the 1.108 ms publication drain was a poll artifact. Under spin, ordered publication is ≤ 0.02 ms/token. **Do not package packet58ar or the Codex partial `packet171-onecard-ordered-publication/` on the spin line.** That partial is an untracked, path-rewritten copy of packet58as HEAD with no mechanism change, superseded by this audit.

## Kill-test status

Only row 1 clears the threshold. It was **not** packaged to READY inside the 60-minute box. Its brief is `BUILD-BRIEF.md` in this directory. No READY file, no queue row and no launch exist.

Measured inputs, by digest, are in `audit.json` → `inputs` (records of `name`, `parent_relpath`, `parent_digest`).
