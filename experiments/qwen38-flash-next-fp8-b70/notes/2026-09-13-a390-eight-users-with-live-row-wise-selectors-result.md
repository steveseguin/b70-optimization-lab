# Result: A390 - live row-wise selectors do not make 2-8 users output-identical; and single-user outputs differ across servers

Preregistration: `2026-09-13-a388-eight-users-with-live-row-wise-selectors-prereg.md` (A388 re-run as A390
with a 6 GB host floor). Head `dc11a3a0a` (= `2a372e86` + the row-wise all-reduce and HC-norm commits),
`max_num_seqs=8`, KV 1,412,136,960, capture sizes [1, 2, 4, 8], selectors at 8, port 20007. Server healthy
at 16:19:42 UTC; host trough 7.93 GB. Same identity-gated oracle as A383, two repeats.

| users | repeat 1: aggregate tok/s, exact | repeat 2: aggregate tok/s, exact | first divergences (r2) |
|---|---|---|---|
| 1 | 30.1, 1/1 | 30.2, 1/1 | - |
| 2 | 10.0 (first two-row batch), 0/2 | 45.5, 0/2 | 97, 87 |
| 4 | 55.3, 1/4 | 56.2, 0/4 | 113, 109, 62, 42 |
| 8 | 70.1, 1/8 | 73.8, 0/8 | 113, 113, 1, 42, 92, 14, 2, 11 |

## Reading

- The batched all-reduce was not the (only) batch-variant term: with both selectors live at 8 rows the
  match rate is unchanged from A383 (3/28 vs 2/28) and the first-divergence positions are largely the
  same prompts and positions (113, 42, 92/95, 14/15, 11). Aggregate throughput is 4-10% lower than A383
  (73.8 vs 81.6 at eight users), the cost of eight per-row collectives per layer.
- Unexpected: the single-user oracle rows differ between A383 (`2a372e86`) and A390 (`dc11a3a0a`) for 3
  of 8 prompts (first differences at tokens 100, 14, 56). Both selectors are gated on `1 < rows`, so the
  one-row arithmetic is the same on both heads; the remaining explanation is that single-user outputs on
  the eight-sequence configuration are not reproducible across servers, which no arm has tested (the
  within-server c=1 repeats only re-ran prompt 0). The certified lines' cross-server reproducibility
  was established at `max_num_seqs=1`.
- Consequence: before any further many-users work, the eight-sequence server itself must be shown to
  reproduce the single-user identity (the certified exact-2K pin `afffd211…` and the same oracle rows on
  two servers). If it does not, the multi-user divergences are partly server-to-server variance and the
  batch-invariance question cannot be asked on this configuration; if it does, the remaining suspects
  are the oneDNN per-M dense-projection primitives and the HC gate-mix mean (agent report, 2026-09-13).
- Publication: the "Many users" cell stays withheld; `dc11a3a0a` is not promoted.
- Evidence: `experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp0-a390-eight-users-rowwise-concurrency-oracle.json`.
