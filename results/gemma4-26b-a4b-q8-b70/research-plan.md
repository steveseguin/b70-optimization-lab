# Gemma 4 26B A4B Q8 B70 Research Plan

Research snapshot: 2026-06-23. Goal: maximize valid single-session decode for
one complete Q8/INT8-quality Gemma 4 26B A4B replica per B70, then run four
replicas on four GPUs for parallel research and aggregate service capacity.

## Non-Negotiables

- Default precision is Q8 / INT8-or-better. Lower precision can be a diagnostic
  side result, but not a promoted result in this lane.
- Validate chat mode first. Raw `/v1/completions` is useful as a diagnostic, but
  the instruction-tuned deployment path is `/v1/chat/completions`.
- No tensor-parallel split in the primary lane. The design is one full model per
  GPU to avoid PCIe collectives.
- `GGML_SYCL_DISABLE_OPT=0` is now the promoted speed lane after repeated
  384-row chat canaries. Keep promotion-depth canaries for every new optimized
  SYCL variant because upstream B70/Gemma corruption reports still make this a
  risky family.
- Do not promote from a smoke. Use 32-repeat early canaries and 96+ repeats
  before any record or LocalMaxxing submission.

## Phase 1: First Valid Q8 llama.cpp Baseline

Status: **completed for the conservative llama.cpp control**.

Fast path wrapper:

```bash
cd /home/steve/qwen36-results-main
scripts/run-gemma4-26b-first-baseline.sh
```

Manual equivalent:

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 UBATCH_SIZE=64 \
  scripts/run-gemma4-26b-llamacpp-replica.sh
```

Gate:

```bash
python3 scripts/gemma4-text-canary.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --api-mode chat \
  --repeats 32 \
  --out data/gemma4-26b-a4b-q8-b70-chat-canary-32.json

python3 scripts/bench-openai-single-decode.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --api-mode chat \
  --prompt-tokens 512 \
  --max-tokens 512 \
  --repeats 8 \
  --out data/gemma4-26b-a4b-q8-b70-p512o512-chat-baseline.json
```

If 8K does not fit, retry `CTX_SIZE=4096`, then `2048`, without changing weight
or KV precision. Only after a valid baseline should q8 KV be tried.

Baseline result:

- run label: `gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z`;
- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, `level_zero:0`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`, exact file size
  `27,636,230,944` bytes;
- flags: `CTX_SIZE=8192`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`, `-fa on`,
  `CACHE_TYPE_K=f16`, `CACHE_TYPE_V=f16`, `POLL=50`,
  `GGML_SYCL_DISABLE_OPT=1`, `REASONING=off`;
- quality: chat canary **128/128 pass**;
- speed: p512/o512 chat decode **26.10 tok/s after TTFT**, **24.24 tok/s
  wall**, CV after TTFT `0.00028`.

Decision: valid baseline, not a speed win. The immediate research value is that
Q8 fits and the chat template is stable with `REASONING=off`; use this as the
control for parallel sweeps.

Current valid best:

- run label: `gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915`;
- change: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `--parallel 1 --cache-ram 0`, `THREADS=16`;
- quality: chat canary **384/384 pass**;
- speed: **42.15 tok/s after TTFT**, **36.41 tok/s wall**;
- caveat: this flag had upstream B70/Gemma corruption reports, so every
  optimized-SYCL variant needs promotion-depth canaries before promotion.

Follow-up: `syclopt0 + POLL=100` was a validated alternative with better TTFT
and wall throughput but lower after-TTFT decode (`40.69 tok/s`). MTP n=2/4/8
was slower than no-spec in first smokes and should not be promoted.

Previous no-spec sustained-decode best:

- run label: `gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945`;
- change from promoted natural-stop best: `BENCH_PROMPT_MODE=long` to force the
  model to emit the full `MAX_TOKENS=512` budget;
- actual benchmark shape: about `75` prompt tokens and exactly `512` output
  tokens on all repeats;
- quality: chat canary **384/384 pass**;
- speed: **42.72 tok/s after TTFT**, **41.35 tok/s wall**;
- decision: valid no-spec sustained-decode record, but keep it separate from the
  natural-stop/default-prompt 42.15 tok/s result.

Current short-prompt sustained-decode best:

- run label: `gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353`;
- change from no-spec sustained-decode best: official Gemma MTP draft GGUF via
  `--spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-ngl all`, with draft
  KV `f16/f16`, on the BMG AOT llama.cpp build;
- actual benchmark shape: `75` prompt tokens and exactly `512` output tokens on
  all repeats;
- quality: chat canary **384/384 pass**;
- speed: **48.35 tok/s after TTFT**, **46.60 tok/s wall**;
- decision: valid short-prompt sustained-decode record. `n=2` was also a win;
  `n=5` and `n=6` with confidence gating were losses on the short 75-token
  prompt, so short-prompt work should tune around `n=2/3`.

Current filled-long sustained-decode best:

- run label: `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-20260623T094131Z`;
- change from prior filled-long best: keep MTP depth at `--spec-draft-n-max 7`,
  confidence gate at `--spec-draft-p-min 0.10`, and draft backend sampling
  disabled, but add `--spec-draft-threads 32`;
- actual benchmark shape: `588` prompt tokens and exactly `512` output tokens
  on all repeats;
- quality: chat canary **384/384 pass**;
- speed: **90.42 tok/s after TTFT**, **82.34 tok/s warmed wall**;
- LocalMaxxing: approved as `cmqqgn3cm0163qo010optg91u`;
- decision: current valid best for the Gemma 4 26B A4B Q8 one-B70 lane. Future
  record attempts should use `filled-long` unless intentionally reproducing a
  short-prompt record.

Near-neighbor follow-ups now in progress / next in queue:

- repeat the draft-threads-32 record to measure reproducibility: completed at
  `90.26 tok/s`, below the `90.42` record but close enough to confirm the
  result family;
- draft-only `V` cache `q8_0`: attempted with `FLASH_ATTN=off`, but llama.cpp
  logged `V cache quantization requires flash_attn`; result fell back near
  no-spec speed and is not a true q8_0-cache benchmark;
- draft `K/V` cache `q8_0`: same invalid/fallback condition as above; retest
  only with `FLASH_ATTN=on`;
- `BATCH_SIZE=1024`: completed at `90.20 tok/s`, valid but below record;
- `THREADS=32`: completed at `90.12 tok/s`, valid but below record;
- `MTP_DRAFT_THREADS_BATCH=32`: completed at `90.31 tok/s`, valid and closest
  in that sweep but below record;
- `POLL=75`: completed at `90.02 tok/s`, valid but below record;
- `FLASH_ATTN=on`: completed at `90.08 tok/s`, valid but below record. Keep it
  only for q8_0-cache retests that require FA-on.
- `MTP_P_MIN` refinement with draft threads 32: repeat `0.10` completed at
  `90.20 tok/s`, `0.11` at `89.55`, `0.12` at `90.08`, and `0.13` at
  `90.33`; all valid, all below the `90.42` record.
- `MTP_DRAFT_THREADS` sweep: `24` completed at `90.30 tok/s`, `32` repeat at
  `90.23`, `48` at `89.67`, and `64` at `89.96`; all valid, all below record.
- active next queue: combine the closest non-winning runtime interaction,
  `MTP_DRAFT_THREADS_BATCH=32`, with the p-min neighborhood: `0.10` repeat,
  `0.11`, `0.12`, and `0.13`.

The `filled-long` prompt mode records prompt hash/preview and usage-derived
prompt/completion-token stats. Use it for near-512-input / 512-output
comparisons. Keep the older `long` mode only for reproducing the published
75/512 short-prompt records.

## Phase 2: Four Replica Baseline

Next step. One GPU is valid, so launch all four independent replicas:

```bash
cd /home/steve/qwen36-results-main
CTX_SIZE=8192 UBATCH_SIZE=64 scripts/run-gemma4-26b-llamacpp-quad.sh
```

Measure each port independently first. Aggregate throughput is only meaningful
after each server passes the same chat canary.

Ports:

```text
18260 -> GPU 0
18261 -> GPU 1
18262 -> GPU 2
18263 -> GPU 3
```

## Phase 3: No-Spec Speed Sweeps

Run one control plus three experiments in parallel:

| GPU | Purpose | First sweep |
| --- | --- | --- |
| 0 | Control | `-fa on`, f16 KV, `CTX_SIZE=8192`, `UBATCH_SIZE=64`, `REASONING=off`, `GGML_SYCL_DISABLE_OPT=1` |
| 1 | Batch/ubatch | `UBATCH_SIZE=128/256/512`, then `BATCH_SIZE=1024/2048` |
| 2 | SYCL runtime flags | `GGML_SYCL_DISABLE_GRAPH=1`, `GGML_SYCL_DISABLE_DNN=1`, then combinations |
| 3 | Risky speed flag | `GGML_SYCL_DISABLE_OPT=0` only with immediate 32-repeat chat canary |

Other follow-up axes:

- AOT build with `GGML_SYCL_DEVICE_ARCH=intel_gpu_bmg_g31`.
- `POLL=25/50/100`, because older Qwen GGUF work found polling can move B70
  decode latency.
- `-fa off` as a correctness/perf control. Keep `-fa on` as default.
- `CACHE_TYPE_K=q8_0 CACHE_TYPE_V=q8_0` only after f16 KV has a valid baseline.
  This may be needed for 32K headroom, but it is a quality-impacting change
  until canaries and practical prompts pass.
- `--no-mmap` / `--mlock` only if load-time paging or first-token stalls show up
  in logs.

Promotion criteria for a speed sweep:

- chat canary 32/32 for smoke, 96+ for promotion;
- no known lower-precision change unless labeled separately;
- benchmark JSON has non-null `usage.completion_tokens` and output tok/s;
- server log captures the exact launcher identity.

## Four-At-A-Time Research Loop

Once a single replica can pass the 32-repeat chat smoke, use all four B70s to
run independent experiments instead of serially hand-tuning one GPU:

| GPU | Lane | First pass | Promotion condition |
| --- | --- | --- | --- |
| 0 | Conservative control | `CTX_SIZE=8192`, f16 KV, `UBATCH_SIZE=64`, `GGML_SYCL_DISABLE_OPT=1` | Baseline canaries and metrics continue to reproduce. |
| 1 | Memory / scheduling | `UBATCH_SIZE=128/256/512`, `BATCH_SIZE=1024/2048`, `POLL=25/50/100` | Same canary pass, higher p512/o512 output tok/s. |
| 2 | Runtime flags / build | `GGML_SYCL_DISABLE_GRAPH`, `GGML_SYCL_DISABLE_DNN`, AOT BMG build | Same canary pass, lower decode ms/token. |
| 3 | Alternate runtime | vLLM int8-per-channel DP=1, or MTP after no-spec baseline | Valid quality and a clear reason to displace llama.cpp Q8. |

Keep each lane's summary under `experiments/gemma4-26b-a4b-q8-b70/sweeps/` or
`data/` with the server log path. Failed lanes are useful; record the exact
failure signature instead of deleting the attempt.

Use the sweep template at
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/README.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/README.md)
for each meaningful lane.

## Carryover Tactics From Earlier Wins

- **Identity lock first.** Before interpreting a speed delta, diff model file,
  revision, quantization, runtime commit, context, KV dtype, prompt/output
  shape, launch flags, and server logs against the last known-good run.
- **Promote only after repeat depth.** Qwen graph smokes passed and later failed
  at full repeat depth; Gemma promotions need 96+ repeats if the runtime path is
  novel or has any prior nondeterminism.
- **Use exact canaries before broad quality.** JSON, sort/color, arithmetic, and
  code canaries catch runtime corruption faster than open-ended chats.
- **Do not weaken quality for speed.** Q6/Q4/MXFP4/NVFP4 are allowed only as
  labeled side results; the primary lane stays Q8/INT8-or-better.
- **Preserve negative results.** Failed patches, bad launcher flags, and
  corrupted outputs belong in notes or sweep summaries with enough identity to
  prevent rediscovery.

## Phase 4: MTP / Speculative Decode

Status: **active; filled-long `n=7, n-min=2, p-min=0.10` with draft backend
sampling disabled is the current sustained-decode best**.

Google's MTP overview warns that MoE models at batch size 1 may have limited
speedup because each MTP token can activate different experts, which reduces
expert-weight locality. That warning held for the short-prompt `75/512` shape,
where `n=5/6` lost and `n=2/3` was the useful zone. The filled-long `588/512`
shape behaves differently: deeper draft budgets are useful, and the current
winner is gated `n=7`.

When ready, download the draft file:

```bash
FILENAME=mtp-gemma-4-26B-A4B-it.gguf \
EXPECTED_BYTES=461766816 \
scripts/download-gemma4-26b-q8-gguf.sh
```

Promoted MTP server shape for current filled-long record:

```bash
LLAMA_SERVER=/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server \
GPU_INDEX=3 PORT=18303 LABEL=gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-<stamp> \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.10 MTP_BACKEND_SAMPLING=0 MTP_DRAFT_THREADS=32 BENCH_PROMPT_MODE=filled-long \
scripts/run-gemma4-26b-mtp-candidate.sh
```

The MTP wrapper fixes the Q8/f16 quality lane and forwards MTP knobs to
`EXTRA_LLAMA_ARGS`. Already tested `--spec-draft-n-max 2/3/4/6/8` on the
short-prompt shape, plus confidence-gated `n=5` and `n=6`; higher n lost there.
On filled-long, `n=4` beat `n=2/3`, `n=5` improved again, `n=6` reached the
low-80s, and `n=7, n-min=2` is the current frontier. `p-min=0.10` slightly beat
`0.15`; `n=8, p-min=0.15` was a large loss. Disabling draft backend sampling
was the next clear win (`90.24 tok/s`), and `--spec-draft-threads 32` improved
that to `90.42 tok/s`. Current follow-up should keep backend sampling off and
sweep draft KV, batch/ubatch, polling, and record reproducibility before
changing model files.

## Phase 5: vLLM Int8 Per-Channel Comparison

Use only after llama.cpp Q8 has a validated baseline or if llama.cpp cannot
serve the model reliably.

Initial shape:

```bash
ZE_AFFINITY_MASK=0 \
vllm serve google/gemma-4-26B-A4B-it \
  --quantization int8_per_channel_weight_only \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --no-enable-prefix-caching \
  --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
  --port 18270
```

Run four separate DP=1 servers for 4 GPU work. Do not use vLLM
`--data-parallel-size 4` until the public MoE DP issue is resolved or locally
patched.

## Phase 6: Multimodal Smoke

Text speed is first. After text baseline:

1. Download `mmproj-F16.gguf`.
2. Launch one server with `--mmproj`.
3. Run a single image smoke for correctness only.
4. Do not mix multimodal tokens into text throughput records.

## Current Best Hypotheses

1. **Single-GPU Q8 llama.cpp is viable at 8K, but the conservative baseline is
   slow.** The validated control is ~26 tok/s after TTFT; optimize before any
   LocalMaxxing submission.
2. **AOT and ubatch sweeps are the likely early speed wins.** They preserve
   quality and avoid the risk of MTP correctness bugs.
3. **`GGML_SYCL_DISABLE_OPT=0` may be faster but is high-risk.** Only test it
   behind repeated canaries because upstream reports B70/Gemma 4 nonsense
   output without the disable flag.
4. **q8 KV may unlock 32K but is not quality-neutral by default.** Treat it like
   a new precision mode.
5. **MTP could help, but may disappoint at batch 1 for MoE.** It becomes worth
   testing after no-spec baseline because the draft files are small.
6. **vLLM int8-per-channel is the main fallback if llama.cpp is slow.** It may
   use B70/XPU kernels better, but vLLM DP must be four independent servers.
7. **The public LocalMaxxing target is around 90-95 tok/s but mixed precision.**
   Treat that as directional pressure, not a direct Q8 B70 failure threshold.
8. **The biggest early risk is correctness, not launch throughput.** The B70
   Gemma SYCL corruption report makes repeat canaries mandatory before touching
   `GGML_SYCL_DISABLE_OPT=0` or promoting any graph/spec path.
9. **Disable thinking for speed baselines.** llama.cpp auto-detected Gemma
   thinking and returned empty `message.content` for exact-answer canaries.
   Default this lane to `REASONING=off`; thinking-enabled throughput is a
   separate product mode.
10. **Separate benchmark shapes.** The default prompt often stops around
    140-160 output tokens; `long` reaches 512 output tokens with a short input;
    `filled-long` should be used when testing a real near-512-token input.
    Do not compare these shapes without labeling the input/output tokens.

## Stop Conditions

- If Q8 GGUF cannot fit even at 2K with f16 KV, test Q8_0 before lowering to
  Q6.
- If `GGML_SYCL_DISABLE_OPT=0` fails any canary, stop using it until the
  upstream corruption cause is understood.
- If MTP speed wins but canaries fail at repeat depth, mark it invalid and
  preserve the logs; do not chase speed-only LocalMaxxing submissions.
- If all llama.cpp Q8 paths are valid but slow, switch to vLLM int8-per-channel
  rather than weakening quality.
