# Laguna and Gemma source archive consolidation

Reviewed against commit `8c4505c31` on 2026-10-10. This is a storage change:
every selected source version and original byte hash is preserved, including
rejected patches and diagnostic states. It does not promote a runtime or result.

| Selection | Files | Original bytes | Archive bytes | Payload bytes saved |
| --- | ---: | ---: | ---: | ---: |
| Four historical Laguna Git bundles | 4 | 185,069,979 | 45,359,284 | 139,710,695 |
| Gemma cumulative source snapshots | 72 | 42,984,043 | 120,716 | 42,863,327 |
| Total | 76 | 228,054,022 | 45,480,000 | **182,574,022 (174.12 MiB)** |

Small manifests, restoration code and documentation add some checkout bytes.
Git history is unchanged, so this reduces checkout size rather than claiming
the same reduction in clone size or existing Git object storage.

## Representation and restoration

The archives use one deterministic PAX tar stream per lane, sorted by original
path, with regular-file mode 0644, zero uid/gid/mtime and single-thread XZ
compression (64 MiB dictionary). Solid compression shares repeated source and
Git-pack bytes while keeping the original files exactly recoverable. Git
repacking or regenerated incremental bundles would change the byte hashes
pinned by historical evidence; this representation avoids that change.

- [Laguna restore guide and member inventory](../../../patches/laguna-s-2.1-xpu-b70/SOURCE-ARCHIVE.md)
- [Gemma restore guide and member inventory](../../../patches/gemma4-26b-a4b-q8-b70/SOURCE-ARCHIVE.md)
- [Machine-readable evidence, consumers and verification](archive-consolidation.json)
- [Restore helper](../../../tools/restore-source-archives.py)

The accepted Laguna shared-elementwise and QKNorm/RoPE bundles remain unpacked.
Gemma's canonical encoded record patch, older top-level review patches and
diffstats remain unpacked. Existing package commands and exact source inputs
therefore retain their normal paths. New names are not hidden: each lane's
ignore file lists only the exact historical paths that the helper restores.

The helper verifies every archive member before any extraction and checks each
member again while writing. It never overwrites different existing data or
follows destination symlinks. By default it only verifies; extraction needs an
explicit destination and passes the repository's 50 GiB reserve check. External
destinations can require their mount with `--require-mount`. It does not execute
historical scripts or apply source patches.

## Evidence preservation checks

Before removing unpacked copies:

- All 76 files were restored under an isolated `/tmp` destination and compared
  byte-for-byte with the originals, in addition to size and SHA-256 checks.
- All four restored bundles passed `git bundle verify`, imported into an
  isolated bare repository and retained their exact heads. Every original and
  restored tip exported the same source tar, with 5,954 entries per tip.
- Original-bundle and restored-bundle repositories had identical inventories
  of 22,563 objects and identical strict `git fsck` results, including the
  inherited limitation below.
- Ten CPU-only helper tests cover corruption, missing/duplicate members,
  traversal, symlinks, conflicting data, idempotence, second-pass changes and
  external mount admission.
- Full tracked-text searches covered each original filename and SHA-256:
  125 matching lines in 61 files. Forty-four maintained narratives received
  dated restoration pointers; shared navigation receives the same pointer.
  Their pre-edit full-file hashes had no tracked hash references. No actual
  Markdown links pointed directly to the selected original members.

Frozen JSON results, old inventories, benchmark corpora and canonical hash
aliases remain unchanged. The machine-readable audit records every matching
consumer, its original file hash, line number, matched member and whether the
match was a filename or hash. The lane manifests resolve their historical
paths to byte-identical restored files; no old measurement or hash was repinned.

## Inherited Git ancestry limitation

Both original and restored large Laguna bundles omit parent
`b5adb027ad03c29b46181752ba3b1cb84eff1dd4` of commit
`40eac9a9d92bba51ad49ca777a5517ee212ea394`. Their strict `git fsck` checks
exit 2 for the same missing ancestor. The original bundles declare no
prerequisite, so `git bundle verify` alone does not reveal the issue. A bounded
check of the two large accepted bundles left unpacked found the same boundary.

The selected tip trees remain fully exportable, and this storage change
preserves the original object sets and bytes. It does not claim complete Git
ancestry or silently repair it. A future ancestry repair would need separately
identified upstream evidence and a new artifact, retaining these originals.

## Why these sources still matter

Laguna's local TP4 DFlash replication preserved arithmetic but added
4.208694 ms of projection work while removing only 1.239689 ms of reductions;
the [component result](../../../data/laguna-dflash-local-tp4-negative-20260801.json)
prevented an unproductive endpoint campaign. Inline gather retirement reached
its intended graph topology but failed model exactness; the
[second attempt](../../../data/laguna-target-inline-gathers-fixed-input-v2-negative-20260801.json)
retained the raw response and localized the first token mismatch to index 176.
These are useful negative mechanisms, not disposable failed builds.

Gemma's [direct sampled-ID experiment](../../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-direct-sampled-egress-negative.md)
shows why parity must include null outputs: the first diagnostic gave false
reassurance, while strict checks caught an unwritten buffer and prevented an
unsafe copy removal. Its [local-memory follow-up](../../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-no-kq-lsm-negative.md)
preserves a valid but noise-level result and a concrete reopening condition:
changed compiler/kernel layout must make that allocation affect occupancy.
The snapshots retain the accepted source, each rejected variation and the
restored state so those distinctions remain reviewable.
