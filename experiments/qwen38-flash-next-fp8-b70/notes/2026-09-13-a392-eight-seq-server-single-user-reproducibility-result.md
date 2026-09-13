# Result: A392 - the eight-sequence server is single-user reproducible within and across servers; dc11a3a0a is retired

Preregistration: `2026-09-13-a391-eight-seq-server-single-user-reproducibility-prereg.md` (A391 re-run with
the full oracle). Head `2a372e86`, `max_num_seqs=8`, KV 1,412,136,960, capture sizes [1, 2, 4, 8],
max-count-2 placement, 6 GB host floor, port 20009. Server healthy at 17:16:54 UTC.

| gate | outcome |
|---|---|
| exact-2K rows vs certified pin | `afffd211…` on both rows (33.9 tok/s) |
| within-server: pass 2 oracle rows vs pass 1 (8 prompts) | identical, 8/8 |
| across servers, same head: pass 1 vs A383's oracle rows | identical, 8/8 |
| across heads: pass 1 vs A390's oracle rows (`dc11a3a0a`) | 3/8 differ (release-plan at token 100, benchmark-analysis at 14, architecture-tradeoff at 56) |
| multi-user identity (both passes) | 1/2, 0/4, 0/8 exact; aggregate 47 / 58 / 78-81 tok/s |

## Reading

- The eight-sequence configuration preserves the certified single-user identity and reproduces itself
  across servers: the multi-user divergences are not server variance, they are deterministic batch
  effects. The lossless many-users question is well-posed on this configuration.
- `dc11a3a0a` changes one-row outputs. Its diff against `2a372e86` is exactly the two gated branches
  (`1 < shape[0] <= max_rows`) and nothing else, so at `max_rows=8` some all-reduce or HC-norm input
  during single-user decode has a leading dimension between 2 and 8 that is not the token dimension:
  the hyper-connection state carries four streams, and a [4, H] tensor is reduced row-wise at 8 but not
  at 2 (the MTP1 lineage's setting, where the selectors were validated). The head is retired; A390's
  multi-user rows were compared against that altered oracle and are not evidence about batch invariance.
- Next: a one-request diag on `dc11a3a0a` + shape logging (every input that enters a row-wise branch,
  once per shape, at `max_rows=8`) to name the offending tensors, then a corrected selector keyed on the
  token dimension. Only after that can the eight-user identity ladder be re-run meaningfully; the oneDNN
  per-M dense primitives and the HC gate-mix mean remain the suspects behind it.
- Evidence: `experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp0-a392-eight-seq-oracle-pass{1,2}.json`.
