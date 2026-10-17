# Packet 63: packet61x with selectable draft HC

The draft HC candidate and its control are built and sealed. Both use one
host build and one device build. The coordinator owns every device window.

Rank balance is **skipped**: packet61x's current screens have rank 1 finishing
last in all 4,536 complete suite cycles. Rank 0's speculative half takes
13.57–13.64 ms; rank 1's target half alone takes 15.20–15.45 ms, before the
separately reported 1.87–1.92 ms draft. Moving another layer to rank 1 fails
the brief's timing condition. No 22/26 arm or memory admission is claimed.
The existing 23/25 split stays in both selections.

| Sealed selection | Difference from packet61x |
| --- | --- |
| `control` | All draft switches use production paths |
| `draft-hc` | Exactly packet59c `screen2-hc`: eight HC schedules and six HC fusions |

The target HC fusion, target arithmetic, full target head, 91,392-row draft
head, BF16 KV/state, pure-spin waits, controller, packet49 oracle and placement
are unchanged. Attention, experts/route and norm/merge draft groups stay off.
Only draft proposals may change; the unchanged target still verifies them.
The strict selection parser binds the exact JSON bytes at startup. Selections
are resolved during command preparation, with the original capture slots kept.

Each selection passes two fresh CPU rank-pair runs: 96 target layer fixtures
and 24 tokens equal packet56, with all 27 draft proposals and five final draft
state files agreeing across repeats. Control also equals packet61x. Synthetic
production-width draft output bytes agree across two fresh processes. Eleven
native selection checks pass, and v3 `--plan` passes on both lanes for both
selections. These are CPU gates, not device exactness or speed qualification.

The retained build and selection views use 167.38 MB logically and 127.00 MB
across unique inodes. Unchanged compiler objects and both selected executables
are hardlinked. No GPU, service, model load or host-setting change ran.
Packet61x's running full chain was neither read nor changed.

- [Task note, measured halves and decision](../../../../notes/2026-10-17-own-runtime-packet63.md)
- [Four coordinator screen commands](WINDOW.md)
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md)
- [Retention and reproduction](RETENTION.md)
- [CPU gates](evidence/cpu-gates.json), [timing diagnosis](evidence/diagnosis.json),
  [packet receipt](packet.json)
- [Do not repeat](DO-NOT-REPEAT.md)
