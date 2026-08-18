# MTP flips from a loss to a gain when the backend changes (one B70)

> **Evidence: `community-reported`; not run in the reference lab.** This pairs
> with [`mtp-single-stream.md`](mtp-single-stream.md) (the llama.cpp-SYCL −5%
> observation) and isolates a single variable: the inference **backend**. It is
> one configuration on one host, not a general MTP conclusion.

> **Maintainer note (2026-08-17):** the report does not actually isolate the
> backend. The two rows also change the model (35B-A3B MoE versus 27B dense),
> quantization, MTP head, and runtime. The reported within-row MTP deltas are
> useful community observations, but the difference between those deltas
> cannot be attributed to the backend alone. No raw logs were available for an
> independent artifact check.

Pinned contributor write-up:
[`results/mtp-spec-decode-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/64df816/results/mtp-spec-decode-b70.md).

## Why this test

The earlier packet reported MTP as a **−5% net loss** on one B70 under
llama.cpp's SYCL backend, and noted an AMD/ROCm cross-run where the *same MTP
model* was **+43%**. That comparison changed vendor, GPU count, and runtime at
once, so it could not attribute the difference to the backend alone. This run
holds the **hardware and the model's MTP head fixed** and swaps only the engine.

## Reported setup

- One Arc Pro B70 (32 GB), ASRock TRX50 WS, Threadripper 9960X, Fedora 44,
  **kernel 7.1.8**, `xe`.
- **Intel LLM-Scaler** `intel/llm-scaler-vllm:0.21.0-b3.1` (vLLM-XPU,
  **torch 2.11.0+xpu** native — IPEX not required), run under podman.
- Model **`Qwen/Qwen3.6-27B`** (dense, `qwen3_5` GatedDeltaNet arch, native
  `mtp` head), **online INT4** (`--quantization sym_int4`, ~18 GB on-GPU),
  single B70 via `ZE_AFFINITY_MASK=1`, `--max-model-len 8192`, `-tp 1`.
- One request stream, 512 generated tokens (`ignore_eos`), temperature 0.
- MTP via `--speculative-config '{"method":"qwen3_5_mtp","num_speculative_tokens":2}'`.

## Reported measurements

| Backend (same B70) | MTP-off tok/s | MTP-on tok/s | Effect | Acceptance |
| --- | ---: | ---: | ---: | --- |
| llama.cpp SYCL (dee2a84, 35B-A3B MoE Q4) | 72.4 | 68.6 | **−5%** | 71% |
| Intel vLLM-XPU (b3.1, 27B dense INT4) | **28.9** | **52.1** | **+80%** | **~74%**, mean accept-len 2.48 |

Each vLLM row is the mean of 3 measured 512-token runs after one warm-up
(28.86 / 28.94 / 29.00 off; 52.03 / 52.07 / 52.08 on). Acceptance and
mean-accept-length are from the server's `vllm:spec_decode_*` metrics.

## Scope and caveats (contributor)

- The two backend rows use **different models/quant** (MoE Q4 vs dense INT4), so
  the absolute MTP-off rates are not comparable — dense activates all 27 B per
  token and is more bandwidth-bound, hence the lower raw rate. **The comparable
  quantity is the MTP *effect*: −5% vs +80% on the same silicon.**
- This is MTP's **best case**: greedy (temp 0) maximises acceptance, and the
  prompt is short (context depth ~0). A separate depth A/B in the pinned
  write-up shows even dense MTP erodes at long context. Expect the +80% to
  shrink with sampling and context length; the durable claim is the **sign**.
- `num_speculative_tokens=2`; the server warns n>1 can lower acceptance.
- Single host, no raw server-log directory published beyond the metrics quoted;
  repeats limited to 3 per arm.

## Side observation: vLLM-XPU multi-GPU brings up on this host

Inside the b3.1 container `torch.xpu.device_count()` returns **3** (B60 + both
B70s) via Level-Zero, although the *host* `sycl-ls` shows OpenCL only — the
container ships a newer bundled compute-runtime. `-tp 2` across the two B70s
reaches `world_size=2` with the **xccl** (oneCCL) collective backend and
completes topology recognition; a full two-B70 serving run is still pending
host-RAM tuning (online INT4 quant loads the full BF16 checkpoint into RAM
first). This is a *different* stack from the llama.cpp `-sm layer` path tracked
in ggml-org/llama.cpp#23797 and is not blocked the same way.
