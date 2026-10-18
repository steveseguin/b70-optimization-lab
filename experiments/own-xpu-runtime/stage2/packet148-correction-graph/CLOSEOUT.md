# Packet148 correction-graph study — closeout

<!-- campaign-closeout -->

## Question and identity

Can both ranks share a miss correction exactly and improve packet136 bundle8
by at least 2% within its memory plan? CPU-only study on October 18, 2026;
two-B70 quantized compressed UD-IQ3_XXS lane, `iq3-p49-split32-v1`, 24/24,
rank1 MTP, full BF16 state/KV, context4096. Anchor: 58.7981087592 tok/s.

## Outcome

Closed without a design brief. No graph has both a supported +2% projection
and a complete memory fit. Row-split sensitivities give +1.042/+1.323%; a
broader head-chain sensitivity with free state coherence gives at most
+1.914%. Whole boundary layers do not fit. Sharing the next causal row alone
does not advance the current emission with the target branch held fixed;
indirect suffix savings remain unmeasured. These are projections, not measurements.
The existing record and quality scope remain unchanged.

## What worked

Replayed all twelve saved requests and 1,188 intervals exactly. The +2% hurdle
is 1.573805 ms net per miss. Actual allocation calls identify the 786.27 MB
rank1 margin. Original transfer logs separate asynchronous dependency waits
from drained copy legs. Costing input/result messages at every dependent
island avoids treating a 24-layer correction as one cheap handoff.

## What failed or remains uncertain

Perfect row scaling, fractional placements, zero scratch and free state
coherence are favorable assumptions, not validated implementations. Current
correction per-layer timing, bulk peer transfers, physical residency and exact
cooperative-state behavior remain unmeasured. The diagnostic class profile
failed its overhead gate. No CPU or device candidate quality pass is claimed.
No fault, GPU work, model read, service or setting change occurred.

## Evidence and patches

[Analysis](ANALYSIS.md), [calculator](analyze.py), [computed values](analysis.json),
[captured inputs](inputs.json.gz), [negative index](DO-NOT-REPEAT.md) and
[work note](../../../../notes/2026-10-18-own-runtime-packet148.md).
The 1.73 MB input archive intentionally retains raw historical transfer logs
and summaries with their hashes; restoration is documented in the analysis.
The existing packet136 archive stays the record authority. No runtime patch
was made, no original evidence was removed, and every existing packet stayed
frozen.

## When to revisit

A specific exact graph must provide supported net C savings of at least
1.573805 ms per miss after all communication, state/draft interference and
assembly costs, with a complete allocation/lifetime plan inside the existing
limits. A different causal verifier must advance C or establish a new critical
suffix benefit, not merely compute future A earlier. See the separate per-graph reopen conditions in the negative
index; do not reopen packet144's small restore/preparation mechanisms.
