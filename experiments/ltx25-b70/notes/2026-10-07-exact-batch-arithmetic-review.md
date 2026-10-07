# Exact batch arithmetic: localization before a kernel change

CPU/source-only audit, 2026-10-07. No model weights, tensors, devices, server,
build, or source materialization were used. Accepted batch-one w93c bytes remain
the gate. Existing batch-two and batch-four results remain output-changing and
are not authorized replacements.

The worthwhile next step is a small first-divergence diagnostic, not a custom
GEMM implementation. There is one concrete low-cost candidate if the diagnostic
supports it: preserve batch-one execution for the small timestep/AdaLN projections
while leaving the expensive transformer batched. A second, less certain candidate
is a batch-preserving oneDNN matmul for a selected **bias-free** linear. Neither
has evidence of matching the accepted output or improving throughput yet.

## What the existing evidence actually localizes

[Packet96 results](2026-10-04-packet-96-results.md) prove fixed-B2 row/slot/partner
independence for full clips; they also show a substantial mismatch against w93c
(17–29 dB picture PSNR). The saved
[data/batch-row-independence/batch-row-independence-02-all.json](../data/batch-row-independence/batch-row-independence-02-all.json)
compares outputs of the first16 real blocks across all11 forwards. Its record
keys contain no per-operator outputs, first-mismatch boundary, GEMM implementation
identifier, or kernel trace. `scripts/probe-batch-row-independence.py:425–480`
compares whole executor outputs; lines535–568 return the original B1 result.

Thus the historical note's statement that GEMM rounding is the known cause is
stronger than this measurement. M-dependent native arithmetic is a credible
hypothesis, but these records do not distinguish input/timestep projection,
attention, reduction, or later linear divergence. The batch-two upsampler probe
matched B1 on its seeded input, narrowing the initial search to the transformer;
it is not a universal upsampler equality proof.

The old roofline note's isolated timing subtraction is also explicitly an
estimate. It cannot tell us what fraction of the current B2 gain survives one
particular operator change. The faster output-changing B2 runs establish useful
motivation, not an exact-throughput prediction.

## First candidate: retain B1 arithmetic in small timestep projections

In packet96 `comfy/ldm/lightricks/model.py:999–1027`, input projection runs first,
then timestep/context preparation, then all transformer blocks. In
`av_model.py:739–857`, `_prepare_timestep` flattens video frame/token timesteps
and audio timesteps into projections. Batch doubling changes these small GEMM
row counts even though the lockstep protocol requires equal sigmas. Their outputs
are subsequently used throughout the blocks. A small upstream rounding change
could therefore contaminate every later comparison.

Test the actual projected inputs and outputs here before selecting a large FF or
attention kernel. If these are the only problematic sites, run the original
small modules independently per clip at their original B1 shape, preserving the
complete native bias/activation/cast sequence. This costs extra small calls but
leaves the large batched operators available. Do not collapse arbitrary timesteps
by value: masks, reference audio, per-frame timesteps and compressed-timestep
metadata must remain part of the exact contract. The simplest first control uses
independent B1 calls; any identical-row sharing would require a later explicit
structural proof, not a cache keyed by sigma or prompt.

This is a hypothesis, not evidence that the timestep modules are the cause.
Other projections may differ even after these outputs match.

## Second candidate: keep per-clip M through a broadcast-weight bmm

The installed Torch reports source commit
`08187d9e0fba026dc8217405802ab5381dc88d90`. Its
[Linear.cpp:50–132](https://github.com/pytorch/pytorch/blob/08187d9e0fba026dc8217405802ab5381dc88d90/aten/src/ATen/native/Linear.cpp#L50)
flattens leading dimensions for the common fused-bias path, or delegates to
matmul. Flattening B and tokens changes GEMM M. The XPU
[Blas.cpp:317–336](https://github.com/pytorch/pytorch/blob/08187d9e0fba026dc8217405802ab5381dc88d90/aten/src/ATen/native/mkldnn/xpu/Blas.cpp#L317)
passes bmm to oneDNN. Its
[Utils.cpp:269–312](https://github.com/pytorch/pytorch/blob/08187d9e0fba026dc8217405802ab5381dc88d90/aten/src/ATen/native/mkldnn/xpu/detail/Utils.cpp#L269)
recognizes a zero-stride broadcast weight batch and reduces it to a single weight
batch before dispatch, avoiding an obligatory duplicated weight tensor.

For one measured divergent **bias-free** projection, a bounded candidate is
`bmm(x[B,M,K], W.T.unsqueeze(0).expand(B,K,N))`, with a materialized contiguous
input batch so both operands are not broadcast. The oneDNN descriptor retains M
and a separate batch dimension. Start with video FF up (`ff.net[0].proj`,
W16384×4096, M64/256), only if localization implicates it. Preserve native
weight/cast context, original output dtype, GELU/down projection and residual.

This is not an algorithm pin. The pinned
[Matmul.cpp:43–46,144–216](https://github.com/pytorch/pytorch/blob/08187d9e0fba026dc8217405802ab5381dc88d90/aten/src/ATen/native/mkldnn/xpu/detail/Matmul.cpp#L43)
creates a shape-dependent primitive and sets determinism when requested; it does
not expose a B1 kernel/reduction-order selector in this call path. A 3D batch can
still select a different kernel. Equal implementation labels would not prove
identical tiling or reduction order. A shared weight descriptor also does not
prove one physical weight read: separate batch tiles may reload it. No promised
speedup is justified. Splitting every linear into B1 calls trivially discards
much of the intended batching benefit and is not the proposed optimization.

## Small decisive diagnostic, after current control

1. Use a separately identity-bound observer on the refreshed accepted-control
   source, not packet96 as a runtime. Observe one first-stage and one second-stage
   native B1 forward, return their original results unchanged. Compare repeated
   B1 A and the two rows of a materialized `(A,A)` B2 diagnostic. Pin all effective
   inputs, casts, masks, schedules and module identities; do not alter arithmetic
   or count this duplicate-input diagnostic as useful generated output.
2. Compare bytewise boundaries after input projection, every returned timestep
   component (including compressed representations), context preparation, then
   first-block projections/norms/attention/residuals. Compare original operands
   before blaming an operator. Preserve only first-mismatch operands/outputs plus
   shapes, strides, dtypes and source identities; impose a32MiB diagnostic artifact
   cap. No weights need export. Stop localization at the first discrepancy; if
   the first block is equal, report insufficient localization rather than add an
   unbounded full-model trace.
3. Only at that isolated mismatch test the applicable candidate above against
   the *observed* original native operation, including a same-operation repeat.
   For a biasful operator, do not substitute bmm-plus-add: that can move bias
   rounding out of the native epilogue. For attention, use B1 slices as a diagnostic
   control only; do not switch SDPA algorithms globally or claim exactness from
   mathematical equivalence.
4. Stop on any mismatch/fault. If the isolated gate passes, later whole-block and
   all11-step raw-output equality remain mandatory before timing. A result must
   also show retained batching benefit under matched execution, not merely an
   equal operator. No new GPU diagnostic was authorized or run by this audit.

No generic QKV fusion, new precision, transport work, or custom GEMM rewrite is
recommended from this evidence. Keep the planned20/28 B1 placement experiment
as the next straightforward throughput test.

## Source identities read

Packet96 source root:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-batch-96/source`.

- `comfy/ldm/lightricks/av_model.py`: `e880b29b1d6e2cefe807c53c26cf4733d90aaae13126d8652f5989de15d1f213`
- `comfy/ldm/lightricks/model.py`: `f0292be2a39491d411ad3cf4b58cebd87e62bf2568aafa35814b954828733718`
- `comfy/ops.py`: `6058f688d936b083c49fa49a57964837476db6d95750ea70198ad60e884ffed0`

Pinned PyTorch sources above were read from the official repository at the
installed version's exact commit; no local Torch code was imported or changed.
