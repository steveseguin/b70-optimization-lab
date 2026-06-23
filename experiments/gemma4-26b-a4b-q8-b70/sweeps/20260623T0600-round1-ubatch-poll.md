# 20260623T0600 Round 1 Ubatch / Poll Sweep

## Goal

Try low-risk llama.cpp scheduler settings while preserving the validated Q8
quality lane:

- UD-Q8_K_XL weights;
- f16 KV;
- `REASONING=off`;
- `GGML_SYCL_DISABLE_OPT=1`;
- chat canary 32 repeats (`128` rows) before ranking speed.

## Results

| Label | GPU | Batch / Ubatch | Poll | Canary | p512/o512 tok/s after TTFT | Wall tok/s | Decision |
| --- | ---: | --- | ---: | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-control-ub64-poll50-20260623T0600` | 0 | `512 / 64` | 50 | 128/128 | `26.0512` | `24.2199` | control reproduced, slightly below first baseline |
| `gemma4-q8-gpu1-ub128-poll50-20260623T0600` | 1 | `512 / 128` | 50 | 128/128 | `26.0837` | `24.3377` | best of this round, but below first baseline `26.0997` |
| `gemma4-q8-gpu2-ub256-poll50-20260623T0600` | 2 | `512 / 256` | 50 | 128/128 | `26.0741` | `24.2687` | no win |
| `gemma4-q8-gpu3-ub64-poll25-20260623T0600` | 3 | `512 / 64` | 25 | 128/128 | `26.0367` | `24.4147` | no after-TTFT win |

## Decision

No promoted speed result and no LocalMaxxing update. Ubatch and poll changes in
this range are mostly noise for steady decode on this setup. Move to runtime
flag and larger batch tests.

## Artifacts

- `data/gemma4-q8-gpu0-control-ub64-poll50-20260623T0600/summary.json`
- `data/gemma4-q8-gpu1-ub128-poll50-20260623T0600/summary.json`
- `data/gemma4-q8-gpu2-ub256-poll50-20260623T0600/summary.json`
- `data/gemma4-q8-gpu3-ub64-poll25-20260623T0600/summary.json`
