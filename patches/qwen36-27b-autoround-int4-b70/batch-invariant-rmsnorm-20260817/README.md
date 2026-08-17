# Qwen3.6 27B INT4 batch-invariant RMSNorm experiment

Status: **preserved experiment; inconclusive and not production-ready**.

This packet freezes the exact source/config identity used by the final
post-reboot 25-prompt candidate. The cumulative
`tested-*.working.patch.gz` files are the authoritative reconstruction
artifacts. Decompress them before applying; they apply against the heads below
and intentionally include the complete tested stack, including disabled
diagnostic code.

| Component | Git head | Cumulative patch SHA256 |
| --- | --- | --- |
| `llm-optimizations` | `f0e86b89e6bdd25ceac762fc34fb2169414b3e32` | `0f0e1e1df2cf324e38b9a7d9f2a45d77166341c74734fca76cf3ba94f548de0f` |
| `vllm` | `a63ff886e1c9c90f919e8b46a63f34027dfae823` | `e8f154cb8e497f6e18bd7d917e12011f45f5664967749392a47a722e1117e263` |
| `vllm-xpu-kernels` | `6a40e2baf3f8710b89e48d18bf214708ba2dbf9a` | `10d7cb28a11d7ddcc1caf5737368a014a06ffd0ec15be699e8e8f31da8649062` |

The loaded `_xpu_C.abi3.so` SHA256 was
`f494925774cf50cd2038684cb64325fcd491c51f2eab94454878c5e804dbaa61`.
The identity and runtime manifests are included. `SHA256SUMS` verifies every
packet file.

`experimental-fast-rmsnorm.patch.gz` has compressed SHA256
`1f592d8e69828a5d593a733d4da70b57a02946299d040594a51ee8e470d65ab9`;
its decompressed patch SHA256 is
`88df2cb721426bdfa34e0a1fb2c3dbec48f6036bd52c373851954cec6bdac6e4`.
It isolates the graph-compatible caller-owned output form of the fixed per-row
Triton RMS reduction. It is preserved for
review; it is **not** a production patch. Although it repaired the focused
near-tie and matched both then-sealed four-prompt controls at `106.663 tok/s`,
the matched 25-prompt candidate was only 12/25 exact at `93.446 tok/s`
conventional.

The stateless M4/M1 oracle is included as
`check-qwen27-w4a16-m4-m1-exact.py` (SHA256
`7f37456e4d00dec32c42e2f00c3318984b3f4b9dbbb2e913783d278a923f67fa`).
`run-arm.sh.snapshot` plus the cumulative lab patch reconstruct the exact
launcher. The final candidate enabled real smoke, benchmark, and quality gates
with `VALIDATION_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=1`, exact GDN recurrence,
PIECEWISE mode, and INT4/INT8 completion barriers on GPUs `0,1`; the full
resolved environment is in `tested-identity.env`.

Important: the omnibus lab patch contains an unexercised graph-safe
FlashAttention build-script change. The final run loaded the already-staged
extension/device/stock hashes recorded in
`tested-xpu-staged-runtime-binaries.sha256`. Rebuilding that overlay from the
current script creates a different runtime identity.

Final target:
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-25-target-a-20260817T063000Z`.

Final candidate:
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-25-spec-b-postreboot-20260817T124553Z`.

See the [closeout note](../../../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md)
and [structured summary](../../../data/qwen36-27b-autoround-int4-batch-invariant-rmsnorm-closeout-20260817.json).
