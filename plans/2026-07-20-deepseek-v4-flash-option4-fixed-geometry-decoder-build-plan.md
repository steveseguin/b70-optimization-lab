# DeepSeek V4 Flash on 4x B70: Option 4 Fixed-Geometry Decoder Build Plan

Date: **2026-07-20**

Status: **committed architecture; design-only build handoff**

Scope of this document: a phased implementation plan for the Intel
SYCL/Level Zero analogue of HIPfire. This document was produced off-GPU. It
does not authorize a model load, service change, held-out evaluation,
LocalMaxxing action, or modification of the active EAGLE training lane.

## Executive decision

Build Option 4 as a new, guarded decoder runtime beside vLLM. vLLM remains the
loader, API server, prefill implementation, scheduler fallback, and exact
oracle. The new decoder owns only the qualified one-request, fixed-geometry hot
decode path. It imports fixed device addresses from vLLM, replays prebuilt
regular Level Zero command lists, and returns committed token IDs and state.

The first implementation target is **one M=1 attention-side boundary
transaction**, instantiated for all 43 model layers. Layer 0 has a distinct
standalone-MHC-pre ingress; layers 1-42 use the recurrent MHC post/pre ingress.
Each transaction begins at its fixed attention ingress (standalone MHC pre for
layer 0; completed reduced FFN output plus MHC post/pre thereafter), runs the
canonical attention preparation/attention/projection kernels, and
ends at the rank-local attention output immediately before the next TP
reduction. It changes no arithmetic. This is the smallest useful boundary that
can remove multiple real launch/synchronization edges without repeating the
already-closed submission-only `all-reduce -> MHC` experiment.

No scope-specific measurement yet predicts the first transaction's gain. Its
**design target and kill band**, not an evidence-backed expectation, is
**22.10-22.38 ms/token** (`45.25-44.68 tok/s`) versus the established
**22.881408 ms/token** baseline. The admission line is at least
**0.50 ms/token** recovered, hence at most **22.381408 ms/token**, under a
same-binary wall-token comparison. This range is a planning target, not a
measured result. The wider architecture remains bounded by the native-K2
evidence: about **20.825625 ms/token / 48.0178 tok/s** empirically and
**19.446408 ms/token / 51.4234 tok/s** under the optimistic full-removal
ceiling. Neither ceiling is a result.

## Evidence that controls the design

The authoritative exact graph-on nonspeculative M=1 result is
`22.881408 ms/token` (`43.703604 tok/s`). Its bounded reconciliation is below;
these are not independently measured additive event sums:

| Bucket | Current ms/token | Design implication |
| --- | ---: | --- |
| Weight-streaming GEMMs | 10.089 | Preserve arithmetic and packing first; only 2.819 ms is measured kernel-efficiency slack. |
| Worker submission/scheduler/outer gap | 3.435 | A fixed native transaction may remove part, but not all, of this bucket. |
| Norms/MHC/RoPE/KV/misc | 3.310 | MHC alone is 2.913 ms and is launch-bound; cross-boundary ownership is required. |
| TP4 all-reduce live critical path | 2.746 | Own producer/reduction/consumer eventually; the 5.601 ms serialized chain is not additive. |
| MoE route/activation/gather/scatter | 1.842 | A strong second transaction target. |
| Sparse QK/LSE and PV | 1.460 | Co-own with MHC and attention preparation; do not change attention arithmetic. |

The measured family inventory is labeled with 85 MHC boundaries, 43 QK/LSE
instances, 43 PV instances, and 86 routed MXFP4 expert GEMMs before counting
dense projections, router work, norms, RoPE/KV insertion, copies, and
sampling. It is therefore fair to describe the hot path as roughly **200+
kernel/operator dispatches**. It is not fair to call all of those 200 separate
Level Zero submissions: the valid host trace directly measures **70.458
effective Level Zero boundaries and 10.792 command-list host synchronizations
per rank/token**. The MHC corpus order starts with layer-0 FFN and then records
attention/FFN post-pre boundaries for layers 1-42 because layer-0 attention
uses standalone MHC pre; this is consistent with 43 attention calls but only 42
recurrent attention post/pre ingresses. Keep these inventories separate in all
reports.

The native K=2 proof is the reason the architecture remains funded. It reduced
effective boundaries from 70 to 33 and host synchronizations from 10 to 4 per
rank/token, and measured `21.751225 ms/token`, a `0.925600 ms/token` recovery
against its same-suite K=0 control. It also proved that cold live capture is
unsafe: lazy compilation during the first capture changed output after two
correct tokens. All kernels must be compiled and exercised in an unscored,
out-of-suite warmup before a command list can enter `ARMED` state.

The three July 20 exact-kernel iterations close local retuning as the program:

- M1 routed-MXFP4 GRF128 is exact but loses about `4.21 ms/token`.
- MXFP4 prefetch distance 3 saves only `0.026013 ms/token` on the slowest
  candidate card and only `0.001310 ms/token` conservatively across cards.
- Dense prepack is slower and, for two W8A16 shapes, inexact.
- Exact MHC RMS-reduction reuse retains `85 -> 85` launches and saves only
  `0.069904 ms/token` on the fail-closed card.
- The faster M8 TF32-DPAS MHC path changes greedy tokens and is permanently
  ineligible.

The conclusion is structural: a new increment has to remove device dispatches,
temporary materializations, metadata round trips, collective breaks, or an
entire framework turn. Merely enclosing existing work in another captured
wrapper is not enough.

## Exact inventory of reusable decoder-shell assets

### Corpus and validation assets

| Asset | Identity and interface | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Real M=1 MHC precursor corpus | `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/real-mhc-boundary-capture-20260715T1200Z`; indexed by `experiments/deepseek-v4-flash-reap-xpu-b70/data/real-mhc-capture-and-graph-fence-20260715.json`; validated by `scripts/validate-real-mhc-boundary-capture.py`; 692 files, 571,072,236 bytes, aggregate SHA-256 `6f8b7b9e7a1c78cc7a2005e2d92d292a80811405725dc43e190526e1be5a59eb`. Per rank: 87 BF16 `[1,4096]` reductions, 85 MHC post/pre records, one final post, and 42 alias boundaries. | Real M=1 reduction/MHC values, rank agreement, boundary ordering, reduction-to-MHC links, recurrent alias topology, and a saved exact oracle. | It does not contain QK/LSE, PV, dense projections, RoPE/KV, MoE, logits, or sampling. There is no neutral checked-in M1 replay worker. The historical external probe `tests/mhc/tp4_real_capture_replay_probe.py` at XPU commit `748a59f` exercises the rejected compact oneCCL+MHC candidate, requires its patched oneCCL preload, and ran only eight graph replays. Reuse the validator and corpus, not that candidate path. |
| M=2 content-addressed corpus | `/mnt/fast-ai/deepseek-v4-corpora/mtp1-m2-cycle-20260717T0710Z`; checked-in index `data/m2-real-cycle-corpus-20260717.json`; manifest SHA-256 `1015e86b1cf46476dbbd10d1cf0cec92246b8af406149f17b0f2dd62b6dd37cd`; 688 manifests, 1,030 blobs, 147,823,004 logical bytes, about 150 MiB. | Per-rank 87 `[2,4096]` reductions, 85 linked MHC boundaries, exact layer order, 84 residual aliases, cross-rank reduced agreement, and content-address validation. | It is a reduction/MHC shell, not a full target forward or endpoint result. |
| Genuine sequential M=4 corpus | `/mnt/fast-ai/deepseek-v4-corpora/mtp-reuse-m4-sequential-20260718T041836Z`; index `data/mwidth-sequential-verifier-20260718.json`; manifest SHA-256 `8c683206da125533737680501647c689a7f8027a708596f4acc8da7deefb96d6`. | Independent consecutive target rows, 87 reductions, 85 linked MHC boundaries, verifier input/logits records, four-rank parity; fixed-M4 MHC saves `1.441370 ms/cycle` with 70 exact replays. | It does not establish predictor acceptance or endpoint throughput. |
| Genuine sequential M=8 corpus | `/mnt/fast-ai/deepseek-v4-corpora/mtp-reuse-m8-sequential-20260718T0440Z`; index `data/mwidth-sequential-verifier-20260718.json`; manifest SHA-256 `1354edce1a16cb73143a597a36ab11ab7e10fa61a7afa9763a6273f80b165ebe`. | Independent consecutive target rows, positions 24-31, 87 reductions, 85 linked MHC boundaries, verifier/logits parity; fixed-M8 MHC saves `4.314321 ms/cycle` with 70 exact replays. | It does not establish acceptance or transfer to the 80.820052 tok/s endpoint. |
| Corpus validators | `validate-real-mhc-boundary-capture.py`, `validate-m2-cycle-corpus.py`, and `validate-mwidth-cycle-corpus.py`. | Content/raw hashes, shapes, dtypes, record counts/order, rank agreement, recurrent links, non-tiled sequential rows, and top-1 agreement. | A validator pass is not device execution or performance evidence. |

The external corpora are protected inputs. New work may read them only in its
own future authorized gate; it must never mutate, repack in place, or overwrite
their manifests or blobs.

### Replay and four-card gate assets

`scripts/replay-m2-cycle-corpus.py` is the current no-model four-B70 worker.
“No-model” means it does not load the 96 GiB checkpoint; it still requires four
GPUs and XCCL. It allocates fixed buffers, captures 87 copy/all-reduces and 85
native M2 MHC consumers in one XPUGraph, checks every reduced element and all
four MHC outputs, and has passed 70/70 replays at a `4.209382 ms` slowest-rank
median.

`scripts/benchmark-mwidth-cycle-corpus.py` accepts `--width 4|8`,
`--source-width 2|4|8`, and explicit control/candidate paths. It tests changed
inputs eagerly, tests collectives separately, then tests static fixed-address
graph stability. A direct sequential gate uses `source_width == width`; only
the historical M2 corpus may be row-tiled.

`scripts/run-mwidth-cycle-gate.sh 4|8 [run-dir]` pins the proven four-card
topology and 128 KiB oneCCL route, records source/binary/runtime/corpus hashes,
and runs each path in a fresh four-rank process. Two fail-closed details matter:

1. `--diagnostic` permits an individual failing Python process to exit zero;
   the generated summary is the result authority.
2. A custom `MWIDTH_PATHS` list suppresses the default summary. A future
   Option-4 runner must explicitly fail if any required row or summary is
   absent.

The single wide BF16 `[4,4096]` collective is prohibited. It corrupts 427,072
elements across the 87 reductions on every rank in eager and graph modes. M4
and M8 must keep segmented `[2,4096]` collectives until a separate repair passes
its own eager and 70-replay qualification.

### Fixed-address and command-list assets

What exists:

- XPUGraph fixed-address capture/replay in the M2 and M-width workers.
- The persistent-K-step patch
  `patches/deepseek-v4-persistent-kstep-a681-to-5a180e5.patch`, which advances
  token, position, slot mapping, attention metadata, and compact top-1 inside
  one worker turn.
- The bounded native-K2 patch
  `patches/2026-07-19-native-k2-single-submission.patch`, which wraps the raw
  two-step path in vLLM graph machinery, uses live fixed attention/KV buffers,
  and replaces host winner gathering with a fixed TP pair bank, SUM reduction,
  and device argmax.

What is missing, and therefore must be built first:

- no checked-in C++/SYCL compute command-list builder loads kernel modules,
  binds fixed arguments, appends decoder compute kernels to a regular
  `ze_command_list_handle_t`, closes the list, and replays it;
- no checked-in decoder-wide address/ABI manifest or state-reset image format;
- no hot-loadable kernel registry that exposes the qualified MHC, attention,
  dense, MXFP4, routing, and sampling kernels to such a builder.

Do not describe XPUGraph or the native-K2 `CUDAGraphWrapper` as that missing
native builder. They are valuable oracle and lifecycle prototypes.

The builder cannot assume that incumbent PyTorch operators expose
`ze_kernel_handle_t`. They do not. Phase 0 must qualify an explicit binding
stack before `M1AttentionBoundaryV1` is buildable:

1. **Queue ownership:** obtain the current PyTorch XPU rank's native Level Zero
   immediate-list/queue identity through a guarded C++ interop shim. V1 must
   record and replay on that same in-order path; it must not create a second
   unsynchronized queue.
2. **Named recording backend:** use
   `sycl::ext::oneapi::experimental::command_graph` in queue-recording mode.
   After all kernels are warmed, create the graph for the current context and
   device, call `begin_recording(current_queue)`, invoke the exact fixed-address
   launchers once, call `end_recording`, and finalize an executable graph owned
   by the decoder. PTI must show that one executable replay maps to one
   `zeCommandListImmediateAppendCommandListsExp` boundary with no intervening
   direct immediate appends. If this installed SYCL/runtime combination cannot
   record every required launcher into one executable graph, Phase 1 is
   blocked. A sequence of ordinary queue submissions is not a substitute.
3. **Queue-explicit SYCL kernels:** lift the exact incumbent C++/SYCL launch
   body into an internal `record(sycl::queue &, FixedArgs const &)` entry point
   without changing the public torch operator. Calling it is valid only between
   `begin_recording` and `end_recording`. MHC starts from
   `csrc/xpu/mhc/xe_2/mhc_pre.cpp::mhc_post_pre_m1_out` and its pinned source
   hash.
4. **Triton kernels:** warm the incumbent callable first, record that exact
   cached dispatch on the same queue, and save its SPIR-V/module hash, kernel
   name, launch geometry, scalar packing, and pointer argument order in the
   manifest. V1 needs this for `xpu_qnorm_rope_kv_fp8_insert` and split sparse
   attention. Any compilation during recording fails the build; a recompiled
   module is a new identity and repeats parity.
5. **oneDNN projections:** recreate the incumbent primitive descriptor and
   attributes exactly, then execute it on a oneDNN SYCL interop stream backed
   by the recorded queue between `begin_recording` and `end_recording`. No
   weight layout, LDB, scratchpad, post-op, or primitive-selection change is
   allowed. If the finalized graph omits or separately submits any oneDNN
   kernel, V1 is blocked; do not substitute the rejected prepack or a new custom
   GEMM.
6. **Capture-safe submission:** a minimal nested-list probe must show that one
   guarded custom op can append the closed V1 list while the surrounding
   vLLM PIECEWISE graph is captured and replayed, with no eager graph break and
   no host synchronization. If Intel/PyTorch interop cannot provide this, the
   boundary must be enlarged to the whole decoder transaction; 43 eager calls
   are not an admissible fallback.

The Phase-0 output is `kernel-abi-v1.json`: exact module paths/hashes, kernel
symbols, argument descriptors, launch geometry, oneDNN primitive descriptors,
queue identity, and ownership/lifetime rules. Phase 1 does not start until
this manifest exists and every listed kernel passes a one-operation bitwise
probe against its incumbent torch call.

### IPC and event assets

`scripts/bench-tp4-level-zero-ipc-events.py` is a self-contained ctypes Level
Zero proof. It creates context-wide IPC+host-visible event pools, preserves the
entire opaque 64-byte handle while substituting the SCM_RIGHTS-duplicated FD,
imports peer pools, and appends seven one-shot signal/wait stages to an
asynchronous immediate list.

`scripts/bench-tp4-ipc-event-max-token.py` adds persistent IPC workspaces and
uses the external vLLM callable
`broker_tp4_ipc_handles(socket_path, rank, world_size, memory_fd,
allocation_offset, memory_words, event_fd, event_words)` to exchange handles.
It proves exact changing winner/tie behavior. Seven pair exchanges improve from
`1,484.5065 us` to `184.7965 us` at the slowest rank, and delayed-rank testing
proves that peer waits are real.

The lifecycle restriction is mandatory: the two-slot reset/reuse protocol
hung. Only one-shot event slots followed by pool retirement are qualified.
The external broker module and its test are not snapshotted in this repository;
the callable interface and standalone ctypes broker are the durable repo
assets. Before decoder integration, snapshot or reimplement the broker in the
new isolated decoder tree and qualify its teardown independently.

The old integrations are negative evidence:

- direct producer/all-reduce/MHC submission saves only `0.109546 ms/cycle`
  after the ordinary comparator is also captured;
- the fixed M8 target builder saves only `0.256 us/cycle` after capture;
- the one-shot M7 IPC+DPAS bundle improves its isolated block by `0.994 ms`
  but falls to `67.227723 tok/s` against the `80.820052 tok/s` record because
  event reservation, wrapping, and an eager break remain in the endpoint.

## Target architecture

```text
vLLM control plane
  loader + weight ownership + API + request validation + prefill
  qualified eager/PIECEWISE oracle + fallback + lifecycle authority
                         |
                         | fixed address/weight/state manifest
                         v
Option-4 decoder, one process per B70 rank
  identity verifier -> module registry -> command cache
  ingress mailbox -> regular L0 command list(s) -> egress mailbox
       |                    |                      |
       |               TP4 IPC events             +-> token/state parity taps
       |               and qualified ring
       +-> fixed KV/MHC/router/spec state
```

### Control-plane contract

vLLM owns:

- safetensor/model loading and the original model revision identity;
- prefill, initial KV and MHC state construction, API behavior, and unsupported
  request fallback;
- allocation of persistent buffers, or export of their Level Zero IPC handles;
- the oracle run used to create immutable boundary packets;
- final fallback if identity, exactness, lifecycle, or shape checks fail.

The decoder is eligible only for one active request, fixed TP4+EP4 topology,
greedy sampling, the unchanged K160 revision/quantization, supported context
buckets, and an explicitly qualified width in `{1,2,4,8}`. Grammar, penalties,
logprobs, LoRA, encoder inputs, unsupported sampling, or mutable addresses fail
closed to vLLM.

### Decoder runtime layers

The implementation should be a new isolated tree, not edits directly in the
active vLLM/XPU source trees. The proposed eventual module layout is:

```text
option4-decoder/
  include/option4/
    abi.h                 fixed dtypes, shapes, addresses, aliases, kernel ABI
    identity.h            model/pack/runtime/topology/cache key
    buffer_layout.h       ingress, layer scratch, KV/MHC, egress, reset images
    kernel_binding.h      SYCL/Triton/oneDNN binding variants and fixed args
    command_cache.h       build/close/replay/retire state machine
    parity.h              boundary IDs, hashes, bitwise comparison records
  src/
    l0_context.cpp        driver/device/context/regular-list ownership
    xpu_current_queue_interop.cpp  guarded current-PyTorch-queue append path
    identity.cpp          fail-closed identity and address checks
    module_registry.cpp   exact module/primitive load and kernel binding
    bindings/             queue-explicit SYCL, Triton SPIR-V, oneDNN adapters
    command_cache.cpp     regular list construction and replay
    state_reset.cpp       pristine snapshots and epoch-safe restore
    ipc_event_broker.cpp  one-shot request-lifetime pool/FD lifecycle
    parity_runner.cpp     oracle/candidate boundary capture and comparison
    transactions/
      m1_attention_boundary.cpp
      m1_ffn_moe_boundary.cpp
      m1_tp4_boundary.cpp
      m1_decode_cycle.cpp
      m8_verify_cycle.cpp
      spec_accept_commit.cpp
  tools/
    validate_manifest.py
    inspect_command_cache.py
    compare_parity_packet.py
```

Each command-cache key must include at least:

- model repository and exact revision;
- quantization/pack format and per-rank pack hashes;
- kernel source hash, AOT module hash, ABI version, and compiler flags;
- driver, Level Zero loader, compute-runtime, oneCCL/transport identity;
- physical BDF/topology/rank mapping;
- width, context bucket, block size, KV dtype, and all fixed shapes;
- every input/output/scratch/weight address and alias declaration;
- command-list recipe version and event-pool generation.

Any mismatch rebuilds or rejects the list. It must never silently reuse a list
after vLLM reallocates a tensor.

### State and lifecycle

Use an explicit state machine:

```text
COLD -> MODULES_LOADED -> WARMED -> BUILT -> PARITY_QUALIFIED -> ARMED
  ^                                                        |
  +---------------- DRAINED <- RETIRING <- replay failure -+
```

- `WARMED` means every kernel variant and oneCCL/IPC path has executed outside
  any scored or served request.
- `BUILT` means arguments and addresses are immutable and the regular command
  list is closed.
- `PARITY_QUALIFIED` requires the gates below for that exact cache key.
- A request gets a fresh logical epoch and one-shot event range. Events are not
  reset or reused under the currently qualified protocol.
- Pristine reset images cover KV metadata, the KV slots the test may touch,
  MHC residual/post/combination state, router scratch, compressor state,
  sampling state, and speculative accept/rollback state.
- Retirement waits for device completion, closes imported handles, retires the
  pool, and only then permits address reuse.

### Hot-cycle launch inventory and command ownership

The initial arithmetic stays byte-for-byte identical. “Fusion” below means
co-ownership in one closed command list unless a separately exact arithmetic
fusion already exists.

| Hot work | Current multiplicity/evidence | First command-list owner |
| --- | ---: | --- |
| MHC fused post/pre | 85; 2.912528 ms/token | Entry/exit of attention and FFN boundary lists. Do not change SG16/WG256/BLOCK_N12 arithmetic. |
| Attention QK/LSE | 43; 1.158989 ms/token | M1 attention-boundary list, after exact Q/K preparation. |
| Attention PV | 43; 0.300611 ms/token | Same attention-boundary list. |
| Input/Q/K norms, RoPE, KV insert | 43-family plus residual norms | Same attention-boundary list using the already-qualified fused QNorm/RoPE/KV insertion where applicable. |
| Dense WQA/WKV, WQ_B, wo_a, WO_B | 43 each | Same attention-boundary list; retain the incumbent oneDNN/W8A16/BF16 primitive and accumulation order. |
| Router select/normalize | 40 non-hash routed layers plus hash-layer route handling | M1 FFN/MoE boundary list; preserve exact top-k/tie/normalization and hash policy. |
| Routed MXFP4 | 86 GEMMs; 3.485 ms/token | Same FFN list; retain M1 N64/GRF256/DPAS/scale/rounding order. |
| Route/remap, clamp/SwiGLU, gather/scatter | 1.842 ms/token family | Same FFN list using the already-promoted slot-direct path; remove metadata round trips, not arithmetic. |
| Shared expert gate/up, activation/quant, down, merge | 43 | Same FFN list; retain exact clamp-at-10 and FP8 scale/value semantics. |
| TP4 reductions | 87 per M1/M2/M4/M8 cycle shell | Phase 3 producer/reduction/consumer list. M4/M8 remain segmented M2. |
| LM head, sharded top-1, sampling | once/token | Whole-cycle list; exact rank-order/tie behavior and fixed pair bank. |
| Position/length/slot/block-table metadata | once/token or once verify cycle | Whole-cycle ingress; use device-resident updates proven by native K2. |
| Spec prepare, target verify, accept/rollback/commit | once speculative cycle | M8/spec list after M1 qualification. |

Sampling remains part of the inventory even though greedy sharded top-1 is
small: if it stays host-scheduled, it recreates the framework turn Option 4 is
supposed to remove.

## Exactness and vLLM parity mode

### Boundary contract

Parity mode runs the qualified vLLM implementation and the decoder from the
same pristine state, then compares every declared boundary. Required M=1
boundaries are:

1. input token, position, sequence length, slot mapping, block-table slice,
   and active context length;
2. MHC `residual_out`, `next_post_mix`, `next_comb_mix`, and `layer_input`;
3. norm outputs and projected Q/K/V-family tensors;
4. RoPE outputs, KV payload bytes/scales, and touched KV addresses;
5. QK scores/LSE and PV output;
6. each dense projection output at the oracle rounding boundary;
7. router scores, selected expert IDs, normalized weights, and compact route
   metadata;
8. routed GEMM1, clamped activation, GEMM2, direct weighted gather/scatter,
   shared-expert result, and merged FFN partial;
9. each local TP partial and reduced tensor;
10. logits shard, compact `(score, token)` pair, chosen global token, and tie
    decision;
11. final KV/MHC/router/sampling state and the next ingress metadata.

Compare integer, BF16, FP16, FP32, and FP8 tensors bitwise. Compare layouts,
strides, storage offsets, fixed addresses, aliases, and untouched guard regions
as well as values. NaNs require identical bit patterns and positions. Top-k and
argmax gates must include ties, duplicate routes, all-local/all-remote EP
patterns, zero/nonuniform weights, and boundary expert IDs.

### Gate matrix for every increment

Every phase is independently admitted in this order:

1. **Static identity gate:** validate manifests, blob hashes, module hashes,
   address alignment, alias declarations, fixed shapes, and cache key. No GPU
   timing claim is possible from this gate.
2. **Changed-input eager oracle gate:** at least 40 deterministic changed
   cases per physical B70 for each new boundary. This tests values; mutating a
   source copied inside an already captured XPUGraph is not accepted as a
   changed-input graph test.
3. **Real captured-tensor gate:** use the M1, M2, and genuine sequential M4/M8
   corpora applicable to the increment. A new append-only corpus is required
   only for boundary tensors absent from the existing packets. Existing corpus
   files are never rewritten.
4. **Fixed-address replay gate:** 70/70 exact replays in a fresh four-rank
   process, with explicit checks at replay positions 28 and 58 and guard-region
   validation. Control and candidate run in separate clean processes when
   collective state could leak.
5. **Four-card gate:** every physical B70 passes. Headline time is the median of
   the per-sample slowest rank; improvement also has to be nonnegative on every
   card.
6. **Submission-structure gate:** report literal submits, immediate kernel/copy/
   signal/wait appends, host synchronizations, event queries, and graph breaks.
   A claimed launch-collapse increment must reduce the named boundaries; a
   timing delta alone is insufficient.
7. **Endpoint exactness gate:** after model integration only, use fresh
   cache-zero public/development canaries, exact token IDs, EOS behavior, and
   rollover coverage. Cold-capture warmup is outside and before the suite.
8. **Same-binary performance gate:** compare default-off control and candidate
   with identical binary, model, runtime, prompts, and request order. Use
   `1000 * post_ttft_s / (completion_tokens - 1)` and report the established
   tokens-1-100 metric as well. The primary comparison is against
   `22.881408 ms/token` and a contemporaneous same-binary control.

No increment inherits a performance pass from a component gate. Savings are
not summed across phases; each new phase is remeasured against the last
qualified same-binary whole-cycle control.

## Phased increment ladder

The expected values below are engineering ranges, not promises. They overlap
and are explicitly non-additive.

### Phase 0: Native substrate and parity shell

Add the new `option4-decoder` tree described above with:

- Level Zero context/queue ownership and a regular command-list lifecycle;
- the current-PyTorch-queue interop shim and nested-list capture probe;
- immutable address/identity manifests;
- queue-explicit SYCL, warmed-Triton-SPIR-V, and exact oneDNN-primitive binding
  adapters plus `kernel-abi-v1.json`;
- parity packet reader/writer and guard-region checking;
- pristine state reset;
- request-lifetime one-shot IPC event-pool broker;
- a no-model adapter for the existing M1/M2/M4/M8 corpus schemas.

Expected endpoint EV: **0 ms/token claimed**. This is enabling infrastructure.
The substrate passes only if it can append, close, replay, destroy, and rebuild
a trivial witness list without address drift; append one multi-kernel test list
inside the surrounding captured vLLM graph with no graph break or host sync;
match each exported kernel/primitive bitwise to its incumbent call; and validate
every existing manifest without mutation. Failure of current-queue ownership,
Triton ABI export, oneDNN recording, or capture-safe nested submission is a
real blocker for Phase 1, not permission to add eager per-layer calls.

### Phase 1: M=1 attention-side boundary transaction — first buildable increment

Build `transactions/m1_attention_boundary.cpp` and the corresponding corpus
adapter/parity runner. Details are in the dedicated section below.

Measured whole-token EV: **unknown before the new boundary corpus and
same-binary gate**. The design/kill target is **0.50-0.78 ms/token**, yielding
approximately `22.38-22.10 ms/token`; no existing attention-boundary upper
bound supports calling that range expected. V1 retains the same device kernel
dispatches and can win only by removing immediate append, synchronization, and
framework edges. Spec-cycle transfer: the module/address/parity design
transfers directly to M8, while M8 attention kernels and timing require their
own exact gate.

### Phase 2: M=1 FFN/routed-MoE boundary transaction

Add `transactions/m1_ffn_moe_boundary.cpp` and bindings for exact router
normalization, promoted slot-direct N64 MXFP4 GEMM1, clamp-at-10 SwiGLU,
MXFP4 GEMM2, weighted gather/scatter, shared expert, and local merge. Start at
an MHC-produced FFN input and stop at the rank-local FFN partial before TP
reduction.

Reuse `scripts/bench-m1-direct-routed-moe.py` for route edge cases, but add a
content-addressed real boundary packet before integration. Do not retry GRF128,
N32/N128 M1, opaque prepack, deletion-only gather, paired GEMM1, recomputed
SwiGLU, or alternate accumulation order.

Expected incremental whole-token EV: **0.50-1.00 ms/token** from the
`1.832892 ms/token` non-GEMM above-ideal scope, capped by same-binary evidence.
Do not credit the `1.575916 ms` MXFP4 roofline slack unless dispatch or staging
actually changes. Spec transfer is medium: the transaction structure transfers,
but M8 uses N128 and different batching.

### Phase 3: TP4 producer/reduction/consumer ownership

Add `transactions/m1_tp4_boundary.cpp`, integrate the qualified oneCCL ring or
a separately qualified fixed TP4 transport, and connect the local attention/
FFN producer to reduction and the next MHC consumer without a Python/c10d or
host synchronization boundary.

The existing oneCCL event-chain source is a reference for dependency plumbing,
not a candidate to replay unchanged. It already failed at `0.109546 ms/cycle`.
The new transaction must co-own producer and consumer arithmetic or eliminate
materialization. M4/M8 keep segmented `[2,4096]` reductions. Resident polling,
cross-device atomics, binary-event reuse, and the corrupt wide collective stay
closed.

Expected incremental whole-token EV: **0.50-1.25 ms/token** against the
`2.746 ms/token` live collective allocation. Spec transfer is high because the
same 87 reductions and 85 MHC boundaries appear in the M8 corpus, but all M8
economics are reported per verifier cycle.

### Phase 4: Complete M=1 decoder transaction

Add `transactions/m1_decode_cycle.cpp`. Stitch qualified attention, FFN, and
TP4 fragments into the smallest possible number of regular command lists; move
position/length/slot updates, LM-head sharded top-1, greedy sample, state
advance, and next-token ingress entirely inside the transaction. vLLM calls one
guarded replay interface per emitted token and receives the committed token and
status mailbox.

Expected target: converge toward the empirical **20.825625 ms/token** ceiling.
The optimistic absolute ceiling is **19.446408 ms/token**. If the complete
transaction is slower than the qualified previous phase, keep the parity shell
and phase components but do not enable the full-cycle path.

### Phase 5: Fixed M=8 target-verifier transaction

Add `transactions/m8_verify_cycle.cpp`. Reuse the genuine sequential M8 corpus,
fixed M8 MHC, exact M8 compressor/router/W8A16/N128 paths, segmented M2
collectives, fixed target-input metadata, and sharded target top-1. Compare all
eight rows at every boundary to vLLM.

Known component EV: fixed M8 MHC has already measured **4.314321 ms/verifier
cycle** versus segmented M2 MHC calls. The incremental command-list EV is
unknown and must clear **0.50 ms/verifier cycle** on the slowest B70. Do not
convert the component number into emitted-token throughput without the measured
acceptance and complete wall cycle.

### Phase 6: Device-resident M=8 speculative cycle

Add `transactions/spec_accept_commit.cpp`. Own DSpark/EAGLE draft preparation,
target verification, rejection sampling/greedy acceptance, rollback, KV/MHC
commit, and next-cycle metadata without returning to Python between stages.
Keep the target model and its verification authoritative.

Expected EV: **unquantified until the predictor job is frozen and target-only
M8 economics are measured**. Admission still requires at least `0.50 ms` per
complete speculative cycle and a positive same-binary endpoint result. This
phase is where launch collapse compounds with the current `80.820052 tok/s`
record: reducing verifier/accept/commit wall time improves throughput at the
same accepted-token count, while a better predictor increases emitted tokens
per now-shorter cycle. The two effects multiply; neither may be inferred from
component acceptance or timing alone.

## First buildable increment in full detail

### Transaction boundary

Name: `M1AttentionBoundaryV1`.

Instantiate it for all 43 layers. `layer0` begins with the incumbent standalone
MHC pre path. `layer1` through `layer42` begin with the recurrent exact
`mhc_post_pre_m1_out` path, consuming the already-reduced preceding FFN output
in current-stream order. The fixed input contract includes that layer's input,
MHC state, attention/KV metadata, and immutable weights. The fixed output
contract is the rank-local BF16 WO_B partial immediately before the following
TP reduction, plus the updated KV and MHC state.

Append the incumbent operations in qualified oracle order:

1. for layer 0, exact standalone MHC pre; for layers 1-42, exact
   `mhc_post_pre_m1_out`, retaining all four saved outputs and aliases;
2. incumbent attention RMSNorm when it is not already part of the qualified
   MHC path;
3. incumbent input/query/KV norm and WQA/WKV projection boundaries;
4. incumbent fused QNorm/RoPE/KV insertion with exact BF16/FP8 stores;
5. incumbent WQ_B projection;
6. promoted split sparse QK/LSE;
7. promoted PV;
8. incumbent `wo_a` BF16 BMM and WO_B W8A16 projection;
9. write a one-BF16 completion witness and leave the rank-local WO_B partial at
   its declared fixed address.

The command list does not include the next TP reduction in V1. That avoids
repeating the closed reduction/MHC submission-only design and keeps the first
compute builder independent of the wide-collective blocker. Phase 3 absorbs
the producer/reduction/consumer boundary after the compute-list result is
qualified.

For isolated replay, the runner calls the closed list directly. For endpoint
integration, add one guarded custom-op branch at
`vllm/models/deepseek_v4/xpu/model.py::DeepseekV4DecoderLayer.forward` (the
current attention/MHC region is around lines 1334-1427 in the native-K2 source
identity). The op returns `residual`, `post_mix`, `res_mix`, the local WO_B
partial, and a status witness. The guarded caller then invokes the incumbent
`tensor_model_parallel_all_reduce` and resumes at the existing FFN MHC
boundary. Use the already-existing local/reduced seam in
`vllm/models/deepseek_v4/xpu/xpu_sparse.py::_wo_b` rather than mutating
`wo_b.reduce_results` globally.

The custom op is registered as graph-capturable with all mutations declared.
It appends V1 to the same current PyTorch XPU immediate list, whose in-order
execution supplies the ingress dependency; V1 does not invent a reusable
per-layer IPC event. Phase 0 must prove that this nested append is captured by
the surrounding PIECEWISE graph without an eager break. If it cannot, V1 is
not endpoint-buildable at this granularity and must not be called eagerly 43
times.

No kernel arithmetic, precision, workgroup geometry, accumulation order,
rounding boundary, attention tile, KV format, or model weight changes are
allowed in V1. The only intended changes are fixed ownership, argument binding,
command append order, and elimination of intermediate framework submission/
synchronization edges.

### Concrete files for the implementation agent

In the new isolated decoder source tree, add:

```text
include/option4/abi.h
include/option4/kernel_binding.h
include/option4/command_cache.h
include/option4/parity.h
src/l0_context.cpp
src/xpu_current_queue_interop.cpp
src/module_registry.cpp
src/bindings/sycl_binding.cpp
src/bindings/triton_recording_binding.cpp
src/bindings/onednn_binding.cpp
src/command_cache.cpp
src/parity_runner.cpp
src/transactions/m1_attention_boundary.cpp
tests/test_manifest_identity.cpp
tests/test_command_cache_lifecycle.cpp
tests/test_nested_list_capture.cpp
manifests/kernel-abi-v1.json
```

In this notebook repository, add new files only:

```text
experiments/deepseek-v4-flash-reap-xpu-b70/scripts/
  validate-option4-boundary-packet.py
  replay-option4-m1-attention-boundary.py
  summarize-option4-m1-attention-gate.py
experiments/deepseek-v4-flash-reap-xpu-b70/data/
  option4-m1-attention-boundary-<stamp>.json
experiments/deepseek-v4-flash-reap-xpu-b70/notes/
  <date>-option4-m1-attention-boundary-gate.md
patches/deepseek-v4-flash-xpu-b70/
  <date>-option4-native-command-list-v1.patch
```

Do not modify `replay-m2-cycle-corpus.py` or the existing validators. Use an
adapter so old evidence remains immutable.

### Corpus plan and exact gate

The existing M1 corpus is sufficient to validate the MHC input/output and alias
portion, but there is no neutral checked-in M1 replay worker; V1 must add an
adapter that calls the canonical MHC implementation, not the rejected compact
candidate. The M2 and genuine sequential M4/M8 corpora validate the common
manifest parser and independently regress the existing width-specific MHC
implementations. They do **not** execute or qualify this M1 attention command
list, its attention ABI, QK/LSE/PV, norm/RoPE/KV, or dense intermediates.
Claiming that they prove V1 would be incorrect.

Therefore V1 has two corpus layers:

1. **Mandatory existing-corpus regression:** validate the immutable M1, M2,
   sequential M4, and sequential M8 packets with their saved hashes. Add a
   neutral canonical M1 MHC replay adapter and qualify it for 70/70; retain the
   established M2/M4/M8 70/70 results and rerun them only when shared MHC or
   manifest-adapter code actually changes. These are regression gates, not V1
   attention evidence.
2. **New append-only `m1-attention-boundary-v1` packet:** during a future
   authorized oracle capture, record **all 43 layer instances** for each of two
   context buckets. Record layer 0's standalone-pre ingress separately from the
   42 recurrent post/pre ingresses, every boundary listed above, every
   layer-specific weight/address binding, fixed addresses/strides/aliases, KV
   before/after bytes and scales, local WO_B partial, and the exact module/
   runtime identity. Every instantiated list must appear at least once; an
   early/middle/late sample cannot qualify 43 address-specific lists. This is
   the only required model capture for V1. It is created beside, never inside,
   existing corpora.

On each physical B70 require:

- 40/40 changed-input eager cases for the individual canonical operations and
  V1 output;
- 70/70 static fixed-address V1 replays with zero bit mismatches at every
  boundary;
- exact guard bytes and untouched KV slots;
- fresh process per control/candidate, explicit warmup before capture, and no
  lazy compilation during capture;
- exact current-queue ordering under an injected `100 us * rank` pre-append
  skew, with the input producer still ahead of V1 on that same queue;
- zero host synchronization between list append and the completion witness;
- a lower effective boundary count than the qualified control.

### Timing and go/no-go

Measure three levels, always against a captured or native fixed-address control:

1. representative per-layer V1 command list, including current-queue append
   and the egress witness;
2. all 43 attention-side V1 invocations per token on the no-model boundary
   packet, with layer 0 reported separately, using the slowest-rank median;
3. same-binary full M=1 endpoint against both its contemporaneous control and
   `22.881408 ms/token`.

**GO** when all exactness gates pass, effective boundaries and host syncs fall
as declared, no physical card regresses, the full endpoint saves at least
`0.50 ms/token`, and candidate time is at most `22.381408 ms/token` on the
comparable metric. The planning band is `22.10-22.38 ms/token`.

**NO-GO for V1 integration** if any bit/address/alias differs, any cold-capture
work enters a scored request, a host sync remains inside the list, a card
regresses, or the endpoint saves less than `0.50 ms/token`. Preserve the
builder, corpus, patch, logs, and negative note. A V1 no-go does not revoke the
user's Option-4 commitment; it moves the next bounded build to the FFN/MoE
transaction while retaining the native substrate. Do not lower precision or
combine V1 with another unqualified phase to rescue the result.

## Risks and mitigations

| Risk | Consequence | Required mitigation |
| --- | --- | --- |
| Command-list batching removes host work but not device launch latency | Component looks architectural but endpoint is flat, as with the event chain and fixed builder. | Count device/host boundaries, include ingress/egress events in timing, require whole-token B-A-B, and never sum eager wins. |
| No checked-in native compute builder | The first agent may mistakenly extend XPUGraph again. | Start with `l0_context`, module registry, regular-list lifecycle, and explicit `zeKernel` bindings in a new tree. |
| Cold capture/JIT changes output | First served request can diverge. | AOT compile where possible; explicit unscored warmup; prohibit `ARMED` if any module compilation occurs during build/replay. |
| Fixed addresses become stale | Silent writes to recycled storage. | Hash every address/size/alias in the cache key; generation counters and guard regions; fail closed on any vLLM allocation change. |
| oneCCL wide geometry corruption | M4/M8 target becomes inexact. | Keep segmented `[2,4096]` collectives; isolate any repair behind a new four-card eager+70-replay gate. |
| IPC event reuse deadlock | Cross-rank hang or teardown failure. | One-shot request-lifetime events, bounded slots, explicit retirement; do not reset/reuse binary events. |
| Cross-device progress or rank skew | False-ready consumption or deadlock. | Context-wide pools, full opaque handle preservation, delayed-rank tests, completion witnesses, timeout and fallback. |
| Exact arithmetic hidden inside oneDNN/Triton dispatch | Rebinding or layout changes accumulation order. | Reuse exact compiled modules and arguments; compare every intermediate bitwise; no prepack/layout substitution in V1. |
| Context length changes launch geometry | A supposedly fixed list becomes invalid or over-dispatches badly. | Key lists by qualified context bucket or use exact masked fixed geometry; parity/timing each bucket independently. |
| Alias or reset mismatch accumulates over tokens | First replay passes but later tokens drift. | Preserve captured alias topology, snapshot recurrent state, test rollover positions 28/58 and long chains, verify untouched regions. |
| Component gains overlap | Ladder projects beyond physical ceiling. | Treat phase EVs as non-additive; rebaseline after every phase; cap expectations at the K2-derived projected 48-51 tok/s nonspec ceiling. |
| Spec acceptance changes | Apparent speed comes from quality loss. | Require identical target tokens/accept decisions and unchanged target verification; report accepted tokens and complete wall cycle separately. |
| Concurrent EAGLE work is disturbed | Lost training progress or invalid shared state. | Use no GPU/model/service commands during design; future runs require explicit orchestration and isolated paths/devices. |

## Honest ceiling and M=8 compounding

The nonspeculative ceiling for this program is not 62 tok/s from subtracting
all theoretical kernel slack. The only end-to-end architectural de-risking is
the warm-captured K2 experiment:

- empirical fixed-overhead extrapolation: `20.825625 ms/token`, **48.0178
  tok/s**;
- optimistic deletion of the full `3.435 ms/token` bucket: `19.446408
  ms/token`, **51.4234 tok/s**.

Those are the honest 48-51 tok/s nonspec bounds until a fuller decoder measures
otherwise. Regular command lists still contain kernel dispatches, so MHC,
attention, and MoE above-ideal time cannot all be counted as recovered.

For the `80.820052 tok/s` M=8 speculative record, launch collapse has two
separate effects:

1. the same fixed-address target transaction reduces the M8 verification and
   TP4 coordination time while target arithmetic remains exact;
2. device-resident prepare/accept/rollback/commit removes framework turns
   around that verification.

If the EAGLE or another frozen predictor raises accepted tokens per cycle, its
gain multiplies with the shorter exact target cycle. If acceptance is
unchanged, only the cycle-time reduction counts. Report target verifier time,
draft time, accept/commit time, emitted tokens per cycle, and full wall tok/s;
never project the exact `4.314321 ms` M8 MHC component saving directly into a
new endpoint record.

## Immediate handoff checklist

The next implementation agent can begin Increment 1 without reopening the
architecture decision:

1. Create a new isolated `option4-decoder` source tree; do not modify the active
   vLLM/XPU trees.
2. Implement `l0_context`, immutable identity/address manifest, module registry,
   regular command-list cache, state reset, and parity records.
3. Bind only the exact incumbent M1 MHC and attention modules for
   `M1AttentionBoundaryV1`.
4. Build the existing-corpus adapters and prove the M1/M2/M4/M8 manifests are
   consumed without mutation.
5. Stop before GPU execution until orchestration assigns cards and confirms the
   EAGLE job is isolated.
6. On authorization, run changed-input and 70-replay no-model gates, create the
   append-only attention boundary packet, then run the same-binary endpoint
   gate.
7. Preserve patches, hashes, commands, outputs, and negative evidence. Leave
   every selector default-off until full parity and the `0.50 ms/token` endpoint
   gate pass.

## Source evidence

- `plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md`, Option 4
- `experiments/deepseek-v4-flash-reap-xpu-b70/ORCHESTRATOR_HANDOFF.md`, section 12.C
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m2-real-cycle-corpus-and-replay.md`
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m4-m8-fixed-mhc-component-gate.md`
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sequential-mwidth-verifier-and-predictor-pivot.md`
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-level-zero-ipc-event-transport.md`
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-19-native-k2-single-submission-option4-gate.md`
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-19-nospec-m1-bandwidth-roofline-profile.md`
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-nospec-unitrace-attribution-crosscheck.md`
- the three `2026-07-20-nospec-m1-kernel-efficiency-iteration*.md` notes
