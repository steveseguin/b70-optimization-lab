# Packet 113 GDN-row recurrence: 1.5x slower, closed (2026-10-18)

Lane B, card 2, `packet113-micro-B-2` 09:13 UTC (the first process had refused twice: at 09:04 on the 19 GiB root floor, at 09:12 because the failed transient unit still existed; it was not re-run after this result). 40 measured iterations per mode per context; 768/768 recurrence byte cases and 572 layer comparisons equal. No fault (count 2).

| Context | Production recurrence µs | p113 (one subgroup per state row) µs | Ratio |
| ---: | ---: | ---: | ---: |
| 128 | 23.96 | 35.94 | **1.500** |
| 4096 | 23.91 | 36.04 | **1.508** |

Kill gate ≤ 0.6×. Removing work-group barriers by giving each state row its own subgroup made the kernel 50% slower (more, smaller work items re-reading shared vectors); closed. Codex p113i (v5 integration prep) was stopped by the coordinator at 09:15 when this result arrived.

Evidence: `experiments/own-xpu-runtime/stage2/packet113-gdn-row/evidence/micro-B-2/native/iterations.jsonl`.
