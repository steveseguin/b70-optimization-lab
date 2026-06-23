# 20260623T0615 Round 2 Batch / Runtime Flag Sweep

## Goal

Continue quality-preserving no-spec llama.cpp sweeps after Round 1 showed
ubatch/poll was mostly flat. All lanes used:

- UD-Q8_K_XL weights;
- f16 KV;
- `REASONING=off`;
- `GGML_SYCL_DISABLE_OPT=1`;
- chat canary 32 repeats (`128` rows) before ranking speed.

## Results

| Label | GPU | Change | Canary | p512/o512 tok/s after TTFT | Wall tok/s | Decision |
| --- | ---: | --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-b1024-ub128-poll50-20260623T0615` | 0 | `BATCH_SIZE=1024`, `UBATCH_SIZE=128` | 128/128 | `26.0657` | `24.1962` | no win |
| `gemma4-q8-gpu1-b2048-ub256-poll50-20260623T0615` | 1 | `BATCH_SIZE=2048`, `UBATCH_SIZE=256` | 128/128 | `26.0125` | `24.2418` | slower |
| `gemma4-q8-gpu2-disable-dnn-20260623T0615` | 2 | `GGML_SYCL_DISABLE_DNN=1` | 128/128 | `26.0057` | `24.2380` | slower |
| `gemma4-q8-gpu3-disable-graph-20260623T0615` | 3 | `GGML_SYCL_DISABLE_GRAPH=1` | 128/128 | `26.0665` | `24.5212` | wall improved slightly; after-TTFT below baseline |

## Decision

No promoted speed result and no LocalMaxxing update. Larger batch/ubatch and
`GGML_SYCL_DISABLE_DNN=1` are not useful for steady single-session decode.
`GGML_SYCL_DISABLE_GRAPH=1` may help wall/TTFT behavior slightly, but it did not
beat the stable after-TTFT metric and needs a targeted repeat only if wall
latency becomes the optimization target.

## Artifacts

- `data/gemma4-q8-gpu0-b1024-ub128-poll50-20260623T0615/summary.json`
- `data/gemma4-q8-gpu1-b2048-ub256-poll50-20260623T0615/summary.json`
- `data/gemma4-q8-gpu2-disable-dnn-20260623T0615/summary.json`
- `data/gemma4-q8-gpu3-disable-graph-20260623T0615/summary.json`
