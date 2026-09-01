# D72 preregistration: strict TP2/MTP1 serving control without repair

Date: 2026-08-31

D71 localized the real-request device loss to rank 1's M=512 padded dense
`down_proj`. D72 changes only projection repair from enabled to disabled. It
retains the immutable dummy-marker/profile-only-sync image, TP2, MTP1, eager
mode, 256-token startup bound, device order, memory limits, exact startup
receipt rules, complete varied 12-prompt/512-cap suite, cache-zero policy,
objective canaries, complete token IDs, and frozen D59r TP2/MTP0 oracle.

D72 may run only after another full reboot and independent compute passes on
both local B70s. Its purpose is twofold: prove whether the serving path is
stable without the M=512 repair, and test whether the current deterministic
kernel image nevertheless preserves the frozen target outputs. All twelve
complete arrays must match D59r. Stability without exact output is a negative
quality result, not a candidate.

A pass requires exact 12/12 token identity, all cache/canary/fresh-response
gates, exactly 1,040 decoder begin/pass receipts both before and after serving,
four receipts per sampler stage, both health checks, clean teardown, and no
GPU, OOM, filesystem, or I/O fault. The primary metric remains the median of
class medians over conventional token-1-to-100 intervals. Any failure rejects
D72 without retry or promotion.
