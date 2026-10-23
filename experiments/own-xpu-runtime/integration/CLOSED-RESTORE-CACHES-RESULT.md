# Closed compiler-cache archive and headroom recovery

## Question and identity

Recover useful root-disk headroom while retaining the exact compiler artifacts
from eighteen closed card0/card3 restore20–28 applications. Active restore29,
model weights, logs, overlays, research results and directories are outside the
removal list. The original normal-user attempt refused before mutation; its
[refusal](CLOSED-RESTORE-CACHES-REFUSAL.md) and frozen inputs remain preserved.

## Outcome

The separately reviewed privileged filesystem path completed one copy/verify
and one prune invocation through the user coordinator CLI, both exit0. All8,766
originals were copied and read back with exact bytes and UID/GID/mode, then all
originals were rehashed. Only after that proof and a second complete verification
did18 guarded batches remove the exact8,766 files:1,070,345,088 logical bytes,
representing1,088,151,552 allocated source bytes. Directories remain in place.

The external tar is
`/mnt/usb-models/own-runtime-archives/closed-restore20-28-compiler-caches-20261023-privileged.tar`,
1,086,013,440 bytes, SHA256
`9d7ef53e18d3e76e58afbdd9614b3ca9097730bffae742a7623a95afca6ff9e6`.
The companion checksum sidecar and exclusive external attempt records remain.
Root had28.746GB free at the subsequent CPU-plan check, roughly940MB above the
27GB floor plus the806,354,944-byte full forecast. This point-in-time headroom
includes concurrent repository writes; it is not exclusive allocation accounting.
External free space remained about102.86GB, above the50GiB reserve.

## What worked

All18 durable sibling incomplete-cache markers and the complete global restore
map existed before the first unlink. Each batch reverified the full recovery
archive, kept its descriptor open, hashed each original, checked inode/stamps,
and unlinked relative to a held no-follow parent descriptor with directory
fsync. The coordinator checked all three current applications and the external
mount before and after batches. Their recorded PIDs and exact restore29
configuration remained unchanged throughout. No service or machine setting was
changed, and no model/native process was started by this operation.

The native-serving preparation now has sufficient measured local headroom to
derive a fresh CPU plan. This storage result does not itself admit device work.

## What failed or remains uncertain

The first unprivileged attempt could not read36 root-owned mode0600 files;1,908
root-owned unlink parents also required scoped privilege. The new child accepted
only fixed copy/verify/prune-root operations and source-bound paths. Review added
explicit0600 user records, original tar attribute verification and preservation
of completed child evidence on later coordinator errors. No operational failure
occurred in the privileged copy or prune. Its exceptional child-retention path
was CPU-tested but was not exercised by these successful actual invocations.

The archive and durable maps are recovery evidence, not an automatic restored
application. The local historical caches are intentionally incomplete. Restore
only into fresh separate directories after checking the entire tar and every
member SHA; no automatic extraction or old-service restart is authorized.
Trusted coordinator exclusivity remains an assumption, with no hostile-user or
atomic-filesystem claim. Historical closure limitations remain documented in
the original retention record.

## Evidence and retention

- [Privilege boundary and operation design](CLOSED-RESTORE-CACHES-PRIVILEGED.md).
- [Independent preparation review](receipts/independent-closed-restore-caches-privileged-review.json).
- [Verified copy receipt](receipts/closed-restore-caches-privileged-copy.json).
- [Complete pre-unlink recovery map](receipts/closed-restore-caches-privileged-prune-start.json).
- [Final prune receipt](receipts/closed-restore-caches-privileged-prune.json).
- [Root final observations](receipts/closed-restore-caches-privileged-root-final.json).

The large copy JSON and global prune map are intentionally permanent Git
artifacts. The copy receipt binds all8,766 original stamps, hashes, ownership/
mode and archive members; the prune helper consumes those exact bytes, and a
future recovery needs the same mapping. The global map proves the recovery
information available before deletion; per-root admissions and batch receipts
preserve failure boundaries and actual removed lists. They are neither build
outputs nor disposable duplicate logs. Recover historical receipt bytes with
`git show <result-commit>:experiments/own-xpu-runtime/integration/receipts/<receipt-name>.json`
into a separate review path. Never regenerate the fixed inventory from pruned
local trees or silently replace source pins. The external tar is retained for
research recovery, with its checksum and location recorded above.

## Independent result audit and next action

[Independent result audit](receipts/independent-closed-restore-caches-privileged-result.json)
passed: the reviewer directly rehashed the whole external archive, checked all
8,766 originals absent, all18 recovery markers complete and all2,197 directory
identities unchanged. Per-member/original verification is attributed to the
reviewed child receipts; retained service proofs are not new service queries.
The separate streaming-window admission still requires its exact source/plan
closure, fresh host checks and successful CI.
