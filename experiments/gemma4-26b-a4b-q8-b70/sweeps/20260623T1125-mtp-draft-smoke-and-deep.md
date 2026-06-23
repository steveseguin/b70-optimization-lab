# Gemma 4 Q8 Draft-MTP Smoke And Deep Run

Date: 2026-06-23
Owner/agent: Codex
GPU / port: four-way smoke on GPUs 0-3, promotion run on GPU 1 / port 18261

## Hypothesis

The no-spec sustained-decode best is memory-bandwidth limited at about 42.72
tok/s after TTFT. Gemma 4 ships a small MTP drafter GGUF; llama.cpp can verify
drafted tokens with the main Q8 model, so quality should remain equivalent to
plain greedy decode when canaries pass. The goal is to raise single-session
decode without lowering weight precision below Q8.

## Run Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main filename: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- main file bytes: `27,636,230,944`
- draft filename: `mtp-gemma-4-26B-A4B-it.gguf`
- draft file bytes: `461,766,816`
- model revision: `3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`
- runtime: llama.cpp server
- runtime commit/version: `dec5ca557`
- backend: SYCL / Level Zero
- context: `8192`
- batch / ubatch: `512 / 64`
- KV cache dtype: main `f16/f16`, draft `f16/f16`
- API mode: `/v1/chat/completions`
- seed: `1`
- common env:
  - `GGML_SYCL_DISABLE_OPT=0`
  - `FLASH_ATTN=off`
  - `REASONING=off`
  - `POLL=50`
- common extra args:
  - `--parallel 1 --cache-ram 0`
  - `--spec-type draft-mtp`
  - `--spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf`
  - `--spec-draft-device SYCL0 --spec-draft-ngl all`
  - `--spec-draft-type-k f16 --spec-draft-type-v f16`

## Four-Way Smoke

All four smoke runs used `CANARY_REPEATS=16` (`64/64` chat canary rows) and
`BENCH_REPEATS=3` with `BENCH_PROMPT_MODE=long` (actual `75` prompt tokens and
`512` output tokens).

| Label | GPU | Draft n-max | Canary | Tok/s after TTFT | Wall tok/s | MTP acceptance | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-mtp-n2-long-smoke-20260623T1125` | 0 | 2 | 64/64 | 45.4235 | 43.8310 | len `2.45`; rates `(0.792, 0.654)` | win over no-spec, close to n=4 |
| `gemma4-q8-gpu1-mtp-n4-long-smoke-20260623T1125` | 1 | 4 | 64/64 | 45.5175 | 43.9124 | len `3.41`; rates `(0.812, 0.641, 0.549, 0.413)` | best smoke, promote |
| `gemma4-q8-gpu2-mtp-n6-long-smoke-20260623T1125` | 2 | 6 | 64/64 | 38.4094 | 37.2702 | len `3.60`; rates `(0.776, 0.578, 0.468, 0.331, 0.240, 0.204)` | loss; draft overhead dominates |
| `gemma4-q8-gpu3-mtp-n8-long-smoke-20260623T1125` | 3 | 8 | 64/64 | 24.0879 | 23.6332 | len `3.91`; rates `(0.779, 0.573, 0.479, 0.315, 0.236, 0.212, 0.174, 0.138)` | loss; too much speculation |

The previous queue note that "MTP smokes were slower" is superseded. That was
true for an earlier speculative setup, but with the current `draft-mtp` flags
and draft GGUF, `n=2` and `n=4` beat the no-spec sustained-decode record.

## Promotion Run

Command:

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

- chat canary: **384/384 pass**
- prompt/output shape: actual `75` prompt tokens, `512` output tokens
- output tok/s after TTFT: **44.499975**
- wall output tok/s: **43.027413**
- TTFT: **392.962 ms**
- after-TTFT repeat range: `42.421963` to `47.601285` tok/s
- CV after TTFT: `0.03637`
- MTP acceptance: average accepted length `3.63`, rates
  `(0.839, 0.702, 0.602, 0.482)`, accepted/generated draft tokens
  `6228/9466`

Decision: valid new sustained-decode best for the Q8 single-B70 lane. It beats
the previous approved sustained-decode record (`42.716267799445156` tok/s) by
about `4.18%`, while keeping Q8 weights, f16 KV, chat mode, and the same
promotion-depth canary. Submitted to LocalMaxxing and approved as
`cmqqblfw30132qo01jbi1svnu`.

## Artifacts

- smoke summaries:
  - `data/gemma4-q8-gpu0-mtp-n2-long-smoke-20260623T1125/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n4-long-smoke-20260623T1125/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n6-long-smoke-20260623T1125/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n8-long-smoke-20260623T1125/summary.json`
- promoted summary:
  - `data/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140/summary.json`
- benchmark JSON:
  - `data/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140/p512o512.json`
- canary JSON:
  - `data/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140/chat-canary.json`
- server log:
  - `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140.server.log`
- LocalMaxxing queue:
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n4-long512-20260623.queue.json`
- LocalMaxxing response:
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n4-long512-20260623.submit.log`

## Follow-Up

Next four-way search should stay near the n=4 optimum instead of pushing much
higher. Candidate axes:

- `n=3`, to see whether a lower draft budget keeps the speed win with lower CV.
- `n=4` plus `POLL=100`, because earlier no-spec sweeps showed polling can move
  wall throughput and TTFT.
- `n=4` plus `BATCH_SIZE=1024`, because AOT and batch changes have not yet been
  retested with draft-MTP.
- `n=4` plus llama.cpp speculative acceptance knobs if available (`p-min`,
  `p-split`, or equivalent), after confirming exact current flag names.

External references checked during this lane:

- Unsloth MTP guide: <https://unsloth.ai/docs/models/mtp>
- llama.cpp Gemma 4 MTP performance issue #24266:
  <https://github.com/ggml-org/llama.cpp/issues/24266>
- llama.cpp B70 optimized-kernel corruption issue #21893:
  <https://github.com/ggml-org/llama.cpp/issues/21893>
