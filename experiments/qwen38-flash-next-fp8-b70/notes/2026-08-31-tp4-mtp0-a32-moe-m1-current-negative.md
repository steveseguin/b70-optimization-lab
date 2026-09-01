# Qwen3.8 Flash-Next TP4 MTP0 A32 M1-only negative

Date: 2026-08-31
Status: lossless short-decode performance negative and exact-4K reliability negative

A32 corrected A31's client binding and completed the frozen battery on the same
boot as A2, affinity A1, and A31. The corrected inner-to-outer supervisor proof
passed, proving that the A31 interruption was orchestration-only.

The inherited quality boundary was unchanged: recovery passed, six of seven
exact semantic cases passed with only the known code-execution miss, all 16
repeat outputs shared one hash, the long-context needle passed, and cached
tokens were zero.

The three short rows preserved the protected output hash but measured:

- `5.421586 tok/s`;
- `5.416722 tok/s`;
- `5.441849 tok/s`.

Their median is `5.421586 tok/s`, `1.70777%` below the protected
`5.515783 tok/s` MTP0 result. M1 warps 8 is therefore not a speed win.

Both exact-4K rows passed transport/cache-zero at `5.252151` and
`5.189331 tok/s`, but produced different hashes from each other and from the
retained authority. M1 warps 8 also does not repair the known long-prefill
reliability issue.

The client failed closed at the final authority assertion. Owned teardown,
four-card compute/free-memory, host recovery, the bounded journal gate, and the
lifecycle evidence manifest all passed. No reboot is required. The M1
treatment remains unpromoted and the protected MTP0/MTP4 results are unchanged.

Structured result:
[`20260831-tp4-mtp0-a32-moe-m1-current-negative.json`](../data/20260831-tp4-mtp0-a32-moe-m1-current-negative.json).
