# Architecture specification — Stage 0

This is a proposed architecture, not a working runtime or a performance claim.
It implements the [owner's objective](../../docs/own-xpu-runtime-objective.md).
All external techniques are attributed in [IDEAS](IDEAS.md); lab mechanisms and
their ownership boundaries are in [INVENTORY](INVENTORY.md). No external runtime
is embedded, forked or used as our implementation skeleton.

## Platform and implementation boundary

Use **C++/SYCL for the runtime and exact kernels, Level Zero for explicit
resource/event ownership, and Triton-XPU for independently written kernel
experiments**. Keep Python as a CPU configuration, preregistration and receipt
control plane; it must not dispatch each operation of the steady decode loop.
Intel oneDNN/oneMKL and, when justified by a matched collective census, oneCCL
are normal dependencies. Library calls still need an arithmetic identity gate.

SYCL gives direct access to Xe subgroup/vector layouts and Intel libraries;
Level Zero exposes queue, event and allocation lifetimes needed for clean exit.
The cost is more explicit lifetime and ABI work than Python. Triton shortens
kernel iteration but brings compiler specialization, reduction-order and JIT
identity risks; compile/cache before admission and record generated binaries.
A pure Python hot loop would retain the dispatch work we intend to remove.
A pure Level Zero kernel authoring stack would duplicate SYCL's useful compiler
work. Do not make arbitrary SYCL/Level Zero queue interoperation an assumption:
prove shared context, native handles and event visibility in a bounded packet.

The [CPU-only toolchain receipt](data/toolchain-20261010.json) records commands,
versions and package metadata from `steve-b70s` on October 10:

| Component | Present on host; not newly installed or GPU-tested |
| --- | --- |
| DPC++/C++ | `/opt/intel/oneapi/compiler/2026.0/bin/icpx`: 2026.0.0 (20260331); 2025.3 installation reports 2025.3.3 (20260319) |
| oneDNN / oneMKL | Current installed headers report oneDNN 3.11.2 and oneMKL 2026.0.0; oneAPI package series 2026.0 and 2025.3 also present. Header hashes and package versions are in the receipt. |
| Level Zero | `libze1`/`libze-dev` 1.28.2; `libze-intel-gpu1` 26.18.38308.1 |
| CPU tools | GCC 13.3.0, CMake 4.3.2, Ninja 1.13.0.git.kitware.jobserver-pipe-1, Python 3.12.3 |
| Existing Python environments | torch 2.11.0+xpu / Triton-XPU 3.7.0 in `~/.venvs/vllm-xpu`; torch 2.12.0+xpu / Triton-XPU 3.7.1 in `deepseek-v4-xpu`; torch 2.14.0+xpu / Triton-XPU 3.8.0 in `ltx25-baseline` and `minicpm5-baseline-20260912` |
| oneCCL package metadata | 2021.17.2 in vLLM/DeepSeek environments; 2022.1.1 in LTX/MiniCPM environments |

These are observations, not a tested combination. Do not alter the existing
environments. Stage 1 pins a new build manifest after CPU contract review;
native compilation waits for authorization. Compiler/tile-library revisions
are part of numerical identity: the existing 27B [package](../../packages/qwen38-27b-fp8-tp1-b70/package.json)
records a mismatched CUTLASS_REVISION changing attention output by 7.6e-6.
Choose the newest available base at implementation time, retaining the old
certified arithmetic as a comparison authority, never silently rewriting it.

Physical scope is one to four 32 GB B70 cards, one compute queue per card.
Additional compute streams do not create compute overlap; only independent
copy-engine traffic can overlap compute, with explicit dependencies. The host
has 128 GiB non-ECC RAM and memory blocks 53–57 excluded. Use actual usable
RAM and per-card physical free bytes, not nominal capacity, for admission.
The [stability guide](../../docs/host-stability-and-fault-diagnosis.md) records
both GuC hard-lockup and process-teardown fault classes; this design does not
claim to cure either. No power, memory, swap, firmware or driver settings change.

## Components and ownership

```text
CPU control / identity manifest / tokenizer / request admission
  -> checked tensor directory + model-specific graph definition
  -> placement census + typed arenas + immutable execution plan
  -> single-card step executor (later: ordered per-card executors)
       target, native MTP, verifier, sampler, transactional state
  -> bounded output readback + receipt writer
  -> quiesce / ordered destruction / idle and journal postflight
```

The tensor directory owns file mappings, shapes, strides, quantization metadata
and byte identities. Graph definitions own operations and arithmetic order;
they never infer model structure from a friendly name. The placement plan owns
device, pinned-host and ordinary-host allocations, their aliases and lifetimes.
The executor owns queues, executable graphs and events. Nothing may free a
buffer merely because its Python or C++ view disappears.

## Loaders and dequantization contracts

All weights must be official-publisher or Unsloth releases, or our own
quantization of an official release. A new outside source requires a written
justification and owner approval. Existing third-party INT4 records remain
comparison evidence, not permission to download them. Quantized targets have
separate quality labels; changing target weights is never a lossless FP8 win.

Use bounded reads, checked offsets/shapes/products and a manifest covering
every shard/config/tokenizer. Validate tensor coverage, duplicate names,
overlaps and expected scale shapes before device allocation. Validate staging
checksums because this host has known non-ECC memory history. No arbitrary
pickle or model-supplied Python execution is needed.

| Input encoding | Required path and kernel contract |
| --- | --- |
| Safetensors block FP8 | Preserve E4M3 payload, 128×128 block boundaries and scale direction (`scale` vs inverse scale). Keep excluded BF16/FP32 tensors at their declared type. FP8 storage does not authorize changing certified W8A16 arithmetic to W8A8. Dequantize tiles in registers with the certified cast/multiply/reduction order; exact oneDNN dispatch may be retained. |
| compressed-tensors / AutoRound INT4 | Read actual quantization config, group size, axis, packing orientation, signedness, zero points and any permutation/group index. Support symmetric and asymmetric separately. A GPTQ relabel is not a conversion and must be proven byte-preserving. Kernel unpacks nibbles, applies each group's scale/zero in the registered order and performs the exact W4A16 reduction. |
| GGUF F32/F16/BF16, Q4_0/Q4_1/Q5_0/Q5_1/Q8_0 | Parse per-tensor ggml type, dimensions and shard split metadata. Separate simple block scale/offset and high-bit unpack paths; never infer type from filename. |
| GGUF K grids Q2_K/Q3_K/Q4_K/Q5_K/Q6_K/Q8_K | Superblock unpack kernels for subblock scale/minimum packing and high-bit masks; Q6_K needs its own signed reconstruction. Direct packed GEMV and small-M verifier GEMM must share the same reconstructed values and reduction contract. |
| GGUF IQ grids (IQ1/IQ2/IQ3 variants, IQ4_XS/IQ4_NL) | IQ1/2/3 require format-specific codebook/index/sign reconstruction, not a generic integer multiply. IQ4_NL uses its nonlinear values; IQ4_XS adds its subblock scaling. Exact codebooks are format data with provenance/license review; implementation is independently written. Unknown grids fail closed. |
| Unsloth UD mixtures | UD is a tensor-wise mixture, not one kernel. Dispatch by each tensor's actual type, preserving higher-precision embeddings, head, attention, router and sensitive tensors. IQ3_XXS/IQ4_XS/Q3_K_XL labels do not prove the complete tensor type census. Metadata in [STORAGE](STORAGE.md) identifies files; header/tensor census is a later acquisition gate. |

GGUF format ideas are credited to [ggml/llama.cpp](https://github.com/ggml-org/llama.cpp)
and mixed quantization packaging to [Unsloth](https://huggingface.co/unsloth).
Parsing a format and implementing its mathematics does not require importing
an upstream runtime or copying its dequantization kernels. Record any normative
table provenance explicitly. Repacking is allowed only as an invertible
storage transform, with source-to-packed-to-source byte tests and its own hash.
Avoid a second full-model CPU copy or wholesale FP16 expansion.

## Actual model graphs

Flash-Next was read from the local model's `config.json`; the
[snapshot](data/flash-next-local-config.json) and [receipt](data/flash-next-local-config-receipt.json)
pin its identity. No 27B config or weights exist under this host's
`/mnt/fast-ai/llm-models`; the [27B snapshot](data/qwen27-official-config.json)
comes from the official pinned revision, with [URL and hash](data/qwen27-config-receipt.json).
Do not confuse the release name with the internal architecture name.

| Field | Qwen3.8 27B FP8 | Qwen3.8 Flash-Next FP8 |
| --- | --- | --- |
| Internal family | `Qwen3_5ForConditionalGeneration`, text `qwen3_5_text` | `Qwen4ExpForConditionalGeneration`, text `qwen4_exp_text` |
| Decoder | Dense, 64 layers, hidden 5120, FFN 17408 | MoE, 48 layers, hidden 2560 |
| Layer schedule | 48 GDN + 16 full attention, every fourth full | 36 GDN + 12 full/QSA layers, every fourth full |
| Full attention | 24 query / 4 KV heads, head dimension 256 | 24 query / 2 KV heads, head dimension 256 |
| GDN | 16 key / 48 value heads, key/value dimensions 128, convolution width 4, FP32 recurrent state | Same head counts/dimensions/width; FP32 recurrent state |
| Full-attention output gate | **sigmoid** in the official `Qwen3_5Attention` implementation; publisher `output_gate_type=swish` is unused metadata, preserved verbatim | `output_gate_type=sigmoid`; bind implementation separately |
| FFN/routing | Dense SiLU gate/up/down; no routed experts | 512 experts, top 10, intermediate 640; shared expert 640; preserve routing order/weights |
| Additional Flash structure | Not applicable | Hyperconnections: 4 streams, low-rank 320. PLE at layer id 2: 20M vocabulary, ngram 3, 8 heads, split 128, embedding dimension 2560 |
| QSA | Ordinary full-attention path | Indexer budget 2048, compression factor 4, indexer head dimension 128, 4 query / 1 KV heads; preserve index selection and compression state |
| Native MTP | One block; shared input embeddings, untied output head | One full-attention hybrid block; shared embeddings, model-specific HC/MoE/QSA handling from lane evidence |
| Vocabulary / rotary | 248320; theta 10,000,000, partial rotary factor 0.25 | 248320; main/MTP theta 10,000,000, partial rotary factor 0.25; default interleaved MRoPE configuration from snapshot |

The [packet 3 preparation source check](stage1/packet3-prep/gate-evidence.json)
corrects the earlier inference that the 27B config's swish field selected the
attention gate. GDN gated normalization and the dense FFN still use SiLU;
certified device arithmetic and cast boundaries remain unverified.

Keep norm epsilon, gating, residual ordering and all exceptions from config
and tensor census. `modules_to_not_convert` is not a graph definition (the 27B
exclusion list contains generic MoE names despite its dense graph). Stage 1
is text decode only; vision metadata remains pinned but is unsupported until
its own stage. Never claim the full multimodal model is implemented.

Define each family as an explicit ordered node list, rather than a generic
transformer switch. For 27B: embedding → 64 scheduled blocks → final norm →
full output head. A block carries its residual through input norm and the
selected attention module, then through post-attention norm and dense
gate/up → SiLU/product → down. GDN nodes include input projections, convolution
and SiLU, Q/K normalization, decay/update gates, recurrent update, gated norm
and output projection. Full-attention nodes include Q/K/V and output-gate
projection, Q/K norm and rotary, KV append, causal attention and gated output.
Keep the certified implementation's exact residual/cast boundaries; a
mathematical shorthand here is not license to fuse or reorder them.

Flash-Next replaces that dense FFN with stable top-10 routing, selected-expert
gate/up/down, shared expert and ordered combination, with hyperconnection
pre/post mixing around its attention and FFN branches. PLE injects the
configured ngram lookup at layer 2. Full-attention layers also carry the QSA
compression/index-selection state; serial verifier rows preserve causal
dependencies. The [HC delta](../../patches/qwen38-flash-next-fp8-b70/vllm-hctriton-mtp1-62219122/README.md)
and [QSA delta](../../patches/qwen38-flash-next-fp8-b70/vllm-qsafused-mtp1-6d872457/README.md)
are arithmetic references, not imported graph implementations. Native MTP
normalizes/merges the previous hidden representation and candidate embedding,
executes its own configured block, then normalizes/projects to proposals;
the target graph alone determines acceptance. Packet 2 resolves tensor names,
node signatures and all cast locations; packet 4 binds saved operator fixtures
to the certified runtime before claiming layer parity.

## One captured decode transaction

The objective is one logical replay per step: target evaluation, native MTP
proposal/target verification, greedy sampler and state commit. Fixed-width
proposal and verification slots are allocated before capture. Accepted count,
token IDs, position, active masks, KV indices and GDN checkpoint indices live
on device. The exact dependency order must match the model's native MTP
schedule; an implementation can carry proposals from the preceding transaction,
but cannot commit an unverified proposal or expose a phantom first token.

Maintain committed state and speculative scratch separately. Verification
computes the unchanged target for every candidate row; a stable first-rejection
scan commits only the verified prefix plus the target correction. Roll back
GDN, convolution, KV length, MTP hidden state, PLE history and QSA state together.
Inactive/padded rows must neither read undefined memory nor modify live state.
Greedy ties use the certified token-index order; random sampling is outside
Stage 1 and later needs a device-resident, receipt-pinned RNG contract.

Capture is allowed only after:

1. Compile and specialize every admitted shape; allocate stable inputs,
   outputs, scratch and graph pools. No allocator/JIT miss inside replay.
2. Run the same operations eagerly from a checkpoint, capture separately,
   restore state and compare eager/replay/repeat bytes.
3. Perturb every input independently, including token, position, embedding,
   KV/state and acceptance pattern; outputs must follow the changed input.
4. Prove failure/stop paths cannot leave committed state half advanced.

Outside capture: file I/O, tokenization, prompt admission, dynamic allocation,
JIT, shape selection, request reset, loading, receipt serialization, output
readback and fault monitoring. Initial prefill can be eager, but it must be our
own exact model path so the end-to-end oracle remains meaningful. A saved
prefill-state fixture is diagnostic only, never a cold-suite headline.

No `.item()`, tensor-to-host branch or temporary host literal may feed the
captured region. The [LTX capture failure](../ltx25-b70/notes/vae-graph-capture-blocked-01.md)
found both stale captured output ownership and H2D pointers to freed host
storage. Produce dynamic constants with device operations or fill owned stable
buffers outside capture and establish a copy dependency. This is not permission
to reintroduce that video lane's forbidden constant cache. Output buffers outlive
the executable graph; repeated equality alone cannot detect an inert graph.

The 27B [profile and failed graph trial](../qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md)
is a specific blocker: its 2.368 GiB host embedding handles sampled draft IDs
inside the step, and a captured attempt changed 9/12 outputs. First test
device-resident embeddings with a separately admitted memory census. If they
do not fit at the certified context, a device-indexed host-UVA gather needs
its own exactness/lifetime/latency proof. Do not hide a CPU embedding callback
inside a claimed single replay, or quietly reduce context to fit.

## Determinism is an interface

Pin accumulation precision, FP32 GDN state, cast locations, FMA contraction,
reduction tree, padding, tile geometry and kernel dispatch for every M/N/K.
KV stays BF16/FP16 per certified lane, never FP8. Batch shape, replay count,
compile cache and allocation address must not choose a new reduction order.
Use fixed-order router top-k and expert accumulation; atomic floating sums
are excluded unless their exact order is proven. Retain explicit collective
completion and cross-queue event dependencies.

Before localizing any output drift, run the whole production-shape operator
census, as required by AGENTS.md. A new arithmetic oracle may establish a new
kernel's determinism, but cannot prove equality to the old certified output.
Keep both checks: same-identity repeat and frozen certified cross-runtime
parity. Any changed bit closes the lossless arm pending an explicit owner
quality decision; speed never overrides that failure.

## Placement and communication

Start Stage 1 on one card. Allocate from typed arenas: immutable weights,
full-precision KV/recurrent state, temporary operator scratch, graph/static
buffers, pinned copy slabs and output ring. Alias only with a proven lifetime
interval and include simultaneous capture/rebuild peaks. Every allocation has
an owner and receipt row; no invisible library pool is treated as free.

For Stage 2 retain TP4/EP4 as the certified Flash-Next comparison topology.
Evaluate layer split versus tensor split using measured compute and message
costs at actual shapes, not card count. Layer split minimizes boundaries and
can preserve arithmetic, but a single request traverses layers serially.
Tensor split may shorten GEMMs but pays reductions, arrival skew and altered
rounding. Four cards do not imply fourfold speed or one 128 GB allocation.

The 27B [September profile](../qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md)
recorded 134 TP2 reductions at about 223 μs, roughly 30 ms of the profiled
step; profiling inflated that step, so these are diagnostic costs. The
[Flash 97-reduction test](../qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-xpu-full-decode-graph-97-collective-positive.md)
measured 19.751–19.756 ms inclusive, with 9,700 changed-input outputs exact
per rank; it includes host generation/readback/hashing and is not wire latency.
Use those to justify a fresh placement census, not to predict a speedup.
Captured collective support must pass changed-input replay, rank ordering and
tail tests; stale-data captures are invalid regardless of timing.

For each candidate compute a declared cost budget: sum of dependent layer
costs plus exposed boundary copies for layer split, or per-rank compute plus
measured collective/arrival cost for tensor split. Measure both admitted
plans before selecting. Per-card weight/KV/workspace/graph floors and host
peak are hard gates. Use the existing census and peer-probe evidence in
[INVENTORY](INVENTORY.md); do not probe hardware in Stage 0.

## Expert streaming, UVA and host shadow

Preserve every expert and top-10 routing. Distinguish host-UVA direct reads
from explicit copy-engine staging into a device slot. Both must preserve
packed bytes, scale tensors and accumulation order. Pin host slab ownership
until all referencing queues/graphs drain. A slot cannot be evicted while
in flight. If routing is not known early enough to overlap transfer, expose
the transfer latency; do not invent next-token expert predictions or skip misses.

Whole-step replay and dynamic offload can conflict. A stable UVA table permits
device-indexed demand reads; a host-managed expert miss introduces a replay
boundary. Stage 2 must either prove device-addressable stable backing/staging
semantics or label segmented replay honestly. Do not promise both arbitrary
host streaming and one immutable graph without that proof.

Account once for each distinct physical allocation and also for runtime-created
shadow backing: resident GPU weights + host pinned experts/PLE + loader staging
+ anonymous runtime overhead + page cache pressure + graph/workspace shadows.
Shared views do not imply shared physical backing across processes. The
[host-memory design](../qwen38-flash-next-fp8-b70/notes/2026-10-08-host-memory-reduction-design.md)
and [stability guide](../../docs/host-stability-and-fault-diagnosis.md) record
multi-card shadow cost and deferred backing. A setting that removed shadow
in one runtime is not guaranteed in ours. Record `/proc/meminfo` GPUActive,
RSS/PSS, pinned bytes, device census and cgroup peaks together. Keep the
current 96 GB Flash loading guard as historical admission evidence, not a
blanket allowance for a new runtime. No swap, cache drop or excluded-memory
change is part of this plan.

## Orderly teardown

Lifecycle: admit → load → prepare → eager-check → capture-check → run →
quiesce → drain → destroy → idle-check → close receipt. On error, stop new
submissions and enter the same cooperative cleanup path.

Quiesce admission and copy producers; join workers after their acknowledgments;
wait all compute/copy completion events and collective work; synchronize every
owning queue; destroy graph executables while their allocations still exist;
release device/UVA views, then backing weights/workspaces and pinned slabs;
drain again after deferred frees; release events/queues/contexts last. The
exact order is a future native gate, with per-step markers and bounded waits.
The supervisor checks idle evidence and a fresh kernel-log window before
declaring success. Process exit code zero is insufficient. Timeout records a
fault/incomplete teardown; it never causes an automatic retry or forced reset.

The [October 10 exit probes](../qwen38-flash-next-fp8-b70/notes/2026-10-10-exit-fault-reproduced.md)
under [reopen-20261008](../qwen38-flash-next-fp8-b70/reopen-20261008/)
passed graceful cleanup and ten-second-idle exit, but immediate abrupt exit
after local-reference release logged a BCS fault. The one-layer first-forward
probe passed with cleanup. These support the lifetime hypothesis, not a
certified four-rank cure or a rule that sleeping ten seconds makes exit safe.
Preserve coredumps and fault receipts; follow the owner's halt and recovery
rules. No new deliberate abrupt-exit experiment is planned.

## Measurement, oracle and promotion contract

Emit a hash-bound run manifest before work: model repository/revision, all
shard/config/tokenizer hashes, tensor formats, quantization and KV/state types;
runtime commit/dirty patch hash, compiler/library/kernel binary identities;
host/boot/kernel/UMD/firmware and card PCI IDs; placement, graph shapes, sampler,
MTP depth/acceptance, flags/env; suite hash, prompt IDs/hashes and cache policy.
Emit allocation census, compile/capture events, token arrays/text hashes,
accepted/rejected counts, health/start/stop logs and errors alongside it.

Use the [fixed 12-prompt suite](../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json)
for 27B, despite its historical directory name. The exact TP1 FP8 authority is
[tp1-mtp0-b896-strict-performance.json](../qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/tp1-mtp0-b896-strict-performance.json),
SHA256 `1ee5743c99c1c0057a9dd19ee5d452e48dd282cca893942b7e2c9e2339998283`.
It contains complete token IDs and text. Accepted candidate outputs are
[October recommended-profile run](../qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/tp1-pkg-32k-strict-performance.json),
with the second run/comparison artifacts in that directory. Flash uses the
certified frozen output pins and full result named in [INVENTORY](INVENTORY.md),
bound by the [A367 identity](../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/identity.json).
October's two strict runs share one server. The independent fresh-server 27B
frontier is **54.223911840596784 tok/s**, retained in its
[September attestation](../qwen38-27b-b70/data/2026-09-18-fp8-tp1-mtp5-r312d-32k-promotion-attestation.json).
Keep both identities and their launcher differences; a newer, slightly slower
within-server check does not lower the historical frontier.

Test layers: CPU parser/packing bounds and known-value dequant fixtures;
every production operator shape and repeat; full layer/state comparisons;
mutated-input eager/capture/replay parity; complete fixed-suite token equality;
same-process repeats and two fresh-process runs; context and queued-request
checks only at measured points; cooperative teardown and clean idle postflight.
An output hash without recoverable token arrays is a verification pin, not
a substitute for those arrays when diagnosing a mismatch.

Every fixed prompt runs once per attempt, cold with `cached_tokens=0`, natural
512-token cap and no prompt/KV/response/history/draft learning reuse. Resident
weights and precompiled kernels are allowed. Primary decode rate is the median
of class medians over 99 intervals between token timestamps 1 and 100; retain
event count, numerator/endpoints, all-prompt median, p10, mean, TTFT, wall and
natural-completion rates. Record short completions without fabricating 100
events. Report measured 512-input one-user prefill separately, or “not measured.”
Profiling is diagnostic and never a speed run. Promotion requires the existing
hash-bound attestation, unchanged-target verification and independent quality
and performance gates. No new benchmark is claimed by these documents.
