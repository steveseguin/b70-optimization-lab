# Packet61x: HC fusion with packet56x pure-spin waits

Separate CPU-prepared candidate from packet61. The packet61 hook is a source
substitution point, not a selectable binary policy, so a minimal host rebuild
is required. Packet56x variant (a) is linked with `P56X_SLEEP20=0`: PAUSE spin
with yield every 256 iterations, until completion or the existing deadline.
There is no environment override.

All covered waits use this policy: native controller mailbox request/reply and
draft publication, device completion including copies/drains and corrected
misses, and the engine's pending-draft progress callback. Existing acquire /
release, cancellation, peer-abort, async-error and callback checks remain.
See [wait audit](WAIT-AUDIT.md) and [source identity](evidence/source-identity.json).

All kernel source bytes and inherited linked kernel objects are packet61's.
Only host entry/wait plumbing and the fixed wait-policy object are rebuilt.
The packet60 HC fusion on both target sides and both serial M=2 rows, rank-0
queue profiling, 91,392-row draft prefix, full target head, BF16 arithmetic/KV,
and packet49 oracle remain unchanged. The target verifies every draft token.

This packet has no device measurement. The supplied v1 screens motivate
combining HC fusion with pure-spin waits; gains are not assumed additive.
Only the coordinator may run the device screens and full chain.

- [Exact v3 lane A, lane B and full-chain commands](WINDOW.md).
- [Submission tooling](SUBMISSION.md), preserving the current record floor.
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
- [Retention and rebuild](RETENTION.md).
- [Task note](../../../../notes/2026-10-17-own-runtime-packet61.md).

Only the lean build/gate and documented coordinator entry points apply.
Inherited historical helper/CMake files are dependencies, not rebuild recipes.
This is a lab candidate with retained local build inputs, not a public package.

**October 17 input repair:** K1/K2 fixture paths are explicit and pinned; all
eleven windows have CPU-only input preflight. See the [repair closeout](INPUT-REPAIR-CLOSEOUT.md).

October 17 KD chain repair: the stopped `device-cards01-a` stays untouched.
`device-cards01-b` imports only its five hash-pinned passed early windows; KD
and all later model windows remain fresh coordinator work. See the
[repair, checks and exact resume command](KD-RESUME-CLOSEOUT.md).
