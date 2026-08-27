# Reproduce Gemma 4 26B A4B Q8 Baseline

For the current pause/resume bookmark and production backend recipe, read
[`HANDOFF.md`](HANDOFF.md) and [`production-service.md`](production-service.md)
first. This file is the deeper reproduction packet.

These commands set up the current llama.cpp/SYCL Gemma 4 26B Q8 lane. Under
the 2026-06-27 policy, synthetic filled-long scores are diagnostic only. The
promoted reproduction target is the fixed realistic cold prompt suite:
`repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`.

Best strict cold-suite result:

- draft-MTP VDR2 selected-down fused weighted-sum plus FA-on 32K/VMM:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`;
- primary metric: `122.16035656735696 tok/s`, the median of per-input-class
  medians using the conventional 99 inter-token intervals; secondary
  all-prompt median `123.72736943965285 tok/s`; historical 100-event
  compatibility value `124.97714084813418 tok/s`;
- config: reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`, LM-head experiment flags
  unset, Q4_0 MTP draft verified by the Q8 target;
- gate: `realistic_final_gate.passed=true`, `cached_tokens=0` on every prompt.

Representative status: the current payload uses the VDR2 selected-down fused
weighted-sum transfer of the strict `n_max=3`, `n_min=2`,
`UBATCH_SIZE=1024` family, with FA-on 32K/VMM and final post-norm residual
fusion. The same raw reproduction measured the three aggregations above; the
class-balanced `122.16035656735696 tok/s` value is now the headline. Historical
comparisons to the prior `123.67689864739785` final-postnorm and
`121.41411987308553` selected-down highs used the older aggregation; do not
compare those figures directly until their raw rows are class-balanced too.
Same-family historical support includes exact-reproduction rows at `121.59076340768573`,
`119.26425148518223`, and `113.63257982764395`, plus the older
`119.94842631460949 tok/s` confirmation and lower variance rows at
`113.572`, `114.088`, and `111.988 tok/s`; treat this as a higher-variance
baseline lane, not as a default-off LM-head source-flag win.
The 2026-07-02 documentation-pass rerun of the same wrapper measured
`120.92334534956485 tok/s` with `512/512` canary rows, `cached_tokens=0` on all
12 prompts, and `realistic_final_gate.passed=true`; it is valid same-recipe
support, not a new record. Evidence:
`../../data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`.
The 2026-07-01 GPU0 thermal sweep ran four exact same-GPU full512 repeats with
privileged `xpu-smi` telemetry and found no thermal-throttle explanation for
the variance: medians were `115.515`, `119.019`, `114.520`, and `120.202
tok/s` while active core max stayed `77-78 C`, memory max `86-90 C`, and
frequency stayed near max. Future close record comparisons should capture the
same telemetry and avoid comparing hot/cold historical outliers without
same-window controls. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`.
Prior LocalMaxxing row `cmqxchyra03xmqr01b963gmi1` at
`98.34046474459183 tok/s`, F16-p021 row
`95.82453787677183 tok/s`, VDR2 rows `90.98312252660529`,
`90.32179401019857`, and `89.45543282863798 tok/s`, plus VDR4
`87.61145306230438 tok/s`, remain valid but are superseded. The current
LocalMaxxing ID is `cmr1u77na01k2ld01kalwzs1e`.

Current no-spec control:

- `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`;
- primary metric: `74.29709476830473 tok/s` median. Use this as the simplest
  target-side quality/control reference.

## 1. Build llama.cpp with SYCL

The strict `124.977 tok/s` cold-suite recipe is not plain upstream llama.cpp.
It uses our Gemma research stack based on upstream commit `c926ad098`. The
canonical record-source aggregate and its verification receipt are now indexed
in `../../patches/gemma4-26b-a4b-q8-b70/README.md`; do not reconstruct the
record by guessing an order for the older incremental experiment patches.

The aggregate is the complete pre-next-experiment source snapshot. It includes
default-off diagnostics and rejected experiment paths that coexisted with the
accepted code. Only the runtime flags in the 125 tok/s reproduction guide are
part of the record identity.

- canonical encoded aggregate:
  `../../patches/gemma4-26b-a4b-q8-b70/llama-cpp-c926ad098-gemma4-q8-record-source-20260701.diff.gz.b64`;
- decoded SHA-256:
  `2dab9dce3d6a41cba8edad559eb754088c6f5ca1de6531f408c069e45b7f727a`;
- base commit: `c926ad09857517978575d6a74d225b463f7417a0` / tag `b9769`;
- restore/build helper:
  `../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh`.

- Optional service/prefill source patch:
  `../../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols2.patch`.
  This adds `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` for the Gemma DV512/GQA8
  FlashAttention tile path. It is a validated long-context service/prefill
  optimization, not a short-decode LocalMaxxing record change.

To reconstruct the record source and build without modifying an existing
checkout:

```bash
cd /path/to/b70-optimization-lab
SOURCE_DIR=/path/to/new/llama.cpp-gemma4-record \
  repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh
```

The helper verifies the base and decoded patch identities before applying,
refuses to overwrite an existing directory, and writes a build receipt. The
historical binary hash was not retained, so a rebuilt binary remains a source
reconstruction until it passes the full semantic and performance gates.

For manual review, the helper's essential record build options are below. The
helper is authoritative and also disables remote/prebuilt UI assets so the API
server does not depend on a changing web bundle:

```bash
cd /path/to/new/llama.cpp-gemma4-record
source /opt/intel/oneapi/setvars.sh
cmake -S . -B build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -DCMAKE_CXX_FLAGS='-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2' \
  -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg-g31 \
  -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON -DGGML_SYCL_DNN=ON \
  -DGGML_SYCL_HOST_MEM_FALLBACK=ON \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 \
  --target llama-server llama-quantize -j 2
```

## 2. Download Q8 GGUF

```bash
cd /home/steve/llm-optimizations
scripts/download-gemma4-26b-q8-gguf.sh
```

The downloader uses resumable `curl` when available and reads Hugging Face
credentials from the local secret files documented in `AGENTS.md`. It falls
back to `huggingface_hub` if curl fails.

Default output:

```text
/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
```

## 3. Launch One Replica

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 UBATCH_SIZE=64 \
  scripts/run-gemma4-26b-llamacpp-replica.sh
```

Use `CTX_SIZE=32768` only after the 8K baseline fits and passes canaries. Keep
`CACHE_TYPE_K=f16 CACHE_TYPE_V=f16` for the quality baseline before trying q8 KV.
The launcher defaults `REASONING=off` so exact-answer speed canaries receive
direct chat content; thinking-enabled mode is a separate follow-up profile.

In another shell:

```bash
python3 scripts/gemma4-text-canary.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --repeats 32 \
  --out data/gemma4-26b-a4b-q8-b70-canary-smoke.json
```

Then run a decode probe:

```bash
python3 scripts/bench-openai-single-decode.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --prompt-tokens 512 \
  --max-tokens 512 \
  --repeats 8 \
  --out data/gemma4-26b-a4b-q8-b70-smoke.json
```

For the first local baseline, the wrapper below starts the server, waits for
readiness, runs both gates, and stops the server:

```bash
cd /home/steve/llm-optimizations
scripts/run-gemma4-26b-first-baseline.sh
```

## Representative Realistic Final Gate Reproduction

The promoted record can be reproduced with the standalone wrapper:

```bash
cd /path/to/b70-optimization-lab
LLAMA_SERVER=/path/to/build/bin/llama-server \
MODEL=/models/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
MTP_DRAFT_MODEL=/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
DRAFT_SHA256=<sha256-printed-by-prepare-draft> \
GPU_INDEX=0 PORT=19350 \
  LABEL=gemma4-q8-gpu0-125repro-$(date -u +%Y%m%dT%H%M%SZ) \
  bash repro/gemma4-26b-a4b-q8-b70-125tps-20260701/run.sh
```

Or directly through the active record script:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=1 PORT=18421 \
  FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Use this command for the current representative draft-MTP realistic-suite
candidate. It reproduces the VDR2 selected-down `n_max=3`, `n_min=2`,
`p_min=0.0475`, `UBATCH_SIZE=1024` family, whose current strict row is
`124.977 tok/s` on the fixed cold suite. The previous FA-on `121.414`,
selected-down `117.915` / `115.728`, prior `98.340`, F16-p021
`95.825`, VDR2 `90.983`, `90.322`, and VDR4 `87.611 tok/s` rows remain valid
evidence but are no longer the promoted headline.

```bash
cd /home/steve/llm-optimizations
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server \
ONEAPI_DEVICE_SELECTOR=level_zero:1 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 \
GGML_SYCL_DISABLE_OPT=0 \
GGML_SYCL_DISABLE_GRAPH=0 \
GGML_SYCL_ENABLE_VMM=1 \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1 \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1 \
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1 \
LLAMA_MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1 \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1 \
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1 \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1 \
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1 \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1 \
LLAMA_SYCL_F16_P021_SMALL_NCOLS=1 \
GPU_INDEX=1 PORT=18421 \
CTX_SIZE=32768 BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 \
CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 FLASH_ATTN=on REASONING=off \
CANARY_REPEATS=32 MAX_TOKENS=512 \
REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf --spec-draft-n-max 3 --spec-draft-device SYCL0 --spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16 --spec-draft-n-min 2 --spec-draft-p-min 0.0475 --no-spec-draft-backend-sampling --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0' \
LABEL=gemma4-q8-gpu1-finalpostnorm-repro-full512-$(date -u +%Y%m%dT%H%M%SZ) \
scripts/run-gemma4-26b-first-baseline.sh
```

## Service / Long-Prefill Reproduction

This is separate from the short-decode LocalMaxxing record. Use it when the
goal is prompt-processing / long-context service throughput with the same Q8
target/verifier quality lane and `cached_tokens=0`.

Balanced service candidate:

```bash
cd /home/steve/llm-optimizations
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_PREFILL_UBATCH_SIZE=2048 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
STAMP=$(date -u +%Y%m%dT%H%M%SZ)-swalb-service \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:2048:1024:phase2048-swalb:2048' \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

This service recipe is separate from the short-decode record. The 2026-07-02
post-clean confirmation measured a combined `+6.927%` long-prefill gain versus
same-window controls, exact JSON validation, `cached_tokens=0`, and no
short-decode regression signal in a full512 guard. Evidence:
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-postclean-baseline-swalb-service-confirm.md`.

To rerun the full four-GPU A/B, cross-over, and short guard:

```bash
cd /home/steve/llm-optimizations
repro/gemma4-26b-a4b-q8-b70/run-vdr2-swalb-service-confirm.sh
```

Pure prefill candidate:

```bash
cd /home/steve/llm-optimizations
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
STAMP=$(date -u +%Y%m%dT%H%M%SZ)-gqa8-prefill \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:2304:2304:ub2304-gqa8' \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Validated reference:

- evidence:
  `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`;
- patch:
  `../../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols2.patch`;
- broad gate: `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-broadA.json`;
- same-build near-32K crossover improved mean prefill from `702.605` to
  `947.589 tok/s` with identical output hash and `cached_tokens=0`;
- broad median prefill: UB2048 `1039.603 tok/s`, UB2304 `1075.983 tok/s`.

Use this no-spec control when testing target-side changes:

```bash
cd /home/steve/llm-optimizations
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31/bin/llama-server \
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 \
GGML_SYCL_DISABLE_OPT=0 \
GGML_SYCL_DISABLE_GRAPH=0 \
GGML_SYCL_ENABLE_VMM=0 \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1 \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1 \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1 \
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1 \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1 \
GPU_INDEX=0 PORT=18314 \
CTX_SIZE=8192 BATCH_SIZE=1024 UBATCH_SIZE=720 THREADS=8 POLL=100 \
CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 FLASH_ATTN=off REASONING=off \
CANARY_REPEATS=32 MAX_TOKENS=512 \
REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0 --ctx-checkpoints 0' \
LABEL=gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-$(date -u +%Y%m%dT%H%M%SZ) \
scripts/run-gemma4-26b-first-baseline.sh
```

Validated conservative baseline:

```text
label: gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z
canary: 128/128 chat rows pass
p512/o512: 26.10 tok/s after TTFT, 24.24 tok/s wall
summary: data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z.server.log
```

Previous no-spec natural-stop best:

```bash
cd /home/steve/llm-optimizations
LABEL=gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915 \
GPU_INDEX=2 PORT=18262 CTX_SIZE=8192 BATCH_SIZE=512 UBATCH_SIZE=64 THREADS=16 \
CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 POLL=50 FLASH_ATTN=off REASONING=off \
GGML_SYCL_DISABLE_OPT=0 CANARY_REPEATS=96 BENCH_REPEATS=12 \
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0' \
scripts/run-gemma4-26b-first-baseline.sh
```

Result:

```text
canary: 384/384 chat rows pass
p512/o512 requested, actual generated output mean: 146.4 tokens
tok/s: 42.15 after TTFT, 36.41 wall
summary: data/gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915.server.log
```

Current sustained-decode best:

```bash
cd /home/steve/llm-optimizations
LABEL=gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945 \
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 BATCH_SIZE=512 UBATCH_SIZE=64 THREADS=16 \
CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 POLL=50 FLASH_ATTN=off REASONING=off \
GGML_SYCL_DISABLE_OPT=0 CANARY_REPEATS=96 BENCH_REPEATS=8 \
BENCH_PROMPT_MODE=long \
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0' \
scripts/run-gemma4-26b-first-baseline.sh
```

Result:

```text
canary: 384/384 chat rows pass
actual benchmark shape: about 75 prompt tokens, 512 output tokens
tok/s: 42.72 after TTFT, 41.35 wall
summary: data/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945.server.log
```

Previous draft-MTP `n=4` sustained-decode record:

```bash
cd /home/steve/llm-optimizations
LLAMA_SERVER=/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-server \
GPU_INDEX=1 PORT=18261 LABEL=gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140 \
CTX_SIZE=8192 BATCH_SIZE=512 UBATCH_SIZE=64 THREADS=16 \
CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 POLL=50 FLASH_ATTN=off REASONING=off \
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf --spec-draft-n-max 4 --spec-draft-device SYCL0 --spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16' \
GGML_SYCL_DISABLE_OPT=0 CANARY_REPEATS=96 BENCH_PROMPT_MODE=long \
PROMPT_TOKENS=512 MAX_TOKENS=512 BENCH_REPEATS=8 READINESS_TIMEOUT_S=1200 \
scripts/run-gemma4-26b-first-baseline.sh
```

Result:

```text
canary: 384/384 chat rows pass
actual benchmark shape: 75 prompt tokens, 512 output tokens
tok/s: 44.50 after TTFT, 43.03 wall
summary: data/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140.server.log
```

Current short-prompt draft-MTP sustained-decode best:

```bash
cd /home/steve/llm-optimizations
LLAMA_SERVER=/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server \
GPU_INDEX=0 PORT=18260 LABEL=gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353 \
MTP_N_MAX=3 scripts/run-gemma4-26b-mtp-candidate.sh
```

Result:

```text
canary: 384/384 chat rows pass
actual benchmark shape: 75 prompt tokens, 512 output tokens
tok/s: 48.35 after TTFT, 46.60 wall
summary: data/gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353.server.log
```

Warmed/history draftless ngram-mod artifact:

```bash
cd /home/steve/llm-optimizations
LLAMA_SERVER=/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31/bin/llama-server \
GPU_INDEX=1 PORT=18261 LABEL=gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855 \
SPEC_TYPE=ngram-mod \
SPEC_EXTRA_ARGS="--ctx-checkpoints 0 --spec-ngram-mod-n-match 20 --spec-ngram-mod-n-min 32 --spec-ngram-mod-n-max 64" \
BENCH_PROMPT_MODE=filled-long PROMPT_TOKENS=512 MAX_TOKENS=512 \
CANARY_REPEATS=96 BENCH_REPEATS=8 \
GGML_SYCL_DISABLE_OPT=0 FLASH_ATTN=off POLL=100 THREADS=16 \
CTX_SIZE=4096 BATCH_SIZE=512 UBATCH_SIZE=512 \
scripts/run-gemma4-26b-spec-candidate.sh
```

Result:

```text
canary: 384/384 chat rows pass
actual benchmark shape: 588 prompt tokens, 512 output tokens
tok/s: 280.64 after TTFT, 206.24 warmed wall
LocalMaxxing: cmqqyby6801dvqo01as3wenz2 (retraction-needed if displayed as headline throughput)
server ngram stats: 3493/3493 accepted/generated draft tokens, mean accepted length 63.38
summary: data/gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855.server.log
```

This is draftless history-cache acceleration on the repeated filled-long
benchmark. It is quality-preserving because the Q8 target model verifies every
drafted token, but it should not be used as a unique-prompt no-cache decode
claim or as a 32K-context result.

Historical synthetic filled-long draft-MTP diagnostic:

For a copy-ready version of the current strict path, start with
[`../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/`](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md).

For a copy-ready version of the older historical diagnostic path, including the exact patch,
configuration, scripts, and copied result artifacts, start with
[`../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/`](../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md)
for the older superseded recipe. The diagnostic 176.216 tok/s recipe is the same
family plus direct argmax-ID unroll, q-only Gemma4Assistant attention inputs,
verifier backend argmax IDs, deferred target `h_nextn`, selected-softmax +
weighted-sum Gemma4 MoE source guards, route cache, fused assistant output
argmax, fused selected-softmax weights, RMS reuse, and the Q8 MoE-ID reorder
path plus reordered Q8_0 MMVQ VDR=2 compile knob that makes
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` viable for the UD-Q8_K_XL target.

```bash
cd /home/steve/llm-optimizations
EXTRA='--parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf --spec-draft-n-max 7 --spec-draft-device SYCL0 --spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16 --spec-draft-n-min 3 --spec-draft-p-min 0.10 --no-spec-draft-backend-sampling --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0'
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 \
GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_DISABLE_GRAPH=0 GGML_SYCL_ENABLE_VMM=0 \
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server \
MODEL=/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
EXTRA_LLAMA_ARGS="$EXTRA" \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1 \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1 \
LLAMA_MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1 LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1 LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1 \
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1 \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1 \
GPU_INDEX=0 PORT=18310 LABEL=gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-$(date -u +%Y%m%dT%H%M%SZ) \
CTX_SIZE=8192 \
BATCH_SIZE=1024 UBATCH_SIZE=720 POLL=100 THREADS=8 \
FLASH_ATTN=off REASONING=off \
CANARY_REPEATS=1536 BENCH_REPEATS=3 \
PROMPT_TOKENS=512 MAX_TOKENS=512 BENCH_PROMPT_MODE=filled-long \
scripts/run-gemma4-26b-first-baseline.sh
```

Result:

```text
canary: 1536/1536 chat rows pass
actual benchmark shape: 588 prompt tokens, 512 output tokens
diagnostic synthetic row0 tok/s: 176.216 first no-cache request after TTFT
supporting repeated-request mean: 176.403 after TTFT; first-row wall: 139.317
prompt cache: cached_tokens=0 on every row
LocalMaxxing: cmqwkedg303jeqr013z753j62
target/draft: UD-Q8_K_XL target/verifier with Q4_0 MTP draft only
summary: data/gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z/summary.json
LocalMaxxing queue: data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627.queue.json
LocalMaxxing response: data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627.submit.log
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z.server.log
```

The historical diagnostic patch path requires the local llama.cpp patch stack captured in
`patches/gemma4-26b-a4b-q8-b70/`, especially the direct-unroll, q-only
assistant-input, RMS reuse, and Q8 MoE-ID reorder patches listed above.
Without that patch stack, `MTP_DRAFT_FAST_ARGMAX`, direct argmax-ID unroll,
q-only assistant inputs, and the CPU hot-path cleanup are not available and
this command falls back toward the older `91.16-95.26 tok/s` recipe families.

Build the `c926ad098` runtime in a separate worktree:

```bash
WT=/home/steve/src/llama.cpp-gemma-record-repro-c926
BUILD="$WT/build-sycl-b70-aot-bmg-g31"
source /opt/intel/oneapi/setvars.sh --force
cmake -S "$WT" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=icx \
  -DCMAKE_CXX_COMPILER=icpx \
  -DGGML_SYCL=ON \
  -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_DEVICE_ARCH=bmg-g31
cmake --build "$BUILD" -j 16 --target llama-server llama-cli llama-bench
```

Short wrapper equivalent for future sweeps:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=1 PORT=18261 LABEL=gemma4-q8-gpu1-mtp-n3-long-deep-<stamp> \
BENCH_PROMPT_MODE=filled-long PROMPT_TOKENS=512 MAX_TOKENS=512 \
MTP_N_MAX=3 scripts/run-gemma4-26b-mtp-candidate.sh
```

Useful safe MTP sweep knobs:

```bash
MTP_N_MAX=3
MTP_N_MAX=5 MTP_N_MIN=2 MTP_P_MIN=0.15
MTP_N_MAX=6 MTP_N_MIN=2 MTP_P_MIN=0.25
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.10 MTP_BACKEND_SAMPLING=0
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.10 MTP_BACKEND_SAMPLING=0 MTP_DRAFT_THREADS=32
POLL=100 MTP_N_MAX=4
LLAMA_CACHE_RAM=1 MTP_N_MAX=3
LLAMA_PARALLEL=2 MTP_N_MAX=3
```

For future sustained-decode comparisons, prefer
`BENCH_PROMPT_MODE=filled-long` if the target is an actual near-512-token input
plus 512-token output. The older `long` mode is intentionally retained so the
published 75/512 record remains reproducible; do not mix the two shapes when
deciding whether a run broke a record.

2026-06-27 audit note: a clean rebuild control initially looked like a severe
regression (`~47 tok/s`) because it accidentally used `BENCH_PROMPT_MODE=long`
(`75` actual prompt tokens). Re-running the same clean binary with
`BENCH_PROMPT_MODE=filled-long` restored the record lane at `102.252 tok/s`
synthetic row0 (`588` actual prompt tokens, `512` output tokens, `64/64` canary).
Treat `long` and `filled-long` as separate benchmark identities.

## 4. Launch Four Replicas

```bash
cd /home/steve/llm-optimizations
scripts/run-gemma4-26b-llamacpp-quad.sh
```

Ports default to `18260`, `18261`, `18262`, and `18263`, mapped to
`level_zero:0..3`.

## 5. Promote A Result

Before adding to the result table:

1. save the benchmark JSON under `data/`;
2. copy or link the server logs from `/mnt/fast-ai/bench-results/...`;
3. update [validity-gates.md](validity-gates.md) if the gate changed;
4. update [README.md](README.md) with the result status;
5. commit the docs/scripts/data packet.
