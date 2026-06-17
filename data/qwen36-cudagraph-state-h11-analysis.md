# Qwen3.6 CUDAGraph Trace Summary

- trace rows: `3888`
- malformed trace rows: `0`
- canary: `data/qwen36-ablation-fastlane-state-trace-piecewise-1-9-color-color-repeat96-20260614h11.json`
- pass_all: `False`
- first mismatch: `h11-color-000022` index `22`

## Counts

- events: `{'direct_start': 360, 'direct_finish': 360, 'capture_start': 135, 'capture_finish': 135, 'replay_start': 1449, 'replay_finish': 1449}`
- stages: `{'unknown': 576, 'prefill': 414, 'first_decode': 414, 'decode': 2484}`
- traced requests: `23`

## Top Labels

- `432` `wrapper:1 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_2 piecewise:1/41`
- `432` `wrapper:2 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_4 piecewise:2/41`
- `432` `wrapper:3 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_6 piecewise:3/41`
- `432` `wrapper:4 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_8 piecewise:4/41`
- `432` `wrapper:5 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_10 piecewise:5/41`
- `432` `wrapper:6 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_12 piecewise:6/41`
- `432` `wrapper:7 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_14 piecewise:7/41`
- `432` `wrapper:8 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_16 piecewise:8/41`
- `432` `wrapper:9 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_18 piecewise:9/41`

## Nearby Requests

### `cmpl-h11-color-000019-0-934588f0`

- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None

### `cmpl-h11-color-000020-0-91f57acc`

- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None

### `cmpl-h11-color-000021-0-8cba2e98`

- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None

### `cmpl-h11-color-000022-0-805902cc`

- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None
- direct_start prefill entry=None addr=None
- direct_finish prefill entry=None addr=None

