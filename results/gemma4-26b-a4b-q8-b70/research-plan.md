# Gemma 4 26B A4B Q8 B70 Research Plan

Research snapshot: 2026-06-23. Goal: maximize valid single-session decode for
one complete Q8/INT8-quality Gemma 4 26B A4B replica per B70, then run four
replicas on four GPUs for parallel research and aggregate service capacity.

## Non-Negotiables

- Default precision is Q8 / INT8-or-better. Lower precision can be a diagnostic
  side result, but not a promoted result in this lane.
- Validate chat mode first. Raw `/v1/completions` is useful as a diagnostic, but
  the instruction-tuned deployment path is `/v1/chat/completions`.
- No tensor-parallel split in the primary lane. The design is one full model per
  GPU to avoid PCIe collectives.
- Preserve `GGML_SYCL_DISABLE_OPT=1` until a repeat canary proves optimized
  SYCL paths are not corrupting Gemma 4 on B70.
- Do not promote from a smoke. Use 32-repeat early canaries and 96+ repeats
  before any record or LocalMaxxing submission.

## Phase 1: First Valid Q8 llama.cpp Baseline

Start after the Q8 file download completes.

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 UBATCH_SIZE=64 \
  scripts/run-gemma4-26b-llamacpp-replica.sh
```

Gate:

```bash
python3 scripts/gemma4-text-canary.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --api-mode chat \
  --repeats 32 \
  --out data/gemma4-26b-a4b-q8-b70-chat-canary-32.json

python3 scripts/bench-openai-single-decode.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --api-mode chat \
  --prompt-tokens 512 \
  --max-tokens 512 \
  --repeats 8 \
  --out data/gemma4-26b-a4b-q8-b70-p512o512-chat-baseline.json
```

If 8K does not fit, retry `CTX_SIZE=4096`, then `2048`, without changing weight
or KV precision. Only after a valid baseline should q8 KV be tried.

## Phase 2: Four Replica Baseline

Once one GPU is valid, launch all four independent replicas:

```bash
cd /home/steve/qwen36-results-main
CTX_SIZE=8192 UBATCH_SIZE=64 scripts/run-gemma4-26b-llamacpp-quad.sh
```

Measure each port independently first. Aggregate throughput is only meaningful
after each server passes the same chat canary.

Ports:

```text
18260 -> GPU 0
18261 -> GPU 1
18262 -> GPU 2
18263 -> GPU 3
```

## Phase 3: No-Spec Speed Sweeps

Run one control plus three experiments in parallel:

| GPU | Purpose | First sweep |
| --- | --- | --- |
| 0 | Control | `-fa on`, f16 KV, `CTX_SIZE=8192`, `UBATCH_SIZE=64`, `GGML_SYCL_DISABLE_OPT=1` |
| 1 | Batch/ubatch | `UBATCH_SIZE=128/256/512`, then `BATCH_SIZE=1024/2048` |
| 2 | SYCL runtime flags | `GGML_SYCL_DISABLE_GRAPH=1`, `GGML_SYCL_DISABLE_DNN=1`, then combinations |
| 3 | Risky speed flag | `GGML_SYCL_DISABLE_OPT=0` only with immediate 32-repeat chat canary |

Other follow-up axes:

- AOT build with `GGML_SYCL_DEVICE_ARCH=intel_gpu_bmg_g31`.
- `POLL=25/50/100`, because older Qwen GGUF work found polling can move B70
  decode latency.
- `-fa off` as a correctness/perf control. Keep `-fa on` as default.
- `CACHE_TYPE_K=q8_0 CACHE_TYPE_V=q8_0` only after f16 KV has a valid baseline.
  This may be needed for 32K headroom, but it is a quality-impacting change
  until canaries and practical prompts pass.
- `--no-mmap` / `--mlock` only if load-time paging or first-token stalls show up
  in logs.

Promotion criteria for a speed sweep:

- chat canary 32/32 for smoke, 96+ for promotion;
- no known lower-precision change unless labeled separately;
- benchmark JSON has non-null `usage.completion_tokens` and output tok/s;
- server log captures the exact launcher identity.

## Phase 4: MTP / Speculative Decode

Do not start here. Google's MTP overview warns that MoE models at batch size 1
may have limited speedup because each MTP token can activate different experts,
which reduces expert-weight locality. That makes no-spec Q8 baseline and
batch/ubatch tuning a higher-value first step.

When ready, download the draft file:

```bash
FILENAME=mtp-gemma-4-26B-A4B-it.gguf \
EXPECTED_BYTES=461766816 \
scripts/download-gemma4-26b-q8-gguf.sh
```

First MTP server shape to test:

```bash
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 UBATCH_SIZE=64 \
  EXTRA_LLAMA_ARGS='--spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf --spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-device SYCL0 --spec-draft-ngl all' \
  scripts/run-gemma4-26b-llamacpp-replica.sh
```

The launcher consumes `EXTRA_LLAMA_ARGS` for this follow-up. Test
`--spec-draft-n-max 2/4/6/8`, record
acceptance metrics if llama.cpp exposes them, and run 96+ chat canaries before
believing any speedup.

## Phase 5: vLLM Int8 Per-Channel Comparison

Use only after llama.cpp Q8 has a validated baseline or if llama.cpp cannot
serve the model reliably.

Initial shape:

```bash
ZE_AFFINITY_MASK=0 \
vllm serve google/gemma-4-26B-A4B-it \
  --quantization int8_per_channel_weight_only \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --no-enable-prefix-caching \
  --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
  --port 18270
```

Run four separate DP=1 servers for 4 GPU work. Do not use vLLM
`--data-parallel-size 4` until the public MoE DP issue is resolved or locally
patched.

## Phase 6: Multimodal Smoke

Text speed is first. After text baseline:

1. Download `mmproj-F16.gguf`.
2. Launch one server with `--mmproj`.
3. Run a single image smoke for correctness only.
4. Do not mix multimodal tokens into text throughput records.

## Current Best Hypotheses

1. **Single-GPU Q8 llama.cpp will be memory-tight but viable at 8K.** This gets
   the quality baseline quickly and validates the GGUF/template path.
2. **AOT and ubatch sweeps are the likely early speed wins.** They preserve
   quality and avoid the risk of MTP correctness bugs.
3. **`GGML_SYCL_DISABLE_OPT=0` may be faster but is high-risk.** Only test it
   behind repeated canaries because upstream reports B70/Gemma 4 nonsense
   output without the disable flag.
4. **q8 KV may unlock 32K but is not quality-neutral by default.** Treat it like
   a new precision mode.
5. **MTP could help, but may disappoint at batch 1 for MoE.** It becomes worth
   testing after no-spec baseline because the draft files are small.
6. **vLLM int8-per-channel is the main fallback if llama.cpp is slow.** It may
   use B70/XPU kernels better, but vLLM DP must be four independent servers.

## Stop Conditions

- If Q8 GGUF cannot fit even at 2K with f16 KV, test Q8_0 before lowering to
  Q6.
- If `GGML_SYCL_DISABLE_OPT=0` fails any canary, stop using it until the
  upstream corruption cause is understood.
- If MTP speed wins but canaries fail at repeat depth, mark it invalid and
  preserve the logs; do not chase speed-only LocalMaxxing submissions.
- If all llama.cpp Q8 paths are valid but slow, switch to vLLM int8-per-channel
  rather than weakening quality.
