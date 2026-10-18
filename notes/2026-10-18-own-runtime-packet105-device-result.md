# Packet 105 head split: device result (2026-10-18 06:44–06:55 UTC): NOT EXACT

- **Smoke** (lane B, `p105s-B-head-split-compute-incident64-v1`, candidate only, 1 prompt, 64 tokens): passed, no fault. The new cross-card transfer path runs.
- **Lane-A grid view 1** (`p105-71fdf43fef81-A-grid-1-head-split-compute`): **failed: "every-token oracle mismatch: architecture-tradeoff"**. The split produced a different token from the packet 49 oracle. The exactness gate stopped the screen; nothing inexact was recorded or used.
- GPU fault count unchanged (2). Lane-A teardown drained; the stale marker and latch were archived by the coordinator.
- All queued packet 105 grid views and packet 106's draft-split jobs (built on packet 105's transfer/merge code) were pulled.
- Packet 105's CPU gates (all 248,320 loader rows, hit/miss mocks, 33 startup checks) passed, so they did not model what diverged on the device. Codex 105x is analysing the first mismatching position (suffix vs prefix row; arithmetic vs data/order) and will propose a fix plus the CPU gate that would have caught it.
- Lesson: a one-prompt smoke proves the path runs, not that it is exact. Exactness needs the full 12-prompt suite.
