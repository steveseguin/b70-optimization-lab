# MoE boundary caught router padding IDs — October 11

**All four ranks supplied 640 signed int32 `-1` values in the raw router
`topk_ids` tensor, shape `[64,10]`. Alignment had not run.** These are intentional
router padding sentinels, not garbage, unsigned IDs, global-to-local map
errors, or values read from an alignment buffer's unused tail. V2 marks every
profile row as padding; the native router emits `-1` for padding, but the
official XPU 0.1.14.1 aligner does not reject negative input IDs. This is the
concrete routing-to-alignment contract defect exposed by the fourth boundary
window, and strong mechanism evidence for the earlier fourth GPU incident.

The production Python overlay now disables the router padding mask **only
for Screen 1b on XPU**, in both ordinary and bias top-k helpers. Padded rows
take ordinary native routing; valid rows keep their existing arithmetic.
The strict diagnostic remains ON for the next proof, including its refusal
of any raw ID outside `[0,512)`. **143 CPU tests pass; no GPU ran in this task.**
Native startup, output parity and performance qualification remain pending.

## Evidence and timeline

Let P be `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/`.
Read-only run: `/mnt/fast-ai/bench-results/flashnext-moe-boundary-window-20261011-first-cause-v4`.
Its container is `flashnext-screen1-flashnext-moe-boundary-window-20261011-first-cause-v4`,
boot `13858eef-ec68-44ea-a67c-9444933b7100`. This is a later run on a different
boot from attempt 8; “fourth boundary window” and “fourth GPU incident” are
different events. The immutable image is
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`;
runtime receipts report vLLM `0.30.0+xpu`, Torch `2.13.0+xpu`, Triton `3.7.2+xpu`
and `vllm-xpu-kernels 0.1.14.1`.

[Evidence index](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-router-ids-20261011/evidence-index.json)
pins full original and compressed receipt hashes, all four complete boundary
streams, saved server log, a fresh `docker logs --timestamps` read of the
existing exited container, controller failure/STOP, watcher and runtime pins.
The original run was not written to. Compressed receipts restore with `gzip -dc`;
compare the restored bytes with `original_sha256` in the index.

| UTC, October 11 | Event |
| --- | --- |
| 04:59:35.931569 | Container starts. |
| 05:11:16.784395 | Rank 3/PID 127 records the router snapshot, sequence 382. |
| 05:11:16.794060–.794073 | Ranks 0/1/2, PIDs 84/93/110, record identical snapshots. |
| 05:11:16.812689–.822196 | All four record failed raw-router range checks, sequence 383. |
| Before 05:11:17.524408 | STOP contains `MoE boundary rank=3 pid=127: router IDs outside [0,512)`. |
| 05:11:17.524408 | Controller preserves `RuntimeError: MoE boundary STOP/FAULT latched`, phase `startup live checks`; no watchdog reason. |
| 05:11:20.697551–.723008 | All four `rank_teardown_complete` receipts. |
| 05:11:45.092890 | Container exits 1, not OOM-killed. |
| 05:16:14.910048 | Saved final watcher receipt remains clear, zero new fault lines. |

The last watcher snapshot is about 270 seconds after container exit; it does
**not** establish the complete preregistered 305-second post-exit gap. The
failure run has no passing calibration receipt. Four Python teardown receipts
do not prove native queue destruction; their field explicitly remains false.
The result is successful fail-closed diagnosis, not a successful startup or
an all-gates-passed window.

## Which tensor, and exactly which values

Each rank has 383 boundary rows; each has one failed invariant. Sequence 378
identifies `router.topk_ids`, contiguous `torch.int32`, `[64,10]`, stride `[10,1]`,
2,560 bytes within its allocation. Sequence 382 records:

```
2b6e99ee899e1515e0cc44b220424cd9da6906b39490504bdcca2236755db51c
```

That is exactly SHA256 of `b'\xff' * 2560`: 640 little-endian signed int32
`-1` values. The original receipt stores **a hash, not a values array**; this
reconstruction matches all four hashes. The failing row's `count=640` is the
total number examined, not independently an invalid-value count. The hash
match establishes that all 640 are `-1`. There is no unsigned reinterpretation:
the snapshot dtype and Python `.tolist()` are signed.

The check is in diagnostic `copies/overlay/vllm/screen1b_moe_boundary.py:173–174`.
The alignment wrapper calls it at `copies/overlay/vllm/model_executor/layers/fused_moe/moe_align_block_size.py:93`,
**before** `alignment.native_begin` and `ops.moe_align_block_size`. None of the
four streams reaches native alignment, raw aligned experts, remapping, or the
first expert GEMM. `sorted_ids` and `expert_ids` had only been allocated; they
were not the checked tensor. Changing their capacity or initialization would
not repair this failure.

## Producer and unsafe consumer

The [frozen source snapshots](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-router-ids-20261011/source/)
come from official vLLM `ced6857afa0ea7b2e3f0846a62e1394e90f15607` and official
XPU kernels `6d92b1bfbf32767ecda8e819613eb151e70030ad` (0.1.14.1), using Git
objects rather than the later mutable source tree. Source hashes are indexed.

1. Production `overlay/vllm/v1/worker/gpu/model_runner.py:956–958` profiles
   with `_dummy_run(64, skip_attn=True, is_profile=True)`. Its dummy branch at
   1755–1763 uses `InputBatch.make_dummy`.
2. Snapshot `vllm/v1/worker/gpu/input_batch.py:171–172` explicitly fills all
   `is_padding[:num_tokens]` with `True`. This is initialized metadata, not an
   uninitialized workspace. The runner passes it as `is_padding` into the
   forward context at production line 1976.
3. The ordinary router's original `_get_padding_mask`, snapshot
   `fused_topk_router.py:19–23`, forwards that mask when the default
   `VLLM_MOE_SKIP_PADDING=1` is enabled. Native top-k is called with it at
   original line 40. The launch supplied no override. The now-overlaid file
   preserves this original path at lines 30–33 and adds the repair at 28–29.
4. Snapshot `csrc/moe/topk.cpp:186,235–238` and `395,574–577` explicitly
   write signed `-1` when `is_pad_row` is true; padding weights are zero.
   The optimized 512-expert path has the same sentinel rule. The all-minus-one
   snapshot therefore needs neither a NaN nor an invalid router-logit theory.
5. Production `routed_experts.py:1203–1207` passes `topk_ids` unchanged to
   the FP8 modular method. The modular path and `experts/triton_moe.py:333–345`
   reach `_prepare_expert_assignment`; with a 512-entry EP map this is the
   alignment path, not the small no-map fast path. The wrapper supplies
   `expert_map=None` to native alignment while `ignore_invalid_experts=False`,
   then remaps aligned global experts afterward.
6. Native `moe_align_sum_kernels.cpp:1073–1074` selects the general path for
   E=512. At **197–218**, the count phase only rejects `expert_id >= E` and
   indexes shared counts with a negative expert offset. At **427–450**, the
   sorting phase again only rejects `>= E`, then atomically updates
   `cumsum_buffer[-1]` and uses the returned value as a `sorted_token_ids`
   write index. Negative input therefore permits invalid reads/writes before
   any expert GEMM. The precise fault VA/instruction of attempt 8 was not saved.

The lab's own historical
[negative-ID guard, commit 2f829747](../patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0004-fix-moe-ignore-padding-sentinels-during-alignment.patch)
fixes this native omission in the older certified runtime. It was absent,
not superseded, in this partial modern stack. This is retained lab provenance,
not a newly discovered outside optimization or a new speed result.

`screen1b_ple.py:284–294` initializes PLE step buffers to zero. The profile
skips its ordinary pre-forward row-fetch hook. Neither those buffers nor the
compact expert ownership tables generate the `-1` router IDs.

## Rank 3 and the passing single-rank probe

The production expert map is consecutive: ranks 0/1/2/3 own global
`0–127 / 128–255 / 256–383 / 384–511`, respectively, mapping to local `0–127`.
Attempt-6 placement moves local rows between host/device storage; it does not
remove experts or change those identities. Layer-0 host-row counts are
27/29/30/31, but all four ranks have the same bad raw-router hash **before the
map is consulted**. Rank 3 is only the first STOP writer. `require` latches
STOP before emitting its failure row; receipt flush timing explains why some
other ranks' failure-row timestamps precede rank 3's.

`probe/single_rank_first_forward_probe.py:331–348` constructs valid local IDs
on the CPU with `routes(resident, host)`, fixed weights, and calls functional
`fused_experts_impl(global_num_experts=128)` without the production router,
V2 dummy InputBatch, padding mask or global EP map. It could not emit the
native router's padding sentinels. Its exact mixed-host result remains useful
for weight addressing but never covered this producer/consumer contract.

## Fix and identity argument

[Production patch and seal](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-router-padding/README.md):
`overlay/vllm/model_executor/layers/fused_moe/router/fused_topk_router.py:28–29`
and `fused_topk_bias_router.py:32–33` return `None` from `_get_padding_mask`
when `B70_SCREEN1B=1` and `current_platform.is_xpu()`. The latter covers the
bias routing family as well; the observed Qwen call uses ordinary top-k.
This selects the existing unmasked native route for dummy, graph-padding and
MTP rows. It is independent of `SCREEN1B_MOE_BOUNDARY`, and is applied to the
production overlay, not merely the diagnostic. Native preimage hashes are
required by the installer; unexpected image source bytes refuse installation.

For every valid row, the old mask was false. Supplying no mask leaves
`is_pad_row=false` and follows the same native softmax/sigmoid, top-k selection,
tie handling, normalization and store expressions. All valid IDs/weights are
therefore unchanged. Each expert's matrix computation remains independent per
token, and the final weighted reduction retains the same per-token top-k order.
The global/local map, compact row tables, scales, dot arithmetic, buffer
dimensions, FP8 weights and full 16-bit KV do not change. Padded outputs have
no valid-token identity to preserve; they now undergo ordinary computation.
No bad ID is clamped to a different expert or silently zeroed.

This is an algorithmic identity argument for valid outputs, **not a native
full-model parity certificate**. Adding padded expert work changes dispatch
load/group occupancy and startup memory behavior; the same-image native
exact-output and fresh-process checks are still required. The proof window
must measure its own plateau under unchanged admission limits. The native
wheel remains unsafe for arbitrary negative IDs from other callers; a future
port of the retained native guard has separate build/qualification gates.

## CPU checks and next window

[143-test receipt](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-router-ids-20261011/cpu-validation.json)
and [log](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-router-ids-20261011/cpu-tests.log):
zero failures, errors or skips. Seven new regression cases execute extracted
production Python helpers/wrappers with CPU operator doubles: reproduce the
exact all-`-1` receipt hash and unsafe address calculation; check corrected
profile IDs; preserve active mixed-padding IDs, weights, all rank maps and
ordered weighted outputs byte-for-byte; test tied/unpadded routes and scope;
check unchanged arithmetic AST; replay the production patch exactly; pass the
unchanged router boundary for all four rank maps. The existing tests verify
boundary checks, teardown/controller first-cause retention, package replay,
staging hashes and complete staged prediction/admission stopped before Docker.

No native kernel was compiled or executed. CPU tests use Torch `2.14.0+xpu`
with XPU entry points and device opens blocked; that is not the run's Torch
2.13 runtime. All work used nice 19 and `OMP_NUM_THREADS=2`. The only live
container operations were logs and inspect of the existing exited container.
No server, GPU, systemd, port 8188, LTX unit or host setting was touched.
Temporary stages and scratch were removed; retained logs are evidence.

The [boundary README's two stage/run commands](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/README.md#future-authorized-window-command--not-run-by-this-task)
use fresh `router-padding-v5` directories and the fixed production modules
with the boundary ON. They retain TP4/EP4, official FP8, attempt-6 placement,
MTP1, 64 tokens, 96 GB load guard, health/boot/disk/quiet-gap admission and zero
generation requests. They are instructions for the coordinator, not commands
executed here. Stop at any failed check; no automatic retry.

For audit hypotheses 1/4: hypothesis 1 now has a specific observed negative-ID
input and a source-level invalid-write mechanism. The rank/global-local/table
variants of hypothesis 4 are not supported by this refusal, because no remap
was reached and all ranks agree. The zero-fault fail-closed run strengthens
the causal explanation for attempt 8's pre-stop CCS writes; it does not
retroactively identify every historical `-ENOENT` fault or exclude other bugs
after the now-blocked point. The next boundary-on profile is the native test
of this fix; the certified 46.854250 tok/s record remains unchanged.
