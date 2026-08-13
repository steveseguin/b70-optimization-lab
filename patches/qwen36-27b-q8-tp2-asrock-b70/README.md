# Qwen3.6 27B Q8 TP2 lab patch

This directory preserves the complete source delta for the 2026-08-13
target-only Q8_0 TP2 result on two ASRock Intel Arc Pro B70 cards.

## Source identity

- Upstream fork: <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization>
- Clean base commit: `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- Patch artifact:
  `llama-cpp-mndodd-4302fb599-lab-tp2-20260813.diff.gz.b64`
- Decoded patch SHA-256:
  `710b8628f6c94025d9a0516f77bddeeebccdd27d5bd3ebc4f79d2e623b1dd6c7`
- Base-to-patch scope: 17 files, 3,431 insertions, 77 deletions.

The artifact is a full diff from the clean mndodd commit. Do not first apply
the smaller compatibility patch from the contributor packet; those changes
are already included here.

## Restore and apply

```bash
git clone https://github.com/mndodd/llama.cpp.git llama.cpp-qwen36-q8-tp2
cd llama.cpp-qwen36-q8-tp2
git checkout 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126

base64 -d \
  /path/to/b70-optimization-lab/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-20260813.diff.gz.b64 \
  | gzip -dc > /tmp/qwen36-q8-tp2.patch

sha256sum /tmp/qwen36-q8-tp2.patch
git apply --check /tmp/qwen36-q8-tp2.patch
git apply /tmp/qwen36-q8-tp2.patch
git diff --check
```

The decoded hash must equal the value above.

## Build identity

The validated build used Intel oneAPI DPC++/C++ 2026.1.0 and:

```bash
cmake -G "Unix Makefiles" -S . -B build-sycl-aot-bmg-g31 \
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

cmake --build build-sycl-aot-bmg-g31 \
  --target llama-bench llama-cli llama-server -j2
```

On the 15 GiB reference host, run the build in a cgroup with an 8 GiB hard
memory limit and do not overlap it with a loaded model. The validated local
binaries had these hashes:

- `llama-server`:
  `206bd4cec822c2340402f7bb25c049655736282c3a6b8aa20e929e8afa4534a9`
- `llama-bench`:
  `4ee4db290ffbb6a25c9c5a635ca48db8acc1784ee0e2148db6406b6cc9723be2`
- `libggml-sycl.so`:
  `d667e6f3ccabede45df4f9512024cb1ae8653ab0bbea7827b6baf8599221e2a6`

## What the patch contains

The full stack is default-off and admitted through strict graph/shape checks.
It includes:

- bounded 64 MiB meta-backend bookkeeping arenas for this low-RAM host;
- exact-F32 TP2 all-reduce/residual/RMS/multiply fusion and fused Q8 handoff;
- repeated activation-Q8 quantization deduplication;
- SWIGLU, full-attention gate, and GDN-tail Q8 producers;
- paired, triple, and recurrent quad reordered-Q8 MMVQ dispatch;
- GDN beta-sigmoid and convolution-state update launch fusion;
- direct in-place GDN persistent-state I/O, removing the exact matched
  `GET_ROWS -> GDN -> CPY` state round trip;
- direct in-place convolution-state I/O, replacing the exact matched
  `GET_ROWS -> CONCAT/CPY -> SSM_CONV` chain with one kernel while preserving
  the stock four-term accumulation loop;
- recurrent RMS normalization/scale, precomputed SiLU gate, final multiply,
  and reordered-Q8 handoff fusion, admitted only when the gate MM is already
  in the precomputed-MMVQ set and preserving the stock FP32 boundaries.

The two state-I/O paths and final recurrent-tail path have poison controls for
validation. Never set a poison variable in a real service.

## Runtime doors

Use the complete environment and server command in
[`repro/qwen36-27b-q8-tp2-asrock-b70/`](../../repro/qwen36-27b-q8-tp2-asrock-b70/).
The source patch alone does not enable the optimized paths.
The promoted environment sets `GGML_SYCL_FUSE_EXT=31`; bit 4 is the final
recurrent-tail fusion. The source default `15` leaves bit 4 off and was used as
the same-binary attribution control.
