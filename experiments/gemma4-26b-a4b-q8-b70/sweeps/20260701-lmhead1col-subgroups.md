# 2026-07-01 LM-head Q8 one-column subgroup sweep

## Goal

Test whether the final Q8_0 LM-head one-column reordered `mmvq` path benefits
from fewer subgroups per workgroup on Gemma 4 26B A4B Q8. This is a
full-logits-preserving launch-geometry experiment: it must not change target
model, target quantization, logits semantics, cache policy, or validation
rules.

## Patch

- Source fragment:
  `patches/gemma4-26b-a4b-q8-b70/20260701-lmhead1col-subgroups-source-fragment.patch`
- Harness metadata:
  `patches/gemma4-26b-a4b-q8-b70/20260701-lmhead1col-subgroups-harness.patch`

The new runtime knob is `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS`. Valid values:
`1`, `2`, `4`, `8`, `16`, `32`. Unset behavior stays at `WARP_SIZE`. The knob
is ignored for `nrows < 65536` so smaller Q8 one-column matmuls do not move.

## Build

The first direct build failed late at final SYCL/OpenMP linking with unresolved
`sycl::_V1::*`, `__kmpc_*`, and `omp_*` symbols. Cause: the shell used for the
manual build had not sourced the Intel oneAPI environment, while the build
directory is configured against oneAPI 2026.0.

Correct build command:

```bash
set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 16
```

Result: build succeeded. Updated binary:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server
version: 9769 (c926ad098)
built with IntelLLVM 2026.0.0 for Linux x86_64
```

The bundled UI emitted an npm engine warning because local Node/npm is older
than the Storybook dependency requires; the build continued using existing UI
assets. That warning was not the original linker problem.

## Validation Rules

Only strict fresh-response results are eligible for promotion:

- fixed realistic prompt suite;
- each prompt once as a cold first response;
- `cached_tokens=0`;
- no prompt/KV cache reuse, context checkpoints, response reuse, n-gram/history
  acceleration, or warmed repeated prompts;
- target model and quantization unchanged:
  `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- MTP accepted tokens verified by target model;
- primary metric: median generated tok/s for tokens 1-100 after TTFT.

## Screen Plan

Run paired strict-128 screens across the four B70 GPUs:

- GPU0: control, knob unset;
- GPU1: `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS=16`;
- GPU2: `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS=8`;
- GPU3: `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS=4`.

If a candidate clearly beats the same-window control and passes the strict gate,
run a full512 confirmation before treating it as a record candidate. Do not
submit to LocalMaxxing unless the strict full512 headline beats the current
valid record of `123.67689864739785 tok/s`.

## Results

Completed with two strict fresh-response screens. Every run passed canaries and
the realistic final gate (`cached_tokens=0` for every prompt row), so the patch
appears quality-safe. It is not a throughput win.

Primary metric is median generated tok/s for tokens 1-100 after TTFT.

| Label | GPU | Subgroups | Valid | Canary | Median | p10 | Mean | Full after-TTFT median | Wall full median | TTFT median ms |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| `gemma4-q8-gpu0-lmheadsg-control-strict128-20260701TscreenA` | 0 | unset | yes | pass | 118.958966 | 103.915650 | 116.931789 | 115.085451 | 98.254469 | 178.246147 |
| `gemma4-q8-gpu1-lmheadsg16-strict128-20260701TscreenA` | 1 | 16 | yes | pass | 118.902771 | 107.953078 | 118.317408 | 117.109933 | 100.734740 | 177.820668 |
| `gemma4-q8-gpu2-lmheadsg8-strict128-20260701TscreenA` | 2 | 8 | yes | pass | 115.848447 | 108.377114 | 118.361809 | 113.861336 | 97.876856 | 179.273871 |
| `gemma4-q8-gpu3-lmheadsg4-strict128-20260701TscreenA` | 3 | 4 | yes | pass | 115.798264 | 107.870952 | 116.769748 | 114.919597 | 97.085283 | 178.096144 |
| `gemma4-q8-gpu0-lmheadsg16-strict128-20260701TscreenB` | 0 | 16 | yes | pass | 115.520102 | 105.729148 | 116.860508 | 117.625895 | 99.011550 | 179.080667 |
| `gemma4-q8-gpu1-lmheadsg-control-strict128-20260701TscreenB` | 1 | unset | yes | pass | 113.820876 | 101.214472 | 115.939452 | 114.952133 | 98.339597 | 179.095516 |
| `gemma4-q8-gpu2-lmheadsg2-strict128-20260701TscreenB` | 2 | 2 | yes | pass | 120.195817 | 105.609352 | 119.262127 | 118.629042 | 101.602984 | 178.412212 |
| `gemma4-q8-gpu3-lmheadsg1-strict128-20260701TscreenB` | 3 | 1 | yes | pass | 115.554522 | 103.968624 | 117.273755 | 117.989568 | 100.211439 | 178.923231 |

Interpretation:

- `16` is a direct near-tie in screen A (`118.902771` vs GPU0 control
  `118.958966`) and loses badly in the GPU0 crossover (`115.520102`).
- `8`, `4`, and `1` are clear losses.
- `2` produced the best candidate screen (`120.195817`) but still sits below
  the current strict record (`123.67689864739785`) and does not have a same-GPU
  control advantage. It is not worth a full512 promotion run.

Decision: **reject as a performance patch**. Keep the default-off source
fragment and harness metadata patch as durable research artifacts, but do not
promote the knob into a record recipe and do not submit to LocalMaxxing.

## No-Spec Calibration Follow-Up

The only near-interesting MTP screen was `SUBGROUPS=2` on GPU2. Because this
knob affects the target-side Q8 LM-head path and is still exercised when MTP is
disabled, it was checked with the lower-variance no-spec calibration lane.

Artifact:

- `data/gemma4-q8-nospec-lmheadsg2-ab-20260701T140828Z.json`
- `data/gemma4-q8-nospec-lmheadsg2-ab-20260701T140828Z.md`

Runs:

- controls:
  - `data/gemma4-q8-gpu0-nospec-lmheadsg-control-full512-20260701T140828Z-nospec-retest/summary.json`
  - `data/gemma4-q8-gpu2-nospec-lmheadsg-control-full512-20260701T140828Z-nospec-retest/summary.json`
- candidate:
  - `data/gemma4-q8-gpu3-nospec-lmheadsg2-full512-20260701T140828Z-nospec-retest/summary.json`

All runs passed the fixed realistic final gate with `cached_tokens=0`. The
paired no-spec result was:

- control run medians: `77.047`, `76.605` tok/s;
- `SUBGROUPS=2` candidate median: `76.548` tok/s;
- median paired ratio 95% CI: `-0.649% / -0.338% / -0.073%`;
- analyzer decision: `no_win`.

This closes `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS=2` as well. Do not retest
the LM-head one-column subgroup family unless a future source change materially
alters the Q8 LM-head kernel shape.

Run directories:

- `data/gemma4-q8-gpu0-lmheadsg-control-strict128-20260701TscreenA/`
- `data/gemma4-q8-gpu1-lmheadsg16-strict128-20260701TscreenA/`
- `data/gemma4-q8-gpu2-lmheadsg8-strict128-20260701TscreenA/`
- `data/gemma4-q8-gpu3-lmheadsg4-strict128-20260701TscreenA/`
- `data/gemma4-q8-gpu0-lmheadsg16-strict128-20260701TscreenB/`
- `data/gemma4-q8-gpu1-lmheadsg-control-strict128-20260701TscreenB/`
- `data/gemma4-q8-gpu2-lmheadsg2-strict128-20260701TscreenB/`
- `data/gemma4-q8-gpu3-lmheadsg1-strict128-20260701TscreenB/`
