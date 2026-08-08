# Corsair USB recovery and model restoration

Date: 2026-08-08

## Why the models appeared missing

The 4 TB `CorsairExternal` USB drive was physically present as `/dev/sda2` but
was not mounted. Its NTFS `$MFTMirr` record 3 did not match `$MFT`, so the normal
`ntfs-3g` mount failed. The historical model directories had not disappeared.

## Fail-safe recovery

1. Mounted the volume read-only with kernel `ntfs3` and inventoried the model
   tree before making filesystem changes.
2. Saved the 183,052-entry inventory at
   `/mnt/fast-ai/storage-recovery/corsair-external-model-tree-pre-repair-20260808.tsv`.
   SHA-256:
   `98f90fdfd1e6ea4de30ba85bd812ede278830821a654cd4109796c954e8ecf8d`.
3. Hashed the important resident Qwen GGUFs into
   `/mnt/fast-ai/storage-recovery/corsair-external-key-model-hashes-pre-repair-20260808.sha256`.
4. Checked the NVMe device through the ASMedia bridge. SMART passed with zero
   reported media/data-integrity errors and zero error-log entries.
5. Unmounted the read-only filesystem, ran `ntfsfix`, and mounted it read/write
   with `ntfs-3g`. A write-and-sync check passed. About 1.8 TB was free.

Windows `chkdsk /f` followed by two Windows reboots is still required at the
next safe maintenance window. `ntfsfix` repaired the immediate Linux-mount
blocker but is not a complete NTFS consistency check.

## Storage convention

The canonical large-download cache is `/mnt/usb-models/llm-cache/hf`.
Standalone GGUFs belong under `/mnt/usb-models/models/<model-family>/`, and
complete direct model directories belong under `/mnt/usb-models/llm-models/`.
The older `/mnt/usb-models/hf-cache` is preserved pending reconciliation.

The external SMB host `DESKTOP-ALIENWA` was reachable at `10.0.0.9`, but guest
access was denied and no local SMB credential was available. It was not needed
because the recovered USB had sufficient capacity. No credential was guessed
or copied from an unrelated service.

## Host changes

Installed `smartmontools`, `cifs-utils`, and `smbclient` for storage diagnosis
and future authenticated backup work. No model or benchmark service was
started during recovery.

## BF16 backup repair

The historical USB copy of `Qwen-Qwen3.6-35B-A3B-995ad96e` had all 26 shard
names but 13 files were truncated. A verified append restored 27.0 GB. A full
content comparison then found three additional same-size mismatches in shards
1, 5, and 6. Those bad copies and their hashes were preserved under the model's
`.quarantine/20260808-content-mismatch/` directory before clean source copies
were installed. The final full `rsync -nrc` comparison against the 71.93 GB
internal source emitted no differences.

## Restored contributor models

The official `unsloth/Qwen3.6-27B-MTP-GGUF` Q4_K_M file was downloaded at
pinned repository commit `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace` to
`/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_K_M.gguf`.
The completed size is `17,106,773,120` bytes and its SHA-256 is
`a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f`,
matching the published artifact.

The complete `Qwen/Qwen3.6-27B` BF16 snapshot
`6a9e13bd6fc8f0983b9b99948120bc37f49c13e9` was also backed up from the
internal Hugging Face cache to
`/mnt/usb-models/llm-models/Qwen-Qwen3.6-27B-6a9e13bd6/`. Cache symlinks were
dereferenced so the 55.59 GB backup is self-contained. A full `rsync -nrcL`
comparison emitted no differences across all 15 weight shards and support
files.

Safetensors header parsing also passed for both BF16 backups: 26 shards and
1,045 tensor entries for 35B-A3B, and 15 shards and 1,199 tensor entries for
27B.
