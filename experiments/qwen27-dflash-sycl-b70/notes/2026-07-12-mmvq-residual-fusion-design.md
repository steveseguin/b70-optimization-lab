# MMVQ output plus residual fusion design

Date: 2026-07-12

Status: implementation-ready design; no source patch yet because the required
graph-loop integration overlaps the active persistent-replay change in
`ggml-sycl.cpp`.

## Exact target

The target GGUF metadata and tensor table establish:

- architecture `qwen35`;
- 65 blocks, of which 64 are the target decoder and one is NextN/MTP;
- hidden width 5120 and FFN width 17408;
- full attention every four layers: 16 full-attention and 48 recurrent layers;
- 64 target `ffn_down` outputs: 56 Q4_0 and 8 Q4_1;
- 16 target `attn_output` outputs: Q4_0;
- 48 target `ssm_out` outputs: Q5_K.

Every target layer has two projection-to-residual boundaries, so the target
decode graph has 128 candidate pairs per pass:

1. attention or recurrent output projection followed by `attn_residual`;
2. FFN down projection followed by `post_ffn`.

All three weight types are handled by the current MMVQ path. Q4_0 and Q5_K
also have reordered MMVQ kernels; Q4_1 uses the non-reordered kernel.

For M=1, a 5120-element FP32 residual is 20 KiB. The unfused pair writes the
20 KiB MMVQ result, then ADD reads that result and the 20 KiB residual and
writes 20 KiB. The fused epilogue reads the residual and writes the final
result. Across 128 pairs it removes:

- 128 kernel submissions;
- 5 MiB of device traffic per target pass (one intermediate write and read);
- the lifetime of 128 intermediate projection-output allocations.

The launch reduction alone reaches the 0.4 ms whole-pass gate at 3.125 us per
submission. The bytes are secondary on B70, but improve the case. This must be
confirmed with a queue timeline rather than assumed.

## Eligibility checks

The SYCL graph loop may fuse nodes `mm` and `add` only when all checks pass:

- `mm->op == GGML_OP_MUL_MAT` and `add->op == GGML_OP_ADD`;
- `add` is the next compute node after `mm`; view/reshape/transpose/permute
  metadata nodes may occur between them only if they do not consume or alias
  `mm`;
- exactly one ADD source is `mm`; the other is `residual`;
- `ggml_node_get_use_count(cgraph, mm_index) == 1`;
- `mm`, `add`, and `residual` are F32, contiguous, on the same SYCL device;
- `mm->ne[]`, `add->ne[]`, and `residual->ne[]` match exactly; no broadcasting;
- no tensor is a split buffer and the matmul selects MMVQ, not DMMV, MMQ,
  oneMKL, or a split-device path;
- weight type is in the MMVQ epilogue allowlist initially limited to Q4_0,
  Q4_1, and Q5_K;
- `src1_ncols` is within the existing kernel's supported width and output and
  residual column strides match;
- `add->data` does not overlap either weight or quantized activation storage;
- in-place `add->data == residual->data` is allowed because each output element
  reads its residual before the subgroup leader overwrites that same element;
- any other overlap between destination, residual, `mm`, weight, or activation
  buffers rejects fusion;
- both nodes have `GGML_TENSOR_FLAG_COMPUTE` set.

Start behind `GGML_SYCL_FUSE_MMVQ_ADD=1`, default off until the strict suite
passes. Log eligible, fused, and rejected-by-reason counters at powers of two.

## Kernel API

Do not add a second copy of every MMVQ kernel. Extend the internal MMVQ launch
templates with an optional epilogue descriptor:

```cpp
struct mmvq_add_epilogue {
    const float * residual;
    int64_t       residual_col_stride;
};
```

The public internal entry point should accept `const mmvq_add_epilogue *`, with
`nullptr` retaining byte-for-byte current behavior. The graph integration
passes the ADD output as `dst_dd_i` and the other ADD source as `residual`.

At the existing subgroup-leader store, change only the final expression:

```cpp
dst[col * dst_stride + row] = sum + residual[col * residual_stride + row];
```

The same optional epilogue must be threaded through:

- scalar-column non-reordered MMVQ;
- multi-column non-reordered MMVQ;
- scalar-column reordered MMVQ;
- multi-column reordered MMVQ.

Instantiate ADD epilogues initially only for Q4_0, Q4_1, and Q5_K to cover the
exact model without multiplying compile cost across unused quant types. Keep
the existing non-ADD instantiations for every type.

The residual pointer must be adjusted by `row_low` in the same place as the
destination pointer. For multi-column verification it must also use the ADD
tensor's physical column stride, not assume tightly packed columns. The
projection's intermediate destination is never passed to the kernel.

## Graph execution

In the non-graph and graph-recording execution loop:

1. inspect the current compute node and locate the next compute node;
2. apply the eligibility checks above;
3. call a `ggml_sycl_mul_mat_add()` wrapper using the MUL_MAT inputs, ADD
   residual, and ADD destination;
4. advance the loop over the consumed ADD node;
5. leave metadata-only nodes untouched;
6. fall back to the two original dispatches on any rejection.

Skipping must be local to execution; do not mutate the persistent ggml graph,
node flags, tensor sources, or allocator plan. This preserves tensor ownership
and makes replay keys independent of whether fusion is enabled. A captured
command graph will then contain the fused MMVQ submission and no ADD
submission.

## Tensor lifetime and correctness

The allocator may still reserve the intermediate `mm` tensor because this
first patch does not rewrite graph allocation. That is acceptable: the speed
win comes from not writing or reading it. Allocation-lifetime removal is a
separate graph-planner optimization.

The ADD destination remains the authoritative value consumed by the following
RMSNorm and retained for the FFN residual. In-place residual output is safe
only under the exact-element mapping check. No fusion is allowed when the
intermediate has callbacks, exports, multiple users, or a backend boundary.

Numerical order changes only from `store(sum); load(sum); sum + residual` to
`sum + residual; store`. Both use the same FP32 reduced `sum`; expected output
is bit-identical for finite values, but tests must compare explicitly.

## Required tests

Extend `tests/test-backend-ops.cpp` with a guarded MUL_MAT+ADD graph case for:

- Q4_0 reordered and non-reordered, M=1, 4, 8, and 17;
- Q4_1 non-reordered, M=1, 4, and 8;
- Q5_K reordered and non-reordered, M=1, 4, and 8;
- destination distinct from residual and destination aliasing residual;
- odd output-row counts and the real 5120-row output;
- residual in ADD source slot 0 and slot 1;
- rejection cases: broadcast residual, non-contiguous residual, second user of
  MMVQ output, mismatched strides, split buffer, and unsupported weight type.

Compare fusion off versus on, require the same values within the existing
quantized matmul tolerance, and separately check exact equality of the ADD
epilogue given an identical captured MMVQ sum.

After backend tests, run the existing 34-case Q4_0 width suite, then MTP3
correctness and the fixed realistic strict suite. Promotion requires:

- no output/correctness regression;
- counters proving 128 fused pairs per target M=1 pass (plus two for each MTP
  pass when applicable);
- timeline proving 128 fewer submissions;
- at least 0.4 ms target-pass reduction or at least 3% end-to-end MTP3 gain.

If it misses both gates, retain the result as a negative experiment and move
to the larger residual+RMSNorm+Q8_1 boundary.
