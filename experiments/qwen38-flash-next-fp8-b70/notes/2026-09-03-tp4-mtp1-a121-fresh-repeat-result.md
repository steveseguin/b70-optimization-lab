# A121: fresh-server repeat of the frozen MTP1 client (2026-09-03, 22:32-22:53)

The byte-identical A120 packet at attempt 121 (port 19793) on an
independently started server, two minutes after A120's teardown with a
clean kernel journal. Client gates: `PASS recovery quality short-repeat
exact-2K-repeat exact-4K-repeat PLE-only 4352 MTP1 QSA-stable treatment`.

| gate | A121 | A120 |
|---|---|---|
| quality | 6/7 semantic (`code_execution=30`), 16/16 one hash `3b0b3192...`, exact needle | same |
| short p146/o256 after first text, tok/s | `22.02 / 31.38 / 27.58`, median `27.58`, hash `5f407446...` | `22.19 / 28.39 / 26.72`, median `26.72`, same hash |
| exact 2K, 99-interval tok/s (TTFT s) | `9.17 / 9.15` (95.4 / 78.3), hash `afffd211...` | `8.92 / 8.84` (94.7 / 83.5), same hash |
| exact 4K, 99-interval tok/s (TTFT s) | `8.01 / 8.05` (151.6 / 140.1), hash `c6193cc6...` | `7.14 / 7.43` (149.7 / 145.2), same hash |
| runtime receipt (after) | 786 size-2 FULL dispatches, 0 size-1 | 786 size-2, 0 size-1 |

Every output on both servers equals the MTP0 line's authority. Pair
centers: short `27.15 tok/s` (median of the two attempt medians; six rows
`22.02-31.38`), exact-2K median `9.04` (four rows `8.84-9.17`), exact-4K
median `7.72` (four rows `7.14-8.05`). Against the MTP0 line (short center
`22.66`, exact-2K `13.99`, exact-4K `12.78`): 1.20x at short context, 0.65x
at 2K, 0.60x at 4K, with about 1.6x the time to first token at depth. Data:
`../data/20260903-tp4-mtp1-a121-frozen-client-summary.json`,
`../data/20260903-tp4-mtp1-a121-fullgraphdet-runtime-after.json`.
