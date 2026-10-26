# Exact O(n) QSA select (2026-10-26), serving in engine bd476fb8af0e (`OWNRT_SELECT_TOPK=1`)

## Problem

At long context, decode slowed mostly in the QSA select. The rank-1 profile at 30K positions (card 27, 7 QSA layers)
showed:

| Pass | Time |
|---|---|
| select pass 0 (indexer scores, one subgroup per block) | 1,271 µs |
| select pass 1 (all-pairs rank count, O(n²)) | 612–1,500 µs |
| attention | 1,326 + 326 µs |

The rank-1 half was 20.5 ms at 30K, against 16.7 ms at short context.

## Change

All of it is in `specialised_submit.cpp`, behind the opt-in switch.
- **Pass 0:** one work item per block. Each head's 128-leaf adjacent pairwise tree runs in registers: groups of four,
  then strides 1..16. These are the same additions in the same order as the subgroup tree and `private_tree<128>`.
- **Pass 1:** one 1,024-lane work-group per row.
  - The finiteness check is as before.
  - The count-th largest bit pattern comes from a three-pass radix select (digits 11/11/9; scores are ≥ +0, so bits
    order like values).
  - Compaction runs in index order with two group scans.
  - Ranks are counted only against the selected set, with the same float comparisons.
  - Every block that outranks a selected block is itself selected, so the ids are identical.

## Evidence

- **Lab (card 27, rank 1):** a 30K batched prefill plus 16 decode steps, all 1,079 buffers bitwise equal to the old
  kernels. This held for each variant: binary search, radix, register-tree pass 0 and chunked compaction.

  | Rank-1 half at 30K | Before | After |
  |---|---|---|
  | select | 2,836 µs | 624 µs |
  | span | 20.52 ms | 18.35 ms |
  | 30K prefill | 353 s | 325 s |

- **Service:**
  - **Gates:** F32 oracle at 32K zero differences; prefill gate 13/13; continuation gate passed.
  - **12-prompt suite:** all 5,965 tokens and MTP hits identical, 48.61 tok/s (B3: 48.21).
  - **10.7K-token long-context test** (`longctx_test.py`, frozen document): both turns' output ids identical to
    1ccb7712cc7a.

    | 10.7K test | 1ccb7712cc7a | bd476fb8af0e |
    |---|---|---|
    | decode | 44.67 tok/s | 45.59 tok/s |
    | prompt read | 107.0 s | 102.5 s |

## Remaining at 30K (rank 1)

- QSA attention, 1.67 ms: a GQA-aware tiles redesign.
- Select pass 1, 0.49 ms: a single work-group per row, bound by latency.
