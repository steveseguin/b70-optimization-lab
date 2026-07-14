# DeepSeek V4 Flash On Four B70s: Investment-Gated Plan

Date: **2026-07-13**

Status: **active planning and low-cost bring-up**

This is the controlling plan for the DeepSeek V4 Flash lane on four Intel Arc
Pro B70 32 GB GPUs. It replaces the earlier assumption that the full Intel
AutoRound checkpoint could be taken directly into a TP4 smoke test.

## Decision

Proceed with the vLLM/XPU program, but do not commit the large-model investment
to a predetermined `K180 W4A16` artifact.

## 2026-07-13 Execution Refinement

The user explicitly authorized downloading a runnable candidate while the
low-cost gates continue. Research found a lower-risk first executable artifact:
`0xSero/DeepSeek-V4-Flash-180B` revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990` is a uniform-K160, standard
safetensors checkpoint with native packed MXFP4 experts and 40 experts per TP4
rank. It avoids heterogeneous loader work and is therefore the first smoke and
performance candidate.

This does not replace the quality plan. The public K160 prunes hash layers 0-2,
its referenced raw observations are unavailable, and its rank-discounted top-k
frequency is not the REAP paper metric. It must not be called the smartest
fitting variant until it passes the frozen quality suite. The official source,
teacher evidence, and a true-REAP hash-preserved nested pack remain required for
the final quality decision. The official-source transfer was paused before any
weight shard completed so bandwidth could prioritize K160; it remains
resumable.

The program will:

- use `deepseek-ai/DeepSeek-V4-Flash` revision
  `60d8d70770c6776ff598c94bb586a859a38244f1` as the immutable source;
- preserve the 256 hash-routed experts in layers 0-2;
- compare native MXFP4 experts against symmetric group-128 INT4/W4A16 on exact
  DeepSeek V4 shapes before choosing the production pack;
- build one nested REAP manifest capable of emitting K160, K168, K176, and
  K180 later-layer variants;
- construct K160 first, then promote the largest variant that passes quality
  and leaves at least 3 GiB free per GPU after warm graph capture at 8K;
- capture a fixed official-source teacher subset after the source download as
  primary quality truth;
- use full, unpruned `bullerwins/DeepSeek-V4-Flash-GGUF` IQ3_XXS revision
  `2be25f699d3efe806def93b0ae5dc632a824abb1` as a secondary all-expert behavior
  control, not as source truth or the assumed production runtime;
- keep speculation disabled until nonspeculative decode is correct, stable,
  profiled, and approaching 40-50 tok/s.

This is a strategic go and a tactical no-go on downloading, pruning, or
requantizing the full checkpoint before the small gates below pass.

## Why This Is Still The Right Direction

DeepSeek V4 Flash is the smartest DeepSeek V4 variant that is even plausibly in
scope for this hardware. The official model is 284B total / 13B activated per
token. DeepSeek V4 Pro is far outside the memory envelope. The official Flash
checkpoint uses native MXFP4 experts and mostly FP8 dense weights.

vLLM plus the Intel XPU kernel package is the only current route that combines:

- DeepSeek V4 model, tokenizer, sparse attention, cache, and MTP awareness;
- merged Intel XPU sparse-attention decode support;
- Xe2 fused MoE kernels for MXFP4 and symmetric INT4;
- a credible path to TP/EP/PP placement and later graph/fusion work.

It is not turnkey. DeepSeek V4 is absent from the current optimized XPU model
matrix, its MXFP4/W4A16 loader work is still incomplete upstream, and the
current model code assumes a global expert count. Those are precisely the
risks this plan tests before the expensive model build.

Primary source pointers:

- https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash
- https://github.com/vllm-project/vllm/pull/42953
- https://github.com/vllm-project/vllm/pull/41426
- https://github.com/vllm-project/vllm/pull/45645
- https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/
- https://huggingface.co/bullerwins/DeepSeek-V4-Flash-GGUF
- https://huggingface.co/sleepyeldrazi/DeepSeek-v4-Flash-REAP-K180-NVFP4

## Corrections To The Earlier K180 Recommendation

1. Public K180 is not an Intel-ready checkpoint. It uses a custom GGUF
   convention, NVFP4 gate/up, Q2_K down projections, Q8 dense tensors, and a
   CUDA-only runtime. Its approximately 99 GiB size is not evidence that a
   native vLLM/XPU K180 pack will occupy the same memory.
2. K180 has heterogeneous layer widths. Layers 0-2 retain 256 experts while
   layers 3-42 retain 180. Current vLLM DeepSeek V4 construction uses one
   global `n_routed_experts`, so a correct implementation needs per-layer
   expert counts and exact old-ID to new-ID mappings.
3. AutoRound metadata does not by itself prove native XPU MoE dispatch. The
   runtime must prove `XPUExpertsWNA16` for symmetric INT4 or the native MXFP4
   fused MoE path. A successful load with BF16 expansion is a failed gate.
4. Native MXFP4 is a first-class candidate. The source experts are already QAT
   MXFP4, and gratuitous requantization to uniform INT4 may reduce quality.
5. K180 quality is unproven on DeepSeek V4. “Best quality” in a K128/K150/K180
   upload ladder is not a task-level comparison with full IQ3_XXS.

## Capacity Audit

The exact source tensor-header audit is recorded in
`../experiments/deepseek-v4-flash-reap-xpu-b70/data/fit-audit-20260713.json`.
The official source occupies about 148.648 GiB of tensor payload. The direct
native-MXFP4 projection below keeps the hash layers and all non-routed tensors,
removes the attached MTP tensors for the initial nonspeculative lane, and
scales only routed experts in layers 3-42:

| Later-layer experts | Projected tensor payload |
| ---: | ---: |
| K128 | 81.710 GiB |
| K144 | 89.679 GiB |
| K160 | 97.648 GiB |
| K168 | 101.632 GiB |
| K176 | 105.617 GiB |
| K180 | 107.609 GiB |
| K192 | 113.585 GiB |
| K200 | 117.570 GiB |

These are file-payload projections, not promises of resident memory. Loader
repacking, duplicated scales, collectives, activations, KV cache, kernel
scratch, and graph pools must be measured. K160 is the first full artifact;
K180 is only an upper candidate.

The initial table excludes the attached MTP tensors. A same-K MTP projection is
99.640 GiB at K160, 103.724 GiB at K168, 107.808 GiB at K176, and 109.850 GiB
at K180. Preserving the full 256-expert MTP adds 3.188 GiB to the base artifact.
Stage 8 therefore requires a fresh capacity decision and may force a step down
in K.

The full Intel W4A16 AutoRound checkpoint is 155,590,474,496 bytes
(144.905 GiB) across its current safetensor shards. It cannot be resident on
this host and must not be downloaded as the deployment candidate.

## Fixed Product And Measurement Contract

- Workload: one active generation, never aggregate throughput.
- Hardware: four B70s for the deployed model; independent cards may be used for
  isolated kernel A/B tests.
- Initial context: 8K maximum; long context is not part of the product gate.
- Runtime destination: clean, pinned vLLM main plus clean, pinned
  `vllm-xpu-kernels`; do not develop in the protected dirty Qwen trees.
- Precision candidates: native MXFP4/BF16 expert execution and symmetric
  group-128 INT4/BF16 expert execution. No silent BF16 expert materialization.
- Initial decode: nonspeculative only.
- Primary performance metric: fixed realistic cold-suite median generated-token
  throughput for tokens 1-100 after TTFT, with `cached_tokens=0`.
- Promotion requires exact run identity, per-rank memory, kernel/backend trace,
  quality results, profile, raw logs, and repeatability.

## Artifact And Cache Layout

Use content-addressed artifacts so model construction happens once and kernel
iteration remains fast:

- source/archive model cache: `/mnt/usb-models/llm-cache/hf`;
- active packed model and hot shards: `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu`;
- benchmark logs: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu`;
- tracked manifests and summaries:
  `experiments/deepseek-v4-flash-reap-xpu-b70/data/`;
- tracked patches:
  `experiments/deepseek-v4-flash-reap-xpu-b70/patches/`;
- tracked chronological results:
  `experiments/deepseek-v4-flash-reap-xpu-b70/results/experiment-ledger.md`.

Cache keys must include source revision, REAP manifest hash, candidate K,
packing format, group size, tensor layout version, runtime revision, and kernel
ABI revision. Preserve:

- downloaded source shards;
- safetensor header/size audit;
- one nested expert-ranking and old-ID/new-ID manifest;
- one-layer H4096/I2048 golden tensors for M=1/4/8;
- packed per-rank weights;
- kernel shared objects and compile caches keyed by revision;
- deterministic golden logits/tokens for each promoted quality gate.

Storage is itself a gate. On 2026-07-13 the external archive had about 2.5 TiB
free, while the internal NVMe had only about 11 GiB free. Before Stage 4,
require at least 800 GiB free in the archive workspace and make a reviewed
decision that preferably frees at least 140 GiB internally for the hot pack and
compile/runtime cache. Do not delete or relocate existing artifacts ad hoc.

## Staged Execution

The executable acceptance details live in
`../experiments/deepseek-v4-flash-reap-xpu-b70/benchmarks/stage-gates.md`.

### Stage 0: Isolate And Freeze

Create clean DeepSeek-specific worktrees and an environment pinned to exact
vLLM, XPU-kernel, PyTorch XPU, oneAPI, oneCCL, and driver revisions. Record the
four-card topology and usable memory. Do not reset or clean the Qwen trees.

Exit: clean builds import on B70, all identities are captured, and the source
model revisions above are frozen.

### Stage 1: Exact-Shape Kernel Gate

Without full model weights, exercise H=4096, I=2048, top-k=6, BF16 activations,
M=1/4/8 and local-expert counts 40/42/44/45/64 where applicable. Compare:

- native MXFP4 fused MoE;
- symmetric group-128 INT4 fused MoE;
- explicit BF16 dequantized oracle.

Measure correctness, bytes, latency, graph capture/replay, and backend identity.

Exit: at least one low-bit path is correct, uses the Xe2 native fused kernel,
replays without rerecording, does not materialize full BF16 expert weights, and
is at least 1.5x faster than the explicit BF16 expert reference at both M=1
and M=4. Record M=8, but do not let it hide a weak single-session path.

Stop: neither low-bit path can enter the native kernel or reusable graph path.

### Stage 2: Heterogeneous Model And Loader Gate

Patch and test per-layer expert counts:

- layers 0-2: 256 global / 64 per TP4 rank;
- layers 3-42: candidate K, divisible by four;
- preserve `tid2eid`, router rows, correction metadata, and exact REAP maps.

Construct all 43 layers with dummy weights. Verify selectors and parameter
mappings without downloading full shards.

Exit: dummy TP4 construction passes, every layer has the intended router and
expert shape, and native quantized methods are asserted in tests.

### Stage 3: Architecture Fixtures

Run isolated correctness fixtures for sparse MLA, FP8 KV layout, compressor,
indexer, inverse RoPE, hash routing, mHC, collectives, and sampler. Test eager
and graph modes separately.

Exit: all fixtures pass against reference implementations and no CUDA-only
path is entered.

### Stage 3.5: Freeze Ranking, Mapping, And Quality Identity

Before the source download, either validate a complete reproducible public
old-ID ranking/map or commit a calibration-v1 plan with prompt hashes, domain
weights, REAP metric, tokenizer/source revision, seeds, and runner revision.
The K candidates must be nested prefixes of one ranking, and hash layers 0-2
remain unpruned. Freeze the quality suite, scoring, critical cases, generation
settings, and numerical tolerances before candidate outputs are visible.

Exit: mapping provenance and calibration/quality identities are complete and
reproducible.

### Stage 4: Source Download And Nested Pack Builder

Only after Stages 1-3.5 pass, download the frozen official source once to the
archive cache. Build one deterministic pruning/packing tool that can emit
K160/K168/K176/K180 from the same ranking manifest without recalibration.
Write directly into the runtime's preferred per-rank layout; avoid repeated
load-time transforms. Derive or validate the nested ranking once on a frozen
calibration mix covering code, tool use, research/knowledge, math/science,
planning, and general QA. A public REAP selection may seed the ranking only if
its full old-ID mapping and calibration provenance can be reproduced.

Exit: the K160 manifest, checksums, tensor inventory, exact size, and one-layer
packed parity all pass.

Capture official-source teacher logits/task results on a fixed tractable
quality subset before pruning. This may use a slow streamed/offloaded reference
path and is never a performance result.

### Stage 5: K160 Full-Model Bring-Up

Load K160 at 8K with speculation, prefix caching, and performance experiments
disabled. Prove full residency and capture per-rank memory before and after
warm graph capture. Run one token, p64/n16, deterministic routing coverage,
greedy decode, and degeneration checks.

Exit: correct text, deterministic canaries, native low-bit kernel traces, no
host/offload path, and at least 3 GiB warm free memory on every rank.

### Stage 6: Quality And Capacity Selection

Compare K160 first with the frozen official-source teacher subset, then with
full IQ3_XXS on coding, math/reasoning, tools/JSON, instruction following, and
user workloads. IQ3 is a secondary quantized/runtime-confounded control;
upstream llama.cpp support exists but current four-B70 allocation failures make
it unsuitable as the production assumption.

If K160 passes quality and memory, emit K168, then K176, then K180 without
rerunning calibration. Select the largest K that:

- keeps at least 3 GiB warm free memory on each GPU;
- has no critical user-canary regression;
- retains at least 98% of the IQ3 normalized aggregate score and loses no more
  than two absolute percentage points on any scored coding, math/reasoning, or
  knowledge suite;
- retains correct native-kernel dispatch and graph behavior.

Do not call any REAP candidate “smartest” until this bakeoff passes.

### Stage 7: Nonspeculative Optimization

Establish a cold baseline and exact cycle timeline. Compare TP4, TP4+EP, and
PP4/layer partitioning for one session. Profile expert compute/routing,
collectives, sparse attention/cache, graph gaps, and sampling in that order.

Milestones:

- first correct resident baseline;
- 25 tok/s nonspeculative;
- 40 tok/s nonspeculative;
- 50 tok/s nonspeculative.

Stop/reassess if the full decode cycle remains above 40 ms and PCIe collectives
dominate with no measured fusion or placement route capable of closing the
gap.

### Stage 8: Speculation

Only after the base path approaches 40-50 tok/s, test native target-verified
MTP first. DFlash/EAGLE are later alternatives, not initial dependencies.
Speculation must preserve the selected target's outputs under rejection and
state rollback/commit tests. Re-run the full warmed memory gate including the
MTP tensors and step down K if necessary to retain 3 GiB free per rank.

### Stage 9: Promotion

Run the fixed realistic cold suite, repeatability gate, full identity capture,
and final quality suite. Promote a result packet and LocalMaxxing submission
only for a verified matching record.

## Immediate Authorized Work

The next permitted implementation work is limited to Stages 0-3.5:

1. create clean worktrees without modifying the protected Qwen checkouts;
2. freeze revisions and environment identity;
3. add exact-shape MXFP4 and INT4 one-layer tests;
4. prove native backend selection and graph replay;
5. implement/test heterogeneous per-layer expert construction with dummy
   weights;
6. run architecture fixtures.
7. freeze ranking/calibration provenance and the quality-suite identity.

Do not start a 100+ GiB model download or full checkpoint construction until
the Stage 1-3.5 evidence is recorded as passed in the experiment ledger.
