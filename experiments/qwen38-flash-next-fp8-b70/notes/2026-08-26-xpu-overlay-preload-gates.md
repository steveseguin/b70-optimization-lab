# Qwen3.8 Flash-Next XPU overlay and preload gates

Date: 2026-08-26

## Outcome

The checkpoint and TP4 model topology are ready for a first real load, but the
load remains fail-closed until a coherent MoE-enabled XPU extension has been
built and tested. This is a runtime-package gate, not a model-fit failure.

The older Qwen matrix and DeepSeek lane remain paused. None of their launch
identities, binaries, patches, or promoted speeds were modified.

## vLLM overlay

The local vLLM `main` overlay is six commits above upstream base
`76cfe1cd88`:

- `3fd193010b`: pinned Qwen4Exp model implementation from PR 53896;
- `a6d6d48a1b`: pinned PLE offload implementation from PR 53899;
- `25482e7979`: eager, blocking shared-host PLE transport for XPU;
- `a1fa0b1bbf`: Qwen4Exp XPU registry/model dispatch;
- `b1b3a68da0`: XPU HyperConnection reference fallbacks;
- `48a350bcf6`: QSA XPU kernel enablement.

CUDA and ROCm paths were not replaced. The XPU path is correctness-first and
keeps graph disabled for initial bring-up.

Targeted validation passed:

- 22 PLE transport/worker tests passed, with one CUDA-only skip;
- 46 Qwen/config tests passed, with four hardware skips;
- real B70 HyperConnection microtests were exact for all six operations;
- real B70 QSA compressed-index, sparse-paged-attention, MQA-score, top-k,
  group-compression, and cache-store tests passed;
- QSA sparse attention had maximum absolute error `0.0078125`, below the
  upstream `0.02` tolerance;
- PLE FP8-to-BF16 dequantization with the checkpoint's global scale was exact.

## Correct TP4 memory accounting

`tools/meta_tp_construct.py` uses the real checkpoint configuration,
`initialize_model`, the real FP8 quantization mapper, BF16 default dtype, and
four distributed ranks while allocating tensors on `meta`.

The earlier direct-constructor failure was not a checkpoint defect. Directly
calling the model class bypassed vLLM's quantization name mapper and produced a
false shared-expert block-divisibility error. The production initialization
path passes.

The earlier 33.81-GiB estimate was also false: the dry constructor had not
entered vLLM's BF16 default-dtype context, so ordinary parameters became FP32.
The corrected figures are:

| Shape | Per-rank parameters | FP8 bytes | BF16 bytes | FP32 bytes |
| --- | ---: | ---: | ---: | ---: |
| TP4 | 31.631803 GiB | 30,198,988,800 | 3,647,434,592 | 117,966,528 |
| TP4 + EP4 | 31.528806 GiB | 30,198,988,800 | 3,647,434,592 | 7,374,528 |

EP4 does not materially reduce bytes per rank, but it preserves the native
checkpoint expert block layout: 128 local experts with intermediate dimension
1280, instead of refining the non-EP layout into 512 experts by 320. EP4 is
therefore the preferred first correctness load.

Each B70 exposes 31.890625 GiB. The first load will use a 12-GiB/rank selective
UVA allowance for only `ple_embedding.ngram_embedding.weight`, plus
`gpu_memory_utilization=0.92`. The allowance covers the approximately
11.92-GiB TP-local PLE shard while leaving all other weights resident; it is
not general-weight offload. Real B70 microtests proved both BF16 matrix
multiplication and FP8 `scaled_mm` can consume pinned host-USM views exactly.
Prefetch offload is not allowed yet because the current implementation
constructs CUDA streams and events directly.

## Kernel-package blocker found before load

The live `_xpu_C.abi3.so` was built with MoE disabled. It therefore lacked the
grouped-GEMM operator needed by Qwen4Exp. It also lacked the `is_xe2_arch` and
`is_xe3_arch` Python operators expected by current vLLM.

This was traced to local merge damage in the maintained kernel stack:

- upstream commit `2e2d56e` added the architecture probes, but a later local
  packed-verifier commit replaced the affected files and dropped those hunks;
- the local CMake list retained `csrc/moe/fused_moe_prologue.cpp`, while the
  file itself was dropped during a later upstream merge even though the
  preserved Qwen layerlet still calls it.

Both source pieces were restored on kernel `main` as focused commits. An
isolated build uses oneAPI 2025.3 to preserve the runtime's `libsycl.so.8` ABI,
MoE and GDN enabled, B70-only AOT, one compile job, and external-drive build
storage. No live binary will be replaced until import, operator-registration,
architecture, grouped-GEMM, GDN, and MoE numerical gates pass.

### Superseding native-build decision

A deeper interface audit stopped that grouped-GEMM build before its expensive
compile. The maintained tree currently mixes the old local 11-argument grouped
GEMM Python/binding ABI with the newer 10-argument C++ interface. More
importantly, a later local performance overlay displaced upstream's explicit
block-FP8 128x128 scale path. Merely making the mixed source compile could
therefore silently execute this checkpoint with the wrong scale semantics.

The first-load path now preserves the accepted existing `_xpu_C`, grouped-GEMM,
GDN, FA2, and optimization binaries and explicitly selects
`--moe-backend triton`. Only `_C` and `_moe_C` are rebuilt from current source
to update their stale operator schemas. That narrow build disables SYCL-TLA,
FA2, GDN, MQA, `_xpu_C`, and the allocator, so it cannot overwrite or dilute
the accepted performance stack. A resident plus UVA block-FP8 Triton
numerical gate is mandatory before the full checkpoint load.

Native grouped MoE is now a later optimization task: reconcile the ABI,
reapply the upstream block-FP8 scale path onto the local INT8/INT4/MXFP4
optimizations, build in isolation, and prove numerical parity before promotion.

Structured evidence is in `data/20260826-preload-gates.json`.

## Frozen first-load identity

After the native package gate passes:

- local checkpoint only, pinned revision and tree hash;
- language-only;
- TP4 + EP4, `allgather_reducescatter`;
- target-only / MTP0;
- eager, no graph, no compilation, no prefix cache;
- 512-token model length, one sequence, 512 batched tokens;
- dedicated PLE CPU-process transport disabled: `VLLM_PLE_CPU_OFFLOAD` is
  unset;
- selective PLE UVA only: `--offload-backend uva`, `--cpu-offload-gb 12`, and
  `--cpu-offload-params ple_embedding.ngram_embedding.weight`;
- Triton MoE backend (native grouped MoE is not correctness-qualified);
- GPU memory utilization 0.92;
- external cache, temp, and log roots;
- exact-token and semantic canaries before any performance claim.

Context, MTP, graph, and speed expansion remain downstream of that exact
correctness gate.

## First real TP4 load: bounded constructor failure and repair

Attempt 4 passed every frozen launcher gate, including four-rank XCCL barrier
and all-reduce, and brought up all four TP4/EP4 workers. It selected Triton for
both GDN decode and block-FP8 MoE. It then stopped in the PLE constructor before
checkpoint weight loading; this was not a hang, OOM, collective failure, model
fit failure, or throughput result.

`PleOffloadLayer.get_target_device()` combined the accelerator-aware current
device index with a literal `cuda` device type. The surrounding default-device
context consequently sent ordinary PLE constructor tensors through
`torch.cuda._lazy_init()` on the XPU-only PyTorch build. All four ranks failed
the same way. The full external log is retained at:

```text
/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1-attempt4/server.log
```

The focused repair is vLLM commit `240899082e`: select the active PyTorch
accelerator's device type while retaining the existing current-device index
and CPU-offload early return. It does not change kernels, quantization,
topology, memory policy, graph mode, or benchmark settings. The worker unit
suite passes `21/21`, covering XPU, CUDA, and CPU-offload selection, and a real
B70 probe proves that the same PLE constructor device context creates ordinary
tensors on `xpu:0`. Patch artifact `vllm/0007` preserves the repair.

Structured attempt evidence is in
`data/20260826-tp4-first-load-attempt4.json`.

Attempt 5 confirmed that repair on all four ranks, constructed the model,
selected the intended backends, and placed exactly 11.92 GiB of PLE parameters
per rank in selective UVA. It then reached `load_weights()` and failed before
reading checkpoint shards because the Qwen integration branch still called
the older `AutoWeightsLoader(skip_prefixes=..., skip_substrs=...)` contract.
Current upstream had replaced its built-in skip filters with weight mappers,
but the imported Qwen implementation has eight calls that still require those
filters for visual, MTP, reconstructed PLE state, and merged HyperConnection
weights.

vLLM commit `71670287ec` restores the two optional filters while retaining
current upstream's tied-embedding alias safety and mapper pipeline. It is a
load-time compatibility repair only. A combined loader/Qwen/PLE suite passes
`73 passed, 1 skipped`; prefix and substring filters have direct regression
tests. Patch artifact `vllm/0008` preserves the delta. Attempt 5 evidence is in
`data/20260826-tp4-first-load-attempt5.json`. The next action is unchanged
attempt 6 with only the compatibility repair and source-head pin advanced.

Attempt 6 loaded all 131 checkpoint shards on every rank. Rank 0 reported
`688.80` seconds for weight loading; all ranks reported approximately `31.61`
GiB of accelerator-side model memory and completed post-load FP8 processing.
The run then failed at KV-cache specification because current upstream replaced
the MLA-specific `compress_ratio` field with the generic
`tokens_per_state` field. The QSA integration still constructed and read the
removed field.

vLLM commit `4382519af0` ports QSA compressed-cache publication and metadata
consumption to `tokens_per_state`, deriving physical states with current
upstream's `num_states` interface. The focused QSA/config/weight suite passes
`71 passed, 27 skipped`. A four-rank TP4+EP4 meta cache-spec gate also passes:
all four ranks expose 73 cache specs, including 12 compressed MLA specs with
four tokens per stored state and 12 circular raw-key specs. Patch artifact
`vllm/0009` preserves the repair.

The API parent remained alive after EngineCore had failed, so the launcher
health loop did not notice the terminal child failure until manually stopped.
The launcher now recognizes the two terminal EngineCore startup messages and
enters its normal bounded process-group and IPC cleanup immediately. Attempt 6
evidence is in `data/20260826-tp4-first-load-attempt6.json`. Attempt 7 keeps the
same runtime identity and advances only the compatibility repair/source pin.

Attempt 7 confirmed the cache-spec port and again loaded all 131 shards, this
time in `549.09` seconds on rank 0. It entered the first dummy/profile forward,
where all ranks raced to build the same Triton launcher in the attempt-local
cache on the external NTFS/FUSE volume. Triton then attempted to load a
launcher shared object that the non-POSIX cache transaction had not preserved.
The missing file was only 548 KiB of generated cache state; model weights,
runtime DSOs, and source artifacts were unaffected.

Attempt 8 moves only fresh Triton and TorchInductor compilation caches to a
unique `/tmp` ext4 directory. Durable logs, model weights, and non-executable
cache roots remain external. The launcher rejects reuse, records the exact
compile-cache path, and removes it during bounded cleanup. This is filesystem
correctness for generated executable artifacts, not a model, kernel, topology,
or decode configuration change. Structured evidence is in
`data/20260826-tp4-first-load-attempt7.json`.

Attempt 8 showed a separate asymmetric startup defect. Ranks 1--3 allocated
the 11.92 GiB selective-UVA PLE table and completed model loading in about 435
seconds. Rank 0 remained CPU-bound for more than 18 minutes in
`UVAOffloader._maybe_offload_to_cpu`, copying the uninitialized accelerator PLE
table to CPU before all checkpoint shards replace its usable rows. The attempt
was stopped through the launcher's bounded cleanup path; no decode measurement
was taken. Structured evidence is in
`data/20260826-tp4-first-load-attempt8.json`.

vLLM commit `bb4ad1cca6` makes skipping that initial copy an explicit
parameter opt-in and applies it only to the Qwen4Exp PLE embedding weight. The
ordinary offload path is unchanged, the FP8 scale is not marked, and the
downloaded checkpoint's 128 FP8 shards exactly cover the TP4 table with no TP
padding. The focused offloader/PLE/Qwen suite passes 68 tests; all 14 PLE tests
pass independently. A real B70 microgate confirmed that the fresh pinned CPU
allocation maps to a writable XPU UVA view. Patch artifact `vllm/0010`
preserves the optimization. Attempt 9 advances only this source pin.

Attempt 9 proved the no-copy startup path on all four ranks: every rank
reported its 11.92 GiB UVA table within one second, all 131 shards loaded, and
all ranks completed post-load processing in about 558 seconds. The first
512-token profiling forward then failed in the Triton MoE path with Level Zero
`UR_RESULT_ERROR_OUT_OF_RESOURCES` on every rank. No decode request ran.
Structured evidence is in `data/20260826-tp4-first-load-attempt9.json`.

Attempt 10 reduces only `max_num_batched_tokens` from 512 to 64. Chunked
prefill remains enabled, so the 512-token model-context limit is unchanged;
TP4, EP4, FP8, eager execution, MTP0, selective UVA, Triton MoE, and every
decode-path optimization remain unchanged. This bounds the startup profile
forward and is intentionally conservative for the first healthy-server gate.
Larger prefill chunks remain a later matrix dimension once correctness and
decode are established.

The first attempt-10 invocation never reached vLLM. The post-OOR management
snapshot hung in `xpu-smi discovery`; one bounded direct PyTorch probe also
timed out. Passive journal evidence then showed a GuC job-timeout/reset storm
on `0000:27:00.0`. With no render-node holders, the console on ASPEED, and
`xe.disable_display=1`, all four live B70 BDFs were unbound and the `xe` module
was reloaded using the repository's proven recovery procedure. Four-device
discovery and the exact BDF mapping returned afterward. The launcher now caps
every XPU-SMI inventory call at 30 seconds so management telemetry can never
block a model launch indefinitely. The fresh model run uses attempt 11.

## Attempt 11: full load passes, first forward faults again

Attempt 11 passed the bounded four-device inventory, staged-runtime schema,
idle-memory, and four-rank XCCL barrier/all-reduce gates. All four ranks made
the 11.92-GiB PLE UVA view ready within one second, loaded all 131 shards, and
completed post-load processing. Rank 0 loaded weights in 551.92 seconds; the
four model-load times were 559.34--560.52 seconds at 31.57 GiB reported per
rank.

The first 64-token dummy/profile forward still failed. The initial Python
symptom was Level Zero error 40 (`UR_RESULT_ERROR_OUT_OF_RESOURCES`) in the
first MoE call; shutdown then surfaced error 20 (`UR_RESULT_ERROR_DEVICE_LOST`)
on all ranks. The kernel journal began recording CCS write faults at 20:30:46
on all four BDFs, followed by unsuccessful `-EPERM` fault responses, CAT error
18, job timeouts/resets, and one coredump per card. The four virtual addresses
are different and only share the low `b69000` suffix. Treat the OOR name as a
runtime symptom, not proof of physical-HBM exhaustion.

The API never became healthy and no decode request or throughput measurement
exists. The server log and all four device coredumps are preserved in the
external attempt directory with hashes in
`data/20260826-tp4-first-load-attempt11.json`. The failed processes and compile
cache are gone, and xe reinitialized all four BDFs. The structured receipt does
not claim a retained launcher exit code or a post-reload compute gate that the
attempt-local evidence did not record.

## Exact routed-MoE isolation after attempt 11

The one-B70 isolation gate now covers the exact local routed-expert geometry:
128 local / 512 global experts, hidden 2560, intermediate 640, top-k 10,
FP8 128x128 block weights, BF16 activations, the production modular NoDPEP
path, and rank-0's 512-to-128 expert map. The live attempt-11 MoE shape is M64,
not M256: TP4+EP4 with DP1/PCP1 does not activate sequence-parallel AG/RS even
though `allgather_reducescatter` is the configured backend.

All corrected gates passed:

- constant-weight functional M64 with the global expert map;
- constant-weight modular M1 and M256 stress;
- real checkpoint layer-0 rank-0 packed weights/scales at modular M1;
- real checkpoint layer-0 rank-0 packed weights/scales at modular M64 with
  the global expert map;
- that exact real M64 arm while an exact 12,800,061,440-byte TP4-local PLE
  host-USM/UVA view remained live.

Every output was finite and shaped correctly. The checkpoint-side CPU audit
also found every rank-0 layer-0 FP8 expert element finite and every scale
finite, positive, and nonzero. This exonerates basic expert packing, scale
layout, EP remapping, the default one-layer Triton tile, and a single live PLE
mapping. The next full launch must be instrumented to separate full-model
residency and earlier/shared/full-forward state from the routed kernel instead
of repeating another blind profile attempt. The gate and exact results are in
`tools/fullshape-triton-fp8-moe-gate.py` and
`data/20260826-fullshape-triton-fp8-moe-isolation.json`.

## Exact BF16 shared-expert isolation after attempt 11

The remaining layer-0 shared path was audited and tested separately. All 48
shared experts are unquantized BF16: each layer has gate/up matrices shaped
`[640, 2560]`, down shaped `[2560, 640]`, and a replicated gate shaped
`[1, 2560]`; there are no shared-expert FP8 scales. At TP4, each rank receives
160 gate rows, 160 up rows, and 160 down input columns with no padding.

A one-B70 gate loaded the exact layer-0 rank-0 checkpoint shards and
synchronized after every production phase. Both M1 and the live M64 profile
shape passed the packed `[320, 2560]` BF16 gate/up linear, the XPU custom
SiLU-and-multiply operator at the previously uncovered `d=160` shape, the
`[2560, 160]` down linear, the replicated N=1 expert gate, and the final
sigmoid multiply. Every intermediate was finite and correctly shaped.

The first M1 invocation is excluded: it attempted to instantiate vLLM's custom
op wrapper without a current engine-config context and stopped before calling
the operator. The corrected gate calls the exact registered XPU operator that
the wrapper dispatches to. No failing kernel result is inferred from the
excluded harness invocation.

Together with the routed FP8 isolation, this removes basic routed packing,
scale layout, EP mapping, shared TP slicing, BF16 GEMMs, shared activation, and
the standalone PLE UVA mapping from the primary fault tree. The next attempt
uses source patch 0011's explicitly enabled MoE synchronization trace. The
trace is default-off, changes execution timing when enabled, and can never be
used for a performance claim. It records entry, gate, dispatch, shared,
router, routed-kernel, and combine completion so the last passing phase
separates a preceding/full-residency fault from the MoE phase that reports it.
Structured evidence is in
`data/20260826-shared-expert-bf16-isolation.json`.

## Attempt 12 phase trace and allocator-pressure replay

Attempt 12 again loaded all 131 shards on all four ranks in 558.14--558.59
seconds at 31.57 GiB reported per rank. The opt-in trace made the failure
boundary exact: every rank synchronized successfully after layer-0 entry,
router-gate projection, dispatch, the complete BF16 shared expert, and top-k
routing. Every rank's final pass was `router_complete`, shape `[64, 10]`, at
33,898,646,016 allocated bytes, 34,185,674,752 reserved bytes, and
34,163,364,352 maximum allocated bytes. No rank reached
`routed_modular_complete`. All four devices faulted simultaneously in the
routed call, then recorded the same error-40/error-20 and xe reset pattern as
attempt 11. The logs and four coredumps are preserved and hashed in
`data/20260826-tp4-first-load-attempt12.json`.

The memory counters were not accepted as proof of a simple OOM. A one-B70
replay used the exact real layer-0 rank-0 expert weights, M64 geometry, global
EP map, and 11.92-GiB PLE UVA mapping. It passed once with 31.57 GiB allocated,
then passed again with 31.57 GiB allocated and the allocator reservation raised
to the exact attempt-12 31.837891 GiB boundary, leaving the same 54 MiB outside
the reservation. The second replay's maximum allocation was slightly higher
than attempt 12. Therefore allocated pressure, cached reservation, and raw
unreserved headroom do not independently reproduce the fault.

The next full candidate adds a 303.125-MiB/rank selective-UVA margin by moving
only the untied input embedding, not the dense LM head or per-layer projections.
The embedding reads one 5,120-byte BF16 row/rank during decode, making it the
lowest expected decode-risk placement change. Source patch 0012 wires the
directly constructed embedding through the existing offloader; without that
patch, merely adding the selector would silently do nothing. Patch 0013 adds a
separate default-off exact routed-input capture. On a diagnostic failure it
writes rank-unique hidden states, top-k weights/IDs, routing buffers, and
pointer/shape/stride metadata immediately before the kernel, allowing an
offline one-B70 replay without another full load. Neither diagnostic mode is
allowed in a speed run. Pressure evidence is in
`data/20260826-fullshape-triton-fp8-moe-pressure-isolation.json`.

A bounded one-B70 mechanism gate then instantiated the exact TP4 rank-local
input-embedding shape (`[62080, 2560]`, BF16), routed it through patch 0012's
Qwen helper and the real XPU UVA offloader, and observed exactly 317,849,600
offloaded bytes. Four boundary/interior rows matched bit-for-bit before and
after offload. This proves the selector is effective and the embedding lookup
remains exact; it is not a full-model health or performance claim. The receipt
is `data/20260826-embed-uva-offload-gate.json`.

Attempt 13 is therefore the next bounded full-model diagnostic. It retains the
exact eager TP4+EP4 MTP0 identity, raises the selective UVA allowance to 12.25
GiB only for the existing PLE embedding and untied input embedding, enables the
phase trace, and enables rank-unique routed-input capture. A healthy diagnostic
must still be followed by a trace/capture-off qualification before any speed
claim; a fault must preserve and hash the capture and device evidence before
recovery.

## Attempt 13 capture and padding-handling correction

Attempt 13 verified the intended placement on all four ranks: each reported
12.22 GiB selectively offloaded, model load fell to 31.27 GiB/rank, and all 131
shards loaded. It nevertheless stopped at the same first routed call. The run
preserved four rank-unique input captures, four device reports, and a bounded
system log before the proven all-card recovery; four-card compute, peer access,
and XCCL all passed afterward.

The captures removed the remaining ambiguity. Every rank had the same finite
BF16 hidden states, and every profile row was intentionally marked as padding:
all expert IDs were `-1` and all expert weights were zero. This is the normal
vLLM dummy-profile contract. The XPU alignment component filtered expert IDs
above the configured range but did not filter the `-1` padding sentinel before
using it in its count/map step. The same omission existed in all four alignment
variants and predates this optimization overlay.

Kernel commit `2f829747503c77d4814834dffd0840fb1dd9f75a` adds the missing
two-sided range check and four focused tests covering the exact 64x10/512-expert
all-padding and mixed-padding shapes, with and without an expert map. All four
tests pass. A new isolated runtime stage changes only `_moe_C.abi3.so`; the
previous stage remains intact. The exact all-padding replay passes at attempt
13's 31.274554-GiB allocation and 31.525391-GiB reservation, and the ordinary
valid-route real-weight M64 control also remains finite and passing. Evidence is
in `data/20260827-moe-padding-guard-gates.json`.

Attempt 14 used that sealed component and passed the complete model profile:
all 48 MoE layers on all four ranks completed routed processing and combination,
with no device or engine execution error. This closes the prior TP4 execution
blocker. Startup then stopped at cache configuration because the launcher's
conservative 92% automatic budget reported `-1.46 GiB` available for cache
blocks after the 31.27-GiB model and diagnostic profile. This is a clean
post-profile configuration stop, not a recurrence of the routed failure.

Attempt 15 kept the same identity and again passed every layer. The explicit
192-MiB cache allocation was accepted, then cache construction stopped cleanly
because the model mixes 53,248-byte and 851,968-byte pages while the inherited
default layout was not block-outermost. Current vLLM explicitly requires a
block-outermost layout for this mixed-page model and names `BLHNC` as the valid
choice. Attempt 16 added that declaration, passed all 48 MoE layers on all four
ranks, and created all 192 bounded routed-input captures. Cache allocation then
reached QSA binding, where the model adapter rejected vLLM's standardized
logical `[blocks, heads, states, width]` view because it still expected the old
kernel-facing dimension order.

vLLM commit `d41e640898` normalizes both raw and compressed QSA side caches
once at bind time with a metadata-only view transpose. It adds no per-token or
decode-path work. The complete QSA reference file passes (`19 passed`, `27`
platform skips), including exact stride/alias checks for both `LBNHC` and a
cross-layer `BLHNC` view. Attempt 17 keeps the attempt-16 diagnostic identity
and adds only this adapter correction. If healthy, issue a real non-padding API
canary before shutdown, then remove trace/capture call sites and run a separate
quality and performance qualification.

Attempt 17 passed the QSA bind, allocated the explicit cache (`1,536` tokens),
and reached final kernel warmup. It then stopped cleanly because current vLLM's
combined GDN wrapper supplied 29 interface fields while the preserved optimized
runtime component exposes its earlier 23-field target-decode interface. This is
a source/component packaging mismatch; no component rebuild or replacement is
required for the MTP0 lane.

vLLM commit `687aa13dc` detects the loaded interface once at module import and,
only for the 23-field component, requires `num_spec_decodes == 0` and the
ordinary contiguous target batch before issuing that component's exact call.
The current 29-field path remains unchanged for a future updated MTP runtime.
The staged import/schema gate passes and the launcher now fails closed unless
the pinned component reports exactly 23 fields. Attempt 18 keeps all attempt-17
runtime settings and changes only this source adapter.

An attempted upstream kernel update was deliberately not completed: the latest
upstream refactors the same GDN file that carries extensive local serving work,
so resolving it is a separate performance-preserving port, not a safe startup
shortcut. The exact pre-update tree is preserved as a complete verified bundle
at `/mnt/usb-models/qwen38-build/source-backups/vllm-xpu-kernels-pre-gdn-sync-2f829747.bundle`
(SHA-256 `be14c05473a77ea908282dc62478dc6fe5f5b55dedd3477f1de0b4f6c21fc149`).

Attempt 18 is the first healthy TP4 server and real-request proof. It completed
all profile and warmup passes, allocated 1,536 cache tokens, served four clean
follow-up canaries (addition, copy, JSON, and deterministic repeat), and shut
down normally. Prefix-cache use was zero throughout. The preregistered Python
range canary returned `30` instead of `14`; the short battery passed exact,
copy, arithmetic, JSON, factual, and all eight repeats, while its strict logic
case returned `Yes` versus expected lowercase `yes` and its Python range case
repeated `30`. Therefore attempt 18 is a healthy diagnostic serving proof, not
a full quality pass and never a speed result.
The compact receipt is `data/20260827-tp4-attempt18-api-and-quality.json`.

Production source head `658965050` adds the remaining GDN fail-closed checks
and reverts both diagnostic commits. Source equivalence to the pre-diagnostic
MoE runner is exact, the selective embedding fix remains byte-identical, and
the embedding (`2 passed`) and QSA (`19 passed`, `27` platform skips) suites
pass separately. The active launcher no longer accepts or exports diagnostic
settings and records `diagnostics=none`. Attempt 19 is the first production
quality/performance candidate.

## Attempt 19: production TP4 research baseline

Attempt 19 used the diagnostic-free production source and sealed runtime. It
became healthy with 1,536 cache tokens and served two short-quality batteries
plus three single-stream timing samples. Both batteries reproduced five of
seven strict exact cases. The case-only `Yes`/`yes` miss and the substantive
`30`/`14` range-expression miss remain. One of the first battery's eight
greedy repeats selected a different four-color answer; the second battery's
eight repeats were stable. Across both batteries, 15/16 repeats matched the
majority answer and every one of the 30 requests reported zero cached tokens.

The three exploratory 146-prompt-token, 256-output-token samples measured
`5.142647`, `5.221850`, and `5.289934 tok/s` after first text, for a median of
`5.221850 tok/s`. All three completed 256 tokens with the same output hash.
This is a valid measurement of the exact eager TP4/EP4/MTP0/512 identity, but
it is only a research baseline: the quality and repeat-stability gates failed,
so it is not record-, deployment-, or promotion-eligible. The log also notes
that no model-specific MoE tuning configuration was available, so this is not
an optimized performance ceiling.

The server was deliberately stopped while idle. The engine entered its drain
path, reported request processing complete, and the API completed shutdown.
The API output handler then logged an engine-ended exception after its manager
had been stopped; ranks 0, 2, and 3 logged final worker completion while rank 1
did not emit that last line. No worker, server, or listener remained. Record
this as a controlled stop with a shutdown-observability caveat, not as a clean
shutdown qualification or a serving failure.

The compact evidence record is
`data/20260827-tp4-attempt19-production-qualification.json`. It closes one
honest matrix cell: TP4 + EP4 + eager + MTP0 at the 512-token bring-up limit.
TP1, TP2, graph, MTP1+, longer context, fresh-boot determinism, and
deployment-grade quality remain explicit gaps.

The additive 1,536-token-cap arm then kept every production source, runtime,
placement, cache-size, TP4/EP4, eager, and MTP0 setting unchanged. It reported
3,949 cache tokens, passed a 987-token exact needle and 16/16 repeats, and
completed the sealed 12-prompt realistic suite cache-zero. Three exact
1,024-prompt-token samples produced a `5.133588 tok/s` after-first-text median;
the realistic suite's preferred 99-interval median was `4.449168 tok/s`. The
known 5/7 short strict result remained, including the substantive `30`/`14`
miss, so the new context cell is a research screen rather than a promotion.
Evidence is in `data/20260827-tp4-mtp0-1536-context-screen.json`.

The following configured-3,072 arm kept the same fixed cache, source, runtime,
placement, eager, and MTP0 identity. It reported 6,144 cache tokens and passed
the exact needle at 2,048 server prompt tokens with all 24 quality requests
cache-zero. Its short answers matched the known 5/7 boundary, but one of 16
repeat outputs diverged. The preregistered stop gate prevented all 2K speed
requests, so this is a quarantined capability result rather than a measured
curve point. Evidence is in
`data/20260827-tp4-mtp0-3072-context-screen.json`.

The repeat-v2 retry preserved that quarantined arm, replaced the future
open-choice gate with a prescribed-set canary, and added a one-token
score-returning sensitivity probe. The prescribed first token passed 32/32
with a 9.19-10.19 logprob margin, while the old open-choice margin was only
0.125-0.375. The full fixed-set repeat passed 16/16, the exact 2K needle and
formal cache-zero depth row passed, and three comparable exact-2K samples had a
`5.228429 tok/s` median after first text. The known 5/7 short boundary remains,
so this supersedes the effective 2K coverage state to research-screened without
rewriting attempt 1. Evidence is in
`data/20260827-tp4-mtp0-3072-context-repeat-v2-screen.json`.
