# 2026-07-01 Current Record Repeat 3 Plan

Status: complete. Valid variance/no-new-record. Do not submit.

## Goal

Run a clean four-GPU repeat of the current Gemma 4 26B A4B Q8 short-decode
record recipe before new source edits. This is useful because the current
record lane has known variance; a valid repeat can either produce a new
policy-compliant high or reinforce the current `~120-124 tok/s` envelope.

## Baseline To Beat

- Current valid headline: `123.67689864739785 tok/s` median generated-token
  throughput for tokens 1-100 after TTFT.
- Evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`.
- LocalMaxxing: `cmr01nnet000mld01x2tt6qds`.

## Run Identity

All lanes should use:

- llama.cpp source worktree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926` at upstream
  `c926ad098` with the local Gemma Q8 research stack;
- server binary:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`;
- target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, f16 KV;
- `n_max=3`, `n_min=2`, `p_min=0.0475`, `--ctx-checkpoints 0`,
  no draft backend sampling;
- promoted source flags:
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`;
- LM-head and accept-prefix experiment flags unset.

## Validity Gate

Promotion/submission requires:

- fixed realistic suite `realistic-suite-v1`;
- each prompt requested once, cold;
- `cached_tokens=0` for every request;
- canary pass;
- `realistic_final_gate.passed=true`;
- no prompt/KV/context/checkpoint/response/n-gram/history reuse;
- primary metric is median generated-token throughput for tokens 1-100 after
  TTFT, with p10, mean, TTFT, full512, wall tok/s, hashes, env, flags, and logs
  retained in each summary.

## Command Shape

```bash
cd /home/steve/qwen36-results-main
STAMP=$(date -u +%Y%m%dT%H%M%SZ)-record-repeat3
for gpu in 0 1 2 3; do
  port=$((18580 + gpu))
  GPU_INDEX=$gpu PORT=$port \
    FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
    LABEL=gemma4-q8-gpu${gpu}-current-record-repeat3-full512-${STAMP} \
    repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh &
done
wait
```

## Decision Rule

- If a lane beats `123.67689864739785 tok/s` and passes the gate, build the
  LocalMaxxing payload and submit after inspecting hashes, cached-token fields,
  model identity, and logs.
- If all lanes pass but do not beat the record, record as valid variance and do
  not submit.
- If any lane fails, preserve the failure path and classify it before changing
  source.

## Result

All four lanes completed and passed the fixed realistic final gate. Every
request reported `cached_tokens=0`, every lane passed canary `512/512`, and no
prompt/KV/context/checkpoint/response/n-gram/history reuse was used. No lane
beat the current `123.67689864739785 tok/s` headline.

Stamp: `20260701T020140Z-record-repeat3`.

| GPU | Summary | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT median ms | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | `data/gemma4-q8-gpu0-current-record-repeat3-full512-20260701T020140Z-record-repeat3/summary.json` | `121.9720691923804` | `107.91585671461549` | `119.60396409857934` | `111.90141645540325` | `107.44785470215634` | `179.43497747182846` | pass |
| 1 | `data/gemma4-q8-gpu1-current-record-repeat3-full512-20260701T020140Z-record-repeat3/summary.json` | `111.87547492588218` | `102.64705385796382` | `114.49132934429626` | `108.25128753891035` | `104.45265685845525` | `178.23999805841595` | pass |
| 2 | `data/gemma4-q8-gpu2-current-record-repeat3-full512-20260701T020140Z-record-repeat3/summary.json` | `118.23096116340783` | `107.85176152702706` | `117.15835938853828` | `109.62288727887523` | `105.44346954635072` | `177.94748302549124` | pass |
| 3 | `data/gemma4-q8-gpu3-current-record-repeat3-full512-20260701T020140Z-record-repeat3/summary.json` | `113.12239033658872` | `107.75217304154978` | `115.69482946857307` | `110.04449587473976` | `106.01191338954393` | `179.4105025473982` | pass |

Decision:

- valid fresh-response evidence;
- no LocalMaxxing submission because best lane `121.9720691923804` is below
  the current `123.67689864739785` record;
- reinforces that the current promoted recipe is a high-variance
  `~116-124 tok/s` lane, so future record work should come from a source
  mechanism rather than more repeat-only runs.
