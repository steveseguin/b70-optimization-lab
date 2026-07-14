# DeepSeek V4 REAP/XPU Scripts

Helpers are added only as their stage begins. The user-authorized public K160
download is the explicit exception to the original pre-Stage-4 hold.

- `download-k160.sh`: immutable 0xSero K160 snapshot using the protected local
  Hugging Face token and external Xet cache;
- `verify-k160-artifact.sh`: fail-closed shard/byte/config, expert-map/index,
  uploader revision, and SHA-256/Hugging Face verification;
- `promote-k160-hot.sh`: verified archive-to-NVMe copy plus stable `current-k160`
  symlink for faster repeated startup;
- `capture-stage0.sh`: runtime, package, topology, and storage identity;
- `bootstrap-clean-runtime.sh`: one-time clean-venv dependency bootstrap that
  filters out the released kernel wheel, pins the critical Torch-adjacent test
  stack, and hands off to the exact source builder. It expects the documented
  clean worktrees and oneAPI 2025.3 system packages to exist;
- `build-clean-runtime.sh`: fail-closed rebuild of the pinned vLLM and kernel
  worktrees with oneAPI 2025.3, Xe2, and SYCL-TLA enabled. It uses the upstream
  default attention profiles (including DeepSeek MLA) instead of compiling the
  roughly 600-variant full profile on every clean build. The durable default is
  eight compile jobs after the grouped-GEMM unit was killed at 16;
- `run-exact-shape-gates.sh`: four-card parallel low-level MXFP4/INT4
  correctness subset at the real H4096/I2048/top-k6 decode shapes. It does not
  replace the native-selector, performance, replay, or TP4/EP gate;
- `serve-k160-tp4-smoke.sh`: fail-closed graph-off TP4+EP/8K server with XCCL
  preflight, full argv/runtime identity, no remote checkpoint code, no prefix
  cache, and no speculation.

The official-source downloader remains separate and deferred until teacher and
hash-preserved pack work begins. Never edit or omit MTP shard 46 in an archived
snapshot; derive a separate target-only hot index if nonspec loading later
benefits from omitting it.
