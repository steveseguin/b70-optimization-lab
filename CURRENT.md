# Current Promoted Results

Date: 2026-06-30

## Active Gemma 4 26B A4B Q8 Lane

Current active optimization target:

- Model: Gemma 4 26B A4B instruct, `UD-Q8_K_XL` target GGUF on one Intel
  Arc Pro B70 32GB per replica.
- Goal: maximize **realistic cold-response** single-session decode while
  preserving the Q8 target/verifier quality lane. Synthetic/repetitive prompt
  scores may guide optimization only; they are not headline throughput or
  LocalMaxxing evidence.
- Best strict realistic-suite result so far:
  `121.41411987308553 tok/s` median generated-token throughput for tokens
  1-100 after TTFT across the fixed cold prompt suite. Evidence:
  `data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`.
  It uses llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
  reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `cached_tokens=0` on every prompt, and `realistic_final_gate.passed=true`.
- Representative / submitted status:
  the VDR2 selected-down fused weighted-sum path plus FA-on 32K/VMM is the
  current policy-compliant Gemma 26B Q8 LocalMaxxing submission. The current
  high is approved as `cmqztiqdn02vnoe01egox6q3f`; the same-family
  confirmation high measured `119.94842631460949 tok/s`, and the prior
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
- Recent non-promoted follow-up:
  `LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1` was valid and trimmed real terminal
  draft work, but four full512 lanes topped out at `113.58569073629727 tok/s`,
  below the current `121.41411987308553` record. Late-head bonus plus
  `LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1` lost strict128. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-eogclip-and-spechead-negative.md`.
  Fusing selected-softmax directly into selected-down VDR2 was a valid
  strict128 small positive (`115.554` best flag-on), but the full512 promotion
  screen lost: best flag-on primary median was `111.90908727268967 tok/s`
  with EOG clip and `111.89648891729823 tok/s` without it, below both same-day
  controls and the current `121.41411987308553` record. It is preserved
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
  below the `121.41411987308553` headline. Do not change the recipe or submit
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
  active `121.41411987308553 tok/s` record, so keep the promoted short-record
  reproduction on UB1024 and treat UB2048 as a validated service/default
  candidate. A repeat UB2048-vs-UB2560 confirmation at 12K- and
  16K-requested long prompts kept that decision: UB2048 wins the
  12K-requested shape and is an effective prefill tie at the 16K-requested /
  ~21K actual-token shape while decoding faster, so do not standardize on
  UB2560. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-ub2048-short-suite-control.md`
  and
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ub2048-vs-ub2560-confirm.md`.
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
  `results/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-record.md`.
- Reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`.
- Validation rules: `results/gemma4-26b-a4b-q8-b70/validity-gates.md`.
- Current research plan: `results/gemma4-26b-a4b-q8-b70/research-plan.md`.

Do not promote the earlier `ngram-mod` `245-280 tok/s` rows, the synthetic
filled-long `170+ tok/s` rows, or any repeated-prompt average as real-world
throughput. They are diagnostic artifacts unless the fixed realistic prompt
suite passes with `cached_tokens=0` on every prompt.

Short-decode status: the reliable `>100 tok/s` target is already broken. Avoid
more Gemma config roulette. The next short-record source lane is either a
guarded accept-prefix verifier LM-head op with parity mode, or a distinct
profile-backed verifier/MoE boundary reduction. Otherwise, work on a separate
prefill / long-context service lane and rerun the short fixed suite afterward to
prove no regression.

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
