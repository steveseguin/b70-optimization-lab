# Qwen3.6 27B FP8 on 2x Intel Arc Pro B70 (Docker TP2)

> **Maintainer note — community submission, `B70-tested`.**
> This recipe was contributed in
> [PR #9](https://github.com/steveseguin/b70-optimization-lab/pull/9) by
> `dominick253` and is preserved below exactly as submitted.
>
> It was executed in the reference lab on 2026-07-25 and **it works**: TP2
> serves `Qwen/Qwen3.6-27B` at native FP8 across two B70s. The **throughput
> claim did not reproduce** — this lab measures 30.171 tok/s median decode
> (stdev 0.302, 15 rows) against the "34 Tokens a second" stated below.
>
> Read [`STATUS.md`](STATUS.md) before running any of this. It records the
> measurement, the deviations required to run the command as written, and
> seven known issues — including a hardcoded path that will fail for you, and
> that the recipe as written exposes an unauthenticated endpoint on every
> network interface.
>
> Everything below this line is the contributor's text, unedited.

---

Deployable Docker recipe for serving `Qwen/Qwen3.6-27B` in native FP8 quantization
across two Intel Arc Pro B70 GPUs using `intel/llm-scaler-vllm`.

## Status

- **Working** on 2x B70 (TP2), tested 2026-07-22
- OpenAI-compatible endpoint on `0.0.0.0:8001`
- Served model name: `qwen36-27b-fp8`
- Max context: `262144` tokens
- FP8 KV cache (`fp8_e4m3`)
- Eager mode (no XPU graph capture)
- Reasoning parser: `qwen3` (thinking enabled by default)
- Tool call parser: `qwen3_coder` with auto tool choice

## Model

- HF repo: `Qwen/Qwen3.6-27B`
- Snapshot commit: `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`
- Quantization: native FP8 (`--quantization fp8`)
- Dtype: `float16`
- Tensor parallel: `2`

## One-Command Start

Requires Docker, two Intel Arc Pro B70s visible at `/dev/dri`, and the model
pre-cached at `~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B`.

```bash
docker run -d \
  --name vllm-qwen36-27b-fp8 \
  --restart unless-stopped \
  --privileged \
  --net=host \
  --ipc=host \
  --shm-size=32g \
  --device=/dev/dri \
  --group-add $(getent group render | cut -d: -f3) \
  -v /home/dom/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B:/model:ro \
  -e ZE_AFFINITY_MASK=0,1 \
  -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
  -e VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1 \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True \
  -e CCL_TOPO_P2P_ACCESS=1 \
  -e CCL_ATL_TRANSPORT=ofi \
  -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
  -e TORCH_LLM_ALLREDUCE=1 \
  -e CCL_ZE_IPC_EXCHANGE=pidfd \
  -e UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
  --entrypoint /bin/bash \
  intel/llm-scaler-vllm:0.21.0-b1 \
  -lc "vllm serve \
    --model /model/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9 \
    --served-model-name qwen36-27b-fp8 \
    --tensor-parallel-size 2 \
    --host 0.0.0.0 --port 8001 \
    --dtype float16 \
    --quantization fp8 \
    --kv-cache-dtype fp8_e4m3 \
    --max-model-len 262144 \
    --block-size 128 \
    --max-num-seqs 4 \
    --gpu-memory-utilization 0.92 \
    --enforce-eager \
    --no-enable-prefix-caching \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --trust-remote-code \
    --override-generation-config '{\"temperature\": 0.7, \"top_p\": 0.8, \"top_k\": 20, \"presence_penalty\": 1.5, \"repetition_penalty\": 1.0}' \
    --default-chat-template-kwargs '{\"enable_thinking\": true, \"preserve_thinking\": true}'"
```

## Environment Variables

| Variable | Value | Purpose |
|---|---|---|
| `ZE_AFFINITY_MASK` | `0,1` | Pin to GPUs 0 and 1 |
| `ONEAPI_DEVICE_SELECTOR` | `level_zero:0,1` | Level Zero device selection |
| `VLLM_ALLOW_LONG_MAX_MODEL_LEN` | `1` | Permit 262K context window |
| `VLLM_WORKER_MULTIPROC_METHOD` | `spawn` | Required for multi-worker XPU |
| `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT` | `1` | Offload weights before FP8 quant |
| `PYTORCH_ALLOC_CONF` | `expandable_segments:True` | Fragmentation mitigation |
| `CCL_TOPO_P2P_ACCESS` | `1` | Enable P2P for oneCCL |
| `CCL_ATL_TRANSPORT` | `ofi` | OFI transport for oneCCL |
| `TORCH_LLM_ALLREDUCE` | `1` | Optimized all-reduce path |
| `CCL_ZE_IPC_EXCHANGE` | `pidfd` | Level Zero IPC via pidfd |
| `UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS` | `1` | Relax Level Zero alloc limits |

## vLLM Serve Flags

| Flag | Value | Purpose |
|---|---|---|
| `--tensor-parallel-size` | `2` | Split across 2 B70s |
| `--dtype` | `float16` | Compute dtype |
| `--quantization` | `fp8` | Native FP8 weight quantization |
| `--kv-cache-dtype` | `fp8_e4m3` | FP8 KV cache |
| `--max-model-len` | `262144` | 256K context window |
| `--block-size` | `128` | Paged attention block size |
| `--max-num-seqs` | `4` | Max concurrent sequences |
| `--gpu-memory-utilization` | `0.92` | 92% VRAM for KV cache |
| `--enforce-eager` | | Disable graph capture (stability) |
| `--no-enable-prefix-caching` | | Disable prefix caching |
| `--enable-auto-tool-choice` | | Enable function calling |
| `--tool-call-parser` | `qwen3_coder` | Qwen3 tool call parsing |
| `--reasoning-parser` | `qwen3` | Qwen3 reasoning/thinking parser |
| `--trust-remote-code` | | Trust HF model code |

## Health Check

```bash
curl http://127.0.0.1:8001/v1/models
curl http://127.0.0.1:8001/health
```

## Stop / Remove

```bash
docker stop vllm-qwen36-27b-fp8
docker rm vllm-qwen36-27b-fp8
```
~Tokens	Output	Total (s)	Prefill (s)	Tokens/sec
10	256	7.4	0.37	34.6
50	256	7.4	0.37	34.7
200	256	8.7	0.44	29.4
500	256	9.0	0.45	28.3
2000	256	7.5	0.37	34.2
## Differences from Prior Qwen3.6 FP8 Slot

The older `configs/model-slots/qwen36-27b-fp8-vrfai.env` slot used
`vrfai/Qwen3.6-27B-FP8` with `compressed-tensors` quantization and required a
BF16 dequant fallback. This recipe uses the official `Qwen/Qwen3.6-27B` model
with native `--quantization fp8`, runs in Docker for isolation, and targets TP2
on two B70s with a 256K context window.

## Notes

- `--enforce-eager` is used for stability; XPU graph capture is not enabled.
- `--no-enable-prefix-caching` avoids prefix cache overhead for this FP8 config.
- Model is mounted read-only from the HF cache. Adjust the `-v` path if your
  cache location differs.
- `--privileged` and `--device=/dev/dri` are required for Level Zero GPU access.
- `--shm-size=32g` prevents IPC shared memory exhaustion during multi-worker
  startup.
