# Pending-target provider rollback qualification

This separate diagnostic follows the accepted quiescent recursive-provider
proof. It is not rolling inference or a speed result. The provider uses the
existing MTP weights and actual canonical/recursive computation; tentative
target tokens are scripted only to force specific rollback coverage. No training
is involved. Existing quiescent controller and v4 evidence semantics remain
unchanged.

`tools/pending_ring_live_driver.py` uses the existing guarded lifecycle and
`pending_ring_live_wire.py`, preserving original ROW identity, ticket and
tentative flag even after local ACCEPT. Its plan binds the reference, native
receipt and controller sources. CPU planning never opens a GPU; execution still
requires the explicit run switch, admission and bounded unit identity.

Add these fields to the accepted quiescent configuration:

```json
{
  "pending_provider_gate": true,
  "pending_cases": [
    {"kind": "two-row-abort", "seed_position": 95},
    {"kind": "accept-then-one-row-abort", "seed_position": 96}
  ]
}
```

Retain `ring_live_draft: true`, `use_proposals: false`,
`verify_recursive_restore: true` and the same authenticated recursive reference.
The planner requires native `pending_survival.inc`, `survival_identity.hpp` and `survival_writer.inc`
capabilities. It adds `--pipeline-ring-pending-provider` and
`--pipeline-ring-verify-restore` to every owner, and
`--pipeline-ring-verify-provider-survival` only to stage 0.

For the 87-token/32-output cohort, seed 95 is accepted locally, then stage 0
executes a wrong tentative row 96 and its child 97. Provider 95 runs while both
are present. The owned seed-95 stream is then forwarded. Actual final-target
truth must reject row 96 before one ABORT discards both rows. Correct row 96
receives a fresh global ID. Its tentative row 97 is scripted correct and row 98
wrong; provider 96 runs with both pending. Actual final truth confirms row 97,
which is accepted without rewinding row 98. Provider 97 then runs with one row
pending, using the original tentative row-97 identity. Actual final truth must
reject row 98 before its suffix abort. Correct row 98 again gets a fresh ID.

Final-owner records remain unchanged until each provider reply. Seed streams
are owned byte copies before later target work overwrites the shared slot. Other
owners are drained at provider calls. This first gate deliberately does not
exercise asynchronous overlap. It expects pending-borrow depths 2, 2, 1 and
two aborts discarding 2 and 1 rows. Canonical provider calls remain 117.

The truthful result sidecar is `pending-ring-live-result.json`, schema
`ownrt.pending-ring-live-driver-result.v1`. It hashes the original lifecycle
result and plan; the inherited lifecycle mode is not the proof schema.
`provider-batches.jsonl`, `schedule.jsonl`, and
`pending-provider-coverage.json` retain actual proposals, target confirmation
and rejection, accepted original flags, cursors, wire sequences and discarded
IDs. Global IDs are deliberately noncontiguous after rollback.

Controller completion is insufficient for qualification. The independent v5
comparison must validate all 32 outputs, 2,065 target buffers, 73 canonical
draft buffers and the actual 117 pairs/32 recursive proposals. Native
`ring-provider-survival.jsonl` must additionally prove both target aborts
preserve the latest provider's canonical device/pinned bytes, private image,
host metadata, prepared bindings and sequence identity, before another provider
step can conceal a rewind. Target snapshots must be fully byte-verified. See
`../../../../notes/2026-10-25-ring-pending-provider-gate.md` for the native proof design.

CPU verification from `engine/tools`:

```sh
python3 -m unittest test_pending_ring_live_driver test_ring_live_driver test_ring_live_wire -q
```

Four pending-gate tests cover fragmented real sockets across 2/4/6 stages,
two-slot rollback, older tentative ACCEPT with one remaining slot, immutable
seed admission, native capability/flag checks, and refusal before ABORT when
actual target truth confirms the purported wrong token. Mock provider state
survival is only a controller sequencing check; it does not substitute for
native memory comparison or GPU evidence.
