# Runtime inventory

Stage 0, 2026-10-10. This is an inventory of source, measurements and failed
approaches already preserved in the lab. Nothing listed here was executed on
a GPU for this review. The current GPU halt remains in force.

Paths below are repository-relative unless explicitly absolute. A lab patch
to an external runtime is evidence of our delta, not ownership of the whole
file. Port our independently authored helpers after checking their provenance;
write new runtime interfaces and independently implement ideas from external
code. In particular, the preserved [vLLM](https://github.com/vllm-project/vllm),
[XPU kernel](https://github.com/vllm-project/vllm-xpu-kernels),
[llm-scaler](https://github.com/intel/llm-scaler) and ComfyUI integration trees
must not become this runtime's base. Intel platform libraries remain allowed
dependencies. Historical weight sources do not authorize a new download.

## Capture, kernels and arithmetic

| Asset and exact location | What is established, with measurement receipt | Exactness and port work |
| --- | --- | --- |
| LTX capture adapter: `experiments/ltx25-b70/scripts/ltx_graph_capture.py`; sharding: `scripts/ltx_layer_shard.py` in that lane | Explicit per-device capture streams, stable signatures, shared static input buffers, non-inert replay proof and restore path. [Random-weight mechanism receipt](../ltx25-b70/data/xpugraph-validation-01.json): deterministic shaped-block step 253.128 to 104.431 ms, **2.424x**. [Actual-model packet19](../ltx25-b70/notes/graph-capture-19-results.md): sampler 3.669 to 2.001 s, **1.83x**; [packet20](../ltx25-b70/notes/graph-capture-20-results.md): 3.584 to 1.931 s, **1.86x**. | Diagnostic 2.424x is not a full-model result. Actual clips matched all four raw tensors bytewise. Port the ownership, residency, signature and eager/replay proofs into our C++ arena/graph layer; replace Python object walking and ComfyUI callbacks with explicit model-step arguments. Capture alone does not prove a text model's MTP transaction. |
| Capture failure corpus: `experiments/ltx25-b70/data/capture-abort-host-read-01.json`; `data/h2d-copy-under-capture-01.json`; `notes/vae-graph-capture-blocked-01.md`; `scripts/ltx_graph_text_encoder.py` | [Decoder investigation](../ltx25-b70/notes/vae-graph-capture-blocked-01.md) found the tensor-to-host `int(en.max())` sizing trap; removal passed 288 geometry cases. Its H2D probe then showed captured `torch.tensor(host_list, device=...)` retaining a host pointer: changing the host list changed replay; already-device-resident values were exact. [Packet19](../ltx25-b70/notes/graph-capture-19-results.md) caught a second-device empty graph that falsely appeared 5.612x faster. | Tests and refusal rules are reusable; no speed is claimed for merely removing the host read. Build device-resident inputs before capture, prohibit ephemeral H2D sources, synchronous host reads and allocations based on device values, and prove live-input mutations affect replay. |
| Flash-Next exact serial GDN extension: `patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/`; probe: `experiments/qwen38-flash-next-fp8-b70/probes/gdn-spec-round-state-equivalence.py` | [Source identity and operation](../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md): move exact per-row recurrent decode inside one extension operation, with persistent scratch and completion barrier. Served stage `/mnt/usb-models/qwen38-build/runtime-gdn-roundstate-bbae3c5-b70`; rebuilt `_xpu_C.abi3.so` SHA256 `6b95dc90c25bb0f9c2503805e4184648ddcac089ec54ec65fe7eeb13ab2b097b`. [A364–A366](../qwen38-flash-next-fp8-b70/notes/2026-09-13-a364-native-exact-gdn-certification-result.md): short battery median 43.03 to 53.41 tok/s (+24.1%); exact-2K +23.6%, exact-4K +23.4%. | Three fresh servers retain certified token pins. A367's full-suite 46.854250 tok/s is a separate measurement. Reimplement the serial row/state-rounding contract and barrier in our operation; do not import the extension tree. The two added round-state/unroll commits are disclosed but inert for the certified exact mode, so do not credit the gain to those switches. |
| MiniMax Triton MoE tile configs: `experiments/minimax_moe_tuned_configs/` | [Isolation receipt](../../notes/2026-06-26-minimax-freshcache-and-b70-moe-config-alias.md): `m1-old-bn64-bk128-current-device` moved fresh-cache output 82.608835 to 83.768670 tok/s. Warps4 alone reached 83.040750; stages4 failed fresh exactness. | Tile-only candidate passed n64/n256 hashes, semantic repeat and arithmetic repeat; metadata is part of arithmetic identity. Reuse the measured shape/config census and numeric tile choices, with a new kernel and own dispatch. Require explicit M=1 coverage: nearest-key dispatch can otherwise silently choose a larger tile. No claim that this beats the historical 89.314195 lane. |
| Flash-Next FP8 MoE tile census: `experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32/`, `configs/moe-m1-w13-n64/`; tools `sweep-moe-m2-tile-configs-offline.py`, `timing-moe-block-graph-offline.py`, `fullshape-triton-fp8-moe-gate.py` | Receipts: `data/20260906-moe-m2-tile-config-sweep-card0.json`, `data/20260907-moe-m1-tile-config-sweep-graph-replay-card0.json` in that lane. [Decomposition](../qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md): A230 w13 11.03 ms versus earlier 12.06 ms, w2 8.77 versus 8.69 ms; placement and config identities differ, so this is not an isolated tile gain. | Preserve routing/order and FP8 scale semantics, gate all served M values and host-hit cases. The 27B dense model has no MoE; these tiles enter Stage 2. Fused upstream MoE implementation is idea/provenance input, not reusable runtime foundation. |
| Flash-Next hyper-connection and exact QSA deltas: `patches/qwen38-flash-next-fp8-b70/vllm-hctriton-mtp1-62219122/`; `vllm-qsafused-mtp1-6d872457/` | [Day-summary attribution](../qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md) records about 5.8 ms removed from 8.4 ms torch-fallback HC work on that diagnostic identity. The certified QSA/HC line preceding exact GDN scored 37.825654 tok/s on the fixed suite, as retained in the [exact-GDN recipe](../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md). | Preserve exact reduction trees and BF16 round boundaries; do not treat diagnostic skip attribution as an independent promoted gain. Extract lab algorithm contracts and reimplement interfaces. |
| Qwen27 fused norm/projection prototype: `experiments/qwen27_fused_postattn_rms_w4a16/` | [Fair baseline](../qwen27_fused_postattn_rms_w4a16/README.md): two-kernel ESIMD path 0.206377 ms versus production native RMSNorm+oneDNN 0.119454 ms at M=4/K=5120/N=17408, **72.8% slower**. | Residual/norm exact; projection was tolerance-tested (`max_abs=0.015625`), not bit-identical. Preserve as a negative and a nibble-layout/harness reference. It derives semantics from llm-scaler `db05b458...`; do not copy its projection into our runtime. Keep oneDNN if it wins matched tests. |
| Qwen27 graph-safe attention patches and tests: `experiments/qwen27_graphsafe_flash_attention/` | [Receipt](../qwen27_graphsafe_flash_attention/README.md): typed local-accessor scratch made graph replay possible; historical Qwen3.6 INT4 full-graph crossover 91.019 versus 88.426 tok/s (**+2.93%**). Forced chunk decode at KV2048 cost 214.984 us versus paged 22.618 us, so it is not a general decode replacement. | 12,000 two-card replay checks in the Qwen3.8 rebuild, mutated inputs and poisoned outputs, FP32-reference tolerance; not by itself a bit-exact target oracle. Port scratch lifetime/barrier requirements, not upstream attention source. New kernel must use its pinned Intel toolchain/library arithmetic identity. |
| Qwen FP8 single-checkpoint GDN: `packages/qwen38-27b-fp8-tp1-b70/overlays/b70_gdn_checkpoint.py`; design `experiments/qwen38-27b-b70/notes/2026-09-17-gdn-single-checkpoint-plan.md` | [Qualified package evidence](../../packages/qwen38-27b-fp8-tp1-b70/README.md): six recurrent copies to one, formerly 0.94 GiB at depth 5; KV budget 26,178 to 40,140 tokens at unchanged memory fraction and unchanged speed. | Two fresh strict runs, request-history and long-context checks exact. Independently implement snapshot/accepted-row replay as explicit transaction state. Capacity gain, not decode-speed gain. |
| Qwen FP8 multi-query attention: `packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_multiq.py`; census `experiments/qwen38-27b-b70/data/2026-09-18-fa-multiq-census/` | [Qualified package evidence](../../packages/qwen38-27b-fp8-tp1-b70/README.md): one KV read for five verification queries; 16K/24K/30K writing speed +10/+14/+17% against R311b. Short contexts kept old path because candidate was 1–2% slower. | Correct sycl-tla/CUTLASS pin made all 22 operator cases exact; wrong revision differed on 8/22. Preserve single-row reduction order across query rows and exact toolchain pin; new implementation must repeat operator and full-suite gates. |
| Qwen bounded upload: `packages/qwen38-27b-fp8-tp1-b70/overlays/b70_chunked_upload.py` | [October 4 accepted receipts](../qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/README.md): 128 MiB pieces for large embedding/output-layer transfers; all profiles exact, no GPU fault in that campaign. | Reliability mechanism with no claimed speed uplift; preserve byte identity and loader staging peak. Our loader owns bounded buffers and completion events. |

## MiniMax fused helpers: useful contracts, mostly negative results

These are standalone lab experiments, not a blanket list of accepted kernels.

The accepted broader MiniMax overlay is preserved in
`repro/minimax-m27-b70-89tps-20260520/patches/vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64`
and `llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64` in the same
directory. The [patch inventory](../../repro/minimax-m27-b70-89tps-20260520/patches/README.md)
pins both upstream bases; the [promoted result](../../repro/minimax-m27-b70-89tps-20260520/results/promoted-result-20260519.json)
records 89.314195 output tok/s at p512/n1536, with its historical quality gates.
That is a whole-stack result, not a measured gain attributable to each file.
Separate our deltas from upstream implementation before any port; neither broad
snapshot is an admissible base for the own runtime.

| Exact source | Measurement and exactness | Port decision |
| --- | --- | --- |
| `experiments/minimax_qk_rms_xpu/minimax_qk_rms_xpu.cpp` | [README](../minimax_qk_rms_xpu/README.md): Q/K variance, apply, and apply+RoPE. Small FP16 helper validated numerically; model output rate fell 39.610585 to 35.681825 tok/s with apply+RoPE. | Retain data-layout and reduction-order tests; no accepted speed win. Rebuild only a larger measured boundary with the certified arithmetic. |
| `experiments/minimax_pair_argmax_xpu/minimax_pair_argmax_xpu.cpp` | [Reducer result](../../notes/2026-05-17-minimax-xpu-reduce-localargmax-no-uplift.md): reduce-only passed ties/sign/random and model quality, but 60.071619 versus 61.404035 tok/s. Full helper's internal collective failed corrected rank-wins oracle. | Reuse tie-case fixtures and explicit pair semantics; do not reuse the failing collective composition. Deterministic sampler must specify tie winner and token-index representation. |
| `experiments/minimax_ar_fused_rms_xpu/minimax_ar_fused_rms_xpu.cpp` | [Ordered result](../../notes/2026-05-19-minimax-ar-rms-ordered-negative.md): old reduction/residual ordering differed by up to 0.015625; ordered variant exact in microcheck but model screen about 10.10 versus clean 88.501953 tok/s and compiler failure. | Negative. Preserve the warning that mathematically equivalent placement of residual before/after reduction changes bits; do not port as an accepted fusion. |
| `experiments/minimax_qk_rms_xpu_ipc/minimax_qk_rms_xpu_ipc.cpp` | [IPC receipt](../minimax_qk_rms_xpu_ipc/README.md): peer polling about 417 ms/iteration versus XCCL 0.061791 ms for FP32 [1,2]. CPU-barrier two-kernel path 0.290768 ms; without barrier fails. | Negative. Peer access is not visibility/remote-atomic correctness. No persistent spin-polling compute kernel on the single compute queue. |
| `experiments/minimax_xpu_kv_offload/probes/xpu_kv_block_copy_probe.py`; `xpu_kv_block_copy_probe_20260524-slice.json` in that lane | [Historical offload investigation](../minimax_xpu_kv_offload/README.md): loop copies about 2.1–2.4 GB/s, contiguous slices about 28 GB/s for 64–256 MiB timed transfers, byte-correct. Subsequent split-attention paths changed output and did not qualify exact active-context overflow. | Reuse copy-coalescing fixtures and bounds as ideas for staging; no general exact offload claim. Keep full 16-bit KV. Historical compressed-KV and server-restoration instructions are superseded by current owner rules and are not port candidates. |

## Placement, host memory and teardown

| Asset and exact path | Measured evidence and limits | Work needed in our runtime |
| --- | --- | --- |
| `experiments/xpu_level_zero_peer_probe/peer_probe.cpp` | [Probe contract](../xpu_level_zero_peer_probe/README.md) checks peer access, fill/readback and forked IPC. [Measured four-card status](../minimax_qk_rms_xpu_ipc/README.md): access/import/export work in every direction, cross-device atomics absent. No runtime speed gain claimed. | Port the functional preflight under explicit GPU authorization later; record directed topology and transport in receipts. Do not infer atomics from ACCESS. |
| Qwen operator census: `experiments/qwen38-27b-b70/scripts/qwen38-fp8-kernel-batch-invariance-census.py`, `qwen38-fp8-kernel-determinism-sweep.py`; collective receipt `data/2026-09-02-qwen38-fp8-tp2-allreduce-census-timed-two-b70-host.json` | Two-card allreduce measured 13.171965 us at two rows, 22.768965 us at 64, 228.398455 us at 900; these rows matched rounded FP16 sum. This is the **two-card host**, not four-card placement evidence. | Port shape generation, poisoned tails, repeated rows and row-prefix invariance as CPU-generated fixtures with independent device runners. Re-measure every 1–4-card topology before choosing tensor versus layer split. |
| Flash placement tools: `experiments/qwen38-flash-next-fp8-b70/tools/build-q38-expert-host-placement-from-census.py`, `diff-q38-placement-census-snapshots.py`, `analyze-q38-moe-placement-balance.py`; `reopen-20261008/placement_plan.py` | The [reopen inventory](../qwen38-flash-next-fp8-b70/reopen-20261008/README.md) retains certified placement pins 63.609487 GB and historical whole-host pressure increase 115.87 GB. Its newer 76.374 GB steady/76.643 GB loading cases are **predictions**, not successful full-load measurements. | Own per-allocation census with VRAM floors, graph pools, all ranks' pinned storage, page-cache and driver shadow. Do not turn cold-expert routing from benchmark prompts into a speed shortcut: any routed expert remains available and every host hit is charged. |
| UVA per-expert rows: `experiments/qwen38-flash-next-fp8-b70/tools/equivalence-and-timing-moe-expert-placement.py`; `patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/`; `reopen-20261008/overlay/vllm/q38_expert_placement.py` | [Design/history receipt](../qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md): base-pointer table with unchanged tiles; resident-table and half-host-table output exact for 32 routings. The production recipe's expert placement is a capacity/latency trade, not a guaranteed throughput improvement. | Independently implement pointer-table bounds, host allocation lifetime, signed offsets and routing-independent availability. Only copy-engine overlap is available; compute cannot hide behind concurrent compute. Retain temporary and final host buffers in peak accounting. |
| Multi-card host-shadow probe: `experiments/ltx25-b70/scripts/probe-multicard-buffer-sharing.py` | [Measured receipt](../ltx25-b70/notes/2026-10-04-host-ram-shadow-of-vram.md): 12 GiB device buffers caused 12.6 GiB driver-held host RAM under defaults; `EnableDeferBacking=0` brought it to 0.3 GiB with identical results and 603 GB/s matvec. Packet95b admitted three workers with 115/115 exact timed clips and 3.6 GiB driver peak. | Design census must include `GPUActive`/MemAvailable rather than RSS alone. This setting is historical tested evidence, not authorization to change host/runtime settings in Stage0. Any future applicability is pinned to driver/runtime identity and revalidated. |
| Teardown overlay: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-teardown/`; `overlay/vllm/screen1b_teardown.py`; `teardown_receipts.py`; probe `probe/single_rank_slab_probe.py` | [October10 verdict](../qwen38-flash-next-fp8-b70/notes/2026-10-10-exit-fault-reproduced.md): clean exit and 10-second idle before abrupt exit passed; immediate abrupt exit after gather faulted. Larger one-layer first-forward passed graceful teardown. Exact receipts: `reopen-20261008/runs/probe-clean-exit-20261010b/receipt.json`, `probe-exit-sleep-20261010b/receipt.json`, `probe-first-forward-20261010c/receipt.json`, `probe-abrupt-immediate-20261010c/receipt.json`. | Port protocol/tests, not patched vLLM controller classes: refuse new work, finish/synchronize outstanding work, release dependent views before owners, close peers/events in order, verify idle before exit, emit per-rank receipt. One-layer success does not qualify a full load or identify the original driver resource; four-card halt stays active. No performance gain claimed. |

## Oracles, cold suites and certification harnesses

The Stage1 FP8 oracle is an actual saved token array, not a displayed hash:

- [Qwen27 TP1 no-MTP recorded outputs](../qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/tp1-mtp0-b896-strict-performance.json),
  SHA256 `1ee5743c99c1c0057a9dd19ee5d452e48dd282cca893942b7e2c9e2339998283`.
  Each of 12 rows retains `token_ids`, `text`, prompt/output hashes and timing.
  Raw origin: `/mnt/fast-ai/bench-results/fp8-ckpt2-20260917/tp1-mtp0-b896-strict/performance.json`.
  Companion files are `tp1-mtp0-b896-strict-identity.json` and
  `tp1-mtp0-b896-strict-canaries.json` in that repository directory.
- [Current accepted candidate outputs](../qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/tp1-pkg-32k-strict-performance.json)
  and `tp1-pkg-32k-run2-strict-performance.json` in the same directory;
  [oracle comparison](../qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/tp1-pkg-32k-strict-vs-reference.json)
  reports 12/12 complete token arrays exact at 54.04713845884902 tok/s on the first
  run. This is the one-card FP8 profile; the faster historical two-card and INT4
  rows are different identities.
- Fixed text suite: `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`,
  shared by the Qwen27 FP8 harness; suite SHA256
  `df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`.
  Harnesses: `scripts/bench-openai-realistic-suite.py`,
  `scripts/compare-strict-attempt-outputs.py`,
  `repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh`.
  Preserve the 12 prompts/six classes, 512-token natural cap, one cold use of each
  prompt, cache-zero requirement and 99-interval metric. Adapt transport for the
  own-runtime CLI; do not alter prompts or the comparator.
- Request-history and concurrency diagnostics:
  `experiments/qwen38-27b-b70/scripts/probe-request-history-determinism.py`,
  `scripts/bench-openai-concurrency-oracle.py`, and
  `experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json`.
  These expose state leaks and batch-shape drift; their short 128-token outputs
  cannot become a replacement final suite.
- Flash-Next certified outputs:
  [A367 full cold suite](../qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json);
  exact battery and fresh-start receipts under
  `experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a364-*`,
  `a365-*`, `a366-*`.
  `repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/check-replay-result.py`
  checks the recorded prompt/output pins and workload booleans. Its [recipe](../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md)
  records **46.854250 tok/s** and the inherited 6/7 semantic case result;
  numerical identity does not erase the base model's known answer error.

These harnesses have no standalone speed gain. Their measured value is that
accepted results have full-array equality, fresh-process repeats and preserved
failure evidence. Keep historical oracles fixed for regression/localization;
any genuinely different arithmetic needs a new explicitly identified
same-kernel oracle and still must meet the objective's certified-output gate.
Changing an oracle never converts a regression into a pass.

## Bounds that keep the inventory honest

The often-quoted **537 GB/s** comes from a historical B70 copy/weight-read
roofline, not a universal promise for every kernel or every host. The [LTX
GEMM decomposition](../ltx25-b70/notes/gemm-ceiling-and-block-decomposition.md)
measured 527.8 GB/s copy and 347.2–619.8 GB/s effective weight-read rates at its
specific shapes. The [pre-graph diagnosis](../ltx25-b70/notes/dispatch-bound-diagnosis-01.md)
reported 536.8 GB/s and substantial dispatch cost; [packet33b](../ltx25-b70/notes/contiguous-capture-retired.md)
then found the captured block region already busy on device and closed
whole-shard capture as a useful lever. The [current caution](../../notes/2026-10-10-sampler-feasibility.md)
explicitly forbids transplanting those small-shape fractions to today's larger
video workload.

The [9B draft-head measurement](../qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md)
is 0.894 ms at M1 and 0.921 ms at M4 for 524 MB of INT4 weights/scales: 586 GB/s,
against 573 GB/s copy; argmax 0.03 ms. It limits expectations for a replacement
GEMV, but is not a measured Qwen27 kernel target. Finally, the [Flash-Next M2
decomposition](../qwen38-flash-next-fp8-b70/notes/2026-09-13-a378-a379-row-wise-selector-cost-result.md)
leaves 11.2 ms of 33.69 ms unattributed to dense projections **and** replay glue;
it does not prove that all 11.2 ms is removable CPU dispatch. New per-shape
measurements, after authorization, decide which kernels deserve replacement.
