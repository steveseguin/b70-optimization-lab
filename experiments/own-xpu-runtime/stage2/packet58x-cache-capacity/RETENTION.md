# Packet58xc source and evidence snapshot

Retain `lineage/58xb-source-snapshot.tar.gz` (10,235,424 bytes). It closes the
old transitive source/evidence dependencies without making readiness depend
on mutable sibling files. It contains 1,159 original files, including the
pre-amendment receipts. Every member was checked against its recorded SHA-256;
changed tracked source files were recovered from the original implementation
commit `e22fe0662cfc75d21a0b5048015aad63ddbbcf53`, never silently repinned.
The archive and member hashes are in `lineage/58xb-source-snapshot.json`.

This archive is deliberately retained in Git because it is required to replay
the maintenance decision and restore the source closure on another checkout.
It contains no model payloads. Frozen parent executable/object binaries are
not duplicated; their exact paths and hashes are in `immutable-inputs.json`.

`maintenance_decision.py` verifies the archive and extracts only the saved
smoke/bracket evidence into temporary storage before replaying all native
tokens against packet49. `frozen_inputs.py` verifies every restored member and
restores historical build/analysis inputs under ignored `frozen-inputs/repo/`.
Source include paths are mechanically relocated there; the archive always
retains the original bytes. Existing local files must match the deterministic
restoration or restoration refuses. No original evidence was removed.

The failed packet58x smoke at `evidence/card0-capacity-a/smoke/` remains
untouched. K1a/K1b passed; WSCREEN never created its native window. New work
must use the fresh `card0-capacity-c` names and pass its own smoke.
