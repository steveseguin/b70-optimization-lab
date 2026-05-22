# MiniMax warm-repeat throughput probe

Date: 2026-05-20

## Purpose

The strict LocalMaxxing-style runs still use separate process launches and full
model reloads for each repeat. That is the right public comparison path, but it
mixes decode variance with 112 GiB checkpoint reloads, XPU graph setup, process
startup, and teardown noise.

This probe keeps one vLLM engine alive, performs one warmup generation, then
runs four measured generations against the same p512/n1536 shape. It is a
diagnostic measurement only, not a replacement for the strict quality gate or
the promoted LocalMaxxing result.

## Setup

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Engine: vLLM `0.20.1-local`, XPU/Level Zero, tensor parallel 4
- Hardware: 4x Intel Arc Pro B70 32GB
- Quantization: AutoRound INT4 / INC WNA16
- Active extension: source-rebuilt llm-scaler WS binary
- Extension SHA256: `30b19be4456abab814f3378561204d575e4e8c01f848634a059d72ff3b23db66`
- Workload: `input_len=512`, `output_len=1536`, `num_prompts=1`
- Runtime: `max_model_len=2048`, `max_num_batched_tokens=512`,
  `block_size=256`, `dtype=float16`, chunked prefill enabled
- Prompt mode: deterministic synthetic offset token prompt
- Sampling: `temperature=1.0`, `top_p=1.0`, `top_k=-1`, `ignore_eos=True`

The log confirms the intended path:

```text
Using llm-scaler XPU INT4 MiniMax logits WS decode path
```

## Command Shape

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
source /home/steve/llm-optimizations-publish/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh

python /home/steve/llm-optimizations-publish/scripts/run-vllm-minimax-warm-throughput.py \
  --model /mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround \
  --out /home/steve/bench-results/minimax-m2.7-post-repro-optimization/warm-throughput-20260520T124510Z/minimax-ws-source-rebuild-warm-throughput-p512n1536.json \
  --tensor-parallel-size 4 \
  --dtype float16 \
  --max-model-len 2048 \
  --max-num-batched-tokens 512 \
  --max-num-seqs 1 \
  --block-size 256 \
  --input-len 512 \
  --output-len 1536 \
  --num-prompts 1 \
  --warmup-repeats 1 \
  --repeats 4
```

## Result

- Mean output throughput: `92.535653` tok/s
- Mean total throughput: `123.380870` tok/s
- Output min/max: `92.518023` / `92.545692` tok/s
- Output standard deviation: `0.012139` tok/s
- Engine init time: `125.668520` seconds
- Warmup repeat: `17.240933` seconds for 1536 output tokens

Measured repeats:

| Repeat | Elapsed s | Output tok/s | Total tok/s | Token hash |
| --- | ---: | ---: | ---: | --- |
| 0 | `16.598489` | `92.538545` | `123.384726` | `d52c7f46696b03d0733f35466cc9865281b13654de156ca988ec6f11598ece29` |
| 1 | `16.598165` | `92.540352` | `123.387136` | `9917b0f1063d3b6a7259aef7326b74ffbe07cdecc9e7dd3d17df627736cfd9c3` |
| 2 | `16.602171` | `92.518023` | `123.357364` | `4c5a39f1641c8fb4261227d2c6a93358f2d21722938f8798d4a471566635b36a` |
| 3 | `16.597207` | `92.545692` | `123.394256` | `2d0703f8a27dabcc00f8e999d7984199fe08e5d4ae956c25f87efc15d3f51748` |

## Interpretation

The warm in-process decode path is very stable and faster than the separate
process strict benchmark (`87.964466` tok/s in the immediate source-rebuild
validation and `89.314195` tok/s in the promoted public result). The gap points
to process-level measurement overhead, dataset/prompt path differences, or
stock benchmark scheduler behavior rather than a quality change.

Do not submit this number to LocalMaxxing as a normal benchmark unless it is
clearly labeled as an in-process warm-repeat diagnostic. The promoted public
result remains `89.314195` output tok/s until a strict, quality-clean run beats
it.

## Follow-ups

1. Add an equivalent warm-repeat mode to the strict harness or wrap stock
   `vllm bench throughput` so the public comparison and warm diagnostic share
   the exact same prompt dataset.
2. Profile the remaining delta between stock-bench `89.31` and warm-engine
   `92.54` before changing model math.
3. Keep strict quality hashes mandatory before promoting any optimization:
   raw145 n64/n256, semantic suite, arithmetic repeat, and extended sixpack.
