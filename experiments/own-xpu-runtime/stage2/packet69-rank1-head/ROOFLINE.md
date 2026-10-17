# Packet69 draft site roofline

Existing packet64 raw device means; no new device run. GB/s uses the stated logical byte model, not hardware traffic counters.

| Site | µs | Logical bytes | GB/s | 590–540 GB/s floor (µs) |
| --- | ---: | ---: | ---: | ---: |
| draft.argmax | 21.047 | 182784 | 8.68 | 0.31–0.34 |
| draft.blk.0.attention | 76.490 | 31457280 | 411.26 | 53.32–58.25 |
| draft.blk.0.hc.a.gate | 27.749 | 6553600 | 236.18 | 11.11–12.14 |
| draft.blk.0.hc.a.inject | 47.826 | 81920 | 1.71 | 0.14–0.15 |
| draft.blk.0.hc.a.low | 22.152 | 6553600 | 295.85 | 11.11–12.14 |
| draft.blk.0.hc.f.gate | 27.233 | 6553600 | 240.65 | 11.11–12.14 |
| draft.blk.0.hc.f.inject | 19.749 | 81920 | 4.15 | 0.14–0.15 |
| draft.blk.0.hc.f.low | 21.901 | 6553600 | 299.24 | 11.11–12.14 |
| draft.blk.0.qsa.attention | 116.010 | 207531 | 1.79 | 0.35–0.38 |
| draft.blk.0.qsa.k | 8.877 | 2621440 | 295.31 | 4.44–4.85 |
| draft.blk.0.qsa.qgate | 127.289 | 62914560 | 494.26 | 106.63–116.51 |
| draft.blk.0.qsa.v | 8.274 | 2621440 | 316.84 | 4.44–4.85 |
| draft.final.gate | 27.182 | 6553600 | 241.10 | 11.11–12.14 |
| draft.final.low | 21.504 | 6553600 | 304.76 | 11.11–12.14 |
| draft.logits | 521.300 | 292454400 | 561.01 | 495.69–541.58 |
| draft.merge.embedding_projected | 33.291 | 13107200 | 393.72 | 22.22–24.27 |
| draft.merge.projected | 58.509 | 13107200 | 224.02 | 22.22–24.27 |
| draft.transfer.hidden | 2.799 | 20480 | 7.32 | 0.03–0.04 |
| draft.transfer.proposal | 0.000 | 4 | unresolved timer | 0.00–0.00 |
| draft.transfer.status | 0.000 | 4 | unresolved timer | 0.00–0.00 |

The full JSON retains the byte definition and official draft tensor identity for each site. Matrix rows count a single weight read; attention counts unique BF16 operands only. These are lower-bound byte models. No bandwidth is invented for zero-time copies, host waits, or target sites absent from packet64.

Target head: 794,624,000 expanded resident bytes, 1,346.82–1,471.53 µs bandwidth floor; measured time pending. Final HC/norm, target argmax and outside transfers are named in the new measurement report; host submission/waits remain a separately reported residual.
