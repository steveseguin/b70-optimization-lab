# 2026-05-25 Phase 6: Session-Cache Canaries And C4 Ladder

Goal: move beyond the first c2 smoke by testing longer post-reload decode,
deterministic canaries, and a c4 smaller-context session-cache shape.

This is still session caching, not true active-context overflow. Every tested
session individually fits in GPU KV. CPU KV offload stores/reloads idle or
repeated prefixes through host RAM.

## Reusable Script

Added:

`scripts/session_cache_canary.py`

The script uses the OpenAI-compatible `/v1/completions` endpoint with
streaming enabled and records:

- prompt tokens
- completion tokens
- elapsed time
- time to first streamed text
- output tok/s after first text
- output text hash
- optional strict-word expected/observed first-word checks
- optional comparisons against a saved baseline JSON

Example:

```bash
experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py \
  --prompt-lines 700 \
  --max-tokens 128 \
  --passes 2 \
  --concurrency 2 \
  --labels A,B \
  --baseline-json /mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-canary-baseline-c1-20260525T013338Z.json \
  --output-json /mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-canary-c2-offload-20260525T013942Z.json
```

## Stable C1 Baseline

Server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-canary-baseline-c1-20260525T013338Z.json`

Shape:

- labels: A, B
- prompt lines per label: `700`
- prompt tokens per label: `16134`
- output tokens per label: `128`
- concurrency: `1`

Baseline results:

| Label | Prompt tokens | Output tokens | Elapsed | TTFT | Output tok/s after TTFT |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | `16134` | `128` | `12.625 s` | `10.907 s` | `74.54` |
| B | `16134` | `128` | `12.563 s` | `10.840 s` | `74.27` |

These are not meant to replace the warmed short-prompt decode benchmark. They
are long-prompt canary baselines for later CPU KV reload checks.

## C2 Longer Reload Decode

Temporary server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --max-num-seqs 2 \
  --no-scheduler-reserve-full-isl
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c2-kvoffload16-canary-20260525T013733Z.log`

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-canary-c2-offload-20260525T013942Z.json`

Startup facts:

- `max_model_len=32768`
- `max_num_seqs=2`
- GPU KV cache size: `34304` tokens after the B70 display was disabled
- CPU KV offload budget: `4.0 GiB` per worker from `--kv-offloading-size 16`

The prior c2 smoke, before this display/memory change, reported only `26112`
GPU KV tokens. This is an important deployment note: display ownership and
graph/cache shape can materially change the remaining KV budget.

Shape:

- labels: A, B
- prompt tokens per label: `16134`
- output tokens per label: `128`
- passes: `2`
- concurrency: `2`

First pass:

| Label | Elapsed | TTFT | Output tok/s after TTFT |
| --- | ---: | ---: | ---: |
| A | `25.961 s` | `23.893 s` | `61.88` |
| B | `25.512 s` | `11.608 s` | `9.21` |

Second pass:

| Label | Elapsed | TTFT | Output tok/s after TTFT |
| --- | ---: | ---: | ---: |
| A | `2.785 s` | `0.656 s` | `60.10` |
| B | `2.785 s` | `0.655 s` | `60.11` |

Observed transfer metrics:

| Direction | Bytes | Time | Effective rate |
| --- | ---: | ---: | ---: |
| GPU -> CPU | `3315597312` | `0.275006836 s` | about `12.1 GB/s` |
| GPU -> CPU | `1105199104` | `0.09217936 s` | about `12.0 GB/s` |
| CPU -> GPU | `8191475712` | `0.588027752 s` | about `13.9 GB/s` |
| CPU -> GPU | `16382951424` | `1.176186076 s` | about `13.9 GB/s` |

The 128-token text hashes did not match the c1 baseline or each other across
passes. The generated answers remained semantically close, but exact text hash
equality is not proven for longer concurrent decode.

One-token c2 check:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-canary-c2-offload-one-token-20260525T014040Z.json`

Result:

- A matched across passes.
- B matched across passes.

Interpretation: one-token checks are a more useful low-level canary than long
free-form completions under concurrent XPU/MoE scheduling, but the quality gate
still needs a better constrained deterministic harness.

## Strict-Word Follow-Up

The canary script now has a constrained prompt mode:

```bash
experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py \
  --prompt-mode strict-word \
  --prompt-lines 700 \
  --max-tokens 2 \
  --stop-newline \
  --passes 2 \
  --concurrency 2 \
  --labels A,B \
  --baseline-json /mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-c1-gpu-baseline-20260525T020926Z.json \
  --output-json /mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-c2-kvoffload16-20260525T022259Z.json
```

Prompt-version caveat: these first strict-word files were produced before the
later `strict-word-answer-space-v2` prompt tweak used by the c2 capacity ladder.
Use the saved JSON files as the record for these exact runs. Use
`notes-20260525-c2-session-cache-ladder.md` for the newer ladder shape.

This mode fills a long context, then asks the model to copy one target word. The
checked target words are:

| Label | Expected word |
| --- | --- |
| A | `red` |
| B | `blue` |
| C | `green` |
| D | `yellow` |

GPU-only baseline:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-c1-gpu-baseline-20260525T020926Z.json`

Shape:

- labels: A, B, C, D
- prompt lines per label: `700`
- prompt tokens per label: `21073`
- max output tokens per label: `2`
- passes: `2`
- concurrency: `1`

Result: all labels produced the expected word, exact output hashes were stable
across passes, and the same hashes became the comparison baseline.

c1 with CPU KV offload enabled:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-c1-kvoffload16-20260525T021800Z.json`

Server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --no-scheduler-reserve-full-isl
```

Startup facts:

- GPU KV cache size: `25344` tokens
- CPU KV offload budget: `4.0 GiB` per worker
- first launch hit the same `ocloc` / IGC error 245 fallback path and spent
  about `231.71 s` in compile before serving

Result: A/B/C/D all matched the GPU-only baseline by expected first word and by
exact output hash across both passes. This isolates the offload connector itself
as not changing the constrained result when each request fits in GPU KV.

c2 with CPU KV offload:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-c2-kvoffload16-20260525T022259Z.json`

Server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --max-num-seqs 2 \
  --no-scheduler-reserve-full-isl
```

Startup facts:

- GPU KV cache size: `34304` tokens
- CPU KV offload budget: `4.0 GiB` per worker
- compile loaded from cache in about `5.06 s`

Shape:

- labels: A, B
- prompt tokens per label: `21073`
- combined prompt pressure: about `42146` tokens, above the `34304` GPU KV
  budget
- max output tokens per label: `2`
- passes: `2`
- concurrency: `2`

Result: A/B both matched the GPU-only baseline by expected first word and exact
output hash across both passes. Second-pass reload was fast:

| Label | Pass | Elapsed | TTFT | Text |
| --- | ---: | ---: | ---: | --- |
| B | 2 | `0.506 s` | `0.498 s` | `blue` |
| A | 2 | `0.885 s` | `0.882 s` | `red` |

Observed c2 transfer metric after the strict run:

| Direction | Bytes | Time | Effective rate |
| --- | ---: | ---: | ---: |
| CPU -> GPU | `10661920768` | `0.698500764 s` | about `15.3 GB/s` |

c4 with CPU KV offload:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/strict-word-c4-kvoffload32-20260525T030545Z.json`

Server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 32 \
  --max-num-seqs 4 \
  --no-scheduler-reserve-full-isl
```

Startup facts:

- GPU KV cache size: `34304` tokens
- CPU KV offload budget: `8.0 GiB` per worker
- compile loaded from cache in about `6.02 s`

Shape:

- labels: A, B, C, D
- prompt tokens per label: `12073`
- combined prompt pressure: about `48292` tokens, above the `34304` GPU KV
  budget
- max output tokens per label: `2`
- passes: `2`
- concurrency: `4`

Result: A/B/C/D all produced the expected first word on both passes and all
first words matched the GPU-only baseline. Exact full-text hashes matched for
A/B/C. D matched on the first pass; on the second pass it produced the correct
first word plus an extra continuation token:

```text
yellow + one extra non-ASCII continuation token
```

The raw output used a non-ASCII comma before the extra continuation. This is not
a wrong target word, but it is still not an exact-output match. Treat c4 as
promising for session-cache reload, not production quality-equivalent yet.

Second-pass reload was fast:

| Label | Pass | Elapsed | TTFT | Text check |
| --- | ---: | ---: | ---: | --- |
| A | 2 | `0.434 s` | `0.425 s` | expected word, exact hash |
| B | 2 | `0.433 s` | `0.425 s` | expected word, exact hash |
| D | 2 | `0.748 s` | `0.731 s` | expected word, extra continuation |
| C | 2 | `0.748 s` | `0.732 s` | expected word, exact hash |

Observed c4 transfer metrics during the strict run:

| Direction | Bytes | Time | Effective rate |
| --- | ---: | ---: | ---: |
| CPU -> GPU | `12222201856` | `0.779602200 s` | about `15.7 GB/s` |
| CPU -> GPU | `24444403712` | `1.555700744 s` | about `15.7 GB/s` |

A one-token strict run is not a good replacement canary because the first token
can be whitespace-only. In that test, A and C on pass 1 produced an empty
observed word before matching on pass 2.

## C4 Smaller-Context Ladder

Temporary server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 32 \
  --max-num-seqs 4 \
  --no-scheduler-reserve-full-isl
```

Logs:

- first compile attempt:
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c4-kvoffload32-canary-20260525T014141Z.log`
- cached rerun used for measurements:
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c4-kvoffload32-canary-rerun-20260525T014833Z.log`

Startup facts from the cached rerun:

- `max_model_len=32768`
- `max_num_seqs=4`
- GPU KV cache size: `34304` tokens
- CPU KV offload budget: `8.0 GiB` per worker from `--kv-offloading-size 32`

The first c4 compile hit an Intel compiler failure while compiling a Triton
reduction candidate:

```text
ocloc failed with error code 245
IGC: Internal Compiler Error: Floating point exception
```

vLLM/Torch continued through fallback compilation, but the first c4 launch
spent about `231 s` in `torch.compile`. The cached rerun loaded the AOT compile
and reduced compile time to about `12 s`.

Longer decode shape:

- labels: A, B, C, D
- prompt lines per label: `400`
- prompt tokens per label: `9234`
- output tokens per label: `64`
- passes: `2`
- concurrency: `4`

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-canary-c4-offload-20260525T015118Z.json`

First pass:

| Label | Elapsed | TTFT | Output tok/s after TTFT |
| --- | ---: | ---: | ---: |
| A | `28.285 s` | `10.651 s` | `3.63` |
| B | `35.683 s` | `31.320 s` | `14.67` |
| C | `31.506 s` | `17.038 s` | `4.42` |
| D | `31.784 s` | `23.657 s` | `7.87` |

Second pass:

| Label | Elapsed | TTFT | Output tok/s after TTFT |
| --- | ---: | ---: | ---: |
| A | `1.615 s` | `0.374 s` | `51.60` |
| B | `1.614 s` | `0.374 s` | `51.60` |
| C | `2.579 s` | `1.771 s` | `79.17` |
| D | `1.613 s` | `0.373 s` | `51.60` |

Observed transfer metrics:

| Direction | Bytes | Time | Effective rate |
| --- | ---: | ---: | ---: |
| GPU -> CPU | `2795503616` | `0.234141388 s` | about `11.9 GB/s` |
| GPU -> CPU | `3640655872` | `0.325711620 s` | about `11.2 GB/s` |
| GPU -> CPU | `2925527040` | `0.270284508 s` | about `10.8 GB/s` |
| CPU -> GPU | `2600468480` | `0.160389736 s` | about `16.2 GB/s` |
| CPU -> GPU | `9361686528` | `0.593711768 s` | about `15.8 GB/s` |
| CPU -> GPU | `18723373056` | `1.182082200 s` | about `15.8 GB/s` |

vLLM reported external prefix cache hit rate rising to `49.9%` after the
second longer pass and `74.9%` after the one-token check.

One-token c4 check:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-canary-c4-offload-one-token-20260525T015202Z.json`

Result:

- A matched across passes.
- B matched across passes.
- D matched across passes.
- C did not match across passes. The first token changed from `Output` to
  `Use`.

Interpretation: c4 session caching works mechanically and is fast on cache
reload, but deterministic exact-token quality is not fully proven under c4
concurrent scheduling. Treat c4 as an experimental session-cache lane, not a
production-quality-equivalent mode.

## Restore

The stable endpoint was restored after the experiments:

```bash
nohup setsid bash -lc 'VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve' \
  > /mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c1-restored-20260525T030740Z.log \
  2>&1 < /dev/null &
```

Smoke check after the latest restore:

```json
{
  "served_on": "0.0.0.0:8000",
  "completion_tokens": 8,
  "max_model_len": 32768
}
```

## Next Steps

1. Keep c1 `32768` as the stable production endpoint.
2. Treat c2 CPU KV session caching as the strongest experimental lane so far:
   strict-word first words and exact hashes matched GPU-only baseline.
3. Keep c4 experimental until an exact-output or token-level/logprob canary
   removes the remaining extra-continuation ambiguity.
4. Add session-cache RAM sizing estimates from transfer bytes per token.
5. Keep true active-context overflow separate from this session-cache lane.
