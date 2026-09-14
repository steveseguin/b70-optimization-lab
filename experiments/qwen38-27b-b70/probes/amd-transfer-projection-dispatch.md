# AMD transfer: heterogeneous GDN projection dispatch screen

Status: compiled and GPU tested September 14. All 12 tensor cases were exact,
but synchronized wall time was neutral at both tested row counts. The screen
failed its 3% admission gate; no larger sweep or endpoint integration followed.
See the [results](../notes/2026-09-14-amd-transfer-results.md).

The Radiance 1.0.16 RX3 report (source revision
`f295b9ef51ad413a68e4192371e0377741a354ce`,
`docs/MXFP4_RX3_CONTINUATION.md`) describes merging two same-format GDN
projections. This prototype borrows the goal of fewer dispatches; it does not
copy that implementation or merge its arithmetic. Our QKVZ weights remain
FP8 and BA weights remain FP16. The local community review owns source pins:
`community/1337hero-r9700-qwen38-radiance/`.

The native extension invokes the existing `_xpu_C::fp8_gemm_w8a16` dispatcher
entry and existing ATen `linear`, with the same 256-row BA prefill padding and
FP16 output types. It adds no device kernel, approximate head, collective,
quantization, cache or input reuse. Device GEMM launches are unchanged;
potential savings are host/Python dispatch overhead, so a large kernel speedup
is not expected.

Baseline sources inspected:

- R304 `model_executor/kernels/linear/scaled_mm/xpu.py`:
  original FP16 activation, transposed-view FP8 weight and contiguous scale.
- R304 `model_executor/layers/utils.py`:
  `xpu_fp16_linear_rowchunk`, CLASSPAD=0/ROWCHUNK=32.
- R304 `model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py`:
  `_deterministic_xpu_ba_prefill`, minimum 17 rows, 256-row blocks.
- `vllm-xpu-kernels` 6d92b1b `csrc/xpu/torch_bindings.cpp` and
  `onednn/onednn_matmul.cpp`: exact native operator schema/implementation.

Run only under the owning parent's GPU schedule. Never launch this beside a
serving workload simply because VRAM appears available. The probe does not
launch, stop or restart servers. Its default is one GPU, rows 1 and 2 only.
The enclosing controller owns kernel-fault checks and must halt on faults.

Dependencies: the qualified R304 Python environment with torch, vLLM and the
original native XPU libraries, a C++17 compiler, Ninja and torch C++ headers.
No internet/package installation is performed. Compiler artifacts and results
must go into a new experiment output directory. `MAX_JOBS=1` avoids an
unnecessary build burst. No SYCL code is compiled by this extension.

Example inside the prepared isolated environment (paths are placeholders):

```bash
MAX_JOBS=1 python /lab/experiments/qwen38-27b-b70/probes/amd-transfer-projection-dispatch.py \
  --compile-only --build-directory /evidence/projection-build \
  --output /evidence/projection.json
```

Compilation writes a receipt with source and compiled shared-object hashes,
runtime package versions and its loaded operator schema. Every started run
reserves its output exclusively; an existing receipt is never overwritten.
A failure after reservation, including an import or build failure, writes
`ABORTED` with the error and traceback. Missing or invalid command-line
arguments and failure to reserve the output are reported by the CLI; those
cannot write to an unreserved receipt.

After parent has verified ownership and health, choose a **different output
filename**, keep the same build directory, and remove `--compile-only` to run
the default rows 1, 2 screen. A passing exactness gate precedes all timing. It
uses the same original operations for the control, cached operator handles,
full byte comparisons for both outputs, random/zero/alternating-sign fixtures,
candidate repeats, independently recomputed control stability checks and alternating ABBA/BAAB timing blocks. Full input, weight and scale hashes and post-run immutability checks are retained. Both synchronized
wall time and host submission time are retained. Inputs are production-shaped
synthetic tensors, not captured model activations. Realistic final gate stays
false and no promotion is inferred from these operator timings.

Only if rows 1, 2 show meaningful repeatable wall-time savings, extend via
`--rows 1,2,8,16,17,32,128,256,512,2048`; this specifically tests the 17-row
route boundary and 256-row BA padding boundary. Further full-model integration
would require a fake implementation, actual captured tensors, unchanged
complete outputs, cache-zero varied workloads and long-context gates. Eager
operator speed does not predict compiled endpoint speed: the current model's
compiled call pattern can remove part of the Python overhead measured here.

Risks to inspect before runtime integration: C++ typed dispatcher ABI matching
the installed torch schema, altered temporary lifetimes, runtime BA policy
changes, graph/fake registration and actual production stride coverage.
