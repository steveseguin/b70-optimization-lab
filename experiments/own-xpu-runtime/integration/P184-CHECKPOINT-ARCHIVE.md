# Packet184 closed checkpoints: verified archive and local pruning

The completed copy covers these four directories below
`experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/v5/evidence/`:

- `device-smoke-B-p184/run/checkpoints/s1`
- `device-lifecycle-B-p184/run/checkpoints/s1`
- `device-lifecycle-B-p184/run/checkpoints/s2`
- `device-lifecycle-B-p184/run/checkpoints/sref`

Both rows have passed summaries and zero native exit status. Their five leg
teardown receipts record `drained=true`. The earlier `RESTORE-ARCHIVE.md`
already identifies packet184 as closed; its October19 archive is separate
historical retention and is not a substitute for verifying this new copy.

The four trees contain 868 binary files (530,718,848 bytes) plus eight metadata
files. Of these, 796 rank tensor files named `blk.*.bin` or containing `.blk.`
account for 530,629,120 bytes. After copy and complete readback verification,
all796 untracked tensor copies were removed. All72 small binary files
(89,728 bytes), four manifests, four `fields.tsv` files, sibling locks and
surrounding receipts remain. Root free space rose from27,668,488,192 to
28,199,522,304 bytes. Local checkpoint trees are incomplete until reconstructed.

`READY-FOR-DEVICE.json` and `v5/cpu-seal.json` do not include these device-output
paths. No tracked Python or JSON file contains an exact reference to either
checkpoint directory path. Generic native tools still consume the trees:

- `v5/lifecycle_report.py` reads `run/lifecycle-inputs.json`, teardown receipts
  and checkpoint manifests. It compares manifest blob digests without reading
  tensors, so retaining metadata preserves historical report analysis.
- `v5/tp2_checkpoint.py` and native full-inspect/restore operations require the
  complete rank blob sets. A pruned local tree must continue to fail those
  checks until its original bytes are reconstructed. Do not weaken a frozen
  checker or relabel metadata-only availability as a restorable checkpoint.

The new helper [archive_p184_checkpoints.py](archive_p184_checkpoints.py) has no
delete mode. The coordinator ran it once after review, then separately ran
[prune_p184_checkpoints.py](prune_p184_checkpoints.py) to remove only copies
whose complete archived and original bytes still matched. Historical command:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/integration/archive_p184_checkpoints.py --copy-verify
```

It creates only the new external uncompressed archive
`/mnt/usb-models/own-runtime-archives/p184-closed-checkpoints-20261023.tar`
and `packet184-twocard-checkpoint/v5/evidence/checkpoint-archive-20261023.json`.
It includes every file and rank directory in all four checkpoint trees, checks
all native manifest blob hashes, records original source/file hashes and inode
stamps, verifies every tar member plus the whole-archive hash, then rehashes
the unchanged originals. A failed attempt leaves its archive and failure
receipt for review and refuses to overwrite them. `--plan` is read-only.

The archive SHA256 is `2109dd3339232557a178e0dd98a23d6ab4682399c189586ba2f256408b968ecb`.
[Copy/readback receipt](../stage2/packet184-twocard-checkpoint/v5/evidence/checkpoint-archive-20261023.json),
[prune receipt](../stage2/packet184-twocard-checkpoint/v5/evidence/checkpoint-local-prune-20261023.json)
and [incomplete-local marker](../stage2/packet184-twocard-checkpoint/v5/evidence/ARCHIVED-CHECKPOINTS-20261023.json)
record the operation. The marker is outside checkpoint directories so it does
not alter their native closed-file-set metadata.

For reconstruction, verify the recorded whole-archive digest and member map,
then extract only the selected checkpoint subtree into fresh local scratch
storage with sufficient free space. Preserve the relative `rank0`/`rank1`
layout and original metadata. Check every file digest/extent against the copy
receipt and native manifest before making the reconstructed root available to
full-inspect/restore. If restoring a pruned original path, first verify its
retained metadata/control files are unchanged, and copy only missing tensor
members; never overwrite surviving metadata or approximate state. The external
archive is durable evidence storage, not a private live checkpoint root.
