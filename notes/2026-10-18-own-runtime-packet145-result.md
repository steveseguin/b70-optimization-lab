# Packet145 result: router-order600 and gdnz-order600 both null (exact); class-layout line closed

One-load v5 brackets, 21:43–21:52 UTC October 18, fault count 2. Both smokes passed, including their report steps (the vendored report fix and `ops/rehearse_entry.py --report`). Both brackets' report steps then failed on a missing head-split receipt (`p105-transfers.jsonl`), as in packet142. The coordinator read the per-view summaries (`stage2/packet145-router-gdnz-layout/v5/evidence/device-*-v5-*/run/views/*/summary.json`):

| Bracket | Control 0 | Candidate 1 | Control 2 | Candidate 3 | Control 4 | Exact |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| router-order600, lane A | 58.635 | 58.549 | 58.540 | 58.481 | 58.516 | 12/12 all views |
| gdnz-order600, lane B | 58.638 | 58.604 | 58.616 | 58.574 | 58.595 | 12/12 all views |

Both are null: every candidate is within −0.1% of the controls and below the best one.

With packet142's attention-order600 null (58.585/58.620 vs 58.624/58.634/58.636), all three classes flagged by packet141 (attention 1.47×, router 1.86×, gdn.z 1.30× cold vs warm) show that **contiguous, kernel-order weight layout does not recover the cold-vs-warm gap**. Whatever the warm micros gain is not weight-stream locality that load-time layout can provide. Class-layout (order600) is closed for every class. Do not retry it with a different slab size or ordering without a measured address/traffic mechanism. The bracket report reader still needs the head-split receipt fix if packet142/145 lineage is ever reused.
