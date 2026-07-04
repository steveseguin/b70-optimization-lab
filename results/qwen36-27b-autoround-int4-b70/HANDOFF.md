# Qwen3.6 27B AutoRound Handoff

Last updated: 2026-07-04

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

Current Intel-checkpoint baseline valid fresh-response result:

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

Current fastest quality-gated variant:

- runtime quantization label: **webhie AutoRound W4A16 + INT8 LM-head
  (BF16 scales)**.
  This is a distinct AutoRound checkpoint from the Intel reference, so keep it
  separate in claims and submissions;
- config: same promote-source MTP3/cg8 recipe plus
  `VLLM_XPU_LM_HEAD_INT8=1` and
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict fresh primary artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-gpu2-crossover-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222859Z.json`;
- primary result: median `65.27648650325429 tok/s`, p10
  `59.608527188588106`, mean `65.07685647020962`, TTFT median
  `603.580 ms`, `cached_tokens=0` on every request;
- supporting BF16-scale rows:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-gpu3-samewindow-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222647Z.json`
  at median `65.00467502982892 tok/s`, and
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-repeat-gpu3-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T223150Z.json`
  at median `64.86390312076414 tok/s`;
- same-window/crossover FP32-scale controls:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-fp32scale-control-gpu2-samewindow-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222647Z.json`
  at median `64.23417302894208 tok/s`, and
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-fp32scale-control-gpu3-crossover-codex-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T222859Z.json`
  at median `64.09039492601592 tok/s`;
- quality:
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
- continuation bookmark:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-continuation-source-and-awq-state.md`.
  It records the latest source-state snapshots, the no-repeat audit for closed
  env/config knobs, and the `cyankiwi/Qwen3.6-27B-AWQ-INT4` strict screen
  closure. The AWQ checkpoint loaded with `--quantization compressed-tensors`
  and passed the fresh/cached-zero gate, but only reached `56.565 tok/s`, so it
  is a no-win versus the `65.276 tok/s` webhie/BF16-scale record. See
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-cyankiwi-awq-int4-screen-no-win.md`.

Current prompt-processing / long-context service baseline:

- note:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-ladder-baseline.md`;
- MBT follow-up:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-mbt-screen.md`.
  Same-window 32K no-parser service screen kept
  `MAX_NUM_BATCHED_TOKENS=4096`: MBT2048 passed but was slower (`22.330s`
  TTFT median, `176.01` approx prefill tok/s), MBT4096 passed (`15.948s`
  TTFT median, `207.91` approx prefill tok/s), and MBT8192 stalled on the
  final long request with no complete gate artifact;
- suite:
  `../../repro/qwen36-27b-autoround-int4-b70/long-context-suite-v1.json`;
- runner:
  `../../experiments/qwen36-27b-autoround-int4-b70/scripts/run-long-context-ladder.sh`;
- classification: service/prefill lane only, not a short-decode headline;
- validation policy: deterministic cold prompts, one request per prompt,
  `cached_tokens=0`, exact JSON retrieval fields passing;
- 32K-capability anchor:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-longctx12288-mml32768-baseline-20260704T061716Z.json`;
  `MAX_MODEL_LEN=32768`, `MAX_NUM_BATCHED_TOKENS=4096`, six rows through
  `17706` actual prompt tokens, exact retrieval pass, TTFT median `22.443s`,
  approximate prefill median `224.67 tok/s`, after-TTFT output median
  `60.19 tok/s`, KV cache size `141,784` tokens, max concurrency `4.33x` at
  32K;
- production-visible service variant: set `QWEN36_27B_REASONING_PARSER=`. The
  32K no-parser content check passed exact retrieval through `17706` actual
  prompt tokens with all rows streaming visible `content` deltas and
  `reasoning_delta_count=0`. Keep it labeled as a service variant and rerun the
  short strict decode suite after any future parser/template change.

Current next-execution plan:

- `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-next-optimization-execution-plan.md`;
- strict candidate runner:
  `../../experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh`.
  Use it for future source/config/checkpoint screens that might become
  headline candidates; it captures the server log, smoke result, fixed Qwen
  realistic suite with token IDs and `cached_tokens=0`, optional quality suite,
  and a compact summary. Synthetic or repeated-prompt diagnostics remain
  separate and must not be submitted as headline throughput;
- Phase 0/1 update:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-phase0-phase1-baseline-and-timing.md`.
  The current record family reproduced at `65.56930784255283 tok/s` median
  generated-token throughput for tokens 1-100 after TTFT, with `cached_tokens=0`
  on all prompts. Fresh timing confirmed the main remaining waste as
  LM-head/logits materialization: `2258` LM-head/logits calls over `540`
  verifier steps (`~4.18` calls/step), with `lm_head_int8.gemm_w8a8` alone
  costing about `10.61 ms` per verifier step under sync instrumentation;
- current focus: the standalone native compact full-vocab LM-head top-1 route
  is now closed no-win. Shift to reducing LM-head call/row count per verifier
  step, improving accepted tokens per target verifier step, or finding a
  oneDNN-integrated top-1/top-k post-op that avoids an extra reduction launch;
- closed Phase 2 precheck:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-lmhead-backend-microbench-no-win.md`.
  Existing Xe2 grouped W8A8 as a single-expert dense LM-head backend is slower
  than oneDNN for rows `1-4` and rejects BF16 weight scales, so do not spend
  endpoint runs on a oneDNN -> grouped-GEMM LM-head swap;
- closed Phase 2 integration precheck:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-spec-greedy-topids-no-headline-win.md`.
  A default-off all-greedy spec verifier path that consumes precomputed target
  top-token IDs passed the strict fresh gate at `65.25583870721442 tok/s`, but
  it did not beat the `65.27648650325429 tok/s` record because current
  `get_top_tokens()` still computes the dense LM-head internally. Keep the
  patch as integration groundwork only; do not retest it as a headline lane
  until a true compact LM-head top-1/candidate-max primitive exists;
- closed Phase 2 kernel precheck:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-compact-lmhead-top1-kernel-no-win.md`.
  `int8_lm_head_top1_w8a8` was buildable and exact versus dense logits on
  synthetic Qwen27 shapes, but the final 8x64 policy still lost to dense oneDNN
  plus argmax (`2.66-2.68 ms` compact vs `2.57-2.61 ms` dense for rows `1-4`).
  Preserve the patch and JSON evidence, but do not wire this op into endpoint
  serving;
- closed candidate-max kernel precheck:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-lmhead-candidate-max-kernel-no-win.md`.
  `int8_lm_head_candidate_max_w8a8` preserved the exact semantics needed by
  target-verified speculation (true top IDs/values plus per-row candidate
  scores) and matched dense logits exactly, but it did not meet the speed gate:
  rows `1,2,3,4` measured `1.010x`, `0.984x`, `0.971x`, `0.961x` versus dense.
  The standalone full-vocab scan plus cross-tile reduction route is now closed
  unless a materially different oneDNN/XPU-integrated primitive is found;
- closed acceptance/depth precheck:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-spec-acceptance-and-adaptive-depth-no-win.md`.
  A strict trace of the current fixed-MTP3 recipe showed the real next
  bottleneck: about `2.70` emitted tokens per verifier step, `0.38`
  full-accept rate, and strong per-prompt speed correlation with acceptance.
  However, scheduler-only adaptive verifier-depth truncation is a no-win:
  aggressive `min1/low1` dropped to `45.748 tok/s`, and same-window
  `min2/low0` / `min2/low1` variants landed at `61.514` / `60.913 tok/s`
  versus fixed-MTP3 baseline `65.986 tok/s`. The patch is preserved as
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-scheduler-adaptive-spec-depth-no-win-20260704.patch`
  and reverted from the active vLLM source;
- closed variant / MTP-layer audit:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-autoround-variant-screening-and-stepidx-audit.md`.
  Same-window strict screens for local AutoRound variants found
  `webhie-Code` at `63.963 tok/s` and `acyildirimer` at `64.326 tok/s`
  versus webhie control `64.813 tok/s`; `poma-ai` passed later at
  `62.951 tok/s`; all are valid no-wins. The webhie no-parser probe was also
  no-win (`64.932` vs parser control `65.179`). The local vrfai FP8 full model
  failed before readiness at `_xpu_C.fp8_gemm_w8a16` with
  `could not set scales primitive attribute`. The possible `spec_step_idx` MTP
  plumbing fix is a no-op for this lane because all checked Qwen27 AutoRound
  checkpoints report `mtp_num_hidden_layers=1`.
- closed current-recipe depth screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-depth-screen-no-win.md`.
  A four-GPU strict same-window pass on the fastest webhie/BF16-scale
  INT8-LM-head recipe confirmed MTP3/cg8 remains best: control `65.809 tok/s`,
  MTP4/cg8 `60.478`, MTP5/cg8 `59.257`, MTP5/cg16 `59.817`, all
  `cached_tokens=0` and gate-passing. Do not promote the `65.809` row; it is
  within variance of the approved `65.276` record and has no recipe change;
- closed current-recipe shallow-depth screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-mtp1-mtp2-depth-coverage-no-win.md`.
  A same-window strict pass filled the MTP1/MTP2 gap on the fastest
  webhie/BF16-scale recipe: MTP1/cg8 `51.246`, MTP2/cg8 `59.589`, MTP3/cg8
  control `64.730`, MTP4/cg8 `59.886`, all `cached_tokens=0` and
  gate-passing. MTP3/cg8 remains the policy;
- closed current-recipe capture-size screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-bf16scale-capture-size-screen-no-win.md`.
  A same-window four-GPU strict pass on the fastest webhie/BF16-scale
  INT8-LM-head recipe confirmed `max_cudagraph_capture_size=8` remains best:
  cg4 `64.507`, cg8 control `65.153`, cg16 `63.500`, cg32 `64.071`, all
  `cached_tokens=0` and gate-passing. Do not retest capture size for this exact
  recipe unless a source change alters graph shapes, row counts, or acceptance;
- closed INT8 GEMM scratchpad ring-size screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-int8-gemm-scratchpad-ring-screen-no-win.md`.
  `VLLM_XPU_INT8_GEMM_SCRATCHPAD_RING_SIZE=4` produced high support rows
  (`65.708`, `65.817`), but same-window crossover against ring1 controls showed
  only `+0.42%` and `+0.27%` median deltas, below the practical variance band.
  Keep the default ring behavior for headline claims; no LocalMaxxing update;
- current webhie/BF16-scale 4-GPU reconfirmation:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-bf16scale-reconfirm4gpu-variance.md`.
  The later high support row (`66.389 tok/s`) did not reproduce; four same-window
  strict reruns landed `63.973-64.741 tok/s`, all gate-passing with
  `cached_tokens=0`. No LocalMaxxing update. Use `~1-1.5%` as the practical
  same-window inconclusive band for this recipe;
- current record reproduction support:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-current-record-repro-support.md`.
  A fresh one-GPU strict run on GPU0 with the approved webhie/BF16-scale recipe
  passed at `65.40973148473643 tok/s`, p10 `58.292274675044496`, mean
  `64.10997285648747`, median TTFT `605.8498464990407 ms`, and
  `cached_tokens=0` on all `12/12` prompts. It is a live reproducibility support
  row only, not a LocalMaxxing update, because the recipe is unchanged and the
  delta over `65.27648650325429` is inside the variance band;
- post-AWQ current record reproduction support:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-post-awq-record-repro-support.md`.
  After the cyankiwi AWQ no-win screen, the same approved webhie/BF16-scale
  recipe passed the strict fresh gate again at `66.12771533602819 tok/s`, p10
  `58.38213638742408`, mean `64.54120315866675`, median TTFT
  `619.981024065055 ms`, and `cached_tokens=0` on `12/12` prompts. This is
  support only: unchanged recipe, no quality rerun, no LocalMaxxing update;
- candidate-runner repro support:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-webhie-runner-repro-support.md`.
  `run-vllm-candidate.sh` reproduced the same recipe at
  `64.84180902803895 tok/s`, strict fresh gate passed, `cached_tokens=0` on
  all `12/12`, smoke passed. Support only; no LocalMaxxing update;
- current source audit:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-lmhead-callcount-source-audit.md`.
  The exact spec top-ID consumer is already present and quality-safe for
  all-greedy requests, but the producer still materializes dense logits:
  `get_top_tokens()` calls the LM-head quant method before `max`, and draft
  greedy sampling calls `compute_logits().argmax()` once per drafted token.
  A Python-level lazy verifier would likely lose because rows `1-4` dense
  oneDNN W8A8 LM-head timings are nearly flat; it would turn one efficient
  rows-4 GEMM into several rows-1 launches. The next credible Qwen27 work is a
  real fused/top-ID LM-head primitive, a native row-adaptive verifier, or deeper
  DFlash multi-KV-group draft metadata support. Treat other Qwen27 config work
  as likely roulette.
- latest explorer synthesis:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-next-optimization-execution-plan.md`.
  Two independent audits agreed that the next useful implementation is not an
  endpoint/config sweep. Public Qwen3.6 27B MTP variants still appear to use
  `mtp_num_hidden_layers=1`, so there is no easy multi-layer MTP knob hiding in
  current checkpoints; oneDNN still exposes dense MatMul/post-op fusion rather
  than an argmax/top-k-emitting LM-head primitive; and partial speculative
  groups remain a broad scheduler/metadata/GDN/graph task. A later arithmetic
  correction in the plan notes says a target-only lazy verifier would save only
  about `0.81 ms/step` (`~65.3 -> ~66.6 tok/s` best case), because draft
  LM-head calls are the larger avoidable bucket; see
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-lmhead-upper-bound-and-priority-correction.md`.
  Corrected ranked lanes:
  (1) oneDNN/XPU-integrated top-ID producer behind `get_top_tokens()` that helps
  both draft and target greedy LM-head calls; (2) target-matched drafter
  calibration on held-out data, with exact target verification; (3) native lazy
  target verifier only if fused with a better producer or pursued as a later
  small cleanup; (4) true partial-group support only if committing to deeper
  metadata/graph engineering.
- draft LM-head batching / DFlash blocker audit:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-draft-lmhead-batching-and-dflash-next-blocker.md`.
  Sequential MTP3 cannot batch the three draft LM-head rows because each next
  draft hidden state depends on the previously sampled draft token. DFlash is
  the real parallel-draft route, but mixed full/sliding attention requires
  full multi-KV-group drafter metadata and future-query block tables; deleting
  the single-KV assertion would risk silent draft-cache corruption. Do not
  repeat draft row batching, local-argmax wrappers, or unsafe DFlash assertion
  removal.
- DFlash mixed-SWA multi-KV attempt:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-dflash-multikv-mixed-swa-attempt.md`.
  A real DFlash multi-KV patch now gets mixed full/sliding DFlash through
  startup and graph capture (`Initialized DFlash draft attention over KV groups
  [64, 65, 66, 67, 68]`), so the old single-KV assertion is no longer the
  first blocker for that patch. Endpoint testing is still closed no-win:
  graph mode device-loses during the strict suite, while graph-off/no-async
  avoids immediate device loss but shows only about `2-3%` draft acceptance and
  single-digit/low-teens generation throughput. Preserve the patch, but do not
  spend more record-chasing time on DFlash mixed-SWA unless draft quality or
  upstream graph stability changes materially.
- held-out calibration trace lane:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-heldout-calibration-trace.md`.
  The benchmark harness now records absolute request windows and deterministic
  request IDs, and `summarize-qwen27-spec-verify-trace.py` can attribute compact
  verifier trace rows back to prompt IDs. The first 24-prompt held-out
  diagnostic run passed cold mechanics (`cached_tokens=0`) at median
  `63.118 tok/s`, with `2.686` target-verified tokens/step and prompt-level
  acceptance/speed correlation `r ~= 0.696`. This is diagnostic-only, not a
  LocalMaxxing result. Use it as the starting point for target-matched drafter
  calibration; keep final-suite prompts isolated from tuning.
- EAGLE1 local training pipeline:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle1-local-training-pipeline-smoke.md`.
  The local pipeline now works end-to-end for Qwen27 hidden size `5120`:
  no-spec hidden dump -> reconstructed async dataset -> compact EAGLE1 training
  -> offline evaluator. The diagnostic corpus has `1536` usable rows,
  `16` samples, and `0` continuity breaks; the 4-sample trainer smoke exported
  a compact draft and offline eval ran. The larger held-out follow-up is
  documented in
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle1-heldout-endpoint-negative.md`.
  It built a four-GPU corpus with `16384` usable rows and trained a draft that
  reached `2.1016` mean accepted tokens on the held-out calibration shard, but
  endpoint EAGLE failed the fixed Qwen realistic suite with repeated-token
  corruption and only `21.7408 tok/s` median over measurable rows. This is not
  a speed result; do not submit or repeat this exact endpoint attempt. Future
  EAGLE work needs larger/diverse non-final training data and stricter held-out
  quality checks before endpoint validation.
- closed EAGLE1 endpoint isolation matrix:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle1-endpoint-isolation-matrix.md`.
  The obvious endpoint controls did not rescue the local EAGLE1 draft:
  current-state eager k3 failed at `19.828 tok/s`, default-state graph k3
  failed at `20.698 tok/s`, and current-state graph k1 still failed at
  `22.410 tok/s`; the current-state graph k3 arm stalled before JSON output.
  The in-repo summary is
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle1-endpoint-isolation-20260704T094450Z-summary.json`.
  Treat this EAGLE1 endpoint lane as closed-negative for now; future EAGLE work
  should start with corpus/eval v2, not more endpoint config sweeps.
- EAGLE corpus/eval v2 tooling:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-tooling.md`.
  The collector can now use suite-driven chat requests with stable request IDs
  and prompt metadata; the dataset builder carries that metadata into samples;
  offline eval reports acceptance by prompt family. This is preparation only,
  not a speed result, but it is the restart point for any future EAGLE work.
- EAGLE corpus/eval v2 chat smoke:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-chat-calib-smoke.md`.
  The calibration-suite chat collection produced `3840` usable rows,
  `24` samples, `0` continuity breaks, and metadata on `24/24` samples after a
  suffix-tolerant request-ID join fix. The tiny draft trained from it reached
  only `0.240` mean accepted offline, so do not endpoint-test it; use the
  metadata path for a larger held-out v2 corpus instead.
- EAGLE corpus/eval v2 four-GPU heldout screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-4gpu-heldout.md`.
  The four-GPU runner collected `96` chat prompts, `15360` hidden rows,
  `96` samples, metadata on `96/96` samples, and `0` continuity breaks. A
  compact draft trained on shards `0-2` reached only `0.489` mean accepted on
  heldout shard `3`, far below the prior `2.1016` offline draft that still
  failed endpoint quality. This draft is not an endpoint candidate; the useful
  result is that corpus v2 collection is healthy and draft quality is now the
  blocker.
- EAGLE corpus/eval v2 followups:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-followups-closed.md`.
  Staged curriculum only reached `0.616` on OOD-family heldout, balanced
  task-holdout reached `0.601`, old strong v1 draft transfer reached `0.201`,
  and all-96 staged training reached only `0.438` on the separate calibration
  suite. These are not endpoint candidates. Current compact EAGLE v2 is closed
  until there is stronger data/training/init or a source/runtime fix.
- EAGLE v2 stronger offline screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-v2-stronger-offline-screen-no-endpoint.md`.
  A bounded four-GPU stronger-draft screen tested larger MLPs plus a residual
  two-layer variant. The best heldout result improved only to `0.6953125` mean
  accepted (`step3` conditional `0.5327`), and all-96-to-calibration scored
  only `0.44091796875`. This remains diagnostic-only; no endpoint test and no
  LocalMaxxing submission.
- closed dynamic-drafter-depth source precheck:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-dynamic-drafter-depth-partial-group-crash.md`.
  Unlike the earlier scheduler-only adaptive-depth patch, this prototype
  actually shortened the MTP proposer loop, but the first partial speculative
  group crashed the XPU verifier path with an `Indexing.h:622` out-of-bounds
  assert. Do not retry variable-depth MTP heuristics until partial groups are
  supported in the Qwen/GDN XPU verifier/metadata path.
- closed DFlash SWA revisit:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-dflash-swa-revisit.md`.
  The local DFlash implementation ignores the draft model's mixed
  `4 sliding + 1 full` layer layout. Honoring that layout exposes a real
  backend gap: `llm_base_proposer.py` assumes all draft layers share one
  KV-cache group and crashes before readiness. A single-group `all-sliding`
  diagnostic remained strict/fresh and `cached_tokens=0`, but collapsed to
  `20.630 tok/s`, so DFlash is still no-win until multi-KV-group draft metadata
  is implemented.
- closed `--language-model-only` screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-language-model-only-no-win.md`.
  The flag saves service memory on the webhie checkpoint (`19.02 GiB` ->
  `18.15 GiB`) and logs text-only mode, but with the current MTP3/cg8 XPU graph
  recipe the server hangs before readiness at decode graph capture. Treat it as
  a service-memory clue only, not a strict decode optimization.
- closed scheduler MBT/chunked-prefill screen:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-scheduler-mbt-and-chunked-prefill-screen.md`.
  `MAX_NUM_BATCHED_TOKENS=768` and `1280` both passed strict/fresh but were
  slower (`64.131` / `64.346 tok/s`) than the approved `65.276` record family;
  disabling chunked prefill is invalid for the current 2048-context / MBT1024
  recipe. Keep MBT1024 and chunked prefill enabled.
- do not resume scale/scope config sweeps, target-only webhie BF16 scope, or
  Python/chunked oneDNN top-1 attempts. Also do not resume scheduler-only
  adaptive-depth heuristics unless the proposer and verifier are both made
  dynamically depth-aware.

Prior Intel-checkpoint quality-gated runtime-quantized variant:

- runtime quantization label: **AutoRound W4A16 + INT8 LM-head**. This is not
  the original BF16-LM-head AutoRound quantization, so keep it separate in
  claims and submissions;
- patch:
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-quality-pass-20260703.patch`;
- config: same promote-source MTP3/cg8 recipe plus
  `VLLM_XPU_LM_HEAD_INT8=1`;
- strict fresh artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-int8lmhead-realistic128-chat-tokenids-qwensuite-20260703T133109Z.json`;
- primary result: median `62.62792826965406 tok/s`, p10
  `58.10368015123676`, mean `62.997843075167445`, TTFT median
  `606.575 ms`, `cached_tokens=0` on every request;
- same-window repeat on GPU3:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-int8lmhead-repeat-gpu3-realistic128-chat-tokenids-qwensuite-20260703T133535Z.json`
  at median `62.276492398420544 tok/s`;
- same-window BF16-LM-head control:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-bf16lmhead-control-gpu2-realistic128-chat-tokenids-qwensuite-20260703T133535Z.json`
  at median `53.33195697867582 tok/s`;
- quality:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-mtp3-cg8-repeat32-ctx1024-20260703T133323Z.json`,
  `pass_all=true`, `baseline_match_all=true`, `long_context_pass=true`;
- compact packet:
  `int8-lmhead-20260703.json`;
- note:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-int8-lmhead-quality-pass.md`;
- LocalMaxxing: approved as `cmr4zkcxb003yq9018408i1pn` with explicit runtime
  INT8-LM-head quantization/mode labeling.

Service-oriented scoped INT8 variant:

- patch:
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-scope-target-quality-pass-20260703.patch`;
- use `VLLM_XPU_LM_HEAD_INT8=1` and
  `VLLM_XPU_LM_HEAD_INT8_SCOPE=target`;
- target-only attribution row:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-scopefix-target-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T140331Z.json`
  at median `61.897978899825404 tok/s`, p10 `57.49406998953655`, mean
  `62.431560666785316`;
- target-only quality:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-targetonly-mtp3-cg8-repeat32-ctx1024-20260703T140623Z.json`,
  `pass_all=true`, `baseline_match_all=true`, `long_context_pass=true`;
- interpretation: the target verifier LM-head dominates the speedup. Draft-only
  INT8 measured `52.858609 tok/s`, essentially BF16 control (`52.707415`).
  Use all-head INT8 for submitted max-throughput rows. This older
  Intel-checkpoint target-only lane passed quality, but the later webhie
  BF16-scale target-only follow-up failed repeat32 stability once, so
  target-only is checkpoint/revision/scale-dtype specific and must be
  revalidated before service or max-context use.

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
- FP8 LM-head is rejected. It reached `64.824 tok/s` on the strict short suite,
  but failed the full 1K long-context quality gate (`B!!!!...` output). Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-fp8-lmhead-quality-rejected.md`.
- Runtime INT8 LM-head is quality-passing and fast. It is not exact BF16
  LM-head math. The older Intel-checkpoint lane passed quality at
  `62.276-62.628 tok/s`; the current fastest quality-gated practical lane is
  the separate webhie BF16-scale variant at `65.27648650325429 tok/s`.
  Continue exact BF16 top-1/candidate-bound research separately if same
  runtime-precision claims matter.
- Older Intel INT8 LM-head follow-ups: MTP depth remained best at k=3
  (`k2=59.162`, `k3=61.921`, `k4=58.372`, `k5=57.401`); capture size remained
  cg8 (`cg32` was noisy at `62.821`, then `61.398`/`63.158` with worse
  p10/mean, and cg16 device-lost). Treat this as historical attribution, not
  the row to beat.
- Later INT8 LM-head source follow-ups did not improve the older `62.628 tok/s`
  Intel strict record. Output-buffer reuse passed the strict gate at
  `62.427810578115064 tok/s` and is no-win; bonus-token argmax fast-path
  reached `62.551370267657624 tok/s` standalone, but same-window A/B measured
  candidate `62.32029632557057` vs control `62.60860919531282`, no-win; the
  draft-only row-count screen collapsed to single-digit tok/s and was
  interrupted as invalid; chunked INT8 top-1 argmax-only verification passed the
  strict gate at `61.40954015865033 tok/s`, no-win; the native compact
  full-vocab `int8_lm_head_top1_w8a8` kernel was exact but slower than dense
  oneDNN. Preserve those patches as evidence, but do not keep them active. The
  useful conclusion is that the next verifier work should reduce LM-head
  call/row count or improve accepted tokens per verifier step, not use
  Python/chunked oneDNN calls, sampler plumbing shortcuts, or standalone
  full-vocab top-1 kernels.
- Latest webhie BF16-scale follow-ups did not improve the `65.27648650325429`
  tok/s row. BF16-scale controls reconfirmed at `64.971` and `64.738 tok/s`;
  FP16 scale storage was slower at `62.902 tok/s`; webhie target-only BF16
  scope reached `64.800 tok/s` with lower TTFT but failed repeat32 quality
  once (`blue, green, red`). Evidence:
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-scale-scope-followup-no-headline-win.md`
  and
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-fused-verifier-top1-design-blocker.md`.
- Variance note for the older promote-source Intel recipe: same-recipe rows are
  `54.861`, `53.992`,
  `53.522`, and `53.608 tok/s` (mean `53.996`, stdev `0.612`, range `2.48%`
  of mean). Treat sub-1% Qwen27 changes as inconclusive unless a same-window
  paired/crossover check supports them.
- The long-lived GPU0 server on port `19410` died during a live reconfirmation
  attempt with `UR_RESULT_ERROR_DEVICE_LOST`. Do not use that failed live
  server result for performance claims. `xpu-smi discovery` later saw all four
  B70s. A fresh single-lane GPU0 control server then passed the strict gate at
  `53.53356374896342 tok/s`, `cached_tokens=0`, confirming the older
  promote-source Intel recipe still reproduces:
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
- prioritize LM-head cost next. The current promoted recipe is no longer
  hitting the traced promoted row-copy helper, and timing shows full logits /
  LM-head work dominates. The INT8 LM-head patch is the current fastest
  quality-gated practical lane; an exact BF16 top-1/candidate-bound kernel is
  still the cleaner same-quantization research goal;
- do not skip full-accept GDN postprocess blindly; it breaks long-context state
  recall. The current win is specifically source-slot promotion plus disabling
  the redundant accepted-state copy, not a semantic elision;
- exact greedy spec argmax-only target verification has been tested and closed
  no-win; do not repeat it unless `get_top_tokens` / LM-head internals change;
- draft proposer local-argmax reduction has been tested and closed flat/no-win;
- draft-only hot-vocab/subset top-1 has been tested and closed no-win. The
  2026-07-04 TP1 patch made Qwen MTP draft proposals use calibration-derived
  hot-vocab INT8 LM-head buffers while leaving target verification exact. A
  same-window strict fresh run passed the gate but lost badly against dense
  control: `65.631 tok/s` control, `50.126` hot512, `52.614` hot1024, and
  `56.418` hot2048/1779-usable. Output hashes matched control on only `11/12`
  prompts. Do not repeat subset-vocab draft approximation; see
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-draft-hot-vocab-top1-no-win.md`;
- deeper wins likely need an AutoRound/INC W4A16 LM-head top-1 or
  candidate-vs-max kernel that avoids materializing full vocab logits;
- for accepted-token / drafter-calibration work, use the compact verifier
  sampler trace, not the scheduler spec trace. Scheduler
  `scheduled_spec_token_ids` are async placeholders (`[-1, -1, -1]`) on this
  XPU path. The useful diagnostic is
  `VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE`, summarized by
  `../../scripts/summarize-qwen27-spec-verify-trace.py`; see
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-verify-trace-for-drafter-calibration.md`.
  A strict traced support run passed at `64.900 tok/s`, with real verifier
  totals: `561` steps, `0.5983` prefix acceptance, `2.795` target-verified
  tokens/step, and `0.4064` full-accept rate. Heavy replay microscope tracing
  wedged after one request and should be kept for narrow single-failure debug,
  not full-suite collection;
- DFlash mixed-SWA was audited and is blocked by a real drafter architecture
  issue, not a config typo. Mixed full/sliding draft attention creates multiple
  KV-cache groups, while the speculative DFlash/EAGLE drafter still assumes one
  `kv_cache_gid`, one block table, and one slot mapping. Do not remove the
  assertion blindly; see
  `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-dflash-mixed-swa-multikv-blocker.md`;
- keep long-context/prompt-processing optimization separate from the short
  decode record.
