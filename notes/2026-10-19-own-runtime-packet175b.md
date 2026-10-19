# 2026-10-19: packet175b, D1 scale-word multicast device micro (CPU preparation only)

Packet: `experiments/own-xpu-runtime/stage2/packet175b-twocard-d1-micro/`.
No device work has run. Nothing is queued.

## Why

The packet168 v3 census puts dense_hc at **11.532 ms** per two-card body pass
(two-thirds of the token). Packet173's ranker lists D1 (`dense_lane` scale-word
sharing, packet140's N1) behind D2, with a mid gain of about +0.6–0.7%. It is a
sub-1% lever, so hourly review 44 allows it only as part of a combined bundle-9
candidate. That candidate holds packet153's static descriptors (+0.35%, exact,
retained), D2 and D1, and each micro must first show a dense GEMV time of
≤ 0.97× baseline, overhead included.

## Decision rule

The analyzer computes the weighted (36 GDN / 12 QSA) dense GEMV time **B/A**:

* **B/A ≤ 0.97:** "eligible for the combined bundle-9 candidate".
* **Otherwise:** "close D1", and the analyzer appends a DO-NOT-REPEAT row.

D1 adds no kernels, so its overhead is inside the timed dense events.
LEVER-TABLE §(c)4 had named 0.95× for D1. Review 44's 0.97 supersedes it, and the
reported ratio still shows where the old gate falls.

## Design

* **Harness.** packet175's committed harness (`012f6f810`, READY `96dc6e147`),
  copied unchanged except for the D1 arm. It runs the real packet166 M1 launch order
  on the real layer 0 and layer 3 weights, with a 256 MiB evict interposer before
  each row. There are 240 interleaved AB/BA pairs per layer. Every timed pass is
  byte-checked, and the inherited real-weight oracle applies.
* **Arm A:** the bundle-8 dense lane (`p68c::dense_lane`).
* **Arm B:** `d1_lane.hpp`.
  * Per 32-word chunk, lane L loads scale word `chunk_base/group + L` once,
    predicated to `[begin, end)`.
  * Each iteration takes its bits from the owner lane through `select_from_group`.
  * Q6_K: one load serves 2 iterations. Q8_0: one load serves 4.
  * Products, add order, trees and BF16 boundaries are unchanged.
  * B applies to every Q6_K/Q8_0 `device_lane` call. Here those are the Q6_K large
    projections and the attention projections.
  * The HC, p49d four-member tuple and p109 shared down kernels are unchanged and stay
    in both sums.
* **Warm-ahead.** packet175's warm-ahead path stays compiled in but is never
  enabled. The analyzer refuses any `warm` event and any stream without
  `variant: d1-scale-multicast`.

## CPU gates (all passed)

* **Builds.** Three native builds through `ops/compile_turn.py`:
  * device `babed7056bd9…`;
  * GNU host `d9261224…`;
  * Intel host `c624f140…`.
* **Synthetic parity, GNU and Intel.**
  * Host A and B are byte-identical. B uses an exact subgroup emulation.
  * All 142 position-31 buffers equal packet175's synthetic trace.
  * The native D1 self-test proves coverage for 16,096 tiles: every consumed word was
    loaded by its source lane and is the baseline's word.
  * 1,728 random-bit lane sums are bit-identical to `p68c::dense_lane` (Q6_K and
    Q8_0, K 320–12288, split 1 and 4).
* **Oracle.** packet175's inherited packet166 real-weight oracle (138 rows) carries
  over unchanged. It is referenced by `{name, parent_relpath, parent_digest}`.
* **Preparation.** A CPU-transport run in the Landlock sandbox completed 964 resets.
  Arm B takes one extra step per D1 site, which proves that B traverses them.
* **Plans.** `lanequeue plan` passed on temporary queue copies (lanes A and B), and
  `run_micro.py --plan` passed for both lanes.
* **Report adapter.** Both decision tails passed. It refused the invalid oracle, the
  real packet166 stream and a warm-ahead stream.
* **Analyzer tests.** 8 passed.
* **Hygiene.**
  * The pin guard was checked on both proposals.
  * Every `sources` map holds SHA256 values only.
  * The packet tree was committed first, and `READY-FOR-DEVICE.json` was written last.

## Proposals (not queued)

| Lane | Card | Proposal | Job |
|---|---|---|---|
| A | 0 | `ops/lane-queue/proposed-p175b-micro-A.txt` | `packet175b-d1-scale-multicast-micro-A1` |
| B | 2 | `ops/lane-queue/proposed-p175b-micro-B.txt` | `packet175b-d1-scale-multicast-micro-B1` |

Admit one, on whichever lane is free; the runner refuses a second lane. It
can run back-to-back with packet175 (D2) on the other lane. Expected time is about
15 minutes, with a 7,200 s watchdog.

## DO-NOT-REPEAT check

The search (`evidence/do-not-repeat-search.txt`) found no device closure of scale
multicast:

* packet140 N1 and packet58ao closed it on CPU priors only.
* packet81 (neutral load-count cut) and packet108 (load8 0.993×/0.901×) are the
  closest negative evidence. They make a B/A ≤ 0.97 unlikely but not excluded.

One CPU gate attempt failed on this packet's own oracle row-count formula. The
formula was wrong because the parent oracle includes `.partial` buffers. It was
replaced with a key-set check, and that failed output directory was removed before
the passing run.
