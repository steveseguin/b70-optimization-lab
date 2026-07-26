# Laguna — RETRACTED: the 3.703 baseline was correct

Date: 2026-07-26 America/Toronto

Status: **this note is retracted.** It claimed the record's emitted-per-cycle
baseline of 3.703 was an unmeasured assumption and should be 3.122. That was
wrong, and the notes it banner-marked have been restored.

## What settles it

The approved record run's own Prometheus counters, captured in
`metrics-after-suite.prom` alongside the 94.920039 tok/s result:

| counter | value |
| --- | ---: |
| `spec_decode_num_drafts_total` | 1718 |
| `spec_decode_num_draft_tokens_total` | 12026 |
| `spec_decode_num_accepted_tokens_total` | 4644 |

`12026 / 1718 = 7.000` draft tokens per draft, confirming depth 7.
`4644 / 1718 = 2.7031` accepted per cycle, so **3.7031 emitted per cycle**, and
`3.7031 / 94.920039 = 39.01 ms` per cycle. All measured, all from the record run.

## Where the error came from

Phase 0 reported a ~32.8 ms cycle, and I used that to argue 3.703 was
inconsistent. But Phase 0 derived that figure by *assuming the record's decode
rate* to split its 145.4 s wall into prefill and decode, and the note says so
explicitly: "the full cycle figure is derived rather than measured and should be
treated as approximate." Using a derived number to overturn a directly measured
one was the mistake.

The other leg of the argument was Phase 0's `6656 / 2132 = 3.122`. That divides
*all* suite output tokens by *speculative* cycles. The record run shows
speculation emitting 6,362 tokens, not the full 6,656, so the two quantities do
not divide cleanly.

## What remains genuinely unresolved

Phase 0 counted **2,132** draft cycles against the record run's **1,718** for the
same 13-prompt, 512-token suite — 24% more cycles, implying materially lower
acceptance under instrumentation, on a different commit (`ee2f07da4`). That gap
is real and unexplained, and it is worth resolving, but it does not bear on what
the record run itself measured.

## Standing baseline

**3.7031 emitted per cycle, 39.01 ms per cycle, 94.920039 tok/s.** Fitted
conditional acceptance p is approximately 0.756.
