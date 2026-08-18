# Reproduced: dual-B70 tensor-parallel + MTP = 84–97 tok/s on Qwen3.8-27B

> **Evidence: `community-reported`; not run in the reference lab.** A reproduction
> of the `0xSero/qwen38-b70` (TP2 patch stack) and `sudoingX/qwen38-mtp` (MTP
> flag recipe) results on a **third** host — Fedora, B60 + 2× B70 — including the
> exact env flag that clears this repo's long-standing SYCL 2-GPU crash.

> **Maintainer reproduction (2026-08-17):** the reference lab reproduced the
> pinned target, draft, TP2 patch family, copy-offload flag, n-max 8, and
> 8192/8192 batch settings, but did **not** reproduce 84–97 tok/s on a fixed
> realistic suite. Across 12 unique cold 512-token prompts, MTP8 measured
> **43.45 tok/s median full decode** versus **48.38 tok/s target-only**
> (−10.2%); its first-100-token median was 46.23 tok/s, with one favorable
> prompt reaching 81.14. Server timing (43.44 tok/s median) agreed with streamed
> full-response timing, so the client did not materially undercount. Quality
> canaries, eight-repeat stability, and a 3,829-token requested-context needle
> (3,582 actual prompt tokens) passed and matched the target baseline, although
> long-form output hashes were not bit-identical.
> The contributor's result is retained as a workload-favorable claim, not a
> general TP2/MTP rate. Full configuration and artifact hashes are in the
> [maintainer audit](maintainer-audit-2026-08-17.md).

Pinned contributor write-up:
[`results/mtp-spec-decode-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/mtp-spec-decode-b70.md).

## The wall this clears

Prior packets from this host reported the SYCL multi-GPU `-sm layer` crash
(`ggml_backend_tensor_copy` SIGABRT) surviving **every** build from b9455 to
fresh master `087f94d`. It is **not** fixed by any upstream commit we tested.
It **is** bypassed by the `0xSero/qwen38-b70` stack: `mndodd/llama.cpp @ 4302fb5`
+ `patches/tp2-full-stack.patch` (a real SYCL tensor-parallel impl — fused
allreduce-add, dedicated **GatedDeltaNet** kernels, fused SwiGLU/attn/GDN/Q8),
built JIT under `intel/oneapi-basekit:2025.3.2`, run with **`--split-mode tensor`**
and the key env flag **`UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1`** (plus
`UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `--fit off`, and JIT quality guards
`GGML_SYCL_MMQ_Q4K_REORDER=0` etc.).

## Reported setup

- ASRock TRX50 WS, Threadripper 9960X, 62 GB RAM; **2× Intel Arc Pro B70** (+ a
  B60 masked off via `ZE_AFFINITY_MASK=1,2` so SYCL0,1 = the two B70s), Fedora
  44, kernel 7.1.8, `xe`.
- `ggml-org/Qwen3.8-27B-GGUF` **Q4_K_M** (SHA-verified to the repo pin) + the
  `mtp-*-Q4_0` draft.
- `--device SYCL0,SYCL1 --split-mode tensor --tensor-split 1,1 --flash-attn on`,
  MTP via `--spec-type draft-mtp --spec-draft-n-max 8 --parallel 1`.

## Reported measurements (server-side `print_timing`, coherent output verified)

| Config | decode tok/s | draft acceptance |
| --- | ---: | --- |
| dual-B70 TP2, MTP-off | **42** | — |
| **dual-B70 TP2, MTP-on** | **84–97** | 73–77%, mean accept-len ~7 |
| single-B70, stock llama.cpp `087f94d`, `draft-mtp` n-max 2 (no TP2 build) | **37** | ~82% |
| single-B70, stock, **no** flag (baseline) | 20.7 | — |

So on **this** host the flag alone (stock build, MTP head already in the unsloth
GGUF, per `sudoingX/qwen38-mtp`) is **+80%** single-GPU (20.7 → 37), and the full
TP2 stack + MTP reaches **84–97** across two B70s with a 262k-capable window.

## Notes for reproducers

- **Entrypoint arg drift** vs current llama.cpp: `--spec-type mtp` → `draft-mtp`,
  `--draft-max` → `--spec-draft-n-max`. The `0xSero` entrypoint predates these.
- `ZE_AFFINITY_MASK` is essential on a **mixed** B60+B70 box: without it,
  `--device SYCL0,SYCL1` grabs the B60 + one B70 (mismatched pair). Mask to the
  two B70s.
- `set_sampler: backend sampling not supported with SPLIT_MODE_TENSOR; using CPU`
  and `spec ... backend offload failed; using CPU sampler` are **warnings**, not
  errors — throughput is unaffected.
- `lmx`/remote decode measurement **undersells** MTP badly here (measured ~46 vs
  the 84–97 server-side) because the streamed inter-token window is bursty under
  speculative decode; trust `llama-server`'s own `print_timing` for MTP numbers.

## Interpretation

The SYCL multi-GPU crash tracked across this repo's field reports is a
**tooling** problem with a **community fix today** (the TP2 patch + the L0
copy-offload env flag), not a hardware limit. For Qwen3.8-27B on a 2× B70 box,
patched-llama.cpp TP2 + MTP is the fastest path we've measured (≈2× a single-card
vLLM-XPU INT4+MTP), and even the *stock*-build single-GPU `draft-mtp` flag is a
free +80%.
