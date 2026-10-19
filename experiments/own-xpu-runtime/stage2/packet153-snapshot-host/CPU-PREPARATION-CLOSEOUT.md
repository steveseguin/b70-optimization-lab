# Packet153 CPU preparation closeout
<!-- campaign-closeout -->

## Question and identity

Can packet136 banked bundle8 remove per-cycle rank-0 snapshot descriptor
construction and upload while retaining iq3-p49-split32-v1 state? October 19,
2026, CPU preparation on steve-b70s for the two-card lane-B smoke and one-load
production/static/production/static/production bracket. No device measurement.

## Outcome

The implementation and CPU gates qualify a static table shared by all six bank
roles. Captures and restores submit one copy instead of upload plus copy. The
984 descriptors occupy 47,232 bytes once at load; the 19,025,640 copied bytes
remain unchanged. Device output equality and speed are pending. The historical
58.798 tok/s record is unchanged. The final readiness marker controls admission.

## What worked

Eight fresh GNU/Intel production/static runs produced one canonical digest for
the 98-step mixed sequence and three corruption negatives, including forced
rollback, six bank roles and reset. Actual copy geometry passed separately at
nine positions through 4095 with synthetic bytes, redzones and older QSA rows.
Actual Engine switches and immutable-table reset protection passed both
compilers twice. Timing analysis rejects missing streams and scopes. The own
submission helper replayed copied packet136 evidence and rejected relabeling it.

## What failed or remains uncertain

Two coordinator freezes consumed much of the preparation window. The first
state attempt timed out after a freeze; another partial run was interrupted.
Their logs are retained and are not passing evidence. The final bounded state
run used the existing sequence-only mode, not the originally planned full
12-position state matrix. Its exact execution driver is retained. The regular
reproduction driver recompiles. A stale source seal correctly refused an entry
rehearsal and was regenerated before repeating it. No GPU output, event cost,
first-minute device proof or throughput improvement has yet been measured.

## Evidence and patches

- [CPU composition](v5/cpu-seal.json), [state](v5/evidence/state.json),
  [real geometry](v5/evidence/real-shape.json), [switch/reset](v5/evidence/switch.json).
- [Source delta](snapshot-static.patch), [retained evidence policy](RETENTION.md),
  [excluded work](DO-NOT-REPEAT.md), [preparation note](../../../../notes/2026-10-19-own-runtime-packet153.md).
- [Queue rehearsal](v5/evidence/queue-plan.json) and [pin admission](v5/evidence/pin-guard.json).

## When to revisit

The coordinator may use the final readiness marker to queue the lane-B smoke.
Only a successful smoke with its first-minute timing proof admits the bracket.
Inspect the unchanged target output before making any performance claim. The
static path can remove host table work and one upload submission, not all of
the measured 0.743 ms snapshot/accept/rollback scope.
