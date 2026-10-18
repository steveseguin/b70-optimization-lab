# Packet 120 — move target layer 24 to rank 0

CPU-only preparation started about 10:11 UTC, 2.5-hour box. Pull refused
unrelated dirty orchestration files; fetch confirmed main and origin/main at
`b83172aa0f153e4276cc2f004911a3c3262f8e62`. Nothing foreign was changed.
Root starts above 37 GB free; stop below 25 GB. Nice19, CPUs 8–15/24–31,
Python -B, closed stdin, CPU entry-only 8 GiB cap and packet94 compiler turn.
No GPU, service, sudo, host setting, reboot or live queue change is authorized.

History checked: packet63, packet79, packet118 boundaries and SPEED5 closeout.
The older 23/25 rank1-draft layout missed its 32K reserve by 185,030,560 bytes.
It is not this 4K split25. No previous 25/23 ledger result was found. The
literal PLACEMENT:/KVBYTES:/MAXLEN: generator options in the brief were not
found in the checked-in tools; the current full_shape.py executes the real
allocation and preparation paths with address-token device storage instead.

## Census milestone

[Exact census](../experiments/own-xpu-runtime/stage2/packet120-placement/evidence/census-first.json)
uses packet118 bundle7: wide64+halfcache, down tile16, head split, draft
prefix 80,128, other-fusion. Only the generated CPU fixture admits split25
at this stage; original runtime source files and parent packets are unchanged.
Its source snapshot and compressed allocation lists are retained alongside it.

| Placement | Rank | Device arena bytes | Arena headroom | Capacity headroom |
| --- | ---: | ---: | ---: | ---: |
| 24/24 | 0 | 28,144,182,388 | 4,068,072,332 | 6,098,115,468 |
| 24/24 | 1 | 31,425,985,242 | 786,269,478 | 2,816,312,614 |
| 25/23 | 0 | 29,276,806,152 | 2,935,448,568 | 4,965,491,704 |
| 25/23 | 1 | 30,296,914,384 | 1,915,340,336 | 3,945,383,472 |

Capacity is 34,242,297,856 bytes; arena cap stays 30 GiB. Both candidate
ranks exceed the requested 0.5 GiB headroom without changing the cache or
head suffix. Rank0 adds 1,132,623,764 bytes and rank1 loses 1,129,070,858;
the difference is rank0 speculative state and preparation storage. Layer24
is recurrent, so BF16 KV stays 58,195,968 / 67,895,296 bytes at 4K.
Both 256 MiB operator scratch arenas, recurrent banks, private speculative
image, staging, expanded E1 half-cache and 155,750,400-byte rank0 head suffix
are counted by the real allocation calls. Half-cache here means an expanded
on-device expert representation, not a host expert-offload policy.
Prepared command captures run in the fixture. Driver/runtime allocations
outside the arena, residency and possible paging are unmeasured on CPU and
must be logged separately from allocator bytes in the eventual screen.

The first fixture link retained an inherited entry object and refused a
duplicate main; the harness now removes both entry objects, as the parent
full-shape harness does. No model operation changed. Census passes; proceed
to two runtime placement views, exact CPU checks and sealed v4 proposals.
No speed or real-model output result is claimed.
