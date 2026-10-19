# Packet58ap release conditions

The [packet58ai coordinator decision](../../../../notes/2026-10-19-own-runtime-packet58ai.md#coordinator-decision-0440-utc-census-superseded-by-the-direct-p58am-screen)
superseded the census release bound with packet58am's direct smoke and v5.
The exact original note and amendment are vendored in
`lineage/packet58ai-note.md` and `lineage/packet58am/RELEASE-AMENDMENT.md`.
The census is parked, not reclassified as a pass. No census number is used
as a measured speedup.

The owner's packet58ap brief preregisters the record-chain release rule:
candidate gain >=0.5% over EVERY warm control, all views exact, drift <=3%,
and A0 as warm-up. This supersedes packet58aj's non-inferiority readiness
wording for this new packet and is distinct from packet58am's original 2%
study threshold. The raw v5 summary is never rewritten. Packet58am's own
smoke admission remains its coordinator's responsibility.

This chain cannot release until its vendored candidate matches that v5's
binary and the checks pass. Future parent builds require a new reviewed
snapshot; neither a mutable pointer nor a saved `passed` flag admits them.
Submission also requires exact chain output and a final WS128 record gain.
It discloses the actual bracket numbers and this supersession, with a
128-token scope and strict512 false.
