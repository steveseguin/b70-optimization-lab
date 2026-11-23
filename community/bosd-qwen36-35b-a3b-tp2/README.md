# Qwen3.6-35B-A3B GPTQ-Int4 — dual-B70 vLLM TP2 serving: the `0.31.0-b1-experimental` image clears the post-init APIServer hang

> **Maintainer note (2026-11-22).** Community submission, not reproduced in the reference lab. The model is a
> local GPTQ export with no published source, so it could not be re-run here. Read [`STATUS.md`](STATUS.md) first.
> Its maintainer review lists what was checked and one inconsistency in the single-stream number.

---

**Evidence level: community-reported** (measured on a community B70 host, not the reference lab).

## TL;DR

Dual-B70 tensor-parallel (TP2) serving of `Qwen3.6-35B-A3B` (GDN MoE) under
vLLM-XPU has two historically-separate walls on Battlemage B70:

1. the init-time `DEVICE_LOST` / `determine_available_memory` crash, and
2. a **post-init APIServer hang** — the engine finishes init but Uvicorn never
   binds, so there is no endpoint.

On `intel/llm-scaler-vllm:1.5` (vLLM 0.26.1) the DEVICE_LOST wall is cleared by
the newer oneCCL, engine init completes cleanly, **but the APIServer never
starts** (`/health` stays `000` forever; `Application startup complete` never
prints). Switching only the image tag to
**`intel/llm-scaler-vllm:0.31.0-b1-experimental`** (newer vLLM; see "Version note"
below), with an otherwise identical command, makes the APIServer bind normally
and produces a **live dual-B70 TP2 OpenAI endpoint** for the first time on this
host. Peak measured aggregate throughput **~1268 tok/s at concurrency 96** on the
35B-A3B MoE across two B70s.

## Claim (as reported by the contributor)

For dual-B70 vLLM-XPU TP2 serving of Qwen3.6-35B-A3B GPTQ-Int4, image
`0.31.0-b1-experimental` serves where `1.5` hangs post-init; measured aggregate
throughput scales near-linearly to concurrency 64 and peaks at ~1268 tok/s at
concurrency 96. Single-stream is ~10.6 tok/s (TP2 communication overhead; TP2's
value here is aggregate throughput and fitting a >24 GB model, not latency).

## Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2× Intel Arc Pro B70, 32 GB each (host also has 1× B60, not used for this run); `ZE_AFFINITY_MASK=1,2` |
| Interconnect | ASRock TRX50 / Threadripper 9960X; both B70s on CPU-attached PCIe (TP2 is not link-bound on this class per prior lab A/B) |
| Host RAM | 62 GB (see "Host-RAM gating" — all other GPU services must be stopped first) |
| OS / kernel | Fedora 44 / kernel 7.3.4 |
| GPU driver | `xe` |
| compute-runtime / level-zero | 26.35.39758.21 |
| Engine / image | `docker.io/intel/llm-scaler-vllm:0.31.0-b1-experimental` (Docker Hub 2026-10-12, 19.7 GB on disk) |
| vLLM version | `0.31.0+xpu.llmscaler` (from the server banner; the `1.5` image that hangs reports `0.26.1.dev0+g568afb3a1`) |
| Model repo / revision | `Qwen3.6-35B-A3B`, GPTQ-Int4 (local GPTQ export; `qwen3_5_moe` / GatedDeltaNet hybrid MoE, 256 experts, ~A3B active) |
| Quantization | weights GPTQ-Int4 (`XPUwNa16LinearKernel` / auto_gptq); KV auto (fp16); dtype float16 |
| Prompt / output / context | ~45-token prompt, 256 output tokens (`ignore_eos` for a fixed decode length), `--max-model-len 8192` |
| Concurrency | 1, 24, 48, 64, 96 (client-side ThreadPool to `/v1/completions`) |
| Cache / speculation | prefix caching off; no speculative decoding; `--enforce-eager` |
| KV cache | 14.58 GiB/worker, 873,033 tokens, 106× max concurrency reported by the engine |

## Command / recipe

Identical to a working `1.5` TP2 launch except for the image tag. Uses the
image's own entrypoint (it sources oneAPI `setvars` + CCL); the model and its
args are passed as the container command.

```bash
IMG=docker.io/intel/llm-scaler-vllm:0.31.0-b1-experimental
MODEL=/path/to/qwen36-35b-a3b-gptq      # substitute your own weights dir

podman run -d --name tp2 \
  --device /dev/dri --security-opt label=disable --privileged --net host --ipc host \
  -e ZE_AFFINITY_MASK=1,2 -e ZE_FLAT_DEVICE_HIERARCHY=COMPOSITE \
  -e CCL_ENABLE_SYCL_KERNELS=0 \
  -e CCL_ATL_TRANSPORT=ofi \
  -e CCL_ZE_IPC_EXCHANGE=pidfd \
  -e CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0 \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
  -e SYCL_UR_USE_LEVEL_ZERO_V2=0 \
  -e UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
  -e ZES_ENABLE_SYSMAN=1 \
  -v "$MODEL":/model:ro \
  "$IMG" \
    /model --quantization gptq --dtype float16 \
    --tensor-parallel-size 2 --distributed-executor-backend mp \
    --max-model-len 8192 --gpu-memory-utilization 0.85 \
    --enforce-eager --port 8000 --served-model-name tp2-test
```

The CCL environment is the community `vllm#41663` recipe (confirmed applied via
the `CCL_WARN ... changed to be` lines in the worker logs). `--shm-size` must NOT
be combined with `--ipc host` (they conflict).

## Results

Aggregate decode throughput, 256 tokens/request, `ignore_eos`, warm engine:

| concurrency | aggregate tok/s | per-stream tok/s |
| --- | --- | --- |
| 1 | 10.6 | 10.6 |
| 24 | 399 | 16.6 |
| 48 | 765 | 15.9 |
| 64 | 985 | 15.4 |
| 96 | **1268** | 13.2 |

Near-linear to concurrency 64 (per-stream barely drops); the knee is ~64–96.
Single-stream is below a single-card Int4 decode of the same family, as
expected for TP2 cross-card communication overhead — the win is aggregate
throughput at concurrency and the ability to serve a model too large to prefer
on one card, not single-request latency.

Independently re-measured with `lmx speed-test matrix run` (the LocalMaxxing CLI's
own sustained-decode method, `benchVersion 0.7.7`, 256 max-tokens, ctx 0) —
aggregate decode tok/s: **1→16.1, 24→391.0, 48→718.8, 64→932.5, 96→1217.4**,
corroborating the table above. Submitted to LocalMaxxing as an inference matrix:
https://www.localmaxxing.com/en/inference-benchmarks/cmwsasd8k008vqh01im51npfg

`init engine (profile, create kv cache, warmup model)` ≈ 60 s; native
`qwen3_5_moe_text` Qwen-Triton warmup runs; then on `0.31.0-b1-experimental`:
`Application startup complete`, `/health` → 200, `/v1/models` → `tp2-test`.

## Key finding: image, not flags

The post-init APIServer hang on `1.5` (vLLM 0.26.1) is **reproducible and
independent of** port (8000 vs 8001), GPU contention (both B70s free), and
`VLLM_ENABLE_V1_MULTIPROCESSING=0` (no effect). `--disable-frontend-multiprocessing`
does not exist in this vLLM (v1). On `1.5` the engine prints
`init engine ... took ~60 s` and then the APIServer process prints nothing
further. The only change that fixes it is the image tag → `0.31.0-b1-experimental`.
So this is a vLLM v1 frontend / EngineCore-handshake behavior that differs
between the two image builds, not a tunable on `1.5`.

## Host-RAM gating (not silicon)

With only 62 GB host RAM, two TP2 workers staging ~20.8 GiB checkpoint shards
each will OOM if other GPU services are running. Stop all single-card services
first (free ~58 GB) before launching TP2. This is a host capacity constraint,
not a GPU/CCL limit.

## Version note / what is still unconfirmed

- The serving image reports vLLM `0.31.0+xpu.llmscaler`; the `1.5` image that
  hangs reports `0.26.1.dev0+g568afb3a1`. The APIServer-start behavior differs
  between the two builds with an otherwise identical command.
- Throughput was measured with a client-side ThreadPool, not vLLM's
  `benchmark_serving`; numbers are wall-clock aggregate completion-tokens/s, no
  TTFT breakdown.
- Quality gate: outputs were coherent on a generic prompt; no formal quality
  eval (e.g. HumanEval+) was run.

## Durable links

- LocalMaxxing inference matrix (lmx-measured, this result):
  https://www.localmaxxing.com/en/inference-benchmarks/cmwsasd8k008vqh01im51npfg

## Repro assets

- `vllm-qwen36-35b-a3b-tp2.sh` — the launch recipe above.
- `reported/bench.txt` — raw concurrency-sweep output (ThreadPool + lmx matrix).
