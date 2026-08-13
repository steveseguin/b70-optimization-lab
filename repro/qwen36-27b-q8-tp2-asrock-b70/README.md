# Reproduce Qwen3.6 27B Q8 target-only TP2 on two B70s

This recipe reproduces the 2026-08-13 lab result on two ASRock Intel Arc Pro
B70 32 GiB cards. It is Q8_0 target-only decode: no MTP, DFlash, draft model,
prompt reuse, or other speculation.

## Promoted result

- Preferred conventional 99-interval median: **35.494434 tok/s**
- Conventional p10 / mean: `34.958732` / `35.506893 tok/s`
- Historical 100-event compatibility median: `35.852963 tok/s`
- Full 512-token after-TTFT median: `35.437512 tok/s`
- Full 512-token wall median: `34.954163 tok/s`
- Median TTFT: `174.892 ms`
- Quality: 12/12 output hashes exact, 12/12 at 512 completion tokens,
  every `cached_tokens=0`, realistic and fresh-response gates passed.

The historical helper divides 100 events by the span between event 1 and
event 100. The preferred conventional rate divides the 99 actual inter-token
intervals by that same span, so it is `legacy × 0.99`.

## Prerequisites

- Ubuntu 24.04 with the validated OMIX 0.3 Intel GPU stack
- two healthy B70 32 GiB cards with full ReBAR
- Intel oneAPI DPC++/C++ 2026.1.0
- the Q8_0 model file identified below
- at least 8 GiB host swap on a 16 GiB-class host

Do not overlap a BMG AOT build with a loaded model on a 15–16 GiB host. The
provided server launcher runs under an 8 GiB soft / 10 GiB hard host-memory
cap. Persistent SYCL caching is intentionally disabled by the common runtime.

## 1. Restore the source

Follow the patch instructions in
[`patches/qwen36-27b-q8-tp2-asrock-b70/README.md`](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md).
The required clean base is mndodd commit
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`.

## 2. Build

Source oneAPI, then configure the patched tree:

```bash
set +u
source /opt/intel/oneapi/tbb/2023.1/env/vars.sh
source /opt/intel/oneapi/compiler/2026.1/env/vars.sh
source /opt/intel/oneapi/mkl/2026.1/env/vars.sh
source /opt/intel/oneapi/umf/1.0/env/vars.sh
set -u

cmake -G "Unix Makefiles" \
  -S /path/to/llama.cpp-qwen36-q8-tp2 \
  -B /path/to/llama.cpp-qwen36-q8-tp2/build-sycl-aot-bmg-g31 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/usr/bin/cc \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  -DBUILD_SHARED_LIBS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_CURL=OFF \
  -DGGML_SYCL=ON \
  -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg_g31 \
  -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_GRAPH=OFF \
  -DGGML_SYCL_DNN=OFF \
  -DGGML_SYCL_HOST_MEM_FALLBACK=OFF \
  -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON

systemd-run --user --wait --collect \
  --property=MemoryHigh=6G \
  --property=MemoryMax=8G \
  --property=MemorySwapMax=8G \
  --property=WorkingDirectory=/path/to/llama.cpp-qwen36-q8-tp2 \
  cmake --build build-sycl-aot-bmg-g31 \
    --target llama-bench llama-cli llama-server -j2
```

Set `QWEN36_SOURCE_DIR` and `QWEN36_BUILD_DIR` in the shell if the restored
paths differ from this host's defaults.

## 3. Prepare the model

The validated artifact is:

- repository: <https://huggingface.co/ggml-org/Qwen3.6-27B-GGUF>
- revision: `8a7ee08e8b9bfb857107ecc25a5599d2f38b76f8`
- file: `Qwen3.6-27B-Q8_0.gguf`
- bytes: `28,595,762,464`
- SHA-256:
  `73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9`

Set `QWEN36_MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf` when using another model
directory. The launcher verifies the complete model hash before loading.

## 4. Start the target-only endpoint

In one terminal:

```bash
cd /path/to/b70-optimization-lab
QWEN36_SOURCE_DIR=/path/to/llama.cpp-qwen36-q8-tp2 \
QWEN36_BUILD_DIR=/path/to/llama.cpp-qwen36-q8-tp2/build-sycl-aot-bmg-g31 \
QWEN36_MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf \
repro/qwen36-27b-q8-tp2-asrock-b70/run-server.sh
```

The exact reference-host selector is `level_zero:1,0`, with the runtime then
addressing `SYCL0,SYCL1`. If enumeration differs on another machine, first map
the two intended B70s explicitly; do not guess from branding.

The endpoint is loopback-only at `http://127.0.0.1:18081` by default. Its
contract is one slot, 8192 context, equal tensor split, F16 KV, FlashAttention
on, graph off, cache RAM zero, context checkpoints zero, and fit off.

## 5. Run the fixed cold suite

In a second terminal:

```bash
cd /path/to/b70-optimization-lab
OUT=/path/to/result.json \
repro/qwen36-27b-q8-tp2-asrock-b70/bench.sh
```

The verifier fails unless the fresh-response/cache gates pass and all 12
output hashes equal the promoted target-only oracle. Throughput varies with
clocks and host load; exact output identity is not optional.

## 6. Verify preserved artifacts

```bash
repro/qwen36-27b-q8-tp2-asrock-b70/verify-artifacts.sh
```

The readable result summary is
[`data/qwen36-q8-tp2-asrock-b70-20260813/summary.json`](../../data/qwen36-q8-tp2-asrock-b70-20260813/summary.json).
The compressed file beside it is the complete raw 12-prompt JSON, including
timestamps, hashes, gates, and per-row telemetry.
