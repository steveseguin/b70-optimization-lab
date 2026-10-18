# Build archived — 2026-10-17

The complete `build/` tree is retained at:

`/mnt/raid-models/own-xpu-runtime-archive/packet38-integrated-build-20261017.tar.gz`

- SHA-256 (two reads): `03543e2ab7414c9e13e3ee13de1bfce6e29ae497a8b42ad13f2fb9b52a425058`
- Archive bytes: 2,380,859,116
- Regular files: 97,992 (including 36,864 tar hardlink entries); symlinks: 0; total tar entries: 101,995.
- Source allocated bytes before removal: 3,253,694,464.

`tar -tzf` passed. Every archived regular file matched the original SHA-256; hardlinks resolve to verified archived bytes and symlink targets matched. No open files were reported before archiving or removal. Active memory-plan checks use embedded baseline evidence; historical preparation scripts need restoration before reuse.

Restore from the repository root (CPU/file work only):

```sh
nice -n 19 ionice -c 3 taskset -c 8-15,24-31 tar -C /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet38-integrated -xzf /mnt/raid-models/own-xpu-runtime-archive/packet38-integrated-build-20261017.tar.gz
```

[Cleanup ledger](../disk-cleanup-20261017-1815/README.md).
