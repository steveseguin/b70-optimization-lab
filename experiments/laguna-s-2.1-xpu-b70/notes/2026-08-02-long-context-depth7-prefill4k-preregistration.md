# Laguna 32K q8/depth-7 plus 4K prefill screening preregistration

Date registered: 2026-08-02 America/Toronto

Status at registration: no service for this combined identity has started.
The prior q8 plus 8K-prefill identity is terminal and preserved; this is a new
memory/preprocessing candidate, not a replacement run.

## Candidate and rationale

The first q8 screen stopped `78,040 KiB` below its frozen 12 GiB available-RAM
floor before any completed row. It had 24.94 GiB swap free and cleanly shut
down, but its no-retry policy closes that exact identity. The successful q12
32K comparison used an 8 GiB floor, which exposed the launch-identity mistake
but does not authorize relaxing the failed q8 campaign after the fact.

This new candidate retains the exact q8/depth-7 decode stack but reduces
`max_num_batched_tokens` from 8,192 to 4,096. The purpose is to reduce peak
prompt-processing working state enough to satisfy the original 12 GiB RAM
guard. It is also a direct measurement of the prefill/TTFT cost of smaller
chunks. All q8 selectors, source commits, model revisions, hardware topology,
case order, request policy, and 0.80 GPU utilization remain unchanged.

The tooling must add 4,096 as an explicit accepted long-context prefill chunk
size and must strengthen topology validation before launch. Default q12/8K
behavior must remain unchanged.

## Frozen screen and gates

Run one fresh service with:

1. `laguna-lc-01024-early` as the unscored warm-up; and
2. `laguna-lc-32640-middle` plus its automatic sentinel.

The candidate passes only if:

- the memory guard never fires with `MemAvailable >= 12,582,912 KiB`, or with
  the existing low-swap combined rule;
- the long row and sentinel pass every intrinsic and retrieval check;
- conventional first-100 long decode is at least
  `41.59251233685705 tok/s`, 3% above the matching q12/8K row;
- four exact q8 target captures and four exact q8 target replays are present,
  all `146/145`, with no other Breakable topology line;
- there is no drafter graph, retry, runtime/device error, or surviving worker;
  and
- prefill throughput and TTFT are reported as a tradeoff against the q12/8K
  evidence, not presented as a matched prefill comparison.

Any post-start failure closes this combined q8/4K identity. A pass authorizes
short canonical exactness and a complete early/middle/late 32K campaign under
the same 4K prefill identity. It does not change the protected q12 record and
cannot itself support a LocalMaxxing submission.
