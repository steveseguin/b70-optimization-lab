# Bundle 8 target audit against packet58ab

The selection authority is `packet136-record-bundle/bundle-selection.json`.
Source references below are siblings under stage2. These are historical
two-card gains, not one-card predictions or additive measurements.

| Missing selection | Mechanism | Two-card gain and evidence | Disposition |
| --- | --- | --- | --- |
| packet73 hc-wide | Adjacent HC gate rows share inputs; retain independent ordered SG32 trees (`p73_hc.hpp`, packet136 `p60_submit.cpp`). | +0.976% A / +0.731% B versus mean controls, `packet85-critical-path/MODEL.md` row HC-wide. | Runtime HC geometry dimension. |
| packet65 wide64 | Smaller expert workgroups and wide packed-code loads preserve 32 logical accumulation lanes. Packet58ab's actual frozen expert object uses WG256; its capture overlay does not change geometry. | +5.385% A / +4.796% B versus mean controls, `packet85-critical-path/MODEL.md`. | Separate `wide64` expert choice and full `wide64+halfcache` composition. |
| packet90 E1 halfcache | Cache exact FP16 scale decoding; original IQ2 rows grow 820→840 bytes (`p90_layout.hpp`, `p90_expert.hpp`). | +0.28%, 55.657 tok/s, [result](../../../../notes/2026-10-18-own-runtime-packet90-result.md). | Runtime expert dimension; exact full-half lookup adaptation retains the one-card 820-byte layout. Literal wider layout is excluded from this immutable one-load bracket. |
| packet109 other-fusion | Route/shared activation and shared-down/ordered mixture/shared blend; 72 fewer launches per half, preserving BF16 intermediates. | Strict +0.318%, about 0.05 ms/half, [result](../../../../notes/2026-10-18-own-runtime-p109-v5-and-headsplit-A.md). | Runtime fusion dimension. Includes the required exact route-fast implementation. |
| packet76 ordered retirement | Test last event's ordered-prefix proof instead of querying each earlier event (`owner_retire.cpp`). Historical enablement is rank1 only. | +1.053% A / +0.409% B versus mean controls; A versus first control +0.450%, `packet85-critical-path/MODEL.md`. | `retirement=production|ordered-foreground`: adapt the proof to two terminal events, one per in-order foreground queue. Keep separate maintenance ownership and both foreground synchronizations/error checks. |
| packet105b target head split | Divide target head between two ranks, transfer hidden state and merge exact winner. | +0.36% B / +0.38% A, same p109/head-split result note. | Excluded: no second card on this target-only line. |

Packet58ab already has packet60 HC fusion and packet100 down-tile16. Its
route-fast/rec-both-plus alternative was tested in packet58r: strict +0.37%,
inconclusive and closed. It is not repeated alone. Packet58t resident lookup
copies lost 0.162% against the warm control and remain closed. Draft HC,
draft prefix, split draft attention, placement, rollback banks and batched
miss restore have no target-only one-card execution path. Final HC remains
unchanged. No changed precision or oracle is admitted.

All source copying and current byte proofs are local to packet58ag. The
oracle stays an immutable binding. Historical parent binaries are linked and
hash-bound; no mutable sibling source is a runtime build dependency.
