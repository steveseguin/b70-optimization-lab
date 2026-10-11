# Attempt 7: first-forward GPU fault analysis

2026-10-08, `steve-b70s`. CPU-only review of saved files. No GPU/device
access, Docker/container operation, server, install, secret access, Git
branch/commit, host-setting change or overlay change was performed. The fault
latch remains untouched. **The probe below is a proposal, not authorization
to run it. It must wait for the owner's reboot decision and a clean boot.**

## Finding and confidence

The failure was in the **initial 64-token dummy forward called by
`profile_run()` inside `determine_available_memory()`**, before final KV-cache
initialization and graph capture. A fixed KV budget does not suppress this
forward. The first table-enabled FP8 Triton MoE kernel is the strongest
localization lead; the saved log does not identify the exact faulting GPU
instruction or expert row.

**Leading hypothesis: the new runtime's first indirect read of host expert
storage through the placement offset table is not accessing a valid resident
mapping.** In particular, that allocation is hidden behind an integer offset;
the MoE launch passes the resident weight pointer and table, but does not pass
the host allocation as a pointer argument. Missing indirect-host residency is
the first mechanism to test. A wrong/stale table entry or later native codegen
error remains an alternative. This is a ranked hypothesis, not a proven root
cause: the run saved no allocation addresses, table contents, USM-context
queries or faulting instruction trace with which to distinguish them.

The description “new expert slab subviews are not USM” is **not supported**.
Attempt 7 did not implement expert slabs. It selected exact-sized allocations
through PyTorch's allocator configuration while retaining separate pinned
expert tensors. The PLE cache has a slab, but its mmap rows are copied on the
CPU and are not read directly by the GPU. Replacing the allocator or pinning
the mmap wholesale is therefore not the proposed fix.

## Evidence identity

Paths below use these abbreviations:

- `S`: [Screen 1b package](../reopen-20261008/).
- `R`: [attempt-7 saved run](../reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt7/).
- `K`: `R/cache/triton/53VVJR52M36CPS5OKWZZUWAK74K27BN65GI2YRRGPK4KHNWBHSYA/`.

`R/runtime-versions.json` records vLLM `0.30.0+xpu`, Torch `2.13.0+xpu`,
Triton `3.7.2+xpu`, kernels `0.1.14.1`, transformers `5.16.1`.
`R/overlay-application.json` identifies upstream
`ced6857afa0ea7b2e3f0846a62e1394e90f15607` and manifest
`3fc4277b1d87df8ef80c82a1b94a7751aa1d98937ecc67529a97a75cfe1a8c42`.
The current manifest matches that receipt; **all 47 overlay file hashes match
the manifest**. This review therefore examines the recorded overlay, not an
unidentified later edit. No container filesystem was inspected.

Saved evidence SHA256s:

| File | SHA256 |
| --- | --- |
| `R/server.log` | `c970f5fbc3bd4d86f0e5ae97aae8057cb3773265c3c88ccabc991056ada9cd06` |
| `R/kernel-fault-window-20261008T2111Z.log` | `1ddff2d88da41de6354a075d082cc633125ba505680f27752c87d9f56625b318` |
| `R/host-memory-samples.jsonl` | `35deae071bdb5bb41723b0a0f2661b00ad06517925801245ce16f42211e8113f` |
| `K/fused_moe_kernel.llir` | `827196a6eef66be5374ab81937856c82d9489109f526cdf065c41dc7afdffd37` |

The compiler cache is local run evidence, not a published reproduction asset.

## What was executing

`R/server.log` gives this sequence (UTC):

| Time | Observation |
| --- | --- |
| 21:10:40 | Ranks 1/2/3 finish loading: 20.87 GiB, 489.56/490.02/490.05 seconds; lines 266–277. |
| 21:11:12 | Rank 0 finishes: 20.87 GiB, 522.46 seconds; line 340. |
| 21:11:13 | Engine selects BLNHC KV layout; line 345. Selecting the layout does not mean KV allocation/capture completed. |
| 21:11:18 | First default MoE configuration warning: E=128, N=640, FP8 W8A8, blocks [128,128]; line 346. Native segfault reports follow. |
| 21:11:18 | Kernel journal: all four cards fault, then CAT errors/resets/dumps. Journal timestamps are local `17:11:18-04:00`. |
| 21:12:07 | Worker 3 reported dead; line 564. |
| 21:12:56 | Engine traceback ends in `shm_broadcast.acquire_read(): RuntimeError: cancelled`; lines 568–612. |

The traceback explicitly follows
`EngineCore.__init__ -> _initialize_kv_caches ->
model_executor.determine_available_memory -> collective_rpc -> response wait`.
It is an engine-side wait traceback, not a worker's model-forward stack.

The remaining call chain is established from source:

1. Local V30 source
   `/home/steve/src/lumnus-20261008/vllm/vllm/v1/worker/xpu_worker.py`
   inherits `Worker.determine_available_memory` from `gpu_worker.py`.
2. `gpu_worker.py:542–545` takes the explicit-KV-budget branch
   (`376,569,856` bytes in the saved command), but still calls
   `self.model_runner.profile_run()` before returning that budget.
   Its later “skipped memory profiling” log means automatic KV sizing is
   skipped, not that no forward executes. That completion log is absent here.
3. The applied `S/overlay/vllm/v1/worker/gpu/model_runner.py:939–958`
   calls `_dummy_run(self.max_num_tokens, skip_attn=True, is_profile=True)`.
   The saved configuration has maximum batch tokens 64 and one sequence.
4. `_dummy_run:835–842` enters `execute_model(dummy_run=True,
   skip_attn_for_dummy_run=True, is_profile=True)`. Attention metadata is
   omitted; the ordinary model path still executes embeddings, routing and
   expert computation. Lines 1766–1773 prohibit FULL graph mode on this path.

Thus this is **profile/dummy warm-up in the KV-initialization stage**, not
KV-cache data access, a user generation request or graph capture. Compilation
mode is NONE; individual Triton kernels still JIT-compile. The warning about
experimental multi-GPU graph support is not evidence that capture caused this
fault. `R/calibration-load.json` records zero generation requests, readiness
false and no ready plateau. The shared-memory cancellation is downstream of
the fault and controller shutdown, not the initiating error.

## Allocations, views and the expert kernel contract

The [attempt-7 implementation record](../reopen-20261008/ATTEMPT7-BUDGET.md)
explicitly selected the allocator-policy alternative. All three allocator
environment aliases in the saved launch contain
`pinned_max_round_threshold_mb:1,pinned_max_cached_size_mb:1`.
Large requests are exact-sized; the cache cap prevents unsafe reuse of
non-power-of-two blocks. This changes sizes and freeing/caching policy, not
the allocator type.

`S/overlay/vllm/q38_expert_placement.py:77–118` still does:

```python
host = torch.empty((len(host_rows), *tail), dtype=dtype,
                   device='cpu', pin_memory=True)
resident = torch.empty((len(resident_rows), *tail), dtype=dtype)
with torch.xpu.device(resident.device):
    uva = get_accelerator_view_from_cpu_tensor(host)
table = torch.tensor(offsets(resident.data_ptr(), uva.data_ptr(), ...),
                     dtype=torch.int64, device='cpu').to(resident.device)
```

There are explicit pinning, contiguous-layout, row-stride and XPU-rank checks.
Each rank has 96 `v5_allocated` receipts (w13/w2 for 48 layers), totaling
12,779,520,000 host expert bytes. For example rank 0 layer-0 w13 has 27 host
rows, 88,473,600 bytes, stride `[3276800, 2560, 1]` and zero remainder modulo
256 for its host address. No receipt records the full pointer.

The saved PyTorch source in `S/evidence/torch-2.13-pinned-allocator/` shows
`CachingHostAllocator.cpp:15–16` calling
`sycl::aligned_alloc_host(512, size, c10::xpu::get_device_context())`.
That is host USM in a SYCL context, not ordinary pageable `torch.empty`, NumPy
allocation or file mmap. A slice of that allocation retains its underlying
USM storage; changing the shape/stride does not itself unregister it.
These snapshots establish intended source behavior, not an audit of the
installed Torch binary or a runtime pointer-type query.

The local V30 helper `vllm/utils/torch_utils.py:915–933` calls the native
`_C.get_xpu_view_from_cpu_tensor`. Local kernel source
`/home/steve/src/lumnus-20261008/vllm-xpu-kernels/csrc/xpu_view.cpp:92–170`
wraps the pinned tensor's **data pointer**, sizes and strides in an XPU
TensorImpl, retaining its owner. The view's pointer already includes any
storage offset. It does not allocate/register a fresh host range for every
row. This checkout was read as mechanism evidence; matching the loaded
extension binary to this source remains unverified.

The row-address formula is:

```text
table[logical_expert] = signed64(row_address - resident_base) / itemsize
row_address = resident_base + resident_index * row_bytes
           or host_uva_base + host_index * row_bytes
kernel row base = B + table[logical_expert]       # element offsets
```

FP8 itemsize is one byte. The table is created **after** final host/resident
allocation and UVA wrapping. `row_view()` only chooses the corresponding
resident or host row for the loader's writes. `_q38_host_cpu`,
`_q38_host_storage` and the saved parameter retain ownership.
Postprocessing calls `restore()` and checks resident pointer/shape equality.
The Triton backend does not shuffle the weights in V30's
`convert_to_fp8_moe_kernel_format`. No one-allocation-per-expert assumption
exists: many host experts already share each per-parameter allocation.

The GPU readers are the two calls to `invoke_fused_moe_triton_kernel` in
`experts/triton_moe.py:387–410,505–528`: w13 gate/up, then w2 down projection.
`fused_moe.py:871–916` passes B and `_q38_base_table`;
`fused_moe.py:426–430,474–485` forms `b_base`, then adds the unchanged K/N
strides. FP8 loads and dot-product arithmetic follow at lines 531–565.
Input embeddings also have a pinned UVA path (`offloader/uva.py:76–90,143–151`),
but their weight tensor is passed directly to embedding operations.

### What the saved compiler output rules out, and what it does not

The attempt's `K/fused_moe_kernel.ttir` has `b_table_ptr: !tt.ptr<i64>` and
loads a 64-bit offset before `tt.addptr`. Its LLVM output contains:

```llvm
%185 = getelementptr [8 x i8], ptr addrspace(1) %2, i64 %184
%186 = load i64, ptr addrspace(1) %185, align 8
%187 = getelementptr i8, ptr addrspace(1) %1, i64 %186
```

So the table branch was compiled, not lost to missing tensor attributes, and
the host delta is not truncated to int32 in this IR. The cache is an FP8
pointer-load kernel, not the tensor-descriptor variant (`USE_TD` is disabled
for quantized inputs). This does not prove the final IGC machine code or
runtime table values are correct. A compiled cache entry is also not an
instruction-level execution trace.

The crucial gap is that host storage is **only reachable through table
contents**. Python retaining a tensor proves lifetime, not residency on the
launching device. Level Zero exposes indirect-host access flags specifically
so a driver can make indirectly accessed allocations resident; see its
[kernel API contract](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/api/apis/kernel.html#zekernelsetindirectaccess).
This supplies a plausible mechanism, not proof of which flags this installed
SYCL/UR launcher set. Static inspection of the saved `spirv_utils` shared
object finds SYCL submission and `zeMemGetAllocProperties` imports but no
direct `zeKernelSetIndirectAccess` import; SYCL/UR can still do that internally.
No claim that its absence proves the bug is justified.

## PLE mmap first access

`S/overlay/vllm/screen1b_ple.py` has this explicit data path:

```text
file mmap -> RowStore.read_row() Python bytes
          -> CPU ClockCache in torch-pinned 1 GiB slab
          -> CPU pinned step buffer
          -> blocking copy_ into XPU step buffer
          -> clone/view of XPU step buffer consumed by the model
```

`RowStore.read_row:105–119` slices the mmap into bytes;
`ClockCache._row/gather_into:167–209` copies bytes through memoryviews.
`bind_module:265–270` allocates the slab with `pin_memory=True` before making
its NumPy view; NumPy is not the allocator here. `pre_forward:306–316`
copies rows to `_screen1b_step_device`; `gather_prepared:319–323` returns
device storage. `ngram_embedding.py:699–703` routes Screen 1b to this function.
The full PLE table is replaced by a small placeholder and skipped by the UVA
offloader; its mmap address is never put into the expert table.

Furthermore `model_runner.py:1918–1928` skips the host pre-forward hook for
dummy/profile/capture runs. Step buffers are zero-initialized at
`screen1b_ple.py:288–289`, so profiling can consume dummy zeros without a
file-row miss. All four saved load-complete snapshots show zero PLE hits,
misses and mapped RSS. Those snapshots precede profiling and alone would not
prove absence of later reads; the control flow supplies the stronger evidence.
Real PLE first-access correctness still needs a future gate, but direct GPU
dereference of mmap is not the supported explanation for this incident.

## Fault addresses, memory and alternative explanations

The saved kernel window contains these page addresses:

| Card BDF | Faulted pages |
| --- | --- |
| `0000:47:00.0` | `0x00000000f4725000`, `0x00000000f4726000` |
| `0000:43:00.0` | `0x0000f5569ed25000`, `0x0000f5569ed26000` |
| `0000:27:00.0` | `0x0000eaaa4b285000`, `0x0000eaaa4b286000` |
| `0000:23:00.0` | `0x0000e001f30e5000`, `0x0000e001f30e6000` |

Only the first pair is below 4 GiB. These addresses cannot be matched to
allocations from the saved receipts, and do not establish a universal
32-bit truncation. The entire saved window has 104 `-ENOENT` responses,
96 CAT errors and four engine-reset messages; multiline diagnostics and
recovery messages make raw line counts differ from the initial 222-line
incident summary. The first faults precede the controller's cancellation.

Memory fit improved, but “76 GB peak” is approximate: the complete saved
sampler's loading peak is **79,208,165,376 bytes (79.21 decimal GB)**, leaving
44,970,967,040 bytes available. In the final roughly 50 seconds before the
fault, samples range from 70.15 to 74.16 GB of pressure. This is a successful
weight load, not a measured serving plateau or full startup peak.

There is an `order:9, GFP_ATOMIC` page-allocation warning in the fault window
(lines 540–565). Its stack is `xe_guc_log_snapshot_alloc ->
devcoredump_snapshot -> xe_devcoredump`, after fault/reset messages. It is
failure to obtain contiguous memory for a recovery snapshot, not evidence
that the initial fault was the loader exhausting RAM. Do not “fix” it by
changing host memory settings.

Ranked alternatives:

1. Indirect host-USM residency/context handling in the refreshed runtime:
   leading candidate given the table-only pointer reachability and first
   expert access. Pinning itself and native indirect access are separate gates.
2. Incorrect runtime table contents or native pointer lowering: still open;
   source math and LLVM width look correct, but the actual values were not
   retained. An immutable pointer snapshot would improve the restore guard.
3. A MoE routing/index defect or another asynchronous preceding kernel:
   possible without a faulting instruction trace. The four-rank linear maps
   passed CPU construction checks, which do not establish GPU correctness.
4. A residual driver problem from the earlier fault on this boot: cannot be
   excluded by source review. No same-boot retry can resolve it safely here.
5. Pageable expert slabs, direct PLE mmap reads, graph capture, and the
   shared-memory cancellation as primary cause: contradicted by the inspected
   implementation or startup sequence.

Attempts 4–6 never reached this same completed-load forward. Therefore attempt
7 being the first failure here does **not** isolate the exact-size policy as
the regression. There is no matched successful V30 forward with the old
rounding policy in this record.

## Proposed fix, held for review

Keep the exact-sized **USM-host** allocator and unchanged FP8 bytes. Make host
expert storage an explicit, actually used pointer argument of the MoE kernel:
pass resident base, host UVA base, local-row index and host/resident selector.
Select the appropriate base and add only an in-allocation row offset, then
retain the existing K/N addressing and FP8 arithmetic. This removes the
cross-allocation pointer jump and makes both allocations visible to submission.
An unused host-pointer argument that the compiler removes is not sufficient.
Changing to an absolute-address table alone still hides the allocations and
does not resolve the residency hypothesis.

Before implementation, verify pointer type in the **launch queue's context**,
ownership and table reconstruction on the tiny probe. If evidence instead
shows a stale table, rebuild it from final storage and save immutable base,
shape/stride/dtype facts for verification immediately before use. If it shows
wrong context/non-USM memory, fix allocation/context ownership; do not paper
over it with a reinterpret cast or a NumPy/mmap view labeled XPU. Explicit
runtime indirect-residency support is another possible fix, but it requires
auditing the actual launcher/UR build and its memory cost.

No proposed fix is certified lossless until it passes raw-byte gather checks,
the lane's kernel/output gates and fresh-runtime repeats. **No overlay edits
have been made.**

## Proposed single-rank tiny probe, after owner-approved reboot only

One process, one selected card, no model, distributed group, server, graph,
checkpoint mmap or four-rank load. Use the already-qualified runtime versions
and the same three exact-allocation aliases before importing Torch. Do not
install another stack or silently substitute the host's Python environment.
If the matching runtime cannot be accessed within the owner's later permission,
leave the probe unrun. No container operation is authorized by this note.

1. Require a different, owner-cleared boot and the owner's allowed health
   preflight. Do not remove `FAULT.json` automatically. Record identities and
   start a bounded fault watcher. No automatic retry/restart on any failure.
2. Allocate **one 3 MiB CPU uint8 pinned slab**, deliberately above the 1 MiB
   exact-size threshold and not a power of two. Fill on the CPU. Make a
   contiguous `[4,4096]` view beginning at byte **4096**, and fill it with
   deterministic bytes `arange(16384) % 251`. Keep the slab and view alive.
3. Select the sole XPU before making exactly one native UVA view. Assert
   matching data pointers, dtype, shape, strides `(4096,1)`, nonzero original
   storage offset and `is_pinned()`. Record slab/view/UVA addresses and spans.
   A read-only native query, when available in the reviewed runtime, must
   identify both slab and interior pointer as `sycl::usm::alloc::host` in the
   launch queue's context. Do not import an unregistered pointer on failure.
4. Allocate a tiny 16 KiB device resident buffer and a device int64 table
   built **after** the UVA view using the production signed-offset formula.
   Choose rows `[3,0,2,1]`. Read back the table and verify on the CPU that
   `resident_base + offset` reconstructs each exact expected host row address,
   including the view's byte offset, modulo 2**64. Keep all owners alive.
5. Submit **one gather kernel launch**, four small programs, one per row,
   reading 4096 uint8 bytes into a 16 KiB device output. Use the same
   table-only indirect contract as the suspect MoE path:

   ```python
   # Proposed kernel body; not executed during this review.
   row = tl.program_id(0)
   col = tl.arange(0, 4096).to(tl.int64)
   delta = tl.load(offset_table + row)  # int64
   values = tl.load(resident_base + delta + col)
   tl.store(output + row * 4096 + col, values)
   ```

   The host UVA tensor stays alive in Python but is deliberately not another
   launch argument. Passing it explicitly would test a different residency
   contract and could hide the suspected failure. Normal setup/copy operations
   may issue runtime kernels; this design calls only one diagnostic gather.
6. Synchronize once, copy output to CPU and require exact equality to rows
   `[3,0,2,1]`, with zero new fault/CAT/reset/dump lines. Save pointer/table
   receipts, hashes and compiler IR. Cleanly release on success. On fault or
   timeout, stop new submissions, retain evidence, and follow the owner's
   recovery decision; no four-rank follow-up or automatic second probe.

A pass establishes this tiny indirect slab-view access only. It does not
certify the large expert tensors, FP8 MoE compute, TP4, PLE or startup.
A failure with CPU-verified addresses makes a mapping/indirect-access failure
much more likely. A subsequent separately reviewed direct-host-pointer
variant would distinguish it from general UVA failure; it is not chained to
this first probe. The proposed explicit-pointer fix likewise needs its own
tiny validation before any full load.
