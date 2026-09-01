# D70 preregistration: strict TP2/MTP1 after dummy-repair bypass

Date: 2026-08-31

D69 passed startup with projection repair enabled and bypassed only for all
dummy forwards. D70 changes `STARTUP_ONLY` from 1 to 0 and adds the frozen D59r
TP2/MTP0 reference; the image, hook, model, TP2, MTP1, eager mode, 256-token
startup bound, device order, memory limits, profile-only decoder sync, M=512
real-request repair, and every startup receipt rule remain unchanged.

The full fixed 12-prompt realistic suite runs once per varied prompt with a
512-token cap, natural EOS, `cached_tokens=0`, no prefix cache, complete token
IDs, and objective canaries. All twelve complete greedy arrays must equal the
frozen D59r MTP0 target oracle. The primary rate is the median of prompt-class
medians over conventional token-1-to-100 intervals; no subset, fixture, warm
repeat, or best-prompt rate is admissible.

Startup and the complete post-request server log must each contain exactly
1,040 decoder begin/pass receipts; any increase proves a request paid for a
diagnostic barrier and fails. A pass also requires exactly four receipts per
sampler stage, both health checks, clean teardown, complete quality/cache gates,
and no GPU, OOM, filesystem, or I/O fault. Any failure rejects D70 without
retry or metric promotion.
