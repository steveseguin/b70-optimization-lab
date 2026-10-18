# Packet142 attention-order600 result: null (exact)

One-load v5 bracket `packet142c-attention-order600-bracket-B`, lane B, 21:17–21:25 UTC October 18 (fault count 2). Evidence: `stage2/packet142-class-layout/v5/evidence/device-attention-order600-v5-142c-B/run/views/*/summary.json`. The packet's report step failed afterwards ("missing suffix timing receipt … p105-transfers.jsonl"; the reader expects a head-split receipt these views do not write). The coordinator read the per-view summaries directly:

| View | tok/s | Exact | Acceptance median |
| --- | ---: | --- | ---: |
| 00 control | 58.624 | 12/12 | 0.787 |
| 01 attention-order600 | 58.585 | 12/12 | 0.787 |
| 02 control | 58.634 | 12/12 | 0.787 |
| 03 attention-order600 | 58.620 | 12/12 | 0.787 |
| 04 control | 58.636 | 12/12 | 0.787 |

The candidates sit at −0.08% and −0.02% against the mean control. Control drift is 0.02%. **Null.**

Laying out each layer's attention weights contiguously in kernel order does not recover packet141's 1.47× cold-vs-warm attention gap. That gap is not weight-stream locality the layout can fix. The same mechanism (order600) is in packet145 for the router and gdn.z. Its router bracket runs on idle lane A as a cheap check; if it is also null, the class-layout line closes. Expert gate/up and HC were already ruled out by packet141.
