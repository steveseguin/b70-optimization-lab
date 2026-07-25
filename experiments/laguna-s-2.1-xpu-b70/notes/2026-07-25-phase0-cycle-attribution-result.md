# Laguna Phase 0 — cycle attribution result

Date: 2026-07-25 America/Toronto

Status: **completed diagnostic stop.** Attribution only. No throughput claim, no
record, no payload, no submission. Timing recorded here must never be cited as a
throughput result.

Run root:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-phase0-cycle-attribution-ee2f07da4-20260725T185645Z`
Instrumentation: vLLM `ee2f07da4`, XPU kernels `4772f7275`, record selector set.

## Contract

13 unique real cold prompts from `realistic-suite-v1.json`, 512 tokens each,
one active generation, prefix caching disabled, `cached_tokens=0` asserted on
every prompt, fresh process. 6,656 generated tokens in 145.4 s wall including
per-prompt prefill. No synthetic prompts.

## Headline: the premise was wrong

**DFlash is a parallel drafter.** All seven speculative tokens come from a
single masked forward — `parallel_drafting_token_id` is the config
`mask_token_id` — so `propose()` exits at the `parallel_drafting` early return
and never runs a sequential loop. The Phase 0 preregistration, and the plan that
motivated it, assumed "seven sequential proposal forwards" and sized the
draft-side graph-capture opportunity accordingly. That sizing was wrong, and it
was wrong in the conservative direction: there is one draft forward per cycle,
not seven.

Two full 13-prompt runs produced an empty attribution directory before this was
understood, because every cycle was being abandoned against an eleven-mark
schema that reality never satisfied.

## Measured attribution

All four ranks, medians. Cross-rank spread is under 0.2%, so this is not a
single-rank artifact.

| rank | cycles | abandoned | draft host ms | ctxkv | draft_forward | pre_ctxkv | post_draft |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2132 | 0 | 8.694 | 0.480 | 9.004 | 0.825 | 0.636 |
| 1 | 2132 | 0 | 8.613 | 0.481 | 8.986 | 0.825 | 0.632 |
| 2 | 2132 | 0 | 8.547 | 0.481 | 9.010 | 0.825 | 0.632 |
| 3 | 2132 | 0 | 8.581 | 0.482 | 8.974 | 0.832 | 0.637 |

2,132 draft cycles for 6,656 tokens is **3.122 emitted tokens per cycle**.

Deriving the full cycle: 6,656 tokens at roughly the record's decode rate is
about 70 s of the 145.4 s wall, the remainder being 13 prefills — consistent
with the record's `ttft_ms_median` of 5,960 ms. That puts the **full decode
cycle near 32.8 ms**, of which the draft is **8.694 ms, about 26%**. The full
cycle figure is derived rather than measured and should be treated as
approximate; the draft figure is measured directly.

## What this kills

**The context-KV workspace lever cannot reach 100 tok/s.** `ctxkv` is
**0.480 ms** per cycle — roughly **1.5% of the full cycle**. Eliminating the
projection entirely would not clear the 5.08% needed, and the workspace does
not eliminate it: it removes per-cycle allocation inside that 0.480 ms. The
lever is real and its exactness gate passed, but its ceiling is far below the
objective.

This is worth stating plainly because the campaign was positioned to spend a
full preregistered graph-vs-graph crossover campaign on it. That campaign would
have measured a fraction of a percent.

## What survives

**`draft_forward` at ~9.0 ms is the dominant interval inside the draft**, about
82% of device time in the draft window, and it is not graph-captured — the
Breakable graph covers the M=8 target replay, not the draft. Capturing it is
one forward rather than seven, so the opportunity is smaller than the plan
assumed, but it is the largest single item measured on the draft side.

Caveat on the device numbers: events are stream-ordered and rank-local, so an
interval absorbs work queued ahead of it. `pre_ctxkv` shows median 0.825 ms
against a mean of 10.705 ms, which is exactly that effect — it absorbs target
work still retiring. Device intervals sum to 10.945 ms against a host cycle of
9.345 ms (117%), confirming the stream lags the host. Treat the device split as
ordering evidence within the draft window, not as an additive budget.

## What is still unanswered

The scored-window penalty is **not** explained by draft cycle time. First 100
cycles measure 9.438 ms against 8.643 ms for the last 100 — a 9% difference,
nowhere near the 29.3% gap between `tok_s_out` 94.920 and
`tok_s_full_after_ttft_median` 122.735. The penalty therefore lives in the
target side or in acceptance, not in the draft.

Resolving it requires accepted-tokens-per-cycle, which this instrumentation does
not record: it captures `num_proposals`, always 7, because acceptance is decided
downstream of the proposer. That is the gap to close next.

One prompt is a strong hint. Per-prompt wall times, 512 tokens each:

| prompt | prompt tokens | wall s |
| ---: | ---: | ---: |
| 0 | 49 | 27.07 |
| 12 | 823 | **6.70** |
| others | 48-188 | 7.52-15.54, median 9.73 |

Prompt 0 carries first-request graph capture and warmup. Prompt 12 has by far
the **longest** prompt and by far the **fastest** generation. If longer context
conditions the draft better and raises acceptance, that is a direct argument
that acceptance — not kernel time — governs the scored window, and it points at
the acceptance axis the campaign has never worked. This is one observation and
is not sufficient on its own.

## Next

1. Record accepted-tokens-per-cycle alongside cycle time, then re-run. Without
   it the early-window question cannot be settled.
2. Do not open the context-KV crossover campaign against the 100 tok/s
   objective. Its ceiling is measured at roughly 1.5%.
3. Size draft-forward graph capture against the ~9.0 ms interval before
   committing to it.
