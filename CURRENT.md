# Current Promoted Results

Date: 2026-07-02

## Active Workspace

Use `/home/steve/llm-optimizations` as the only active workspace for new
optimization work. It is the branch-attached `main` checkout and should track `origin/main`; run `git status --short --branch` and `git log -1 --oneline` for the exact current head.

Do not run new experiments from `/home/steve/qwen36-results-main`; it is a
detached linked worktree retained for audit/back-reference only. See
`notes/worktree-consolidation-20260701.md`.

## Active Gemma 4 26B A4B Q8 Lane

Current active optimization target:

- Model: Gemma 4 26B A4B instruct, `UD-Q8_K_XL` target GGUF on one Intel
  Arc Pro B70 32GB per replica.
- Goal: maximize **realistic cold-response** single-session decode while
  preserving the Q8 target/verifier quality lane. Synthetic/repetitive prompt
  scores may guide optimization only; they are not headline throughput or
  LocalMaxxing evidence.
- Best strict realistic-suite result so far:
  `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT across the fixed cold prompt suite. Evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.
  It uses llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
  reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
  `cached_tokens=0` on every prompt, and `realistic_final_gate.passed=true`.
- Representative / submitted status:
  the VDR2 selected-down fused weighted-sum path plus FA-on 32K/VMM plus
  final post-norm residual fusion is the current policy-compliant Gemma 26B Q8
  LocalMaxxing submission. The current high is approved as
  `cmr1u77na01k2ld01kalwzs1e`; the prior same-family high
  `123.67689864739785 tok/s` (`cmr01nnet000mld01x2tt6qds`), the prior
  `121.41411987308553 tok/s` (`cmqztiqdn02vnoe01egox6q3f`), the
  `119.94842631460949 tok/s` confirmation row, and the prior
  FA-on 32K/VMM row `cmqzq5zu402troe01t774uyox`, selected-down repeat
  `cmqyrpox4021dqk01co5o4fcw`, and initial selected-down confirmation
  `cmqyo0jyt08ippk01vhiobdnm` remain valid support. The prior LocalMaxxing
  row `cmqxchyra03xmqr01b963gmi1` at `98.34046474459183 tok/s`, prior
  F16-p021 row
  `cmqx3687103v4qr01ace1ft3m`, earlier VDR2 submissions, and prior VDR4
  submission `cmqwnl2ag03lgqr01ch5bxknq` are now superseded.
- Current valid no-spec control:
  `74.29709476830473 tok/s` median on the same realistic suite. Evidence:
  `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`.
  Treat it as the simplest target-side quality/control baseline for new work.
- Latest service/prefill source lane:
  global FlashAttention right-bound is closed negative. The default-off source
  patch built and passed one-case long-context exact JSON validation with
  `cached_tokens=0`, but a four-GPU A/B+crossover on `lc-12288-early` showed
  the candidate regressed mean approximate prefill from `1221.324446` to
  `1206.916212 tok/s` (`-1.179722%`). Do not leave the patch active or promote
  it. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-right-bound-negative.md`
  and
  `data/gemma4-globalrb-comparison-20260702T061900Z-globalrb-onecase.json`.
- Latest service node-profile diagnostic:
  a profiler-only run of the current validated service recipe (`ncols2=8`,
  prefill ubatch `2048`, SWA left-bound min-Q `2048`) intentionally used
  short outputs, so the exact long-context JSON gate failed by truncation and
  this is not a headline result. A follow-up `MAX_TOKENS=1`,
  `CANARY_REPEATS=0` profile confirmed the hotspot is real TTFT/prefill, not
  just decode mixing: after SWA left-bound, full/global FlashAttention layers
  `5/23/17/11/29` dominate at about `55 ms` isolated average each, with global
  GQA shapes like `Q=[512,2,16,1]`, `K/V=[512,256,2,1]`,
  `mask=[256,2,1,1]`. Further service work should target structural global
  FlashAttention tile/scheduling changes for `DKQ=576`, `DV=512`, not more
  SWA/ubatch/right-bound roulette. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-service-nodeprofile-swalb-global-fattn.md`.
- Latest global FlashAttention KQ handoff follow-up:
  the default-off `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1` patch now covers
  both the original `DKQ=512` path and the profiled `DKQ=576`, `DV=512`,
  `ncols=16` global service shape. The DKQ576 extension built and passed a
  four-wave service A/B + crossover with exact long-context JSON validation and
  `cached_tokens=0` on all 48 rows. Candidate vs control improved approximate
  prefill by `+0.722%` mean / `+0.813%` median, TTFT by `-0.765%`, and was
  positive on every GPU and every long-context case. A candidate short-decode
  guard also passed four lanes at `MAX_TOKENS=256`, `CANARY_REPEATS=8`,
  `cached_tokens=0`, with no regression signal. A later full512 short-decode
  A/B isolated `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1` on top of
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`; all eight lanes passed the fixed cold
  gate with `cached_tokens=0`, but the paired median-ratio CI was
  `-2.666% / -0.040% / +3.119%`, decision `no_win`. This is a small
  service/prefill win only, not a LocalMaxxing headline decode result, and KQ
  reg-bcast should not be added to the short-decode record recipe.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-kq-reg-bcast-dkq576-service-win.md`,
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-short-full512-no-win.md`,
  `data/gemma4-global-fattn-kq-reg-bcast-dkq576-comparison-20260702.json`, and
  `data/gemma4-kqregbcast-short-full512-ab-20260702T112211Z-kqregbcast-short-full512-ab.json`.
- Latest hot global FlashAttention scheduler follow-up:
  `GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1` is closed no-win. A default-off
  source patch forced `parallel_blocks=1` only for the profiled global GQA8
  service shape (`DV=512`, `ncols1=2`, `ncols2=8`, `Q=[*,2,16,1]`,
  `K=[*,256,2,1]`, mask present, no `KV_min`) while leaving SWA and decode
  paths alone. The one-case smoke passed exact long-context validation and
  `cached_tokens=0`. The four-wave A/B + crossover on top of the current KQ
  register/broadcast service stack also passed all 48 exact rows with
  `cached_tokens=0`, but improved prefill by only `+0.102%` mean /
  `+0.260%` median, below the service promotion threshold. The source patch was
  reverted exactly and the active binary rebuilt to the baseline
  `libggml-sycl.so.0.15.2` hash
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`.
  Do not retest broad `PARALLEL_BLOCKS=1`; future global FlashAttention service
  work needs a structural tile/scheduling redesign, not another static one-pass
  override. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-hotglobalpb1-service-no-win.md`
  and
  `data/gemma4-global-fattn-hotglobalpb1-comparison-20260702Thotglobalpb1-service-ab1.json`.
- Latest current-service context ladder:
  the validated service recipe (`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`,
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`,
  `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`, `BATCH_SIZE=2048`,
  `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`, `CTX_SIZE=32768`,
  FA on, VMM on) was re-run across all four B70s on the full long-context
  ladder from 512 through 24K target prompt tokens. All 32 long-context rows
  passed exact JSON validation with `cached_tokens=0`; all 64 canary rows
  passed. Average lane median prefill was `1192.965 tok/s`, average lane median
  long-context decode was `131.786 tok/s`; at the longest `32571` actual-token
  case, prefill stayed about `991-1006 tok/s` and decode about `114-115 tok/s`.
  This is the current service/prompt-processing baseline only, not a short
  LocalMaxxing headline. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-current-service-context-ladder.md`
  and
  `data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json`.
- Latest Q-global FlashAttention staging follow-up:
  `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_QGLOBAL=1` is closed negative. The
  default-off source patch built and passed exact one-case long-context
  validation with `cached_tokens=0`, but same-binary same-case control showed
  Q-global regressed prefill from `1232.948` to `1188.722 tok/s` (`-3.59%`),
  decode from `128.226` to `123.438 tok/s` (`-3.73%`), and TTFT by `+3.72%`.
  The active source was restored to the known record-stack hash
  `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3`, and the
  active `libggml-sycl.so.0.15.2` was rebuilt to baseline hash
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`. Do not
  retest Q-global Q staging for this hot shape; direct global Q reloads lose
  more than the saved local-memory staging buys. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-qglobal-qstaging-negative.md`.
- Latest global FlashAttention vec-dispatch follow-up:
  forcing the profiled Gemma global GQA shape (`Q=[512,2,16,1]`,
  `K/V=[512,256,2,1]`) from the current tile path to the existing vec kernel is
  closed negative. The default-off patch built and passed exact long-context
  validation with `cached_tokens=0`, but a four-GPU same-window A/B over
  `lc-12288-early`, `lc-16384-late`, and `lc-22000-middle` regressed paired
  mean approximate prefill by `-0.165%`, decode by `-0.088%`, and TTFT by
  `+0.166%`. The active source was restored; do not promote or retest this
  existing-vec dispatch route. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-vecdispatch-negative.md`
  and `data/gemma4-global-fattn-vecdispatch-comparison-20260702.json`.
- Latest verifier-top2 diagnostic:
  closed as an instrumentation failure, not a performance result.
  The v2 patch built and made the host top2 profile path non-missing, but raw
  records stayed at initialized `-1` values (`top1=-1`, `top2=-1`, NaN logits)
  because the added side tensor was not produced by the active MTP verifier
  graph path. Do not draw LM-head margin, candidate-vs-max, or row-adaptive
  conclusions from this diagnostic. The active llama.cpp source was restored to
  the pre-top2 record stack (`cmp_rc=0`) and rebuilt. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-verifier-top2-v2-instrumentation-failure.md`.
- Post-restore sanity after removing the v2 top2 hooks and rebuilding passed
  the fixed cold gate at `MAX_TOKENS=64`: `16/16` canary rows,
  `cached_tokens=0`, median `124.03008933114222 tok/s` for tokens 1-50 after
  TTFT. This confirms the active binary is back on the promoted lane, but it is
  a compact sanity check, not a full512 record claim. Evidence:
  `data/gemma4-q8-gpu0-post-top2v2-revert-sanity-20260701T201036Z/summary.json`.
- Latest candidate-proof diagnostic:
  `LLAMA_SPEC_VERIFY_CANDIDATE_PROOF_PROFILE=1` is a host-side profile only,
  not a performance result. A compact cold gate (`MAX_TOKENS=64`) passed
  canary and `cached_tokens=0`, with the final cumulative profile line:
  `steps=452`, `verifier_rows=1802`, `draft_rows=1350`,
  `draft_match_rows=1102` (`81.630%`), `full_draft_matches=277`
  (`61.283%`), `missing_sampled_rows=0`, `nonconsecutive_steps=0`,
  `first_mismatch_counts=(0:72, 1:48, 2:59, 3:273)`. This confirms the
  default full-bonus verifier rows are inspectable and often candidate-matched,
  but a draft-candidate-only shortcut is not exact enough because early
  mismatches still require the true target top token. Use this only to guide a
  deeper exact accept-prefix / verifier graph design. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-candidate-proof-profile.md`.
- Latest verifier-lane audit:
  Candidate-bound LM-head proof is not a credible exact shortcut unless it can
  avoid full-vocab Q8 LM-head work; the current design cannot, and exact
  verification still needs the target top token on the first mismatch. A
  follow-up read-only row-semantics audit confirmed there is no small credible
  exact accept-prefix patch in the current architecture: the existing
  `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX` mode is already the simple exact
  row-gated design, and it lost because it serializes per-row LM-head
  launch/reduce work. Future verifier work needs a new non-serial backend
  row-adaptive LM-head path or a mathematically sound candidate-bound
  certificate, not another post-hoc mask or serial accept-prefix variant.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-verifier-row-adaptive-readonly-audit.md`,
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-candidate-bound-lmhead-proof-design.md`,
  and `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-row-economics-profile.md`.
- Latest conditional-bonus verifier follow-up:
  `LLAMA_SPEC_VERIFY_CONDITIONAL_BONUS_ARGMAX=1` is closed negative. The
  tracked A/B lanes were valid fixed cold-suite diagnostics (`cached_tokens=0`,
  canary pass, unchanged Q8 target/verifier), but candidates reached only
  about `101-102 tok/s` versus same-window controls at about `113-116 tok/s`.
  Do not retest conditional bonus, no-bonus, adaptive bonus, late-head,
  prefix-tail, or post-hoc accept-prefix masking without a deeper row-adaptive
  verifier design. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-conditional-bonus-negative.md`.
- Latest accept-prefix top1-epilogue follow-up:
  `LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE=1` plus
  `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` is closed negative. It preserved
  exact target verification and all four A/B lanes passed the fixed cold suite
  with `cached_tokens=0`, but candidates averaged `105.080 tok/s` versus
  controls at `116.498 tok/s` (`-9.80%`). The source was restored exactly to
  the preedit record stack and rebuilt; `libggml-sycl.so.0.15.2` is back to
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`. Do not
  repeat row-by-row accept-prefix variants; future verifier work needs a
  non-serial backend row-adaptive design or a real candidate-bound certificate.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-acceptprefix-top1-epilogue-negative.md`.
- Latest frontier audit:
  a source/flag inventory after the conditional-bonus and global-right-bound
  closures found no hidden easy knob. Adaptive MTP, accept-prefix v1/v2,
  top1-epilogue/partial, sampled-ID pointer/copy variants, post-norm combo,
  draft quant/depth, global fast-mask, global right-bound, and hot-shape
  `nbatch_K` retunes are all closed or non-promotable for the current identity.
  The only credible short-decode frontier is a real backend row-adaptive
  verifier path or a mathematically sound candidate-bound LM-head certificate
  that avoids full-vocab work; the only credible service frontier is structural
  global FlashAttention tile/scheduling work. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-frontier-audit-after-closed-knobs.md`.
- Latest direct-confidence / logit-gap follow-up:
  Tail-only MTP direct-confidence producer is closed negative. A source patch
  made `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES=1` compute top2 score rows only
  at/after `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS`, padding earlier ID-only
  rows so the fixed score-mode stride remained intact. The patch built and all
  four strict128 cold-suite lanes passed with `cached_tokens=0`, but the best
  candidate (`tail3-gap0`) reached only `118.4709837563259 tok/s` versus the
  same-window control at `120.49223560283977 tok/s`, and the real gap-filter
  lane (`tail3-gap050`) reached only `117.52940584638576 tok/s`. Do not
  promote, submit, or continue simple draft-confidence filtering as a record
  lane. The patch/result are preserved, and the active source/binary were
  restored to the pre-experiment record stack. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-tail-only-direct-confidence-negative.md`.
- Latest post-norm combo MTP follow-up:
  The only bounded follow-up from no-spec calibration was tested in a four-GPU
  same-window MTP full512 run. All lanes passed the fixed realistic gate with
  `cached_tokens=0`, but the combo remained inconclusive and below the current
  record: controls `116.787` / `113.962`, combo-on `117.227` / `115.861`,
  paired 95% CI `-2.754% / +0.395% / +3.346%`. Do not promote or submit.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-postnormcombo-mtp-followup.md`.
- Latest no-spec target-side calibration batch:
  Paired no-spec A/B closed packed GEGLU all as `no_win`
  (`-1.046% / -0.858% / -0.570%`) and confirmed the LM-head subgroup closure.
  Attention post-norm (`+0.431% / +0.804% / +1.119%`) and the final +
  attention + per-layer post-norm combo (`+0.744% / +1.014% / +1.292%`) are
  small target-side positives but below the `+1%` lower-bound promotion rule.
  The post-norm combo is the only eligible bounded MTP same-window follow-up; do
  not submit or promote no-spec-only results. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-nospec-retest-candidates.md`.
- Latest post-clean no-spec anchor:
  Four GPUs passed the fixed realistic cold suite with `cached_tokens=0`,
  canary pass, and `realistic_final_gate.passed=true`; lane medians were
  `76.923`, `76.718`, `76.289`, and `76.682 tok/s`, average `76.653 tok/s`,
  spread `0.828%`. Use this as the current low-variance target-side
  micro-change reference, not as a headline record. Evidence:
  `data/gemma4-nospec-anchor-20260702T045339Z-nospec-anchor.json` and
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-fattn-nbatchk-and-nospec-anchor.md`.
- Latest LM-head subgroup calibration:
  `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS=2` is closed by the lower-variance
  no-spec calibration workflow. The candidate and controls all passed the fixed
  realistic final gate with `cached_tokens=0`, but paired prompt analysis gave
  a median-ratio 95% CI of `-0.649% / -0.338% / -0.073%`, decision `no_win`.
  Do not retest the LM-head one-column subgroup family, DMMV, or no-reorder
  variants unless a future source change materially alters the kernel shape.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-lmhead1col-subgroups.md`
  and `data/gemma4-q8-nospec-lmheadsg2-ab-20260701T140828Z.md`.
- Latest sampled-ID egress follow-up:
  `LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS=1` is a closed negative /
  incomplete implementation. The first parity smoke passed only because the
  parity check ignored `LLAMA_TOKEN_NULL`; the stricter diagnostic showed
  direct sampled IDs stayed `-1` while copied sampled IDs were valid, and
  `LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_SKIP_COPY=1` crashed the sampler
  because logits are not exported in backend-argmax mode. Backend-copy and
  pre-allocation `op_params` variants rebuilt and passed canaries, but still
  failed strict parity (`356` and `355` mismatches respectively: direct `-1`,
  copied token valid). The failed source hooks were removed from the active
  llama.cpp checkout, rebuilt, and sanity-checked with a compact cold gate
  (`32/32` canary, `cached_tokens=0`, median tokens 1-50 `120.302963`). Do not
  enable skip-copy, and do not keep retesting pointer-only `op_params` variants
  without a producer-side graph/output design. Any future version must patch the
  actual sampled-row producer and prove null-sensitive direct-vs-copied parity
  first. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-direct-sampled-egress-negative.md`.
- Latest prompt-processing source follow-up:
  DV512/Gemma GQA hot-shape `nbatch_K` retune is closed as valid but noise.
  For `DKQ=576`, `DV=512`, `ncols=16`, baseline `nbatch_K=64`, both
  `nbatch_K=32` and `nbatch_K=128` passed eight-lane long-context A/B +
  crossover with exact JSON validation and `cached_tokens=0`, but improved
  prefill by only about `+0.1%` (`+0.082%` / `+0.139%` median-prefill average),
  far below the `+1.5%` service-lane promotion threshold. Do not retest these
  constants for the current FlashAttention kernel. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-fattn-nbatchk-and-nospec-anchor.md`
  and `data/gemma4-fattn-nbatchk-sweep-20260702.json`.
  A compact post-restore GPU0 sanity then passed the fixed cold gate with
  `cached_tokens=0`, `64/64` canary rows, and median tokens 1-50 after TTFT
  `120.296 tok/s`; this is restore evidence only, not a full512 record claim.
  Evidence:
  `data/gemma4-q8-gpu0-postnbk-restore-sanity-20260702T053257Z-postnbk-restore-sanity/summary.json`.
- Latest spec-profile diagnostic:
  `LLAMA_SERVER_SPEC_PROFILE=1` on the current Gemma Q8 record recipe passed
  the fixed cold realistic gate (`cached_tokens=0`, `32/32` canary rows) but
  reached only `117.22735440926772 tok/s` median for tokens 1-100 after TTFT,
  below the current `124.97714084813418 tok/s` record. The useful breakdown is
  that draft/process/sample/accept overheads are negligible, while target
  generation (`20.005 ms/call`) and prompt/prefill (`74.929 ms/call`) dominate.
  Treat this as diagnostic evidence only. It supports focusing next on exact
  FlashAttention right-bound / KV-max service work or a real backend
  row-adaptive verifier design, not on more MTP wrapper/config roulette.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-spec-profile-and-next-lanes.md`
  and
  `data/gemma4-q8-gpu0-specprofile-20260702T053810Z/summary.json`.
- Latest node-profile diagnostic:
  a profiler-only refresh of the current record stack also passed the fixed
  cold gate (`cached_tokens=0`, `16/16` canary rows), but is diagnostic only:
  `GGML_SYCL_NODE_PROFILE=1` disables SYCL graph execution and the run used
  `MAX_TOKENS=128`, so its `76.928 tok/s` median is not a LocalMaxxing or
  record claim. The useful signal is hotspot order. The final profile block
  shows the target/verifier full-vocab LM-head as rank 1
  (`MUL_MAT:node_1715`, `817.753 ms` total), followed by MoE gate-up and three
  separate MTP draft argmax LM-head nodes:
  `mtp_direct_argmax_unroll_token_0/1/2` at about `239-240 ms` each. Log detail
  shows the draft output weights are `q6_K`. Host bookkeeping and verifier sync
  remain negligible (`0.394 ms` total sync over `512` calls). A follow-up source
  audit found the backend already supports multi-column `MUL_MAT_ARGMAX`, but
  these three draft heads are autoregressive and cannot be naively batched:
  token 0 feeds step 1, and token 1 feeds step 2. Future draft work needs a new
  single-node `q6_K` argmax kernel design or a different draft algorithm, while
  verifier LM-head reduction remains high-risk unless it is exact and
  non-serial. The bounded current-record screen of
  `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16` on the draft path is closed
  no-win: all 8 full512 lanes passed with `cached_tokens=0`, but paired
  median-ratio CI was `-2.594% / +0.001% / +4.021%` and no candidate beat the
  `124.977 tok/s` record.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-recordstack-nodeprofile-hotspots.md`,
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-argmaxtile16-draft-q6k-no-win.md`,
  and `data/gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z/summary.json`.
- Prior prompt-processing source follow-up: DV512 Gemma GQA `ncols2=16` is a
  closed negative. The default-off source branch rebuilt, but both candidate
  lanes failed the first JSON canary with empty text before long-context cases
  could run. The validated `ncols2=8` service/prefill lane remains the current
  safe path. The active llama.cpp source was restored to the preedit record
  stack and rebuilt; `llama-server --version` reports `c926ad098`, and the
  failed branch is absent. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-fattn-dv512-gqa-ncols16-negative.md`.
- Latest post-clean baseline/service confirmation:
  `20260702-postclean-baseline-swalb-service-confirm.md` re-established the
  clean-workspace Gemma state. Exact MTP record recipe passed on all four GPUs
  but averaged `114.483 tok/s` in this window (normal MTP variance below the
  historical `124.977` high). The no-spec calibration lane was very tight at
  `76.804 tok/s` average with only `0.35%` range, so use it for target-side
  micro-change comparisons. The long-context service recipe
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` + phase prefill `2048/1024` +
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048` reconfirmed a
  `+6.927%` median-prefill win with exact JSON validation, `cached_tokens=0`,
  and no short-decode regression signal. This is a service/prefill result, not
  a LocalMaxxing short-decode headline.
- Recent non-promoted follow-up:
  `LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1` was valid and trimmed real terminal
  draft work, but four full512 lanes topped out at `113.58569073629727 tok/s`,
  below the current `124.97714084813418` record. Late-head bonus plus
  `LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1` lost strict128. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-eogclip-and-spechead-negative.md`.
  Fusing selected-softmax directly into selected-down VDR2 was a valid
  strict128 small positive (`115.554` best flag-on), but the full512 promotion
  screen lost: best flag-on primary median was `111.90908727268967 tok/s`
  with EOG clip and `111.89648891729823 tok/s` without it, below both same-day
  controls and the current `124.97714084813418` record. It is preserved
  default-off and not submitted. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-down-selected-softmax-strict128.md`
  and
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-selected-softmax-full512-negative.md`.
  Adaptive bonus-row skipping was also tested on 2026-06-29 with three exact
  thresholds. All lanes passed the cold strict128 gate, but the best adaptive
  lane reached only `109.5558044655227 tok/s` versus the same-build control at
  `112.02098406811635 tok/s`, with worse p10 and full-output speed. It is a
  closed negative; do not full512-confirm or submit it. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-adaptive-bonus-row-negative.md`.
  Deferred verifier pending-`h` copy
  (`LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY=1`) was then tested with a paired
  strict128 screen plus cross-over. All lanes were valid cold-suite runs, but
  the apparent `118.10959835079939 tok/s` flag-on outlier did not survive the
  cross-over: control medians averaged `114.45317635681107`, flag-on medians
  averaged `112.421810001393`. It is a closed negative; do not full512-confirm
  or submit it. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-defer-verifier-pending-h-copy-negative.md`.
  Exact LM-head candidate-vs-max plumbing was audited next. The verifier row
  mapping is usable in the narrow full-output MTP shape, but the design is not
  a current record lane because exact speculative verification still needs the
  true target top token on mismatch, which preserves the expensive full-vocab
  max/challenger work. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-candidate-threshold-lmhead-no-go.md`.
  Fused-down selected-softmax precompute was tested next as a source patch
  against the previously negative `LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1`
  lane. It passed strict128 and full512 validity but lost: full512 candidate
  medians were `114.99472751325114` and `119.55472070939985 tok/s` versus
  same-build controls at `119.83691077465154` and `121.35664372753011 tok/s`.
  The backend hunk was reverted and the patch/results are preserved. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-down-selected-softmax-precompute-negative.md`.
  VDR2 selected-down `ROWPACK=2` was then tested as a narrower source patch
  that packs two output rows per workgroup. It is valid but rejected for the
  short-context headline metric: the full512 cross-over primary medians were
  `119.75026683034108` and `110.62392954093656 tok/s` with rowpack=2 versus
  same-window controls at `120.62626200287556` and `117.70674646289913 tok/s`.
  It improved full-output/window throughput, so keep it as a possible service
  lane idea, but not as the current 1-100-token record path. The active source
  hunk was reverted; patch/results are preserved in
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-vdr2-selecteddown-rowpack2-negative.md`.
  A rebuilt record-identity spec profile was then captured under
  `LLAMA_SERVER_SPEC_PROFILE=1` / `LLAMA_MTP_DRAFT_PROFILE=1`. It passed the
  fixed cold gate with `cached_tokens=0`, but is diagnostic only. It confirms
  target/verifier graph work dominates (`target_decode_ms=38529.540` vs
  `draft_ms=2665.342`); `sampled_extract_ms=1665.262` is the sampled-token
  backend read/sync boundary and should not be treated as a simple copy-size
  issue. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-record-refresh-specprofile.md`.
  A follow-up default-off sync-profile wrapper measured the later accept-side
  verifier `llama_synchronize(ctx)` at only `1.734 ms` over `896` calls
  (`0.002 ms/call`), confirming that sampled extraction cost is not in the
  sampler accept loop. A row-economics diagnostic then measured the best-case
  output-row savings for an oracle adaptive verifier shape:
  `rows_current=3679`, `rows_oracle=2893`, `rows_saved=786`
  (`21.365%`), with `full_match_with_bonus=541/921` steps. It passed the cold
  gate and canary, but remains diagnostic only. It rules out simple bonus-row
  removal as a record path and points only to a bonus-preserving row-output
  design or deeper verifier graph/MoE work. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-row-economics-profile.md`.
  A final-record FA-on 32K/VMM UBATCH screen then tested `UBATCH_SIZE=768`,
  `896`, `1024` control, and `1152`. The strict128 pass made `BATCH_SIZE=1152`,
  `UBATCH_SIZE=1152` look promotion-worthy (`121.24708378127268 tok/s`), but
  the paired full512 confirmation closed it: all lanes stayed valid, candidate
  average was `117.36308529017367 tok/s` versus paired-control average
  `114.3071667009025`, and the best candidate was `118.43353215490006`, still
  below the `124.97714084813418` headline. Do not change the recipe or submit
  it. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-faon-vmm-ubatch-screen.md`.
  A verifier row-shape audit followed. The apparent one-column Q8 LM-head node
  profile detail is not a simple row-coalescing opportunity: a verbose
  `LLAMA_BATCH_DEBUG=1` diagnostic showed the standard full-bonus MTP verifier
  path already uses `n_tokens=4`, `n_outputs=4` microbatches. The SYCL node
  profiler keeps the first detail it saw for a node name, often a one-output
  prompt/decode graph. The remaining exact row-output idea is a deeper
  accept-prefix verifier LM-head backend op, not a config knob. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-verifier-row-shape-and-accept-prefix-audit.md`.
  A final small FA-on 32K/VMM p_min gap screen tested `0.04625`, `0.04725`,
  `0.047625`, and `0.04875` under the current selected-down VDR2 strict128
  identity. All lanes passed, but the best candidate was `0.047625` at
  `118.41776692242152 tok/s`, below matching-stack `0.0475` controls
  (`119.79709987498046` / `119.51944277144372`). This closes the remaining
  threshold-only gap; do not full512-confirm or submit. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-faon-vmm-pmin-gap-screen-negative.md`.
  A four-lane full512 repeat of the current promoted recipe then passed the
  strict cold final gate and 128/128 canary on every lane, but did not beat the
  record: medians were `118.21311630972258`, `117.71732552906994`,
  `114.87763475869593`, and `112.94544241316387 tok/s`. This is
  variance/no-new-record; do not submit. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-record-repeat-full512-variance.md`.
  Final post-FFN RMS norm + residual fusion
  (`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`) was then retested on the
  FA-on 32K/VMM selected-down VDR2 identity. It passed strict128, cross-over,
  and full512 validity. The best full512 lane reached the current valid record
  `123.67689864739785 tok/s` and LocalMaxxing approved it as
  `cmr01nnet000mld01x2tt6qds`. Paired full512 averages were noisy but positive
  for the flag (`120.11414175477651` vs controls `116.29133772533568`);
  repeat confirmations should continue before treating the GPU0 jump as the
  expected effect size. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-final-postnorm-fusion-screen.md`.
  A later exact reproduction after the LM-head/Q8 subgroup experiment matched
  the promoted full512 identity (`512/512` canary rows, `cached_tokens=0`,
  LM-head subgroup unset) and reached the new valid high
  `124.97714084813418 tok/s` on GPU0. Same-batch support lanes were
  `121.59076340768573`, `119.26425148518223`, and
  `113.63257982764395`. LocalMaxxing approved the new row as
  `cmr1u77na01k2ld01kalwzs1e`. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-reproduction-check.md`.
  A same-GPU thermal follow-up then ran four exact GPU0 full512 repeats with
  privileged `xpu-smi dump` telemetry. All passed the fixed cold gate,
  `cached_tokens=0`, and 512/512 canary; medians were `115.515`, `119.019`,
  `114.520`, and `120.202 tok/s`. Active core max stayed `77-78 C`, memory max
  `86-90 C`, frequency stayed near max, and no thermal-throttle samples
  appeared, so current variance is not explained by simple temperature
  throttling. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`.
  The reliability method is now explicit:
  `scripts/analyze-gemma-realistic-ab.py` compares prompt-paired A/B runs with
  bootstrap CIs, and
  `results/gemma4-26b-a4b-q8-b70/reliability-protocol.md` requires a paired
  bootstrap lower bound above `+1.0%` before promoting micro-changes. Same
  thermal repeats show `2.324%` run-median CV and `4.409%` p90 pairwise
  absolute run-median delta, so `+1-4%` single-run spikes are not actionable.
  A four-lane full512 repeat of the promoted final-postnorm recipe then passed
  the strict cold gate and 512/512 canary on every lane but did not beat the
  record: medians were `118.78941183022032`, `115.48824790393866`,
  `112.71902407241845`, and `116.80124865921995 tok/s`. This is valid
  variance/no-new-record support; do not submit. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-finalpost-repeat2-full512-variance.md`.
  The analogous attention post-norm residual fusion
  (`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1`) was tested next as a
  default-off source patch after fixing harness flag capture. All strict128
  lanes passed the cold gate and 512/512 canary, but it lost on the primary
  short metric: controls averaged `119.3616057307415 tok/s`, flag-on lanes
  averaged `116.75359048324216 tok/s`. It improved full-output medians in that
  screen, so keep only as a possible service/full-output idea. Do not full512
  confirm or submit for the short record. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-attn-postnorm-residual-fusion-negative.md`.
  The analogous per-layer embedding post-norm residual fusion
  (`LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`) was tested next after
  snapshotting the source and wiring the harness metadata. All four strict128
  lanes passed the cold gate and 512/512 canary, but the effect was too small
  and GPU-dependent for promotion: controls averaged `115.80942063480597 tok/s`,
  flag-on lanes averaged `116.81238861292647 tok/s`, and the best flag-on lane
  (`119.96280008214512`) stayed below the `124.97714084813418` record. Keep the
  flag default-off, preserve the patch/results, and do not submit or full512
  confirm for the short record unless a future service/full-output lane needs
  it. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-perlayer-postnorm-residual-fusion-inconclusive.md`.
  An accept-prefix parity probe followed as design proof for a possible future
  backend verifier LM-head op. `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY=1`
  reconstructs the accepted token vector from backend sampled verifier rows and
  checks it against the existing sampler accept path on the full-bonus MTP
  shape. The first strict helper incorrectly required `n_draft == 3` and failed
  valid short-tail steps; the rebuilt helper accepts any full-bonus tail with
  `n_draft > 0`, consecutive verifier rows, and `spec_i_batch.size()` equal to
  `n_draft + 1`. The validated full512 run passed the fixed cold gate,
  `cached_tokens=0`, and 128/128 canary at `117.60357286123875 tok/s`, below
  the record, so it is diagnostic only and not a LocalMaxxing candidate. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-accept-prefix-parity-probe.md`.
- Current context/service diagnostic split:
  with flash attention off, MTP remains useful through about `ctx24576` /
  `ctx25600`, degrades near `ctx26624`, and cliffs by `ctx27648`. With
  `FLASH_ATTN=on`, the MTP cliff is removed and true `ctx32768` reaches about
  `103 tok/s` after TTFT on the synthetic ~11K-token diagnostic prompt, with
  `cached_tokens=0`. Keep the short-record recipe unchanged unless FA-on passes
  the fixed realistic gate. These are service/context diagnostics, not
  LocalMaxxing headline records. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-context-threshold-mtp-vs-nospec.md`.
  The first FA-on 32K/VMM prefill ladder for the current record stack is now
  recorded in
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ladder-baseline.md`.
  It used `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, unique long prompts, 16-token
  outputs, `cached_tokens=0`, and canary pass on every row. Approx prefill
  throughput peaked around `~1.09K-1.11K tok/s` for 2.9K-5.6K actual prompt
  tokens, stayed `~1.07K tok/s` at 8.1K actual tokens, then declined to
  `955.9`, `887.7`, and `794.2 tok/s` at 12.1K, 16.2K, and 21.5K actual tokens.
  Treat this as the baseline for service-lane batch/ubatch screens; do not
  submit it or infer a short-decode record from it.
  Follow-up service UBATCH screen:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ubatch-service-screen.md`.
  `BATCH_SIZE=2048`, `UBATCH_SIZE=2048` is the best general long-prefill
  candidate tested so far, improving approximate prefill versus UB1024 by
  `+10.8%`, `+9.2%`, `+7.4%`, and `+6.1%` at 8.1K, 12.1K, 16.2K, and 21.5K
  actual prompt tokens. UB2560 is only a possible very-long-prompt follow-up;
  UB3072 is a valid regression boundary. The follow-up fixed realistic
  cold-suite control passed for UB2048 with `cached_tokens=0` and no observed
  short-decode regression: UB2048 averaged `118.30159066915866 tok/s` versus
  UB1024 controls at `116.46794311469674 tok/s`. It still did not beat the
  active `124.97714084813418 tok/s` record, so keep the promoted short-record
  reproduction on UB1024 and treat UB2048 as a validated service/default
  candidate. A repeat UB2048-vs-UB2560 confirmation at 12K- and
  16K-requested long prompts kept that decision: UB2048 wins the
  12K-requested shape and is an effective prefill tie at the 16K-requested /
  ~21K actual-token shape while decoding faster, so do not standardize on
  UB2560. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-ub2048-short-suite-control.md`
  and
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ub2048-vs-ub2560-confirm.md`.
- A stricter fixed long-context service gate now exists:
  `repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json`,
  `scripts/bench-openai-long-context-suite.py`,
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`, and
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh`. The paired
  long-context suite through `22730` actual prompt tokens passed exact JSON
  retrieval, `cached_tokens=0`, and canaries on all lanes; UB2048 averaged
  `1013.884` median approximate prefill tok/s versus UB1024 at `936.865`
  (`+8.22%`). The corrected near-32K boundary case at `30400` actual prompt
  tokens also passed after increasing `MAX_TOKENS` from `64` to `96`; UB2048
  averaged `701.487` versus UB1024 at `661.905` (`+5.98%`). A paired full512
  fixed short-suite guard passed on all lanes and did not show a decode
  regression (`119.153` UB2048 average versus `116.402` UB1024), but it did
  not beat the `123.67689864739785` short record. Decision: UB2048 is the
  validated long-context/prefill service candidate; keep UB1024 for short-record
  reproduction. Follow-up heavy-context cross-over screens at `16213`, `22730`,
  and `30400` actual prompt tokens showed UB2560 has the best narrow prefill
  number (`835.782` combined median prefill tok/s versus UB2048 at `815.106`),
  but UB2560 and UB2304 both lost enough short-suite throughput in their
  follow-up guards that they remain diagnostics only. A profiled UB2048
  near-32K row showed the prompt path is dominated by `FLASH_ATTN_EXT` /
  KV-cache attention work, not verifier LM-head or MoE selected-down kernels.
  Next service work should target attention/prefill source behavior, while
  keeping the short-record recipe untouched. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-long-context-prefill-service-gate.md`.
  Follow-up source work found the first large service-prefill win:
  a default-off SYCL FlashAttention tile selector patch
  (`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`) for Gemma full-attention
  `DV=512` / GQA8 layers. On the cold `30400` actual-token JSON retrieval
  case, same-build GPU crossover improved mean prefill from `702.605` to
  `947.589 tok/s` (`+34.87%`) with identical output hash and `cached_tokens=0`.
  The broader three-case gate passed at `16213`, `22730`, and `30400` actual
  prompt tokens; median prefill was `1039.603 tok/s` for UB2048, `1075.983`
  for UB2304, and `1066.029` for UB2560. Short fixed-suite guards passed, but
  did not beat the active `124.97714084813418 tok/s` short record, so this is
  promoted only as a service/prefill patch. Keep UB1024 for short-record
  reproduction; use UB2048 as the balanced long-service setting and UB2304
  only for pure prefill. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`.
  Follow-up KV-max mask pre-scan testing is closed negative: disabling
  `flash_attn_mask_to_KV_max` with
  `GGML_SYCL_FATTN_KV_MAX_SCAN_MIN_Q=-1` passed exact validation and
  `cached_tokens=0`, but regressed the same `30400` actual-token prefill from
  `955.2365` to `862.9161 tok/s` (`-9.7%`). Keep the scan enabled. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`.
  Follow-up forced-`ncols1` testing inside the same GQA8 tile path is also
  closed negative: paired controls at the implicit `ncols1=2` path measured
  `953.0630` and `950.5813` prefill tok/s, while forced `ncols1=1` measured
  `821.6392` and forced `ncols1=4` measured `856.8965`. Keep the implicit
  `ncols1=2`; do not force `GGML_SYCL_FATTN_DV512_GQA8_NCOLS1`. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.md`.
  Follow-up compile-time retuning of the selected GQA8 FP16 tile from
  `nbatch_fa=64` to `128` is also negative/noise: four valid lanes averaged
  `951.5273 tok/s` prefill with per-lane results `953.3767`, `944.6846`,
  `955.1166`, and `952.9311`, matching the same-case controls. Keep
  `GGML_SYCL_FATTN_TILE_CONFIG_CASE(576, 512, 16, 256, 2, 64, 64)`. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`.
  Phase-specific prefill ubatch was then screened as a source/service patch.
  The v1 context-only patch is closed negative because
  `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`,
  `LLAMA_PREFILL_UBATCH_SIZE=2048` hit repeated KV retry fallback and dropped
  to `880.2510 tok/s` prefill. The v2 patch also sizes SWA/ISWA attention
  memory with `max(n_ubatch, n_ubatch_prefill)`, removed retries, and is valid:
  `2048/1024 + prefill2048` measured `956.7217 tok/s` long-prefill,
  `112.9063 tok/s` long-context decode, and `120.8849 tok/s` on the short
  guard. It is useful service evidence but not a new LocalMaxxing candidate
  because it does not beat the `124.97714084813418 tok/s` short record.
  `prefill2304` and `prefill2560` were valid but not better balanced. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md`.
- Current diagnostic best, not a real-world headline:
  `176.21623213048554 tok/s` after TTFT on the first no-cache synthetic
  filled-long benchmark row, `176.40259133127742 tok/s` supporting repeat mean,
  `1536` canary repeats / `6144` rows passed, LocalMaxxing
  `cmqwkedg303jeqr013z753j62`. Under the stricter final gate this is
  synthetic/diagnostic only and should not be promoted further or resubmitted.
  Its VDR2 setting won synthetic filled-long; the strict VDR2 result above is
  the separate realistic-suite promotion path and uses `n_max=3` rather than
  the synthetic `n_max=7` diagnostic recipe.
- Result packet: `results/gemma4-26b-a4b-q8-b70/README.md`.
- Current record note:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-final-postnorm-fusion-screen.md`.
- Reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`.
- Validation rules: `results/gemma4-26b-a4b-q8-b70/validity-gates.md`.
- Current research plan: `results/gemma4-26b-a4b-q8-b70/research-plan.md`.

Do not promote the earlier `ngram-mod` `245-280 tok/s` rows, the synthetic
filled-long `170+ tok/s` rows, or any repeated-prompt average as real-world
throughput. They are diagnostic artifacts unless the fixed realistic prompt
suite passes with `cached_tokens=0` on every prompt.

Short-decode status: the reliable `>100 tok/s` target is already broken. Avoid
more Gemma config roulette. The accept-prefix parity mode is now validated as a
sampled-row invariant check; it is not itself a speed path. The next
short-record source lane is the actual backend accept-prefix verifier LM-head
op, or a distinct profile-backed verifier/MoE boundary reduction. Otherwise,
work on a separate prefill / long-context service lane and rerun the short fixed
suite afterward to prove no regression.

## Historical MiniMax M2.7

Date: 2026-05-19

Current strict quality-passed speed result:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM `0.20.1-local`, XPU TP4
- Recipe: FP16 activations, AutoRound INT4 W4A16, default XPU FlashAttention v2, XPU PIECEWISE graph, exact MiniMax router-logits path feeding llm-scaler INT4 MoE work-sharing decode with `VLLM_XPU_USE_LLM_SCALER_MOE_WS=1`, `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`, `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0`, clone-safe compiled allreduce custom-op via `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1` plus `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1`, direct in-place Q/K variance allreduce+scale via `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1`, final MoE output allreduce moved inside the MoE custom-op boundary via `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1`, and decode-sized router-linear plus fused MoE wrapped in a guarded MiniMax full-forward custom-op boundary via `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1` with `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`
- Shape: p512/n1536, ctx2048, batch 1
- Result: `89.314195` output tok/s, `119.085594` total tok/s, mean of four clean long repeats
- Output tok/s repeats: `[88.927239, 89.396677, 89.527321, 89.405544]`
- Quality: raw145 exact n64/n256 hashes, semantic suite, 16-repeat arithmetic, and extended sixpack all passed before benchmarking
- Delta: `+0.43%` output tok/s over the previous strict high (`88.927945`) and `+10.81%` over the earlier MoE-WS FlashAttention/PIECEWISE baseline (`80.602755`)
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

Primary artifacts:

- Current strict clean high: `notes/2026-05-19-minimax-moe-full-forward-customop-plus-output-ar.md`, `data/minimax-m27-moe-full-forward-customop-plus-output-ar-20260519.json`, `data/localmaxxing-minimax-m27-autoround-moe-full-forward-customop-plus-output-ar-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-moe-full-forward-customop-plus-output-ar-p512n1536-20260519.response.json`, `patches/minimax-moe-full-forward-customop-plus-output-ar-20260519.md`
- Previous MoE output-allreduce custom-op high: `notes/2026-05-19-minimax-moe-output-allreduce-inside-customop.md`, `data/minimax-m27-moe-output-allreduce-inside-customop-20260519.json`, `data/localmaxxing-minimax-m27-autoround-moe-output-allreduce-inside-customop-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-moe-output-allreduce-inside-customop-p512n1536-20260519.response.json`, `patches/minimax-moe-output-allreduce-inside-customop-20260519.patch`
- Current clean direct Q/K variance follow-up: `notes/2026-05-19-minimax-qk-direct-inplace-scale.md`, `data/minimax-m27-qk-direct-inplace-scale-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qk-direct-inplace-scale-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qk-direct-inplace-scale-p512n1536-20260519.response.json`, `patches/minimax-qk-direct-inplace-scale-20260519.patch`
- Cleaner Q/K-helper follow-up: `notes/2026-05-19-minimax-qk-helper-tinyfp32-inplace.md`, `data/minimax-m27-qk-helper-tinyfp32-inplace-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qk-helper-tinyfp32-inplace-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-qk-helper-tinyfp32-inplace-20260519.response.json`
- Cleaner alias-correct tiny-FP32 in-place path: `notes/2026-05-19-minimax-qkvar-inplace-fp32n2.md`, `data/minimax-m27-qkvar-inplace-fp32n2-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qkvar-inplace-fp32n2-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qkvar-inplace-fp32n2-20260519.response.json`, `patches/minimax-qkvar-inplace-fp32n2-20260519.patch`
- Previous warning-prone speed headline: `notes/2026-05-18-minimax-qkvar-skipclone-fp32n2-win.md`, `data/minimax-m27-qkvar-skipclone-fp32n2-win-20260518.json`, `data/localmaxxing-minimax-m27-autoround-qkvar-skipclone-fp32n2-p512n1536-20260518.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qkvar-skipclone-fp32n2-p512n1536-20260518.response.json`, `patches/minimax-qkvar-skipclone-fp32n2-20260518.patch`
- Recent Q/K helper guard rejections: `notes/2026-05-19-minimax-qk-helper-max1-currenthigh-quality-fail.md`, `data/minimax-m27-qk-helper-max1-currenthigh-quality-fail-20260519.json`, `notes/2026-05-19-minimax-qk-helper-max2-currenthigh-negative.md`, `data/minimax-m27-qk-helper-max2-currenthigh-negative-20260519.json`
- QKV narrow-split negative: `notes/2026-05-19-minimax-qkv-narrow-split-negative.md`, `data/minimax-m27-qkv-narrow-split-negative-20260519.json`, `patches/minimax-qkv-narrow-split-negative-20260519.patch`
- Current-high CCL fabric-vertex override rejection: `notes/2026-05-19-minimax-currenthigh-ccl-fabric-vertex-off-negative.md`, `data/minimax-m27-currenthigh-ccl-fabric-vertex-off-negative-20260519.json`
- Current-high skip-contiguous rejection: `notes/2026-05-19-minimax-currenthigh-skip-redundant-contiguous-negative.md`, `data/minimax-m27-currenthigh-skip-redundant-contiguous-negative-20260519.json`

Previous promoted MiniMax baselines:

- MiniMax MoE full-forward custom-op high: `89.314195` output tok/s, `119.085594` total tok/s, LocalMaxxing `cmpct6t4m007fnw01yjdtlcs4`.
- MoE output-allreduce-inside-custom-op: `88.927945` output tok/s, `118.570593` total tok/s, LocalMaxxing `cmpco63q90052nw01ov1zxvwp`.
- Direct Q/K variance in-place scale: `88.501953` output tok/s, `118.002604` total tok/s, LocalMaxxing `cmpc8cmqm0060pc016g5l5ukh`.
- Q/K helper plus alias-correct tiny-FP32 in-place op: `88.313105` output tok/s, `117.750807` total tok/s, LocalMaxxing `cmpc5xmm6005jpc01k84dxd14`.
- Alias-correct tiny-FP32 in-place op: `88.103866` output tok/s, `117.471821` total tok/s, LocalMaxxing `cmpc1dxgv0052pc01s1j9i37l`.
- Warning-prone tiny-FP32 skip-clone headline: `88.748424` output tok/s, `118.331232` total tok/s, LocalMaxxing `cmpbz7lyc004rpc019jburzqv`.
- Clone-safe custom allreduce without tiny-FP32 clone elision: `87.279129` output tok/s, `116.372172` total tok/s, LocalMaxxing `cmpbsqm4l001qpc0199azisgz`.
- No-attention-delay logits-WS baseline without clone-safe compiled allreduce custom-op: `82.404268` output tok/s, `109.872357` total tok/s, LocalMaxxing `cmpbifcx3013bmn01747cxix8`.
- Delayed-attention logits-WS baseline: `81.758267` output tok/s, `109.011023` total tok/s, LocalMaxxing `cmpay7th600bbmn01v6csyaro`.
- Earlier MoE-WS FlashAttention/PIECEWISE baseline: `80.602755` output tok/s, `107.470340` total tok/s, LocalMaxxing `cmpasdq5v007nmn019elaut3s`.

Recent quality-safe rejections and screens:

- Q/K helper max1 current-high: lowered `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS` from `4` to `1`. It failed `raw145-n64-exact` before benchmarking: expected `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`, observed `21404821eb70a2ee3de9e82c039b5cbb5c9eef884c5019579f442c6a272a9c5a`. Output was deterministic and non-degenerate, but exact-token drift violates the quality rule. Decision: reject, do not benchmark, do not submit to LocalMaxxing.
- Q/K helper max2 current-high: lowered `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS` from `4` to `2`. It passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `88.541226` output tok/s / `118.054968` total tok/s. Decision: reject and do not submit to LocalMaxxing because it is `0.772970` output tok/s below the promoted mean. Keep Q/K helper max tokens at `4`.
- Current-high CCL fabric-vertex override: `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `89.037858` output tok/s / `118.717144` total tok/s across four repeats, `0.276337` output tok/s below the promoted mean. The arithmetic-repeat shutdown log also printed oneCCL/PMI `Broken pipe` and `ccl::v1::exception` teardown errors. Decision: reject, do not submit to LocalMaxxing, and keep this env unset.
- Current-high skip-redundant-contiguous: `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1` passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `89.141961` output tok/s / `118.855948` total tok/s across four repeats, `0.172235` output tok/s below the promoted mean. The extended-sixpack and first benchmark-repeat logs printed `Bad address (src/pipe.cpp:367)` during shutdown. Decision: reject and do not submit to LocalMaxxing.
- QKV narrow-split: `VLLM_MINIMAX_QKV_NARROW_SPLIT=1` replaced `qkv.split(...)` view extraction with explicit `Tensor.narrow()` views around the Q/K RMS helper. It passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `88.802625` output tok/s / `118.403500` total tok/s. Decision: reject and do not submit to LocalMaxxing because it is `0.511570` output tok/s below the promoted mean. The lesson is that split-view selection is not a meaningful decode bottleneck under the current XPU graph replay path.
- MiniMax MoE full-forward guard sweep: max1 `89.031893`, max2 `88.854010`, max3 `88.886159`, max4 `89.314195`, max512 `85.209082` output tok/s. Decision: keep `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`.
- Post-attention norm plus MoE custom-op: quality passed but measured `89.007143` output tok/s / `118.676191` total tok/s. Reject.
- Full-forward plus callable-cache: quality passed but measured `88.828891` output tok/s / `118.438521` total tok/s. Reject.
- MoE output-allreduce plus callable-cache stack: quality passed but measured `88.912296` output tok/s / `118.549728` total tok/s. Reject.
- MiniMax MoE WS skip-redundant-contiguous without full-forward custom-op: quality passed but measured `88.885135` output tok/s / `118.513514` total tok/s. Reject.
- Current-high `--block-size 128` failed `raw145-n64-exact`; keep `--block-size 256`.
- `VLLM_MINIMAX_MOE_FINAL_INPLACE_ALLREDUCE=1` failed the first strict quality gate before benchmarking; do not use larger FP16 hidden-state in-place allreduce under the current graph recipe.
- `VLLM_XPU_LOGITS_CHUNKED_GATHER=32768` failed 16-repeat arithmetic determinism; do not use chunked logits gather until deterministic.
- Exact-shape XCCL microbench found raw decode-sized allreduces around `15-17 us`; full-model loss is dominated by framework/compiler/graph boundaries around collectives, not raw CCL latency alone.
- `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=4096` and `=2048` both passed quality but were slower than dtype-specific tiny-FP32 routing. Keep generic in-place threshold unset or `0`.

Detailed historical candidate screens remain in `notes/` and `data/`. The local lab copy of `CURRENT.md` may include a longer running chronology than this concise repo status file.

## Qwen3.6 27B

The quality-preserving Qwen targets remain separate from MiniMax AutoRound:

- Q4_0 GGUF TP3 remains the current Qwen decode-speed focus.
- Static FP8 TP4 remains the preferred long-context Qwen layout.
- AutoRound/INT4 results should not be compared as equal-quality replacements for FP8/BF16/GGUF without separate quality validation.

## Next Optimization Targets

- Use the MiniMax MoE full-forward custom-op result as the current strict baseline for future code work.
- Keep `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`; the guard-size sweep found max4 as the local optimum.
- Keep `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=4`; max1 failed exact quality and max2 was quality-safe but slower.
- Keep `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=0`; generic thresholds are quality-safe but slower than dtype-specific tiny-FP32 routing.
- Keep `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK` unset; the current-high retest was slower and showed oneCCL shutdown noise.
- Continue targeting true XPU fused-boundary work: hidden allreduce plus residual/RMSNorm, Q/K variance allreduce plus Q/K RMS apply, MoE output plus epilogue, and final lm-head/projection boundaries.
- Preserve vLLM's proven allreduce semantics unless a candidate has an exact repeatability proof across fresh graph/cache captures.
- Keep strict quality gates as promotion blockers; do not promote logits/router/argmax shortcuts unless they pass raw exact hashes, semantic checks, arithmetic repeat, and extended sixpack.
- Keep speculative decode optional and quality-gated; no current promoted MiniMax result uses speculation.
