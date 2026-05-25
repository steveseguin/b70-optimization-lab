# 2026-05-25 C2 Session-Cache Capacity Ladder

Goal: characterize the best currently promising CPU KV offload lane: two
OpenAI-compatible requests, each individually fitting in the 32K server window,
with combined KV pressure above the live GPU KV budget.

This is still session caching/reload. It is not true active attention over a
single 64K or 196K request.

## Prompt Harness

The canary script was tightened for this ladder:

```bash
experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py \
  --prompt-mode strict-word \
  --prompt-lines 1080 \
  --max-tokens 4 \
  --passes 2 \
  --concurrency 2 \
  --labels B,D
```

Script prompt version:

`strict-word-answer-space-v2`

The v2 change makes the final `ANSWER:` field include a trailing space. That
avoids one false-failure class where the first generated token is only
whitespace or a newline.

Labels used:

| Label | Expected word |
| --- | --- |
| B | `blue` |
| D | `yellow` |

These labels were chosen because the GPU-only baseline consistently produced
the expected first word across the ladder. Label A/red and C/green were less
stable under shorter v2 prompt shapes, so they are not good capacity-ladder
canaries yet.

Primary pass condition:

- expected first word matches
- first word matches the GPU-only baseline

Exact full-text hashes are still recorded, but they are not the main pass
condition for this ladder because the model can add additional continuation text
after the correct word even in GPU-only mode.

## Server

Temporary c2 server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --max-num-seqs 2 \
  --no-scheduler-reserve-full-isl
```

Startup facts:

- `max_model_len=32768`
- `max_num_seqs=2`
- GPU KV cache size: `34304` tokens
- maximum concurrency for 32768 tokens per request: `1.05x`
- CPU KV offload admission budget: `4.0 GiB` per worker
- 4 tensor-parallel workers, so the configured CPU KV budget is about `16 GiB`
  total
- cached compile time: about `5.65-6.08 s`

Main log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c2-kvoffload16-ladder-20260525T032821Z.log`

Fresh near-max log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c2-kvoffload16-ladder-coldmax-20260525T033304Z.log`

## GPU-Only Baselines

Baselines used the normal stable server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

Baseline files:

| Prompt lines | Prompt tokens/session | File |
| ---: | ---: | --- |
| `264` | `7994` | `strict-word-v2-c1-gpu-ladder-bd-lines264-20260525T032230Z.json` |
| `531` | `16004` | `strict-word-v2-c1-gpu-ladder-bd-lines531-20260525T032252Z.json` |
| `700` | `21074` | `strict-word-v2-c1-gpu-ladder-bd-lines700-20260525T032335Z.json` |
| `1000` | `30074` | `strict-word-v2-c1-gpu-ladder-bd-lines1000-20260525T032434Z.json` |
| `1080` | `32474` | `strict-word-v2-c1-gpu-ladder-bd-lines1080-20260525T032559Z.json` |

Every baseline produced the expected first word for B and D across both passes.

## C2 Ladder Results

The ladder was run from small to large prompts. Because the prompts share long
prefixes, larger first-pass timings after the first few shapes are warm-prefix
numbers. The fresh near-max run below gives the independent cold 32.5K result.

| Prompt lines | Tokens/session | Combined prompt tokens | C2 pass 1 TTFT | C2 pass 2 reload TTFT | First-word result |
| ---: | ---: | ---: | ---: | ---: | --- |
| `264` | `7994` | `15988` | `5.876-11.256 s` | `0.315 s` | pass |
| `531` | `16004` | `32008` | `6.135-11.821 s` | `0.531 s` | pass |
| `700` | `21074` | `42148` | `5.606-8.210 s` | `0.437-0.857 s` | pass |
| `1000` | `30074` | `60148` | `7.211-14.323 s` | `0.563-1.075 s` | pass |
| `1080` | `32474` | `64948` | `2.309-4.569 s` | `0.612-1.173 s` | pass |

Result files:

| Prompt lines | File |
| ---: | --- |
| `264` | `strict-word-v2-c2-kvoffload16-ladder-bd-lines264-20260525T033112Z.json` |
| `531` | `strict-word-v2-c2-kvoffload16-ladder-bd-lines531-20260525T033128Z.json` |
| `700` | `strict-word-v2-c2-kvoffload16-ladder-bd-lines700-20260525T033144Z.json` |
| `1000` | `strict-word-v2-c2-kvoffload16-ladder-bd-lines1000-20260525T033157Z.json` |
| `1080` | `strict-word-v2-c2-kvoffload16-ladder-bd-lines1080-20260525T033217Z.json` |

Interpretation:

- `700`, `1000`, and `1080` exceed the `34304` GPU KV budget when two sessions
  are combined.
- All tested c2 shapes produced the expected first word for both sessions.
- All tested c2 shapes matched the GPU-only baseline by first word.
- The 32.5K/session shape is very close to the 32K production context window and
  still reloaded in about `0.6-1.2 s` on the second pass.

## Fresh Near-Max C2 Run

To avoid warm-prefix effects from the increasing ladder, c2 was restarted and
the largest shape was run first.

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-v2-c2-kvoffload16-coldmax-bd-lines1080-20260525T033558Z.json`

Shape:

- prompt lines: `1080`
- prompt tokens/session: `32474`
- combined prompt tokens: `64948`
- max output tokens/session: `4`
- concurrency: `2`

Results:

| Label | Pass | Elapsed | TTFT | Expected word |
| --- | ---: | ---: | ---: | --- |
| D | 1 | `25.568 s` | `24.758 s` | pass |
| B | 1 | `48.400 s` | `48.363 s` | pass |
| D | 2 | `0.706 s` | `0.668 s` | pass |
| B | 2 | `1.279 s` | `1.232 s` | pass |

This is the cleanest current result for "two parked near-full-context sessions."
The first pass is expensive because it performs the cold prefill. The second
pass shows the practical reload cost.

## Transfer Rates

Representative vLLM transfer metrics:

| Run | Direction | Bytes | Time | Effective rate |
| --- | --- | ---: | ---: | ---: |
| ladder | CPU -> GPU | `31595692032` | `2.199539368 s` | about `14.4 GB/s` |
| ladder | CPU -> GPU | `15212740608` | `1.057119960 s` | about `14.4 GB/s` |
| ladder | CPU -> GPU | `10661920768` | `0.758284748 s` | about `14.1 GB/s` |
| cold max | CPU -> GPU | `16382951424` | `1.110355116 s` | about `14.8 GB/s` |
| cold max | GPU -> CPU | `3640655872` | `0.313721252 s` | about `11.6 GB/s` |
| cold max | GPU -> CPU | `3185573888` | `0.265817760 s` | about `12.0 GB/s` |

The PCIe4-era host reload path is roughly `14-15 GB/s` CPU-to-GPU in these
measurements.

## CPU RAM Notes

System/RSS measurement file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-v2-c2-kvoffload16-ladder-system-20260525T033112Z.log`

Fresh near-max system/RSS file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-v2-c2-kvoffload16-coldmax-system-20260525T033558Z.log`

Observed process RSS:

| Run | Before | After | Delta |
| --- | ---: | ---: | ---: |
| increasing ladder | `23.487 GiB` | `23.756 GiB` | `+0.269 GiB` |
| fresh near-max | `17.962 GiB` | `18.260 GiB` | `+0.298 GiB` |

Do not treat RSS delta as the true KV size. vLLM reports a configured CPU KV
admission budget of `4.0 GiB` per worker, about `16 GiB` total across four
workers. Linux memory accounting also moved around because page cache changed
during model loads and test runs.

## Recommendation

Current stable production endpoint remains c1 32K:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

The c2 CPU KV session-cache lane is now the best experimental multitask mode:

- two near-32K sessions can be parked/reloaded
- first-word correctness matched the GPU-only baseline across the ladder
- near-max reload TTFT was about `0.7-1.3 s`
- host reload bandwidth was about `14-15 GB/s`

Do not yet call it quality-equivalent for all production use. Exact full-text
hashes can vary because the model sometimes emits different continuation text
after the correct word even in GPU-only mode. A stronger semantic/logprob canary
is still needed before this becomes the default server mode.
