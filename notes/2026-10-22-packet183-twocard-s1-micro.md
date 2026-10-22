# 2026-10-22: packet183, the two-card S1 dense-scales bracket (CPU preparation)

Packet: [`experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/`](../experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/README.md).
Proposal: `experiments/own-xpu-runtime/ops/lane-queue/proposed-p183-two-card-B.txt` (not queued).
No GPU, service, setting, PAUSE file or live queue was touched. Nothing was committed.

## Why

Resume-queue item (a) of the 2026-10-19 owner pause: the S1 dense-scales lever from
packet177, lane B. The prep named there (`stage2/packet178-twocard-s1-micro/`, untracked) is
gone from this host, so this packet starts fresh and supersedes it; packet178 is now the
one-card portable packet.

## What S1 does

Each loaded Q6_K weight row keeps, next to its int8 codes, both the loader's FP32 scale words
(64 bytes per 256 weights) and the original 18 bytes of scale data. The fast kernels read the
64 bytes. S1 reads the 18 bytes and redoes the loader's one multiply. Same bits for every finite
scale, 14.4% fewer weight bytes per dense read. A load-time check refuses to start if any scale
is not finite or any stored word does not match.

On the real model, all 249 Q6_K tensors pass that check (213.9 million scale groups, none
non-finite, no mismatch). At full production shape, S1 covers per token 87 kernel launches on
card A's half and 91 on card B's half, including the big output head on card B, plus the draft
head. The small K/V projections, card A's slice of the head and all non-Q6 kernels stay as they are.

## Expected gain

From recorded numbers (packet110 per-kernel times and bytes, packet160's interval breakdown of
the 58.80 record, the 590 GB/s read ceiling): **+4.4%** if only the removed bytes' time
disappears (about 61.4 tok/s), +6.2% if the kernels keep their achieved bandwidth. +2% needs
46% of the first case. Packet177 had priced +3.7% without the two heads. Known risk: a
different scale-path change in the same kernels (packet175b D1) cost 6.7%, so extra per-step
work is not free here. The bracket decides.

## How it will be measured

One model load on cards 2+3: expanded, S1, expanded, S1, expanded; 12 cold prompts x 128 tokens
per view plus a 64-token check, every view exact, identical draft guesses. A short S1-only smoke
runs first. About 12 minutes of device time. Screen win: both S1 views at least +0.5% over
every control. Record-path rule: both at least +2% and at least 59.97 tok/s.

## Win path

A waiter is prepared but not armed (`chain/ARMING.md`). A two-card record chain cannot be
derived from this packet: it needs its own record bundle (bundle 8 plus S1), built only after a
win. So on a win the waiter runs the same bracket once more on cards 0+1, where a record chain
would run, through the queue's own launch command. It never deletes PAUSE files, refuses while
any owner endpoint is up, and was rehearsed on CPU (seven cases plus a PAUSE hold/restore test).

## Checks done on CPU

Build (both compilers' host builds and the device build, old objects reused unchanged),
lane/kernel byte equality with mutation proofs, the real-weight census, production-shape
startup and switching, expected-gain pricing, the inherited harness gates, seal, private-copy
queue plan, entry rehearsal, pin guard, waiter rehearsal, READY written last and the pin guard
re-run: 1,103 pins, 0 that point at another packet's changeable files.
The drain-fix scan reports two unfixed copies; both are vendored history that nothing loads.

## Next

Owner window: stop the three endpoints, keep PAUSE-A, run the two rows on lane B (or lane A),
arm the waiter as written. On a win, build the bundle-8 + S1 record bundle; on a loss, close
S1 with a DO-NOT-REPEAT row from the summary.

## Device result (2026-10-22, lane B window 11:56-12:21 UTC, unit lanequeue-B32)

**S1 is a loss: -6.2%.** One load, five views, every view 13/13 exact with identical draft
proposals, control drift 0.072%:

| View | Selection | tok/s |
| --- | --- | --- |
| 0 | expanded (control) | 58.617 |
| 1 | metadata (S1) | 54.987 |
| 2 | expanded | 58.587 |
| 3 | metadata (S1) | 54.985 |
| 4 | expanded | 58.630 |

Decision (`v5/evidence/device-metadata-v5-B-p183/bracket-summary.json`, `s1_decision`): min gain
-6.216%, screen_winner false, chain rule not met; the waiter logged the decision and exited 0
without a confirmation (`v5/evidence/waiter-decision.json`). The smoke row passed first (12 x 64
exact, one load). No kernel faults in the window; endpoints were stopped only after the live plan
passed and are back as `*-20261022-restore8` (validations true); PAUSE-B re-armed, PAUSE-A untouched
throughout. Window receipts: `lineage/window-20261022/`.

**Reading.** The byte saving did not buy anything: reading 46 fewer bytes per 256 weights and
recomputing `half(d) * sc` per group cost 6.2%, the same size as packet175b D1's 6.7% loss for a
different scale-path change in the same kernels. Two independent scale-path changes with opposite
byte deltas losing the same amount says these dense GEMV lanes are not paying for the scale
bytes; they pay for per-group work in the inner loop. S1 is closed with a DO-NOT-REPEAT row, and
per packet177's rule S2 (B/A would have to be <= 0.90; it is 0.938) is closed with it.
