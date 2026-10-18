# CPU harness corrections during preparation

Two preparation-only failures occurred before the final gate receipts:

- The byte runner used `cases` for both the numeric native case count and its
  retained case-log path. Python refused the duplicate keyword after the first
  successful GNU production comparison. The path key is now `cases_path`.
- The native-plan comparison included rank1's separate draft weight labels.
  The target plan intentionally excludes those. The comparison now selects the
  exact `card0:weight:` namespace; real draft allocations still remain in the
  full census and unchanged memory admission. Rank0's first check had passed.

Both gates were rerun after correction. No candidate arithmetic was relaxed,
no device ran, and no failed candidate was accepted. Compile turns waited for
packet58g's complete build processes, not just gaps between compiler children.

The full startup fixture also corrected an assumed 48 IQ2 cached tensors on both ranks: the actual dispatch specializes 46 on rank 0 and 48 on rank 1. Memory plans now use the actual per-rank increments (301,465,600 / 314,572,800 bytes). Native-plan and real-allocation comparisons remain mandatory.
