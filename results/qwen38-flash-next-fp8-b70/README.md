# Qwen3.8 Flash-Next FP8 on four Arc Pro B70s

Status: **research screen; not deployment-qualified**

Last updated: 2026-08-27

This is the first instrumentation-free TP4/EP4 server result for the official
Qwen3.8 Flash-Next FP8 export on four 32-GiB Intel Arc Pro B70 cards. It proves
that the exact checkpoint and maintained XPU overlay can load, profile, become
healthy, and serve real requests. It does not yet establish a production
recipe, a quality-qualified speed, long-context behavior, or vision support.

## Measured point

The exact attempt-19 identity was text-only, TP4 + EP4, eager/graph-off, MTP0,
automatic KV precision, prefix caching disabled, and a configured maximum
length of 512 tokens. Three sequential single-request samples used one
repetitive 146-token prompt and forced 256 output tokens:

| Sample | Output tok/s after first text | Wall output tok/s | TTFT |
| --- | ---: | ---: | ---: |
| 1 | 5.142647219 | 4.449694512 | 7.752230 s |
| 2 | 5.221849709 | 4.705774975 | 5.376468 s |
| 3 | 5.289933931 | 4.836666254 | 4.535220 s |

The median after-first-text rate is **5.221849709 tok/s**. All three requests
completed 256 tokens with the same output hash. This is a narrow research
speed screen, not the lab's conventional realistic-suite 99-interval metric
and not an optimized ceiling; the runtime reported that no model-specific MoE
tuning table was available.

## Quality boundary

Two short batteries each passed 5/7 strict cases. Exact response, copy,
arithmetic, JSON, and factual cases passed. The logic case differed only by
case (`Yes` instead of `yes`), while the range-expression case substantively
returned `30` instead of `14`. The first eight-repeat battery contained one
different valid-looking four-color selection; the second was 8/8 stable, for
15/16 majority stability overall. All 30 quality requests reported zero cached
tokens.

These results fail the full-quality and repeat-determinism gates. The measured
speed must not be submitted as a record, promoted as deployment-ready, or used
to lower any prior captured result.

## Exact identity

- Base model family: `Qwen/Qwen3.8-Flash-Next`.
- Quantized child artifact: `Qwen/Qwen3.8-Flash-Next-FP8` at
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
- Artifact tree: 144 files, 131 safetensor shards, 185,563,783,127 bytes,
  152,089 indexed tensors, tree SHA-256
  `4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2`.
- vLLM source: `658965050f259999e635b52a850004a3771cd644`.
- vLLM XPU-kernel source: `2f829747503c77d4814834dffd0840fb1dd9f75a`.
- Runtime stage:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`.
- Selective UVA placement: PLE n-gram embedding plus input embedding,
  12.22 GiB reported per rank.
- Cache: block-outermost `BLHNC`, fixed 192 MiB, 1,536 tokens available.
- Diagnostics: none.

Installed-package version strings are stale metadata for this source-overlay
run. The Git identities and staged-binary hashes in the retained evidence are
authoritative.

## Evidence and remaining work

The compact receipt is
[`20260827-tp4-attempt19-production-qualification.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-attempt19-production-qualification.json).
The full bring-up chronology is in the
[`XPU overlay and preload ledger`](../../experiments/qwen38-flash-next-fp8-b70/notes/2026-08-26-xpu-overlay-preload-gates.md),
and the source series is documented in the
[`patch packet`](../../patches/qwen38-flash-next-fp8-b70/README.md).

The next qualification point is the same sealed TP4/EP4/eager/MTP0 runtime at
1K active context under a 1,536-token configured maximum. TP1 and TP2 require a
separate fit/offload design. MTP1+ requires a performance-preserving port to
the newer speculative runtime interface. Graph, longer context, vision,
fresh-server determinism, full quality, clean-host replay, and a sealed
deployment package remain explicit gaps.
