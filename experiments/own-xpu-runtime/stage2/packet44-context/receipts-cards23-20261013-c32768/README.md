# Packet 44 on cards 2+3, capacity 32,768 (2026-10-12 23:22 – 2026-10-13 01:08 UTC): twelve-prompt 128-token suite, decode median 37.71 tok/s, submission median 37.70 tok/s, every request exact

Packet 38's integrated runtime at `--context 32768`, the largest sealed capacity:
two processes (one per card), official draft head on the second card (same evidence
label as the 4,096 chain), kernels selected on card 2 in this chain, native
controller. K0, K1a and K1b ran as companions on the disjoint card pair during the
4,096 chain; K2, W0p, KD, W2m, WS128 and WS64 then ran on cards 2+3; all passed
through the packet's wrapper; clean kernel log. Same sealed device binary as the
4,096 chain (SHA256 `e9ccb50aeb9ebea772eb4437bf38ade2b8356989fa120c1b29dc71a1f4991eb3`).

## Suite window WS128 ([summary](WS128/summary.json), [window](WS128/window.json))

The reference's twelve prompts, one repeat, 128 generated tokens per request, same
oracles and checks as the 4,096 chain: **12 of 12 exact, 1,536 of 1,536 tokens,
4,608 of 4,608 retained layer fixtures**.

**Median decode rate 37.71 tok/s** (range 34.27–40.46). **Submission metric 37.70
tok/s** (99 intervals between generated tokens 1 and 100 per prompt).

| Prompt | Decode tok/s | Submission tok/s | Guess acceptance |
| --- | ---: | ---: | ---: |
| incident-retrospective | 38.72 | 37.43 | 0.787 |
| code-review | 35.06 | 35.24 | 0.701 |
| customer-email | 38.00 | 36.84 | 0.772 |
| sql-debugging | 36.84 | 37.03 | 0.787 |
| release-plan | 36.40 | 37.69 | 0.764 |
| benchmark-analysis | 37.26 | 37.71 | 0.803 |
| architecture-tradeoff | 39.57 | 39.43 | 0.850 |
| bug-report-synthesis | 34.27 | 35.06 | 0.709 |
| technical-guide | 39.13 | 37.79 | 0.803 |
| risk-register | 38.59 | 38.67 | 0.866 |
| performance-hypotheses | 37.43 | 38.58 | 0.795 |
| decision-memo | 40.46 | 39.09 | 0.803 |

## The other windows

| Window | Result |
| --- | --- |
| [K2](K2/window.json) | measured selection on card 2 at capacity 32,768, including context lengths 8,192 and 32,767 ([selection](K2/dispatch-measured.json)); the selection holds at every timed length |
| [KD](KD/window.json) | draft head on the second card equals its host reference at capacity 32,768 |
| [W2m](W2m/window.json) | development prompt: the same 64/64 tokens and 384/384 layer fixtures as at 256 and 4,096, **38.22 tok/s**, 53 of 63 guesses right |
| [WS64](WS64/summary.json) | the 64-token suite, two repeats: **24 of 24 exact**, median **37.57 tok/s** |

## Incidents on the way, neither a device or exactness problem

- First WS64 attempt (queue item 945, 00:43–00:48 UTC): the suite itself completed
  on the cards (23 of 24 rows written, all exact) but the wrapper's storage
  admission then refused the run: the packet's build tree (4.46 GB) plus this
  window's reserve write (1.55 GB) would have crossed its 6 GB cap. The coordinator
  deleted about 1 GB of unhashed, regenerable KV state dumps the 32,768 W2m run had
  written outside its receipts (the packet's disk rules already forbid keeping raw
  files of that size), removed the failed output, and reran the window as item 947:
  passed, 24 of 24 exact.
- The queue runner labelled the rerun FAIL: it derives an item's log path by
  stripping the numeric prefix, so it read the first attempt's old log. The window's
  own log and receipt show rc=0 and passed=true; the queue ledger carries a
  correction line ([coordinator-queue.log](coordinator-queue.log)).

At 32,768 positions the runtime keeps 37.6–37.7 tok/s on the suite against 37.8 at
4,096 and 38.25 at 256: per-token cost follows the positions used, not the capacity.
Queue ledger: [coordinator-queue.log](coordinator-queue.log).
