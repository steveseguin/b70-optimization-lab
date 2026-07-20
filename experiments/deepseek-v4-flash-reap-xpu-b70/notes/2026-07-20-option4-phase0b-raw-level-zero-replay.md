# 2026-07-20 Option 4 Phase 0b raw Level Zero replay

## Numbers first

- **Verdict: GO. Phase 1 (`M1AttentionBoundaryV1`) is unblocked.**
- GPU: logical XPU **2**, PCI `0000:43:00.0`, renderD128.
- Protected EAGLE: PID **1710496** remained alive on logical XPU **1**, PCI
  `0000:27:00.0`, renderD131, with the same render-node FD before and after
  every qualifying run. No signal, restart, service change, or shared-runtime
  rebuild occurred.
- Raw mechanism: a regular finalized Level Zero graph list is appended directly
  to PyTorch's owned in-order immediate list with
  `zeCommandListImmediateAppendCommandListsExp`.
- Changed-input bitwise parity: **40/40** qualification cases and a second
  **40/40** traced-support run using the same fixed seed schedule.
- PTI replay window: **1 Level Zero submission boundary, 0 host syncs**. The
  only Level Zero call is one
  `zeCommandListImmediateAppendCommandListsExp`; there are zero direct kernel
  appends, zero queue executes, and zero `zeEventHostSynchronize` calls.
- Phase 0 comparison: the SYCL replay wrapper also had one boundary but made
  **1 `zeEventHostSynchronize`** per replay, measured at **400.641 us** in the
  direct trace (408.306 us nested).
- Raw replay host enqueue overhead with two pending input updates is **39.129
  us median**, 39.94386 us mean, 37.851-53.480 us range over 100 serialized
  replays; completion waits are outside the measurement. The same untraced
  SYCL-wrapper control is 42.2795 us median, a measured **3.1505 us / 7.45%**
  host-enqueue reduction. Under PTI, the raw append itself is 412.945 us and
  the trace-window wall time is 599.276 us. PTI timing is instrumentation-
  perturbed: the removal of Phase 0's 400.641 us traced host-sync call must not
  be presented as a 400 us real-wall saving. PTI is authoritative for API/count
  structure and the paired untraced harness is authoritative for overhead.

## Mechanism

The arithmetic and capture source are unchanged from Phase 0: oneDNN
`fp8_gemm_w8a16` produces BF16 `[1,8192]`, reshaped as `[1,16,512]`, and the
promoted Triton fused QNorm/RoPE/FP8-KV-insert kernel consumes it in place.
The exact cached SPIR-V and loaded XPU extension hashes are unchanged.

PyTorch exposes its current SYCL queue through
`c10::xpu::getCurrentXPUStream().queue()`. On this runtime,
`sycl::get_native<sycl::backend::ext_oneapi_level_zero>(queue)` returns the
owned `ze_command_list_handle_t` immediate list. The bridge fails closed unless
the queue is in order and its native handle remains identical.

The installed oneAPI 2025.3 headers declare a Level Zero graph backend return
type, but executable `command_graph` has neither `get_backend()` nor
`getNative()`; direct public native extraction does not compile. Phase 0b
therefore enables the standard Level Zero tracing layer for one sacrificial
build-time `queue.ext_oneapi_graph` replay. An epilogue callback observes the
single regular child-list argument to
`zeCommandListImmediateAppendCommandListsExp`. The tracer is then disabled and
destroyed. This one-time replay and its SYCL host sync are outside parity,
overhead, and PTI verdict windows.

All measured replays call Level Zero directly with the borrowed immediate and
regular list handles. The XPUGraph remains alive and owns the finalized list,
kernel modules, captured oneDNN scratchpad, and allocator pool. No mutable list
is required because all addresses and geometry are fixed. The installed loader
supports the mutable-list extension but does not expose
`zeCommandListCreateImmutable`; a harvested regular list cannot be made
mutable retroactively.

## Gate evidence

Every replay checks the current queue identity plus ten tensor bindings,
including data pointer, backing-storage pointer/size, shape, stride, storage
offset, dtype, and device. Both 40-case runs finish in
`PARITY_QUALIFIED`; Q output, KV cache, and guard storage match eager byte for
byte. Serialized completion waits prevent reappending the same regular list
while an earlier execution may still be in flight.

The decisive paused PTI window contains exactly:

| API | Count |
| --- | ---: |
| `zeCommandListImmediateAppendCommandListsExp` | 1 |
| direct `zeCommandListAppend*` calls | 0 |
| `zeCommandQueueExecuteCommandLists` | 0 |
| `zeEventHostSynchronize` | 0 |
| all host-sync/query markers | 0 |

This is one executable boundary with no graph break and no host synchronization
on replay. The dependency between pending input preparation and the mixed
cluster remains device ordered because both are appended to the same in-order
PyTorch-owned immediate list.

## Decision and scope

Phase 1 may proceed on this raw regular-list substrate. It must retain the same
fail-closed ownership, in-order queue, fixed-address, lifetime, bitwise parity,
and PTI no-host-sync rules. Phase 0b does not build any Phase 1 primitive.

Raw evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/option4-phase0b-raw-lz-20260720T195000Z`

That root includes `topology-and-protected-process-postflight.json`, recorded
after the qualifying runs. It maps logical XPU 2's renderD128 to
`0000:43:00.0`, confirms EAGLE PID 1710496 remained on renderD131 /
`0000:27:00.0`, and shows no remaining workload on XPU 2.

Tracked structured packet:

`experiments/deepseek-v4-flash-reap-xpu-b70/data/option4-phase0b-raw-level-zero-20260720.json`

No frozen held-out pack was opened or modified. No LocalMaxxing action
occurred. No model service or shared XPU/oneCCL runtime was built or replaced.
