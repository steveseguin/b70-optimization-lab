# Packet 44 on cards 0+1, capacity 4,096 (2026-10-12 23:22 – 2026-10-13 00:57 UTC): twelve-prompt 128-token suite, decode median 37.59 tok/s, submission median 37.77 tok/s, every request exact

Packet 38's integrated runtime extended by packet 44 to real context capacities,
run here with `--context 4096` (the reference's context): two processes (one per
card), the official one-token draft head on the second card as the guess provider
(label: official draft head, draft-only 8-bit requantisation, output identical to
sequential decode), kernels selected on the card in this chain, native controller.
K0, K1a, K1b, K2, W0p, KD, W2m, WS128, WS64 and WSs128 passed through the packet's
wrapper; clean kernel log (no `xe` line). Decode windows ran pinned to the reserved
cores. Device binary SHA256 `e9ccb50aeb9ebea772eb4437bf38ade2b8356989fa120c1b29dc71a1f4991eb3`
(the sealed packet build; see ../../BINARY-HASHES.md).

## Suite window WS128 ([summary](WS128/summary.json), [window](WS128/window.json))

The reference's twelve prompts, one repeat, 128 generated tokens per request, in one
launch of the two rank processes (one warm-up request, not measured; complete state
reset before each request). Every request is checked against its own arithmetic-v2
128-token CPU oracle with no tolerance: **12 of 12 exact, 1,536 of 1,536 tokens,
4,608 of 4,608 retained layer fixtures** (first eight generated steps × 48 layers
per request).

**Median decode rate 37.59 tok/s** over the twelve prompt medians (range 34.45–40.71).
**Submission metric 37.77 tok/s**: the 99 intervals between the completion of
generated tokens 1 and 100 per prompt, the shape public submission requires (at
least 100 generated tokens). The reference median on the same twelve prompts at this
context capacity is **28.49 tok/s** (llama.cpp SYCL, two cards).

| Prompt | Decode tok/s | Submission tok/s | Guess acceptance |
| --- | ---: | ---: | ---: |
| incident-retrospective | 38.71 | 37.46 | 0.787 |
| code-review | 35.13 | 35.25 | 0.701 |
| customer-email | 37.76 | 36.54 | 0.772 |
| sql-debugging | 36.73 | 36.98 | 0.787 |
| release-plan | 36.50 | 37.75 | 0.764 |
| benchmark-analysis | 37.32 | 37.78 | 0.803 |
| architecture-tradeoff | 39.69 | 39.61 | 0.850 |
| bug-report-synthesis | 34.45 | 35.26 | 0.709 |
| technical-guide | 39.17 | 37.83 | 0.803 |
| risk-register | 38.70 | 38.70 | 0.866 |
| performance-hypotheses | 37.42 | 38.61 | 0.795 |
| decision-memo | 40.71 | 39.24 | 0.803 |

## The other windows

| Window | Result |
| --- | --- |
| [K2](K2/window.json) | measured selection on card 0 at capacity 4,096 ([selection](K2/dispatch-measured.json)); the frozen selection holds at every timed context length |
| [KD](KD/window.json) | draft head on the second card equals its host reference at capacity 4,096 |
| [W2m](W2m/window.json) | development prompt: 64/64 tokens, 384/384 layer fixtures, **38.33 tok/s**, 53 of 63 guesses right (39.05 tok/s at capacity 256) |
| [WS64](WS64/summary.json) | the 64-token suite, two repeats: **24 of 24 exact**, median **37.77 tok/s** (38.25 at capacity 256) |
| [WSs128](WSs128/summary.json) | sequential (no guesses) 128-token suite: **12 of 12 exact**, median **25.00 tok/s** (25.36 at capacity 256) |

## Reading against capacity 256

Same runtime, same oracles, only `--context` changed: 38.25 → 37.77 tok/s on the
64-token suite (about −1.3%), 39.05 → 38.33 on the development prompt, 25.36 →
25.00 sequential. Per-token cost follows the positions actually used, not the
capacity, as designed; the small difference is the larger index/mask traffic at
4,096 positions. The 4,096 figures are the ones comparable to the reference as a
product. The 32,768 chain is in [receipts-cards23-20261013-c32768](../receipts-cards23-20261013-c32768/README.md).

Queue ledger for the whole evening (both chains): [coordinator-queue.log](coordinator-queue.log).
