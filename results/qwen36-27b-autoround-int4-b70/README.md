# Qwen3.6 27B INT4 AutoRound on B70

This folder is the result packet for Qwen3.6 27B AutoRound INT4 on Intel Arc
Pro B70. The current TP2 record uses `webhie/Qwen3.6-27B-int4-AutoRound`; the
earlier `Intel/Qwen3.6-27B-int4-AutoRound` checkpoint remains a separate
baseline inside the same historical lane. The exact `95.385 tok/s` source and
run reconstruction is in
[`../../repro/qwen36-27b-autoround-int4-b70/README.md`](../../repro/qwen36-27b-autoround-int4-b70/README.md).

## Model Identity

- Current record repo: `webhie/Qwen3.6-27B-int4-AutoRound`
- Current record revision: `f5750c90b3776db658594df5fe8051098226dd8e`
- Earlier Intel reference: `Intel/Qwen3.6-27B-int4-AutoRound` at
  `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`
- Base model: `Qwen/Qwen3.6-27B`
- License: Apache-2.0, following the base model license constraints
- Runtime target: vLLM/XPU first, one B70 per replica before any TP experiments
- Quantization: AutoRound INT4, `bits=4`, `group_size=128`, symmetric,
  `packing_format=auto_round:auto_gptq`
- Model card vLLM starting point:
  `--tensor-parallel-size 1 --max-model-len 2048 --reasoning-parser qwen3`
  with optional `qwen3_next_mtp` speculation at `num_speculative_tokens=2`

The model card reports ten safetensor shards plus
`model_extra_tensors.safetensors`; Hugging Face metadata reports about
`17.71 GiB` of tracked files.

## Current Status

This lane was reopened on 2026-08-15 for an independent correction and
performance attempt. No new result is promoted yet.

The 2026-08-15 independent revalidation used a frozen 25-prompt suite, two
physical GPU pairs, four fresh speculative starts, two target-only controls,
512-token outputs, cache-zero enforcement, and conventional 99-interval
accounting. Its central speculative estimate was **98.766 tok/s** combined
(four-arm range 98.353–101.078), while the old 12-prompt subset reproduced at
**94.689 tok/s**. Every arm passed smoke and objective quality checks, but the
strict verdict was **fail**: all speculative arms diverged from target-only on
25/25 realistic prompts, and same-pair restarts diverged on 19/25 and 21/25.
See the
[`independent validation packet`](../../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md).
Do not promote the 101.078 fastest arm or describe this as a robust `>100`
result; the July row below remains historical evidence under its original
metric and narrower quality standard.

The final 2026-08-17 recovery attempt is also closed without promotion. A
fixed per-row RMSNorm implementation repaired one focused near-tie and matched
both then-sealed four-prompt controls at `106.663 tok/s`, but the matched-source
25-prompt speculative gate matched only 12/25 complete target outputs and
measured `93.445681 tok/s` conventional. See the
[closeout](../../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md).
No new LocalMaxxing row or production patch was promoted.

A follow-up replaced ReplaySSM with the native packed GDN transaction and made
its command-graph scratch persistent. This removed the graph-address lifetime
failure and improved repeatability. Four fresh candidate arms measured a
central **98.639 tok/s** (98.523–99.051), but each still differed from its
same-pair target-only control on 10 or 11 of 25 realistic outputs. The result
is therefore a preserved failed experiment, not a record. See
[`fixed-scratch-validation-20260815.json`](fixed-scratch-validation-20260815.json)
and the validation README for the full interpretation.

Initial TP1 single-B70 vLLM/XPU bring-up passed on 2026-07-03. The lane now has
a strict fresh-response BF16-LM-head baseline, one validated env-only speed win,
and faster quality-gated runtime INT8/draft-INT4 variants. LocalMaxxing approved
the BF16-LM-head result as `cmr4gokx90061nv01lhoe3ft8` and the runtime
INT8-LM-head variants as `cmr4zkcxb003yq9018408i1pn`,
`cmr576apv0079q901i6dvsh0l`, `cmr5iu3gk00bfq901nidgcana`,
`cmr8rg5d900glqr01g4fesy6i`, and `cmr9atqb800msqr01u760xh0t`.

Current TP2 record:

- model/runtime recipe: webhie AutoRound W4A16 with FP16 target compute,
  runtime INT8 target LM-head with BF16 scales, runtime INT4 group128 draft
  LM-head with BF16 scales, ReplaySSM exact GDN state, target-verified MTP3,
  graph-safe FlashAttention, one FULL four-row target graph, exact ReplaySSM
  pending/direct-output transaction fusions, and a PIECEWISE draft graph;
- collective runtime: public oneCCL parent
  `b52f40c07f0b140e6aba87548c80720a350a9827`, libccl
  `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`, injected only into the server;
- strict headline: median **`95.384868 tok/s`**, p10 `86.975415`, mean
  `95.623050`, full after-TTFT median `91.698097`, wall median `80.405331`,
  TTFT median `742.308 ms`;
- exact cases + repeat128 + baseline parity + 1K needle all passed;
- strict validity: 12 unique fixed realistic prompts, each once cold,
  `cached_tokens=0` throughout, no prompt/KV/history/response reuse, token-id
  timing for generated tokens 1-100 after TTFT;
- variance: both swapped four-GPU assignments favored the transaction
  candidate (`95.332 vs 87.901`, then `94.523 vs 93.685 tok/s`);
- LocalMaxxing: `cmrh35ct50092mj01h7jgydqj`; prior full-graph row
  `cmrgue7kl007pmj01yrkcyqmv`;
- packet: `tp2-fp16-fullgraph-transaction-20260711.json`;
- build/oracle/repro:
  `../../experiments/qwen27_graphsafe_flash_attention/README.md`.

The mechanisms matter: installed oneCCL `Gold-2021.17.2` failed the exact
BF16 `[4,5120]` XPUGraph all-reduce oracle on nearly every replay, while the
pinned public revision passed direct `256/256` and graph `512/512` on both
ranks. The draft then required a compiled all-gather custom-op boundary because
Inductor's functional `wait_tensor` cannot run inside an XPU command graph;
direct BF16 `[4,2560]` all-gather capture passed `512/512` on both independent
GPU pairs. Do not reproduce TP2 records against the known-broken installed
collective or omit the draft-graph patch/env gate.

Validated so far:

- pinned snapshot downloaded under `/mnt/fast-ai/llm-cache/hf`;
- TP1 vLLM server loaded on GPU0 at `max_model_len=2048`;
- vLLM auto-detected quantization as `inc` / AutoRound-compatible W4A16 path;
- model loaded in `17.84 GiB`;
- OpenAI smoke passed with thinking disabled;
- MTP2 is active and accepted `105/108` draft tokens across the smoke/manual
  probes, so the Intel checkpoint is not showing the public 0%-acceptance MTP
  packaging failure in this local runtime.
- four independent TP1 replicas have been used for parallel screening across
  the four B70s;
- local vLLM can now report explicit zero cached-token details after applying
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-prompt-tokens-details-zero-20260703.patch`
  and restarting the server.

Current Intel-checkpoint baseline valid fresh-response result:

- config: TP1, Intel checkpoint, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=3`, `max_cudagraph_capture_size=8`,
  `max_num_batched_tokens=1024`;
- env delta: `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` and
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- API/gate: chat mode, Qwen-specific fixed realistic suite, 12 unique prompts,
  each prompt once, `cached_tokens=0` for every request,
  `return_token_ids=true`, thinking disabled;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT, timed from streamed token-id receipt timestamps;
- conservative Qwen-suite artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json`;
- result: median `53.522 tok/s`, p10 `48.406`, mean `53.986`,
  full-output after-TTFT median `53.817`, wall median `42.545`,
  TTFT median `628.9 ms`;
- support rows:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-realistic128-chat-tokenids-qwensuite-20260703T044123Z.json`
  at `54.861 tok/s`, and
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat-realistic128-chat-tokenids-qwensuite-20260703T044221Z.json`
  at `53.992 tok/s`;
- same-window baseline control:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-samewindow-control-realistic128-chat-tokenids-qwensuite-20260703T044221Z.json`
  at median `48.345 tok/s`, p10 `43.733`, mean `49.290`, TTFT median
  `642.3 ms`;
- quality evidence:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-promotesource-noacceptedpost-mtp3-cg8-repeat32-ctx1024-20260703T043946Z.json`,
  `pass_all=true`, `baseline_match_all=true`;
- compact packet:
  `promote-source-noacceptedpost-20260703.json`;
- LocalMaxxing: `cmr4gokx90061nv01lhoe3ft8`;
- vLLM patch-stack snapshot:
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-current-xpu-qwen27-promote-source-stack-20260703.patch`.

Prior TP1 fastest quality-gated variant:

- label this separately as **webhie AutoRound W4A16 + runtime INT8 target
  LM-head (BF16 scales) + runtime INT4 draft LM-head (BF16 scales)**. Do not
  merge it into the Intel-checkpoint row;
- config: same promote-source MTP3/cg8 recipe plus ReplaySSM exact GDN state
  handling, `VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1`,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4=1`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16`, and
  `VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1` for the conservative
  headline;
- strict fresh primary artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-realistic128-chat-tokenids-qwensuite-20260706T140317Z.json`;
- result: median **`68.236 tok/s`**, p10 `62.317`, mean `67.830`,
  TTFT median `479.146 ms`, `cached_tokens=0` on every request;
- interpretation: this is the current best measured valid same-recipe row, not
  a new mechanism; the improvement over the approved `67.519` row is small and
  should be treated with the lane's variance caution;
- July 11 current-source reconfirmation produced three isolated strict medians
  at `65.359`, `66.716`, and `65.420 tok/s`; the first also passed exact,
  repeat64, baseline parity, and the 1K check. Their mean is `3.52%` below the
  historical high and remains inside the established `4.4%` endpoint band.
  A swapped four-GPU draft graph/eager crossover measured `-0.05%`, proving
  that the TP2 distributed all-gather graph fix is not a missing TP1 win. Keep
  `68.236` as the valid historical high and use `65.4-66.7` as the current
  reproduced band. Packet:
  `tp1-draftgraph-attribution-reconfirm-20260711.json`;
- support rows:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-draftint4-slotmgmt-torchfallback-solo-confirm-20260706T050135Z-realistic128-chat-tokenids-qwensuite-20260706T050135Z.json`
  at median `67.519 tok/s`,
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-textonlymtp-control-20260706T140004Z-candidate-summary-20260706T140004Z.json`
  at median `68.397 tok/s` with quality skipped,
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-slotcopy-native-20260706T045223Z-candidate-summary-20260706T045223Z.json`
  at median `68.481 tok/s`,
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-slotcopy-native-confirm-gpu1-20260706T045712Z-candidate-summary-20260706T045712Z.json`
  at median `66.871 tok/s`, and
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-slotcopy-torchfallback-control-gpu2-20260706T045712Z-candidate-summary-20260706T045712Z.json`
  at median `67.300 tok/s`;
- full quality gate:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-repeat64-ctx1024-20260706T140317Z.json`,
  `pass_all=true`, `baseline_match_all=true`, `repeat_pass=true`;
- compact packet:
  `webhie-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.json`;
- note:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-current-confirm-68tok-and-textonlymtp-no-win.md`;
- LocalMaxxing: approved as `cmr9atqb800msqr01u760xh0t`, with queue/response at
  `../../experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.queue.json` and
  `../../data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.submit.log`;
- latest closed native-prefix follow-up:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-native-prefix-exact-state-rescreen-no-win.md`.
  After the prefix-base extra state-column repair, exact-native offset/writeout
  rows still failed quality at single-digit speed, prefill-column replay
  collapsed acceptance, and replaypartial reached only `6.323 tok/s`. The
  native fast path remains blocked by the missing projected GDN row for the
  target-owned replacement/bonus token sampled after verifier logits.
- important attribution: native ReplaySSM slot-copy/reset ops passed direct XPU
  parity, but same-window endpoint control did not show a speed win (`66.871`
  native vs `67.300` PyTorch slot-management fallback), so the native slot-copy
  patch is preserved as an experiment artifact rather than the promoted source
  of this record.
- latest target-body no-win: direct Q-gate Q/K norm + RoPE fusion beat the
  isolated full-attention section in microbench, but the strict endpoint screen
  regressed to `66.953 tok/s` with quality skipped. See
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-qgate-direct-qkrope-no-win.md`.
- latest true native gated RMSNorm kernel no-win: a new `_C.rms_norm_gated`
  op exactly matched the Qwen GDN output norm and was `~3.6x` faster in
  isolated hidden-size-128 microbench, but strict endpoint A/B did not improve
  (`67.980` baseline vs `67.928` native). Active source and `_C.abi3.so` were
  restored; see
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-rmsnorm-gated-native-xpu-kernel-no-win.md`.

Previous fastest quality-gated variant:

- label this separately as **webhie AutoRound W4A16 + runtime INT8 LM-head
  (BF16 scales)**. Do not merge it into the Intel-checkpoint row;
- env delta on top of the current promote-source MTP3/cg8 recipe:
  `VLLM_XPU_LM_HEAD_INT8=1` and
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict fresh primary artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-gpu2-crossover-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222859Z.json`;
- result: median **`65.276 tok/s`**, p10 `59.609`, mean `65.077`,
  TTFT median `603.6 ms`, `cached_tokens=0` on every request;
- supporting BF16-scale rows:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-gpu3-samewindow-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222647Z.json`
  at median `65.005 tok/s`, and
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-repeat-gpu3-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T223150Z.json`
  at median `64.864 tok/s`;
- latest unchanged-recipe support rows:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-current-record-repro-support.md`
  at `65.410 tok/s` and
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-post-awq-record-repro-support.md`
  at `66.128 tok/s`. Both passed the strict fresh/cached-zero gate and are
  support only, not new records or LocalMaxxing updates, because the recipe is
  unchanged and the lane has a known variance band;
- same-window/crossover FP32-scale controls:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-fp32scale-control-gpu2-samewindow-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222647Z.json`
  at median `64.234 tok/s`, and
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-fp32scale-control-gpu3-crossover-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222859Z.json`
  at median `64.090 tok/s`;
- full quality gate:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-webhie-int8lmhead-bf16scale-mtp3-cg8-repeat32-ctx1024-20260703T223138Z.json`,
  `pass_all=true`, `baseline_match_all=true`, `long_context_pass=true`;
- compact packet:
  `webhie-int8-lmhead-bf16scale-20260703.json`;
- note:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-int8-lmhead-bf16-scale-quality-pass.md`;
- LocalMaxxing: approved as `cmr5iu3gk00bfq901nidgcana`, with queue/response at
  `../../experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-bf16scale-20260703.queue.json` and
  `../../data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-bf16scale-20260703.submit.log`;
- previous webhie INT8-LM-head packet:
  `webhie-int8-lmhead-20260703.json`, LocalMaxxing
  `cmr576apv0079q901i6dvsh0l`.

Current prompt-processing / long-context service baseline:

- lane note:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-ladder-baseline.md`;
- suite:
  `../../repro/qwen36-27b-autoround-int4-b70/long-context-suite-v1.json`;
- runner:
  `../../experiments/qwen36-27b-autoround-int4-b70/scripts/run-long-context-ladder.sh`;
- policy: service/prefill lane only, not a short-decode LocalMaxxing headline;
  rows are cold, unique prompts, `cached_tokens=0`, exact JSON retrieval;
- current 32K-capability anchor: `MAX_MODEL_LEN=32768`,
  `MAX_NUM_BATCHED_TOKENS=4096`, six rows through `17706` actual prompt tokens,
  exact retrieval pass, TTFT median `22.443s`, approximate prefill median
  `224.67 tok/s`, after-TTFT output median `60.19 tok/s`, KV cache size
  `141,784` tokens, max concurrency `4.33x` at 32K;
- same-window 32K no-parser MBT screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-mbt-screen.md`.
  Keep `MAX_NUM_BATCHED_TOKENS=4096`; MBT2048 passed but was slower, and
  MBT8192 stalled on the final long request without a complete gate artifact;
- production-visible service variant: set `QWEN36_27B_REASONING_PARSER=`. The
  32K no-parser content check passed the same exact retrieval gate through
  `17706` actual prompt tokens with all rows streaming visible `content`
  deltas (`reasoning_delta_count=0`). Keep it labeled as a service variant and
  rerun the short strict decode suite after any future parser/template change.

Prior Intel-checkpoint quality-gated runtime-quantized variant:

- label this separately as **AutoRound W4A16 + runtime INT8 LM-head**. Do not
  call it the original BF16-LM-head AutoRound quantization;
- source patch:
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-quality-pass-20260703.patch`;
- env delta on top of the current promote-source MTP3/cg8 recipe:
  `VLLM_XPU_LM_HEAD_INT8=1`;
- strict fresh Qwen-suite artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-int8lmhead-realistic128-chat-tokenids-qwensuite-20260703T133109Z.json`;
- result: median **`62.628 tok/s`**, p10 `58.104`, mean `62.998`,
  TTFT median `606.6 ms`, `cached_tokens=0` on every request;
- same-window repeat on GPU3:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-int8lmhead-repeat-gpu3-realistic128-chat-tokenids-qwensuite-20260703T133535Z.json`
  at median `62.276 tok/s`;
- same-window BF16-LM-head control on GPU2:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-bf16lmhead-control-gpu2-realistic128-chat-tokenids-qwensuite-20260703T133535Z.json`
  at median `53.332 tok/s`;
- full quality gate:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-mtp3-cg8-repeat32-ctx1024-20260703T133323Z.json`,
  `pass_all=true`, `baseline_match_all=true`, `long_context_pass=true`;
- compact packet:
  `int8-lmhead-20260703.json`;
- note:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-int8-lmhead-quality-pass.md`;
- LocalMaxxing: approved as `cmr4zkcxb003yq9018408i1pn` with explicit
  `AutoRound INT4 W4A16 + runtime INT8 LM-head` quantization/mode label.

Service-oriented scoped variant:

- patch:
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-scope-target-quality-pass-20260703.patch`;
- env delta on top of the INT8 lane: `VLLM_XPU_LM_HEAD_INT8_SCOPE=target`;
- attribution result:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-scopefix-target-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T140331Z.json`
  at median `61.898 tok/s`, p10 `57.494`, mean `62.432`;
- target-only quality:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-targetonly-mtp3-cg8-repeat32-ctx1024-20260703T140623Z.json`,
  `pass_all=true`, `baseline_match_all=true`, `long_context_pass=true`;
- interpretation: target verifier LM-head is the bottleneck. Target-only INT8
  is nearly throughput-equivalent to all-head INT8 while avoiding the extra MTP
  INT8 LM-head copy. Use all-head INT8 for the submitted max-throughput row.
  This older Intel-checkpoint target-only variant passed quality, but the later
  webhie BF16-scale target-only follow-up failed repeat32 once, so target-only
  is an attribution/service idea that must be quality-gated per checkpoint and
  scale dtype before use.

Post-GGUF recheck:

- the same promoted recipe reproduced at `53.608 tok/s`, p10 `49.574`, mean
  `54.716`, with `cached_tokens=0` for every request:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-current-repeat-realistic128-chat-tokenids-qwensuite-20260703T062204Z.json`;
- later no-parser, shorter-context, and `MAX_NUM_BATCHED_TOKENS` probes did
  not produce a stable promotable record. `MAX_NUM_BATCHED_TOKENS=384` had one
  high row at `54.791 tok/s`, but the repeat fell to `53.373`; shorter context
  rows were confounded by GPU/window variance. Summary:
  `post-gguf-config-sweeps-20260703.json`;
- use `../../scripts/run-qwen36-27b-autoround-vllm-candidate.sh` for future
  one-shot vLLM candidate checks before promoting any config.

Current best synthetic diagnostic:

- config: TP1, Intel checkpoint, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=5`, `max_cudagraph_capture_size=16`,
  `max_num_batched_tokens=1024`;
- file:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T031846Z.json`;
- synthetic `vllm-random` p512/o512 corrected after-first throughput:
  `81.773 tok/s`, decode `12.182 ms/token`, draft acceptance `95.51%`;
- status: **diagnostic only**, not a headline result, because it uses a
  repetitive synthetic prompt and is not the fixed realistic cold suite.

Current realistic research interpretation:

- MTP5/cg16 wins the synthetic p512/o512 screen at `81.773 tok/s`, but loses
  under realistic chat at median `43.771 tok/s`;
- no-spec graph-on control is `31.179 tok/s` after TTFT on the same Qwen suite;
- MTP2/cg8 reached `45.638 tok/s` but had one suspicious repetitive first
  response and is not a quality baseline;
- MTP4/cg8 reached median `45.669 tok/s` under the same gate;
- retesting deeper MTP with the valid promote-source/no-accepted-postprocess
  env pair still did not beat MTP3: promote-source MTP4/cg8 reached
  `49.918 tok/s`, and promote-source MTP5/cg8 reached `47.439 tok/s` with a
  first-prompt quality warning;
- retesting deeper MTP again on the then-fastest webhie BF16-scale
  INT8-LM-head recipe also did not beat that recipe's MTP3: same-window strict rows were
  MTP3/cg8 control `65.809 tok/s`, MTP4/cg8 `60.478`, MTP5/cg8 `59.257`, and
  MTP5/cg16 `59.817`, all with `cached_tokens=0`. The MTP3 control is support
  only and not promoted because it was within variance of the then-approved
  `65.276` row. See
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-depth-screen-no-win.md`;
- retesting MTP3 graph-capture size with the valid promote-source env pair did
  not beat cg8: cg4's initial `54.449 tok/s` row fell to `52.697` and `53.238`
  in paired repeats against cg8 controls at `53.509` and `53.518`; cg16
  crashed with device lost, and cg32 was no-win;
- keeping accepted counts GPU-resident between spec steps was no-win. The
  default-off `VLLM_XPU_SPEC_DECODE_KEEP_ACCEPTED_COUNTS_GPU=1` source
  experiment passed the strict gate, but same-source control beat candidate
  (`53.420` vs `52.542 tok/s`), so the active source was reverted and the
  patch is retained only as a failed experiment artifact;
- plain MTP3/cg8 is the stable control family at `47.624`, `48.003`, and
  `48.536 tok/s`;
- promote-source/no-accepted-postprocess is the current best valid family at
  `54.861`, `53.992`, and `53.522 tok/s`; the conservative row is `+10.71%`
  over the same-window plain MTP3/cg8 control;
- MTP3/cg16 produced one high row at `50.750 tok/s`, but the immediate repeat
  fell to `47.045 tok/s`, so it is variance/inconclusive and not promoted;
- `MAX_NUM_BATCHED_TOKENS=768` reached `49.352 tok/s` in a later strict
  same-window sweep, but its paired control was `48.884`, so this is
  directional only and not promoted;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_FULL_ACCEPT=0` is an invalid fast path:
  it reached `51.273 tok/s` on the strict suite, but failed 1024-token needle
  quality (`B!!!!...` instead of the needle) while baseline passed;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0` by itself is invalid /
  diagnostic only, but paired with
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` it is currently quality-passing:
  the forward metadata reads the accepted speculative slot as the running
  source, avoiding the separate postprocess copy without dropping the accepted
  state transition;
- the Mamba/GDN `batch_memcpy` block-size patch at `4096` was no-win and the
  active source was reverted; preserve the patch artifact only for reference;
- accepted-state copy tracing shows why the invalid skip flag was fast:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/mamba-copy-trace-summary-mtp3-cg8-p512o128-20260703T042542Z.json`
  recorded `36` postprocess copy launches in a short MTP3/cg8 p512/o128
  diagnostic, `96` copy entries per launch, `~156.9 MB` copied per launch,
  and `5.44 GB / 5.65 GB` of bytes in temporal state copy. Full accepts were
  `32/36` postprocess copies. The trace run is diagnostic-only, but it makes
  the current source target explicit: preserve full-accept semantics while
  avoiding or structurally replacing the physical state copy;
- however, a later promoted-recipe row-copy trace found zero records for
  `_xpu_gdn_copy_state_rows_native` /
  `_xpu_gdn_promote_running_state_native`, so the current
  promote-source/no-accepted-postprocess recipe appears to have removed that
  promoted physical row-copy hot path. A 2026-07-03 synchronized timing
  diagnostic next suggested full logits / LM-head dominated the MTP3 path; that
  was useful historically, but the 2026-07-05 timing refresh corrected the
  current frontier after the INT8 LM-head/local-argmax path matured. Current
  synchronized timing shows LM-head is small, the apparent `~11 ms`
  recurrent-MTP-next timing was async attribution, and the real blockers are
  target verifier forward cost plus emitted tokens per target step. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-lmhead-verifier-bottleneck.md`
  and
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-replayssm-stage-profile-and-frontier.md`.
- exact greedy target argmax-only verification is closed no-win. The
  default-off patch preserved normal greedy spec semantics and passed the
  strict fresh gate with `cached_tokens=0`, but reached only `52.543 tok/s`.
  Since target `get_top_tokens` still pays the TP1 LM-head matmul, avoiding
  sampler/logits plumbing was not enough. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-exact-argmax-verifier-no-win.md`.
- draft proposer `use_local_argmax_reduction` is closed no-win. After adding
  `get_top_tokens()` to the active Qwen MTP draft class, the server confirmed
  local argmax reduction was active. Same-window GPU crossover gave controls at
  `53.0196 tok/s` average and candidates at `52.9727 tok/s` average
  (`-0.088%`), below the variance floor. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-draft-local-argmax-no-win.md`.
- external EAGLE3 compressed drafter compatibility is closed for now. The
  `Ex0bit/Qwen3.6-27B-PRISM-EAGLE3` compressed drafter loaded locally and k=1
  passed the strict fresh gate, but it reached only `30.063 tok/s` with
  `8734 ms` median TTFT. k=2 graph and k=3 eager crashed with
  `UR_RESULT_ERROR_DEVICE_LOST`; k=3 graph with default accepted-state handling
  stalled after 8 prompts and hit zero-acceptance intervals. Do not use EAGLE3
  compressed as a current record route without source/runtime fixes. The
  full-vocab EAGLE3 variant was also tested at k=2; it loaded and captured
  graphs, but crashed with the same `UR_RESULT_ERROR_DEVICE_LOST` at
  `num_accepted_tokens_event.synchronize()` and was slow before crashing.
  A 2026-07-05 retest fixed a real compatibility gap for nested
  `eagle_config.eagle_aux_hidden_state_layer_ids=[1,31,60]` and confirmed the
  intended aux layers were used, but endpoint acceptance still collapsed and
  throughput was operationally unusable. Preserve the patch as a compatibility
  artifact, not a current record route:
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-eagle3-nested-aux-layers-compat-20260705.patch`.
  A 2026-07-06 offline aux-hidden acceptance probe makes the closure stronger:
  the target-owned no-spec aux corpus path now works (`96` prompts, `15360`
  rows, aux layers `1,31,60`, zero continuity breaks), but Ex0bit compressed
  averaged only `0.289908` accepted tokens over `14784` starts and the
  full-vocab checkpoint spot check averaged `0.291016`. This is far below the
  current MTP3 accepted-token depth, so do not port/integrate this checkpoint
  as-is; use the aux corpus tooling only for a target-matched EAGLE3/DFlash
  training attempt.
  Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-eagle3-drafter-compatibility.md`
  and
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-ex0bit-eagle3-aux-probe-no-win.md`.
- local EAGLE1 drafter training is mechanically usable but not a record route
  yet. The first 128-sample hidden-state corpus reached `2.1016` heldout mean
  accepted offline but failed endpoint quality/speed; endpoint isolation
  controls also failed. The newer corpus/eval v2 path fixes metadata and
  collection hygiene, and the four-GPU runner collected `96` chat prompts,
  `15360` hidden rows, `96/96` metadata-bearing samples, and `0` continuity
  breaks, but a compact draft trained on three shards reached only `0.489`
  heldout mean accepted. Do not endpoint-test that draft; future EAGLE work
  needs stronger data/training/init before serving. Followups did not rescue
  it: staged curriculum `0.616`, balanced task holdout `0.601`, old-draft
  transfer `0.201`, and all-96 training on a separate calibration suite
  `0.438`. A later stronger residual/two-layer offline screen reached only
  `0.695` heldout mean accepted and `0.441` on separate calibration, so it is
  also not an endpoint candidate. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-followups-closed.md`
  and
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-v2-stronger-offline-screen-no-endpoint.md`.
- target-matched Ex0bit EAGLE3/DFlash training later made real but insufficient
  offline progress. The best historical diagnostic line is still the v5
  survival-objective checkpoint at `1.340886544011544` heldout mean accepted,
  while v6/v6b data-quality and step-focus work stayed around `1.04-1.06`.
  A four-GPU v6b all-scope continuation from the best r3/r5 step-focus
  checkpoints reached only `1.1014610941216445` mean accepted over `14715`
  heldout starts, below the v5 best and far below the `1.5-2.0` endpoint
  threshold. Do not endpoint-test or port this draft family unless a new
  mechanism materially improves offline accepted depth. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-ex0bit-eagle3-target-adaptation-screen.md`,
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-eagle3-v6b-allscope-no-endpoint.md`, and
  `../../experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6b-allscope-summary-20260707.json`.
  A top-k oracle then showed upper-bound headroom (`top8=2.249`, `top16=2.590`
  mean accepted), but cheap single-token rerankers did not extract it:
  the diagonal reranker reached only `1.1069`, and the small MLP follow-up
  peaked at only `1.1193`;
  see
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-eagle3-topk-oracle-and-diag-reranker.md`.
  The same note's tree-cost model closes naive full-tree verification too:
  same-cost top-16 oracle estimates only `91.65 tok/s`, while legal full-tree
  expansion is far too expensive.
- external DFlash drafter compatibility is also closed no-win locally.
  `z-lab/Qwen3.6-27B-DFlash` loaded and passed the strict fresh gate at k=8,
  k=10, and k=12, but the best median was only `49.994 tok/s` and k=15
  crashed before readiness with `UR_RESULT_ERROR_DEVICE_LOST`. The DFlash model
  card warns that full engine support may require a vLLM PR for interleaved SWA
  and target hidden-state handling, so keep this as a local Intel AutoRound/XPU
  result rather than a universal DFlash claim. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-dflash-drafter-no-win.md`.
  The later Hipfire/DFlash feasibility gate is also closed: the true mixed
  sliding/full draft architecture initialized with the preserved multi-KV
  patch, but showed only about `1.1-1.2` mean acceptance before device-loss or
  manual stop, so an Intel Hipfire/DFlash port is not justified for this lane.
  Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-dflash-feasibility-plan-closure.md`.
- variance floor: older same-recipe promoted rows span `53.522-54.861 tok/s`
  (`2.48%` range of mean, stdev `0.612`). A fresh four-GPU reconfirmation after
  the DFlash/EAGLE experiments showed GPUs 1-3 tightly clustered at
  `52.836`, `53.048`, and `52.865 tok/s` (`0.40%` range), while GPU0
  device-lost in speculative decode. Use GPUs 1-3 for near-term same-window
  candidate/control comparisons and treat sub-1% deltas as inconclusive unless
  repeated/crossover runs agree. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-current-best-reconfirm-and-variance.md`.
- completions-mode rows can be faster (for example MTP5/cg8 full-output
  after-TTFT `63.840 tok/s`) but are diagnostic only because completions mode
  bypasses the chat template and emits `<think>` text.

Next milestone: beat the runtime INT8-LM-head row with a real source change.
The bounded retests after the record closed as no-promo: MTP depth remains best
at k=3, including the later shallow-depth coverage pass where MTP1/cg8
`51.246` and MTP2/cg8 `59.589` both lost to MTP3/cg8 control `64.730`
(`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-mtp1-mtp2-depth-coverage-no-win.md`),
current webhie/BF16-scale capture size remains best at cg8
(`65.153` same-window control versus cg4 `64.507`, cg16 `63.500`, cg32
`64.071`; see
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-bf16scale-capture-size-screen-no-win.md`),
older target-only attribution was enough to justify the LM-head kernel lane,
but the latest synchronized timing shows the active INT8 LM-head/local-argmax
path is now small. The standalone native compact full-vocab top-1 kernel is
exact but slower than dense oneDNN, and the semantic candidate-max version is
also closed no-win: exact top IDs/values plus candidate scores, but only
`1.010x` at rows `1` and slower at rows `2-4`. A low-level INT8 GEMM scratchpad
ring-size screen is also closed no-promo: ring4 produced high support rows
(`65.708`, `65.817`) but crossover deltas versus ring1 controls were only
`+0.42%` and `+0.27%`; see
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-int8-gemm-scratchpad-ring-screen-no-win.md`.
A later producer-side INT4 draft-LM-head top-1 prototype also closed no-win:
the sycl8 build passed top-id correctness, but full-vocab rows `1..4` were
slower than dense logits plus argmax (`2.30/5.82/6.52/9.15 ms` vs
`1.95/1.37/1.21/1.22 ms`); see
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-int4-top1-prototype-sycl8-no-win.md`.
The next meaningful decode-rate work is improving accepted/generated tokens per
target verifier step, finding a stronger fresh-request draft source, reducing
target-forward cost in the Qwen3.5/Next body, or building a graph-safe exact
GDN/spec-state transaction that lets stronger drafting remain correct. LM-head
producer work is now a secondary cleanup unless it is a genuinely new backend
primitive with microbench evidence.
The follow-up source audit in
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-lmhead-callcount-source-audit.md`
narrows that further: small Python-level row/call shortcuts are unlikely to
win because they still use dense LM-head primitives. Future Qwen27 work should
start with a real fused/top-ID LM-head primitive, a native row-adaptive verifier,
or a materially stronger target-matched drafter, not another config sweep. The
latest frontier audit also tested oneDNN Graph `MatMul -> ReduceMax` directly:
BF16 stayed as two one-op partitions and the tested INT8 graph form was
rejected, so there is no cheap oneDNN Graph wrapper shortcut to promote. See
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-frontier-audit-onednn-graph-and-drafter.md`.
The 2026-07-06 branch/regenerate trace probe added default-off
`VLLM_XPU_BRANCH_REGEN_TRACE=1`, repaired the local XPU runtime after sycl9
`_C`/`_moe_C`/FA2 binaries broke device inference and FA2 `varlen_fwd`, and
completed a strict fresh diagnostic row at `65.078 tok/s` with `cached_tokens=0`
on every prompt. The trace summarized `220` scheduled verifier rows:
`1.6727` mean accepted draft-prefix tokens, `2.6727` mean raw visible tokens,
`39.09%` full accept, and `292` branchable remaining draft rows after partial
rejects. Treat this as branch/tape infrastructure evidence, not a headline
result: by itself the measured MTP3 branch surface is too narrow to be the
primary `125+ tok/s` path. See
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-branch-regen-trace-probe-and-sycl8-restore.md`.
The 2026-07-06 draft-side `mtp.fc` runtime INT8 experiment is also closed:
it targeted only the BF16 Qwen3.5 MTP `mtp.fc` layer and preserved exact target
verification, but the completed candidate (`66.777 tok/s`) lost to same-window
controls (`67.954` and `67.994 tok/s`), while another candidate exposed a
TorchDynamo fake-tensor unsupported-op failure for `_xpu_C.int8_gemm_w8a8`
inside compiled MTP. See
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-mtp-fc-int8-no-win.md`
and
`../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mtp-fc-int8-no-win-20260706.patch`.
The GDN gated-RMSNorm `rstd` skip is also closed no-win: skipping an ignored
Triton `rstd` allocation/writeback via `VLLM_XPU_RMSNORM_SKIP_RSTD=1` produced
`66.329` and `66.595 tok/s`, below same-window controls at `67.716` and
`67.910 tok/s`; see
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-rmsnorm-skip-rstd-no-win.md`
and
`../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-rmsnorm-skip-rstd-no-win-20260706.patch`.
The DFlash mixed-SWA audit is captured in
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-dflash-mixed-swa-multikv-blocker.md`:
the target runner is multi-KV aware, but the DFlash/EAGLE drafter path assumes
one KV group, so deleting the assertion would risk invalid draft-cache writes.
The later mixed-SWA implementation attempt and Hipfire feasibility closure found
the real mixed DFlash draft was not accepting enough tokens on this fixed suite,
so do not reopen it for record chasing without a stronger draft.
Keep synthetic screens for candidate search only, then rerun the Qwen realistic
suite with `--return-token-ids` and the quality suite before promotion.

First diagnostic realistic-suite run (not a headline result):

- file:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/mtp2-xpugraph0-ctx2048-realistic-v1-reasoningdelta-20260703T013627Z.json`;
- config: TP1, MTP2, XPU graph off, `max_model_len=2048`,
  `max_tokens=128`, thinking disabled by request;
- median wall throughput: `36.327 tok/s`;
- median full-output after-TTFT throughput: `41.972 tok/s`;
- median TTFT: `484.821 ms`;
- validity: **diagnostic only** because `cached_tokens=null` and exact
  tokens-1-100 timing is not measurable from grouped SSE text chunks.

## Start Here

- [Reproduce](reproduce.md): download, launch, smoke, and benchmark entry
  points.
- [Validity gates](validity-gates.md): what counts as a baseline, record, or
  LocalMaxxing candidate.
- [Bugs and failed paths](bugs-failed-paths.md): loader/runtime failures and
  invalid speed lanes.
- Experiment lane:
  `../../experiments/qwen36-27b-autoround-int4-b70/README.md`.
- Research plan:
  `../../experiments/qwen36-27b-autoround-int4-b70/research-plan.md`.

## Initial Hypotheses

1. TP1 should fit on a single 32 GB B70 at short context because the checkpoint
   is INT4 AutoRound with FP16 exceptions, not full BF16.
2. The fastest research loop should use four independent TP1 replicas on the
   four B70s, mirroring the Gemma workflow, before considering TP2/TP4.
3. Built-in `qwen3_next_mtp` may provide an early speedup, but headline claims
   must still use fresh prompts with `cached_tokens=0` and target-verified
   accepted tokens.
4. Loader support is the first risk: local vLLM must correctly map
   `quant_method=auto-round` / `auto_round:auto_gptq` to an XPU-supported
   W4A16 path without silently dequantizing or CPU fallback.

## Claiming Rules

- Do not submit LocalMaxxing results unless the Qwen realistic gate passes and
  the result improves a matching prior record.
- Do not average warmed repeated prompts into fresh-response throughput.
- Do not promote `vllm-random`, repeated-output, completions-with-raw-thinking,
  or server-metric-only rows as real-world throughput.
- Do not compare this INT4 quality lane directly against Gemma Q8 or Qwen35
  W8A8 without labeling the quantization and quality differences.
