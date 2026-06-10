# Qwen3.6 Sync Timing Device-Lost Screen

Date: 2026-06-10

## Context

The accepted Qwen3.6 INT8 runtime was restored to the TP4, 32K, no-prefix
profile after the safe in-place all-reduce follow-up. I tried to get per-op
decode timing without changing weights, quantization, context length, or the
serving surface.

Accepted runtime baseline:

- Model: `Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Served name: `qwen36-35b-a3b-fp8`
- TP: `4`
- Context: `32768`
- Prefix caching: disabled
- XPU graph: PIECEWISE
- Custom all-reduce: clone-safe custom-op path

## Diagnostic Attempt

Runtime:

- Session: `qwen36-tp4-timing`
- Log: `/tmp/qwen36-quark-int8-tp4-timing.log`
- Env delta from accepted no-prefix runtime:
  - `VLLM_XPU_DECODE_TIMING=1`
  - `VLLM_XPU_DECODE_TIMING_SYNC=1`
  - `VLLM_XPU_DECODE_TIMING_RANK=0`
  - `VLLM_XPU_DECODE_TIMING_SKIP_FIRST=20`
  - `VLLM_XPU_DECODE_TIMING_PRINT_EVERY=200`

The backend reached `/health`, but the first p512/n128 benchmark request
failed with HTTP 500 and killed the engine.

Only one timing sample was emitted before the crash:

```text
[vllm-xpu-timing] rank=0 label=all_reduce:(48, 2048):torch.bfloat16 count=200 last_ms=0.106150
```

The root failure was a Level Zero device-lost error during normal input staging:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

The stack first failed in `block_table.copy_to_gpu(...)` and then again in
`num_computed_tokens.copy_(...)` while the dead engine was unwinding.

## Restore Lesson

An attempted restore through `/opt/intel/oneapi/setvars.sh` was not reliable on
this host:

- `setvars.sh` tripped `set -u` on `OCL_ICD_FILENAMES`.
- After working around that, `/opt/intel/oneapi/compiler/latest` resolved to a
  `2026.0` stack and XCCL/Level Zero segfaulted in collective init.

The stable restore path is to use the vLLM XPU venv libraries first and avoid
the system oneAPI `latest` environment:

```bash
source /home/steve/.venvs/vllm-xpu/env/vars.sh
export LD_LIBRARY_PATH=/home/steve/.venvs/vllm-xpu/lib:/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:${LD_LIBRARY_PATH:-}
export CCL_ROOT=/home/steve/.venvs/vllm-xpu
```

That restored the accepted backend:

- Session: `qwen36-tp4-noprefix-32k`
- Backend smoke: direct completion OK
- Frontdoor smoke: chat completion with thinking disabled returned `OK`

## Restore Speed Check

After restore, direct-backend p512/n512 streaming with four measured repeats
landed back in the current-control band:

| metric | restored accepted runtime |
| --- | ---: |
| corrected after-first output tok/s | `98.5468` |
| end-to-end output tok/s | `97.3130` |
| total tok/s | `194.6260` |
| mean client TTFT | `76.03 ms` |
| mean vLLM TTFT | `74.69 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-restore-after-timing-single-20260610.json`

## Decision

Reject synchronized per-op timing for this runtime. It is too invasive for the
current Level Zero/XCCL stack and caused a device-lost engine failure before a
valid benchmark could complete.

Future profiling should prefer lower-risk routes first:

- no-sync timing logs, if the helper can be used without forcing device syncs;
- generated graph inspection;
- coarse request-level metrics;
- short reliability screens after any instrumentation change.
