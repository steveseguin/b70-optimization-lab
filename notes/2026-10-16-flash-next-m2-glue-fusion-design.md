# Flash-Next M=2 glue fusion: source-only design, 2026-10-16

The cheapest candidate removes row-collective copies while retaining both
one-row reductions. Two smaller candidates fold integer work into existing
consumers. All three are default-off, unapplied design patches. None has been
compiled or run on a device. Their plausible savings do **not** establish the
survey's 2–4 ms target; the evidence currently supports a smaller first screen.

## Scope and identity

This is lever 1 of the [FP8 return survey](2026-10-16-flash-next-fp8-return-survey.md)
(`ae8d9879b`), for the certified **46.854250 tok/s** FP8 TP4+EP4, lossless
native MTP1 line. It does not change its record or certify a new implementation.
Only repository evidence and
`/home/steve/src/vllm-flashnext-a367-clean-20261016` were read as source. The
export was not changed. No builds, runtime imports, GPU probes, device runs,
privileged commands, or service changes were performed. Commands used
`taskset -c 4-15,20-31 nice -n 19 ionice -c 3`; Python used `python3 -B`.
Only this note and the three linked patch files are deliverables.

The [source reconstruction](../data/2026-10-16-flash-next-a367-prep/source-reconstruction.json),
[preparation](2026-10-16-flash-next-a367-prep.md), and
[reseal](2026-10-16-flash-next-a367-reseal.md) bind the design to:

- Upstream `76cfe1cd88d30d525eec8be5bff75f8b77471c88`, certified overlay
  `6d8724577dabbee5fa0bbc70c4d927c6174c8d8a`, source tree
  `3e8dfc5937087d186cd4a99a6bf15213be732462` (2,305 pinned Python files).
- Official checkpoint revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
  Keep the certified model bytes, placement, quantization, and FP8 scales.
- A367 stage hybrid `2f829747`, served `_xpu_C` identity `bbae3c59` over
  `e421889`; retain the exact serial native GDN implementation. A newly built
  wheel is not automatically this runtime.
- Torch 2.11.0+xpu, Triton 3.7.0, Python 3.12, oneAPI 2025.3 and the pinned
  oneCCL `4ceafd1` stack. Native SYCL operators and Triton kernels coexist.
- `FULL_DECODE_ONLY`, compilation `NONE`, graph sizes `[1, 2]`, max sequences
  1, max batched tokens 64, capacity 4,352. BF16 KV: 376,569,856 bytes/rank.
- Preserve deterministic mode, HC Triton, fused QSA indexer, row-wise
  all-reduce and HC norm thresholds of 2, native serial exact speculative
  recurrence, persistent scratch and completion barrier. Preserve the CCL
  twoshots algorithm and 4,096 threshold. Do not change graph mode, GEMM
  tuning, reduction selectors or MTP acceptance to obtain a saving.

The model has 48 MoE layers, 36 GDN and 12 QSA layers; hidden width 2,560,
512 global/128 local experts, top-k 10, routed intermediate width 640.
The shared intermediate width is 640 globally (160/rank under TP4).
HC has four streams (width 10,240), low-rank width 320, and 97 mixes including
the final mix. There is one PLE layer. QSA expands 512 selected blocks at
compression ratio 4 into up to 2,051 token indices. These counts come from
[the model identity packet](../experiments/own-xpu-runtime/stage2/packet1/identity.json)
and the certified source, not from timing instrumentation.

## What the timing evidence actually says

[A384–A386](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a384-a386-m2-remainder-decomposed-result.md)
uses zeroing diagnostics and A369's three exact-2K rows:

| Term | Evidence, ms per M=2 forward | Interpretation |
| --- | ---: | --- |
| Whole target forward | 33.69 median, 31.90 minimum | Diagnostic reference, not a fresh control in this work |
| Routed MoE GEMMs | about 14.2 | Difference against zero-GEMM arm |
| MoE surround, shared expert and collectives | about 4.7 | Difference between two zeroing arms; not a kernel trace |
| QSA including projections | about 4.7 | Module-level attribution |
| GDN | about 2.1 | Module-level attribution |
| HC / PLE | about zero resolved | Below that experiment's resolution; not literally free |
| Unattributed remainder | about 8.0 | Subtraction residual, not a measured fusion budget |
| Sampling / draft | 0.89 / 2.22 | Separate from the 33.69 ms forward; LM head also outside it |

**Census limitation:** the retained result describes “~400 small kernels” at
“~15–20 µs” but does not attach an exhaustive M=2 kernel-name/duration census.
No such complete trace was found in the allowed repository/export. The
inventory below is a source census with explicit estimates, not a fabricated
measured launch census. Opaque native operators may issue several kernels.
An exact list of every sub-50-µs device launch remains a device-trace task.

The available [A141/A142 attribution](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-04-tp4-mtp1-a141-a142-subop-timing-attribution.md)
and [A141 JSON](../experiments/qwen38-flash-next-fp8-b70/data/20260904-tp4-mtp1-a141-subop-timing-2k.json)
are synchronized eager instrumentation: their roughly 400 ms forward is not
the 33.69 ms graph replay. The historical
[A162 launch/event JSON](../experiments/qwen38-flash-next-fp8-b70/data/20260905-tp4-mtp0-a162-event-launches-2k.json)
is MTP0, not this M=2 identity. Its 48 MoE + 49 other + 1 PLE collective calls
help check source structure; its durations must not be transferred here.

The [September 5 summary](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)
reports a roughly 2.3 µs graph-replayed tiny-add floor and large event-hook
perturbation. [Packet 20](../experiments/own-xpu-runtime/stage2/packet20-launch/receipts-card3-20261011-attempt-a/README.md)
reports about 3.4–5 µs SYCL issue cost, with roughly 9.5 µs including host
wait; it did not establish a graph-replay launch cost. Neither number can
simply be multiplied by all source operations to predict a server saving.

## Dispatch audit: avoid counting work that is absent

Source paths below are relative to the certified export. The XPU model uses
`vllm/models/qwen4_exp/amd/model.py`; the directory name does not mean an AMD
runtime is being proposed.

1. The MoE expert implementation is modular
   `vllm/model_executor/layers/fused_moe/experts/triton_moe.py::TritonExperts.apply`.
   Do not count the functional `fused_experts_impl` path's separate activation,
   quantization and cache-zero launches as additional live work.
2. EP4 does not by itself imply token all-to-all. With DP=PCP=SP=1 the runner
   selects the no-DP prepare/finalize path (`use_all2all_kernels=false`). Its
   logical permutation is the GEMM gather/scatter through sorted token IDs;
   there is no standalone token permutation/unpermutation buffer to remove.
3. The modular path already calls native `silu_and_mul_per_block_quant` for
   SILU, FP8 block `[128,128]`, no LoRA and no UE8M0. The first input
   quantizer is still separate. Finalize already skips an output-alias copy.
4. Native alignment receives the global expert layout, then Python applies
   `expert_map[expert_ids]`. Remote experts become -1 and their GEMM outputs
   are zeroed. Do not compact them away or change native sorting order.
5. Shared + routed output is combined **before** the late TP all-reduce.
   Moving the shared term across that reduction changes BF16 rounding.
6. HC already fuses residual combine/RMSNorm, SiLU/multiply and gate/mix.
   The BF16 store/reload boundary inside combine/norm is intentional.
7. `VLLM_XPU_QSA_SERIAL_SPEC_INDEXER` is not enabled by the audited A367 launch
   plan. The fused pre-indexer has its own eligibility conditions; preserve
   its fallback. Do not assume every conditional QSA branch executes.
8. Views, splits, `empty`, workspace slicing and already-satisfied `.to()` /
   `.contiguous()` calls are not automatically device launches. Record actual
   dtype/stride and capture dispatch before counting one.

## Source census of small work and fusion boundaries

Timing notation: **E** is an unmeasured screening estimate per source operation
at M=2; **H** is a historical measurement on another explicitly named setup.
The 2–20 µs E range is a small launch/memory-op hypothesis; 5–50 µs E allows
native multi-stage/reduction work. These are not confidence intervals or
certified timings. “Trace” means a sub-50-µs classification cannot yet be made.
Counts are per target M=2 forward/rank, unless stated otherwise. Nested rows
are alternative/detail views of a group, not costs to sum twice.

| Group / source operation | Calls or extent | µs per operation | Exact-preserving boundary |
| --- | --- | --- | --- |
| Router projection, native `fused_topk` softmax/top-k/renormalization | 48 routers, M=2 × 512 scores | Projection: trace; fused routing E 5–50 | Keep native softmax reduction, tie order, BF16/FP32 transitions and normalized weights. Integer-only consumers can fuse; replacing softmax/top-k is not exact by construction. |
| `moe_align_block_size`: counts, prefix offsets, padding, token/expert ordering inside native op | 48; 20 routed assignments each | E 5–50 for op; internal launch count unknown | Keep exact sorted-ID bytes and sentinels. A new compact sorter requires stronger tests than “same token set per expert.” |
| `expert_map[expert_ids]` advanced indexing | 48 | E 2–20 | Fold map into both GEMM consumers, before any expert address access. Same global order and local IDs, patch 02. |
| Token permutation / unpermutation | Gather in W13, scatter in W2 | No separate live launch | Already absorbed; neither extra AG/RS nor Python permutation buffers occur on this dispatch. |
| Input `per_token_group_fp8_quant`, groups of 128 | 48; 2 × 2,560 activations and scales | E 5–50 | Group max, abs/clamp, scale/divide, rounding and FP8 cast must match native implementation. Cannot combine with a norm by changing reduction layout. |
| Routed `silu_and_mul_per_block_quant` | 48; 20 × 640 intermediates | E 5–50 | Already fused. Keep BF16 intermediate rounding, native nonlinear operation and group-scale reduction. No remaining separate routed SiLU/quant saving. |
| Routed-weight multiply, BF16 store in W2 | Inside 48 W2 GEMMs | No separate launch | Keep the cast before expert sum. Folding a later sum into W2 changes arithmetic scheduling/reduction ownership. |
| Native `moe_sum` over top-k | 48; 10 × 2 × 2,560 BF16 inputs | E 5–50 | Preserve its reduction tree and store rounding. Sum+shared-add fusion possible only by reproducing this implementation and explicit BF16 boundary. |
| Shared gate, gate/up, down projections | 48 sets; width 160/rank intermediate | Trace; some low-M GEMMs may be <50 | Projections are real work in the 4.7 ms bucket; do not count their runtime as removable glue. No GEMM retuning proposed. |
| Shared `SiluAndMul` | 48 | E 2–20 | Native BF16 nonlinear output must survive any fusion exactly. Already fuses SiLU and multiply. |
| Shared `F.sigmoid(gate(x))`, multiply by shared down output | 48 each | E 2–20 each | Possible native SYCL pointwise fusion only if sigmoid math and BF16 materialization match. Triton sigmoid is not an interchangeable oracle. |
| Shared + routed `add` | 48; 2 × 2,560 | E 2–20 | Can consume a rounded shared multiply; cannot reassociate the sum, fold across TP reduction, or eliminate the rounded intermediate. |
| Row-wise TP reduction pre/post copies | About 96 eligible 2 × 2,560 tensors: 48 MoE + 36 GDN + 12 QSA; embedding/PLE conditional extra | Each clone/copy E 2–20 | Two row clones + two post copies become one whole-tensor clone, preserving two one-row CCL calls. Patch 01; actual invocation count must be checked. |
| One-row `dist.all_reduce` calls | Two per eligible tensor | Trace; do not classify as <50 from old hooks | Keep payload, dtype, communicator, algorithm and rank order. One two-row reduction is a known quality-changing path. |
| Finalize copy / collective views | Alias copy already skipped; row views only | Zero additional launches for these cases | Do not count the already-removed self-copy or slice views as savings. |
| HC combine + RMSNorm (`hc_combine_norm`), including pending residual streams | 97 norm boundaries; combine is conditional on pending state | H M1 2.8 fused vs 30.7 old torch; M2 trace | Already fused. Retain explicit BF16 round trip and fixed reduction hierarchy; no reassociation or alternate norm tree. |
| HC standalone grouped norm / materialized combine at first mix or PLE boundary | Conditional subset of the HC schedule | E 2–20; M2 unmeasured | Preserve materialization before PLE or another external add; these are not additional 97 combines. |
| HC down/up projections, split views | About 97 pairs | Projections trace; views zero | GEMM cost remains; split/select views are not kernels. Do not repeat the closed geometry sweep. |
| HC SiLU/multiply (`hc_silu`), gate/residual mix (`hc_gate_mix`) | About 97 each | H M1 0.8 / 1.1 vs old 5.9 / 12.9; M2 trace | Already fused and banked in the certified line. Preserve intermediate casts and branch norm order. |
| QSA Q/K norm, rotary transform, cache/index metadata writes | 12 sets; pre-indexer branch dependent | E 2–50 per materialized small op; native internals trace | Fused pre-indexer already covers eligible work. Keep rotary/norm reductions, cache values and ordering. No speculative deletion of stateful setup. |
| QSA paged index score and visible-count output | 12 | Trace; can exceed 50 | Score reduction and logits untouched. Visibility is an integer consumer input. |
| QSA stable descending `argsort` | 12; actual columns depend on cache pages | H 23.5 at 1×512, 24.1 at 1×1024, 30.3 at 1×2048, 23.2 at 4×512; M2 unmeasured | Preserve stable ties and exact sorted order: attention reduction order depends on it. Do not substitute `topk`. |
| QSA `blocks.copy_(ranked)` int64→int32, `arange(512)`, broadcast `>=`, `masked_fill_(-1)` | 12 of each on XPU selection path | E 2–20 each | Fold cast and visibility test into existing integer expansion; eliminate rank buffer and bool mask. Patch 03. |
| QSA block-to-token expansion, causal tail, -1 fill | 12; 2 × 2,051 output indices | E 2–20 | Same ordered integer indices, exact sentinel/tail arithmetic; preserve output shape, stride and all stores. |
| QSA output-gate sigmoid and multiply | 12 each | E 2–20 each | Similar pointwise opportunity to shared gate; must retain native sigmoid and rounded BF16 gate/multiply. |
| QSA sparse attention / output projection | 12 | Trace; not assumed small | Outside these patches; selected order and KV precision unchanged. |
| GDN QKVZ and BA projections, output projection | 36 sets | Trace | No geometry/weight changes; shared casts and projections stay. |
| GDN core-output zero; fused reorder / convolution metadata / state updates | 36, shape-dependent | Zero E 2–20; native internals trace | Output zero may protect unused slots. Prove every read is dominated by a write before removing it; state/rollback stores are not dead. |
| GDN `.to(int32)`, contiguous metadata, state-index copies | Conditional, not 36 guaranteed launches each | E 2–20 only if a conversion/copy occurs | Preserve dtype, layout, valid masks and graph addresses. Already-matching views/conversions cost no device launch. |
| GDN gated RMSNorm, flatten view | 36 | Norm E 5–50; flatten normally zero | Keep exact reduction, gate math and cast order. Exact serial recurrence, persistent scratch and completion barrier remain untouched. |
| Embedding lookup, HC stream expansion/materialization, MTP hidden-buffer `copy_` | Once each where selected | E 2–20 per small materialization; lookup trace | Copies may fuse with an existing producer only with identical bytes and stable lifetime. Final MTP buffer is consumed outside target forward. |
| PLE n-gram hash, gather/UVA, dequant; key/value projections | One layer | Hash/dequant E 2–50; gather/projections trace | PLE removal did not resolve a saving. Preserve compressed-weight interpretation and n-gram/cache state. |
| PLE key/query norm, elementwise multiply, sum/divide, sign, abs, clamp, sqrt, multiply, sigmoid, gate multiply, norm | One layer; branch-dependent | E 2–20 pointwise, E 5–50 reductions | Could fuse pointwise chains with explicit casts, but reductions and nonlinear math must stay exact. Low frequency and zeroing evidence make this low priority. |
| PLE short-conv zero/output copy, inner add, outer multi-stream add; speculative arange/searchsorted/where/pack/cat/gather/index-copy and rollback metadata | Once; actual speculative branch conditional | E 2–20 per small op; conv/search trace | Not all fallback operators execute together. Retain rollback/state ordering; no claim that every listed op is a live launch. |
| Runner input staging, position/slot/state metadata copies, acceptance/rollback handling | Once per scheduling step, capture boundary dependent | E 2–20 for small copies; otherwise trace | Separate from layer attribution; input copies must finish before replay. Do not count CPU loops or static graph setup as per-replay kernels. |
| LM head, sampler and native MTP draft's own small operations | Outside target-forward 33.69 ms | Whole sampling/draft 890 / 2,220 µs historical | Measure in whole verify-cycle timing, but do not attribute these totals to target-forward glue or change sampling/verification. |

Source anchors for this inventory: `vllm/model_executor/models/qwen3_next.py`,
`qwen2_moe.py`; `vllm/model_executor/layers/fused_moe/{router/,runner/moe_runner.py,
prepare_finalize/,modular_kernel.py,moe_align_block_size.py,fused_moe.py,
experts/triton_moe.py}`; `vllm/distributed/device_communicators/xpu_communicator.py`;
`vllm/models/qwen4_exp/amd/{model.py,hyperconnection.py,indexer_qsa.py,qsa.py,
ple_layer.py,ops/hc.py,ops/qsa.py}`; `vllm/model_executor/layers/fla/` and
`vllm/_xpu_ops.py`. Trace labels deliberately leave opaque backend sub-kernels
unclassified rather than assigning invented timings.

## Ranked implementation choices

Estimates below are **planning ranges for a successful exact-preserving
implementation**, per M=2 verify cycle with one target forward. They allow zero
benefit; regression is also possible. They are not measurements, projections
for publication, or promises. They exclude LM-head/draft acceleration.

| Rank | Candidate | Planning saving, ms/cycle | Effort and risk | Decision |
| --- | --- | ---: | --- | --- |
| 1 | Coalesce row-wise collective copies | 0–0.8 | Low Python change; medium CCL storage-offset/capture qualification | Patch 01; first screen |
| 2 | QSA post-sort cast/mask inside expansion | 0–0.25 | Small Triton integer change; stable sort unchanged | Patch 03; second screen |
| 3 | EP map lookup inside both MoE GEMMs | 0–0.2 | Moderate plumbing; altered GEMM compilation and repeated scalar loads can lose | Patch 02; cheap screen only |
| 4 | Shared sigmoid/multiply/add or moe_sum/shared-add epilogue | Not defensibly quantified; 48 repeated sites | Higher: native nonlinear parity, BF16 round boundaries, sum-tree preservation | Audit native implementation first; no speculative patch |
| 5 | Remove apparently redundant QSA `project_qk` before fused pre-indexer | Not defensibly quantified; up to 12 conditional sites | Medium: rotary cache-dtype mutation and fallback/serial branch side effects | Prove setup/lifetime semantics before removing calls |
| 6 | New compact native MoE alignment/sort | At most part of the 4.7 ms surround bucket; not measured | High: native ordering and padding oracle, kernel integration | Keep current sorter; do not replace with generic descriptor engine |
| 7 | New row-invariant two-row reduction | Historical selector difference 1.47, **not** an exact-preserving saving | High: needs identical one-row reduction arithmetic at every rank | Existing two-row path changes hashes; excluded from patches |
| 8 | More HC, routed activation/quant, permutation or PLE fusion | Most already fused, absent, or below zeroing resolution | Poor return / high arithmetic risk | Do not reopen closed work under a new name |

At the historical 2.3 µs tiny-add replay floor, removing 288 copy nodes
(96 × 3), 48 QSA nodes (12 × 4), or 48 mapping nodes would correspond to
0.66, 0.11, or 0.11 ms respectively. These are **illustrations of scale only**:
copy traffic, backend dispatch, CCL dependencies, graph scheduling and compiler
changes differ. Do not add them to claim 0.88 ms, or stretch them to 2–4 ms.
Count live calls before interpreting a speed delta. A larger saving requires
a newly demonstrated source of work, not relabeling the unattributed 8 ms.

The [row-wise selector experiment](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a378-a379-row-wise-selector-cost-result.md)
changed hashes when reducing two rows together. Its 1.47 ms difference includes
collective behavior, not just copies. [A355](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-12-a355-views-fast-path-is-exact-but-only-0.9-ms.md)
saved only 0.86 ms on an older serial-GDN line despite many removed launches;
that result is not additive to the newer exact-native baseline. The
[QSA sort note](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-08-qsa-selection-sort-is-launch-bound-not-work-bound.md)
found unstable `topk` unsuitable. Its old ×48 multiplication is not the
12-QSA-layer count of this configuration.

[Packet 24's generic kernels](../experiments/own-xpu-runtime/stage2/packet24-kernels/evidence/20261011-k2-c0-generic-kernels-slow/README.md)
were 50–100× slower when interpreting descriptors. These patches use ordinary
host-side selection and compile-time-specialized existing kernels; no device
opcode loop, runtime descriptor interpreter, new host synchronization, new
atomics or new device-to-host scalar reads. Native SYCL remains the right
place for a future fusion that must reuse native nonlinear arithmetic.
Isolated Triton geometry wins previously lost in the server; retain tuned
geometry and decide using whole-cycle graph replay.

## Unapplied patches and exactness obligations

Each patch applies independently to the pinned clean export; all three also
pass `git apply --check` together. Selectors default to zero and are fixed
before capture. Changing an environment variable cannot change an already
captured graph. M=1/prefill and unsupported shapes retain their old dispatch.
The patches are review artifacts, not production overlays.

### 01: one copy around two row reductions

[Patch 01](../patches/flash-next-m2-glue-fusion-01-row-copy.patch), selector
`Q38_M2_GLUE_ROW_COPY=1`, is restricted to four ranks, BF16 contiguous
`(2,2560)` inputs and the existing row-wise threshold 2.

Before: allocate output; clone row 0, all-reduce it, copy it to output;
clone row 1, all-reduce it, copy it to output. After: clone the whole input
once; all-reduce output row 0, then output row 1. Copying BF16 bytes has no
arithmetic rounding. The two collective tensors still have shape `(1,2560)`,
stride `(2560,1)`, the same 5,120 bytes and same ordered calls/communicator.
Their base allocation differs; row 1 is now a view at a 5,120-byte offset
(a multiple of 256). Both old and new return fresh storage and preserve input.

Exactness is conditional on CCL using the same reduction algorithm/order for
these views. Equal payload shape alone does not prove that: storage offset,
IPC registration, allocation alignment and capture lifetimes require device
qualification. No new simultaneous collective or two-row collective is used.

Unit plan: compare raw uint8 views, including signed zero, cancellation,
subnormals and NaN payloads, on all four ranks; inspect collective selection
and inputs; compare both intermediate row reductions, input immutability and
output aliasing. Replay graphs repeatedly with changed input bytes. Cover M=1,
M=3, other widths/dtypes, noncontiguous inputs, other world sizes and selector
off. Test capture sizes 1 and 2 and normal prefill-to-decode transitions.

### 03: consume QSA argsort indices directly

[Patch 03](../patches/flash-next-m2-glue-fusion-03-qsa-expand.patch), selector
`Q38_M2_GLUE_QSA_EXPAND=1`, only changes the XPU two-row selection path.
It retains the exact stable argsort. Existing expansion reads its strided
int64 slice directly, casts each selected block to int32, and applies the
same rank-versus-visible-count mask before integer expansion. The int32
copy, arange, comparison and masked-fill disappear. Scores, selected order,
token order, attention arithmetic and KV values do not change.

The cast precedes multiplication, matching the old int32 temporary. Masking
uses rank, not block ID. Causal complete groups, the open-group tail and -1
padding retain their old logic. The optional visible-count input must be
contiguous int32 on the same device; it is produced that way by paged scoring.
Existing unused empty workspaces remain for now; removing their allocations
is not claimed as per-replay acceleration.

Unit plan: compare all 2,051 output indices byte-for-byte for both rows,
including dirty output buffers, strided int64 sorted slices, early positions,
4-token group boundaries, 2,048/4,096 boundaries, capacity 4,352, zero and
clipped visible counts, invalid/padded requests and ragged sequence lengths.
Run equal-score/tie and NaN-logit cases through the unchanged actual argsort.
Compare attention outputs as well as indices. Verify graph replay, M=1 and
other-device fallback; keep sparse-attention ordering identical.

### 02: defer the global-to-local expert map

[Patch 02](../patches/flash-next-m2-glue-fusion-02-align-map.patch), selector
`Q38_M2_GLUE_ALIGN_MAP=1`, adds a narrow no-LoRA FP8 M=2/top-k10/global512/
block128 guard with both GEMM M tiles equal to 16 and an int32 contiguous
512-entry map. It leaves native alignment untouched. `_prepare_expert_assignment`
still receives the real map, so it cannot accidentally select the map-free
naive path. Only the materialized advanced-index map lookup is deferred.

Both W13 and W2 load the same local expert ID immediately after loading the
native global ID and before expert placement-table/weight/scale addressing.
Remote mappings stay -1, preserving the existing remote-zero behavior.
The map load guards negative and out-of-range global IDs rather than indexing
from an invalid sentinel. This follows the
[negative-sentinel lesson](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/DO-NOT-REPEAT.md).
The exactness domain is active native blocks with global IDs in [0,512):
unused suffix blocks return before loading the ID. The invalid-ID guard is
a safety condition, not a claim that Python negative indexing and -1 output
are equivalent. Prove this active-prefix invariant in the native unit test.
Native token ordering, padded count, top-k weights, FP8 scales, geometry,
float operations and BF16 store/reduction boundaries are unchanged in source.

A new scalar map load occurs in each GEMM program: removing one map kernel
can lose to repeated loads or register pressure. Moreover unchanged float
source does not prove unchanged compiler scheduling. Inspect generated code
and compare exact intermediate bytes before attributing speed. This is a
bounded experiment, not a reason to reopen GEMM geometry tuning.

Unit plan: compare native sorted-token IDs and padded counts unchanged;
compare mapped valid expert IDs for every rank and all 512 globals. Include
all-remote routes, repeated experts, padding, -1 and invalid sentinels without
out-of-bounds loads. Compare W13, fused activation/quant values and scales,
W2 and moe_sum bytes separately using the same original weights and seeds.
Cover per-expert placement tables, both graph sizes, guard fallbacks and
selector off. Retain the same compiled floating-point instruction/reduction
structure; no tolerance test substitutes for byte comparison.

## CPU-only checks performed

No test imported torch, Triton or vLLM. No test compiled a kernel.

- `git apply --check` accepted all three patches against the unchanged clean
  export. An in-memory unified-diff reader verified context/hunk counts and
  Python AST parsing for five resulting files (27 hunks).
- The patched communicator method was extracted with AST and run against
  byte-buffer mocks: 72 cases covering eligible input and five fallback
  classes. Output bytes and collective payload/order matched; inputs stayed
  unchanged and outputs were fresh. Eligible copy counts changed from two
  clones plus two copies to one clone and no post-copy. This tests Python
  control/copy behavior, not CCL.
- A pure integer model covered 1,000 routing cases across four EP maps,
  remote experts and invalid sentinels. It checked deferred map semantics,
  not native alignment or generated GEMM code.
- A pure integer QSA model compared 462 boundary cases / 947,562 output
  indices. Old copy/cast/mask and fused expansion agreed. This is not a
  device-compiler or attention-output test.
- Repository hygiene passed with four changed paths and no large-artifact
  warnings. Source whitespace checks (`git apply --check --whitespace=error`)
  passed. A whole-file patch-text whitespace check flags the required single
  space on blank unified-diff context lines; those source-context markers are
  retained, not stripped to satisfy a text-file check.
- Export file hashes were checked unchanged. Total patch size: 17,291 bytes;
  this note plus patches are well below the 500 MB growth cap.

For reproducibility of the CPU models: the row-copy matrix is 12 patterns
for each of `(2,2560)`, `(1,2560)`, `(2,128)`, `(3,2560)`, noncontiguous
`(2,2560)` and world-size 2. QSA crosses positions
`[-1,0,1,2,3,4,2046,2047,2048,4095,4351]`, sequence lengths
`[0,1,4,2048,4096,4352]` and visible counts `[0,1,2,511,512,513,1088]`,
using permuted ranked indices and every output column. The essential equality
is `int32(ranked[r]) if r < visible else -1` before unchanged expansion.
These checks are reported here rather than added as unauthorized test files.
Actual native/device tests above remain required.

Patch SHA256:

```text
9a31076b55f5e6298226c9caa8c2ddf34a0ed479508512ad70be7de089c1c912  flash-next-m2-glue-fusion-01-row-copy.patch
290450b3e0923804c9609110bc67663af1676b7bbe19adaf99e550d0d005b7dd  flash-next-m2-glue-fusion-02-align-map.patch
6ece224f80a5b51298a69979eb7b841a3ca65f37c464f2316555136fb8585546  flash-next-m2-glue-fusion-03-qsa-expand.patch
```

Patched-source base SHA256 (paths relative to the export):

```text
8a30e5973e8025a68eb36cbb4438ca017ddfc58f18400fcc30dde2775acd7c3d  vllm/distributed/device_communicators/xpu_communicator.py
c3f7fc2087836f0160a32ab99ceb1d8f6e87c793679da34dd672e225cb7fa31b  vllm/model_executor/layers/fused_moe/moe_align_block_size.py
c6903b8aa621e7cfd26f2572e384e1f65caa7d47d633b58d2c0cbf8713aee654  vllm/model_executor/layers/fused_moe/fused_moe.py
c0ef7d8b64cb18621a43a78c99e9726a244d2b6dc1db6d9d4c9fb4eb0440cfa6  vllm/model_executor/layers/fused_moe/experts/triton_moe.py
b8907242ade523a6731b2e2fd596e210f65a51cb3396fe8065978a68ce259e3b  vllm/models/qwen4_exp/amd/ops/qsa.py
```

## Cheapest decisive device screen — future work only

**Not executed, queued or authorized by this source-only task.** Current
calibration prerequisites in CURRENT.md, including external evidence storage
and the owner-controlled host-memory decision, still apply. Do not launch an
old runner that writes receipts to the root disk. Keep the 500 MB root-growth
cap; use the approved external destination for later device evidence.

Start with patch 01 alone. Preregister one fresh server, one process lifetime,
no automatic retry, all four ranks and the exact certified identity above.
The strongest cheap within-server diagnostic is A/B/A graph replay, with four
requests total: the first suite prompt `incident-retrospective` on control A,
that prompt plus the second suite prompt `code-review` on B, then the first prompt on A
again. Taking the first two in fixed suite order avoids acceptance-based
prompt selection. Use [the fixed suite](../repro/rapid-model-snapshots-b70/realistic-suite-v1.json)
and the full `token_ids` / `text` of their rows in the
[A367 receipt](../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json),
not just hash prefixes. Retain chat mode, no system prompt, thinking disabled,
seed 20260609, temperature 0, top_p 1 and max_tokens 512. The historical inputs
are 87 and 90 tokens, so these requests screen mechanisms at short context;
they do not reproduce A369's exact-2K timing. The later qualification must add
the existing exact-2K/4K oracle and full suite.

Pinned inputs and oracle:

```text
suite file SHA256: 0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812
A367 receipt SHA256: f88da9b4e041255dc36363363bd78756ebcd10418953e1ea7477d63e7b8014dc
incident-retrospective prompt: b6c5ea9e2495278fbe9314b60c34cb3eb51421c6489478812e598f7b3cc83538
incident-retrospective output: 2adc7a61c265c0a60ae6db433ff67f511c8af3227b116a3f08900cbd2a9315e9
code-review prompt: 5a92dcc76e641515c54d71d2d3fef6e3b12a88baa616cc967eba6c897e684a33
code-review output: 6e75a60a15763ff3c9e177b2c8b6c8cb2d97260a2af35186ca8ee59f75f08546
```

Byte-compare all generated token IDs and UTF-8 output against that certified oracle; save full response bytes,
hashes, accepted-token sequence and stopping reason. Do not regenerate the
oracle on the candidate to make a mismatch disappear.

A small, reviewed coordinator adapter is a prerequisite for this design: at
each arm boundary drain requests on every rank, finish outstanding work,
release the old graphs, set the module selector consistently, and recapture
sizes 1 and 2 with the same normal warmup/state initialization. Do not switch
a flag underneath a live graph. Reuse loaded weights; never cycle the server.
Preserve GDN/PLE request reset and cache ownership, and verify that graph
recapture does not accumulate buffers. If the installed runner cannot safely
recapture, do not improvise during the experiment: use a candidate-only fresh
server for the exact-output rejection test and report that a matched timing
comparison is still missing. A historical control cannot replace it.

Every request starts with empty request state: prefix/prompt/KV/response cache
reuse, checkpoints, history/n-gram acceleration and learned drafts disabled;
require `cached_tokens=0`. Kernels/weights may be initialized. Repeated prompts
here serve a declared diagnostic comparison only. This is not the complete
varied realistic suite and must have `realistic_final_gate.passed=false`.

Time **graph replay in the complete serving path**, not isolated copy kernels.
Use existing coarse boundary timing around the complete verify iteration
(target forward, verification/sampling, accepted-state update and native draft
work), with rank synchronization only at outer measurement boundaries.
Report target-forward time separately, M=2 cycle median/p10/p90, M=1 frequency,
accepted tokens per cycle, TTFT and request wall time. Keep the historical
33.69 ms target-forward comparator separate from whole-cycle timing. Use the
maximum critical-rank duration where rank events are collected. No per-op
synchronization/event hook belongs in the timing pass. Discard capture/setup
work, disclose excluded cycles and retain the full distribution. Require the
same output, acceptance and M=2 cycle counts before comparing time.

A preflight byte-level collective unit check must establish the storage-offset
premise. In a separate untimed diagnostic window of the same server, capture
only a few decode steps to collect the missing kernel names/durations and
actual eligible call counts. Keep profiler overhead out of the timed requests;
on the existing host, use the documented short window. Record rank, graph
shape, source operation, kernel name, count and duration; distinguish copy,
collective and native sub-kernels. That trace closes the census limitation
without turning a synchronized eager profile into a speed claim.

Stop this arm on any byte mismatch, capture failure, unexpected algorithm,
invalid access or GPU fault; preserve evidence and follow the standing fault
procedure, with no automatic restart. Stop normally after the four requests
and shut down gracefully, leaving cards empty. Do not try patches 02/03 in
the same first screen or bundle their effects into patch 01.

Decision: any mismatch rejects the candidate; identical bytes plus correct
capture/copy counts establish its mechanism. If A/B/A timing is flat within
control drift (about 3% back-to-back), close this small lever quickly. A clear
saving is only grounds for a subsequent matched qualification, not a speed
verdict: repository rules require at least two fresh servers, determinism
repeats, the full realistic suite and hash-bound promotion evidence. Neither
this design nor one diagnostic server changes the certified record.

## Design disposition and revisit conditions

This source-only design is complete; device qualification is pending. Retained
artifacts are this inventory, exactness/test plans and three unapplied patches.
The export and certified runtime remain untouched. The 2–4 ms objective is
unproven, and missing per-kernel graph evidence is the main uncertainty. Revisit
larger shared-expert or QSA-projection work only after an actual M=2 trace
shows enough cost and its native arithmetic/state obligations are understood.
No failed or lossy candidate is adopted, and no device experiment is reported
as having happened.
