# Production-size memory accounting

The private packet58u bundle is extended by the unchanged packet58ah cache
allowance. The 95,401,027,072-byte admission at an 18 GB cache becomes
98,990,252,032 bytes at a 21.55 GB cache. No admission is lowered.

| Window | Pinned experts | Resident lookups | Host bound | Reserve | Required available |
| --- | ---: | ---: | ---: | ---: | ---: |
| K1a | 0 | 0 | 4,294,967,296 | 8,589,934,592 | 12,884,901,888 |
| K1b | 0 | 0 | 4,294,967,296 | 8,589,934,592 | 12,884,901,888 |
| KD | 48,627,712,000 | 29,321,610,240 | 90,400,317,440 | 8,589,934,592 | 98,990,252,032 |
| W2m | 48,627,712,000 | 29,321,610,240 | 90,400,317,440 | 8,589,934,592 | 98,990,252,032 |
| WS | 48,627,712,000 | 29,321,610,240 | 90,400,317,440 | 8,589,934,592 | 98,990,252,032 |
| WS128x | 48,627,712,000 | 29,321,610,240 | 90,400,317,440 | 8,589,934,592 | 98,990,252,032 |
| WS128 | 48,627,712,000 | 29,321,610,240 | 90,400,317,440 | 8,589,934,592 | 98,990,252,032 |
| WSCREEN | 48,627,712,000 | 29,321,610,240 | 90,400,317,440 | 8,589,934,592 | 98,990,252,032 |

All numbers are bytes. K1 is a bounded synthetic fixture, not the full model.
WSCREEN uses the full resident budget for smoke and all five bracket views.
Device cache allocation/usage is 21,552,729,600 bytes in every model window.
The full device-owned bound is 29,963,128,848 bytes, driver allowance 536,870,912,
and device reserve 1,500,000,000, within the 32,000,000,000-byte floor.

The host categories are disjoint: pinned experts 48,627,712,000; resident
lookups 29,321,610,240; remaining file allowance 4,001,477,120; measured
process overhead 565,325,824; independent shadow margin 4,294,967,296;
cache/metadata/staging 3,587,987,968; newer observed increment 1,236,992.
They total 90,400,317,440 bytes. The unchanged 8 GiB reserve is additional.

Anonymous copies replace the same bytes in the original 33,323,087,360-byte
file allowance. Live accounting is completed pinned experts + true GPUActive
shadow + all process RssAnon + 4,001,477,120 file allowance. It does not add
planned resident bytes again or subtract them from RSS. Partial copies are
charged as they grow. Clean source-file pages stay naturally reclaimable.
The 4 GiB shadow and 8 GiB available-memory stops are retained.

The 29,321,610,240-byte tensor count is production metadata, not a miniature
fixture. Packet58t already measured copies on the old line; this composition's
full allocation and native census still require the coordinator device run.
No model payload was read to derive this table.
