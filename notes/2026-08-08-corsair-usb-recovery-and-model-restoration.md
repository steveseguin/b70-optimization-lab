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
