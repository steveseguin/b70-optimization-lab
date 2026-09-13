# Result: A394 - the exact-mode MTP1 32K ladder reproduces on a second server, hash for hash

Preregistration: `2026-09-13-a394-32k-mtp1-fresh-server-repeat-prereg.md`. A382's packet regenerated with
the 6 GB host floor and the cached-receipt xpu-smi bypass; head `6d872457`, stage v2, exact-mode exports,
MAX_MODEL_LEN 33280, KV 1,341,530,112, never-hit + max-count-2 placement, port 20011. Server healthy at
18:19:39 UTC; host trough 8.11 GB.

| depth | A394 tok/s r1 / r2 | A382 tok/s r1 / r2 | TTFT s | ids | == A382 (and A381) |
|---|---|---|---|---|---|
| 2K | 29.33 (cold) / 47.25 | 29.29 / 47.25 | 31.5 / 11.3 | `afffd211…` | yes |
| 8K | 42.69 / 42.69 | 42.71 / 42.72 | 47.7 | `0126d542…` | yes |
| 16K | 45.52 / 45.57 | 45.59 / 45.56 | 99.4 | `789cbcb8…` | yes |
| 32K | 44.04 / 44.04 | 44.06 / 44.09 | 206.1 | `1cc1699e…` | yes |

## Reading

Two servers, four rows per depth (16 rows total), one hash per depth, rates within 0.1 tok/s: the 32K cell of the
exact-mode MTP1 line is reproducible in the same sense as the certified 4K line (A365/A366). The family
entries for 8K/16K/32K now cite both servers; the front-page cell (44.06) is unchanged. The step left
before a certified long-context claim is a frozen client that pins these four hashes and runs the
quality battery at the served 33,280 capacity, generated from the A305/A364 lineage with the context
options; that is the next publication packet on this line.

Evidence: `experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a394-32k-context-depth-ladder-fresh-server.json`.

Post-interruption audit: row evidence verified directly; teardown rc 143 and cached
GPU receipts do not establish a clean shutdown. See
[recovery note](../../../../notes/2026-09-13-a394-freeze-recovery.md).
