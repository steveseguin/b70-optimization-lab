# 2026-07-20 Option 4 Phase 0 mixed command-graph gate

## Numbers first

- **Verdict: PARTIAL; Phase 1 NO-GO.**
- The exact warmed oneDNN+Triton cluster records together and replays bitwise
  exactly: **40/40** changed-input direct-graph cases and **40/40** nested-graph
  cases.
- PTI enqueue-only windows fall from **2 eager Level Zero kernel appends to 1
  executable graph append**, a **1-boundary / 50% reduction**.
- The direct recorded replay and nested recorded replay each execute exactly
  one `zeCommandListImmediateAppendCommandListsExp` and zero direct kernel
  appends.
- Both recorded paths also execute one blocking `zeEventHostSynchronize`
  immediately before that append: **400.641 us direct**, **408.306 us nested**.
  This violates the committed Phase-0 no-host-sync rule.
- GPU used: logical XPU **3**, PCI `0000:47:00.0`, renderD129. The EAGLE worker
  remained PID **1710496** on logical XPU **1**, PCI `0000:27:00.0`, renderD131,
  alive with the same render-node FD before and after every probe. This task
  issued no signal or restart command.

## Exact feasibility cluster

The cluster is a dependent slice of the real M1 attention path:

1. `torch.ops._xpu_C.fp8_gemm_w8a16`, the incumbent oneDNN W8A16 `wq_b`
   primitive, M/N/K `1/8192/1024`, BF16 input, E4M3 weight, `[8,64]` FP32
   scales with `{128,128}` grouping;
2. its BF16 `[1,8192]` result is reshaped to `[1,16,512]` and consumed in place
   by Triton `_xpu_qnorm_rope_fp8_insert_kernel`, grid `(1,17)`, four warps.

The final qualification uses the actual M1 specialization: FP32 cos/sin,
block size 64, KV-cache shape `[2,64,584]`, production stride
`[1039680,584,1]`, and the copied incumbent warmed SPIR-V with SHA-256
`98c95c15d5411a79532c2379f7f4e0771e88934d0c6ce09d104e9e4587f7a91e`.
The copied cache entry is an immutable input to the probe; it was not rebuilt.

Supporting PTI device logging names the two eager kernels as:

- `gemm_kernel[SIMD16 {64; 1; 1} {16; 8; 8}]`;
- `_xpu_qnorm_rope_fp8_insert_kernel[SIMD32 {1; 17; 1} {128; 1; 1}]`.

## Substrate built

The new `option4-decoder/` Phase-0-only tree contains:

- `python/option4_decoder/command_cache.py`: COLD/WARMED/BUILT/
  PARITY_QUALIFIED/RETIRED lifecycle, same-queue enforcement, fixed pointer,
  shape, stride, offset, dtype, device, and backing-storage-size checks;
- `python/option4_decoder/parity.py`: raw-byte comparison including NaN payloads;
- `src/xpu_current_queue_interop.cpp`: isolated C++/SYCL shim that appends an
  XPUGraph-owned executable to the current PyTorch queue;
- `tools/phase0_mixed_capture_probe.py`: warm, capture, fixed-address replay,
  changed-input parity, guard checking, nested surrounding capture, EAGLE PID
  checks, and trace-window control;
- `tools/summarize_unitrace.py`: fail-closed boundary and host-sync counter;
- `manifests/kernel-abi-v1.json`: target/runtime/kernel ABI and ownership rules;
- `tests/test_parity.py`: byte-parity, storage identity, and fail-closed
  qualification tests.

The native shim was built only as a tiny isolated extension under the raw
result root. No shared XPU-kernel `.so`, vLLM runtime, service, or trainer was
rebuilt or replaced.

## PTI decision evidence

The authoritative enqueue-only trace windows exclude warmup, capture build,
input preparation, and the explicit parity-completion wait.

| Path | Direct kernel appends | Executable appends | Effective boundaries | Host sync |
| --- | ---: | ---: | ---: | ---: |
| eager | 2 | 0 | 2 | 0 |
| recorded | 0 | 1 | 1 | 1 |
| nested recorded | 0 | 1 | 1 | 1 |

Thus neither Triton nor oneDNN breaks recording: both are present in one
finalized executable and retain bitwise parity. The blocker is the installed
SYCL `command_graph` replay mechanism itself. Even the direct native shim calls
`zeEventHostSynchronize` before
`zeCommandListImmediateAppendCommandListsExp`, and capturing that replay in a
surrounding graph does not remove it.

Phase 1 must remain closed until one of these substrates passes the same gate:

1. a raw Level Zero regular/mutable command list appended directly on the owned
   PyTorch immediate queue/list without SYCL event bookkeeping; or
2. a whole-decoder command transaction that removes nested graph replay.

This finding does **not** require custom Triton or GEMM arithmetic: both kernel
types record correctly. If raw Level Zero cannot reuse their captured handles,
then the next escalation would be queue-explicit SYCL reimplementations, but
the present evidence does not justify that work yet.

## Evidence and preserved negatives

Authoritative raw root:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/option4-phase0-mixed-command-graph-exactmodule-20260720T192738Z`

That root includes `topology-and-protected-process-postflight.json`, which
preserves the `xpu-smi` logical-device/BDF inventory, sysfs render-node/BDF
mapping, and protected PID FD snapshot supporting the card assignments above.

The structured packet is
`experiments/deepseek-v4-flash-reap-xpu-b70/data/option4-phase0-mixed-command-graph-20260720.json`.

Earlier roots are preserved but do not qualify: the first used BF16 cos/sin;
the next fixed FP32 but retained benchmark block geometry; later iterations
successively fixed block size, cache stride, and exact cached-module identity.
Their paths are recorded in the structured packet so these mistakes are not
rediscovered.

No held-out pack was opened or modified. No LocalMaxxing action occurred.
