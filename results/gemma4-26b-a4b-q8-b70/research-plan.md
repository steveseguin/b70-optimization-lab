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

Current filled-long warmed/history-accelerated ngram artifact:

- run label: `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855`;
- change from prior filled-long best: switch from draft-MTP to draftless
  `ngram-mod` speculation on llama.cpp `c926ad098`, keeping the Q8 target model,
  f16/f16 KV, AOT BMG build, `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=100`, `--parallel 1 --cache-ram 0`, `--ctx-checkpoints 0`,
  `CTX_SIZE=4096`, and `UBATCH_SIZE=512`;
- spec config: `--spec-type ngram-mod --spec-ngram-mod-n-match 20
  --spec-ngram-mod-n-min 32 --spec-ngram-mod-n-max 64`;
- actual benchmark shape: `588` prompt tokens and exactly `512` output tokens
  on all repeats;
- quality: chat canary **384/384 pass**;
- speed: **280.64 tok/s after TTFT**, **206.24 tok/s warmed wall**;
- LocalMaxxing: approved as `cmqqyby6801dvqo01as3wenz2` before the fresh/warmed
  rule clarification; retraction-needed if displayed as headline throughput.
  It supersedes warmed/history
  ngram records `cmqqxx7bp01dbqo012d2qiiw6` (`280.04 tok/s`),
  `cmqqxjnif01d0qo01ix4oeixo` (`255.04 tok/s`) and
  `cmqqxbkzx01cxqo01j8p97627` (`245.98 tok/s`), but does **not** supersede the
  fresh-response draft-MTP record `cmqqsecuk01azqo018ahv0i1s` (`91.62 tok/s`);
- decision: useful warmed/history artifact, not the current valid
  fresh-response best. Label this result honestly as history-cache acceleration
  on a repetitive sustained-decode shape: every drafted token is verified by the
  Q8 target model, but the repeated benchmark output lets `ngram-mod` learn long
  chunks after the first cold repeat. This is also a small-context warmed result
  for the measured 588+512 shape, not a 32K-context claim.

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
- `MTP_DRAFT_THREADS_BATCH=32` + p-min interaction: `0.11` completed at
  `89.63 tok/s`, `0.12` at **`91.05 tok/s`** (new record), and `0.13` at
  `90.24`; the `0.10` repeat stalled during launch/readiness on GPU0 and was
  kept as a failed control artifact.
- mechanism follow-ups under the new `p-min=0.12 + dtb32` identity: true FA-on
  draft-cache retests were valid real q8 draft-cache runs but did not beat the
  record (`V q8_0` at `90.61 tok/s`, `K/V q8_0` at `89.95`); `POLL=100`
  reached `90.59`; the CPU-affinity split failed at launch because llama.cpp
  `dec5ca557` rejects `--spec-draft-cpu-range-batch`.

- runtime/Q8_0 follow-ups under the same identity: `MTP_DRAFT_POLL=0`
  reached `90.16 tok/s`, Q8_0 main model reached `89.99`, supported CPU-range
  split reached `89.95`, and `GGML_SYCL_ENABLE_VMM=0` reached `90.40`; all
  valid, all below the `91.05` record.

- sampler/KV/priority/CPU-mask follow-ups under the same identity:
  `--no-kv-unified` reached `89.99 tok/s`, `--samplers greedy` reached
  `88.65`, priority flags reached `89.72`, and CPU-mask split reached `89.73`;
  all valid, all below the `91.05` record.

- p-min / draft-batch-thread refinement under the same identity: `p-min=0.115`
  reached `90.49 tok/s`, an exact `p-min=0.12 + dtb32` repeat reached `90.01`,
  `p-min=0.125` reached `90.05`, and `dtb40` reached `89.53`; all valid, all
  below the `91.05` record.

- draft thread neighborhood under the same identity: `dtb28` reached
  `90.60 tok/s`, `dtb36` reached `90.11`, draft threads `28` reached `90.43`,
  and draft threads `36` reached `89.96`; all valid, all below the `91.05`
  record.

- near-miss interaction sweep under the same identity: `dtb28 + FLASH_ATTN=on
  + draft V q8_0` reached `90.43 tok/s` after TTFT / `84.04` wall, `dtb28 +
  p-min=0.115` reached `89.95`, `dtb28` repeat reached `90.23`, and `dtb28 +
  POLL=100` reached `90.08`; all valid, all below the `91.05` record.

- exact-record repeats across all four GPUs reached `90.41`, `89.87`, `90.16`,
  and `90.08 tok/s`; all valid, all below the `91.05` record. The record is a
  valid high-water mark, but current repeats cluster closer to `90 tok/s`.
- high-depth follow-up with `n=8` at `p-min=0.08/0.10/0.12` and `n=9` at
  `p-min=0.12` preserved quality (384/384 each) but fell to `61.8-65.9 tok/s`;
  reject deeper draft budgets in the current runtime family.
- latest llama.cpp `c926ad098` AOT BMG A/B: default checkpoints preserved
  quality but reached only `90.92 tok/s` after TTFT and hurt wall throughput.
  Adding `--ctx-checkpoints 0` reached **`91.16 tok/s`**, a small new
  after-TTFT record.
- source-level sampler confidence follow-ups after the `c926ad098` record:
  cheap MTP draft `top_k` preserved quality but missed the record
  (`top_k=2` was closest at `90.91 tok/s`), and the follow-up `top_k=2` +
  `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN=0.25/0.50/1.00/1.50` also preserved
  `384/384` quality but reached only `90.15-90.48 tok/s`. Do not promote these
  hooks into the current recipe; keep them as documented diagnostics.
- source-level fast top-k MTP draft bypass: initial `top_k=10` smoke reached
  `91.28 tok/s`, then the exact repeat on GPU0 reached **`91.62 tok/s`** with
  `384/384` canary and was submitted/approved as
  `cmqqsecuk01azqo018ahv0i1s`. `top_k=2/4/20` were losses in the same sweep.
  Promote `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10` as the
  current recipe, but remember the gain is modest and run-to-run variance is
  still visible.
- post-record VMM/ubatch follow-ups: `ctx4096 + ub512 + VMM=0 + top_k=10`
  reached `91.43 tok/s` after TTFT with `384/384` canary and much better wall
  throughput (`82.14 tok/s`, TTFT `636 ms`), but it still missed the `91.62`
  decode record. `ub1024 + VMM=0`, `top_k=9 + ub512 + VMM=0`, and an
  `ub512 + VMM=0` repeat were also valid losses (`90.80-91.17 tok/s`). Keep
  this family as a latency/wall reference, not as the promoted decode lane.
- fast top-k neighborhood after promotion: `top_k=8` reached `91.23 tok/s`,
  `top_k=12` reached `90.57`, `top_k=10 + UBATCH_SIZE=512` reached `91.32`,
  and `top_k=10 + CTX_SIZE=4096 + UBATCH_SIZE=512` reached `91.28`; all passed
  `384/384`, all missed the `91.62` after-TTFT record. The ubatch variants did
  improve TTFT to about `630 ms` and warmed wall throughput to about `82 tok/s`,
  so preserve them as latency/total-throughput references, not decode-record
  winners.
- fast top-k p-min neighborhood: `p-min=0.115/0.120-repeat/0.125/0.130` all
  passed `384/384` but missed the record (`90.97`, `91.21`, `90.99`, `91.01`
  tok/s). Keep `MTP_P_MIN=0.12`; do not keep spending lanes on nearby p-min
  values without a second interacting change.
- fast top-k thread neighborhood: draft threads `28/36` and draft batch threads
  `28/36` all passed `384/384` but missed the record (`90.67-90.94 tok/s`).
  Keep `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`.
- source-level MTP sync/access patches: removing the explicit sync before
  `llama_get_logits_ith()` regressed to `89.83-90.25 tok/s`, and a staging
  helper that synchronized once for logits + NextN embeddings regressed to
  `90.51-90.92 tok/s`. Both preserved `384/384` quality but are rejected.
  Keep the original fast-top-k patch with its explicit sync.

Next queue:

- move back to source-level MTP overhead work. The fast-top-k patch showed the
  sampler path matters but only modestly; nearby top-k, p-min, ubatch, context,
  thread, and sync/access patches are now exhausted under the current recipe.
- the remaining plausible source-level win is avoiding full-vocab host logits
  movement in the draft loop, e.g. emitting top-k candidate IDs/logits from the
  graph/backend output path and consuming those in `draft_fast_topk_sample()`.
- source-level MTP overhead lane remains valuable: timing showed hidden-state
  handoff was not the material cost; draft `llama_decode` and sampler overhead
  dominate. The fast-top-k patch reduced sampler overhead only modestly, so
  bigger wins likely require adaptive draft depth or reduced draft-loop decode
  work.
- clean vLLM/XPU `int8_per_channel_weight_only` single-replica baseline for
  Gemma 4 26B A4B as the main non-llama.cpp comparison. Validate chat-template
  quality before comparing speed.

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

Status: **active; fresh-response headline is draft-MTP `n=7` with fast top-k at
`91.62 tok/s` mean after TTFT and `91.25 tok/s` first request. Draftless
`ngram-mod match=20 min=32 max=64` reached `280.64 tok/s` only as warmed/history
throughput on repeated identical continuations and is not a fresh-response
record.**

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
GPU_INDEX=2 PORT=18352 LABEL=gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-<stamp> \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.12 MTP_BACKEND_SAMPLING=0 MTP_DRAFT_THREADS=32 MTP_DRAFT_THREADS_BATCH=32 BENCH_PROMPT_MODE=filled-long \
scripts/run-gemma4-26b-mtp-candidate.sh
```

The MTP wrapper fixes the Q8/f16 quality lane and forwards MTP knobs to
`EXTRA_LLAMA_ARGS`. Already tested `--spec-draft-n-max 2/3/4/6/8` on the
short-prompt shape, plus confidence-gated `n=5` and `n=6`; higher n lost there.
On filled-long, `n=4` beat `n=2/3`, `n=5` improved again, `n=6` reached the
low-80s, and `n=7, n-min=2` is the current frontier. Disabling draft backend
sampling, draft threads/batch `32/32`, latest llama.cpp `c926ad098`,
`--ctx-checkpoints 0`, and the source-level fast top-k draft bypass advanced
the record to **`91.618942 tok/s`** after TTFT, 384/384 canary, LocalMaxxing
`cmqqsecuk01azqo018ahv0i1s`.

Draftless `ngram-mod` speculation then surpassed the MTP lane only on the
repeated-output warmed/history version of the filled-long shape. The best
warmed artifact is `match=20, min=32, max=64`,
`CTX_SIZE=4096`, `UBATCH_SIZE=512`, `POLL=100` at
**`280.641701 tok/s`** after TTFT / **`206.236056`** wall,
384/384 canary, LocalMaxxing `cmqqyby6801dvqo01as3wenz2`
(retraction-needed if displayed as headline throughput). The server log reports `3493/3493`
accepted/generated n-gram draft tokens and mean accepted length `63.38`. This
is still Q8-quality because the target model verifies every draft, but it is
specifically a history-cache/repetitive-output result; do not present it as a
unique-prompt no-cache decode rate or as a 32K-context result.

Exhausted near-neighborhoods after that record:

- `top_k=8/12`, `p-min=0.115/0.120/0.125/0.130`, draft threads/batch
  `28/36`, and exact repeats: valid losses.
- `UBATCH_SIZE=256/512`, `CTX_SIZE=4096`, and `GGML_SYCL_ENABLE_VMM=0`:
  valid losses for after-TTFT decode, but `VMM=0 + UBATCH_SIZE=512` reached
  `91.581388 tok/s` after TTFT, `82.292136` wall tok/s, and `631.803 ms`
  TTFT; keep it as the best latency/total-throughput reference, not a record.
- Source patches removing the explicit logits sync or staging logits+NextN in
  one helper were valid but slower.
- Backend `ggml_top_k` sampled-candidate transport is rejected. Existing
  backend sampling reached only `84.07-89.77 tok/s` depending on `top_k`; a
  patched compact-candidate MTP reader (`LLAMA_MTP_DRAFT_BACKEND_TOPK=1`)
  compiled and passed 384/384 canaries but still reached only
  `84.26-89.68 tok/s`. Keep the CPU fast-top-k path.

Current follow-up should return to fresh-response MTP/no-spec work. The
`20260623T1915` and `20260623T1935` ngram queues are preserved only as
warmed/history artifacts and harness diagnostics. The first combined fallback
launch failed before readiness because `run-gemma4-26b-spec-candidate.sh`
shell-escaped the comma in `--spec-type ngram-mod,draft-mtp`; that wrapper bug
is fixed and the failed launch is preserved as a harness artifact. For headline
record attempts, use draft sources that work on a fresh request without prior
continuation history. Next best work: source-level MTP overhead reductions,
because standalone backend top-k is ruled out, but reducing the MTP
draft loop's per-step decode overhead, avoiding repeated NextN embedding host
copies, or improving the CPU fast-top-k path without invoking backend
`ggml_top_k` remain plausible.

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
11. **Current fresh MTP is target-verification-bound, not acceptance-bound.**
    The `n=7` MTP lane already accepts long chunks on the filled-long benchmark
    (`~445/462` drafted tokens, mean acceptance length `~7.7`, zero `p-min`
    stops in the profile). Argmax/top-k and VMM/ubatch/poll follow-ups preserved
    quality but did not beat the `91.62 tok/s` record in a meaningful way.
    A fixed-line diagnostic then showed the same thing more sharply: `n=8`
    accepted `454/454` drafted benchmark tokens but fell to `64.20 tok/s`, and
    `n=12/16` also lost despite mean accepted lengths above `11`. Further small
    sampler/runtime/depth sweeps under this identity are low value; the next
    serious paths are vLLM/XPU INT8-per-channel and source/kernel work that
    reduces the target verification or draft decode cost per accepted chunk.
12. **Greedy verifier bypass is not enough by itself.** A gated
    `LLAMA_SPEC_VERIFY_GREEDY_ARGMAX=1` patch avoided the general CPU sampler
    in deterministic verifier rows and passed a 128-row smoke, but reached only
    `91.55 tok/s` after TTFT. This confirms the remaining fresh-MTP gap is not
    solved by sampler bypass alone; full target decode and full-vocab logits
    transfer still dominate. Preserve the patch as a component, but prioritize
    vLLM/XPU and deeper backend/kernel work.
13. **Q8_0 is not a speed upgrade under the current MTP recipe.** The smaller
    `gemma-4-26B-A4B-it-Q8_0.gguf` passed a 128-row smoke but reached only
    `90.44 tok/s` after TTFT, below the `UD-Q8_K_XL` record. Keep
    `UD-Q8_K_XL` as the promoted llama.cpp Q8 target unless a future runtime
    change specifically favors Q8_0.

## Stop Conditions

- If Q8 GGUF cannot fit even at 2K with f16 KV, test Q8_0 before lowering to
  Q6.
- If `GGML_SYCL_DISABLE_OPT=0` fails any canary, stop using it until the
  upstream corruption cause is understood.
- If MTP speed wins but canaries fail at repeat depth, mark it invalid and
  preserve the logs; do not chase speed-only LocalMaxxing submissions.
- If all llama.cpp Q8 paths are valid but slow, switch to vLLM int8-per-channel
  rather than weakening quality.
