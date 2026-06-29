# Reproduce Gemma 4 26B A4B Q8 Baseline

These commands set up the current llama.cpp/SYCL Gemma 4 26B Q8 lane. Under
the 2026-06-27 policy, synthetic filled-long scores are diagnostic only. The
promoted reproduction target is the fixed realistic cold prompt suite:
`repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`.

Best strict cold-suite result:

- draft-MTP VDR2 selected-down fused weighted-sum plus FA-on 32K/VMM:
  `data/gemma4-q8-gpu3-faon-vmm-ctx32768-full512-20260629T211437Z/summary.json`;
- primary metric: `117.91456485086059 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT;
- config: reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, Q4_0 MTP draft
  verified by the Q8 target;
- gate: `realistic_final_gate.passed=true`, `cached_tokens=0` on every prompt.

Representative status: the current payload uses the VDR2 selected-down fused
weighted-sum transfer of the strict `n_max=3`, `n_min=2`,
`UBATCH_SIZE=1024` family, with FA-on 32K/VMM. The current repeat measured
`117.91456485086059 tok/s` and supersedes the previous selected-down high
`115.8466634928202 tok/s`. Same-identity confirmations measured
`116.45776605647993`, `117.41509141115063`, `115.08942949119734`, and
`117.45737477243767 tok/s`; this is a small confirmed variance-class
improvement. Prior LocalMaxxing row `cmqxchyra03xmqr01b963gmi1` at
`98.34046474459183 tok/s`, F16-p021 row
`95.82453787677183 tok/s`, VDR2 rows `90.98312252660529`,
`90.32179401019857`, and `89.45543282863798 tok/s`, plus VDR4
`87.61145306230438 tok/s`, remain valid but are superseded.

Current no-spec control:

- `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`;
- primary metric: `74.29709476830473 tok/s` median. Use this as the simplest
  target-side quality/control reference.

## 1. Build llama.cpp with SYCL

The current diagnostic `176.216 tok/s` recipe is not plain upstream llama.cpp.
It uses the local Gemma research stack based on upstream commit `c926ad098`;
apply the current cumulative stack plus the Q8 MoE-ID reorder patch snapshot
and VDR compile-knob patch:

- `../../patches/gemma4-26b-a4b-q8-b70/20260626T2225-llamacpp-gemma4-current-record-stack.patch`
- `../../patches/gemma4-26b-a4b-q8-b70/20260626T2225-llamacpp-gemma4-current-record-stack.md`
- `../../patches/gemma4-26b-a4b-q8-b70/20260627T0704-llamacpp-gemma4-moe-reuse-attn-rms-incremental.patch`
- `../../patches/gemma4-26b-a4b-q8-b70/20260627-llamacpp-gemma4-moe-reuse-attn-rms-record.md`
- `../../patches/gemma4-26b-a4b-q8-b70/q8-moe-id-reorder-positive-20260627.md`
- `../../patches/gemma4-26b-a4b-q8-b70/q8-reorder-vdr-compile-knob-20260627.patch`
- Current full local worktree capture for the selected-down record:
  `../../patches/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-reordervdr2-source.patch`
  plus the harness identity patch
  `../../patches/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-reordervdr2-harness.patch`.

The `20260626T2225` patch is intentionally cumulative and includes default-off
rejected experiment paths. The RMS patch is the small incremental source change
for the superseded `104.309` micro-record. The Q8 MoE-ID reorder snapshot
documents the `170-171` path. The VDR compile-knob patch is default-preserving;
the current promoted realistic-suite build explicitly sets
`-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2`.

To reconstruct the current local source snapshot from clean llama.cpp:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
git checkout c926ad098
git apply /home/steve/qwen36-results-main/patches/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-reordervdr2-source.patch
```

This full-worktree patch is for recovery and review. It includes default-off
negative experiments as well as promoted paths, so do not enable every flag
blindly.

```bash
cd /home/steve/qwen36-results-main
scripts/build-llama-cpp-sycl-b70.sh
```

Default output:

```text
/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-server
/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-cli
/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-bench
```

For the current strict VDR=2 record build, use a dedicated build directory so
the default VDR=4 binary remains available for comparison:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh
cmake -S . -B build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -DCMAKE_CXX_FLAGS='-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2' \
  -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg-g31 \
  -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON -DGGML_SYCL_DNN=ON \
  -DGGML_SYCL_HOST_MEM_FALLBACK=ON
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 \
  --target llama-server -j 8
```

## 2. Download Q8 GGUF

```bash
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
scripts/run-gemma4-26b-first-baseline.sh
```

## Representative Realistic Final Gate Reproduction

The promoted record can be reproduced with:

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=1 PORT=18421 \
  FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Use this command for the current representative draft-MTP realistic-suite
candidate. It reproduces the VDR2 selected-down `n_max=3`, `n_min=2`,
`p_min=0.0475`, `UBATCH_SIZE=1024` family, whose current strict row is
`117.915 tok/s` on the fixed cold suite. The previous selected-down
`115.728`, prior `98.340`, F16-p021
`95.825`, VDR2 `90.983`, `90.322`, and VDR4 `87.611 tok/s` rows remain valid
evidence but are no longer the promoted headline.

```bash
cd /home/steve/qwen36-results-main
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server \
ONEAPI_DEVICE_SELECTOR=level_zero:1 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 \
GGML_SYCL_DISABLE_OPT=0 \
GGML_SYCL_DISABLE_GRAPH=0 \
GGML_SYCL_ENABLE_VMM=0 \
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
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1 \
LLAMA_SYCL_F16_P021_SMALL_NCOLS=1 \
GPU_INDEX=1 PORT=18421 \
CTX_SIZE=8192 BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 \
CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 FLASH_ATTN=off REASONING=off \
CANARY_REPEATS=32 MAX_TOKENS=512 \
REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf --spec-draft-n-max 3 --spec-draft-device SYCL0 --spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16 --spec-draft-n-min 2 --spec-draft-p-min 0.0475 --no-spec-draft-backend-sampling --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0' \
LABEL=gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-$(date -u +%Y%m%dT%H%M%SZ) \
scripts/run-gemma4-26b-first-baseline.sh
```

Use this no-spec control when testing target-side changes:

```bash
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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

For a copy-ready version of this historical diagnostic path, including the exact patch,
configuration, scripts, and copied result artifacts, start with
[`../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/`](../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md)
for the older superseded recipe. The current 176.216 tok/s recipe is the same
family plus direct argmax-ID unroll, q-only Gemma4Assistant attention inputs,
verifier backend argmax IDs, deferred target `h_nextn`, selected-softmax +
weighted-sum Gemma4 MoE source guards, route cache, fused assistant output
argmax, fused selected-softmax weights, RMS reuse, and the Q8 MoE-ID reorder
path plus reordered Q8_0 MMVQ VDR=2 compile knob that makes
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` viable for the UD-Q8_K_XL target.

```bash
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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
cd /home/steve/qwen36-results-main
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
