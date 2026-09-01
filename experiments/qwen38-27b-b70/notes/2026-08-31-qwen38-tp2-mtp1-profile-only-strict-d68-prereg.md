# D68 preregistration: profile-only startup fix, strict TP2/MTP1

Date: 2026-08-31

D67 confirmed that 1,040 decoder barriers confined to the first profile forward
stabilize TP2/MTP1 startup while the later warmup forward runs without them.
D68 is the first inference qualification of that fix. It restores the proven
M=512 projection repair with its runtime barrier disabled and keeps the exact
profile-only image, TP2, MTP depth 1, eager execution, 256-token startup profile
bound, local direct-verified model, device order, and memory limits.

The full fixed 12-prompt realistic suite runs once per varied prompt at a
512-token cap with natural EOS required, `cached_tokens=0`, no prefix cache,
complete token IDs, and objective canaries. All twelve complete greedy token
arrays must equal the frozen D59r TP2/MTP0 oracle. The primary rate is the
median of prompt-class medians over conventional token-1-to-100 intervals; no
fixture, subset, warm-repeat, or best-prompt number is admissible.

Startup must produce exactly 1,040 decoder begin/pass receipts and exactly four
receipts for each sampler stage. The complete post-request server log must
still contain exactly 1,040 decoder receipts, proving no inference request
executed a diagnostic barrier. A pass also requires both health checks, clean
teardown, and a timestamp-bounded kernel delta without GPU, OOM, filesystem, or
I/O faults. A single startup, output, cache, canary, determinism-oracle, receipt,
or kernel failure rejects D68 without retry or metric promotion.
