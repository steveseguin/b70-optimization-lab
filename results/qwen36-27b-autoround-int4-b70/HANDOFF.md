# Qwen3.6 27B AutoRound Handoff

Last updated: 2026-07-03

This is the bookmark for `Intel/Qwen3.6-27B-int4-AutoRound` on Intel Arc Pro
B70.

## Current State

The lane has passed initial TP1 bring-up. The repository scaffolding exists,
the pinned Intel snapshot is downloaded under `/mnt/fast-ai/llm-cache/hf`, and
one B70 can serve the model through vLLM/XPU at `max_model_len=2048`.

Known-good smoke:

- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/servers/tp1-gpu0-port19410-20260703T012317Z.log`;
- smoke JSON:
  `../../data/qwen36-27b-autoround-openai-smoke-20260703T013020Z.json`;
- result: `pass=true`, content
  `{"answer": 42, "unit": "widgets"}`, `finish_reason=stop`;
- runtime: vLLM local `/home/steve/src/vllm`, `torch 2.11.0+xpu`,
  quantization auto-detected as `inc`, XPU graph off;
- MTP2 acceptance observed: `105/108` accepted draft tokens.

Current best valid fresh-response result:

- config: Intel checkpoint, TP1, one B70, vLLM/XPU chat endpoint, XPU graph on,
  `qwen3_next_mtp`, `num_speculative_tokens=3`,
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`,
  `MAX_NUM_BATCHED_TOKENS=1024`, thinking disabled;
- env delta:
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` and
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- final-gate policy: Qwen-specific fixed realistic suite, each prompt once,
  `cached_tokens=0` on all 12 requests, no prefix/KV/context/response reuse,
  `return_token_ids=true`, primary metric timed from streamed token-id counts
  for generated tokens 1-100 after TTFT;
- conservative Qwen-suite artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json`;
- primary result: median `53.522 tok/s`, p10 `48.406`, mean `53.986`,
  full-output after-TTFT median `53.817`, wall median `42.545`,
  TTFT median `628.9 ms`;
- supporting same-config Qwen-suite artifacts:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-realistic128-chat-tokenids-qwensuite-20260703T044123Z.json`
  at `54.861 tok/s`, and
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat-realistic128-chat-tokenids-qwensuite-20260703T044221Z.json`
  at `53.992 tok/s`;
- same-window plain-MTP3/cg8 control:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-samewindow-control-realistic128-chat-tokenids-qwensuite-20260703T044221Z.json`
  at median `48.345 tok/s`, so the conservative promote-source row is
  `+10.71%`;
- quality artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-promotesource-noacceptedpost-mtp3-cg8-repeat32-ctx1024-20260703T043946Z.json`
  with `pass_all=true` and `baseline_match_all=true`;
- compact packet:
  `promote-source-noacceptedpost-20260703.json`;
- LocalMaxxing: approved as `cmr4gokx90061nv01lhoe3ft8`.

Recent ladder controls:

- no-spec, graph on, cg8: valid control at median `31.179 tok/s` after TTFT;
- MTP2/cg8: valid but no-win at `45.638 tok/s`, with one suspicious
  repetitive first output;
- MTP3/cg16: one high row at `50.750 tok/s`, immediate repeat `47.045 tok/s`.
  Treat as variance/inconclusive, not a new baseline.

Post-baseline follow-up:

- The promoted recipe reproduced after the GGUF sweep at median
  `53.608 tok/s`, p10 `49.574`, mean `54.716`, cached tokens all zero:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-current-repeat-realistic128-chat-tokenids-qwensuite-20260703T062204Z.json`.
- Bounded config follow-ups after the GGUF lane did not produce a promotable
  replacement for the `53.522 tok/s` conservative record. Evidence summary:
  `post-gguf-config-sweeps-20260703.json`.
- `QWEN36_27B_REASONING_PARSER=` / no-parser was a no-win at
  `53.081 tok/s`. The launcher now supports this empty override for testing,
  but the default remains `qwen3`.
- Shorter `MAX_MODEL_LEN` (`512`, `768`, `1024`) produced small positive or
  neutral rows (`~53.1-54.4 tok/s`), but crossover runs across GPUs showed
  GPU/variance/context-window confounding. Do not promote a shorter context as
  a general replacement for the `2048` recipe without a paired repeat ladder.
- `MAX_NUM_BATCHED_TOKENS=384` produced one high row (`54.791 tok/s`) but the
  immediate repeat fell to `53.373`; `256` was no-win; `320` and `448` timed
  out before readiness and were cleaned up. Treat MBT tuning as inconclusive.
- Reusable one-shot runner for future bounded candidates:
  `../../scripts/run-qwen36-27b-autoround-vllm-candidate.sh`.
- Latest post-GGUF diagnostics moved the next source target away from blind
  GDN row-copy tuning and toward exact verifier / LM-head cost. A promoted
  row-copy trace run passed the strict fresh gate at median `53.316 tok/s`, but
  the trace file had zero records, meaning the current
  promote-source/no-accepted-postprocess recipe does not exercise
  `_xpu_gdn_copy_state_rows_native` / `_xpu_gdn_promote_running_state_native`.
  A synchronized timing diagnostic passed the strict gate but slowed to
  `48.776 tok/s`; its timing summary showed logits dominating:
  `spec_decode.greedy_sample.compute_logits` averaged `4.452 ms` across `1740`
  draft samples, target `gpu_model_runner.compute_logits` averaged `4.424 ms`
  across `580` target steps, while proposer model forward was only
  `0.65-0.83 ms` and metadata/copy regions were tiny. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-lmhead-verifier-bottleneck.md`.
- Exact greedy target argmax-only verification is closed no-win. The
  default-off patch reused the normal greedy rejection kernel and preserved
  target replacement / target-owned bonus semantics. Debug logs confirmed the
  path was active, and the strict fresh gate passed with `cached_tokens=0`, but
  median throughput was only `52.543 tok/s`, below the `53.522 tok/s`
  conservative record. Interpretation: on TP1, `get_top_tokens` still pays the
  full LM-head matmul, so bypassing sampler/logits plumbing is not enough.
  Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-exact-argmax-verifier-no-win.md`.
- Draft proposer `use_local_argmax_reduction` is also closed no-win. A minimal
  patch added `get_top_tokens()` to the Qwen MTP draft classes and the server
  confirmed the path was active. The first strict row was `53.237 tok/s`, close
  enough to require variance handling. Same-window GPU crossover produced
  controls averaging `53.0196 tok/s` and candidates averaging `52.9727 tok/s`
  (`-0.088%`), so the effect is flat/no-win. Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-draft-local-argmax-no-win.md`.
- Variance note: current same-recipe promoted rows are `54.861`, `53.992`,
  `53.522`, and `53.608 tok/s` (mean `53.996`, stdev `0.612`, range `2.48%`
  of mean). Treat sub-1% Qwen27 changes as inconclusive unless a same-window
  paired/crossover check supports them.
- The long-lived GPU0 server on port `19410` died during a live reconfirmation
  attempt with `UR_RESULT_ERROR_DEVICE_LOST`. Do not use that failed live
  server result for performance claims. `xpu-smi discovery` later saw all four
  B70s. A fresh single-lane GPU0 control server then passed the strict gate at
  `53.53356374896342 tok/s`, `cached_tokens=0`, confirming the current best
  recipe still reproduces:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-control-gpu0-freshreconfirm-realistic128-chat-tokenids-qwensuite-20260703T112954Z.json`.
- `MAX_NUM_BATCHED_TOKENS` strict same-window sweep (`512`, `768`, `2048`) did
  not produce a promotable win. `768` reached `49.352 tok/s`, but the paired
  same-window control was `48.884`; directional only and below the current
  noise floor.
- Promote-source deeper-MTP checks did not transfer. With the same accepted-slot
  promotion env pair and `max_cudagraph_capture_size=8`, MTP4 reached median
  `49.918 tok/s` and MTP5 reached `47.439 tok/s` under the strict Qwen suite,
  both below the MTP3 promote-source baseline. MTP5 also showed a degenerate
  first response / only `112` streamed token IDs on the first prompt, so treat
  MTP5 as a rejected quality/performance branch until verifier/GDN overhead is
  reduced by source work.
- Promote-source MTP3 capture-size sweep also did not move the baseline.
  cg4 looked directionally positive in one parallel pass (`54.449 tok/s`), but
  paired sequential repeats were lower than cg8 controls (`52.697`, `53.238`
  vs `53.509`, `53.518`). cg16 crashed with
  `UR_RESULT_ERROR_DEVICE_LOST`; cg32 was no-win and had a first-request TTFT
  outlier. Keep `max_cudagraph_capture_size=8`.
- GPU-resident accepted-count shortcut is closed no-win. A default-off source
  experiment (`VLLM_XPU_SPEC_DECODE_KEEP_ACCEPTED_COUNTS_GPU=1`) tried to keep
  the scalar accepted-count tensor on GPU between spec steps for the
  single-request non-align lane. The strict suite passed, but the clean
  same-source comparison lost to control (`52.542` vs `53.420 tok/s`). The
  patch is preserved at
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-keep-accepted-counts-gpu-20260703.patch`
  and the active source was reverted.
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_FULL_ACCEPT=0` is **invalid**. It is fast
  (`51.273 tok/s` strict Qwen-suite median and `74.877 tok/s` synthetic), but
  the 1024-token needle quality check failed with `B!!!!...` while baseline
  passed. Do not use this flag for service, LocalMaxxing, or promoted claims.
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0` by itself is also
  invalid / diagnostic. It becomes the current valid speed win only when paired
  with `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`, which changes the running
  source metadata to the accepted speculative slot instead of simply dropping
  accepted-state postprocess.
- A default-off/default-equivalent patch to sweep the Mamba/GDN
  `batch_memcpy` block size was tested at `4096`; it was no-win
  (`66.908 tok/s` synthetic vs clean baseline around `66.807`). The active
  vLLM source was reverted; patch artifact is preserved at
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-mamba-batch-memcpy-block-size-env-20260703.patch`.
- Accepted-state copy tracing now identifies the concrete hot path:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/mamba-copy-trace-summary-mtp3-cg8-p512o128-20260703T042542Z.json`.
  In a short MTP3/cg8 p512/o128 diagnostic, full accepts dominated
  (`accepted_count=4` in `32/36` postprocess copies), every copy launch had
  `96` entries, and the run copied `5.65 GB` of GDN/Mamba state total
  (`~156.9 MB` per launch). Temporal state copy was `5.44 GB`; conv state was
  only `0.21 GB`. The throughput from this trace run is diagnostic-only
  because tracing was enabled.

Current synthetic diagnostic optimization state:

- best synthetic search row so far: Intel checkpoint, TP1, XPU graph on,
  `qwen3_next_mtp`, `num_speculative_tokens=5`,
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":16}'`,
  `MAX_NUM_BATCHED_TOKENS=1024`;
- synthetic p512/o512 `vllm-random` corrected after-first throughput:
  `81.773 tok/s`, decode `12.182 ms/token`, draft acceptance `95.51%`;
- evidence:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T031846Z.json`;
- MTP6/cg16 lost (`78.556 tok/s`), so do not keep increasing
  speculative-token count without a new acceptance/cost reason;
- this is **not** a headline or LocalMaxxing result. It is a synthetic
  repetitive diagnostic. It is useful for screening MTP/graph changes, but it
  lost to MTP3/cg8 under the realistic chat gate.

Fresh-gate instrumentation status:

- local vLLM reporting patch applied and preserved at
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-prompt-tokens-details-zero-20260703.patch`;
- after restarting a server with that patch, non-stream chat/completions return
  `usage.prompt_tokens_details.cached_tokens=0`;
- `scripts/bench-openai-realistic-suite.py --return-token-ids` requests vLLM
  streamed token IDs and computes the primary tokens-1-100 metric from token-id
  receipt timestamps. Text chunks are still grouped, so do not use chunk counts
  as tokens.

Read in order:

1. `README.md`
2. `reproduce.md`
3. `validity-gates.md`
4. `bugs-failed-paths.md`
5. `../../experiments/qwen36-27b-autoround-int4-b70/README.md`
6. `../../experiments/qwen36-27b-autoround-int4-b70/research-plan.md`

## Current Goal

Continue INT4 optimization without promoting synthetic scores:

- use MTP5/cg16 as the current synthetic reference for quick screens;
- prefer chat-mode realistic-suite checks for quality because completions mode
  bypasses the chat template and emits `<think>` text;
- treat promote-source/no-accepted-postprocess MTP3/cg8 as the current valid
  realistic-chat baseline to beat;
- do not pursue MTP4/MTP5 as config-only changes; promote-source MTP4/MTP5 were
  strict-gate no-wins, and MTP5 had a quality warning;
- do not keep sweeping `max_cudagraph_capture_size` for MTP3; cg4/cg16/cg32
  were rejected, and cg8 remains the best service candidate;
- do not promote MTP3/cg16 from the single `50.750 tok/s` row without a paired
  repeat batch; the first repeat fell to `47.045 tok/s`;
- rerun the realistic Qwen suite with `--return-token-ids` before promoting any
  MTP/speculation or kernel change;
- prioritize exact greedy verifier / LM-head cost next. The current promoted
  recipe is no longer hitting the traced promoted row-copy helper, and timing
  shows full logits / LM-head work dominates;
- do not skip full-accept GDN postprocess blindly; it breaks long-context state
  recall. The current win is specifically source-slot promotion plus disabling
  the redundant accepted-state copy, not a semantic elision;
- exact greedy spec argmax-only target verification has been tested and closed
  no-win; do not repeat it unless `get_top_tokens` / LM-head internals change;
- draft proposer local-argmax reduction has been tested and closed flat/no-win;
- deeper wins likely need an AutoRound/INC W4A16 LM-head top-1 or
  candidate-vs-max kernel that avoids materializing full vocab logits;
- keep long-context/prompt-processing optimization separate from the short
  decode record.
