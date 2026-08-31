# D61 preregistration: repaired TP2/MTP1 strict qualification

Date: 2026-08-31

D60 reproduced every D59r TP2/MTP0 token stream in a second fresh process and
passed all strict gates. D61 adds exactly one Qwen3-Next MTP speculative token
using the checkpoint's own MTP weights. TP2, eager mode, the M=512/no-barrier
projection repair, bounded 256-token profile, local weights, and all cache and
quality rules remain unchanged.

Speculative verification must preserve the target model's greedy output, so all
twelve complete token-ID streams must equal D59r. The complete workload and
objective canaries must pass, cached tokens must remain zero, and startup logs
must prove MTP depth 1 was bound. Compare the median of prompt-class medians to
the D59r/D60 MTP0 range (17.896698–18.067737 tok/s); no best-prompt or fixture
speed is admissible.

A pass authorizes a fresh MTP1 replay or cautious depth expansion. A startup,
quality, determinism, or target-token mismatch rejects the lane without
silently relaxing the comparator.
