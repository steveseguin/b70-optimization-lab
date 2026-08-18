# Qwen3.8 AutoRound INT4 stock-image low-RAM bring-up

Date: 2026-08-18 (America/Toronto)

Status: **closed unsafe on this host; do not retry unchanged**

This was a bounded, target-only TP2 load smoke for
`devan-carlin/Qwen3.8-27B-int4-AutoRound` revision
`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`. It used the already-installed
`intel/llm-scaler-vllm:0.21.0-b3.1` image, eager execution, FP16 activations and
KV, 2,048 context, one sequence, no prefix cache, no graph, no speculation,
and a 9 GiB memory / 12 GiB memory-plus-swap cgroup. No power or firmware
setting changed.

## First startup: incompatible optional GDN probe

The model loaded far enough to initialize both TP ranks. During the dummy
decode, the image's `_gdn_outproj_esimd_eligible()` probed
`self.out_proj.weight` before establishing that the projection was FP8.
AutoRound INT4 correctly exposes `RowParallelLinear.qweight`, so both ranks
raised:

```text
AttributeError: 'RowParallelLinear' object has no attribute 'weight'.
Did you mean: 'qweight'?
```

The image provides `DISABLE_ESIMD_GDN_OUTPROJ=1`; that is the correct
same-binary fallback for this optional FP8-only path.

## Second startup: host cgroup OOM and device reset

With only `DISABLE_ESIMD_GDN_OUTPROJ=1` added, all eight model shards loaded in
8.51 seconds. vLLM reported `8.44 GiB` model memory per rank and reached KV
cache/warmup initialization. The 9 GiB container cgroup then OOM-killed one TP
worker (`anon-rss: 4,656,412 KiB`). During distributed teardown, the Xe driver
logged one BCS engine reset on `0000:e3:00.0` followed by:

```text
Fault response: Unsuccessful -EINVAL
```

The container exited with status 1 and `OOMKilled=true`. It was removed. Both
cards subsequently reported `Device State: normal`; no render-node users or
model servers remained, and this was not a kernel panic.

## Decision

Do not retry the stock image unchanged and do not increase the cgroup limit on
this 15 GiB-RAM host. The separately published Qwen3.8 AutoRound handoff uses
the pinned Qwen3.6-derived source/runtime stack and already completed an MTP3
baseline on another host. Reproduce that low-RAM identity rather than treating
the stock-image failure as a model failure.

This incident proves that checksum-valid weights and architecture recognition
are not sufficient runtime gates. Future bring-up must check quantized GDN
eligibility before model load and must preserve enough cgroup headroom for both
TP workers' warmup allocations.
