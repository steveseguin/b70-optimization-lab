# Packet121: smoke, then a conditional one-load bracket

Candidate: reverse the admitted capture table at restore. Control: packet118's
unchanged production restore. Only `restore_table` differs. The head, prefix,
draft, all target arithmetic, split, target weights, context and BF16 KV match.
Runtime switching must preserve both loaded arena descriptor hashes and weight
hashes, with zero weight uploads after initial load.

1. `ops/lane-queue/proposed-p121-smoke-B.txt`: B lane, one target/draft load,
   control / candidate / control. Each view uses the twelve fixed cold prompts
   for exactly 64 output tokens plus a separately reset 64-token incident.
   Every token must match the unchanged `iq3-p49-split32-v1` oracle, including
   architecture-tradeoff token31 = 215495. Misses and the candidate reverse
   restore counter must both be nonzero. All view/reset receipts, zero cached
   tokens, exact registered selections, unchanged allocations, isolation,
   successful drain and released lease are required. No speed verdict.
2. `ops/lane-queue/proposed-p121-v5-B.txt`: blocked until that exact sealed
   smoke passes. One target/draft load, control / candidate / control /
   candidate / control; twelve 128-token requests plus a separate incident64
   per view. Require every target token, per-prompt acceptance counts and arena
   identity to match. All three control rates must stay within 3%. Compare
   each candidate against the fastest control; report the slower candidate
   divided by the fastest control. This deliberately rejects a lucky view.

Both jobs estimate **900 seconds** including loading, resets and graceful
drain; watchdog **3,600 seconds (4×)**. These are conservative planning budgets,
not measured durations. The full bracket has 8,000 generated tokens across
65 requests; smoke has 2,496 across 39 requests. A dynamic device failure ends
that job without retry or server cycling. The established coordinator owns
fault handling and any later work. These files are proposals, not live jobs.

The primary screen rate is the median across input-class medians, using the
99 timestamp intervals between generated tokens1 and100. Keep all individual
rates, TTFT, acceptance and output receipts. This is a one-load diagnostic,
not independent fresh servers or a 512-token realistic final gate. Neither
the 0.10 ms/miss screening scenario nor any device speedup is assumed true.

The table reuse removes a small part of the 0.55 ms restore envelope. A loss,
drift or indistinguishable result closes this lever without a broad parameter
sweep. A win warrants the existing matched fresh-server final chain; it does
not change the lab frontier or authorize a submission.
