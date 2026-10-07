# Resolution 102 W2 memory observation

Packet102 reached a successful freeze with all four card/worker graph chains exact and all seven model owners resident. This is a receipt-only comparison with successful W1 packet101c; it is not a throughput or final qualification claim.

102 manifest: `25761564f8e6790d25cbc4495662b2be19dfe2001401c5b8966e0a9c09264db4`.
101c manifest: `236637003cf90e2146a8e5bd8fef6aca0a280a1d580c192f5666ae2476f0a966`.

The102transition explicitly binds101c as reviewed predecessor and99b as constructor. Both packets retain identical99b RoPE/runtime manifests and model-verification identity; model-owner device/byte inventories also match. W2 adds a sampler worker, not another model-weight copy.

| Card | W1 post-freeze free GiB | W2 post-freeze free GiB | W2 net extra used MiB | Reported reserved change GiB | W2 margin over2GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| xpu:0 | 7.628361 | 7.203808 | 434.742 | +0.369 | 5.203808 |
| xpu:1 | 12.344238 | 11.989262 | 363.496 | +0.295 | 9.989262 |
| xpu:2 | 9.740879 | 9.740887 | -0.008 | +0.000 | 7.740887 |
| xpu:3 | 14.739845 | 14.739861 | -0.016 | +0.000 | 12.739861 |

Within102, synchronized admission receipts bracket the sequential captures and completed-tail retirement:

| Interval | Card0 net used MiB | Card1 net used MiB |
| --- | ---: | ---: |
| worker0_capture_and_retirement | 518.738 | 533.594 |
| worker1_capture_and_retirement | 432.762 | 361.520 |
| both_workers_before_decode | 951.500 | 895.113 |

Before second capture, card0 had 7.617649GiB and card1 12.257481GiB, both above the explicit7GiB threshold. Card0's margin was 0.617649GiB. The whole-chain temporary admission budget was1,198,784,632bytes/card (1.116455GiB); its floor is judged after chain-check memory is released, and all four cards remained above2GiB.

These are **net physical-free deltas**, not allocation peaks. Normal allocator reuse/release and driver bookkeeping are included; the second-capture interval is not a universal incremental-worker bound. Freeze reservedGiB fields are rounded to three decimals. No new safe-worker-count, maximum resolution, OOM guarantee, or rate claim follows.

The per-request graph-capture memory_before/after fields precede completion of asynchronous submitted work and must not replace these quiescent admission/freeze observations. All exact input paths, complete-fileSHA256 hashes, sizes and byte-valued calculations are in [resolution102-memory.json](../data/resume-20261007/resolution102-memory.json). No runtime source, sealed packet, GPU state, endpoint or host setting was changed.
