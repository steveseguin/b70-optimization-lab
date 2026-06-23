# Reproduce Gemma 4 26B A4B Q8 Baseline

These commands set up the first llama.cpp/SYCL baseline. They do not delete any
Qwen models or modify the dirty Qwen vLLM source tree.

## 1. Build llama.cpp with SYCL

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

Validated conservative baseline:

```text
label: gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z
canary: 128/128 chat rows pass
p512/o512: 26.10 tok/s after TTFT, 24.24 tok/s wall
summary: data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z.server.log
```

Current valid best:

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

Current filled-long draft-MTP sustained-decode best:

```bash
cd /home/steve/qwen36-results-main
LLAMA_SERVER=/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server \
GPU_INDEX=3 PORT=18303 LABEL=gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-filled-long-deep-20260623T093619Z \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.10 MTP_BACKEND_SAMPLING=0 BENCH_PROMPT_MODE=filled-long \
scripts/run-gemma4-26b-mtp-candidate.sh
```

Result:

```text
canary: 384/384 chat rows pass
actual benchmark shape: 588 prompt tokens, 512 output tokens
tok/s: 90.24 after TTFT, 82.24 warmed wall
LocalMaxxing: cmqqgftv50160qo01km3s7lkt
summary: data/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-filled-long-deep-20260623T093619Z/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-filled-long-deep-20260623T093619Z.server.log
```

Short wrapper equivalent for future sweeps:

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=1 PORT=18261 LABEL=gemma4-q8-gpu1-mtp-n3-long-deep-<stamp> \
MTP_N_MAX=3 scripts/run-gemma4-26b-mtp-candidate.sh
```

Useful safe MTP sweep knobs:

```bash
MTP_N_MAX=3
MTP_N_MAX=5 MTP_N_MIN=2 MTP_P_MIN=0.15
MTP_N_MAX=6 MTP_N_MIN=2 MTP_P_MIN=0.25
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.10 MTP_BACKEND_SAMPLING=0
POLL=100 MTP_N_MAX=4
LLAMA_CACHE_RAM=1 MTP_N_MAX=3
LLAMA_PARALLEL=2 MTP_N_MAX=3
```

For future sustained-decode comparisons, prefer
`BENCH_PROMPT_MODE=filled-long` if the target is an actual near-512-token input
plus 512-token output. The older `long` mode is intentionally retained so the
published 75/512 record remains reproducible; do not mix the two shapes when
deciding whether a run broke a record.

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
