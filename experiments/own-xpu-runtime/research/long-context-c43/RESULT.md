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
## Matched unprofiled decode baseline

Follow-up runs on the same card and B19 binary found no multi-millisecond decode bottleneck: 12.473 ms/half at 4096
positions versus 12.531 ms at 30000, only +0.057 ms. Device timestamp modes added about 3.9 ms per half and could drop
retired events, so their apparent slowdown and zero site timings were artifacts. Wall-site comparison showed only +44 us
for QSA select at 30K. The existing 2051-slot cap already keeps long-context attention nearly flat. Further long-context
work should target the 30K prompt's roughly 127-second processing cost, not this nonexistent decode regression.
