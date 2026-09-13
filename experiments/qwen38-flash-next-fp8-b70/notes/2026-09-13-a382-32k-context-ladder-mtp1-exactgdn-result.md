# Result: A382 - the exact-mode MTP1 line at a 33,280-token capacity is lossless to 32K, 44 tok/s

Preregistration: `2026-09-13-a375-a376-32k-context-ladder-prereg.md` (A376 re-run as A382). Overlay
`6d872457`, stage v2 (`bbae3c5`), the four exact-mode exports, never-hit + max-count-2 placement,
`MAX_MODEL_LEN=33280`, KV 1,341,530,112 bytes, port 19995. Server healthy at 10:01:19 UTC; host
MemAvailable trough 8.08 GB against the 8 GB floor (the exact-mode scratch adds ~1 GB over A381's 9.16).
Same harness and fixture as A381, two rows per depth.

| depth | MTP1 exact-mode tok/s r1 / r2 | MTP0 (A381) r1 / r2 | TTFT s | output ids | r1 == r2 | == MTP0 |
|---|---|---|---|---|---|---|
| 2K | 29.29 / 47.25 | 33.39 / 33.25 | 31.9 / 11.3 | `afffd211…` (certified pin) | yes | yes |
| 8K | 42.71 / 42.72 | 32.02 / 32.08 | 47.7 | `0126d542…` | yes | yes |
| 16K | 45.59 / 45.56 | 31.37 / 31.33 | 99.5 | `789cbcb8…` | yes | yes |
| 32K | 44.06 / 44.09 | 32.67 / 32.66 | 206.2 | `1cc1699e…` | yes | yes |

## Reading

- The preregistered lossless gate holds at every depth: A382 r1 == r2, and A382 == A381 (the MTP1
  exact-mode line reproduces the MTP0 line's output ids, the lineage's definition of lossless) at 2K,
  8K, 16K and 32K; 2K equals the certified pin `afffd211…`. The exact serial GDN verifier rows in the
  kernel extension therefore stay exact at long context, not only at the 2K/4K certification depths.
- Speed: 1.33-1.45x the MTP0 line at 8K-32K (42.7 / 45.6 / 44.1 vs 32.0 / 31.4 / 32.7 tok/s). The
  2K first row (29.29) is the server's cold first request (warm-up and graph first-touch inside the
  row; TTFT 31.9 s vs 11.3 s for row 2); row 2 at 47.25 is the line's warm 2K rate and matches the
  certified 48.2 within noise. The MTP1 gain grows with depth because the target step is nearly flat
  with depth while acceptance is unchanged.
- The host-memory margin at the trough is 80 MB. Any further widening of the placement, or a third
  exact-mode scratch buffer, needs either a leaner placement or a lower floor; recorded in memory.
- Publication: the "32K input" cell for the exact-mode MTP1 row reads 44.06 tok/s (lab-measured
  depth ladder, both rows one hash, equal to the MTP0 line); the four measurements go into the family
  file with this ladder JSON as evidence. A certified long-context suite (frozen client, fresh servers)
  remains the step between this and a record claim.
