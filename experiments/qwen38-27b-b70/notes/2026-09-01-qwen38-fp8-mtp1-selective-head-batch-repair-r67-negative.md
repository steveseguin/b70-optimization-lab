# Qwen3.8 FP8 TP2 MTP1 selective head repair R67: cross-shard miss

R67 passed its small c1/c2 screen but failed the fresh 64-slot ladder. It
matched 1/2 outputs at c2 and 54/64 at c64; c64 measured 753.077 tok/s, below
the preregistered 875 tok/s floor. The fail-closed harness exited 4. No cache
tokens or new GPU/Xe faults were observed, and no public value changes.

The failure is now precisely localized. `cache-c000` repeatedly diverged at
token index 96. A post-run logprob probe showed the sequential global top two
were exactly tied (`-1.2340074778` each), while c2 separated them by only
0.015625. R67 nevertheless did not repair that row because its top-two margin
was calculated inside each TP rank's local vocabulary shard. The competing
tokens span the gathered vocabulary, so neither local shard saw the global
near tie.

The next implementation must detect the margin after TP all-gather. Only then
should both ranks recompute the globally flagged row at the M1 head shape and
gather its repaired local shards. That should remove the blind spot and avoid
the many irrelevant local-shard repairs that reduced aggregate throughput.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-full-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-full-result.json).
