# Qwen27 INT4 top-1 LM-head prototype sycl8 no-win

Date: 2026-07-07

## Context

The current valid Qwen27 INT4 headline remains the webhie runtime INT8
target-LM-head / runtime INT4 draft-LM-head ReplaySSM recipe at:

- median `68.23626314761921 tok/s` for generated tokens 1-100 after TTFT;
- strict fresh prompt suite, each prompt once, `cached_tokens=0`;
- repeat64 quality passed;
- LocalMaxxing id `cmr9atqb800msqr01u760xh0t`.

This diagnostic tested the producer-side LM-head shortcut idea: avoid
materializing full `[rows, vocab]` INT4 draft logits when only the greedy top-1
draft token is needed.

## Patch

Patch artifact:

`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-int4-top1-prototype-sycl8-no-win-20260707.patch`

It adds a default-unwired native XPU op:

`torch.ops._xpu_C.int4_gemm_w4a16_top1(A, B, B_scale, B_zp, group_size, g_idx, tile_size=2048) -> (ids, values)`

Prototype design:

- input shape matches the Qwen27 draft INT4 LM-head diagnostic:
  `hidden [rows, 5120] x packed W4 [5120, 248320]`;
- stage 1 scans a vocabulary tile and writes per-tile `(top_id, top_value)`;
- stage 2 reduces per-tile maxima to one top id/value per row;
- supports BF16/FP16 activations and BF16/FP16/FP32 scales;
- scalar zero point only, hardcoded to `8` inside the prototype after an
  earlier version incorrectly dereferenced the XPU scalar tensor on host.

The patch is intentionally not integrated into vLLM endpoint code. It applies
against the current local XPU-kernel research tree, where older ReplaySSM/GDN
patches are already present.

## First Build Attempt: oneAPI 2026 / sycl9 Runtime Hang

The local kernel tree is already a dirty research tree with ReplaySSM/GDN
changes in the same binding files. The prototype was built in a BMG-only build
directory:

```bash
cd /home/steve/src/vllm-xpu-kernels
VLLM_XPU_AOT_DEVICES=bmg-g31-a0 \
VLLM_XPU_XE2_AOT_DEVICES=bmg-g31-a0 \
cmake --build build/xpu-int4-topid-20260706 --target _xpu_C -j2
```

The build completed, but produced an extension requiring oneAPI 2026
`libsycl.so.9`. The normal vLLM runtime uses the sycl8-compatible package
binary, so copying the test extension into the package breaks ordinary imports
unless `/opt/intel/oneapi/compiler/2026.0/lib` is prepended to
`LD_LIBRARY_PATH`.

The microbench command was:

```bash
cd /home/steve/llm-optimizations
ZE_AFFINITY_MASK=0 \
LD_LIBRARY_PATH="/opt/intel/oneapi/compiler/2026.0/lib:/home/steve/src/vllm-xpu-kernels/build/xpu-int4-topid-20260706:/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen27-draft-int4-lmhead.py \
  --rows 1,2,3,4 --warmup 10 --iterations 30 \
  --output-json experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-int4-top1-prototype-microbench-20260707.json
```

The process hung with no row output, GPU idle, about `1 GiB` allocated, and the
only visible runtime diagnostic:

```text
onednn_verbose common,error,runtime,bad engine kind,src/xpu/sycl/capi/capi_engine.cpp:45
```

After several minutes it was killed and the original sycl8 package binary was
restored from:

`/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so.pre-int4top1diag-20260707T070411Z`

Post-restore import check:

```text
import ok /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so
has top1 False
```

No JSON result was produced.

## Follow-Up: sycl8 Build, Correct but Slower

The same prototype was then applied with correct local hunk placement and built
in the known-good oneAPI 2025.3 / sycl8 build tree:

```bash
cd /home/steve/src/vllm-xpu-kernels
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
cmake --build build/int8-top1-microbench-20260703-2025 --target _xpu_C -j2
```

That build succeeded, imported in the normal runtime, and exposed
`torch.ops._xpu_C.int4_gemm_w4a16_top1`. The test extension was copied into the
package only for the smoke/microbench and then the original sycl8 package
binary was restored. Post-restore import check again shows `has top1 False`.

Small-shape smoke (`hidden=128`, `vocab=4096`, rows `1..4`) passed top-id
correctness, but was already slower than dense logits plus argmax:

- row 1: dense+argmax `0.10195 ms`, top1 `0.13901 ms`;
- row 2: dense+argmax `0.08965 ms`, top1 `0.12383 ms`;
- row 3: dense+argmax `0.08920 ms`, top1 `0.12249 ms`;
- row 4: dense+argmax `0.08995 ms`, top1 `0.12287 ms`.

Full Qwen27 vocabulary diagnostics (`hidden=5120`, `vocab=248320`) also passed
top-id correctness, but scaled badly:

- row 1: dense+argmax `1.94522 ms`, top1 `2.30077 ms`;
- row 2: dense+argmax `1.36592 ms`, top1 `5.82082 ms`;
- row 3: dense+argmax `1.21295 ms`, top1 `6.51761 ms`;
- row 4: dense+argmax `1.21935 ms`, top1 `9.14523 ms`.

Diagnostic JSON:

- `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-int4-top1-prototype-smoke-small-20260707.json`;
- `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-int4-top1-prototype-fullvocab-row1-20260707.json`;
- `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-int4-top1-prototype-fullvocab-rows2-4-20260707.json`.

## Status

Closed as a no-win diagnostic.

Do not wire this op into the endpoint or spend a strict benchmark on it. The
prototype now has enough evidence:

1. sycl8 build/import is possible;
2. dense-argmax top-id correctness passes;
3. performance loses to dense logits plus argmax, especially at rows `2..4`,
   which are the relevant MTP verification/proposer row counts.

The broader route remains conceptually valid because full-logit materialization
is a real waste target, but a naive vocabulary-tile scan is not the right
implementation. A future attempt needs a different primitive, such as
candidate-only score extraction or an optimized top-k/max design that reuses
matrix-tile structure instead of serially recomputing every token score.
