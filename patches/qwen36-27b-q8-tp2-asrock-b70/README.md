# Qwen3.6 27B Q8 TP2 lab patch

This directory preserves the complete source delta for the 2026-08-14
target-only Q8_0 TP2 result on two ASRock Intel Arc Pro B70 cards.

## Source identity

- Upstream fork: <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization>
- Clean base commit: `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- Patch artifact:
  `llama-cpp-mndodd-4302fb599-lab-tp2-20260814.diff.gz.b64`
- Decoded patch SHA-256:
  `c917fcbf01b5af3ed45bb19532cfa0f337066b1330ffde6765564918e7a8d772`
- Base-to-patch scope: 18 files, 3,715 insertions, 100 deletions.

The artifact is a full diff from the clean mndodd commit. Do not first apply
the smaller compatibility patch from the contributor packet; those changes
are already included here.

## Restore and apply

```bash
git clone https://github.com/mndodd/llama.cpp.git llama.cpp-qwen36-q8-tp2
cd llama.cpp-qwen36-q8-tp2
git checkout 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126

base64 -d \
  /path/to/b70-optimization-lab/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-20260814.diff.gz.b64 \
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
  `32c581628082fa1352824650d45f523d52b526aaefdfd23e1c34d438f7ad084a`
- `llama-bench`:
  `f7010c08b534a4f338b9cbd83f97f22b82f13ddab5be0c727d16c3bb0f8c4312`
- `libggml-sycl.so`:
  `944e2ddb026bfdcd3147323f7edbfdabbae7754a51cfdb74149045f8895ddd5f`

These hashes identify the promoted build; they are provenance, not a required
rebuild gate. A later rebuild from the same accepted source produced a
different Intel AOT shared-library hash while retaining the server/bench
hashes and passing the complete 12/12 exact-output replay. Reproduction is
gated by the source-patch hash, declared build/runtime settings, fresh/cache
checks, and output hashes.

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
- register-direct TP2 reordered-Q8 handoff, retaining each 32-value Q8 block
  in registers after RMS/scale while still writing the graph-visible F32
  multiply output;
- direct IMRoPE-to-indexed-F16-KV-cache writes for the exact
  `ROPE -> VIEW -> SET_ROWS` attention-K graph closure.

The two state-I/O paths and final recurrent-tail path have poison controls for
validation. Never set a poison variable in a real service.

## Runtime doors

Use the complete environment and server command in
[`repro/qwen36-27b-q8-tp2-asrock-b70/`](../../repro/qwen36-27b-q8-tp2-asrock-b70/).
The source patch alone does not enable the optimized paths.
The promoted environment sets `GGML_SYCL_FUSE_EXT=31`; bit 4 is the final
recurrent-tail fusion. The source default `15` leaves bit 4 off and was used as
the same-binary attribution control. The 2026-08-14 increment additionally
sets `GGML_SYCL_COMM_DIRECT_Q8=2` and `GGML_SYCL_FUSED_ROPE_SET_ROWS=1`.
Both selectors are default-off and were exact-output gated independently.

The previous 2026-08-13 patch artifact remains in this directory for the
earlier 35.699225 tok/s record; it must not be stacked with the 2026-08-14 full
patch because the newer artifact already contains the complete source delta.
