# vLLM-XPU on the B70: what's unblocked, and the quantized-MoE-kernel wall

> **Evidence: `community-reported`; not run in the reference lab.** One host,
> the **public** `intel/llm-scaler-vllm:0.21.0-b3.1` image, single Arc Pro B70,
> kernel 7.1.8. Exact error strings are quoted so others can pattern-match.
> Scope: this is about the *public* image; Intel's internal builds differ (see
> the "native int4 v4" note at the end).

## TL;DR

- **vLLM-XPU is usable on the B70 now** (kernel 7.1.8): inside the b3.1
  container `torch.xpu.is_available()` is true and `torch.xpu.device_count()`
  sees all GPUs via Level-Zero — even though the *host* `sycl-ls` shows OpenCL
  only. The container ships its own newer compute-runtime + **torch 2.11.0+xpu**
  (native XPU, IPEX not required).
- **Dense quantized models serve fine.** Qwen3.6-27B INT4 (`sym_int4`) runs
  single-stream and at concurrency (see numbers below).
- **Quantized MoE models do NOT fit.** The public b3.1 image has **no
  quantized-MoE compute kernel on XPU**, so it *dequantizes MoE experts to fp16
  at load*. A 35B-A3B MoE therefore reinflates to ~35–70 GB **regardless of how
  small the int4 checkpoint is**, and won't fit one 32 GB B70.

## The smoking gun

Serving any 4-bit **MoE** checkpoint logs, right before the stall/OOM:

```
INFO ... [unquantized.py] Using XPU Unquantized MoE backend out of potential backends: ['XPU'].
```

i.e. the MoE path falls back to **unquantized** compute. The int4 weights load,
then the expert tensors are expanded to fp16 for the XPU MoE kernel — which
blows past 32 GB (or hangs during the conversion).

## Failure matrix (Qwen3.6-35B-A3B, one B70, public b3.1)

| Checkpoint | Format | Disk | Result |
| --- | --- | ---: | --- |
| `cyankiwi/…-AWQ-4bit` | AWQ | 24 GB | `ValueError: Marlin does not support weight_bits = uint4 … device_capability=-1` — AWQ/GPTQ route to the **CUDA-only Marlin kernel**; fails on XPU even with `--quantization awq` |
| `palmfuture/…-GPTQ-Int4` | GPTQ | 24 GB | same Marlin path (not re-run, same kernel) |
| `Intel/…-int4-mixed-AutoRound` | auto-round | 21 GB | **loads on XPU (no Marlin!)** but is "int4-*mixed*" — keeps the vision tower + attention in fp16 → **31.1 GB weights on a 31.9 GB card → XPU OOM**, zero KV room |
| `cyburn/…-int4-AutoRound` | auto-round | 19 GB | **fully quantized** (`modules_to_not_convert: 0`), *should* fit — but **hangs at weight-load**: `Using XPU Unquantized MoE backend` → expert dequant to fp16 stalls/reinflates |

**Key discriminator:** **AutoRound loads on XPU (no Marlin); AWQ/GPTQ do not.**
That matches the lab's existing Intel-AutoRound-gemma B70 entries. But for a
*MoE*, even a valid, lean, fully-quantized AutoRound checkpoint can't stay
compact, because the MoE compute path is unquantized.

## Why dense works but MoE doesn't

Dense INT4 (`sym_int4`) uses the per-layer int4 **GEMM** kernel, which XPU has.
Only the **MoE expert path** lacks a quantized XPU kernel. So:

| Model | Quant | Single-stream decode | Concurrency (serve) |
| --- | --- | ---: | ---: |
| Qwen3.6-27B (dense) | INT4 online | ~29 tok/s | **438 agg tok/s @ 64** (saturates ~64; 128-way = 414) |
| Qwen3.6-35B-A3B (MoE) | any int4 | — | **does not serve** (dequant) |

The dense-27B concurrency figure (`lmx speed-test run vllm --bench-kind serve
--concurrency 64`, 512-in/256-out, no MTP) is offered as the **achievable
public-tooling B70 vLLM concurrency baseline** on one card.

## Multi-GPU (tp=2) status on the public image

`-tp 2` across two B70s brings up the **xccl / oneCCL** collective backend
(`world_size=2`) and shards weights (~9 GiB/card for a dense model). Two gotchas:

1. **oneCCL hangs at the first collective by default** — the two B70s are
   PCIe-connected with **no XeLink**, so default P2P IPC stalls. Fix:
   `CCL_ZE_IPC_EXCHANGE=sockets` (+ `ZES_ENABLE_SYSMAN=1`). With that, a dense
   tp=2 run completes engine warmup.
2. After warmup the **APIServer↔EngineCore handshake stalls** (no
   `startup complete`), and a quantized-MoE tp=2 load hangs earlier still. So
   tp>1 is not yet reliable on b3.1.

This is a *different* stack from the llama.cpp `-sm layer` path (which SIGABRTs
immediately, ggml-org/llama.cpp#23797); vLLM-XPU tp=2 gets much further but is
not production-usable here yet.

## Interpretation

A compact quantized **35B-A3B MoE for concurrency is not achievable on one B70
with the public LLM-Scaler image today** — it's gated on Intel shipping a
**quantized-MoE XPU kernel**. A community B70 leaderboard entry reporting a
64-concurrent MoE aggregate around ~1100–1200 tok/s is consistent with Intel's
*internal* "native int4 v4" build (which has that kernel), not the public
image. Re-test when a future `llm-scaler-vllm` release adds quantized-MoE XPU
support.

## Environment

- ASRock TRX50 WS, Threadripper 9960X, 62 GB RAM; one Arc Pro B70 (32 GB),
  Fedora 44, kernel 7.1.8, `xe`.
- `intel/llm-scaler-vllm:0.21.0-b3.1` under podman, `ZE_AFFINITY_MASK` to pin
  one B70, `--enforce-eager`, `--trust-remote-code`.
- Pinned contributor write-up (context, MTP results):
  [`results/mtp-spec-decode-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/mtp-spec-decode-b70.md).
