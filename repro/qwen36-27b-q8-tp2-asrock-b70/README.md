# Reproduce Qwen3.6 27B Q8 target-only TP2 on two B70s

> **Certification: `lab-replay`.** This replays the result on a host where the
> lab's source trees, binaries, caches, models, and topology already exist. It
> is not a portable install guide; see its `missing` entry in
> [`repro/guide-catalog.json`](../guide-catalog.json).

This recipe reproduces the 2026-08-15 lab result on two ASRock Intel Arc Pro
B70 32 GiB cards. It is Q8_0 target-only decode: no MTP, DFlash, draft model,
prompt reuse, or other speculation.

## Promoted result

- Preferred conventional 99-interval median: **36.604128 tok/s**
- Conventional p10 / mean: `36.351245` / `36.634072 tok/s`
- Historical 100-event compatibility median: `36.973866 tok/s`
- Full 512-token after-TTFT median: `36.533899 tok/s`
- Full 512-token wall median: `36.053833 tok/s`
- Median TTFT: `180.255 ms`
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

This directory is a self-contained runtime snapshot: `runtime-common.sh`
preserves every generic SYCL environment door, `config.env` preserves the
result-specific fusion and device settings, `run-server.sh` launches the
bounded endpoint, `bench.sh` runs and verifies the cold suite, and
`verify-artifacts.sh` checks the embedded source patch, raw result, readable
summary, and quality gates as one coherent snapshot. It does not depend on a
contributor packet elsewhere in this repository.

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

The device-list separator differs between the two llama.cpp front ends. The
server uses `--device SYCL0,SYCL1`, as captured by `run-server.sh`. A direct
`llama-bench` TP2 run must instead use `-dev SYCL0/SYCL1`; passing a comma to
`llama-bench` creates separate one-card benchmark rows and is not a TP2 result.

The endpoint is loopback-only at `http://127.0.0.1:18081` by default. Its
contract is one slot, 8192 context, equal tensor split, F16 KV, FlashAttention
on, graph off, cache RAM zero, context checkpoints zero, and fit off.
`GGML_SYCL_FUSE_EXT=31` enables accepted fusion bits 0 through 4. Bit 4 is the
recurrent RMS/gate/final-multiply/reordered-Q8 tail fusion; leaving the variable
at the source default `15` provides the same-binary control for that final
increment. `GGML_SYCL_COMM_DIRECT_Q8=2` retains the TP2 RMS/multiply values in
registers while writing their graph-visible outputs and directly produces the
reordered Q8 handoff. `GGML_SYCL_FUSED_ROPE_SET_ROWS=1` writes attention K
IMRoPE results directly into the indexed F16 KV cache.
`GGML_SYCL_COMM_REDUCE_VEC4=1` preserves the exact scalar arithmetic order but
uses aligned four-float loads/stores and one quarter as many work-items in the
5,120-element TP root reduction. All three selectors remain default-off
outside this recipe. `GGML_SYCL_FUSED_QK_NORM_ROPE=1` joins the full-attention
Q and K RMS+scale+IMRoPE path and K-cache write into one SIMD16 launch. Its
1 KiB workgroup-local FP32 buffer deliberately preserves the incumbent
RMS+MUL materialization boundary; removing that boundary was faster but failed
10 of 12 output-hash gates. This fourth selector is also default-off outside
the exact Qwen shape matcher.
`GGML_SYCL_FUSED_CONV_SILU_L2=1` joins recurrent convolution/state update,
SiLU, and paired Q/K L2 normalization. One 256-thread workgroup owns two
complete 128-channel heads and uses a 1 KiB local FP32 SiLU boundary before
the stock-order SIMD16 L2 reductions. It is exact-shape admitted and
default-off. The rejected output-only and output-head research switches are
explicitly unset by `config.env`.

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
[`data/qwen36-q8-tp2-asrock-b70-20260814/summary.json`](../../data/qwen36-q8-tp2-asrock-b70-20260814/summary.json).
The compressed current candidate and retained earlier controls beside it are
complete raw 12-prompt JSON, including timestamps, hashes, gates, and per-row
telemetry. The promoted raw result is
`dp4a2-full-realistic512.json.gz.b64`. The current compile-time increment
evaluates each reordered-Q8 block's four DP4As as two independent integer
chains and joins the integer partials before the unchanged FP32 boundary.
It requires no additional runtime environment door.
