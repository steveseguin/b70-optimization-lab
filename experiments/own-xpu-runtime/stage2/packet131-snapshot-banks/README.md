# Packet131: recurrent snapshot buffer rotation

New copy of frozen packet124c, preserving symlinks. CPU preparation in
progress; no GPU result or speed claim. Only the `miss` choice differs:
`batch` control versus `banks-batch` candidate. The existing packet62 mechanism
now needs qualification against bundle7 and packet128b's measured capture cost.

All inherited receipts and preparation helpers are historical dependencies,
not packet131 admission. New evidence lives under `evidence/` and is named by
the `*131.py` entry points. No old seal admits this new candidate.

Run CPU entry points with `nice -n 19 taskset -c 8-15,24-31 env
OMP_NUM_THREADS=2 python3 -B`, stdin `/dev/null`. CPU-only mains cap address
space at 8 GiB; runtime imports do not. `build131.py` uses packet94's exact
compiler turn. Root must remain above 25 GB and build below 300 MB.

- `build131.py`: incremental GNU host and Intel device-target build.
- `census131.py`: production allocation and exact snapshot descriptor census.
- `state131.py`: actual host target/snapshot bytes, GNU/Intel, forced outcomes.
- `seal131.py`: screen seals from new byte, memory and reset evidence.
- `queue131.py`: new proposed jobs and temporary queue tests only.
- `run131.py`: coordinator-only smoke then v4 fresh-load grid.

[Work note](../../../../notes/2026-10-18-own-runtime-packet131.md).
