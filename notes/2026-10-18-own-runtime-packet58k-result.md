# Packet 58k one-card screen: port loses (2026-10-18)

Lane A, card 0, whole-host lease, packet 58k fix `6ffec6f7c`, output
`stage2/packet58k-onecard-screen/evidence/card0-screen-b/`.

| Arm | Window | 12-prompt median (submission100) | fixed64 median | Exact |
| --- | --- | ---: | ---: | --- |
| production-before | 07:30–07:39 UTC | **24.969** | 24.992 | 12/12 |
| port (down-tile16 + route-fast + rec-both-plus) | 07:41–07:49 UTC | **22.181** | 22.047 | 12/12 |

- Port is **−11.2%**. Both arms chose zero-copy expert misses (K1 useful GB/s: production 13.96/14.03, port 17.56/17.47; threshold 12.5), so the loss is not a streamed-miss fallback.
- The coordinator pulled `production-after` (07:49) because a −11% result cannot become a ≥ 0.5% win; the bracket is therefore incomplete by design and packet 58m's `ready.json` stays false. No fault (count 2).
- The 2-card levers do **not** transfer as a bundle to the one-card engine. Which one hurts is unknown: on one card the down weights of missed experts are read over PCIe by zero-copy, so tile16's 16-row interleave may change the host read pattern; route-fast and rec-both-plus were never measured alone on one card.
- Production at 24.97 in this screen is the same configuration as the 24.339 record chain; it is not a new record and will not be resubmitted.
- Next: leave-one-out on one card only if a CPU analysis predicts a positive single lever (packet 58n).
