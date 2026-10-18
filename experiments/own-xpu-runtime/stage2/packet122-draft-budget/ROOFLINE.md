# Packet122 complete draft byte and event budget

Event times are pending until the coordinator completes both fresh processes. No old class times are substituted.

Each row counts unique useful weights and activation/state bytes per step. It is a byte reference, not measured HBM traffic: cache reuse, repeated reads, scratch, launch latency, reductions and instruction cost are excluded. Divide by the historical 555 GB/s calibration only for scale; it is not a hard floor or an attainable-speed claim. No numerical compute floor is justified. Draft INT8 expert scales and BF16/FP32 boundaries are unchanged.

The captured-input 4K fill cycles real host-reference hidden/token captures. This is an operator diagnostic, not a natural prompt or model-speed headline. Event sums exclude transfers, loading, state restoration, host submission and comparison. Complete-step timing is the median of each step sum, not a sum of class medians.

## Occupied context 128

| Draft event class | Weight bytes | Other read bytes | Write bytes | /555 GB/s, µs | Process1, µs | Process2, µs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| merge.embedding_norm | 10,240 | 5,120 | 5,120 | 0.037 | pending | pending |
| merge.hidden_norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| merge.embedding_projected | 13,107,200 | 5,120 | 5,120 | 23.635 | pending | pending |
| merge.projected | 13,107,200 | 20,480 | 20,480 | 23.690 | pending | pending |
| merge.add | 0 | 25,600 | 20,480 | 0.083 | pending | pending |
| begin.0 | 0 | 8 | 4 | 0.000 | pending | pending |
| blk.0.hc.a.norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| blk.0.hc.a.low | 6,553,600 | 20,480 | 1,280 | 11.847 | pending | pending |
| blk.0.hc.a.gate | 6,553,600 | 21,120 | 25,600 | 11.892 | pending | pending |
| blk.0.hc.a.inject | 81,920 | 20,480 | 8 | 0.185 | pending | pending |
| blk.0.hc.f.norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| blk.0.hc.f.low | 6,553,600 | 20,480 | 1,280 | 11.847 | pending | pending |
| blk.0.hc.f.gate | 6,553,600 | 21,120 | 25,600 | 11.892 | pending | pending |
| blk.0.hc.f.inject | 81,920 | 20,480 | 8 | 0.185 | pending | pending |
| final.norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| final.low | 6,553,600 | 20,480 | 1,280 | 11.847 | pending | pending |
| final.gate | 6,553,600 | 21,120 | 25,600 | 11.892 | pending | pending |
| blk.0.qsa.qgate | 62,914,560 | 5,120 | 24,576 | 113.413 | pending | pending |
| blk.0.qsa.k | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.qsa.v | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.qsa.iq | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.qsa.ik | 655,360 | 5,120 | 256 | 1.191 | pending | pending |
| blk.0.qsa.prepare | 2,560 | 26,752 | 26,624 | 0.101 | pending | pending |
| blk.0.qsa.pool | 512 | 3,200 | 2,560 | 0.011 | pending | pending |
| blk.0.qsa.select | 0 | 9,216 | 8,204 | 0.031 | pending | pending |
| blk.0.qsa.attention | 0 | 287,236 | 12,288 | 0.540 | pending | pending |
| blk.0.attention | 31,457,280 | 12,288 | 5,120 | 56.711 | pending | pending |
| blk.0.attn.combine | 0 | 25,616 | 20,480 | 0.083 | pending | pending |
| blk.0.router | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.route | 0 | 1,032 | 80 | 0.002 | pending | pending |
| blk.0.gather | 0 | 5,168 | 51,440 | 0.102 | pending | pending |
| blk.0.expsgate | 40,960,000 | 5,240 | 25,680 | 73.858 | pending | pending |
| blk.0.expsdown | 20,480,000 | 12,920 | 51,240 | 37.017 | pending | pending |
| blk.0.expsgate.check | 0 | 48 | 4 | 0.000 | pending | pending |
| blk.0.expsup.check | 0 | 48 | 4 | 0.000 | pending | pending |
| blk.0.expsdown.check | 0 | 48 | 4 | 0.000 | pending | pending |
| blk.0.expsact | 0 | 25,608 | 12,800 | 0.069 | pending | pending |
| blk.0.shexpgate | 3,276,800 | 5,120 | 1,280 | 5.916 | pending | pending |
| blk.0.shexpup | 3,276,800 | 5,120 | 1,280 | 5.916 | pending | pending |
| blk.0.shexpdown | 3,276,800 | 1,280 | 5,120 | 5.916 | pending | pending |
| blk.0.shared_gate | 5,120 | 5,120 | 2 | 0.018 | pending | pending |
| blk.0.shexpact | 0 | 2,568 | 1,280 | 0.007 | pending | pending |
| blk.0.moe | 0 | 56,370 | 5,120 | 0.111 | pending | pending |
| blk.0.ffn.combine | 0 | 25,616 | 20,480 | 0.083 | pending | pending |
| logits | 256,409,600 | 5,120 | 160,256 | 462.297 | pending | pending |
| argmax | 0 | 160,264 | 8 | 0.289 | pending | pending |
| commit.final | 0 | 12 | 4 | 0.000 | pending | pending |

## Occupied context 4096

| Draft event class | Weight bytes | Other read bytes | Write bytes | /555 GB/s, µs | Process1, µs | Process2, µs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| merge.embedding_norm | 10,240 | 5,120 | 5,120 | 0.037 | pending | pending |
| merge.hidden_norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| merge.embedding_projected | 13,107,200 | 5,120 | 5,120 | 23.635 | pending | pending |
| merge.projected | 13,107,200 | 20,480 | 20,480 | 23.690 | pending | pending |
| merge.add | 0 | 25,600 | 20,480 | 0.083 | pending | pending |
| begin.0 | 0 | 8 | 4 | 0.000 | pending | pending |
| blk.0.hc.a.norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| blk.0.hc.a.low | 6,553,600 | 20,480 | 1,280 | 11.847 | pending | pending |
| blk.0.hc.a.gate | 6,553,600 | 21,120 | 25,600 | 11.892 | pending | pending |
| blk.0.hc.a.inject | 81,920 | 20,480 | 8 | 0.185 | pending | pending |
| blk.0.hc.f.norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| blk.0.hc.f.low | 6,553,600 | 20,480 | 1,280 | 11.847 | pending | pending |
| blk.0.hc.f.gate | 6,553,600 | 21,120 | 25,600 | 11.892 | pending | pending |
| blk.0.hc.f.inject | 81,920 | 20,480 | 8 | 0.185 | pending | pending |
| final.norm | 40,960 | 20,480 | 20,480 | 0.148 | pending | pending |
| final.low | 6,553,600 | 20,480 | 1,280 | 11.847 | pending | pending |
| final.gate | 6,553,600 | 21,120 | 25,600 | 11.892 | pending | pending |
| blk.0.qsa.qgate | 62,914,560 | 5,120 | 24,576 | 113.413 | pending | pending |
| blk.0.qsa.k | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.qsa.v | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.qsa.iq | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.qsa.ik | 655,360 | 5,120 | 256 | 1.191 | pending | pending |
| blk.0.qsa.prepare | 2,560 | 26,752 | 26,624 | 0.101 | pending | pending |
| blk.0.qsa.pool | 512 | 3,200 | 2,560 | 0.011 | pending | pending |
| blk.0.qsa.select | 0 | 263,168 | 8,204 | 0.489 | pending | pending |
| blk.0.qsa.attention | 0 | 4,227,076 | 12,288 | 7.638 | pending | pending |
| blk.0.attention | 31,457,280 | 12,288 | 5,120 | 56.711 | pending | pending |
| blk.0.attn.combine | 0 | 25,616 | 20,480 | 0.083 | pending | pending |
| blk.0.router | 2,621,440 | 5,120 | 1,024 | 4.734 | pending | pending |
| blk.0.route | 0 | 1,032 | 80 | 0.002 | pending | pending |
| blk.0.gather | 0 | 5,168 | 51,440 | 0.102 | pending | pending |
| blk.0.expsgate | 40,960,000 | 5,240 | 25,680 | 73.858 | pending | pending |
| blk.0.expsdown | 20,480,000 | 12,920 | 51,240 | 37.017 | pending | pending |
| blk.0.expsgate.check | 0 | 48 | 4 | 0.000 | pending | pending |
| blk.0.expsup.check | 0 | 48 | 4 | 0.000 | pending | pending |
| blk.0.expsdown.check | 0 | 48 | 4 | 0.000 | pending | pending |
| blk.0.expsact | 0 | 25,608 | 12,800 | 0.069 | pending | pending |
| blk.0.shexpgate | 3,276,800 | 5,120 | 1,280 | 5.916 | pending | pending |
| blk.0.shexpup | 3,276,800 | 5,120 | 1,280 | 5.916 | pending | pending |
| blk.0.shexpdown | 3,276,800 | 1,280 | 5,120 | 5.916 | pending | pending |
| blk.0.shared_gate | 5,120 | 5,120 | 2 | 0.018 | pending | pending |
| blk.0.shexpact | 0 | 2,568 | 1,280 | 0.007 | pending | pending |
| blk.0.moe | 0 | 56,370 | 5,120 | 0.111 | pending | pending |
| blk.0.ffn.combine | 0 | 25,616 | 20,480 | 0.083 | pending | pending |
| logits | 256,409,600 | 5,120 | 160,256 | 462.297 | pending | pending |
| argmax | 0 | 160,264 | 8 | 0.289 | pending | pending |
| commit.final | 0 | 12 | 4 | 0.000 | pending | pending |

Per-row assumptions and formulas are retained in `roofline.json` and this generator. Fused activation and mix consumers have no separate event or extra byte row. The unchanged host embedding decode and input copies are outside the measured kernel sum. See `LEVER-RANKING.md` for the independent candidate decision.
