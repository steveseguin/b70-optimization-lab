# Xe2 M=6 Q5_K GDN-output compile handoff

Date: 2026-07-13

Status: compile-validated only; no GPU comparator or runtime integration run

The Qwen lane closed after the isolated implementation compiled and before the
required real `6 x 6144` fixture was available. This note deliberately makes
no correctness or speed claim.

## Target and control

The target is the 48 recurrent-layer `ssm_out` projections:

```text
Q5_K weights: 6144 -> 5120
verification width: M=6
blk.0.ssm_out.weight absolute GGUF offset: 1,963,459,456
blk.0 source bytes: 21,626,880
```

The comparator uses the exported production entry point
`ggml_sycl_op_mul_mat_vec_q`, a runtime-format reordered Q5_K pack, and the
ordinary production-compatible reordered Q8_1 activation. It does not compare
against Q4_0 or a scalar/dequantized surrogate.

## Implemented offline ABI

The candidate is a true Q5_K expansion for signed-S8 x signed-S8 Xe2 DPAS:

| Component | Per-layer bytes |
|---|---:|
| Expanded uint5 values in signed-S8 VNNI order | 31,457,280 |
| Exact 6-bit scale/min pairs, one pair per K32/output | 1,966,080 |
| Raw fp16 `d,dmin`, one pair per K256/output | 491,520 |
| Total | 33,914,880 |

The pack is `32.344 MiB/layer`; all 48 layers require `1.516113 GiB`. The
module layout ID is `Q27_XE2_LAYOUT_Q5K_GDN_OUT_M6_V1`. Launch validation
requires the exact shape, bytes, model content tag, and
`Q27_XE2_PACK_GDN_OUTPUT` role before any queue submission. An invalid layout
must return `Q27_XE2_BAD_LAYOUT`, making ordinary fallback safe.

The Q8 workspace is 46,080 bytes: six K6144 signed-S8 rows plus one `{fp32 d,
int32 qsum}` record per K32 block and row. Half rounding for `d` is made
observable through volatile half bits because BMG AOT previously proved that
it can remove a local `float(sycl::half(value))` round trip.

The DPAS kernel assigns complete K256 superblocks to an eight-way split. Each
superblock accumulates its eight K32 scale/min groups before applying the raw
half `d,dmin`, preserving the important Q5_K arithmetic boundary. The first
candidate intentionally has no residual epilogue. That epilogue may be added
only after the projection itself clears the speed and numerical gates.

## Roofline and memory priority

The serialized real operation census measured GDN output at `7.297 ms / 48`,
or `152.021 us/layer`. This is a work-ranking trace, not production wall time.

For the 33,914,880-byte candidate pack:

- 608 GB/s gives a `55.781 us` bandwidth floor, `2.725x` optimistic ceiling,
  and `4.620 ms/48` projected saving;
- 545 GB/s gives a `62.229 us` floor, `2.443x` ceiling, and `4.310 ms/48`
  projected saving;
- the optimistic value density is `2.843-3.047 projected ms/GiB`.

This justified implementing the comparator. It does not establish the win;
DPAS instruction utilization, scale/min work, activation quantization, and
production queue overlap can reduce it substantially.

Current production headroom after full187 plus Q6 is about `3.84 GiB`. An
all-48 Q5 pack leaves roughly `2.32 GiB`, barely preserving the required 2 GiB
reserve. It cannot coexist with the approximately `2.20 GiB` all-layer QKVZAB
pack while preserving that reserve. If validated, Q5 should be packed by
per-layer limits and prioritized by measured ms/GiB; do not assume all pack
families coexist.

## Compile-only validation

The `bmg-g31` AOT module and comparator both compiled with oneAPI 2026.0:

```text
q27_xe2_module: build succeeded
q27_q5k_gdn_out_module_compare: build succeeded
```

No GPU execution occurred after this implementation. In particular, the
following remain unvalidated:

- Q5 unpack/VNNI byte correctness against the real block;
- signed-S8 DPAS operand order;
- output numerical error against the integrated symbol and captured oracle;
- invalid-layout no-submit behavior on device;
- kernel speed, cycle projection, and memory allocation behavior.

## Required fixture and reopening gate

The existing DFlash fixture is `6 x 5120` and is not the input to
`ssm_out`. Reopening requires a real integrated artifact containing:

- row-major `input.f32`, exactly `6 x 6144`;
- ordinary pre-add `projection.f32`, exactly `6 x 5120`;
- `residual.f32` and ordinary post-add `add.f32`, each `6 x 5120`;
- manifest identity: layer, tensor name/type/dims, absolute GGUF offset/bytes,
  model fingerprint, runtime/build/env identity, strides, and file hashes.

The requested external convention is:

```text
/mnt/fast-ai/bench-results/qwen27-q5k-gdn-out-m6/capture-v1/
  manifest.json
  input.f32
  projection.f32
  residual.f32
  add.f32
```

Run the comparator with an explicitly idle B70:

```bash
ZE_AFFINITY_MASK=<idle> ./run-q5k-gdn-out-comparator.sh
```

Continue only if all of these hold:

1. the integrated control matches the captured ordinary projection within the
   established Q5_K/Q8 tolerance;
2. the candidate has tight numerical agreement with both control and capture;
3. invalid layout returns `Q27_XE2_BAD_LAYOUT` before submission;
4. candidate projection speed is at least `1.5x` the integrated production
   control;
5. measured saving projects to at least `2 ms` over 48 layers, with pack
   footprint and a 2 GiB reserve included in the decision.

Only after those gates pass should an output+residual epilogue be added and
measured. Protected `ggml-sycl` runtime files were not changed by this lane.
