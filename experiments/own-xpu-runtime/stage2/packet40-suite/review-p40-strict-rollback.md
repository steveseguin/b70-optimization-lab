# Independent strict rollback review

Reviewed the proposed `strict-terminal-snapshot.patch` independently before application. Twelve ownership, write-set, ordering and proof-scope conditions are recorded in the JSON receipt. No unresolved source defect remains in this patch review; execution qualification is still required.

The snapshot preserves every declared speculative output plus token/position/history and mutable standalone storage before the speculative upload or preparation. It restores original allocation IDs after rollback selects the saved bank parity, then restores host lookup/cache/history metadata. Streaming weights must already be released at both boundaries; live FP32 source validation prevents reviving a freed source.

Committed active banks and valid QSA prefixes are excluded from restoration so an illegal write cannot be hidden. The CPU-only negative command deliberately corrupts those protected extents and must be detected by complete final-state comparison. Sticky errors cannot be restored away.

Only the private backup is canonicalized at a resolved dump/reset/finish boundary. It remains in the mutable allocation inventory. No model allocation is cleared to obtain equal hashes. The new storage belongs to the existing owner and its admission, reset, drain and teardown path.

One finding was resolved: the initial patch constructed the image after the memory census and READY reply. The reviewed revision constructs it before after-load accounting, census and READY. The patch has not yet been applied or executed by this review; final source hashes and all affected CPU qualification must be refreshed afterward. Device timing, copy overhead and overlap remain unmeasured.
