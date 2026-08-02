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

## Result: memory pass, decode loss

The screen completed cleanly at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-long-depth7-prefill4k-screen-gpu080-20260802T202340Z
```

All three rows passed intrinsic, retrieval, prompt-token, completion-length,
and cache-zero checks. The strengthened topology gate found exactly four q8
target captures and four replays at `146/145`, no drafter graph, and no other
Breakable topology line. Cleanup and all four post-run device diagnostics
passed.

The 4K prefill change solved the strict-memory question: minimum available RAM
was `13,466,776 KiB`, above the 12 GiB floor, with at least
`15,719,348 KiB` swap free. It did not solve performance:

| 32,640 middle row | q12 / 8K | q8 / 4K | q8 ratio |
| --- | ---: | ---: | ---: |
| prefill | 7,351.147 tok/s | 6,488.359 tok/s | 0.883x |
| client TTFT | 4.477 s | 5.069 s | 1.132x |
| conventional decode | 40.381 tok/s | 32.691 tok/s | 0.810x |
| draft acceptance | 0.644% | 0.994% | 1.544x |

Both candidates accepted eight tokens over the same 118 draft cycles. q8
proposed fewer total tokens, so its percentage acceptance was higher, but it
did not emit more tokens per cycle. Its smaller target verifier did not offset
the BF16 eager drafter and absence of q12's FP8 segmented-drafter stack.

The q8 output retrieved correctly but did not match either the q12 matching row
or q1 long teacher bitwise. The post-32K sentinel also retrieved correctly; it
is not a matched preprocessing comparison because this protected q8 source does
not contain the separate exact-prefill-chunk candidate.

The candidate misses the frozen 41.593 tok/s gate by a wide margin and is
rejected. No short oracle or full three-position 32K campaign is authorized,
the protected q12 record is unchanged, and there is no LocalMaxxing submission.
The durable structured result is
`data/laguna-s-2.1-xpu-b70/long-context-depth7-prefill4k-screen-20260802.json`.
