**Packet 93x — CPU analysis of the lane-A head-transpose loss**

Keep `head=production` for packet 97's lane-A record configuration. The six
original screens show head-transpose 2.369% slower on A and 0.857% faster on B
against each lane's two controls. A's extra hit time comes from rank 1's draft
and target half. Misses hide the draft delay behind correction, so they can
still improve. Output hashes, guesses and acceptance sequences match across
all six screens.

Most of the draft delay is outside its measured GPU compute events. The
receipts do not prove a permanent card or physical-placement effect, and
handoff gaps do not explain it. Both candidates have identical rank-1 logical
allocations and target-head virtual alignment. The draft still uses an
expanded prefix. Full allocation records show only 8.53 MiB saved; the larger
DRM difference was recorded before the candidate allocated its draft prefix.

Lane A's head is card 1 (`27:00.0`), lane B's is card 3 (`47:00.0`). The
microbenchmark used card 2 (`43:00.0`), whose fault history therefore does not
identify the slow A head card. A follow-up needs head and shared/separate
draft-prefix timings on cards 1 and 3, then fresh matched engine repeats.
The next device work is a recommendation; nothing was launched or queued.

[Full analysis](../experiments/own-xpu-runtime/stage2/packet93x-lane-analysis/ANALYSIS.md)
and [JSON](../experiments/own-xpu-runtime/stage2/packet93x-lane-analysis/analysis.json)
retain per-lane/view medians, host gaps, paired component differences, placement
records, source hashes and limitations. The CPU reproducer checks all joins,
original receipt consistency, output/guess parity, reported cycle statistics,
and deterministic recomputation. No GPU, service, sudo, setting or reboot was
used. Existing trees, including CURRENT.md and packet 97, remain frozen; only
the new analysis folder and this requested note were written.
