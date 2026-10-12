# Independent strict rollback review

Reviewed `strict-terminal-snapshot.patch` independently before application, then checked the applied source bindings. Fifteen ownership, write-set, ordering and proof-scope conditions are recorded in the JSON receipt. No unresolved source defect remains in this patch review; execution qualification is still required.

The snapshot preserves every declared speculative output plus token/position/history and mutable standalone storage before the speculative upload or preparation. It restores original allocation IDs after rollback selects the saved bank parity, then restores host lookup/cache/history metadata. Streaming weights must already be released at both boundaries; live FP32 source validation prevents reviving a freed source.

Committed active banks and valid QSA prefixes are excluded from restoration so an illegal write cannot be hidden. The CPU-only negative command deliberately corrupts those protected extents and must be detected by complete final-state comparison. Sticky errors cannot be restored away.

Only the private backup is canonicalized at a resolved dump/reset/finish boundary. It remains in the mutable allocation inventory. No model allocation is cleared to obtain equal hashes. The new storage belongs to the existing owner and its admission, reset, drain and teardown path.

One finding was resolved: the initial patch constructed the image after the memory census and READY reply. The reviewed revision constructs it before after-load accounting, census and READY. The applied GNU binary passed the 20-case diagnostic screen: both controllers, retention on/off, four cancellation boundaries and actual active-bank/QSA corruption controls. This screen does not establish exhaustive coverage; the full mini and sampled real gates and affected qualification remain in progress. Device timing, copy overhead and overlap remain unmeasured.

The follow-up boundary delta also clears the private saved host vectors, histories and parity after resolution. Live Engine metadata is untouched. Snapshot validity is false; capture, restore and copied-byte counts remain explicitly labeled telemetry. This short delta was independently reread and its patch hash refreshed.

The second follow-up saves/restores exactly the 65,536-byte rank0 producer slot, whose reader copies only into the separate rank1 slot. It never restores rank1 input, draft/verification publication or the native mailbox. The shared mapping outlives restoration. The implementer also corrected the backup category to its required process lifetime; this now matches the owner allocation contract. Both changes were independently checked and the patch hash refreshed.
