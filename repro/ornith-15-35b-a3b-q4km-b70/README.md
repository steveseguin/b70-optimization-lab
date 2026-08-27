# Ornith 1.5 35B-A3B — one-B70 neural.download guide

> **Integrity status, 2026-08-27: strict headline pending.** The measured
> `131.460231 tok/s` performance and same-binary patch exactness remain useful
> scoped evidence, but the runtime produced 0/12 identical complete natural
> response hashes across fresh stock servers. It therefore does not satisfy
> the lab's cross-server determinism requirement for a package headline.

Status: **model verified, one-card operating point validated, and lab decode
patch promoted** (2026-08-23). Lane: enthusiast MoE; the measured stock
two-card comparison was slower than one card for single-stream decode.

**Current directly measured target-only conventional serving mean:
`131.460231 tok/s`** (fresh-suite 99-interval medians `130.451371` and
`132.469090`, one B70, cache-zero). The corresponding legacy 100-event
compatibility pair, `131.769061` and `133.807162`, remains retained but is not
the preferred headline.

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

PATCH=/path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-twelve-feature-stack-shared-gate-residual-rms-20260823.patch
echo "7b9204f8f44608fc5b1858a15498b3cf9bf52b4f02c27c0f91a1807af5b5d15d  $PATCH" | sha256sum -c -
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
`21b9196911c9254f06756317a7cac85942517dbd4495e41694ec7f22c80db868`.
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
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_ENABLE_GRAPH=0
export GGML_SYCL_FUSED_MOE_ADD_REDUCE=1
export GGML_SYCL_FUSED_ORNITH_CONV_SILU=1
export GGML_SYCL_FUSED_RESIDUAL_RMS_NORM=1
export GGML_SYCL_FUSED_ORNITH_CONCAT_STATE=1
export GGML_SYCL_FUSED_ORNITH_CONCAT_STATE_DIRECT=1
export GGML_SYCL_FUSED_ORNITH_ALPHA_GATE=1
export GGML_SYCL_FUSED_ORNITH_MOE_GATE_UP=1
export GGML_SYCL_FUSED_ORNITH_MOE_SHARED_RESIDUAL_RMS=1
export GGML_SYCL_FUSED_ORNITH_GDN_RMS_GATE=1
export GGML_SYCL_FUSED_ORNITH_GDN_STATE_IO=1
export GGML_SYCL_FUSED_ORNITH_QK_NORM_ROPE=1
export GGML_SYCL_FUSED_ORNITH_MOE_GATE_RESIDUAL_RMS=1

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
Keep `UR_L0_USE_IMMEDIATE_COMMANDLISTS` unset: its independent matched server
screen regressed serving. The copy-offload setting above is validated only for
this exact one-B70 recipe and is not a global default for other models.

## Current twelve-feature context-depth profile (llama-bench, FA on, 5 reps)

![optimized depth sweep](optimized-depth-sweep-twelve-feature.svg)

| Depth | decode tg128 tok/s (±σ) | prefill pp2048 tok/s (±σ) |
|---:|---:|---:|
| 0 | 141.92 (±0.43) | 1422.4 (±47.9) |
| 2,048 | 136.85 (±0.13) | 1343.9 (±9.4) |
| 4,096 | 133.33 (±0.06) | 1338.2 (±5.2) |
| 8,192 | 126.83 (±0.07) | 1301.2 (±7.7) |
| 16,384 | 116.27 (±0.02) | 1238.6 (±4.9) |
| 24,576 | 106.97 (±0.28) | 1212.9 (±6.5) |
| 32,768 | 99.61 (±0.10) | 1115.6 (±3.4) |

These are directly measured raw engine rates from the exact twelve-feature
source stack and accepted copy-offload setting, with command graphs off, F16
KV, and five samples at every displayed depth. The points are not inferred
from the 8K server result; no missing depth is interpolated or extrapolated.
Raw engine rates exclude HTTP and sampling overhead, so use the current
fresh-server suite mean above as the serving headline. Evidence:
`ornith-15-35b-a3b-q4km-twelve-feature.sweep.json` plus
`ornith-15-35b-a3b-q4km-twelve-feature.meta.json` (model, benchmark, patch,
library, environment, and activation hashes/counts inside).

## Aggregate decode over concurrent sequences

The accepted stack was also measured with raw-engine continuous batching. This
is `llama-batched-bench` aggregate decode, not HTTP users/sec: it excludes
request parsing, queueing, networking, and server scheduling.

| concurrent sequences | aggregate tok/s | arithmetic per-user tok/s |
| ---: | ---: | ---: |
| 1 | 98.025 | 98.025 |
| 2 | 102.672 | 51.336 |
| 4 | 118.883 | 29.721 |
| 8 | 146.283 | 18.285 |
| 16 | 162.504 | 10.156 |
| 32 | 216.513 | 6.766 |

Exact command shape, raw rows, limitations, and the matched candidate result
are in the [aggregate evidence note](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-multirow-aggregate-positive.md)
and [machine-readable summary](../../experiments/ornith-15-b70/data/2026-08-23-ornith35b-multirow-aggregate-summary.json).
No point is interpolated or extrapolated.

For multi-sequence deployments only, an optional research patch extends the
one-row MoE-reduction and residual/RMS fusions to 2--32 rows. It improved a
focused four-sequence C/B/B/C comparison by **+2.21%** and was neutral at one
sequence. Apply it after the required twelve-feature patch:

```bash
MULTIROW_PATCH=/path/to/b70-optimization-lab/experiments/ornith-15-b70/patches/llamacpp-ornith15-multirow-aggregate-fusions-candidate-20260823.patch
echo "61135a790d749b66ca6fd63a045a5b675ec7c2e868d913e8234adff7cabbbe6e  $MULTIROW_PATCH" | sha256sum -c -
git apply --check "$MULTIROW_PATCH"
git apply "$MULTIROW_PATCH"
cmake --build build-sycl-aot-bmg-g31 --target llama-server llama-batched-bench -j2
export GGML_SYCL_FUSED_ORNITH_MULTIROW=1
```

Keep this flag unset for the package's documented `--parallel 1` launch. The
candidate is default off and has not been promoted into the required patch.

## Historical stock context-depth reference (patch off; llama-bench, FA on, 5 reps)

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
stock reference. It is not the optimized package's context curve. Raw engine
rates also run above server-suite medians by design (no HTTP/sampling). Evidence:
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
[complete source patch](../../patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-twelve-feature-stack-shared-gate-residual-rms-20260823.patch),
[patch packet](../../patches/ornith-15-35b-a3b-q4km-b70/README.md), and
[`experiments/ornith-15-b70/`](../../experiments/ornith-15-b70/).

The current complete patch also fuses each of the 30 recurrent
`SSM_CONV -> SILU` pairs, removing another 30 launches/token. Against the
ordered-MoE stack, matched engine means improved `107.467 -> 108.740 tok/s`
(**+1.18%**) and fresh-server means improved `103.012 -> 105.171 tok/s`
(**+2.10%**). The forced 400-token same-binary output was byte-identical and
all objective canaries passed. Evidence:
[`2026-08-22-ornith35b-conv-silu-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-conv-silu-positive.md).

The third package increment uses Ornith's Qwen-derived residual layout. It
materializes each `attn_residual-*` and `l_out-*` tensor in its original
volatile FP32 graph buffer, then executes the stock RMS reduction order and
fused norm-weight multiply in the same kernel. This removes another 80
launches/token, bringing the complete stack to 350 removed launches/token.
Matched engine means improved `109.629 -> 111.826 tok/s` (**+2.00%**) and
fresh-server means improved `106.319 -> 107.776 tok/s` (**+1.37%**). All four
freshness gates passed, forced 128-token output was byte-identical, and the
canary battery passed. Evidence:
[`2026-08-22-ornith35b-residual-rms-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-residual-rms-positive.md).

The fourth package increment transfers another narrowly matched optimization
from this lab's Qwen work. Each recurrent layer normally materializes a
`[4,8192]` FP32 convolution input and then copies rows 1-3 into persistent
state. The fused kernel preserves both destinations while removing the second
launch, and the matcher fails closed unless the state copy is the next real
compute node with exact names, shapes, strides, consumers, and non-overlap.
This removes another 30 launches/token, bringing the complete stack to 380.
Matched engine means improved `111.523 -> 115.457 tok/s` (**+3.53%**) and
fresh-server means improved `105.767 -> 108.662 tok/s` (**+2.74%**). The
forced 128-token output was byte-identical and the full canary battery passed.
Evidence:
[`2026-08-22-ornith35b-concat-state-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-concat-state-positive.md).

The fifth package increment uses the same Qwen lineage but tightens the
transfer to Ornith's exact one-row persistent-state layout. One channel-owned
kernel now materializes the original gathered-state tensor, full convolution
input, and shifted persistent state, while leaving `SSM_CONV` separate. It
loads all old values before the in-place state write and requires exact source
identity, sole-consumer, node-order, shape, stride, and non-overlap proofs.
This removes another 30 launches/token, bringing the complete stack to 410.
Matched engine means improved `114.559 -> 116.818 tok/s` (**+1.97%**) and
fresh-server means improved `110.646 -> 111.883 tok/s` (**+1.12%**). The
forced 128-token output was byte-identical, the hardened matcher retained all
3,810 expected hits, and the full canary battery passed. Evidence:
[`2026-08-22-ornith35b-concat-state-direct-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-concat-state-direct-positive.md).

The sixth package increment fuses Ornith's exact 32-element recurrent
`alpha + ssm_dt.bias -> softplus -> multiply by ssm_a` chain. The backend
already fused the latter two operations; this path removes the preceding ADD
launch while writing and rereading its original rounded FP32 graph buffer. The
matcher requires exact node adjacency, names, shapes, types, layout, source
order, and sole-consumer proofs. This removes another 30 launches/token,
bringing the complete stack to 440. Pooled matched engine means improved
`116.657 -> 118.040 tok/s` (**+1.18%**) and fresh-server means improved
`112.030 -> 114.314 tok/s` (**+2.04%**). Both candidate server runs exceeded
both controls, forced 128-token output was byte-identical, and the full canary
battery passed. Evidence:
[`2026-08-22-ornith35b-alpha-gate-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-alpha-gate-positive.md).

The seventh package increment retains the tuned reordered-Q4_K routed-expert
dispatcher while computing each layer's gate and up projections in one
subgroup kernel and writing SWIGLU directly. It removes a duplicate input
quantization, the second routed GEMV launch, and the standalone GLU launch in
all 40 MoE layers: 120 launches/token, bringing the complete stack to 560.
Mirrored engine means improved `118.229 -> 120.695 tok/s` (**+2.09%**) and
fresh-server means improved `113.043 -> 115.680 tok/s` (**+2.33%**). Every
candidate exceeded every control, forced 128-token output was byte-identical,
and the full canary battery passed. Evidence:
[`2026-08-23-ornith35b-moe-gate-up-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-moe-gate-up-positive.md).

The eighth package increment extends the Qwen-derived residual/RMSNorm fusion
over the preceding routed-plus-shared-expert ADD in all 40 MoE layers. It
materializes and reloads both original FP32 ADD outputs before using the stock
RMS reduction order, so both graph-visible rounding boundaries remain intact.
This removes another 40 launches/token, bringing the complete stack to 600.
Mirrored engine means improved `120.260 -> 121.456 tok/s` (**+0.99%**) and
fresh-server means improved `116.406 -> 118.048 tok/s` (**+1.41%**). Every
candidate exceeded every control, forced 128-token output was byte-identical,
and the full canary battery passed. Evidence:
[`2026-08-23-ornith35b-moe-shared-residual-rms-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-moe-shared-residual-rms-positive.md).

The ninth package increment transfers the Qwen3.5 recurrent gated-normalization
boundary directly to Ornith's exact graph. Once the parallel `z` projection is
ready, one kernel now performs the existing per-head RMS reduction, learned
weight multiply, SiLU, and final gate multiply while preserving the original
FP32 rounding boundary. It replaces the established RMS/weight and SiLU/gate
kernels with one launch in each of 30 recurrent layers, bringing the complete
stack to 630 removed launches/token. Mirrored engine means improved
`121.287 -> 121.698 tok/s` (**+0.34%**) and fresh-server means improved
`116.535 -> 117.446 tok/s` (**+0.78%**). Both candidates exceeded both
controls, forced 128-token output was byte-identical, all freshness gates
passed, and the full canary battery passed. The `117.446` then-current mean is
directly measured rather than extrapolated from the prior 118.048 point.
Evidence:
[`2026-08-23-ornith35b-gdn-rms-silu-gate-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-gdn-rms-silu-gate-positive.md).

The tenth package increment completes the Qwen-derived recurrent-state
transfer. The existing cache fusion already writes the updated GDN state to
its persistent buffer; the new strict matcher also reads that sole state row
in place and skips the temporary `GET_ROWS`. It requires exact state/value
shapes, K=1, identical persistent input/output storage, non-overlap with GDN
activations, and no other compute consumer. This removes another 30 launches
per token, bringing the complete stack to 660. Mirrored engine means improved
`122.074 -> 129.870 tok/s` (**+6.39%**) and fresh-server means improved
`118.148 -> 126.179 tok/s` (**+6.80%**). Both candidates exceeded both
controls; forced 128-token output was byte-identical, exactly 3,810 hits were
recorded, and all objective canaries passed. The realistic same-process repeat
probe retained the separately documented stock-runtime prose variability, so
it is disclosed rather than presented as a determinism pass. Evidence:
[`2026-08-23-ornith35b-gdn-state-io-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-gdn-state-io-positive.md).

The eleventh increment transfers this lab's Qwen full-attention Q/K path to
Ornith's 10 exact full-attention layers. One kernel preserves the stock SIMD16
RMS reduction, learned scale, and IMRoPE arithmetic for Q and K, leaves Q in
FP32 for flash attention, and writes K directly to its F16 cache. It replaces
five operations with one per matching layer, removing another 40 launches per
token and bringing the complete stack to 700. Mirrored engine means improved
`130.397 -> 133.424 tok/s` (**+2.32%**) and fresh-server means improved
`126.470 -> 128.832 tok/s` (**+1.87%**). Both candidates exceeded both
controls; forced 128-token output was byte-identical, exactly 1,270 hits were
recorded, and every objective canary passed. Evidence:
[`2026-08-23-ornith35b-qk-norm-rope-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-qk-norm-rope-positive.md).

The current runtime increment also comes from screening this lab's Qwen B70
work against Ornith rather than assuming that every Qwen setting transfers.
With `UR_L0_USE_IMMEDIATE_COMMANDLISTS` unset in both arms, setting
`UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1` improved mirrored seven-repetition
engine means from `131.535 -> 133.188 tok/s` (**+1.26%**) and conventional
fresh-server means from `126.884 -> 128.273 tok/s` (**+1.09%**). The legacy
compatibility means were `128.166 -> 129.568 tok/s`. The candidate won 9/12
prompt-matched averages, every response was uncached and passed the final
gate, and the forced 128-token transcript remained byte-identical. This is a
recipe-only runtime setting: the eleven-feature source patch and its binary
hashes are unchanged. Evidence:
[`2026-08-23-ornith35b-copy-offload-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-copy-offload-positive.md).

The twelfth source increment completes the shared-expert gate boundary rather
than repeating the earlier one-launch broadcast candidate. Its exact matcher
folds the scalar sigmoid and 2,048-element broadcast multiply into the already
accepted routed/shared/residual/RMS launch while preserving every rounded FP32
intermediate. This removes 80 launches/token and brings the complete stack to
780. Mirrored engine means improved `132.925 -> 134.564 tok/s` (**+1.23%**).
Conventional fresh-server mean-of-run-medians improved
`129.676 -> 131.460 tok/s` (**+1.38%**); pooled median improved +2.11%, pooled
mean improved +1.69%, and 12/12 prompt-paired averages won. The legacy
100-event compatibility means were `130.986 -> 132.788 tok/s`. The forced
128-token transcript was byte-identical across 5,080 candidate hits. Evidence:
[`2026-08-23-ornith35b-shared-gate-residual-rms-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-shared-gate-residual-rms-positive.md).

## Stock two-card comparison (patch off; layer split, GPUs 0+1)

Using the earlier stock serving protocol, `--split-mode layer` measured
**`102.011447 tok/s`** and **`102.200045 tok/s`** (canaries 5/5), about 2.6%
below the stock one-card points (`104.839983` and `104.810772 tok/s`). The
roughly 3B-active MoE already fits on one card, so the second card adds
inter-GPU latency for single-stream decode. **Recommendation: one card.**
Evidence: `ornith-15-35b-a3b-tp2.bench{A,B}.json` in the retained operating
point results.
