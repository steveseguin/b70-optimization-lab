# DeepSeek V4 K160 XPU graph recovery and TP4 profile

Date: 2026-07-14

## Outcome

Reusable XPU graph decode now works for the K160 checkpoint. The exact TP4+EP4
128-token diagnostic improved from the warm eager `2.616225 tok/s` control to
`8.616232 tok/s` on the fresh headline row (`3.29x`). The arithmetic canary
still returns `1073`.

This is a meaningful runtime recovery, but it remains far below the
nonspeculative 40-50 tok/s gate. Speculation remains out of scope.

## Why graph capture was wrong

The original sparse-FP8 decode path sized and packed its index tensor using
five device-to-host scalar reads, beginning with
`combined_lens.max().item()`. A Level Zero command graph cannot wait on that
device event during capture. More importantly, even a successful capture would
have frozen the capture-time sequence-length maximum, while sequence length is
not part of the graph key. Replay could therefore silently truncate later
attention indices.

vLLM commit `0ed5ecc5d20c06f5bad71a9d8504bfe5e243df65` replaces that path with a
fixed-width, device-only pack. It also adds a finite sentinel for masked sparse
attention chunks so graph padding cannot produce NaNs. Exact command-graph
replay with changed length tensors passes.

A first attempt to replace the pack with one Triton launch segfaulted the Intel
Triton driver. Preserve that as a negative result. The checked-in static
PyTorch pack is the correctness/bootstrap implementation; a native one-launch
packer remains possible later, but is not the present bottleneck.

## Second graph blocker

After packing was fixed, FULL capture reached the native
`fp8_paged_mqa_logits` operation. Its use of
`sycl_ext_oneapi_work_group_scratch_memory` is unsupported inside the current
SYCL graph implementation. vLLM commit
`436298dcd7c71bc9b567a873098e46d8f7cd7780` adds a narrow FULL-mode eager break
around only this operation and copies into caller-owned stable storage. The
default behavior of the generic breakable-graph helper is unchanged.

PIECEWISE-only capture was already correct at `8.512062 tok/s`; FULL with the
narrow indexer break reached `8.616232 tok/s`, only `1.22%` higher on the
fresh headline row. Graphing the remainder of sparse attention is therefore
not the major remaining opportunity.

## SYCL ABI failure and launcher correction

The first patched run loaded oneAPI 2026 through the umbrella `setvars.sh`,
then JIT-compiled launchers against `libsycl.so.9` while Torch and the pinned
XPU extension use the SYCL 8 lane. It failed on missing symbol
`urDeviceWaitExp`. The three contaminated Triton caches were quarantined at:

`/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-7c360e1cd4a5168099dbc54d16d929bf6df04990/quarantine-sycl9-20260714T1011Z`

The launcher now sources only the pinned oneAPI 2025.3 component environments
and places the virtual-environment library directory before oneCCL/ambient
libraries. New JIT launchers consequently remain in the same SYCL ABI lane as
Torch.

## Exact performance evidence

| Mode | Fresh row tok/s after TTFT | Supporting repeated row | Evidence |
| --- | ---: | ---: | --- |
| eager, warm | 2.616225 | n/a | `tp4-smoke-20260714T132607Z/steady-long-128.json` row 1; support-only baseline because row 0 includes JIT |
| PIECEWISE graph | 8.512062 | 8.496965 | `tp4-graph-piecewise-20260714T1015Z/steady-long-128.json` |
| FULL+narrow break | **8.616232** | 8.622068 | `tp4-full-narrow-indexer-20260714T1020Z/steady-long-128.json` |

The graph runs use the same 65-token prompt, 128-token completion, greedy
decode, TP4, EP4, FP8 KV, K160 revision, and pinned XPU kernel commit. The
benchmark contract treats row 0 as the headline because later rows repeat the
prompt.

## Profile and architecture result

The four-rank Torch profile is at
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-full-profile-20260714T1024Z`.
It observes 87 `c10d::allreduce_` calls for one decoder step, approximately two
TP reductions across 43 layers. The profiler serializes/distorts collective
duration, so its reported 36 seconds is not normal wall time and must not be
quoted as decode latency. The call count, combined with normal wall time of
about 116 ms/token, points to PCIe TP synchronization as the dominant next
boundary. Sparse MLA itself accounts for 43 kernel calls and about 70.5 ms in
the distorted profile; the paged indexer is small.

## DP2 x TP2 x EP4 experiment

This topology is attractive in theory because expert layers remain sharded
over all four ranks while dense/attention TP groups shrink to two ranks. It is
not usable on the current XPU runtime:

- the model constructs with 40/160 experts per EP rank and uses 26.66 GiB/card;
- automatic KV sizing fails, but a manual 64 MiB FP8 KV cache provides 160
  tokens and proves the model fits;
- FULL+PIECEWISE and PIECEWISE-only both stall at 0/2 during the first
  mixed-token graph dummy run;
- eager startup succeeds, but the first request leaves all four workers
  indefinitely waiting in the first DPEP `all_gather` inside
  `MoEPrepareAndFinalizeNaiveDPEPModular`.

The preserved runs are:

- `tp2-dp2-ep4-full-20260714T1029Z`: 95% startup free-memory guard;
- `tp2-dp2-ep4-full-mem94-20260714T1030Z`: pathological automatic memory
  profile;
- `tp2-dp2-ep4-full-mbt128-20260714T1035Z`: negative automatic KV capacity;
- `tp2-dp2-ep4-full-kv64m-20260714T1037Z`: graph dummy stall;
- `tp2-dp2-ep4-piecewise-kv64m-20260714T1043Z`: same graph dummy stall;
- `tp2-dp2-ep4-eager-kv64m-20260714T1047Z`: first-request DPEP all-gather
  stall.

Do not spend time on DP2 graph capture until the XPU DPEP all-gather works in
eager execution. This branch has no valid speed result.

## Next gate

Port and validate the graph-safe XPU custom-allreduce path against this clean
runtime, or otherwise reduce the 87 TP synchronization points. Require exact
canary/output repeatability before performance promotion. Generic attention
tuning, sparse-pack micro-optimization, speculation, and more DP topology
sweeps are lower value until collective wall time is reduced.

## Later same-day promotion: direct and split FP8 attention

The earlier profile overestimated sparse-attention cost because the fallback
materialized BF16 staging tensors and the profiler distorted scheduling. Two
subsequent graph-safe implementations removed that boundary:

- vLLM `cff886bb7165a7328f6412c199bb93c2fbdcfb98` reads paged UE8M0 FP8 KV
  directly, uses device-side runtime lengths, and applies the learned attention
  sink. It reached `21.5448125 tok/s` on the strict cold suite, LocalMaxxing
  `cmrkw8db205nymj01gl5bbmsc`.
- vLLM `b63b1f2b2106a26128a8a0dae55855493b3ada1d` separates QK/LSE from an
  8-by-64 tiled PV kernel, reducing accumulator/register pressure. It reached
  `29.8223801 tok/s` median and `29.4263241 tok/s` p10, LocalMaxxing
  `cmrkxoavs05uimj01p9ix2dtk`.

The promoted split run is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-split-fp8-attn-recordidentity-20260714T1733Z`.
All 12 prompts were cold with `cached_tokens=0`; arithmetic, exact-copy,
Paris, and strict-JSON canaries passed. The identity includes native mHC,
1,024 context/batch, prompt-token details, TP4+EP, FP8 KV, and reusable graphs.

The preceding run at
`tp4-split-fp8-attn-recovery-20260714T1728Z` is rejected. It accidentally ran
without native mHC, at 2,048 context/batch, and without prompt-token details.
Its output failures and `19.74 tok/s` cannot be attributed to the split kernel.

## Device-loss recovery

Rank 1 (`0000:27:00.0`) entered an Xe timeout storm and two launches failed
with `UR_RESULT_ERROR_DEVICE_LOST`. A PCI reset did not recover it and briefly
left GT PF self-configuration errors. Unbinding only that function from the Xe
driver and rebinding it restored service. Four independent compute smokes and
the four-rank XCCL barrier/allreduce then passed. Do not generalize PCI reset as
the recovery procedure for this symptom. The host also reports installed BMG
GuC firmware `70.44.1` while the kernel recommends `70.49.4`; schedule that as
maintenance rather than mixing it into a performance experiment.

## Current residual timeline

The exact-identity eager trace at
`tp4-split-eager-profiler-20260714T1737Z` resolves the former unknown overhead.
Per steady decoder token, excluding distorted profiler collectives:

| Component | Approximate time |
| --- | ---: |
| dense GEMMs, 343 launches | 9.1 ms |
| MXFP4 MoE, 86 launches | 3.67 ms |
| native mHC | 2.69 ms |
| split sparse QK/LSE | 1.94 ms |
| indexer select/sort | 0.98 ms |
| FP8 activation quantization and scale copies | 0.91 ms |
| split sparse PV | 0.28 ms |
| other non-collective kernels | about 3.4 ms |

The non-collective sum is about 23.3 ms. The production graph period is about
33.53 ms/token; prior real XCCL measurements supply about 8 ms and the remaining
roughly 2 ms is queue/host/gap time. The next work is exact dense-projection
shape attribution, followed by the highest-value fusion or kernel replacement.
Speculation remains disabled below the 40-50 tok/s base gate.

## FP8 WO_A negative result

The shape trace showed the BF16 `wo_a` BMM at about 1.39 ms/token. The XPU
extension already contains a fused inverse-RoPE plus UE8M0 FP8 quantizer and a
batched block-FP8 GEMM, so vLLM `4b2d2e0efaee9e08ebe9d77392cead912fdb6909`
wires those operations to the checkpoint's original FP8 `wo_a` weights behind
`VLLM_XPU_V4_FP8_WO_A=1`.

Focused M=1/M=4 correctness and changed-input command-graph replay pass. At the
exact local G=2, M=1, K=4096, N=1024 geometry, FP8 BMM measured 24.89 us versus
30.79 us BF16, and the full isolated inverse-RoPE/projection path measured
39.78 us versus 55.97 us. The end-to-end result did not follow the microbench:
the fixed cold suite reached only `29.5140826 tok/s` median and `28.9644464`
p10 versus the `29.8223801` record. The 128-token screen likewise fell from
29.413 to 29.105 tok/s. Exact canaries and all cached-zero gates passed.

Decision: keep the implementation and tests as a default-off negative artifact,
but do not promote or submit it. The next target is the approximately 8 ms of
real TP collective time, not further `wo_a` work.

## TP-only in-place all-reduce record

The clean communicator cloned every TP output before each XCCL reduction. A
standalone synchronized four-rank BF16 `[1,4096]` measurement reached 104.66 us
median on rank 0; multiplying by the observed 87 reductions reproduces 9.11 ms
per token. The first clone-skip implementation was stopped before measurement
because it violated the out-of-place custom-op alias contract. The corrected
vLLM `bfac86e7d22418a88b0f50f4593aa1e2281d3f2d` adds a no-return mutating op
with schema `Tensor(a0!)`, limits it to the TP group, contiguous XPU BF16
4096-element tensors, and non-compiled execution, while leaving ordinary
all-reduce out of place.

The record lane is explicitly `CompilationMode.NONE` because breakable XPU
graphs disable Dynamo/Inductor, so the guarded path is active during FULL
decode capture. Changed-input replay returned `1073`, `437`, then `1073` again;
exact copy, Paris, and strict JSON canaries also passed with cached tokens zero.
Two full fixed-suite passes measured `29.9132845` and `29.9112607 tok/s` median.
The first is LocalMaxxing `cmrkz6vo7061fmj01v09nwz72`. A middle support run had
29.9672 tok/s across its 11 measurable prompts but failed promotion because one
response emitted EOS after 90 tokens.

The gain over `29.8223801` is only `0.30%`. This is useful attribution: the
clone was real overhead, but most of the 8-9 ms communication bucket is the
ordered XCCL/PCIe wait. The next local fusion target is native MHC post/pre plus
the immediately following RMSNorm, which occurs twice per layer and can remove
86 global-memory/launch boundaries.

## PP4 x TP1 negative result

PP4 x TP1 was tested as a single-session topology, not an aggregate-throughput
configuration. All four stages loaded successfully with layer partition
`[11,11,11,10]`, 22.62-24.99 GiB of weights per card, FULL_AND_PIECEWISE graph
capture, native mHC, and split FP8 attention. Changed-input replay returned
`1073 -> 437 -> 1073`; copy, Paris, and strict-JSON canaries were exact and all
reported `cached_tokens=0`.

The fresh 128-token screen reached only `16.7988310 tok/s` after TTFT, versus
the TP4 record of `29.9132845 tok/s`. PP4 removes the 87 TP all-reduces but makes
each batch-one token visit the four layer partitions serially. TP4 instead has
all four B70 memory systems reading each active layer concurrently. The lost
weight-bandwidth parallelism is much larger than the saved collective cost.
PP2 x TP2 has the same partial-serialization tradeoff and is not a justified
base-decode lane. Keep TP4 for the target and reserve extra-device speculation
experiments for after base decode reaches the 40-50 tok/s gate.

## MHC post/pre plus RMSNorm negative result

XPU-kernel `473a55e2a8b34da3c97c143401955d0c5746120b` adds a distinct
`mhc_fused_post_pre_norm` op. It rounds the MHC-produced activation to BF16,
computes RMS from that rounded value, casts the normalized value to BF16 before
applying the BF16 weight, and therefore matches the existing RMSNorm boundary.
vLLM `520df585c06c5227f2bdbafd3f4789b9bcca9dd2` routes 85 of the 86 layer
norms through it only when `VLLM_XPU_V4_MHC_NORM_FUSION=1`.

M=1/M=4 parity and changed-input command-graph replay passed. Full-model replay
returned `1073 -> 437 -> 1073`, and copy, Paris, and strict-JSON canaries were
exact with `cached_tokens=0`. Two fresh 128-token screens measured
`29.4080025` and `29.4410902 tok/s`, below the `29.4844` in-place-allreduce
comparison screen. The work-group reduction, global fence, and raw-activation
reread offset the removed RMSNorm launch. Keep the implementation default-off
as a correctness base for a larger producer + norm + consumer-quantization
kernel; do not promote or submit this boundary by itself.

## oneCCL 8 KiB protocol sweep

The exact installed oneCCL source is
`4ceafd15c03ce46f11eeaf91781a92afebd3cecf`. On Arc, its default small
all-reduce path selects `allreduce_ll<RingTransmit>` while
`CCL_SYCL_ALLREDUCE_LL=twoshots` selects the alternate built-in protocol.
Synchronized standalone BF16 `[1,4096]` measurements found:

| Route | Rank-0 median | 87x budget |
| --- | ---: | ---: |
| default ring | 128.6915 us | 11.1962 ms |
| twoshots | 87.3690 us | 7.6011 ms |
| Arc LL256 (`CCL_SYCL_ALLREDUCE_ARC=1`) | 89.6885 us | 7.8029 ms |
| ring with LL threshold 8192 | 94.7080 us | 8.2396 ms |
| twoshots with LL threshold 8192 | 88.1310 us | 7.6674 ms |

All ranks passed numerical validation. The apparent 3.60 ms standalone saving
did not transfer to reusable graph decode: exact changed-input and canary gates
passed, but two fresh screens reached only `29.4211775` and `29.3399156 tok/s`
versus the `29.4844` comparison screen. The synchronized microbenchmark folds
host/device synchronization into every sample and does not represent the graph
critical path. Keep `ring` as the production default and require end-to-end
evidence for future collective changes.

## Static block-scale prepack record

Default XPU block-FP8 dispatch transposed and materialized the immutable weight
scale grid on every dense projection. The model executes five such projections
per layer, or 215 calls per decoder token. vLLM
`a77aadb26ac27699aa0537915547cf67c7ab3281` now performs the
`[N/128,K/128] -> [K/128,N/128]` conversion once during weight processing and
reuses the address-stable tensor during graph replay.

Changed-input replay and arithmetic/copy/Paris/JSON canaries passed. The strict
cold suite at `tp4-fp8-scale-prepack-20260714T2110Z` reached `30.2953052 tok/s`
median and `29.7269413` p10, with all 12 prompts cached-zero. This is `+1.28%`
over the `29.9132845` record and was approved by LocalMaxxing as
`cmrl0rf5u06b6mj01y1s9ew2u`.

## Small-M block-FP8 W8A16 record

The exact rank-0 shape trace established five repeated M=1 dense families per
layer:

| Projection | N | K |
| --- | ---: | ---: |
| fused WQA/WKV | 1536 | 4096 |
| Q-B | 8192 | 1024 |
| O-B | 4096 | 2048 |
| shared gate/up | 1024 | 4096 |
| shared down | 4096 | 512 |

The reusable microbenchmark is
`scripts/bench-fp8-dense-shapes.py`; evidence is
`fp8-dense-shapes-w8a16-20260714T1920Z.json`. Existing oneDNN
BF16-activation/block-FP8-weight execution beat quantized W8A8 GEMM by
`1.23-1.88x` on every exact shape. The five-shape weighted eager measurement
fell from about `8.16 ms/token` for activation quantization plus W8A8 to
`4.01 ms/token` for W8A16. Standalone event totals include eager submission
effects and are diagnostic; the reusable-graph suite is authoritative.

vLLM `9fe91a6d6c36806b0428b6c3487bd10b05eee20c` routes only M<=2 block-FP8
dense calls through W8A16 behind `VLLM_XPU_V4_BLOCK_FP8_W8A16=1`. Prefill and
larger M remain on W8A8. The checkpoint FP8 weights and 128x128 weight scales
are unchanged; activation quantization is removed, increasing rather than
reducing activation precision.

Changed-input replay returned `1073 -> 437 -> 1073`; exact copy, Paris, and
strict JSON canaries passed. Two screens reached `33.4813` and `33.3463 tok/s`.
The first full suite was non-promotable only because one row emitted EOS after
10 tokens; its 11 measurable prompts reached `33.8584 tok/s`. The complete
fresh confirmation passed all gates at **`33.8866379 tok/s`** median,
`33.3446529` p10, all 12 rows with 128 streamed token IDs and cached-zero.
This is `+11.86%` over the scale-prepack record and `+13.28%` over the
start-of-turn `29.9133` record. LocalMaxxing approved it as
`cmrl12pke06ehmj01i9a1f0gu`.

The base remains below the 40-50 tok/s speculation gate. The next measured
targets are MXFP4 small-M dispatch, native mHC, and the ordered 87-collective
critical path; do not re-enable speculation yet.
