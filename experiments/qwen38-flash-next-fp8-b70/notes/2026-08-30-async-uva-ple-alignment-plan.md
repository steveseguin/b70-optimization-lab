# Qwen3.8 Flash-Next FP8 asynchronous-UVA PLE alignment plan

Date: 2026-08-30
Status: source/design audit complete; XPU port ordered after A25

## Intended deployment

The separate 51B n-gram embedding table belongs in TP4-sharded pinned host
memory. The target, routed experts, attention, and other ordinary weights stay
sharded across the four B70s. NVMe is the cold checkpoint source, not the
decode-time PLE transport. Qwen's model repository explicitly describes host
offload with asynchronous row prefetch overlapped with model computation:

- <https://github.com/QwenLM/Qwen3.8-Flash-Next>

The official vLLM recipe likewise describes host-resident PLE with asynchronous
prefetch, although its initial supported implementation is not XPU:

- <https://recipes.vllm.ai/Qwen/Qwen3.8-Flash-Next>

All 12 directed B70 peer-access checks pass locally. That helps TP4's PLE
reduction and per-layer MoE collectives, but it does not make the host table
GPU-resident.

## Current gap

The accepted A24/A25 path uses generic selective UVA. Each rank has an
accelerator view of its pinned host shard, but lookup is serialized on the main
stream. The separate process-worker port begins work earlier, yet its current
XPU completion path host-polls and performs a blocking result copy. It remains
a correctness/fallback candidate, not the preferred speed implementation.

The most relevant upstream direction is draft vLLM PR 54371, currently headed
by `43d8dd4` after a force-push on 2026-08-30:

- <https://github.com/vllm-project/vllm/pull/54371>

Its focused PLE/UVA change adds a pinned-host embedding, persistent output,
dedicated CUDA stream, explicit start/finalize operations, and a model hook
that starts the layer-1 PLE lookup before layer 0 executes. It also adds n-gram
parallelism. The draft is CUDA-specific, broad, unreviewed, and has no XPU
validation or published performance result, so it must not be cherry-picked
wholesale.

## Bounded XPU port

After the frozen A25 fresh-start trace:

1. add a distinct default-off `VLLM_XPU_PLE_UVA_PREFETCH` selector;
2. retain the proven XPU UVA lookup and current TP4 owner-shard reduction;
3. add one dedicated XPU stream and persistent result buffer;
4. start the sole layer-1 PLE lookup immediately before layer 0;
5. wait only at the layer-1 PLE boundary, then run the unchanged reduction;
6. keep the synchronous UVA path as the control and fallback;
7. compare raw FP8 rows, scaled BF16 rows, reduced vectors, and complete PLE
   output exactly before a full endpoint run;
8. measure lookup duration, exposed wait, overlap, and reduction separately;
9. require short/4K output authorities, semantic battery, needle, same-server
   repeat, and fresh-server repeat before promotion.

The draft's compact row kernel is a separate later experiment. Its FP8-to-BF16
conversion and scale ordering may change low-order bytes, so the first XPU arm
must preserve the accepted arithmetic order.

## Performance interpretation

Each target token looks up 16 rows of 160 FP8 elements, only about 2.5 KiB of
host reads collectively, then reduces roughly 5 KiB of BF16 data. At the
current 5.5 tok/s target rate, aggregate PCIe bandwidth is not a credible
primary limiter. Serialized random-read latency, launch/synchronization cost,
and the reduction boundary are the relevant PLE costs; a side stream directly
targets their exposed portion.

This design work changes no source selector or protected result. A25 remains
the next and only full load after a fresh boot.
