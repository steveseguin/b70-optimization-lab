# 2026-05-21 MiniMax Cudagraph Extra Negatives

This addendum extends the cudagraph repeatability boundary note with four additional launch/debug paths.

## Results

| Variant | Result | Notes |
| --- | --- | --- |
| `VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1` | FAIL | raw145 n512 still failed exact repeat; no NUL/control output |
| `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1` | FAIL | raw145 n512 still failed exact repeat; weak output refs are not the cause |
| `VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS=1` | ENGINE ERROR | recapture tries to capture after vLLM globally disables capture after startup |
| `--cudagraph-mode full_decode_only` | ENGINE ERROR | XPU FlashAttention scratch-memory feature is not available under SYCL Graph |

The first generated run in the failed repeatability variants still matched the deterministic cudagraph-none/eager raw145 n512 hash:

`faa1113318d1ee669cf204baa22dad501a6b9505a7211d13cf44a716f304e95b`

## Interpretation

The easy launch-flag surface now looks exhausted. The remaining path to keep the ~93 tok/s graph speed while satisfying long exact-repeat quality is code-level debugging of XPU graph replay state.

Most likely areas:

1. Runtime buffers whose addresses are stable but whose values are not being refreshed correctly before replay.
2. Piecewise graph replay around attention/KV metadata or positions.
3. The communicator no-op capture path used to force XPU graph with TP communication.
4. Any XPU graph limitation in FlashAttention that makes non-piecewise graph modes unsafe.

## Decision

No LocalMaxxing submission from these diagnostics. They are negative evidence and should remain in the reproduction notes so future runs do not repeat the same flag tests.
