# Qwen3.8 Flash-Next FP8 A83 result: eager MTP1 reproduces the graph MTP1 outputs

Date: 2026-09-03 10:54--11:18 EDT
Status: **diagnostic; the depth divergence belongs to the speculative path,
not to graph replay**

## Server

Eager deterministic identity (A66 lineage: `--enforce-eager`, mkldnn
deterministic, public oneCCL twoshots, tuned M1 W13-N32 map, PLE-only UVA)
at 4352 tokens from the NVMe copy with MTP1 and the 32-block MTP1 KV
budget; overlay head `2169dbfe`. Weights 66 s (target) plus 15 s (draft);
ready 7 minutes after launch.

## Battery (same driver and pins as A81)

| gate | A83 (MTP1, eager) | A81 (MTP1, graph) | MTP0 line |
| --- | --- | --- | --- |
| short rows (tok/s) | `9.916134 / 9.605060 / 9.672459` | `38.79 / 44.02 / 38.53` | `22.26-24.73` |
| short hash | `5f407446...` | same | same |
| quality 7 cases / 16-repeat / needle | 6/7, `3b0b3192...`, pass | same | same |
| exact-2K rows (tok/s; TTFT s) | `5.862267 / 5.904584` (159.0 / 102.1) | `7.25 / 6.91` (146.6 / 99.8) | `13.44-14.91` (47-58) |
| exact-2K hash | **`460b0d5c...`** | **`460b0d5c...`** | `afffd211...` |
| exact-4K rows (tok/s; TTFT s) | `6.598454 / 7.385791` (173.1 / 158.8) | `7.61 / 7.62` (166.1 / 151.4) | `12.24-13.50` (89-103) |
| exact-4K hash | **`bf25b9d1...`** | **`bf25b9d1...`** | `c6193cc6...` |
| draft acceptance over the battery | 733 of 787 | 733 of 787 | |

## Reading

- The speculative path is deterministic and graph-invariant: eager and
  graph MTP1 agree token for token at every depth, including the two
  continuations that differ from the MTP0 line, and accept exactly the same
  drafts. The graph is not the cause of the depth divergence.
- The speculative verification path is a different function from
  single-row decode at 2K and 4K prefill (two-row verify step: M=2 GEMMs
  and the GDN spec-decode kernel) while being equal to it at short context
  over hundreds of tokens. A84 measures the logit gap directly.
- The graph's effect on MTP1 is 3.9x at short context (9.7 to 38.8 tok/s)
  but only about 1.15x at depth (5.9 to 7.1 at 2K), whereas on MTP0 it is
  about 4x at short and 3x at 2K. Something in the MTP1 depth step runs
  outside the captured graph or is bound elsewhere; that is a separate
  question from exactness and only worth pursuing once the path is exact.

Under the lab's lossless standard, MTP1 on Flash-Next is not promotable
until its verification step reproduces single-row decode bit for bit at
depth. That is the kernel-side work the 27B FP8 lane did (serial spec
attention, serial GDN gates, M-invariant GEMM paths), now the first item
on this lane's list.

Receipts: run dir `...attempt83/`, tracked
[`diagnostic`](../data/20260903-tp4-mtp1-a83-eager-mtp1-diagnostic.json).
