# Archived detmath test vectors

Archived on 2026-10-17 from `packet17-detmath/build/wa-reference` on
`steve-b70s`. The numerical input evidence is preserved in this archive:

- Archive: `/mnt/raid-models/own-xpu-runtime-archive/packet17-detmath-wa-reference-20261017.tar.gz`
- SHA-256: `6de096ea7f50fe9cb14f3ff3926bff23e9a26c4d12d402acd8cf2e06c026161b`
- Archive bytes: **14,151,268,858**
- Regular files: **30**
- Original file bytes: **14,643,930,234**; allocated disk bytes: **14,644,039,680**

The archive was written directly to the RAID disk. Before removing the exact
source directory, its listing passed, the file count matched `find -type f`,
every archived member matched its original SHA-256, and two full archive
checksum reads agreed. Source names, sizes, timestamps and inodes were unchanged.
No active/queued reader, inbound symlink or open file was identified.

Restore into the packet's **build** directory (the archive contains
`wa-reference/`):

```sh
printf '%s  %s\n' '6de096ea7f50fe9cb14f3ff3926bff23e9a26c4d12d402acd8cf2e06c026161b' '/mnt/raid-models/own-xpu-runtime-archive/packet17-detmath-wa-reference-20261017.tar.gz' | sha256sum -c -
nice -n 19 ionice -c 3 taskset -c 8-15,24-31 tar -C /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet17-detmath/build -xzf /mnt/raid-models/own-xpu-runtime-archive/packet17-detmath-wa-reference-20261017.tar.gz
```

Restore before rerunning old exhaustive-vector checks.
[Cleanup ledger](../../disk-cleanup-20261017-1815/README.md).
