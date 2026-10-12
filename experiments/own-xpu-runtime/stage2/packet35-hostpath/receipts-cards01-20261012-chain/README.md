# Packet 35 on cards 0+1 (2026-10-12 03:15–03:48 UTC): exact, 23.28 tok/s natively; wrapper rejected the receipt format

K0, K1a, K1b, K2 and W0 passed through the wrapper. The W2m decode ran to completion on
the cards and is exact; the wrapper then marked the window failed because its summary
step requires a per-family issue-timing table in every token row and the native program
writes that table only in class-timing mode (`enqueue_family_ms: null` otherwise). No
fault, no retained process, clean kernel log. The window is therefore **not sealed**;
the native receipt and the wrapper's own token and layer comparison are kept as evidence.

| | Packet 29 (pinned repeat) | Packet 35 W2m (pinned) |
| --- | ---: | ---: |
| Tokens / layers equal to the v2 oracle | 64/64, 384/384 | 64/64, 384/384 (compared by the wrapper before it stopped) |
| Decode rate | 22.49 tok/s | **23.28 tok/s** (native receipt: 63 tokens in 2,706 ms) |
| ms per token (mean of token rows) | 44.3 | 42.5 |
| Launches per token | 2,307 | 1,935 |
| Host enqueue loop | 12.4 ms (5.4 µs per launch) | 9.1 ms (4.7 µs per launch) |
| Token preparation | 0.59 ms | 0.11 ms, 0.05 major faults per token |
| Waiting on the cards | 30.7 ms | 32.7 ms |

Readings:

1. **The fixed selection rule works**: K2 kept the three small merged-GEMV fusions
   ([selection](k2-r35/dispatch-measured.json); fusion against the sum of its selected
   members: 21.0 against 32.5 µs, 4.6 against 7.3, 15.6 against 20.1), which removes 372
   launches per token.
2. **Prepared launches are exact on the cards** and cut the host's own per-launch work,
   but the token is GPU-bound, so the gain is the launches removed, not the host time:
   about 1.8 ms per token (4%).
3. **The residency pass over the lookup tables** keeps token preparation at 0.1 ms.

Nothing here is rerun: the host path and the rule fix are carried into the pipeline
runtime by packet 37, whose wrapper does not have this check.
