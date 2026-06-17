# Qwen3.6 CUDAGraph Trace Summary

- trace rows: `1360`
- malformed trace rows: `0`
- canary: `/home/steve/llm-optimizations/data/qwen36-ablation-fastlane-gdnmask-clone-output5-6-deep-trace-color-repeat512-20260614h22.json`
- pass_all: `False`
- first mismatch: `h22-color-000137` index `137`

## Counts

- events: `{'direct_start': 60, 'direct_finish': 60, 'replay_start': 620, 'replay_finish': 620}`
- stages: `{'prefill': 120, 'first_decode': 120, 'decode': 1120}`
- traced requests: `6`

## Top Labels

- `136` `wrapper:0 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_0 piecewise:0/41`
- `136` `wrapper:1 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_2 piecewise:1/41`
- `136` `wrapper:2 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_4 piecewise:2/41`
- `136` `wrapper:3 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_6 piecewise:3/41`
- `136` `wrapper:4 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_8 piecewise:4/41`
- `136` `wrapper:5 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_10 piecewise:5/41`
- `136` `wrapper:6 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_12 piecewise:6/41`
- `136` `wrapper:7 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_14 piecewise:7/41`
- `136` `wrapper:8 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_16 piecewise:8/41`
- `136` `wrapper:9 mode:PIECEWISE type:vllm.compilation.piecewise_backend.PiecewiseBackend submod:submod_18 piecewise:9/41`

## Nearby Requests

### `cmpl-h22-color-000135-0-8ba6be12`

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

### `cmpl-h22-color-000136-0-8ebc7884`

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

### `cmpl-h22-color-000137-0-a866c7da`

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

