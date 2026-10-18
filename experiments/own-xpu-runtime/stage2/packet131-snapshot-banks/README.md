# Packet131: recurrent snapshot buffer rotation

New copy of frozen packet124c, preserving symlinks. CPU preparation; no GPU
result or speed claim. Only the `miss` choice differs:
`batch` control versus `banks-batch` candidate. The existing packet62 mechanism
now needs qualification against bundle7 and packet128b's measured capture cost.

The production census removes 29,601,792 of 48,627,432 capture bytes per
cycle, with zero increase in owned device allocation. See the
[complete census](CENSUS.md), [1,021-source inventory](capture-extents.csv)
and [exactness argument](EXACTNESS.md). Remaining captures already use one
descriptor upload and one flat compute kernel.

All inherited receipts and preparation helpers are historical dependencies,
not packet131 admission. New evidence lives under `evidence/` and is named by
the `*131.py` entry points. Only `evidence/ready131.json`, verified by
`ready131.py`, admits the new CPU preparation. No old seal admits this candidate.

CPU-only mains cap address space at 8 GiB; four state workers each have a
1.5-GiB cap. Runtime imports never set caps. `build131.py` uses packet94's
exact compiler turn. Root must remain above 25 GB and build below 300 MB.
The positive launch-limit probe deliberately starts from an uncapped shell;
it intercepts native execution and allocates only small CPU metadata.

From the repository root, these commands rebuild/verify CPU preparation and
write proposals only. They never launch a device or service:

```sh
env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/qualify131.py </dev/null
env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/limits131.py </dev/null
env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/queue131.py </dev/null
env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/report131.py </dev/null
env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/ready131.py </dev/null
```

- `build131.py`: incremental GNU host and Intel device-target build.
- `census131.py`: production allocation and exact snapshot descriptor census.
- `state131.py`: actual host target/snapshot bytes, GNU/Intel, forced outcomes.
- `extra131.py`: production recurrence and original/fixed reset regression.
- `startup131.py`: both selections through eleven window startup paths.
- `inherited_gate131.py`: full inherited Python paths, K2 replay and real queue validators.
- `oracle131.py`: this copy's actual queue oracle subprocess, no root redirection.
- `python131.py`, `extended_queue131.py`: lifecycle and every queue failure position.
- `arguments131.py`, `limits131.py`: six new screen entries to both native argv boundaries.
- `seal131.py`: screen seals from new byte, memory and reset evidence.
- `queue131.py`: new proposed jobs and temporary queue tests only.
- `run131.py`: coordinator-only smoke then v4 fresh-load grid.

The new allocation and prepared-bank layout is not runtime-switchable in the
existing v5 wrapper. The proposals therefore specify a lane-B 12 × 64 exact
smoke, then fresh loads C/X/C/X/C with twelve cold 128-token prompts per load.
Both candidate loads must win; controls must stay within 3%, and oracle tokens
and acceptance counts must match. These short screens are diagnostic and never
qualify a strict512 record or a submission. No proposal modifies a live queue.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) and
[work note](../../../../notes/2026-10-18-own-runtime-packet131.md).
