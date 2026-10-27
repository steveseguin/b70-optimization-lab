# Long-context K/V fetch experiment (card 43)

`OWNRT_ATTN_LONG=1` was an exact candidate for launch extents above 8192. It fetched each selected K/V element once per
tile and reused it for all 12 query heads, retaining score/value reduction trees and partial layout. Full F32 KV and
selection ids/order were unchanged.

CPU/oracle evidence: 108 attention cases had zero score/value bit differences; raw-ring tests covered 76 launches and
4,977 positions with exact keys/values/pooled state. Negative controls detected corruption.

The GPU microbenchmark on card 43 rejected the variant before a full-model run:

| Variant at n=2051, hot tiles | Incumbent | Candidate |
|---|---:|---:|
| K and V shared once | 20.42 us | **31.25 us** |
| K only shared once | 20.31 us | **22.92 us** |
| V only shared once | 20.31 us | **25.52 us** |

All three were slower despite reduced fetch traffic. Exactness was 0 failures over 23 cases per variant and no kernel
faults occurred. The lever is closed negatively; no full-model speed claim or integration followed. `analysis.json`
contains the fetch model and `attention-long.patch` retains the experiment.
