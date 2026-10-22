# 2026-10-22: packet186, two-card V3 (verified-boundary rebalance), CPU preparation

Packet: [`experiments/own-xpu-runtime/stage2/packet186-twocard-v3/`](../experiments/own-xpu-runtime/stage2/packet186-twocard-v3/README.md).
Proposal: `experiments/own-xpu-runtime/ops/lane-queue/proposed-p186-two-card-B.txt` (four lane-B rows). It was not queued.

No GPU, `/dev/dri`, device binary run, service, setting, PAUSE/STOP or queue file was touched. Nothing was committed.
Compilers ran only after `window-p185-driver.service` was inactive. It read active at 14:23 and 14:34 UTC, inactive
at 14:46 and 14:52 UTC, and the first compile started at 14:52:54 UTC.

## Why

Packet185 measured V3's kill thresholds on lane B today and decided **V3 GO**:

* u = 0.222 ms;
* decoupled B - A = 0.851 ms;
* sigma = 0.403 ms/cycle;
* every view exact;
* drift 0.145 %.

The coordinator's ruling was to build V3.

## What V3 is

* The full target head is on rank 1, with no merge.
* Rank 0 holds the GDN layers 24-25. After every rank-0 accept it runs them for the verified token in one boundary
  command, then exports layer 25.
* Rank 1 starts at layer 26. The draft is unchanged.
* Packet153's static snapshot is bundled with it. Under V3, rank 0's speculative half binds the emission, so the
  saving reaches the critical path. Packet153 closed static only as a standalone change.

**Build.** The three entry TUs were rebuilt over the 78 pinned parent objects, with 0 warnings. The device ELF is
`693cc194...`.

**Bundle-8 identity.** The production selection is bundle 8. At production shape it is capture-identical to
packet185.

## Priced on measured numbers

The replay runs per interval over packet185's two un-split views (`analysis/price_v3_measured.py`).

| Case | Gain over the best control (58.621) | V3 rate |
|---|---:|---:|
| central (s1 0.48, c0 0.55) | +2.64 % | 60.17 tok/s |
| anchored on the measured rank-0 layer cost (0.483 ms/layer) | +2.76 % | |
| anchored + static | +2.95 % | 60.35 tok/s |
| corner c0 0.73 | +2.17 % | |
| corner s1 0.39 | +1.70 % | |
| both corners | +1.24 % | |

* **Break-evens for +2 %:** c0 at most 0.768 ms; s1 at least 0.415 ms.
* **Hits** fall from 14.77 to 14.08 ms. **Misses** rise from 25.71 to 26.15 ms, because the boundary is serialized
  after the corrected half.

## Moved-layer state

* **Never guessed.** Layers 24-25 on rank 0 are neither banked nor in the speculative image. The image capture is
  unchanged at 19.0 MB.
* **Guarded.** The boundary refuses unless the last rank-0 command accepted the matching (position, token). For
  decode positions, the token must also match rank 1's own verification.
* **Ordered.** No rank-0 half may start before the pending boundary.
* **CPU-tested.**
  * The engine-level sequence matches a direct reference on every rank-0 byte. It covers hits, misses at every
    cancellation cut, and abandoned redos.
  * A detecting negative control is included.
  * Two-rank miniature one-load brackets ran in both start orders: 54 requests, with hits, misses, no-guess and EOS.
    Tokens, fixtures, proposals, draft state and target state all equal the production-layout reference.

## Memory

| | Change | Arena headroom remaining |
|---|---|---:|
| Rank 0 | +2,100,819,444 B: layers 24-25 add +2,258,141,716 B, the suffix head frees 157,322,272 B | 1.97 GB (of 4.07) |
| Rank 1 | +155,750,384 B | 0.63 GB (of 0.79) |

V3 rows add the 2.26 GB device delta to host admission.

## Rows (proposal, lane B, chained)

| Row | Content | Expected time |
|---|---|---:|
| 1 | V3 smoke | ~300 s |
| 2 | fresh bundle-8 control | ~217 s |
| 3 | one-load U/V3/U/V3/U bracket | ~486 s |
| 4 | fresh bundle-8 control | ~217 s |

The total is about 23 min.

**Decision `s186_decision`:**

* **Screen winner:** V3 is at least +0.5 % over every control view.
* **Chain rule:** V3 is at least +2 % over every split-head control AND at least 59.974 tok/s.

The rule was tested on packet185's and packet183's real summaries.

## Next

If the chain rule is met, build the record bundle (bundle 8 + V3 + static): a fresh chain on cards 0+1, as in
packets 136/143. See the packet README for the exact recipe.

## Device result (2026-10-22, lane B window 16:09-16:34 UTC, unit lanequeue-B34): chain rule met

| Row | Content | Rates (tok/s, class-balanced) | Exact |
| --- | --- | --- | --- |
| 0 | V3 smoke, 12 x 64 + incident64 | 60.137 (smoke, no verdict) | 13/13, draft proposals identical |
| 1 | fresh bundle-8 control (split head) | 58.595 | 13/13 |
| 2 | one load, U / V3 / U / V3 / U | 57.832 / **60.573** / 57.802 / **60.533** / 57.840 | every view 13/13, draft proposals and acceptance identical |
| 3 | fresh bundle-8 control (split head) | 58.441 | 13/13 |

`s186_decision` (`v5/evidence/device-row3-control-production-B-p186/bracket-summary.json`): screen winner and
**chain rule met**: min gain vs every control +3.31% (vs the un-split views +4.66%), slower V3 view 60.533 >=
1.02 x 58.798109 = 59.974; split-control drift 0.26%, U drift 0.07%. Measured mechanism: rank-1 saving per
moved layer 0.463 ms (threshold 0.39), boundary command on rank 0 1.026 ms for the two layers (0.513 per layer,
threshold 0.73); hit cycle 14.78 -> 14.06 ms (A 12.51 -> 12.09, B 13.16 -> 12.43), miss 25.71 -> 25.75 ms;
rank 1 binds the emission on 100% of V3 hits. No kernel faults; endpoints restored afterwards as
`*-20261022-restore10`. **Next: the record bundle** (bundle 8 + V3 + packet153 static snapshot, fresh chain
on cards 0+1) as packet187; nothing in this packet certifies a record.
