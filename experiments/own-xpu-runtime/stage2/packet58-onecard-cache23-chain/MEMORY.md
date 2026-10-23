# Production-size memory accounting (packet58-onecard-cache23-chain)

The packet58u/58ah accounting is extended by the packet58-onecard-cache23 re-partition (coordinator
ruling, one-card synthesis 1): the 98,990,252,032-byte admission at a 21.55 GB cache (packet182c) becomes
**100,487,123,456 bytes** at the 23,049,601,024-byte arena (`cache_cap max23`): full host backing of the
+1,496,871,424-byte growth. No admission is lowered. Source: `admission.json` (`admission` block, copied from
packet58-onecard-cache23) and that packet's `memory-plan.json` (every number with its receipt).

| Window | Pinned experts | Resident lookups | Host bound | Reserve | Required available |
| --- | ---: | ---: | ---: | ---: | ---: |
| K1a | 0 | 0 | 4,294,967,296 | 8,589,934,592 | 12,884,901,888 |
| K1b | 0 | 0 | 4,294,967,296 | 8,589,934,592 | 12,884,901,888 |
| KD | 48,627,712,000 | 29,321,610,240 | 91,897,188,864 | 8,589,934,592 | 100,487,123,456 |
| W2m | 48,627,712,000 | 29,321,610,240 | 91,897,188,864 | 8,589,934,592 | 100,487,123,456 |
| WS | 48,627,712,000 | 29,321,610,240 | 91,897,188,864 | 8,589,934,592 | 100,487,123,456 |
| WS128x | 48,627,712,000 | 29,321,610,240 | 91,897,188,864 | 8,589,934,592 | 100,487,123,456 |
| WS128 | 48,627,712,000 | 29,321,610,240 | 91,897,188,864 | 8,589,934,592 | 100,487,123,456 |

All numbers are bytes. K1 is a bounded synthetic fixture, not the full model.
Device cache allocation is 23,049,601,024 bytes in every model window (`--cache-bytes 23049601024`,
`--cache-cap max23`: the whole arena is usable; `max` = 21,552,729,600 usable is the packet182c record policy).
Device-owned bound 29,828,911,360 = floor 32,000,000,000 - reserve 1,500,000,000 - driver
allowance 671,088,640 (measured lifetime overhead 604,827,916 over the packet182c chain).
Device categories: target_nonexpert 5,815,529,984; KV 116,391,936; recurrent
59,019,280; pointer tables 2,359,296; publication staging
1,179,648; half table 262,144; arena 23,049,601,024;
transfer bound 268,435,456; control transaction bound 402,653,184; workspace
bound 113,479,168; category sum 29,828,911,120; margin 240 bytes.
Projected after growth (packet58-onecard-cache23 `memory-plan.json`): allocate() peak 29,338,775,796 (490,135,564
under the bound); DRM 29,943,603,712 (556,396,288 under the unchanged 30.5 GB native/supervisor guard). The
packet58-onecard-cache23 screen measured the same plan live on card 0 (2026-10-23) with no guard trip.

The host categories are disjoint: pinned experts 48,627,712,000; resident lookups 29,321,610,240; remaining
file allowance 4,001,477,120; measured process overhead 565,325,824; independent shadow margin 4,294,967,296;
cache/metadata/staging 5,084,859,392 (3,587,987,968 + the 1,496,871,424 growth); newer observed increment
1,236,992. They total 91,897,188,864 bytes. The unchanged 8 GiB reserve is additional.
The 4 GiB shadow and 8 GiB available-memory stops are retained. No model payload was read to derive this table.
