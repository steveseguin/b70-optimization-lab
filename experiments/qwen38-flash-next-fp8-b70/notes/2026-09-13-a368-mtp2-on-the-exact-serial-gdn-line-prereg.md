# Preregistration: A368 - two speculative tokens on the exact-serial-GDN line

## Question

On the fused-QSA head, MTP2 was lossless within the lineage but slower than MTP1 (A309,
2026-09-07: exact-2K 35.12 vs 38.97 tok/s) because every verifier row paid the Python serial
GDN path. With the verifier rows in the kernel extension's exact mode the per-row tax is gone
at two rows (42.7 -> 33.7 ms). Does a three-row verify step now make MTP2 the faster setting?

## Treatment

A368 = the frozen A309 MTP2 frozen-client packet (head 6d872457, two speculative tokens,
row-wise selectors at 3 rows) with only the kernel stage (v2 `bbae3c5`), the exact-mode
exports and the client's matching identity checks moved, by
`tools/rewrite-q38-a309-to-a368-mtp2-native-exact-gdn-screen.py`. Port 19981. The extension's
exact mode is generalised to the MTP row count (`ad25aa9`); three rows have not been exercised
before, so the server's health is the first gate.

## Predictions

- Exactness: exact-2K `afffd211…` and exact-4K `1d833e5f…` (A309 held afffd211 at 2K), quality
  6/7 with the inherited miss, 16/16 repeat.
- Speed: the two-row step lost 8.7 ms of its 15.5 ms excess over one row; if the three-row
  step loses proportionally, MTP2's exact-2K row is above MTP1's 48.2 only if the acceptance of
  the second draft token pays for a step of roughly 40 ms. A309's 35.12 against A305's 38.97 puts
  the break-even close; the arm decides.

## Stop rules

Server fails health (three-row exact mode); any pin differs; client FAIL. A pass above 48.2 at
exact-2K with the pins held sends MTP2 to a fresh-server repeat and the record suite; a pass below
closes MTP2 on this line with the number recorded.

## Amendment (04:45 UTC): A368 failed in the client, re-run as A374

A368's server came up healthy at 04:36 UTC (the three-row exact mode captured and served), but the
frozen client stopped at its first pin: the A309 client names its runtime verifier
`verify-q38-a309-fullgraph-runtime.py`, a file that never existed (the a139->a309 generator renamed
the attempt inside the file name; the 2026-09-07 screen used a row driver, not this client). The
digest it pins is `verify-q38-a139-fullgraph-runtime.py`'s. The generator now maps the name back
to the a139 file; the arm is regenerated as A374 (port 19987) and queued behind the A369-A373
decomposition chain with the five-minute gap. The server health itself answers the first gate:
the extension's exact mode accepts three verifier rows.

## Amendment 2 (07:10 UTC): A374 stopped at the next latent pin, re-run as A380

A374's server was healthy at 07:06 UTC (three verifier rows in the exact mode capture and serve
again) and the client passed the verifier-file pin, then stopped at "W13-N32 selection verifier
drifted": the A309 client pins the selection verifier at its 2026-09-07 bytes (`20546ff1…`), and
the verifier was repointed at the corrected fused head afterwards (`260ad72c`); the A305/A364
clients pin the current file (`c874852b…`), which passes. The generator now repins it; the arm is
regenerated as A380 (port 19993), queued after A379.
