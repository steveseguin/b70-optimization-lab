# Packet 3 — Flash-Next IQ3 host decode orchestration

**CPU gate passes; native execution and checkpoint parity are unverified.**
This is the ordered C++20 target step for the separate **Qwen3.8 Flash-Next
UD-IQ3_XXS (Unsloth), quantized compressed version**. It is our code, with a
synthetic CPU backend and an independent NumPy oracle. It loads no model,
opens no device and starts no server. The [receipt](test-receipt.json) records
23 Python tests and 18 C++ cases, including fresh-process repeats.

The authenticated directory has **48 total layers: 36 GDN and 12 QSA**, not
48 GDN plus 12 QSA. It has 512 experts, top-10 routing, a shared expert and four
HC streams per layer, with PLE at zero-based layer 1. **There is no MTP block.**
Requesting MTP fails explicitly; no unverified draft token enters the sampler.
The [Stage 2 plan](../../STAGE2-PLAN.md#mtp-source-for-the-two-card-line) records
the separately pinned official draft option. It needs its own loaded weights,
merge/block/head bindings and target-verification/rollback transaction before
it can add any launch to this target-only graph.

## Model directory and placement

[model/plan.py](model/plan.py) admits the loader's tensor directory against the
[real IQ3 census](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json).
It rejects missing, duplicate, extra, wrongly shaped or wrongly typed tensors.
All **1,224 tensors occur exactly once** in physical weight ownership. Shapes,
types, byte extents, layer schedule and per-layer names come from the directory;
attention kind is selected by the actual projection tensors, not a model label.
[model/directory.hpp](model/directory.hpp) also checks row/grid alignment and
packed extents, derives dimensions, and adapts packet 2's `iq3::Model::plan`
records through `directory_from_loader`. The text exporter is only a CPU test
adapter, not another GGUF payload loader.

- Card 0 owns layers 0–23, including every expert in those layers and PLE's
  small projections. Card 1 owns layers 24–47 and the final HC mixer/head.
- Each card owns its layers' BF16 GDN state/history, BF16 attention K/V, raw
  index keys and pooled QSA keys. Pooling is the model's architecture; KV
  precision remains full 16-bit.
- `token_embd.weight` and `per_layer_token_embd.weight` remain host-backed:
  **29,321,610,240 file bytes**, not a promise of resident host RAM. The step
  requires device-indexed gathering of one embedding and 16 PLE rows through
  stable, admitted device-addressable backing. Native mapping, residency,
  latency and driver shadows are not implemented or qualified. A host row
  callback would require segmented execution and cannot claim whole-step
  capture. The 15 GiB host still needs a bounded backing solution.
- Cross-card streams and scalar controls have two distinct allocations.
  The forward handoff copies streams, token, position, active and error;
  the return handoff copies sampler output and sticky error before either
  card commits. Integer IDs are I32/U32, routes are three U32 fields, and
  PLE metadata/history/IDs are I64. No float-encoded native routing.

At the **historical** packet 1c capacity of 34,242,297,856 bytes/card, with one
user and 32,768 context tokens:

| Card | Packed resident weights | Estimated total | Remaining estimate |
| --- | ---: | ---: | ---: |
| 0 | 26,165,134,080 B | 30,179,566,616 B | 4,062,731,240 B |
| 1 | 26,464,055,040 B | 30,478,118,656 B | 3,764,179,200 B |

Each total includes full-16-bit KV, recurrent/conv/index state, recurrent/conv
rollback, 1 GiB each for graph buffers, scratch and allocator/driver reserve,
and 256 MiB staging. These are allowances, **not native fit measurements**.
No expanded FP32 weight shadow is admitted. Layer splitting needs no duplicate
HC matrices: packed device weights total 52,629,189,120 bytes. Packet 1c's
53,304,619,520-byte tensor-split scenario includes an extra 675,430,400-byte HC
copy. PLE dilation three requires **nine history rows / 184,320 bytes**, plus
rollback; the earlier three-row estimate was too small. Append-only KV/index
rollback uses committed lengths, not a second full context allocation.

## Ordered step and kernel interface

[step/plan.hpp](step/plan.hpp) builds the immutable launch list against
[kernels/api.hpp](kernels/api.hpp). `Plan::execute` forwards only handles and
events; it has no readback, routing callback, model I/O or allocation API.
Token, position, active/error, routing and lengths are device values. A backend
must allocate/bind all named buffers before enqueue/capture. One compute queue
per card is ordered by explicit events, including transfers. At entry,
`inputs_ready` must cover identical token/position/active controls uploaded to
both owners; request reset cannot update just card 0 because both checkpoint
sites precede the forward handoff. Every native commit advances its own local
position once. The commit parameter only identifies the last submission to
the unified CPU mock, whose single logical position advances once. The CPU
mock does not qualify physical peer-copy or two-queue synchronization.

The sequence is begin/checkpoint on both cards → embedding gather → HC stream
broadcast → layers → final HC mixer → full head → stable argmax → error/token
handoff → commit on both cards. Within each layer:

1. Layer 1 only: PLE hash/gather, key/value projections, grouped norms, gating,
   dilation-three convolution and two rounded residual adds.
2. HC stream norms, down/4/SiLU/up, ordered stream mix and injection projection.
3. GDN projections → convolution → normalized Q/K recurrence → BF16 output
   and state → gated norm → output projection; or QSA projections → norm/rotary
   → KV/raw append and pool → stable selection → selected-order attention/gate
   → output projection. Then HC residual combination.
4. A second HC mix → router softmax/top-10/renormalization → device gather of
   `iq3::Route` descriptors and repeated input → gate/up/product/down for all
   ten selected experts → shared expert and shared gate → ordered weighted
   sum and rounded addition → HC residual combination.

`routed_gemv` uses packet 2's input shape `[top,K]`. Gate/up routes request
`mid` rows; down routes request `H` rows. Each routed projection has a separate
status check that ORs failures into the sticky error. No expert is pruned.
Argmax selects greatest finite logit and lowest vocabulary ID on ties;
positive and negative zero tie. Nonfinite output forbids commit.

GDN output is computed from the FP32 updated state **before** its BF16 store.
The next row widens that BF16 state. Norm/tree, convolution tap order, QSA pool
and selected-token ordering, router/expert order, shared-expert casts and HC
rounding follow the [packet 1b dependency ledger](../packet1b/README.md).
No FMA contraction, fast math, floating atomic reduction or hidden BLAS call is
used. A submission exception rolls the CPU mock back; native backends must
poison execution until tracked work drains and checkpoint restoration is safe.
They must retain all arena/graph leases through the stage 1
[Device/Arena shutdown owner](../../stage1/packet3-prep/src/owner.hpp).
That adapter, UVA admission, native graph lowering and capture are still work
for the next device packet, not implicitly provided by this CPU mock.

## Launch plan and bandwidth arithmetic

Record mode emits **1,873 planned dispatch sites per target step**, with
operation names, tensor names, shapes, cards, dependencies implied by list
order, scalar buffer types and byte extents. This includes 144 routed GEMVs
and 144 status checks, 36 GDN recurrences, 12 QSA attention sites, two
cross-card transfers and the transaction boundaries. Compound sites such as
QSA preparation describe a fused kernel contract. A native lowerer must report
any expansion: **1,873 is not a measured driver launch count**.

The exact census payload is **4,951,240,940 bytes/step**: dense weights once,
949,760,000 selected-expert bytes, 3,540 lookup bytes and 280 metadata bytes.
It is not total DRAM traffic. The recorder separately labels full buffer read
and write *extents*; context capacity, rather than current valid length, bounds
these. Extents can include untouched cache capacity and repeated aliases.
They must not be added up as measured bus traffic. Transaction state traffic,
cache effects, activation reuse and transfers need native counters/timing.

The table uses the lab's historical [507–537 GB/s evidence](../../STAGE2-PLAN.md#four-card-quantitative-case--arithmetic-not-measurement)
(27B streaming linear and LTX copy diagnostics), in decimal GB/s. Neither is a
measurement of this IQ3 step or simultaneous two-card bandwidth.

| Two-card arrangement | Counted bytes/step | Assumed bandwidth | Bandwidth-only time | Reciprocal ceiling |
| --- | ---: | ---: | ---: | ---: |
| Sequential layer split | 4,951,240,940 | One active card, 507–537 GB/s | 9.766–9.220 ms | 102.40–108.46 tok/s |
| Tensor split within each layer, balanced | 5,626,671,340 including HC replica | Two simultaneous cards, 1,014–1,074 GB/s | 5.549–5.239 ms | 180.21–190.88 tok/s |

These are optimistic arithmetic bounds. They exclude compute/dequantization,
launch cost, KV/state, PCIe, collective waits and routing imbalance. Counting
host lookup bytes at VRAM rates is also optimistic. Tensor splitting is only
this comparison, **not an implemented or selected execution path**; it needs
matched collectives and unchanged reduction order. Layer splitting preserves
the single-card arithmetic but cannot double a single request's active-card
bandwidth. At 1,873 sites even an illustrative 1 microsecond/site is 1.873 ms
of issue work; that is an illustration, not measured latency. Whole-step
capture and qualified fusion matter, but no speedup follows from launch count
alone.

## CPU identity, tests and remaining differences

The two-layer mini-model has the same operator kinds, four streams, 16 experts
with top 10, GDN and QSA, PLE and a full synthetic head. Five tokens cross a QSA
pool boundary. The second fixture runs a complete **H2560 GDN/HC/MoE layer**,
including 512 router logits and BF16 `[48,128,128]` state, for five tokens.
Weights are small, nonzero periodic synthetic rows; evaluating four unique
rows bounds CPU work without changing any dot order. No real weight payload
or whole expert bank was materialized. It is not a representative performance
workload or a real-model answer.

Independent [NumPy code](tests/reference.py) computes the mathematical graph
without reading the C++ launch list. The comparisons check every final buffer:
**113 / 3,873 values** for the mini-model and **49 / 996,958 values** for the
real-width layer. All FP32 bit patterns and all BF16 rounding points/state bits
match exactly. Fresh C++ processes repeat both fixtures byte-for-byte.
Adversarial tests cover BF16 ties, reduction cancellation, changed token/state,
routing and sampler ties, nonfinite values, inactive masks, context bounds,
failed submission rollback, dependency rejection and absent MTP.

Explicit identity deltas and limits:

- Packet 2's `iq3::gemv_row` fixes 32 strided logical lanes and `tree32`.
  Packet 1b used PyTorch matmul and an FP8 surrogate. GGUF decode preserves
  its grid's FP32 decoded values; it adds no FP8 scale or pre-dot BF16 weight
  rounding. This is a separate arithmetic identity, not proof of old FP8 parity.
- Stored GGUF norm gains are used directly; the exporter already added unit
  offsets. Stored `ssm_a` is negative `exp(A_log)` and enters the decay product
  directly. There is no second exponent or inverse-log reconstruction.
  Synthetic fixtures construct these stored values from the packet 1b base
  controls. F32 stored controls remain F32. The graph records these choices.
- GDN and QSA output gates use **sigmoid**, following the corrected packet 1b
  [official architecture evidence](gate-evidence.json). The sibling
  CPU audit resolved its earlier SiLU/configuration conflict while this packet
  was being built; both C++ and the independent NumPy reference were updated
  and regression-tested. The small evidence file is retained byte-for-byte
  from the sibling packet so this commit has its own gate binding.
  Convolution, FFN and HC retain SiLU. This source
  correction does not establish native cast/reduction parity.
- Host scalar `expf/logf/sqrtf/sinf/cosf/powf` are explicitly shared with the
  NumPy oracle to isolate reduction/cast differences. Device transcendental
  parity remains unverified; no tolerance is silently accepted.
- PLE's full post-lookup injection extends packet 1b's lookup-only reference.
  Its equations and dilation were researched in the same pinned
  [PLE/model sources](../packet1b/source-evidence.json); no external runtime
  code was imported. PLE uses synthetic hash metadata here. Native signed64
  hash overflow, real lookup mapping and checkpoint casts need their own gate.

## Reproduce and packet 2 handoff

CPU-only test command, using the already installed NumPy environment:

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet3/run_tests.py
```

It builds sequentially with host `g++`, runs tests, writes the small receipt
and deletes its ignored `build/` scratch in `finally`. No SYCL executable is
built or run. To inspect every planned site without a device:

```bash
P=experiments/own-xpu-runtime/stage2/packet3
mkdir -p "$P/build"
nice -n 19 env OMP_NUM_THREADS=2 g++ -std=c++20 -O2 -ffp-contract=off -fno-fast-math "$P/step/main.cpp" -o "$P/build/step"
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$P/model/plan.py" --export-directory "$P/build/directory.txt"
nice -n 19 env OMP_NUM_THREADS=2 "$P/build/step" record "$P/build/directory.txt" > "$P/build/launches.json"
# Read the JSON, then remove only this regenerable scratch:
rm -r "$P/build"
```

Packet 2 appeared during this job; its existing names are adopted:
`iq3::Type`, `Route`, `element`, `bf16_bits`, `gemv_row`, `gemv`, `routed_gemv`,
`Model::plan`, and `Planned`. Packet 2 must provide authenticated directory and
packed buffers for all seven present grids, BF16 input/output GEMV with that
exact order, device-selected routes with bounded access/status, and stable
owned handles. Its primitive implementations do not automatically supply
norms, recurrence, QSA, HC, PLE, sampler, graph lowering or owner integration.
The packet 3 backend contract specifies those remaining launches. Lookup
mapping must be admitted separately; no host callback is a hidden fallback.

**First device gate:** after a native window is separately authorized, bind one complete GDN layer on one card to
its real packed weights. Compare every projection, routing ID/probability,
expert/shared output, HC output, convolution history and BF16 recurrent state
bit-for-bit against the CPU reference using the same decoded bytes. Require
changed-input checks, two fresh processes, deterministic repeats and orderly
Device/Arena shutdown with clean health evidence. The existing stage 1 native
smoke pass is a resource-owner result, not this layer gate. No device command
or window is authorized by this document.
