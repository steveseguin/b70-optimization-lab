# Host memory fault evidence, 2026-10-03 (four-B70 host)

Raw evidence behind [Host stability and fault diagnosis](../../docs/host-stability-and-fault-diagnosis.md).

| File | What it is |
| --- | --- |
| `memtester-20261003-summary.txt` | Per-worker state when the 8 x 13 GiB locked `memtester` run was stopped |
| `memtester-20261003-worker-{3,7}-failures.txt` | Every `FAILURE:` line from the two workers that failed (1,024 and 168) |
| `memtester-20261003-phys-addresses.txt` | Physical pages behind the failing offsets, from `/proc/<pid>/pagemap` |
| `physmap-20261003-run1.jsonl` | Targeted test, last 4 MiB of each 1 GiB block, 3 rounds: 128 mismatches |
| `physmap-20261003-run2.jsonl.xz` | Targeted test, last 8 MiB, 5 rounds before the host reset itself: 226,271 mismatches |
| `physmap-20261003-run2-summary.json` | Counts per round, per byte lane and per 32 KiB physical chunk, with the sha256 of the uncompressed log |
| `physmap-20261003-run3-all-after-offline.jsonl` | Every page of 99 GiB after memory blocks 53-57 were taken offline, 2 rounds: 0 mismatches |

Tools: [`tools/physmap_memtest.py`](../../tools/physmap_memtest.py),
[`tools/memtester-phys-addresses.py`](../../tools/memtester-phys-addresses.py).
