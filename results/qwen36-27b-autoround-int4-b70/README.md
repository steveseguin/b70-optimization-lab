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
a strict fresh-response baseline and one validated env-only speed win.
LocalMaxxing approved the current strict/fresh result as
`cmr4gokx90061nv01lhoe3ft8`.

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

Current best valid fresh-response result:

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
- completions-mode rows can be faster (for example MTP5/cg8 full-output
  after-TTFT `63.840 tok/s`) but are diagnostic only because completions mode
  bypasses the chat template and emits `<think>` text.

Next milestone: beat the promote-source/no-accepted-postprocess result without
changing model identity or using warmed/history/cache effects. Keep synthetic
screens for candidate search only, then rerun the Qwen realistic suite with
`--return-token-ids` and the quality suite before promotion.

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
