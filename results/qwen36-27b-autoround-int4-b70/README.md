# Qwen3.6 27B INT4 AutoRound on B70

This folder is the result packet for the `Intel/Qwen3.6-27B-int4-AutoRound`
lane on Intel Arc Pro B70.

## Model Identity

- Hugging Face repo: `Intel/Qwen3.6-27B-int4-AutoRound`
- Revision: `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`
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

Initial TP1 single-B70 vLLM/XPU bring-up passed on 2026-07-03. The lane now has
a strict fresh-response BF16-LM-head baseline, one validated env-only speed win,
and one faster quality-gated runtime INT8-LM-head variant. LocalMaxxing approved
the BF16-LM-head result as `cmr4gokx90061nv01lhoe3ft8` and the runtime
INT8-LM-head variants as `cmr4zkcxb003yq9018408i1pn`,
`cmr576apv0079q901i6dvsh0l`, and `cmr5iu3gk00bfq901nidgcana`.

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

Current fastest quality-gated variant:

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
- retesting deeper MTP again on the later fastest webhie BF16-scale
  INT8-LM-head recipe also did not beat MTP3: same-window strict rows were
  MTP3/cg8 control `65.809 tok/s`, MTP4/cg8 `60.478`, MTP5/cg8 `59.257`, and
  MTP5/cg16 `59.817`, all with `cached_tokens=0`. The MTP3 control is support
  only and not promoted because it is within variance of the approved `65.276`
  row. See
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
  promoted physical row-copy hot path. The latest synchronized timing diagnostic
  instead shows full logits / LM-head dominating the current MTP3 path:
  draft `spec_decode.greedy_sample.compute_logits` averaged `4.452 ms`, target
  `gpu_model_runner.compute_logits` averaged `4.424 ms`, and proposer forward
  was only `0.65-0.83 ms`. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-lmhead-verifier-bottleneck.md`.
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
  Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-eagle3-drafter-compatibility.md`.
- external DFlash drafter compatibility is also closed no-win locally.
  `z-lab/Qwen3.6-27B-DFlash` loaded and passed the strict fresh gate at k=8,
  k=10, and k=12, but the best median was only `49.994 tok/s` and k=15
  crashed before readiness with `UR_RESULT_ERROR_DEVICE_LOST`. The DFlash model
  card warns that full engine support may require a vLLM PR for interleaved SWA
  and target hidden-state handling, so keep this as a local Intel AutoRound/XPU
  result rather than a universal DFlash claim. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-dflash-drafter-no-win.md`.
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
at k=3, capture size remains best at cg8, target-only attribution shows the
target verifier LM-head dominates the win, and the standalone native compact
full-vocab top-1 kernel is exact but slower than dense oneDNN. The next
meaningful decode-rate work is reducing LM-head call/row count per verifier
step, improving accepted tokens per target verifier step, or finding a
oneDNN-integrated top-1/top-k post-op that avoids a second reduction launch.
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
