# Portable live-MTP replay: PASSED

All 32 output IDs match. Target state comparison against accepted live PP4:
True (2065 canonical buffers/layouts).
Full draft-state comparison: True.
All 117 true-pair hidden hashes and proposals match: True;
actual native provider rows agree with the controller: True.
Retained legacy head proposals match: True.

[Summary and distinct authority identities](summary.json),
[target comparison](accepted-live-target-comparison.json.gz),
[pair comparison](pair-comparison.json), [shared state proof](state-proof/summary.json).
Original portable plan/config/build/profile/binding and passive observations are
retained in `original/`. The derived input adds only the independently matched
tensor-manifest model identity needed by the common comparator.

This qualifies this generated portable live recipe against the accepted local
reference. It does not certify clean-host installation or performance. No model
payload was reread. Original raw states remain external and are durably archived.

Full controller/native logs and all six raw target/draft bundles are now retained
in the independently verified [durable archive](../../portable-live-durable-archive.json);
[raw-member verification](../../portable-live-archive-verification.json) checked each
archive payload against its original native seal. Original files remain untouched.
