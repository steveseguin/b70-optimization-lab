# Packet 38 on cards 0+1 (2026-10-12 16:04 – 16:41 UTC): twelve-prompt suite, median 38.25 tok/s, every request exact

The integrated runtime: two processes (one per card), the official one-token draft head
on the second card as the guess provider (label: official draft head, draft-only 8-bit
requantisation of its experts, output identical to sequential decode), the kernels
selected on the card in this chain, the native controller. K0, K1a, K1b, K2, W0p, KD,
W2m and the suite window WS passed through the packet's wrapper under the suffix `c`;
clean kernel log (no `xe` line). Decode windows ran pinned to the reserved cores.

## Suite window WS ([summary](WS/summary.json), [window](WS/window.json))

The reference's twelve prompts, each run twice, in one launch of the two rank
processes: one warm-up request that is not measured, then 24 requests with a complete
state reset before each. Every request is checked against its own arithmetic-v2 CPU
oracle with no tolerance: **24 of 24 exact, 1,536 of 1,536 tokens, 9,216 of 9,216
retained layer fixtures**.

**Median decode rate 38.25 tok/s** over the 24 requests (repeat medians 38.27 and 38.25;
range 35.05–41.43; mean 38.30). Rate per request: 63 intervals between the completion
of generated token 1 and token 64, the definition of the reference table, whose median
on the same prompts is **28.49 tok/s** (llama.cpp SYCL, two cards, 22 rows).

| Prompt | Prompt tokens | Prompt tokens/s | Guesses right | Repeat 1 tok/s | Repeat 2 tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| incident-retrospective | 87 | 48.5 | 53 of 63 | 39.26 | 39.05 |
| code-review | 90 | 48.9 | 43 of 63 | 35.54 | 35.41 |
| customer-email | 77 | 48.5 | 51 of 63 | 38.40 | 38.36 |
| sql-debugging | 83 | 48.7 | 48 of 63 | 37.16 | 37.25 |
| release-plan | 68 | 48.9 | 46 of 63 | 37.00 | 36.99 |
| benchmark-analysis | 65 | 48.6 | 49 of 63 | 37.98 | 38.14 |
| architecture-tradeoff | 67 | 48.5 | 55 of 63 | 40.36 | 40.40 |
| bug-report-synthesis | 71 | 48.5 | 40 of 63 | 35.07 | 35.05 |
| technical-guide | 69 | 48.6 | 54 of 63 | 39.88 | 39.98 |
| risk-register | 61 | 48.3 | 52 of 63 | 39.44 | 39.37 |
| performance-hypotheses | 64 | 48.5 | 49 of 63 | 38.14 | 38.08 |
| decision-memo | 60 | 48.4 | 57 of 63 | 41.41 | 41.43 |

Guesses right over the suite: 597 of 756 (79.0%), from 40 of 63 to 57 of 63 by prompt;
the decode rate follows it. On the development prompt a right guess costs 23.0 ms and a
wrong one 38.7 ms on average. Prompt reading runs at about 48 tokens/s (both cards
overlapped; the reference reads at about 55).

What is still inside these numbers: the first eight generated tokens of every request
also copy 48 layer snapshots each to the host for the fixture check, which slows those
tokens; the measured rate includes them. A run without that instrumentation, and a
128-token run for the public submission metric (which needs at least 100 generated
tokens per prompt), are prepared in packet 40.

## The other windows

| Window | Result |
| --- | --- |
| [K2](K2c/window.json) | measured selection on card 0 ([selection](K2c/dispatch-measured.json)): `p30.attention.sg32` for QSA attention (fastest at all six timed context lengths), `p33.down.select`, `p33.dense.segment` for the large dense classes, `p30.small.rows4` for the router/shared-expert group |
| [KD](KD/window.json) | draft head on the second card equals the host implementation byte for byte, two fresh owners |
| [W2m, native controller](W2m-native/window.json) | development prompt: 64/64 tokens, 384/384 layers, **39.05 tok/s**, 53 of 63 guesses right |
| [W2m, Python controller](W2m-python/window.json) | the same run with the Python controller: 64/64, 384/384, 36.26 tok/s: the native controller is worth 7.7% |
| [W2s](W2s-native/window.json) | development prompt without guesses (sequential generation): 64/64, 384/384, **24.93 tok/s** |
| [WSs](WSs/summary.json) | the twelve-prompt suite without guesses, two repeats: 24 of 24 requests exact, **median 25.36 tok/s** (25.16–25.48) |

Stops on the way, none a device problem, each with an evidence folder:
[K2's 66-length grid](../evidence/20261012-k2-grid-exceeds-watchdog/README.md),
[K2's compression step against the packet's own storage cap](../evidence/20261012-k2-retention-storage-cap/README.md).

Progression of the exact two-card decode on the development prompt: 3.15 → 12.08 →
17.85 → 19.63 → 22.49 (sequential) → 30.37 (draft head) → 39.05 tok/s.
