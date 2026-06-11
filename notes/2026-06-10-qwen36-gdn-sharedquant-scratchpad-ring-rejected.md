# Qwen3.6 GDN Shared-Quant Scratchpad Ring Rejected

Date: 2026-06-10

## Context

Current accepted runtime:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Runtime: vLLM XPU, TP4, 32K, Quark W8A8 INT8, BF16 activations
- Prefix cache: disabled
- XPU graph: PIECEWISE
- Accepted GDN setting: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- Accepted `_xpu_C` hash:
  `d2c6cc8d1cc92c3671a3a9357bed6c5783bdbcf505ee663d16f2e42f1e46ce8c`

The unguarded GDN qkvz/ba quant reuse path was previously rejected because it
was a small speed win but failed repeat-stability quality checks. The suspicious
part of the native path was `int8_gemm_w8a8`: it uses a thread-local oneDNN
scratchpad tensor cache, while the torch binding declares the inputs as
non-mutating.

This candidate tested whether rotating oneDNN INT8 GEMM scratchpads prevents
full-endpoint instability and lets us use the faster shared quant tensors.

## Candidate

Kernel candidate:

- Source artifact:
  `patches/vllm-xpu-kernels-qwen36-int8-gemm-scratchpad-ring-rejected-20260610.patch`
- Built `_xpu_C` hash:
  `3e0524e9ee55784667b3c45e962573a8ca78b5912b27671503b8ffb732e52118`
- Runtime knob:
  `VLLM_XPU_INT8_GEMM_SCRATCHPAD_RING_SIZE=4`
- GDN knob:
  `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=1`

The ring defaults to size `1`, preserving existing behavior unless the env is
set. The endpoint test used size `4`.

## Native Probe

Artifacts:

- `scripts/probe-qwen36-gdn-int8-shared-quant.py`
- `data/qwen36-gdn-int8-shared-quant-probe-20260610.json`
- `data/qwen36-gdn-int8-shared-quant-scratchring-probe-20260610.json`

The probe isolates:

- per-token XPU INT8 quantization of a Qwen3.6 GDN-like input
- `qkvz` W8A8 INT8 GEMM, shape `K=2048`, `N=3072`
- `ba` W8A8 INT8 GEMM, shape `K=2048`, `N=16`
- row counts `m=1,2,8,18,64`
- eager and `torch.compile` variants

Result:

- shared and cloned quant tensors matched exactly in the isolated native probe;
- no `x_q` mutation observed;
- no `x_s` mutation observed;
- compiled and eager outputs matched exactly;
- isolated eager shared quant was much faster than clone, as expected.

This means the obvious eager/native input-mutation theory was not reproduced in
isolation. Any instability from unguarded shared quant is likely in the full
vLLM graph/runtime path rather than a simple one-call mutation.

## Endpoint Test

Runtime tmux:

- `qwen36-tp4-gdn-reusequant-scratchring4-32k`

Candidate launch used the current accepted 32K TP4 env plus:

```bash
VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=1
VLLM_XPU_INT8_GEMM_SCRATCHPAD_RING_SIZE=4
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/build/xpu-c-only-scratch-ring-20260610:...
```

Startup telemetry:

- checkpoint size: `34.15 GiB`
- model loading memory: `8.58 GiB`
- available KV cache memory: `20.67 GiB`
- GPU KV cache size: `2,052,915 tokens`
- estimated max 32K concurrency: `62.65x`
- torch.compile: `55.27 s`
- graph capture: `12 s`

Speed artifact:

- `data/qwen36-quark-int8-tp4-noprefix-gdn-sharedquant-scratchring4-single-r8-20260610.json`

Result:

| metric | scratchpad ring shared-quant | accepted control family |
| --- | ---: | ---: |
| corrected after-first output tok/s | `99.0553` | `~99.3-99.8` |
| e2e output tok/s | `96.5292` | `~98.0-98.6` |
| mean client TTFT | `104.53 ms` | `~74-79 ms` |

Representative accepted controls:

- `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-single-r8-20260610.json`
  - corrected after-first: `99.3181 tok/s`
  - e2e: `97.9820 tok/s`
  - TTFT: `79.45 ms`
- `data/qwen36-quark-int8-tp4-noprefix-restore-after-xpushared-reject-r4-20260610.json`
  - corrected after-first: `99.7816 tok/s`
  - e2e: `98.5507 tok/s`
  - TTFT: `74.11 ms`

## Decision

Rejected at the endpoint speed gate.

The scratchpad ring did not recover a useful full-endpoint win for unguarded GDN
shared quantization. It was slower than the accepted clone-mode runtime and had
worse TTFT. Because speed failed first, the full quality suite was not run; a
quality pass would not make this candidate worth keeping.

The useful lesson is negative but concrete: rotating oneDNN INT8 GEMM
scratchpads does not explain or fix the full-runtime problem with sharing the
same GDN `x_q` and `x_s` tensors across the qkvz and ba GEMMs.

## Restore

The rejected `_xpu_C` was removed from the active package and the pre-test
binary was restored:

```text
d2c6cc8d1cc92c3671a3a9357bed6c5783bdbcf505ee663d16f2e42f1e46ce8c
```

The accepted endpoint was relaunched as:

- tmux: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend: `127.0.0.1:18080`
- health: OK

## Next Steps

Do not spend more time on oneDNN scratchpad rotation for this issue unless a
new failure mode appears. Better next investigations:

1. Trace full-graph aliasing/lifetime around the two GDN INT8 GEMM calls.
2. Check whether vLLM/XPU graph capture assumes distinct storage for repeated
   custom-op arguments even when the op schema says inputs are read-only.
3. Look for a lower-overhead safety barrier than full clone, but only if it
   passes endpoint speed before quality.
