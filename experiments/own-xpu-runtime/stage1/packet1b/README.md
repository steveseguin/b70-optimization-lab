# Packet 1b — CPU arithmetic and loader preparation

CPU preparation only, 2026-10-10. This packet freezes an independently written
reference and synthetic tests for packet 4. **It does not establish certified
XPU arithmetic parity, qualify a model, or advance packets 2/3.** No weights,
GPU operations, servers, systemd calls, port access, device-node access, native
builds, or changes to existing environments were needed. Temporary synthetic
files use automatically removed directories; no scratch is part of the packet.

The [initial test receipt](test-receipt.json) preserves the first swish reference.
The [gate-corrected receipt](test-receipt-gate-correction.json) binds the current
sigmoid reference after [official-source review](../packet3-prep/gate-evidence.json).
The current receipt binds the tests, source files, schema,
format data, documentation and packet 1 contract by SHA256. All tests run at
nice 19 with `OMP_NUM_THREADS=2`, two torch CPU threads and one interop thread.
The existing torch distribution has an `+xpu` build suffix; only CPU tensors
and CPU operations are used. The tests never query or initialize a device.

## What is frozen

- [reference/math.py](reference/math.py): E4M3 block dequantization with **BF16
  stored scales**, W8A16 and excluded-BF16 linear operators, unit-offset and
  ordinary RMSNorm, FP32 residual carry, convolution, gates, GDN serial
  recurrence, full attention with Q/K norm and text RoPE, FP16 KV, SiLU FFN,
  final norm/full target head, stable argmax and native MTP forward. Functions
  specify the arithmetic sequence and casts. No external runtime is imported.
- [loaders/headers.py](loaders/headers.py): bounded safetensors shard/header
  validation against the [packet 1 contract](../packet1/tensor-contract.json),
  and GGUF v3 little-endian metadata/tensor-info parsing. Header readers never
  read tensor payloads. Shape, dtype, extent, alignment, duplicate, overlap,
  scale pairing and shard-coverage checks fail closed.
- [loaders/dequant.py](loaders/dequant.py): independently written scalar CPU
  decoders for IQ3_XXS, Q3_K, IQ4_XS, Q4_K, Q5_K, Q6_K, Q8_0, F16 and BF16.
  [Format notes](loaders/FORMAT.md) give block sizes, equations, limitations,
  official specification links and the exact provenance/license of IQ data.
- [tests](tests/): synthetic representable-value round trips, known-value
  arithmetic, malformed headers, payload-read guards, all 66 retained packet 1
  headers / 1,606 tensors, hidden-5120 GDN and attention decoder layers, native
  MTP's contract-sized merge/block, causal row checks, and bit-identical CPU
  repeats. Production-shaped weights are nonzero expanded synthetic views;
  the ordinary arithmetic runs, without allocating a full checkpoint. The MTP
  head test uses seven synthetic vocabulary rows; a separate 248,320-logit
  fixture tests full-vocabulary tie selection. No full 27B model was executed.
- [fixture-extraction.schema.json](tests/fixture-extraction.schema.json): the
  future comparator fixture envelope, validated with JSON Schema 2020-12.
  There are **no extracted comparator tensors** in this packet. Synthetic
  schema examples are generated only in memory and cannot be mistaken for
  real quality evidence.

Reference tensors use FP16 activations/KV, FP32 recurrent state and residual
carry, and the contract's BF16 stored weights/scales. FP8 is decoded as E4M3FN.
`weight_scale_inv` is treated as a multiplier, consistent with the inspected
oneDNN scale attribute, not inverted because of its suffix. Source-level scale
semantics are stronger evidence than naming; actual fused numerical behavior
still needs the U1 fixture.

The stable greedy rule is **first/lowest token index on an exact tie**. Signed
zeros tie. Infinities are supported; NaN logits and an empty vocabulary are
rejected. This rule is frozen for our CPU reference, with comparator tie
behavior still U6. The target head receives all target vocabulary weights;
there is no shortlist, quantized activation, compressed KV, or MTP acceptance
shortcut. MTP proposes only; transaction/rollback and target acceptance remain
later packets. Vision and multimodal positions remain outside Stage 1 text
scope. GGUF support does not amend packet 1's official FP8 target identity.

## Source-derived order

[Source evidence](source-evidence.json) records the exact inspected commits,
paths and blob hashes. Source reads were from existing local trees, with no
execution of their model code. Local paths are provenance, not dependencies
needed to run this packet.

| Key | Evidence and what it establishes |
| --- | --- |
| S1 | [Rebuilt Flash-Next extension](../../../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md), head `bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26`; `csrc/xpu/gdn_attn/gated_delta_rule.hpp`, `causal_conv1d.hpp`, `spec_decode.hpp`. The [A361–A363 note](../../../qwen38-flash-next-fp8-b70/notes/2026-09-12-a361-a363-the-extension-exact-serial-mode-removes-the-tax.md) binds serial row execution; the [27B R311 patch](../../../qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch) and [checkpoint note](../../../qwen38-27b-b70/notes/2026-09-17-gdn-single-checkpoint-plan.md) establish accepted-row replay/commit. |
| S2 | Kernel tree `e421889999bc1e5a5f11044d14548b9afdba644d`, `csrc/xpu/onednn/fp8_gemm_w8a16.h`: F16 activation / E4M3 weight dispatch, two-axis block scales and their supplied dtype passed to oneDNN. It does not disclose internal oneDNN reduction/cast geometry. |
| S3 | Local vLLM tree `44fc8fde09fc311d3099dab10366b672d9142ea4`, `vllm/model_executor/layers/layernorm.py`, `GemmaRMSNorm.forward_native`: gain `1+w`, FP32 residual sum on the F16 path, final cast. `RMSNormGated` uses ordinary gain and normalizes before the gate. `models/qwen3_next.py` provides the residual/FFN schedule. This inspected tree is not itself a certified 27B image binding. |
| S4 | Same model tree, `models/qwen3_next.py`: Q/gate split within each query head, Q/K norms, rotary, attention, output gate and projection. The pinned [27B config](../../data/qwen27-official-config.json) supplies 24/4 heads, D256, 64 rotary dimensions and theta 1e7. Packet 3 prep resolves the gate: official `Qwen3_5Attention` uses **sigmoid** and never reads the publisher swish metadata. [Pinned source evidence](../packet3-prep/gate-evidence.json). |
| S5 | Same tree, `models/qwen3_5_mtp.py`: separately normalize embedding and previous hidden, concatenate **embedding first**, merge, execute the MTP decoder, final norm, shared head. Its exact correspondence to the certified comparator is U7. |

S1's recurrent state layout is `[value_head, value_dimension, key_dimension]`.
The reference partitions K128 into 32 lanes of four consecutive keys and adds
each lane's four products in increasing K order. The device subgroup reduction
itself is unresolved; the CPU freezes an adjacent-pair binary tree. Per row:
normalize Q/K, scale Q by `1/sqrt(128)`, compute sigmoid update and softplus
decay gates, multiply state by decay, dot that decayed state with K, compute
`(V - prediction) * beta`, add `K * delta`, then dot the updated state with Q.
Output rounds to FP16; state remains FP32 before the next row. The historical
Flash-Next BF16 state write is **not** transplanted into 27B. Flash's two
round-state/unroll patches were inert on its promoted serial mode; the source
README explicitly says so.

## UNVERIFIED — packet 4 census items

Every row below is **UNVERIFIED** against the certified comparator. A passing
CPU unit test does not close any row. Known dependencies above are preserved;
unknown device arithmetic is deliberately explicit.

| ID | Unverified behavior | Frozen CPU choice / fixture needed |
| --- | --- | --- |
| U1 | oneDNN fused block-scale placement, dequant intermediate precision, K reduction, FMA, padding and M-dependent dispatch | FP32 FP8×BF16 multiplication, F16 dequant rounding, FP32 CPU BLAS dot, F16 output. Extract every production projection at M1/M2/M6, edge blocks and cancellation/rounding-sensitive cases. |
| U2 | Excluded BF16 weight load/casts, norms/conv/gate parameter conversion, embedding/head/merge execution precision | Keep BF16 storage, cast execution weights to FP16; A_log widens directly to FP32. Save post-load parameter bytes and excluded-linear fixtures, including head and MTP merge. |
| U3 | RMS reduction tree, rsqrt/exp/sigmoid/SiLU accuracy, residual/norm/gate fusion and compiler rounding | Explicit FP32 operations, fixed CPU tree, stated FP16 boundaries, FP32 residual carry. Extract input/output/residual for each norm family, conv activation and FFN product. |
| U4 | GDN subgroup sum tree, FMA contraction, exp/sqrt implementation, 27B serial/spec/checkpoint equivalence | Preserve row/lane dependency order with separate FP32 mul/add and FP32 state writes. Extract every row's conv/Q/K/gates, output and before/after recurrent state, including accepted-prefix replay. |
| U5 | Certified attention kernel, RoPE cache casting, score/softmax/PV reductions, output-gate implementation | Text split-half RoPE with F16 tables; FP32 scores/softmax/PV; F16 output and KV; source-corrected sigmoid gate. Gate function is resolved; certified cast/fusion parity still needs an image-bound fixture. Test nonzero positions, past KV, causal multirow and context lengths. |
| U6 | Target logits precision and certified stable tie/NaN policy | F16 linear output, full vocabulary, lowest index for ties; NaNs rejected. Save head logits and tie fixtures with comparator sampler dispatch. |
| U7 | Certified MTP merge/norm/block boundaries and proposal-head profile | Embedding-first concatenation, one full-attention block, shared full target head. Save intermediate hidden/KV/logits; separately bind any certified draft shortlist. Acceptance/rollback is not implemented by this forward reference. |

All declared storage types and production tensor shapes used by these
operators are honored. **Certified numerical identity cannot yet be honored**:
there are no real payload/operator fixtures and the U1–U7 choices are not
qualified. The contract itself leaves numerical scale/cast proof to packet 2.
The GGUF specification's incomplete quant-layout detail required the credited
format supplement above. Neither limitation is disguised as a passed gate.

## Run offline

From the repository root, using an existing environment with torch and
jsonschema (no installation or environment mutation required here):

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet1b/run_tests.py --receipt experiments/own-xpu-runtime/stage1/packet1b/test-receipt-gate-correction.json
```

Omit `--receipt` for a read-only rerun. The runner refuses other nice/thread
settings and enables deterministic torch CPU algorithms. No external source
checkout, service, model file or network is required. It reads the packet's
files and packet 1's retained headers/contract only. Receipts exclude their own
hash to avoid a circular identity and are rewritten only by explicit request.
Tests use temporary directories with automatic cleanup; `-B` prevents pycache.

## Packet 4's authorized window

After the owner resolves storage and native authorization, preregister one
complete operator census at M1/M2/M6. Pin the admitted official payload hashes,
certified runtime/image/overlay, compiler, library revisions, kernel binaries,
dispatch, environment and launch flags. Fill the extraction schema with
separate raw tensor files, little-endian dtype/shape/strides/offsets, byte sizes
and SHA256s for inputs, outputs, residuals, conv state, recurrent state and KV.
The schema is an envelope: the extractor must additionally validate actual
hashes, dtype byte counts, stride bounds, matching dimensions and complete
shape coverage. A schema-valid JSON file alone is not numerical evidence.

First prove instrumentation neutrality against packet 1's **12 complete token
arrays**, including uninstrumented and instrumented controls. A tracing custom
op can split a graph and change numerics; do not bless those altered outputs.
Then compare reference/operator outputs and all state bytes, repeat in the same
process and a fresh process, and retain every mismatch with its U-row and
source identity. Do not localize with token-stream bisection before the full
operator census. Changed CPU reference choices require a new frozen receipt;
do not overwrite the first reference silently. No speed or lossless claim is
made here. Packets 2/3 remain pending the owner's decisions.
