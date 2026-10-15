# Packet45 audit 6

All 28 production-size rows pass; no additional defect found. No device was opened or executed, and no model weight payload was read.

The sparse CPU backend runs the actual Engine, draft owner, prepared bindings, rollback capture/restore, request reset and readback paths. Tensor sizes come from the target plan and official draft manifest. Weight reads and numerical compute are replaced; allocation sizes, CopyEngine guards and admission rules stay intact. Five positions cover zero, 31/32 and the last two context positions. Twenty native replays cover the common KD, MTP and sequential paths; WS/WS128x/WS128 share the same MTP allocation/lifetime path, with separate real storage projections. W0p uses its unchanged 256-byte geometry and 2,000 checked copies.

The census measures explicit peak live allocation bytes, not driver residency. Headroom is against the stricter of the 30 GiB Engine cap and physical capacity less the 1.5 GB reserve. KD occupies the selected physical card; the other card has no KD allocations. The tightest headroom is 448.06 MiB. The 375,396 model-path copies all satisfy the unchanged checker; the largest is exactly 128 MiB in chunked rollback.

Binary payload writes in this size-only replay are counted and suppressed. Empty sink outputs were inventoried and removed; progress logs were compressed and verified. They are never oracle output. The per-card censuses, source-bound static inventory of every copy expression and host admission rule, storage budget records, and compile/run logs are under `evidence/audit6/` and `audit6-gates.json`. All 28 storage reservations pass the actual `admit` function. Prior CPU rehearsals shrank production tensors; this gate retains their production byte sizes.

| Window | Context | Draft rank | Card 0 headroom MiB | Card 1 headroom MiB | Max copy MiB | Storage projection MiB | admit |
|---|---:|---:|---:|---:|---:|---:|---|
| W0p | 4096 | 0 | 30720.00 | 30720.00 | 0.000244141 | 30.52 | pass |
| KD | 4096 | 0 | 901.31 | 30720.00 | 4 | 550.54 | pass |
| W2m | 4096 | 0 | 2459.03 | 1971.93 | 128 | 667.77 | pass |
| WS | 4096 | 0 | 2459.03 | 1971.93 | 128 | 1033.98 | pass |
| WSs | 4096 | 0 | 6458.44 | 1971.93 | 128 | 1033.98 | pass |
| WS128x | 4096 | 0 | 2459.03 | 1971.93 | 128 | 1228.98 | pass |
| WS128 | 4096 | 0 | 2459.03 | 1971.93 | 128 | 1033.98 | pass |
| W0p | 4096 | 1 | 30720.00 | 30720.00 | 0.000244141 | 30.52 | pass |
| KD | 4096 | 1 | 30720.00 | 901.31 | 4 | 550.54 | pass |
| W2m | 4096 | 1 | 4317.18 | 901.31 | 128 | 667.77 | pass |
| WS | 4096 | 1 | 4317.18 | 901.31 | 128 | 1033.98 | pass |
| WSs | 4096 | 1 | 4317.18 | 4100.28 | 128 | 1033.98 | pass |
| WS128x | 4096 | 1 | 4317.18 | 901.31 | 128 | 1228.98 | pass |
| WS128 | 4096 | 1 | 4317.18 | 901.31 | 128 | 1033.98 | pass |
| W0p | 32768 | 0 | 30720.00 | 30720.00 | 0.000244141 | 30.52 | pass |
| KD | 32768 | 0 | 448.06 | 30720.00 | 4 | 744.79 | pass |
| W2m | 32768 | 0 | 1746.78 | 1518.68 | 128 | 1509.52 | pass |
| WS | 32768 | 0 | 1746.78 | 1518.68 | 128 | 1875.73 | pass |
| WSs | 32768 | 0 | 5810.94 | 1518.68 | 128 | 1875.73 | pass |
| WS128x | 32768 | 0 | 1746.78 | 1518.68 | 128 | 2070.73 | pass |
| WS128 | 32768 | 0 | 1746.78 | 1518.68 | 128 | 1875.73 | pass |
| W0p | 32768 | 1 | 30720.00 | 30720.00 | 0.000244141 | 30.52 | pass |
| KD | 32768 | 1 | 30720.00 | 448.06 | 4 | 744.79 | pass |
| W2m | 32768 | 1 | 3540.18 | 448.06 | 128 | 1509.52 | pass |
| WS | 32768 | 1 | 3540.18 | 448.06 | 128 | 1875.73 | pass |
| WSs | 32768 | 1 | 3540.18 | 3711.78 | 128 | 1875.73 | pass |
| WS128x | 32768 | 1 | 3540.18 | 448.06 | 128 | 2070.73 | pass |
| WS128 | 32768 | 1 | 3540.18 | 448.06 | 128 | 1875.73 | pass |

Static copy-site inventory (complete expressions and bounds are in the JSON gate):

| Source | Line | Largest n bytes | Limit bytes | Scope |
|---|---:|---:|---:|---|
| main.cpp | 728 | 4194304 | 134217728 | all model windows |
| main.cpp | 740 | 4194304 | 134217728 | all model windows |
| main.cpp | 1152 | 20480 | 134217728 | all model windows |
| main.cpp | 1531 | 20480 | 134217728 | single-process decode only; not used by listed windows |
| main.cpp | 1544 | 4 | 134217728 | single-process decode only; not used by listed windows |
| main.cpp | 1545 | 4 | 134217728 | single-process decode only; not used by listed windows |
| mtp.hpp | 197 | 20480 | 134217728 | KD and MTP model windows |
| mtp.hpp | 216 | 4 | 134217728 | KD and MTP model windows |
| mtp.hpp | 217 | 4 | 134217728 | KD and MTP model windows |
| mtp.hpp | 254 | 4 | 134217728 | KD and MTP model windows |
| mtp.hpp | 255 | 20480 | 134217728 | KD and MTP model windows |
| rank.hpp | 154 | 20480 | 134217728 | two-rank model windows |
| strict_snapshot.hpp | 32 | 134217728 | 134217728 | two-rank model windows |
| rank_canary.hpp | 32 | 256 | 4096 | W0p |
| rank_canary.hpp | 37 | 256 | 4096 | W0p |
