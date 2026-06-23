# Gemma 4 26B A4B Q8 B70 Experiments

Active experiment lane for one Gemma 4 26B A4B Q8-quality replica per Intel B70.

The promoted/reference packet is
[`../../results/gemma4-26b-a4b-q8-b70/`](../../results/gemma4-26b-a4b-q8-b70/README.md).
Keep raw attempts, failed knobs, and patch notes here until a result is worth
promoting.

Before launching new sweeps, read the current
[research plan](../../results/gemma4-26b-a4b-q8-b70/research-plan.md) and
[model/runtime options](../../results/gemma4-26b-a4b-q8-b70/model-options.md).

## Layout

Suggested subfolders:

```text
experiments/gemma4-26b-a4b-q8-b70/
  logs/          # short copied logs or checksums of external logs
  patches/       # source/config patches tested in this lane
  sweeps/        # small markdown/json summaries of parameter sweeps
```

Large logs should live under `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/`
with paths and summaries recorded here or in `../../data/`.

## First Sweep Matrix

After the first replica serves:

| GPU | Purpose | First knobs |
| --- | --- | --- |
| 0 | Control | `-fa 1`, f16 KV, default graph/DNN |
| 1 | ubatch | `-ub 64/128/256/512` |
| 2 | graph/DNN | `GGML_SYCL_DISABLE_GRAPH=0/1`, `GGML_SYCL_DISABLE_DNN=0/1` |
| 3 | alternative runtime | vLLM int8-per-channel or candidate patch |

Every sweep entry should state quality status, not only speed.
