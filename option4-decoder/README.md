# Option 4 decoder: Phase 0 substrate

This tree contains only the Phase 0 fixed-address command-graph and bitwise
parity substrate. It does not contain `M1AttentionBoundaryV1` or any later
decoder transaction.

The July 20 gate is **PARTIAL / Phase 1 NO-GO**. Mixed oneDNN+Triton capture is
bitwise exact and reduces two eager appends to one executable append, but the
installed SYCL replay path performs one `zeEventHostSynchronize` immediately
before that append. See the dated experiment note for the deciding traces.

The installed PyTorch XPU `XPUGraph` implementation is the native binding used
here. In this runtime it owns a
`sycl::ext::oneapi::experimental::command_graph`, records the current PyTorch
XPU stream, finalizes an executable graph, and replays it on that same stream.
The local `FixedAddressCommandGraph` wrapper adds the lifecycle, address/queue
identity checks, explicit warmup rule, and fail-closed parity qualification
needed by Option 4. PTI remains authoritative for whether one replay becomes
one Level Zero executable boundary.

The Phase 0 feasibility probe uses a real dependent M1 attention slice:

1. exact oneDNN W8A16 `wq_b`, BF16 `[1,1024]` by E4M3 `[1024,8192]`, with
   the incumbent `{128,128}` block-scale descriptor;
2. the resulting BF16 `[1,16,512]` Q tensor feeds the promoted fused Triton
   QNorm/RoPE/FP8-KV-insert kernel.

Run only on a verified free card. The July 20 qualification used logical XPU
device 3 while the protected EAGLE trainer remained on logical device 1.

```bash
export ZE_AFFINITY_MASK=3
export PYTHONPATH=/home/steve/src/deepseek-v4-vllm-native-submit-proof-20260719:\
/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=1

/home/steve/.venvs/deepseek-v4-xpu/bin/python \
  option4-decoder/tools/phase0_mixed_capture_probe.py \
  --mode graph --parity-cases 40 \
  --native-build-dir /path/to/isolated-native-build \
  --output /path/to/graph-probe.json
```

Set `CXX=/opt/intel/oneapi/compiler/2025.3/bin/icpx` when using the native
shim. It is compiled as a separate extension and never replaces the shared
`vllm_xpu_kernels` binary. XPUGraph remains the owner of the executable graph
and captured allocator pool; the shim appends that owned executable directly
with `current_queue.ext_oneapi_graph`. This separates PyTorch wrapper
bookkeeping from synchronization inherent to the installed SYCL graph replay;
PTI must still prove that the latter inserts no host synchronization.

Add `--nested` to prove surrounding-graph capture of the inner executable.
For the decisive trace, start unitrace paused and give the probe the matching
session name. Warmup, graph construction, changed-input preparation, and
output comparison stay outside the trace window; exactly one eager cluster or
one graph replay is collected.
