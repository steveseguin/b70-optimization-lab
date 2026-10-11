# Independent rule (ii) arithmetic review

Reviewed on 2026-10-11 by a separate agent that did not write the GEMV batch
implementation. The reviewer also implemented CPU dependency instrumentation
and the two-submission host split4 control; those are not independently
reviewed by this document. This is source review, not a device gate or a speed
claim. No device binary was executed.

## Bound sources

- `gemv_batch.hpp`: SHA256 `4b963550897488c6c4edf41925000814282e7bfde6f35210ad036217b7b5bbf6`.
- `gemv_batch.cpp`: SHA256 `500bceed93571cc1e2604ec9f26dcc4b3e14552815f2c0249957897f4d6391bc`.
- `gemv_fixture.cpp`: SHA256 `5b82e9aca2069a4c5bbb2c6209d00314b8690aa644f043f7e735d851fa3a640b`.

Authorities read directly: packet18 `arithmetic.hpp`, `core_v2.hpp`, and
`performance.cpp`; packet6 `reference.hpp`; packet7 `reference.hpp`; packet8
`decode.hpp`, `reference.hpp`, and device kernels; packet9 `reference.hpp` and
`dispatch.hpp`; packet10 `expanded.hpp` and device kernels. The implementation
was reviewed against these bodies, not against its author's conclusions.

## Per-matrix arithmetic

Every output row has a work-group-uniform descriptor, including its own weight
format, row bytes, column count, and reduction variant. The descriptor selection
has at most seven range comparisons for eight siblings; this is scalar indexing
work and does not change the arithmetic. Each subgroup is confined to one row
and one format, so quantization metadata broadcasts remain uniform.

| Matrix class | Required dequantization retained |
| --- | --- |
| F32/F16/BF16 | Original scalar element conversion, then BF16 input conversion |
| Q8_0 | Half scale multiplied by signed eight-bit code |
| Q6_K | Half scale multiplied by signed subscale, then signed six-bit code |
| Q3_K | Half scale multiplied by subscale minus 32, then signed three-bit code |
| IQ4_NL | Half scale multiplied by the original nonlinear table value |
| IQ2_S | `(d * (0.5 + subscale)) * 0.25`, then original grid/sign handling |
| IQ3_S | `d * (1 + 2 * subscale)`, then original grid/sign handling |
| IQ3_XXS | `(d * (0.5 + subscale)) * 0.5`, then original grid/sign handling |

Variant0's device use of `kopt2::lane` on the full interval is equivalent to
packet6's `lane_dot` with subgroup 32: both start at `lane*8`, advance by 256,
call the same `decode8<T>`, use the same tail element conversion, and separately
multiply and add the eight values in the same order. Variant1 uses the original
packet7 lane function with contiguous tile bounds. Variants2/4 use the original
packet8 dot function, tables and subgroup-sharing equations, including the
exceptional-scale fallback and IQ NaN handling. Variants6/7 use the unchanged
expanded-value lane function and expanded row-byte layout.

The subgroup reduction combines adjacent lanes at widths 1, 2, 4, 8, 16.
Split4 uses the original contiguous 256-column tile partitions and final tree
`(p0+p1)+(p2+p3)`. Empty partitions start at positive zero. Four subgroup
partials are stored before the local-memory barrier; each work-item reaches
that barrier. Every row result is converted to BF16 before any epilogue.
Neither mixed quantization formats nor row-range boundaries change these trees.

## Prologues and epilogues

- SiLU/4 reads the BF16 GEMV output, divides by four, applies v2 deterministic
  sigmoid/SiLU, and rounds to BF16.
- HC mix accumulates streams 0 through 3 sequentially, divides by four, and
  rounds to BF16. It does not replace that accumulation with a tree.
- Paired gate/up retains each separate BF16 output before `SiLU(gate)*up` and
  its BF16 store.
- HC residual retains the BF16 GEMV output and computes
  `old + output*(2*sigmoid(inject/4))` before the residual BF16 store.
- Generic residual operand order was flagged during review and corrected to
  `old + BF16(dot)`, preserving the reference order even for exceptional values.
- Route finishing uses the adjacent selected-probability tree, including adding
  positive zero at odd levels, followed by the original per-slot division.
  Its separate work-group is valid because no projection row reads probabilities.

The final host-only optimization prepares each transformed input once per
**current descriptor and submission**, then uses those BF16 bytes for its rows.
The vector is local to `Batch::run` and cannot survive into another operation or
token. The same pure `transformed` function computes each column. Whole-bundle
writable-alias rejection prevents any output or sibling from changing those
source bytes. The materialized-input contract permits only one input per token
(shared routed input or count one), so its contiguous host copy matches the
device's token-wise stores. This hoist is arithmetically equivalent to the
device's repeated per-row evaluation and is not prompt/KV/response reuse.

## Aliasing and guards checked

The complete batch rejects writable allocation aliases against all sibling
weights, inputs, auxiliaries and outputs. HC residual explicitly permits its
single combined read/write stream binding with `input_rows=1` and `count=1`;
each output row owns exactly its four distinct stream coordinates. Any sibling
read of those streams still appears separately and is rejected by the batch
alias check. A separate agent owns the full alias review.

Paired descriptors now validate their own nonzero format layout, column-block
alignment, full-row span, and route/status pairing before computing row bytes.
This closes malformed-peer division-by-zero and geometry paths without changing
valid arithmetic.

Routed descriptors are checked with the original `valid_route` before weight
addressing. Invalid routes substitute canonical NaN output and set their status;
paired projections retain separate status outputs. These status values are
consumed by the runtime's sticky-error checks. The standalone GEMV kernel does
not itself own the runtime sticky-error allocation, so complete fault-path
behavior remains an integration-gate responsibility. Descriptor tables stay
read-only and device-resident during a submission.

## Fixture review and limits

`gemv_fixture.cpp` checks ten matrix classes with variants 0, 1, 2, 4, 6 and 7,
M=1/3/87, K=512/1280/2560, odd sibling row counts 3 and 5, and both
sides of every row-range boundary. K=512 includes empty split4 partitions;
K=1280 and K=2560 exercise four nonempty contiguous partitions with unequal
lengths. The loop contributes 540 matrix-output checks; nine nonlinear-output
checks, one HC residual check, and three routing/probability checks bring the
recorded total to 553. Additional materialized-input and alias assertions are
not counted as separate output checks. Additional fixtures cover mixed-variant paired projections, each
implemented nonlinear prologue, materialized BF16 inputs, coordinate-local HC
residual, a valid and invalid routed expert, distinct routed statuses,
probability finishing, and rejection of a sibling-input/output alias.

The device path first launches the original unfused dense/routed kernels on the
same owner and checks their output against host bytes. Independently transcribed
standalone elementwise submissions check the prologue, activation, HC residual
and probability boundaries. The fused outputs then compare against those same
host bytes. This establishes transitive fused/unfused/host comparisons if K1
passes; source inspection is not a substitute for running K1 after authorization.
The fixture now embeds the actual `Device::shutdown` receipt in its teardown
array after checking `safe_to_exit`; it does not synthesize a teardown record.
The output-byte hash and maximum observed submission duration are retained.
Final fixture-only adjustments assign unique monotonic owner-allocation labels
and explicitly report `sequential_owners=1` for this single-owner executable.
These changes affect allocation bookkeeping and receipt metadata, not the
fused/unfused equations or runtime sources. Two fresh-owner K1 repeats remain
the window runner's responsibility.

Limitations retained for the final report:

- Fixture coverage now includes four nonempty split4 partitions. Full production
  row counts and every production K still depend on the full-model oracle gates
  and eventual device windows.
- Fixtures include finite extremes: quantized half scales span subnormal,
  smallest normal, positive/negative maximum finite and negative zero; F32/BF16
  raw weights include very small and large finite values. Exceptional NaN/Inf
  scale handling is retained by direct reuse/source proof, but this fixture
  file does not independently exercise every NaN payload or infinity encoding.
- Generic scale and generic residual helpers are not separately exercised by
  this fixture file; the integrated HC residual is exercised.
- No source review or host oracle pass certifies device compilation, queue
  behavior, actual per-submission duration, or speed. Those remain sealed-window
  gates. Per-row prologue recomputation and one work-group per row can increase
  arithmetic/resource cost despite fewer launches.

No unresolved arithmetic identity defect was found in the bound implementation.
Acceptance still requires the recorded full CPU gates and the deferred device
exactness windows; neither was claimed by this review.
