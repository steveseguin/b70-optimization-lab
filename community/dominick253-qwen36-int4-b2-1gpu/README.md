# Qwen3.6 27B / 35B A3B INT4 on Intel Arc B70 (vLLM Docker, b2, one GPU)

Deployable vLLM Docker recipe for serving `Qwen3.6-27B` (dense) or
`Qwen3.6-35B-A3B` (MoE) in INT4 (`sym_int4`) quantization on a single Intel Arc
B70 with FP8 KV cache, MTP speculative decoding, thinking mode, tool calling,
and vision — using the `intel/llm-scaler-vllm:0.21.0-b2` image.

## Status

> **Benchmarked (2026-08-04).** llama-benchy results recorded for both models
> (pp 2048 / tg 1024, 5 runs per depth, depths 0–32k). Tables in
> [`benchmarks/BENCHMARKS.md`](benchmarks/BENCHMARKS.md); raw per-run data in
> `benchmarks/*.json` / `*.csv`.

## Model

- HF repo: `Qwen/Qwen3.6-27B` (dense) or `Qwen/Qwen3.6-35B-A3B` (MoE), full BF16 checkpoints
- Quantization: in-place INT4 via `sym_int4` + `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1`
- KV cache: `fp8_e4m3` (Triton attention backend)
- Docker image: `intel/llm-scaler-vllm:0.21.0-b2`

## One-Command Start

Requires an Intel Arc B70 visible at `/dev/dri`, Docker, and the model downloaded locally.

```bash
# --- Abstracted top-level variables ---
MODEL_HOST_DIR=/home/dom/llm-scaler-prod/models/Qwen3.6-27B   # or Qwen3.6-35B-A3B
SERVED_NAME=qwen36-27b                                        # or qwen36-35b
NAME=vllm-qwen36-27b-int4                                     # unique per instance
PORT=8001                                                     # 8002 for second instance
GPU_ID=0                                                      # 0 -> 27B, 1 -> 35B
IMAGE="intel/llm-scaler-vllm:0.21.0-b2"
MAX_LEN=262144
GPU_UTIL=0.95
# --- End variables ---

bash vllm-qwen36-int4-b2-1gpu.sh
```

Runs one model per GPU: 27B on GPU 0 (port 8001), 35B on GPU 1 (port 8002).

## Launch Script

See `vllm-qwen36-int4-b2-1gpu.sh` for the full launcher with:
- Abstracted top-level variables (model dir, port, GPU, context, util)
- Stale container cleanup
- In-container launch script generation (avoids nested-quote JSON mangling of
  `--speculative-config` / `--override-generation-config`)
- Health check loop with startup monitoring (~4 min load: BF16 + INT4 quant + MTP)
- Smoke tests (thinking + tool call) and KV cache report

## Environment

| Field | Value |
| --- | --- |
| OS | Ubuntu 26.04 LTS |
| Kernel | 7.0.0-29-generic |
| CPU | AMD Ryzen 9 9950X (16 cores) |
| GPU | 2x Intel Arc B70 (Battlemage G31), PCIe 4.0 x8 |
| VRAM | 32 GB per card (64 GB total) |
| Driver | xe |
| Runtime | vLLM 0.21 via `intel/llm-scaler-vllm:0.21.0-b2` |
| Model | Qwen3.6-27B (dense) / Qwen3.6-35B-A3B (35B total, 3B active MoE) |
| Quantization | INT4 (sym_int4, in-place, group_size 128, GPTQ layout) |
| KV cache | fp8_e4m3 (Triton attention backend) |
| Context | 27B: 131072 (131k) | 35B: 262144 (262k) |
| Tensor parallelism | 1 (one GPU per instance; see design notes) |
| Thinking mode | enabled via chat template kwargs, preserved |
| Reasoning parser | qwen3 |
| MTP | **disabled** (A/B-verified: costs 3.45x decode at depth 32k on 35B) |
| Tool calling | `--enable-auto-tool-choice --tool-call-parser qwen3_xml` |
| Sampling | 27B: temp 0.6, top_p 0.95, top_k 20, min_p 0.0, presence 0.0 | 35B: temp 1.0, top_p 0.95, top_k 20, min_p 0.0, presence 1.5 |
| Max sequences | 27B: 2 | 35B: 3 |

## Measured Results (2026-08-04, dual B70 host)

| Model | GPU | Weights (INT4) | KV cache | KV tokens | Load time |
| --- | --- | --- | --- | --- | --- |
| Qwen3.6-27B | 0 | 18.2 GiB | 10.2 GiB | 292,759 | ~240s |
| Qwen3.6-35B-A3B MoE | 1 | 19.7 GiB | 8.74 GiB | 728,975 | ~360s |

Verified on live servers:
- MTP acceptance: 84-88% avg draft acceptance, mean acceptance length ~2.7
- Tool call: model emitted `get_weather` with `{"city":"Knoxville"}`,
  `finish_reason: tool_calls`
- Vision: correctly identified red circle / green square / blue triangle +
  dark blue background on a generated test image
- Thinking: `reasoning` field populated in API responses

## Benchmark Results (llama-benchy 0.4.1.dev1, pp=2048 tg=1024, 5 runs/depth)

Method, verification, and raw per-run data in
[`benchmarks/BENCHMARKS.md`](benchmarks/BENCHMARKS.md).

| Model | depth | pp tok/s | tg tok/s | peak tok/s | TTFR ms |
| --- | --- | --- | --- | --- | --- |
| 35B-A3B MoE | 0 | 5647.8 ± 399.2 | 103.3 ± 3.5 | 119.4 | 378.3 |
| 35B-A3B MoE | 4096 | 6220.4 ± 188.8 | 77.8 ± 3.7 | 89.4 | 946.6 |
| 35B-A3B MoE | 8192 | 5671.5 ± 303.8 | 33.3 ± 13.1 | 43.4 | 1691.0 |
| 35B-A3B MoE | 16384 | 5573.9 ± 29.4 | 39.7 ± 2.8 | 52.8 | 3021.2 |
| 35B-A3B MoE | 32768 | 4677.6 ± 13.2 | 24.8 ± 2.0 | 33.4 | 6814.8 |
| 27B dense | 0 | 1494.6 ± 107.7 | 46.3 ± 1.5 | 54.8 | 1307.1 |
| 27B dense | 4096 | 1536.1 ± 6.8 | 35.9 ± 2.2 | 44.4 | 3711.1 |
| 27B dense | 8192 | 1506.8 ± 5.7 | 29.0 ± 0.7 | 37.4 | 6211.4 |
| 27B dense | 16384 | 1421.5 ± 7.5 | 21.6 ± 1.2 | 28.8 | 11781.5 |
| 27B dense | 32768 | 1264.3 ± 1.6 | 14.9 ± 0.7 | 19.2 | 25060.4 |

Note: the 35B MoE benches faster than the 27B dense because only ~3B experts
are active per token (~9x less compute), despite the larger parameter count.
Both models ran simultaneously (one GPU each) with no interference.

> **MTP A/B finding (2026-08-05):** the MTP-on decode numbers above **understate
> deep-context throughput**. With `--speculative-config` removed (only change),
> tg at depth 32768 rises from 24.8 → **85.5 tok/s** (35B MoE, 3.45x) and
> 14.9 → **23.3 tok/s** (27B, 1.56x). MTP's draft+verify forwards both attend
> the full KV cache at deep context, doubling per-step attention work. MTP
> helps only shallow-context dense serving (27B depth 0: 46 vs 28 tok/s).
> Disable MTP for deep-context workloads. Full A/B in
> [`benchmarks/BENCHMARKS.md`](benchmarks/BENCHMARKS.md).

## Key Design Decisions

- **One GPU, not TP=2**: b2's multi-GPU all-reduce is broken on B70. Intel's own
  source (`vllm/distributed/device_communicators/xpu_communicator.py`) states the
  XPU all-reduce "only returns NaN on large (prefill-sized) buffers" and the NaN
  "cascades to garbage ('!!!!') decode output". Every TP=2 launch died with
  `UR_RESULT_ERROR_DEVICE_LOST` at the first forward pass; TP=1 serves correctly.
- **sym_int4 instead of FP8**: b2 ships dedicated ESIMD INT4 fused kernels;
  `sym_int4` is its native online-quant method (registered CLI choice, no
  checkpoint metadata needed). Its fast path is the GPTQ layout (`qweight [K/8, N]`,
  group_size 128, symmetric).
- **fp8_e4m3 KV cache**: XPU flash-attention reports `flash_attn_supports_fp8=False`,
  but the **Triton attention backend** implements FP8 KV with per-tensor scales.
  Result: ~3x KV tokens at the same memory (103k -> 293k on the 27B).
- **In-place INT4 quant**: `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1` stages BF16
  weights in system RAM and quantizes in place — no VRAM spike.
- **Full BF16 checkpoint, NOT pretrained quantized**: online quant is the proven
  path on this image (same as the FP8 recipe); pretrained FP8 still hit the
  TP=2 all-reduce crash.
- **`ZE_AFFINITY_MASK` only**: `ONEAPI_DEVICE_SELECTOR=level_zero:1` breaks
  device discovery on the second GPU (torch sees zero devices). Mask alone
  re-maps the chosen GPU to index 0.
- **gpu_memory_utilization 0.95**: full 262144 context needs ~9.1 GiB fp8 KV;
  0.90 leaves only 8.6 GiB ("estimated maximum model length is 245760").
- **MTP is a tradeoff, not a default win**: verified by A/B — at depth 32768,
  MTP costs 3.45x (35B) / 1.56x (27B) decode throughput because draft+verify
  both attend the full KV cache. It only helps shallow-context dense serving.
  **Disabled by default in the final config.** See `benchmarks/BENCHMARKS.md`.
- **35B MoE + thinking mode emits `!`-repetition garbage (open issue)**: the
  MoE under `sym_int4` degenerates into `!!!!...` in the reasoning chain on
  trivial prompts, across all sampling values; 27B dense is clean on the same
  recipe. Workaround: thinking OFF on the 35B, or a different quantization.
  See `benchmarks/BENCHMARKS.md` quality finding.

## Dead Ends Documented (do not retry)

| Attempt | Result |
| --- | --- |
| TP=2 with pre-quantized `Qwen/Qwen3.6-27B-FP8` (block-128) | loads in 4s, correct `XPUFp8BlockScaledMMKernel`, still DEVICE_LOST at first forward |
| `TORCH_LLM_ALLREDUCE=1` | causes DEVICE_LOST at profile_run — remove |
| `VLLM_XPU_ALLREDUCE_RETRY_ON_NAN=1` | hangs at 98% CPU in `_xpu_tensor_has_nan` |
| Host L0/NEO stack mount (libze 39122 + igc 2.38.2) | b1/b2 ship identical bundled drivers; no effect |
| `xpu_block_stub.py` (disable ESIMD FP8 block kernel) | does not fix TP=2 |
| `DISABLE_ESIMD_*=1` (all ESIMD off) | does not fix TP=2; causes OOM in native rms_norm |

## Reasoning / Thinking Mode

- `enable_thinking=true` via `--default-chat-template-kwargs`
- `preserve_thinking=true` in chat template kwargs
- Reasoning parser: `qwen3` via `--reasoning-parser qwen3`
- MTP note: `min_p`/`logit_bias` are ignored under speculative decoding (vLLM warning); harmless here since `min_p=0.0`

## Notes

- Model directory must be mounted read-only: `-v ${MODEL_HOST_DIR}:/model:ro`
- Port 8001 default; 8002 for the second instance; change via `PORT`
- `--limit-mm-per-prompt` is NOT set: vision is enabled and verified
- Container auto-restarts (`--restart unless-stopped`)
