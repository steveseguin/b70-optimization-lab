# Archived untracked files (2026-10-19)

This packet is closed. Its untracked/ignored build outputs and device-run bulk (4283 files, 622346240 bytes) were moved by the coordinator to
`/mnt/raid-models/own-xpu-runtime-archive/closed-packets-2026-10-19/packet184-twocard-checkpoint.tar` (verified with `tar -d` before removal). The file list is `packet184-twocard-checkpoint.files` and sha256 manifest `packet184-twocard-checkpoint.sha256` in the same folder.
Tracked files (sources, notes, committed summaries) are unchanged. Restore from the repository root:

```bash
tar -xf /mnt/raid-models/own-xpu-runtime-archive/closed-packets-2026-10-19/packet184-twocard-checkpoint.tar
sha256sum -c /mnt/raid-models/own-xpu-runtime-archive/closed-packets-2026-10-19/packet184-twocard-checkpoint.sha256
```

## October23 checkpoint tensor archive

Four subsequently present closed checkpoint trees now have a separately verified
[complete archive and reconstruction map](../../integration/P184-CHECKPOINT-ARCHIVE.md).
Their796 redundant local tensor files were pruned; metadata and small controls
remain. Use that new receipt for those trees before native full inspection or
restore. The October19 source/build archive above remains a separate artifact.
