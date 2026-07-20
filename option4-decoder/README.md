# Option 4 decoder: Phase 0/0b substrate

This tree contains only the Phase 0 fixed-address command-graph, raw Level Zero
replay, and bitwise
parity substrate. It does not contain `M1AttentionBoundaryV1` or any later
decoder transaction.

The July 20 Phase 0b gate is **GO / Phase 1 unblocked**. Mixed oneDNN+Triton
capture remains bitwise exact, and raw replay of the finalized regular Level
Zero list on PyTorch's owned in-order immediate list produces one executable
append and zero host synchronization. The earlier SYCL replay path remains a
preserved negative: it performs one `zeEventHostSynchronize` before the same
append. See the
[Phase 0](../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-option4-phase0-mixed-command-graph-feasibility.md)
and
[Phase 0b](../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-option4-phase0b-raw-level-zero-replay.md)
notes for the deciding traces.

The installed PyTorch XPU `XPUGraph` implementation is the native binding used
here. In this runtime it owns a
`sycl::ext::oneapi::experimental::command_graph`, records the current PyTorch
XPU stream, finalizes an executable graph, and replays it on that same stream.
The local `FixedAddressCommandGraph` wrapper adds the lifecycle, address/queue
identity checks, explicit warmup rule, and fail-closed parity qualification
needed by Option 4. The raw bridge uses one sacrificial, build-time SYCL replay
under an in-process Level Zero callback to borrow the finalized regular-list
handle. Measured replay then calls
`zeCommandListImmediateAppendCommandListsExp` directly. The XPUGraph stays
alive as owner of the list, kernel modules, oneDNN scratchpad, and allocator
pool. PTI remains authoritative for boundary and host-sync counts.

The Phase 0 feasibility probe uses a real dependent M1 attention slice:

1. exact oneDNN W8A16 `wq_b`, BF16 `[1,1024]` by E4M3 `[1024,8192]`, with
   the incumbent `{128,128}` block-scale descriptor;
2. the resulting BF16 `[1,16,512]` Q tensor feeds the promoted fused Triton
   QNorm/RoPE/FP8-KV-insert kernel.

Run only on a verified free card. Phase 0 used logical XPU 3. Phase 0b used
logical XPU 2, PCI `0000:43:00.0`, renderD128, while the protected EAGLE
trainer remained on logical XPU 1, PCI `0000:27:00.0`, renderD131.

```bash
export ZE_AFFINITY_MASK=2
export ZE_ENABLE_TRACING_LAYER=1
export PYTHONPATH=/home/steve/src/deepseek-v4-vllm-native-submit-proof-20260719:\
/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=1

/home/steve/.venvs/deepseek-v4-xpu/bin/python \
  option4-decoder/tools/phase0_mixed_capture_probe.py \
  --mode raw-lz --parity-cases 40 \
  --native-build-dir /path/to/isolated-native-build \
  --output /path/to/raw-lz-probe.json
```

Set `CXX=/opt/intel/oneapi/compiler/2025.3/bin/icpx` when using the native
shim. It is compiled as a separate extension and never replaces the shared
`vllm_xpu_kernels` binary. `ZE_ENABLE_TRACING_LAYER=1` is needed only so the
one-time handle harvest can observe the ordinary SYCL append. The raw replay
path requires the current queue to remain the same in-order Level Zero
immediate list, checks all fixed tensor identities before every replay, and
does not destroy either borrowed handle.

`--mode graph` preserves the Phase 0 SYCL-wrapper control, and `--nested`
preserves its surrounding-graph negative. For the decisive raw trace, start
unitrace paused and give the probe the matching session name. Warmup, graph
construction, the sacrificial handle harvest, changed-input parity, and output
comparison stay outside the trace window; exactly one raw replay is collected.
