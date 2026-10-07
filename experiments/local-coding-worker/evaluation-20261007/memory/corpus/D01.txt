# Four-card consolidation follow-up — October 6 EDT / October 7 UTC

The owner authorized continuing the consolidation independently. We kept LTX
and Flash-Next parked, preserved models and experiment history, and raised the
disk reserve without using the unreliable external drive. No model process,
GPU test, restart, host power or memory setting change was introduced.

## Storage result and recovery

Eight inactive August runtime/build trees occupied 20,336,185,344 allocated
bytes (18.94 GiB). Complete tar.zst archives occupy 2,672,559,773 bytes (2.49 GiB)
under `/home/steve/git-archives/staging-consolidation-20261007/`. Their unpacked
copies were removed only after verification. This saves about 16.45 GiB net;
available root space afterward was 57,829,376,000 bytes (53.86 GiB).

[Audit](../data/maintenance/staging-consolidation-20261007/audit.json),
[complete verification](../data/maintenance/staging-consolidation-20261007/complete-verification.json),
and [archive hashes and exact restore commands](../data/maintenance/staging-consolidation-20261007/summary.json)
preserve the evidence. The immutable sealed q64k32-r2 build remains recoverable
byte for byte, including source, dependencies, compiled runtime and receipts.
Historical launchers retain their original path references; restore the
relevant tree before replaying them. No published runtime pin was replaced.

The audit found no models, internal symlinks, hardlinked files or special files
in these trees. Privileged process checks covered command lines, environments,
maps, open files and working directories, with zero matches or access errors.
Inbound-link checks were limited to home top-level and tracked repository
symlinks; they were not a full-system link census.

Archive creation preserved modes, ACLs and extended attributes. Every archive
was SHA-256 checked and compared against the original. Independent review
added complete member inventories to catch files omitted or newly added during
archival, and directory/receipt fsync before final removal. The complete
inventories matched the source trees and audit file counts; repeated tar byte
comparisons passed for all eight trees.

The initial unprivileged removal hit a write-protected directory in
`qwen38-gdn-poison-stage-20260822` and stopped. Its complete verified archive
was restored in place, including the files already removed. All eight sources
then passed the full inventory and repeated byte comparisons. This also
rehearsed restoration of that real archived runtime. After a repeated idle-use
check, privileged removal handled the preserved read-only modes. Archive and
receipt files plus parent directories were fsynced. Nothing was reconstructed
from a newer build or silently discarded.

These archives remain on the internal disk. They protect against accidental
loss of unpacked staging content, **not failure of that disk**. The external
EX400U remains unmounted and unqualified after its USB incident.

The existing storage admission check now admits a planned 3 GiB write while
retaining 50 GiB, and refuses 5 GiB at this snapshot. Receipts are alongside
the archive summary. Admission is a point-in-time check, not a reservation;
budget simultaneous caches, temporary files and outputs before each new job.
There is no automatic deletion policy or new background service.

## Safer future resumption

- [LTX progress-lock recovery](../experiments/ltx25-b70/recovery/20261007-progress-lock/README.md):
  the exact installed source leaks its display lock after synthetic ENOSPC.
  An isolated try/finally patch passes ten CPU tests, preserves error propagation
  and normal rendering, and is linked from the resume handoff. Nothing is
  installed or changed in sealed packets. This supports the incident diagnosis
  but does not prove the original lock owner or GPU correctness.
- [Qwen TP2 candidate](../experiments/qwen38-27b-b70/release-candidates/20261006-tp2-state-fix/README.md):
  20 overlay and 14 offline-preflight tests pass. Local vLLM source can ignore an
  excluded or unimportable plugin, even though registration exceptions propagate.
  Receipt validation therefore refuses pending/self-declared kernel qualification.
  No real runtime is allowlisted and no launcher is provided. The exact R314
  kernel/source evidence and in-process checks in every worker remain required;
  local older-loader evidence does not qualify R314.

## Priorities after consolidation

1. Obtain a dependable independent backup destination and copy the preserved
   research plus archives with read-back verification. Do not regard Git as a
   backup of model weights or untracked raw experiment artifacts.
   **Later October 6 update:** [a selected additional EX400U backup](2026-10-06-ex400u-backup-review.md)
   passed full read-back and restore checks; internal originals remain. This
   closes the immediate additional-copy gap for its selected scope, while
   long-term drive reliability and complete-machine coverage remain unqualified.
2. Keep the existing RAM exclusion unchanged. **Owner clarification October 6:
   no RAM replacement in 2026.** Blocks 53–57 were rechecked offline and the boot
   service enabled. Hardware replacement is removed from the near-term plan;
   the mitigation remains active and ordinary fault handling still applies.
3. Coordinate exact Qwen inputs and owning-host availability, then qualify the
   candidate with actual kernels, unchanged-model checks and full release
   evidence. Do not interfere with the other host's active context experiment.
4. Resume LTX or Flash-Next when the owner returns to that lane, using its saved
   handoff and current storage admission. Keep failed trials and original
   references, and do not silently adopt output-changing performance gains.

Further deletion is not needed for the immediate unblock. The remaining margin
is modest; a large new model or build needs separately verified capacity.
