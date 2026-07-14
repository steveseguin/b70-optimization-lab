# DeepSeek V4 REAP/XPU Patches

Store focused runtime, loader, kernel, packer, and diagnostic patches here.
Preserve failed patches with a linked ledger result. Do not mix in the dirty
Qwen worktree diff or the historical AutoRound packet's identity.

## Active patches

- `0001-deepseek-v4-exact-xpu-moe-shapes.patch` adds fail-visible kernel
  coverage for the real DeepSeek V4 decode shapes: M=1/4/8, hidden width 4096,
  expert intermediate width 2048, top-k 6, and 40/64 local experts. It is
  committed as `552c9ceaf49622fefe170a527c84b1afc3b6b4bf` in the clean kernel
  worktree on top of v0.1.11 (`dda91d171fbc3f51d1d65a7f8839714b1efffd42`).
- `0002-deepseek-v4-unambiguous-shape-selectors.patch` adds explicit
  `experts40`/`experts64` and shape IDs so pytest filtering cannot accidentally
  select both expert counts through the shared `4096` dimension. It is commit
  `840482d03ee12f6398967757efee9a493225644d`.
