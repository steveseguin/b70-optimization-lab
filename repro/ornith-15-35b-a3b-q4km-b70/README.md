# Ornith 1.5 35B-A3B — one-B70 neural.download guide

Status: **model verified, one-card operating point validated, and lab decode
patch promoted** (2026-08-22). Lane: enthusiast MoE; the measured stock
two-card comparison was slower than one card for single-stream decode.

**Intake diagnostic baseline (1x B70, 8K ctx, f16 KV, target-only,
128/100 window, cache-zero verified): `105.782 tok/s` median /
`105.284` p10.** This is the historical stock intake point; the optimized
serving result and matched controls are below.

## Identity

| Field | Value |
| --- | --- |
| Model | Ornith 1.5 35B-A3B, arch `qwen35moe` (256 experts / 8 used, 41 layers, GQA 16/2, embed 2048, native ctx 262144) |
| File | `Ornith-1.5-35B-Q4_K_M.gguf` (21,713,462,848 bytes) |
| SHA-256 | `ca6ea26329c88b78ffd90a85163be2e746c2fafd1024f56db47e499f117f9a7f` |
| Source | `ornith-ai/Ornith-1.5-35B-A3B-GGUF` @ `fbbaed45c2f0e200276ffa51701a24d45dc7f57e` |
| Store | `/mnt/usb-models/llm-models/ornith-1.5-35b-a3b-q4km/` (catalog id `ornith-15-35b-a3b-q4km`) |
| Base | upstream llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`, SYCL AOT bmg-g31, IntelLLVM 2026.0.0 |
| Device | 1x Intel Arc Pro B70 (32 GiB); stock 2x comparison documented below |

Question this packet answers: provide a reproducible, independently validated
one-B70 recipe for this model. The model, runtime, patch, and local evidence in
this repository define the recipe.

## Storage requirement

Stage the GGUF on a local NVMe/SATA SSD or a sufficiently fast direct-attached
USB SSD before serving or benchmarking. On the audit host, first-token setup
also rereads the approximately 20.0 GB of routed expert tensors while creating
the optimized device layout. A 100 Mb/s NFS mmap therefore made a cold attempt
require two slow passes and was rejected as performance evidence. Verify the
local copy against the pinned SHA-256 before launch.

## Restore, patch, and build

Use a clean source tree at the pinned revision. Do not apply the patch to an
arbitrary newer checkout.

```bash
git clone https://github.com/ggml-org/llama.cpp.git llama.cpp-ornith15
cd llama.cpp-ornith15
git checkout 9fee29e9435f865ec0b811a783a6471a136d9317

PATCH=/path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-moe-add-conv-silu-20260822.patch
echo "8e780b0f4c43a69bd18d0d8d66087d65813cb83353437c3443898231b94c0f9c  $PATCH" | sha256sum -c -
git apply --check "$PATCH"
git apply "$PATCH"
git diff --check

source /opt/intel/oneapi/setvars.sh --force
cmake -G Ninja -S . -B build-sycl-aot-bmg-g31 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  -DBUILD_SHARED_LIBS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_CURL=OFF \
  -DGGML_SYCL=ON \
  -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg_g31 \
  -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_GRAPH=ON \
  -DGGML_SYCL_DNN=ON \
  -DGGML_SYCL_HOST_MEM_FALLBACK=ON \
  -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON \
  -DGGML_SYCL_MAX_PARALLEL_LINK_JOBS=8
cmake --build build-sycl-aot-bmg-g31 --target llama-server llama-bench -j2
```

The validated compute library SHA-256 was
`d478e4ca7c84faef34e6acf8b1bcf3bdfd8b6e37abe884ea9e0b2826f0dfe883`.
AOT output can vary with the compiler installation, so the source revision,
patch hash, build settings, and validation gates are the durable identity.

## Launch

First verify the model with the repository preflight, then enable the
default-off lab patch:

```bash
export MODEL_DIR=/models/ornith-1.5-35b-a3b-q4km
python3 /path/to/b70-optimization-lab/scripts/verify-neural-download-model.py \
  /path/to/b70-optimization-lab/repro/ornith-15-35b-a3b-q4km-b70/model-manifest.json \
  "$MODEL_DIR"

source /opt/intel/oneapi/setvars.sh --force
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export GGML_SYCL_ENABLE_GRAPH=0
export GGML_SYCL_FUSED_MOE_ADD_REDUCE=1
export GGML_SYCL_FUSED_ORNITH_CONV_SILU=1

build-sycl-aot-bmg-g31/bin/llama-server \
  --model "$MODEL_DIR/Ornith-1.5-35B-Q4_K_M.gguf" \
  --alias ornith35b --reasoning off --ctx-size 8192 \
  --cache-type-k f16 --cache-type-v f16 --device SYCL0 \
  --gpu-layers 99 --flash-attn auto --parallel 1 \
  --cache-ram 0 --ctx-checkpoints 0 --fit off --metrics --no-webui \
  --host 127.0.0.1 --port 18100
```

Do not enable SYCL command graphs for this model on the pinned stack; the
matched model-level experiment regressed decode by 52%.

## Stock context-depth reference (patch off; llama-bench, FA on, 5 reps)

![depth sweep](depth-sweep.svg)

| Depth | decode tg128 tok/s (±σ) | prefill pp2048 tok/s (±σ) |
|---:|---:|---:|
| 0 | 108.91 (±0.06) | 1171.2 (±9.1) |
| 2,048 | 105.15 (±0.25) | 1082.7 (±4.1) |
| 4,096 | 102.85 (±0.19) | 1065.1 (±5.3) |
| 8,192 | 98.76 (±0.16) | 1049.3 (±6.9) |
| 16,384 | 91.92 (±0.03) | 1008.5 (±4.6) |
| 24,576 | 85.79 (±0.03) | 1002.6 (±8.3) |
| 32,768 | 80.42 (±0.16) | 920.1 (±7.4) |

This sweep predates the ordered-add patch and is retained only as a measured
stock reference. It is not published as the optimized package's context curve;
that patch-on sweep remains pending. Raw engine rates also run above
server-suite medians by design (no HTTP/sampling). Evidence:
`ornith-15-35b-a3b-q4km.sweep.json` +
`ornith-15-35b-a3b-q4km.meta.json` (model/bench SHAs inside).

## Published operating point: optimized standard (8K, F16 KV, target-only)

The promoted ordered-add patch removes 240 launch boundaries per token. In a
matched two-control/two-candidate screen:

| Protocol | Controls | Patched | Mean change |
|---|---|---|---:|
| raw engine `p0/n128/d0/r7` | `102.627`, `103.469` | `107.856`, `108.340` | **+4.90%** |
| fresh 12-prompt server suite | `100.240`, `99.088` | `104.016`, `104.983` | **+4.85%** |

The serving rows used 512-token responses and the median generated-token rate
for tokens 1-100 after TTFT. Every prompt was unique and executed once;
`cached_tokens=0` was verified for every request.

Correctness gates:

- forced 400-token same-binary door-off/on greedy output: byte-identical;
- candidate 8x same-server repeat stability: pass;
- arithmetic, exact-copy, and JSON-schema canaries: pass;
- fresh stock servers were already cross-process nondeterministic (`0/12`
  complete suite hashes matched), so cross-process response identity is an
  open runtime limitation rather than a patch acceptance gate.

Patch instructions and evidence:
[`patches/ornith-15-35b-a3b-q4km-b70/`](../../patches/ornith-15-35b-a3b-q4km-b70/)
and
[`experiments/ornith-15-b70/`](../../experiments/ornith-15-b70/).

The current complete patch also fuses each of the 30 recurrent
`SSM_CONV -> SILU` pairs, removing another 30 launches/token. Against the
ordered-MoE stack, matched engine means improved `107.467 -> 108.740 tok/s`
(**+1.18%**) and fresh-server means improved `103.012 -> 105.171 tok/s`
(**+2.10%**). The forced 400-token same-binary output was byte-identical and
all objective canaries passed. Evidence:
[`2026-08-22-ornith35b-conv-silu-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-conv-silu-positive.md).

## Stock two-card comparison (patch off; layer split, GPUs 0+1)

Using the earlier stock serving protocol, `--split-mode layer` measured
**`102.011447 tok/s`** and **`102.200045 tok/s`** (canaries 5/5), about 2.6%
below the stock one-card points (`104.839983` and `104.810772 tok/s`). The
roughly 3B-active MoE already fits on one card, so the second card adds
inter-GPU latency for single-stream decode. **Recommendation: one card.**
Evidence: `ornith-15-35b-a3b-tp2.bench{A,B}.json` in the retained operating
point results.
