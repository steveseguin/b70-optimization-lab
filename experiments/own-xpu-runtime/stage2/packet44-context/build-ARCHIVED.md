# Build archived — 2026-10-17

The complete `build/` tree is retained at:

`/mnt/raid-models/own-xpu-runtime-archive/packet44-context-build-20261017.tar.gz`

- SHA-256 (two reads): `d919cb0cabba2dcc9704c8dfc307a57bc066233c8aa5e91dd50a214956ebd771`
- Archive bytes: 1,439,389,433
- Regular files: 115,423 (including 49,920 tar hardlink entries); symlinks: 0; total tar entries: 120,243.
- Source allocated bytes before removal: 3,301,097,472.

`tar -tzf` passed. Every archived regular file matched the original SHA-256; hardlinks resolve to verified archived bytes and symlink targets matched. No open files or inbound symlinks were found. Historical `speed4_attribution.py` analyses need restoration before reuse; active runtime source references are outside this build tree.

Restore from the repository root (CPU/file work only):

```sh
nice -n 19 ionice -c 3 taskset -c 8-15,24-31 tar -C /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet44-context -xzf /mnt/raid-models/own-xpu-runtime-archive/packet44-context-build-20261017.tar.gz
```

[Cleanup ledger](../disk-cleanup-20261017-1815/README.md).
