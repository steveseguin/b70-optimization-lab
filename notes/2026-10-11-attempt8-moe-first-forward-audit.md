# Attempt 8: first MoE forward, memory ownership and repair plan

**October 11, boundary-window verdict update:** all four raw router tensors
were 640 signed `-1` padding IDs; native alignment/remapping had not run.
The V2 dummy batch intentionally marks every row as padding, and the pinned
native aligner lacks the negative-ID guard already present in the older lab
runtime. Hypothesis 1 now has an observed input and a specific unsafe-write
mechanism; rank-specific/global-local/table versions of hypothesis 4 are not
supported by this refusal. The production router compatibility fix is applied
and passes 143 CPU tests; its next native proof retains the strict boundary.
[Evidence, exact source lines, identity argument and commands](2026-10-11-moe-boundary-caught-router-ids.md).
The original audit below is preserved as the pre-boundary assessment; its
“unknown” verdict and “no patch applied” statements describe that earlier state.


**The cause is still unknown. The first investigation should isolate a bad
device write in the production routing/alignment/workspace path, with native
dispatch failure and VM closure as a close competing explanation. An
unregistered mmap PLE row is not the leading explanation.** No saved trace
identifies the faulting operator or associates its address with an allocation.
The patch sketches below are unverified; no runtime patch was applied.

This audit was CPU-only on `steve-b70s`, with nice 19 and
`OMP_NUM_THREADS=2`. No Torch import, accelerator enumeration, device open,
container operation, server, systemd operation, endpoint access, signal,
host-setting change or native test was performed. No scratch was created.
The fourth-incident halt remains in force. This document designs future work;
it neither launches nor queues it.

## Evidence and source identity

Let **P** mean
`experiments/qwen38-flash-next-fp8-b70/reopen-20261008/`, **O** mean
`P/overlay/vllm/`, and **B** mean `vllm/` at base commit
`ced6857afa0ea7b2e3f0846a62e1394e90f15607`. All source references below use
those prefixes and one-based line numbers. B files were read with `git show`
from `/home/steve/src/lumnus-20261008/vllm`; they are not guessed replacements
from another installed version. O overrides B wherever the manifest says so.

- [Incident timeline](2026-10-11-attempt8-fourth-incident.md),
  [saved evidence index](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/index.json),
  [container log](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/container.log),
  [kernel log](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/kernel-window.log).
  All **31 indexed saved files** were rehashed successfully.
- [Manifest](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-manifest.json)
  SHA256 `daf50d2391549a9fb5c03ee2cf3a69e763cc44e621fdaf35e4b06529c7142b69`:
  all **50 replacement files** match. The image is
  `vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.
  vLLM 0.30.0+xpu, Torch 2.13.0+xpu, Triton 3.7.2+xpu,
  vllm-xpu-kernels 0.1.14.1. The compiled extension's exact native source/build
  correspondence is not established by a Python overlay hash.
- [Attempt 6 run](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt6/),
  [attempt 7 run](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt7/),
  [validation history](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md)
  and [attempt 7 ordering audit](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-attempt7-ordering.md).
  Attempt 6 stops during allocation: 89,975,808,000 + 196,608,000 bytes
  exceeds its 90 GB guard (`server.log:219,300`). It is not a forward control.
  Attempt 7 reaches the same profile phase and the same missing-config warning
  (`server.log:542`), then fails. Both exit 1 without an OOM kill. Their
  application receipts record 47 replacements; attempt 8 has the later
  teardown overlay and 50. They are not identical-runtime replicates.
- The requested `P/evidence/exit-probes-20261010/probe-first-forward-20261010c`
  directory does not exist in this checkout. The passing evidence is in
  [P/runs/probe-first-forward-20261010c](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/probe-first-forward-20261010c/),
  with [receipt](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/probe-first-forward-20261010c/receipt.json)
  and `stages.jsonl`. The evidence-directory `...10b` is the earlier refusal,
  not the passing run. Probe manifest `e00bb55d...` differs from attempt 8's
  manifest; do not claim the manifest hashes match. The historical manifest at
  repository commit `d05cabc14df9b4ca3b784eb3f02b605c1320da23` has that probe
  hash; **all 50 replacement-file hashes match attempt 8**. The retained probe
  script also matches its receipt's source hash. Support/authorization identity
  and the executed call path still differ.

All four ranks finished loading; rank 0 reports completion at 00:56:45 UTC.
At 00:56:50 all four cards fault on CCS. Container line 348 is the first
logged MoE configuration lookup, **not a kernel-entry/completion trace**.
Controller cancellation/SIGINT completion follows the first fault. Later
segfault reports, `VllmWorker-1` death and engine failure cannot establish
which native event occurred first. Timed-out jobs identify four workers,
including host PID 1280817, not that PID alone.

The 110 detailed fault records all say `AccessType: 1` (87 at level 2, 23 at
level 3). Upstream Linux v7.0 calls that **WRITE**. Its fault-service code
returns `-ENOENT` for a closed VM; a missing VMA in that function instead
returns `-EINVAL`. These are upstream interpretations, not a verified audit
of Ubuntu's running `7.0.0-39` binary. Thus `-ENOENT` does not prove a missing
host registration, and the write field weakens a direct weight-read theory.
[Access types](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/xe/xe_pagefault_types.h),
[fault service and deferred reporting](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/xe/xe_pagefault.c#L146-L197).

## Static call path to the first routed-expert GEMM

This is the path selected by the saved configuration and source, not a claim
that every asynchronous kernel below completed. Native operator internals and
actual pointer values were not captured in attempt 8.

| Step | Exact source and behavior |
| --- | --- |
| Worker and profiling | O `v1/worker/xpu_worker.py:24` inherits `Worker`; O `v1/worker/gpu_worker.py:542–545` calls `profile_run()` even with explicit 376,569,856 KV bytes/rank. |
| Dummy shape | O `v1/worker/gpu/model_runner.py:220–221,939–958` uses `max_num_batched_tokens=64`, `max_num_seqs=1`, `_dummy_run(64, skip_attn=True, is_profile=True)`. At `776–844`, uniform decode is false, giving one dummy request with 64 tokens, followed by `execute_model(..., dummy_run=True)`. This is not a two-token MTP decode or graph replay. |
| Model invocation | O runner `1790–1840` skips attention metadata for this profile; `1873–1881` builds model inputs; `1918–1928` skips `b70_pre_forward`; `1964–1994` calls the raw model under forward context. No PLE mmap fetch is scheduled here. |
| Model to layer | O `models/qwen4_exp/nvidia/model.py:1025–1053` (conditional wrapper) calls `language_model.model`; causal wrapper `703–719` also leads to `Qwen4ExpModel.forward:491`. The layer loop at `525–545` calls decoder `275–334`; hyperconnection/PLE/attention work precedes `self.mlp(block_input)` at `329`. The log is insufficient to assign the fault to the GEMM rather than that preceding work. |
| MLP to MoE runner | O model `161–172` inherits `Qwen3NextSparseMoeBlock`; B `model_executor/models/qwen3_next.py:217–237` constructs `FusedMoEFactory`, and `239–259` calls it. B `model_executor/layers/fused_moe/layer.py:88–146` constructs a `MoERunner`, not the legacy functional probe path. Sequence-parallel MoE is explicitly rejected by O model `166–168`. |
| Gate and routing | B `model_executor/layers/fused_moe/runner/moe_runner.py:681–731` enters its custom-op wrapper (`116`/`153`), then `_forward_impl:862`, gate projection `905`, `_apply_quant_method:916`; that method's `626–638` calls `router.select_experts` then `routed_experts.forward_modular`. B `router/fused_topk_router.py:80–113,156–171` produces top-k IDs/weights. |
| Quantized expert wrapper | O `model_executor/layers/fused_moe/routed_experts.py:1175–1209` calls the FP8 method; O `model_executor/layers/quantization/fp8.py:852–875` passes weights, scales through the kernel object, 512 global experts and `layer.expert_map`. The latter is the canonical -1/local-ID map (`routed_experts.py:216–225`). |
| Preparation and workspace | O `fused_moe/modular_kernel.py:1733–1760` delegates to modular `apply:1453`, `_prepare:1212–1299`, `_fused_experts:1301–1381`. The saved log line **227** selects `MoEPrepareAndFinalizeNoDPEPModular`; B `prepare_finalize/no_dp_ep.py:57–78` quantizes locally. There is no token all-to-all/all-gather in this prepare path: EP4 ownership does not turn M=64 into M=256 here. |
| Quantization | B `fused_moe/utils.py:223–246,361–375` calls block FP8 quantization; B `quantization/utils/fp8_utils.py:554–680` allocates quantized activations and scales and dispatches the platform quantizer. This already submits device work before the config warning. |
| Config and assignment | O `fused_moe/experts/triton_moe.py:293–307` selects config using **logical E=128**, M=64, N=640 in the filename, block [128,128]. Lines `333–345` call O `fused_moe/fused_moe.py:1552–1598` with **global E=512** for alignment because `expert_map` is present. B `fused_moe/moe_align_block_size.py:74–101` allocates sort buffers, calls `_moe_C.moe_align_block_size` via B `_custom_ops.py:2256–2273`, then remaps `expert_ids = expert_map[expert_ids]`. This native alignment kernel and the remap precede w13. |
| First routed-expert GEMM | O `experts/triton_moe.py:387–409` calls `invoke_fused_moe_triton_kernel`; O `fused_moe.py:768–918`, especially `871–917`, launches `fused_moe_kernel:299`. It quantizes/reads A, reads w13 through an optional offset table, reads FP32 scales, writes BF16 C. Bias is absent and routed weighting is false for w13. |
| Following work, not proven reached | Activation, second quantization and w2 at O `experts/triton_moe.py:476–529`, reduction/finalization and rank reduction. MTP proposal occurs later in O runner `862–897`, after the target forward returns. |

The warning at O `fused_moe.py:1175–1180` says that a tuning file is absent.
`1430–1459` then selects `get_default_config`. For the recorded M=64,
FP8 blocks [128,128], absent a batch-invariance override, `1328–1363` gives
M/N/K tiles **16/128/128**, group M=32, four warps, three stages, split K=1.
It stays on the same Triton kernel; quantized weights explicitly disable tensor
descriptors at `799–805`. The actual compiled specialization was not saved.
Do not interpret the warning as proof that an incompatible workspace was used.

## Pointer and ownership census

Every worker is spawned and initializes its device before loading
(O `v1/executor/multiproc_executor.py:680–688`, O `xpu_worker.py:42` onward).
Tables contain addresses computed **inside that worker**, not addresses sent
from rank 0. A Python tensor's `device` label is not proof of native USM kind,
residency, registration or queue-context compatibility. Process address spaces
and device VMs require their own valid mappings; copying a pointer integer or
opening the same mmap file elsewhere does not establish one. Shared USM within
a runtime context can be accessible to several devices, but that cannot be
assumed across these four processes. No per-rank native mapping query was saved.

### All eleven pointer arguments of `fused_moe_kernel`

The signature is O `fused_moe.py:299–311`; launch arguments are `873–883`.
Rows below distinguish actual w13 dereferences from optional/later arguments.

| Pointer | Allocation, ownership and intended backing | Dereference and bounds |
| --- | --- | --- |
| `a_ptr` | Quantized hidden states, expected [64,2560] FP8. B `fp8_utils.py:594` allocates on input device; NoDPEP preparation supplies it. Rank-local device storage, not mmap/UVA. | A loads at O `fused_moe.py:537–542`; 64 rows with token mask, K=2560. BF16 input, PLE and routing logits are not directly passed here. |
| `b_ptr` | Resident w13 compact tensor. O `fp8.py:601–606` calls O `q38_expert_placement.py:77–120`; resident allocation at `95`, under the worker's device context. Layer-0 resident counts ranks 0–3: 101/99/98/97, shape [resident,1280,2560], FP8. | Base may refer to device storage **or jump into host storage via table offsets**. B loads at `534–542`. w2 later uses [resident,2560,640]. |
| `b_table_ptr` | `_q38_base_table`: 128 signed int64 offsets, created on CPU then copied to resident device at O placement `103–105`. Each rank owns its device copy. If absent, B is passed as a placeholder and not read as a table. | `425–428` loads local expert ID then table entry. No upper-bound check exists in the GEMM. `-1` indexes entry zero before `431–447` returns after writing zeros. A positive ID >=128 could read beyond this table. |
| host allocation reached through B | `_q38_host_cpu` is separate contiguous pinned CPU FP8 storage, O placement `88–100`; `_q38_host_storage` is its XPU alias, retained at `109–110`. Layer-0 host counts 27/29/30/31. Allocation occurs in each worker; view creation explicitly selects `resident.device` and verifies matching device at `98–102`. | Each entry represents `B + signed_offset * itemsize`, modulo address width, targeting that rank's resident or host row. Host pointer is **indirect**, not a separate kernel argument. Python pin/device checks do not attest native indirect residency. |
| `c_ptr` | `intermediate_cache1`, [64,10,1280] BF16 view into workspace2, O `experts/triton_moe.py:324–330`. O `modular_kernel.py:1118–1195` obtains simultaneous workspace slices; B `v1/worker/workspace.py:116–140,199–209` allocates rank/device-local uint8 storage, with aligned disjoint slices. | Writes at O `fused_moe.py:615` and `write_zeros_to_output:45–61` for nonlocal experts. C1 needs 1,638,400 bytes. C3 later uses the same workspace2, [64,10,2560], 3,276,800 bytes. This is a concrete WRITE candidate. |
| `b_bias_ptr` | `None`: placement validation forbids bias (O placement `56–59`). | No bias load, `HAS_BIAS=false`. |
| `a_scale_ptr` | Expected [64,20] FP32 device allocation, B `fp8_utils.py:618`; returned with quantized A. 5,120 bytes, owned by this rank/call. | Block-scale reads at O `fused_moe.py:494,550–552`, masked by valid tokens. w2 later has [640,5]. |
| `b_scale_ptr` | w13 scales [128,10,20] FP32, 102,400 bytes, **full logical local expert count**, not compact resident count. O `fp8.py:643–660`; loaded and replaced at `702–721`. Device storage; generic offload selector does not select these scales. w2 [128,20,5], 51,200 bytes. | Local expert index and block strides at `496–498,553`. Host experts still use device-resident scales. A bad local ID threatens scales as well as the offset table. |
| `topk_weights_ptr` | **None for w13**, explicitly O `experts/triton_moe.py:394,398`. Later w2 receives rank-local [64,10] FP32 route weights allocated by B `router/fused_topk_router.py:92–94`. | No w13 dereference; later weighted GEMM uses O `fused_moe.py:599–602`. |
| `sorted_token_ids_ptr` | Rank-local device int32 array from B `moe_align_block_size.py:74–83`, written by native align/sort. At 640 routes, E=512, block M=16: capacity **8,320** entries, 33,280 bytes. | O `fused_moe.py:407–423` reads padded blocks below the reported padded-token count. Expected valid route indices 0..639; padding uses 640. Neither the contents nor actual padded count survives in the incident evidence. |
| `expert_ids_ptr` | Native alignment output, then separate `expert_map[expert_ids]` device result in B align `85–101`. Capacity **520** int32 entries at these shapes. Each process maps global experts to its 128 local logical experts or -1. | O `fused_moe.py:425`: active entries must be -1 or 0..127. Entire-array remap also reads the alignment output's unused tail; native initialization of that tail is an ABI requirement, not demonstrated by the Python source. |
| `num_tokens_post_padded_ptr` | One device int32, B align `88`, written by native alignment. | O `fused_moe.py:407–409` controls which blocks execute. Must be nonnegative, divisible by 16 and <=8,320; wrong values can expose unwritten sort entries. |

The extra host row in the table is a derived address, so the table has twelve
rows but the kernel still has eleven pointer arguments. Physical addresses and
USM handles are unavailable. The logged VA alone cannot fill that gap; a pointer
from the passing probe is from a different process. Address canonicalization
also has to be accounted for before matching a Xe VA to a Torch pointer.

### Supporting pointers before/after that GEMM

- **Expert ownership and loader:** B `expert_map_manager.py:63–79` assigns
  global `[128*r,128*(r+1))` to local 0..127 and every other expert to -1.
  O `routed_experts.py:642–645` loads the physical row using
  `q38_expert_placement.row_view:123–128`; bulk loading of a compact table
  is refused. O `fp8.py:720–721` restores metadata after postprocessing;
  placement `131–142` refuses a changed base pointer/shape. The placement JSON
  has 2,600 host rows per rank over 48 layers; CPU validation found no duplicate
  or out-of-range local IDs. Every logical row is in exactly one host/resident
  partition. “Not resident” is intentional for those host rows, not proof of
  a missing expert. Scales remain in logical order.
- **Router:** gate weights/device logits [64,512], BF16 block input, top-k IDs,
  top-k weights and `token_expert_indices` [64,10] are rank-local device
  allocations. B `router/fused_topk_router.py:92–110` supplies the three output
  buffers to native top-k. Native alignment additionally owns temporary prefix
  counts/cumsum storage; that scratch is not a Triton GEMM parameter. Its exact
  allocation/queue lifetime depends on the shipped extension. The local
  `/home/steve/src/vllm-xpu-kernels-current-main/csrc/moe/moe_align_sum_kernels.cpp`
  has a device cumsum allocation and initializes tail expert IDs, but it is
  **not established as the source of 0.1.14.1**; no defect in the shipped binary
  is inferred from a different checkout.
- **Workspaces:** O `experts/triton_moe.py:218–233` requests workspace13 and
  workspace2 each with 1,638,400 BF16 elements at M=64/topk=10/K=2560.
  Each is 3,276,800 bytes; the simultaneous allocation is 6,553,600 bytes before
  unrelated workspace use. Activation is [640,640] BF16 within workspace13;
  final [64,2560] BF16 output may alias the separate output tensor. Config tile
  size affects alignment capacity, not these GEMM-output dimensions. The
  workspace manager grows storage for the current request and retains views;
  there is no demonstrated “old tuned-config-sized buffer” here. Stream/lane
  reuse and native writes still need direct checks.
- **Input embedding UVA:** O `offloader/uva.py:76–90,139–162` allocates pinned
  CPU storage, bounded-copies weights and keeps `_screen1b_host_storage` alive
  while replacing parameter data with an XPU view. This is 317,849,600 bytes
  per TP4 rank in the memory contract; MTP aliases are retained/deduplicated.
  Unlike expert allocation, the generic wrapper has no explicit device scope
  around view creation. Worker current-device setup is relied upon. B
  `utils/torch_utils.py:915–931` calls the native view op; it is not an mmap
  registration routine. This pointer can feed an embedding lookup, **not w13**.
  If `uses_inputs_embeds` selects the dummy embedding buffer, the lookup is
  bypassed: O runner `263–268,1845–1852`, B model state
  `v1/worker/gpu/model_states/default.py:91–95`. Save that flag next time rather
  than guessing from the model name.
- **PLE file mappings:** O `screen1b_ple.py:43–101` maps checkpoint payload
  slices read-only in the current process. `read_row:103–115` and
  `ClockCache:153–202` copy bytes on CPU. `bind_module:248–279` creates a
  per-rank 1 GiB pinned cache and CPU metadata. These are not device pointers
  handed to the MoE kernel. Pinning the cache is not registering the source
  file mmap, nor does the implementation require that mmap registration.
- **PLE staging and model state:** O `screen1b_ple.py:285–295` allocates one
  zeroed pinned-host and one zeroed device step buffer, each [64,16,160] uint8
  (**163,840 bytes**). `pre_forward:298–320` normally gathers CPU rows and
  synchronously copies to device; the profile skips it. `gather_prepared:323–328`
  clones the device slice for masking/reduction. O `ngram_embedding.py:699–703`
  selects this path, `2228–2235` registers it. Its legacy UVA marker does not
  make the mmap or clock cache a GEMM pointer. IDs, owner masks, scale and
  dequantized BF16 PLE values are device intermediates; the MoE sees only the
  resulting hidden state. O `model_state.py:49–65` creates device n-gram
  context, offsets and query-start storage in each worker.
- **PLE helpers and inactive path:** O `common/ple.py:24–108` computes CPU
  shard overlap and bounded-copies loader tensors; no UVA registration occurs
  there. O `nvidia/ple_nvme.py:587–792,838–918` contains the older O_DIRECT
  bounce buffers/clock-cache implementation. O `ngram_embedding.py:2215–2216`
  refuses the external/requantized PLE path under Screen 1b, and O
  `model_state.py:229–234` redirects to `screen1b_ple`. Do not attribute the
  current profile to that older background prefetcher or its stale rows.

O `screen1b_guard.py:375–377` drains loading copies before `load_drained`.
That helps exclude an intentionally pending checkpoint copy, but does not prove
every native queue/context is healthy. Teardown's retained aliases protect
intended Python ownership; they cannot repair an already invalid native queue.

## Ranked hypotheses and discriminating observations

Ranks are investigation priority, not probabilities or a causal verdict.

| Rank | Hypothesis | Evidence for | Evidence against / still missing | Decisive next observation |
| --- | --- | --- | --- | --- |
| 1 | Invalid write or invalid write destination in production routing/alignment/remapping/workspace, or a preceding asynchronous operator | All saved accesses are type 1; startup phase repeats in attempts 7/8. Production uses global E=512 alignment, -1 local filtering and a shared workspace manager; the passing probe does not. The warning precedes alignment and GEMM submissions in Python, leaving both as candidates. | No per-operator synchronization or allocation-span census at failure; the source-level capacities are sufficient. No proven out-of-bounds instruction. Pre-MoE model work remains possible. | Per-stage begin/end synchronization and flushed pointer spans. Verify router IDs, sorted IDs, active expert IDs and padded count before w13. Match fault VA to writable allocation and stage. |
| 2 | Native dispatch crash/queue or VM lifetime failure; faults serviced after VM closure | Upstream -ENOENT interpretation, four delayed native crash reports, native boxed Python-dispatch stacks; the separate immediate-exit probe proves this driver can fault after process teardown. | Attempt 8 fault precedes controller stop and recorded crash reports; orderly one-rank first-forward succeeds. No native signal/VM-close trace proves early closure. Exit-probe BCS is not this CCS incident. | External signal/exit/VM-close timestamps plus operator boundaries; establish whether a live worker faults before any native closure. Do not “fix” by sleeping after exit. |
| 3 | Indirect host-expert USM reachability/residency or stale offset metadata after full load | Host addresses are hidden behind offsets; full run retains 96 expert host allocations/rank and 12.77952 GB/rank, much larger than the probe. A tensor label alone does not establish queue-context accessibility. | Explicit per-worker/per-device allocation and alias checks exist; row coverage and restore checks pass. The real-shape mixed-host probe is byte-exact. Recorded writes are not direct weight reads. No proof of an inherited or unregistered mmap pointer. | Native allocation kind/context, base-table readback and reconstructed full-row spans in each worker after target and MTP load, plus direct-pointer diagnostic against the offset path. |
| 4 | Global/local expert confusion, missing table attribute, or placement loader/postprocess mismatch | An ID >=128 or lost `_q38_base_table` could interpret compact resident storage as 128 contiguous experts. Probe uses local IDs only and bypasses production loading. | 2,600 rows/rank map cleanly; placement is not a list of experts removed from the model. Logical E repairs appear in config, problem size, alignment and modular wrapper; restore rejects changed base/shape. | Check all ranks/layers after postprocessing, enforce table presence for compact weights, validate active remapped IDs and readback row addresses. |
| 5 | Config-specific code generation or workspace lifetime problem | Missing tuned file; modular buffer reuse differs from the functional probe. Actual compiled kernel identity not retained. | Both paths call the same selector/kernel at 64 tokens; config does not choose a smaller output shape. Probe launches confirm real w13/w2 shapes. Tensor-descriptor path is disabled for FP8. | Record actual launch kwargs/IR, workspace capacities and stream/lane; bounded one-layer modular-vs-functional replay with identical routes. No tuning sweep before localization. |
| 6 | `EnableDeferBacking=0`, peer/context interaction or accumulated boot damage | Full TP4 opens collective/device contexts absent from one-card probe; incident is on a boot with earlier faults. Device allocation policy can affect backing/mappings. | No matched Flash-Next A/B isolates the flag; LTX's separate measurement passed. The flag cannot remove intentionally pinned expert memory. No driver/host policy change is justified by these logs. | Fresh authorized boot/window with environment held fixed; record visible devices, queue contexts and native allocations. A flag A/B would need separate admission and memory accounting, not an automatic retry. |
| 7 | 64-token profile overflows fixed PLE/adapter buffers, or stale pinned clock-cache rows | Full runner/state absent in probe; future padding or token gathering could matter. | Capacity is exactly 64 and guarded; current NoDPEP path keeps M=64. PLE buffers start at zero; profile never populates/reads the host clock cache. Counts/hits/misses were zero at load. No prior real step exists to leave stale rows. | Log actual padded token count and PLE shape; assert <=capacity at profile entry. Zero-cache profile should leave hit/miss counters unchanged. |

No OOM kill or memory-watchdog trip preceded this incident. The recovery-time
order-9 atomic allocation failure concerns coredump/GuC logging and is later
than the initial fault. [Host-shadow findings](../experiments/ltx25-b70/notes/2026-10-04-host-ram-shadow-of-vram.md)
explain a separate multi-device backing mechanism; [the Flash memory correction](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/ATTEMPT7-BUDGET.md)
withdraws the claim that attempts 4/6 isolated its savings. Attempt 8's
75.45 GB sampled host peak is neither proof of safe residency nor evidence
that a registration was missing.

## What the passing first-forward probe did not test

P `probe/single_rank_first_forward_probe.py:203–258,317–355` constructs one
synthetic layer, calls **functional `fused_experts_impl`**, and compares
device-only and mixed-host results byte-for-byte. It does test 64 tokens,
topk=10, FP8 w13 [128,1280,2560], w2 [128,2560,640], BF16 output,
block [128,128], host w13/w2 allocations 88,473,600/44,236,800 bytes,
and the rank-0 layer-0 host placement. `stages.jsonl` records all four actual
GEMM launches. That is stronger than a tiny copy probe and must not be ignored.

It does **not** test:

1. Four processes, device selection on ranks 1–3, XCCL or reduction; the actual
   rank-1/2/3 layer-0 host counts are 29/30/31 rather than 27.
2. Global 512-expert router logits/IDs, the 512-entry expert map, nonlocal -1
   blocks or production remapping. Its `global_num_experts=128` and absent
   expert map yield sort capacities 2,560/160, versus production 8,320/520.
   Functional alignment explicitly sets `ignore_invalid_experts=True`
   (O `fused_moe.py:1797`); modular alignment leaves it false.
3. `MoERunner`, native router, `Fp8MoEMethod` post-load conversion/restore,
   NoDPEP preparation, or `WorkspaceManager`. Functional buffers are independent
   Torch allocations, not the production simultaneous workspace slices.
4. Official checkpoint rows/scales, target plus MTP loading, 48 layers,
   approximately 12.78 GB expert pins/rank, PLE, generic input-embedding UVA,
   model-state preparation, hyperconnections, attention warmup or actual
   `profile_run`. A one-layer synthetic test is not EP1 of the full model.
5. A cold mixed-host kernel specialization: control precedes mixed and the
   probe synchronizes around stages. Full startup has different allocation
   history, compilation, concurrency and asynchronous ordering.
6. Native pointer kind/context or destruction proof: the receipt explicitly
   says USM queries/context identity are unavailable and
   `native_queue_destruction_verified=false`. It does prove its saved exact
   output comparison, rank-0 teardown receipt and fault-free watcher window.

## Bounded next-window design — not executed or authorized here

**Requested order: EP1 full-model profile, then EP2, stopping at the first
failure.** These are not existing runnable flags. O placement `22–23,46–47`
requires four rank keys/128 local experts; O `screen1b_ple.py:255–263` requires
TP4 and the sealed four-rank memory contract. Merely changing `--tensor-parallel-size`
to 1 or 2 must refuse. Preserve those guards in the current package.

Before an authorized window, prepare a separately pinned diagnostic adapter:
512/256 local experts for EP1/EP2, explicit local-to-global identity, proper
vocabulary/PLE shard ranges and native per-worker allocation ownership. Keep
weights, scales, arithmetic and full 16-bit KV unchanged. Convert the existing
placement through **global expert identities**, never reuse rank-0's 128-row
table for a larger rank. CPU-check coverage, row spans, scales, loader mapping,
PLE capacity and postprocess metadata at all three topologies. Register the
complete stages, evidence paths and one-launch/no-retry policy in advance.

**Memory admission is a real blocker for EP1.** Routed expert payload alone is
`48 * 512 * (1280*2560 + 2560*640) = 120,795,955,200` bytes. At utilization
0.90, even assigning an entire 32 GiB card's usable budget to these experts
leaves approximately 89.87 GB on the host, before non-expert weights, MTP,
input embedding, PLE cache, staging, metadata and runtime overhead. The actual
split needs a fresh full census; the 96 GB loading guard/24 GiB available-RAM
floor cannot be assumed to pass. EP2 likewise needs a census. A CPU refusal
counts as **not run**, not as an operator failure or permission to raise a cap.

If simultaneous full-model EP1 cannot meet existing guards, keep that arm
blocked. A layer-at-a-time full-model walk could exercise more operators, but
changes loading history and retention and is a **different, weaker diagnostic**;
it must not be called the requested full-load control. The smallest practical
fallback is the existing one-layer-sized probe rewritten to invoke the actual
modular pipeline with 512 global routing IDs and a rank-specific expert map.
It isolates the largest untested software difference without claiming to
reproduce full-model memory pressure. This is a separate preregistered arm,
not a silent substitution or another automatic launch after failure.

| Stage | Scope and fixed limits | Pass/fail and interpretation |
| --- | --- | --- |
| Admission | Owner resolves fourth-incident halt/repeated-fault boot first; exclusive approved window, fresh saved health receipt, reviewed topology package and memory prediction, source/image hashes. No power/driver/host-memory changes. | Any missing prerequisite: refuse before device work. No unchanged attempt-9 retry. |
| A: one card, TP1/EP1 | One spawned worker; full official model plus MTP loaded, same 64-token/one-request startup profile, context 4,352, MTP1 retained, explicit KV bytes, no capture/serving. At most one full target/draft profile. Suggested preregistered bounds: 30 min load, 10 min profile, 5 min orderly teardown; no progress for 120 s writes a stop intent. | Require all load/ownership checks, operator boundaries, valid indices/spans, finite outputs and completed profile, then complete rank teardown and a clean post-exit watcher read. Finite dummy output is only a diagnostic pass, not a quality gate. A fault/invalid index/native crash/timeout fails and forbids B. |
| B: two cards, TP2/EP2 | Only after A passes and memory admission passes; one fresh two-worker launch with the same profile shape and policy, 256 local experts/rank, full load, no capture/serving. Same bounds. If A is memory-blocked, B is not automatically substituted; an amended preregistration must say which comparison is lost. | Same gates for both ranks, plus valid global/local maps and all expected rank lifecycle receipts. A passes/B fails raises distributed ownership, mapping, collectives and scale/placement differences; both passing still does not clear TP4. |

Use the existing **host kernel watcher** design (P `probe/watch_kernel.py`),
independent of container progress, polling at most one second apart. Retain
UTC/monotonic timestamps, precise fault signatures, boot ID, worker host/container
PIDs and ASIDs where observable, memory samples and flushed stage records.
Record the flag/visible-device differences from attempt 8. No profiling tool
is necessary and none of these diagnostic timings is a speed result.

Boundaries to instrument, in order: full-load drain; model entry; embedding/
PLE/hyperconnection/attention output; router; activation quantizer; native
alignment; expert-map remap; w13; activation/quantizer; w2; reduction; target
exit; MTP entry/exit. Synchronize and flush immediately before/after each during
the diagnostic. At each first-MoE boundary save allocation base/end, storage
offset, dtype/shape/stride, owner PID/rank/device, queue/context, table bytes,
native USM kind if queryable and compiled launch kwargs/IR identity. A missing
native query is recorded as missing, not passed. Save kernel fault VA versus
allocation spans with the correct VA-width normalization. Existing native
signal/VM-close tracing, if available and authorized, separates hypotheses 1/2;
without it retain that causal limit.

Preregister invariants before GEMM: M=64, topk=10; router IDs in [0,512);
map exactly covers local experts; padded count within allocated sort capacity;
active remapped IDs are -1 or valid local IDs; sort entries are valid routes
or padding; reconstructed weight rows fit their owning allocations; scales
cover every logical expert; workspace regions have sufficient capacity and
intended non-overlap; PLE count <=64 and no cache fetch during this profile.
Compare the candidate operator with the unchanged same-topology reference on
identical tensors, exact bytes and fresh-process repeat before calling a fix
lossless. No cross-topology tolerance or dummy-output pass promotes a result.

On the first fault, stop new submissions and save evidence, including any
coredump before removal. No second arm, retry, forced group kill, automatic
reset/reboot or automatic recovery probe. Send at most one cooperative stop
request to owned worker PIDs; workers should exit at safe boundaries. On normal
completion drain queues, release aliases before host owners, close PLE views
before mmaps, finalize communicators, and require all rank teardown receipts.
Keep the host watcher through exit and a 60-second quiet period. On a hang or
fault where safe drainage cannot be established, retain ownership/processes
and report the pending teardown instead of freeing memory underneath commands.
The 5-minute bound ends the controller's wait, not permission to SIGKILL.
The current CPU-only task performs none of these operations.

## Unverified patch sketches

There is insufficient evidence to select a production repair. The useful first
patch is a fail-closed ownership/index diagnostic, followed by one mechanism
change only when the boundary evidence supports it. Do not mask bad IDs by
clamping them to another expert or silently returning zero.

**A. Production-path validation and local mapping (highest-priority sketch).**
Add a default-off diagnostic boundary around O
`experts/triton_moe.py:333–345,387–409` and the native alignment call. Save the
raw alignment result **before** its B `moe_align_block_size.py:101` remap.
CPU-readback checks occur only in a clean diagnostic window, after watcher
approval and synchronization; no `.cpu()` or additional device command after
a fault latch. Then validate the actual remapped IDs, tables and buffer spans.

```python
# Sketch only: helpers, native trace and watcher plumbing are not implemented.
raw_ids, padded, sorted_ids = align_with_boundary_receipts(...)
assert_valid_alignment(raw_ids, padded, sorted_ids, global_experts=512)
local_ids = remap_with_boundary_receipts(expert_map, raw_ids)
assert_active_ids(local_ids, padded, block_m, local_experts)
assert_compact_weight_has_table(w13, local_experts)
assert_compact_weight_has_table(w2, local_experts)
assert_all_rows_in_owner_spans(w13, w2)  # post-load, current PID/device/context
assert_workspace_capacity_and_nonoverlap(workspace13, workspace2, M, topk, N, K)
launch_w13_with_boundary_receipts(...)
```

If evidence finds an unwritten alignment tail, repair the native producer or
initialize tail expert IDs to a valid sentinel and remap **only valid blocks**;
preserve nonlocal-expert zero writes. Do not blindly set
`ignore_invalid_experts=True`: removing nonlocal blocks without zeroing all
omitted contributions can change output. If compact-weight metadata is lost,
restore/rebuild it from retained owners after the last replacement and reject
unrecoverable identity changes before execution. Add a table length/local-E
check to the host launch wrapper; move the -1 early return ahead of table
access. This is defensive hardening, not evidence that -1 currently reads
out of bounds (the current code explicitly clamps that access to zero).

**B. Explicit host/device bases, only if indirect addressing is implicated.**
Keep the same physical weight bytes and expert order, but replace cross-storage
signed deltas with two explicit launch pointers and a local row-kind/index
table. Retain both owners through queue completion and validate them in the
actual worker/device/context. Conceptually:

```python
# Host wrapper: no pointers imported from another rank.
assert owner.pid == current_pid and owner.device == launch_device
host_view = make_or_validate_view(owner.host_tensor, launch_device, launch_context)
launch(A, device_rows, host_view, row_kind, row_index, scales, C, ...)
```

```python
# Triton sketch: unchanged dot/scales, local expert ID already validated.
if expert == -1:
    write_zeros_to_output(...)
    return
row = tl.load(row_index + expert)
is_host = tl.load(row_kind + expert)
if is_host:
    b_base = host_rows_ptr + row * row_stride
else:
    b_base = device_rows_ptr + row * row_stride
```

This makes the host allocation visible as a kernel argument and avoids a
cross-allocation base-relative address calculation. It does **not** register
an arbitrary mmap, prove residency, or cure a closed VM. Implement only with
the shipped native context/USM API understood; preserve byte identity and exact
same-kernel output gates. Reject a wrong device in generic
`offloader/uva.py` too: create its view inside `torch.xpu.device(p.device)`
and verify device/owner, while retaining its existing host tensor. That closes
a reliance on ambient device state without claiming that state was wrong here.

**C. Workspace/lifetime repair, conditional on localization.** If a writable
span is stale or overlaps live work, allocate separate diagnostic buffers using
the exact production dimensions on the launch device, retain them through a
completion event, and compare with the manager path. A successful controlled
comparison would justify fixing the manager's stream/lane lifetime; a larger
buffer alone does not fix indexing. If native VM closure precedes execution,
repair the specific dispatch/crash/cleanup path instead. Preserve native traces
and fix ownership ordering; do not relabel a delay, suppressed warning or
disabled fault watcher as a repair.

## Audit checks and next action

Completed here: source/line inspection, 50 replacement SHA256 checks, all 31
saved-evidence hash checks, attempt-6/7 failure receipt review, placement row
coverage/count checks, fault access-type recount, probe call/launch/receipt
comparison, buffer arithmetic, Markdown links and `git diff --check`.
No runtime test or GPU health probe was repeated. No source, manifest,
original receipt, fault marker or owner acceptance was changed.

Next: prepare the bounded production-path diagnostics and topology/memory
admission on CPU. The leading actionable hypothesis is a production-only
write/dispatch failure, not proven mmap access. The smallest requested full-model
test is **EP1 at the real 64-token profiling shape**, subject to the explicit
adapter and memory blockers above; then EP2. Candidate repair is validated
local routing/ownership and, only if supported, explicit host/device weight
pointers or corrected workspace lifetime. Every candidate remains unverified.
