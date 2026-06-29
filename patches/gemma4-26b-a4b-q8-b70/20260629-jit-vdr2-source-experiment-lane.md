# Gemma 4 26B Q8: JIT VDR2 Source-Experiment Lane

Date: 2026-06-29

Status: infrastructure note, not a benchmark result.

## Purpose

The current promoted Gemma 4 26B A4B Q8 record stack uses a B70 AOT SYCL build.
That is the right path for promoted results, but source experiments that touch
`ggml-sycl` can spend a long time in B70 AOT link/`ocloc`, and failed experiments
can leave the AOT build tree with dangling `libggml-sycl.so` symlinks.

For source proofing, keep a non-AOT/JIT build available. It is useful for:

- compile/parity smoke checks before spending time on B70 AOT;
- source-path sanity checks for verifier, LM-head, and MoE experiments;
- avoiding repeated long AOT stalls while rejecting obviously bad patches.

Do not use this lane for headline LocalMaxxing submissions unless it is later
validated against the fixed realistic cold suite and compared fairly to the AOT
record lane.

## Build Command

Run from the active llama.cpp record source:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh --force >/dev/null

cmake -S . -B build-sycl-b70-jit-q8reorder-vdr2 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -DCMAKE_CXX_FLAGS='-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2' \
  -DGGML_SYCL=ON \
  -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_GRAPH=ON \
  -DGGML_SYCL_DNN=ON \
  -DGGML_SYCL_HOST_MEM_FALLBACK=ON

cmake --build build-sycl-b70-jit-q8reorder-vdr2 --target llama-server -j 8
```

Key difference from the promoted B70 AOT build: do not set
`GGML_SYCL_DEVICE_ARCH`. In the local CMake logic, AOT is only enabled when that
variable is provided.

Resulting binary:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-jit-q8reorder-vdr2/bin/llama-server
```

## Current Context

- Current valid record remains `115.72789384447941 tok/s` median 1-100 after
  TTFT on the fixed realistic full512 suite.
- Record evidence:
  `/home/steve/qwen36-results-main/data/gemma4-q8-gpu1-vdr2-selecteddown-reordervdr2-full512-20260629B/summary.json`
- Record repro wrapper:
  `/home/steve/qwen36-results-main/repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh`
- The failed Q8 reordered multi-column compact-argmax attempt is recorded in
  `20260629-q8-argmax-multi-ncols-aot-negative.md`; it did not reach a runtime
  benchmark and should not be interpreted as evidence for or against the current
  promoted record.

## Validation Discipline

This JIT lane is diagnostic only. Promote a result only after running the fixed
realistic cold prompt suite:

- each prompt once as a cold first response;
- `cached_tokens=0` for every request;
- no prompt/KV cache reuse, context checkpoints, response reuse, n-gram/history
  acceleration, or warmed repeated prompts;
- same target model and quantization as the record recipe;
- MTP/speculation allowed only when target-verified;
- headline metric is median generated-token tok/s for tokens 1-100 after TTFT,
  with p10, mean, TTFT, wall tok/s, full512 tok/s, prompt/output hashes, model
  identity, runtime commit, env vars, flags, and logs preserved.
