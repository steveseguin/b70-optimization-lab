# Gemma 4 26B A4B Q8 B70 Research Plan

Research snapshot: 2026-06-30. Goal: maximize valid single-session decode for
one complete Q8/INT8-quality Gemma 4 26B A4B replica per B70, then run four
replicas on four GPUs for parallel research and aggregate service capacity.

## Current Realistic Cold-Suite Frontier

Best one-B70 Q8 strict result under the promotion gate:

- result:
  `data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/`;
- primary metric: **123.67689864739785 tok/s** median generated-token
  throughput for tokens 1-100 after TTFT across the fixed realistic suite; p10
  `105.67252530778094`, mean `120.82536080117124`, median full-512
  after-TTFT `110.68310696601407`, median wall full-512
  `106.44076646173642`, median TTFT `179.12497598445043 ms`;
- config: llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
  reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
  `--ctx-checkpoints 0`, no n-gram/history acceleration; LM-head experiment
  flags `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV` and
  `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_NO_REORDER` unset;
- gate: fixed suite `gemma4-26b-a4b-q8-b70-realistic-v1`, each prompt sent
  once, `cached_tokens=0` on every request,
  `realistic_final_gate.passed=true`.

This is the policy-compliant VDR2 selected-down fused weighted-sum transfer of
the strict `n_max=3`, `n_min=2`, `UBATCH_SIZE=1024` family, with FA-on
32K/VMM and final post-norm residual fusion. The current LocalMaxxing ID is
`cmr01nnet000mld01x2tt6qds`. The previous LocalMaxxing ID was
`cmqztiqdn02vnoe01egox6q3f` for `121.41411987308553 tok/s`, preceded by
`cmqzq5zu402troe01t774uyox` for `117.91456485086059 tok/s`. Same-family
support includes a `119.94842631460949 tok/s` row plus lower variance rows at
`113.572`, `114.088`, and `111.988 tok/s`; earlier same-identity confirmations measured
`116.45776605647993`, `117.41509141115063`, `115.08942949119734`, and
`117.45737477243767 tok/s`. Treat this as a higher-variance `~120-124 tok/s`
baseline lane, not as a no-reorder flag win. It
supersedes the prior selected-down rows (`115.8466634928202` /
`cmqyrpox4021dqk01co5o4fcw` and `115.72789384447941` /
`cmqyo0jyt08ippk01vhiobdnm`), the prior LocalMaxxing row
`cmqxchyra03xmqr01b963gmi1` at `98.34046474459183 tok/s`, prior F16-p021
`95.82453787677183 tok/s`, VDR2 `90.98312252660529`,
`90.32179401019857`, and `89.45543282863798 tok/s` submissions, and prior
VDR4 `87.61145306230438 tok/s` submission. The older
`86.47445652599384 tok/s` `p_min=0.075` row did not repeat and is also
superseded.
The older `100+`, `170+`, and `280+` rows remain useful diagnostics, but they
are not representative real-world throughput unless revalidated by the fixed
cold suite.

2026-06-29 pre-FA record-repeat variance: four additional full512 cold-suite repeats
of the promoted recipe all passed gate/canary but did not beat the record:
`113.810`, `113.227`, `107.329`, and `114.829 tok/s`. Keep the existing
`115.8466634928202 tok/s` LocalMaxxing row as the then-current headline. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-record-repeat-full512-variance.md`.

2026-06-29 context/service split update: the fixed realistic-gate retest made
FA-on 32K/VMM the current short-record recipe as well as the service profile.
With flash attention off, the current Q4_0 MTP draft stack is useful at
`CTX_SIZE=24576` / `25600` (`~73 tok/s` after TTFT on an ~11K actual prompt),
degrades at `26624`, and falls off a cliff by `27648`. The follow-up FA-on
screen fixed that service cliff: `FLASH_ATTN=on` with MTP reached
`~102.7-103.2 tok/s` after TTFT at `CTX_SIZE=27648`, `28672`, and `32768` on
the same diagnostic shape, with `cached_tokens=0` and 8/8 canary rows. These are
synthetic unique-prompt context diagnostics, not LocalMaxxing headline rows;
the separate fixed realistic retest is recorded in
`20260629-faon-vmm-ctx32768-record.md`.
See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-context-threshold-mtp-vs-nospec.md`.

2026-06-30 prefill/long-context ladder baseline: the current FA-on 32K/VMM
record recipe was run on unique long prompts with `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, 16 generated tokens, `cached_tokens=0`, and canary pass on
all rows. Approx prefill throughput (`prompt_tokens / TTFT`) peaked around
`~1.09K-1.11K tok/s` at 2.9K-5.6K actual prompt tokens, stayed `~1.07K tok/s`
at 8.1K, then declined to `955.9`, `887.7`, and `794.2 tok/s` at 12.1K,
16.2K, and 21.5K actual tokens. This is service-lane baseline data only. Keep
the short-decode record recipe unchanged unless a service candidate later
passes the fixed cold suite with no decode regression. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ladder-baseline.md`.

2026-06-30 service UBATCH screen: `BATCH_SIZE=1536/2048/2560/3072` with matching
`UBATCH_SIZE` was tested on the 8.1K, 12.1K, 16.2K, and 21.5K actual-token
service shapes above. All rows were unique-prompt, canary-passing, and
`cached_tokens=0`. `2048` is the best general candidate, improving approximate
prefill over UB1024 by `+10.8%`, `+9.2%`, `+7.4%`, and `+6.1%`; `2560` is only
a possible very-long-prompt follow-up; `3072` fits but regresses. The follow-up
fixed realistic cold-suite check passed for UB2048 with `cached_tokens=0` and
no observed short-decode regression: UB2048 averaged
`118.30159066915866 tok/s` versus UB1024 controls at
`116.46794311469674 tok/s`, but the best UB2048 candidate was only
`118.70031578164084 tok/s`, below the current `123.67689864739785 tok/s`
record. Keep UB1024 for the promoted short-record reproduction; use UB2048 as
the validated general service/default candidate. A repeat UB2048-vs-UB2560
confirmation at the 12K- and 16K-requested long-prompt shapes kept the same
decision: UB2048 wins the 12K-requested shape and is only an effective prefill
tie at the 16K-requested / ~21K actual-token shape while decoding faster. Do
not standardize on UB2560. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ubatch-service-screen.md`
and
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-ub2048-short-suite-control.md`
and
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ub2048-vs-ub2560-confirm.md`.

2026-06-30 fixed long-context service gate: a deterministic JSON-retrieval
suite was added at
`../../repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json` with a streaming
OpenAI-compatible harness at
`../../scripts/bench-openai-long-context-suite.py`. The paired four-GPU service
wrapper `../../repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`
and the paired short guard
`../../repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh` make the
service-vs-short split reproducible. The main long-context screen through
`22730` actual prompt tokens passed exact JSON retrieval, `cached_tokens=0`,
and canaries on every lane; UB2048 averaged `1013.884` median approximate
prefill tok/s versus UB1024 at `936.865` (`+8.22%`). The first near-32K run
with `MAX_TOKENS=64` failed only because the exact JSON answer was truncated;
the corrected `MAX_TOKENS=96` run at `30400` actual prompt tokens passed on all
lanes, with UB2048 averaging `701.487` versus UB1024 at `661.905` (`+5.98%`).
The paired full512 short-suite guard also passed on all lanes and did not show
a short decode regression (`119.153` UB2048 average versus `116.402` UB1024),
but it did not beat the `123.67689864739785` record. Decision: UB2048 is the
validated long-context/prefill service candidate; keep UB1024 for short-record
reproduction and LocalMaxxing record work. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-long-context-prefill-service-gate.md`.

Follow-up heavy-context refinement closed the obvious UBATCH-only lane:
UB1792/2048/2304/2560 were cross-over tested on the `16213`, `22730`, and
`30400` actual-token cases. UB2560 was the fastest narrow prefill point
(`835.782` combined median prefill tok/s, `718.968` at 30400 actual tokens),
but its paired short guard averaged only `113.252` median 1-100 tok/s after
TTFT. UB2304 also stayed below the controls in its short guard (`116.547`
average). Keep both as diagnostics only, not service defaults. A profiled
UB2048 near-32K row (`20260630Tprefill-profile-ub2048`) showed
`FLASH_ATTN_EXT` nodes dominate prompt processing, with the top five attention
nodes around `4511-4529 ms` each and final prompt eval at `43193.83 ms / 30400
tokens = 703.80 tok/s`. Next prefill source work should target
FlashAttention/KV-cache attention shape, layout, or graph behavior rather than
verifier LM-head/MoE work.

2026-06-30 record-identity full512 repeat: four parallel lanes of the current
FA-on 32K/VMM selected-down VDR2 recipe all passed the strict realistic final
gate with `cached_tokens=0` and 128/128 canary, but did not beat the
then-current `121.41411987308553 tok/s` record. Primary medians were `118.21311630972258`,
`117.71732552906994`, `114.87763475869593`, and
`112.94544241316387 tok/s`. Treat as variance/no-new-record, not a
LocalMaxxing submission candidate. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-record-repeat-full512-variance.md`.

2026-06-30 final post-norm fusion promotion: the default-off
`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` path was retested after the
FA-on 32K/VMM selected-down VDR2 record stack. Strict128, cross-over, and
full512 A/B all passed the fixed cold gate. The best full512 flag-on lane
reached the current valid record `123.67689864739785 tok/s` and was submitted
as LocalMaxxing `cmr01nnet000mld01x2tt6qds`. The effect is noisy:
paired full512 finalpost lanes averaged `120.11414175477651` versus controls
`116.29133772533568`, but the second finalpost lane was only
`116.55138486215519`. Keep the flag in the promoted recipe, and keep repeat
confirmation separate from effect-size claims. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-final-postnorm-fusion-screen.md`.

2026-06-30 final post-norm repeat2: four additional full512 lanes of the
promoted final-postnorm recipe all passed the fixed cold gate, `cached_tokens=0`,
and 512/512 canary, but did not beat the `123.67689864739785 tok/s` record.
Medians were `118.78941183022032`, `115.48824790393866`,
`112.71902407241845`, and `116.80124865921995 tok/s`. Treat as valid
variance/no-new-record support and do not submit. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-finalpost-repeat2-full512-variance.md`.

2026-07-01 current-record repeat3: four more full512 lanes of the promoted
final-postnorm recipe all passed the fixed cold gate, `cached_tokens=0`, and
512/512 canary, but again did not beat the `123.67689864739785 tok/s` record.
Medians were `121.9720691923804`, `111.87547492588218`,
`118.23096116340783`, and `113.12239033658872 tok/s`. Treat as valid
variance/no-new-record support and do not submit. This strengthens the
decision to stop repeat-only runs unless paired with a new source mechanism.
See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-current-record-repeat3-plan.md`.

2026-07-01 final-postnorm + UBATCH 1152 screen: retested the earlier
`BATCH_SIZE=1152` / `UBATCH_SIZE=1152` local-positive after the current
final-postnorm promotion. The strict128 A/B was valid on all four lanes
(`cached_tokens=0`, canary complete), but `1152/1152` did not repeat as a win:
same-window `1024/1024` controls measured `121.88626919341718` and
`117.32450078824291 tok/s`, while `1152/1152` candidates measured
`111.13257897167367` and `118.75276241034763 tok/s`. Candidate average
`114.94267069101065` was below control average `119.60538499083004` and below
the `123.67689864739785 tok/s` headline. Decision: close as valid no-change,
no full512 confirmation, no LocalMaxxing submission, and do not renew this
UBATCH interaction unless another source/runtime change alters the shape. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpost-ub1152-screen.md`.

2026-06-30 attention post-norm residual fusion: implemented default-off
`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1`, updated the harness to pass and
record it, rebuilt the AOT BMG-G31 llama-server under oneAPI, and ran a verified
strict128 A/B. All lanes passed the cold gate and 512/512 canary, but it lost
on the short headline metric: controls averaged `119.3616057307415 tok/s`,
flag-on lanes averaged `116.75359048324216 tok/s`. It improved full-output
medians (`117.785` flag-on average versus `115.134` controls), so keep only as
a possible service/full-output idea. Do not full512-confirm or submit for the
current 1-100-token record. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-attn-postnorm-residual-fusion-negative.md`.

2026-06-30 per-layer post-norm residual fusion: implemented default-off
`LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`, updated the harness and
payload metadata, rebuilt the same AOT BMG-G31 llama-server, and ran a verified
strict128 A/B. All four lanes passed the fixed cold gate, `cached_tokens=0`,
and 512/512 canary. The result is valid but too small and GPU-dependent to
promote: controls averaged `115.80942063480597 tok/s`, flag-on lanes averaged
`116.81238861292647 tok/s`, and the best flag-on lane was
`119.96280008214512 tok/s`, below the `123.67689864739785` headline. Keep the
flag default-off and preserve the before/after source snapshots; do not submit
or full512-confirm for the short record unless future service/full-output work
needs this path. This closes the obvious sibling norm/residual fusion after the
final-postnorm win. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-perlayer-postnorm-residual-fusion-inconclusive.md`.

2026-07-01 final/attention/per-layer norm fusion combination: the promoted
final post-norm recipe was paired with both sibling fusions
(`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1` and
`LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`) in a four-GPU strict128
A/B. All lanes passed the fixed cold gate with `cached_tokens=0`, but the
candidate average was flat/slightly worse (`119.145` tok/s) than the same-window
controls (`119.184`) and below the `123.67689864739785` headline. Decision:
closed negative; do not full512-confirm this exact combination. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpost-attnper-normcombo-negative.md`.

2026-07-01 accept-prefix argmax verifier prototype: implemented default-off
`LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` in the dirty llama.cpp Gemma stack,
including GGML/SYCL plumbing for a reordered-Q8 LM-head op that stops computing
later verifier rows after the first rejected draft token. The path was
semantically valid: parity and non-parity strict128 runs both passed the fixed
cold gate, had `cached_tokens=0`, and passed canaries. Performance was negative:
the flag-on strict128 run measured `104.27951393842321 tok/s` versus
`111.26833798937403 tok/s` for the same-build control, and far below the
`123.67689864739785 tok/s` record. Decision: closed negative; preserve the
patch, but do not full512-confirm, submit, or reuse this serial per-row design.
Any future accept-prefix verifier work needs a single-kernel/global-row
scheduler or a larger graph change that removes verifier LM-head rows without
sacrificing the existing multi-row Q8 reorder efficiency. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-acceptprefix-argmax-negative.md`.

2026-07-01 next-lane audit / phase-prefill identity hardening: a fresh audit
kept the short-decode frontier unchanged at `123.67689864739785 tok/s` and
closed the near-term "try another small flag" path. The remaining credible
short-decode source lane is a non-serial, bonus-preserving accept-prefix
verifier v2; otherwise effort should move to the separate service/prefill lane.
For that service lane, the phase-prefill recipe
`BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`,
`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` remains the practical hardening target.
The launcher was updated to record `prefill_ubatch_size` in both the server log
header and `summary.json` `launcher_identity`, so future phase-prefill artifacts
can be compared without relying on wrapper memory. A four-GPU validation run
passed the long-context gate on all lanes with `cached_tokens_all_zero=true`,
recorded `prefill_ubatch_size=2048` in all summaries/log headers, and measured
`1051.794789819953 tok/s` aggregate median prefill average plus
`119.50639487463019 tok/s` aggregate median decode average. This is
reproducibility/service evidence only, not a LocalMaxxing claim. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-next-lane-audit-and-phase-prefill-identity.md`.

2026-07-01 phase-prefill per-lane ladder: the long-context service wrapper now
supports optional per-lane `LLAMA_PREFILL_UBATCH_SIZE` via
`LANE_SPECS=GPU:BATCH:UBATCH:TAG:PREFILL_UBATCH_SIZE`, and aggregate summaries
group by that field. A valid four-lane ladder showed `2304`/`2560` can improve
pure prefill (`1078.9997` / `1071.8658 tok/s`) but lower long-context decode
(`116.9092` / `116.3453 tok/s`). A crossed two-lane A/B ruled out `1792` as a
better balanced default: `2048` averaged `1052.6123` prefill and `119.7308`
decode, versus `1792` at `1047.0015` and `119.3035`. Decision: keep the
balanced phase-prefill service recipe at `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`,
`LLAMA_PREFILL_UBATCH_SIZE=2048`; keep `2304`/`2560` as pure-prefill
diagnostics only. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-phase-prefill-per-lane-ladder.md`.

2026-06-29 verifier LM-head candidate-threshold audit: shifted
`t_inp_tokens[r + 1]` does provide the draft candidate ID for narrow standard
MTP verifier rows, but this is not a good next record implementation. Exact
verification still needs the true target token on mismatch, so the op would
still scan full vocab and do the same top1/challenger work as the closed
top1-epilogue/reduction lanes. Do not build this unless a future design removes
verifier LM-head rows or proves a candidate win without full-vocab dot work.
See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-candidate-threshold-lmhead-no-go.md`.

2026-06-28 F16 p021 small-ncols record: a four-GPU strict screen found
`LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` was the only useful source flag in the
batch. The 128-token confirmation produced a strong lead (`98.44959726864674`
best, all lanes valid), but it was not promoted until a full512 confirmation
matched the exact successful identity. A first full512 reconstruction was
invalid (`cached_tokens=1` everywhere) because it changed launch identity
details (`BATCH_SIZE=512`, `THREADS=16`, `POLL=50`, missing
`--no-spec-draft-backend-sampling`, missing draft threads, missing
`--ctx-checkpoints 0`, `ONEAPI_DEVICE_SELECTOR=level_zero:*`, and accidental
`LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1`). The corrected full512
confirmation passed on all four GPUs and produced the new `95.82453787677183`
record. Lesson: for Gemma promotion, diff the full launcher identity before
interpreting any speed or validity change. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0047-strict-f16p021-smallncols-record.md`.

2026-06-28 bulk sampled-ID verifier update: a default-off host-side verifier
cleanup (`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`) reads the consecutive
backend-sampled verifier ID buffer directly after the existing synchronize
instead of calling the per-row nosync accessor for each verifier row. It
preserves target-verifier semantics and lifted the strict record to
`98.34046474459183 tok/s`, but still did **not** crack reliable `>100`. Keep
it in the promoted reproduction recipe; the next >100 work needs verifier
economics rather than more host read cleanup.

2026-06-29 VDR2 selected-down fused weighted-sum update: the verifier MoE
selected-down backend was extended to support VDR2-reordered Q8 expert weights
under `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`. This removed
the separate selected-down materialization plus weighted-sum pass in the active
VDR2 record stack. Full512 confirmations passed on all four GPUs and lifted the
strict record to `115.72789384447941 tok/s`. This finally cracked reliable
`>100` under the fixed fresh-response gate; keep this as the new baseline before
trying deeper verifier LM-head or MoE boundary work. See
`20260629-vdr2-selected-down-record.md`.

2026-06-29 compact verifier argmax reorder-ncols screen: a default-off SYCL
route under `LLAMA_SYCL_MUL_MAT_ARGMAX_REORDER_NCOLS=1` attempted to make
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` competitive by sharing reordered Q8
LM-head weight loads across verifier rows. It passed the fixed cold gate and
512/512 canary, but did not beat the regular verifier path:
`109.94207305976514 tok/s` versus same-window control
`110.18642209569018 tok/s`, both below the promoted `123.67689864739785`
full512 record. Decision: negative, keep default-off; do not promote or submit.
See
`../../patches/gemma4-26b-a4b-q8-b70/20260629-compact-argmax-reorder-ncols-negative.md`.

2026-06-29 current selected-down node profile: after the compact-argmax
negative, a fresh diagnostic profile of the selected-down VDR2 record stack
passed the fixed cold gate and 64/64 canary, but profiling reduced measured
throughput to `66.03793628965451 tok/s`. Treat this as diagnostic only. The
top hot node remains the target/verifier full-vocabulary Q8 LM head
(`MUL_MAT:node_1930`, `1.377 ms/call`), followed by final-layer BF16 routed
gate/up (`MUL_MAT_ID:ffn_moe_gate_up-29`, `0.590 ms/call`), many Q8 routed
gate/up layers around `0.34-0.38 ms/call`, then draft argmax nodes around
`0.41 ms/call`. Server spec profile still shows target decode dominating:
`target_decode_ms=39792.793` versus `draft_ms=3880.504`; sampler/accept
overhead is negligible. Decision: do not retest late-head bonus, stage-MTP3,
or small host/copy tweaks as record candidates. Next credible work must reduce
exact verifier graph cost, especially LM-head or routed MoE kernels. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-selecteddown-rebuild-profile-and-skipstateless.md`.

2026-06-29 FA-on 32K/VMM node profile: a newer diagnostic profile of the
promoted FA-on 32K/VMM identity also passed the fixed cold gate and 256 canary
rows, but profiling reduced measured throughput to
`73.0624227983514 tok/s`. Treat it as diagnostic only. It confirms the same
target/verifier-bound shape on the current record identity: server profile
shows `target_decode_ms=81326.913` versus `draft_ms=6471.396`, while
sampler/accept overhead is noise. The hottest node is the one-column Q8_0
LM-head `MUL_MAT:node_1775` (`1.367 ms/call`, `token_embd.weight`,
`ne=[262144,1,1,1]`), followed by final BF16 routed gate/up and many Q8
routed gate/up layers. The existing Q8 MMVQ small-ncols idea is not a good
next step: the source already has Q8_0 reordered dispatch for
`src1_ncols > 1 && src1_ncols <= 8`, and the current LM-head hotspot is
`src1_ncols == 1`. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-faon-vmm-nodeprofile.md`.

2026-06-29 packed routed gate/up GEGLU epilogue screen: preserving the tuned
`MUL_MAT_ID` gate/up matmul and replacing split views with packed
`ggml_geglu(gate_up)` was safe but did not improve the promoted full512
identity. The narrow BF16 layer-29 mode was mixed and below threshold; the broad
`LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE=all` mode showed one promising
strict128 lane (`121.62 tok/s`) but failed full512 promotion: DMMV-unrelated
full512 candidates were `115.40` and `115.04 tok/s` against controls
`117.57` and `117.79`, all valid. Decision: closed negative; keep as
default-off research artifact only. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-packed-gateup-geglu-epilogue-negative.md`.

2026-06-29 Q8 LM-head one-column DMMV screen: a default-off guard
`LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV=1` kept DMMV enabled for the large-vocab
one-column Q8_0 LM-head shape instead of suppressing it in favor of reordered
MMVQ. It passed strict and full gates, but full512 candidates were only
`115.04` and `115.49 tok/s`, below same-window controls and the
`123.67689864739785 tok/s` record. Decision: closed negative. The next
credible LM-head variant is not DMMV; test regular MMVQ without Q8 reorder for
the same one-column LM-head shape, because the current reordered-Q8 path has no
multi-column reuse when `src1_ncols == 1`. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-q8-lmhead-1col-dmmv-negative.md`.

Follow-up source direction from read-only audits:

- first priority: an exact **regular-Q8-MMVQ top1 epilogue** for verifier
  LM-head. The goal is to keep the fast regular reordered-Q8 `MUL_MAT` dot body
  used by `node_1930` while publishing only sampled token IDs, instead of
  falling back to the scratch/reduce-heavy `GGML_OP_MUL_MAT_ARGMAX` family that
  has repeatedly lost. Guard as default-off and validate strict128 against the
  paired selected-down control before any full512 promotion attempt.
- second priority if LM-head top1 fails: a BF16 final-layer gate/up + GEGLU
  matmul-epilogue op that preserves the existing BF16 `ggml_sycl_mul_mat()`
  path, then fuses only post-GEMM GEGLU/scatter. Do **not** retry
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT`; the existing graph-safe
  version already lost. The BF16 epilogue idea is larger because it needs graph
  and backend op plumbing, so it should follow the narrower LM-head attempt.

2026-06-29 regular-Q8-MMVQ top1 epilogue screen: the first-priority LM-head
idea was prototyped under
`LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE=1` and
`LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE=1`. It rebuilt successfully and passed the
fixed cold gate plus 256 canary rows, but lost the strict128 headline metric
against the paired control: `111.89428679462038` vs
`112.52074349461066 tok/s` median tokens 1-100 after TTFT. Full-output and wall
medians were slightly better, but this is not the promotion metric and remains
below the `123.67689864739785 tok/s` record. A follow-up node-profile run proved
the new route was active:
`MUL_MAT_ARGMAX:spec_verify_regular_mmvq_top1_epilogue_token_rows`, but it was
still the hottest node at ~`1.325 ms/call`. Decision: closed negative for this
implementation; do not run full512 promotion on this path as-is. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-regular-mmvq-top1-epilogue-negative.md`.

2026-06-29 top1 partial-reduction follow-up: a material redesign was tried
under `LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE_PARTIAL=1`. It replaced the v1
row-level top1 reduction with per-workgroup partial candidates plus a final
reduction, while preserving the same tie-breaking. It passed strict128 quality
and the fixed cold gate, but lost decisively: `107.09528059923313 tok/s`
against the same-screen control at `116.81887639329213 tok/s` and v1 at
`114.4784737775974 tok/s`. Decision: closed negative; do not run full512 or
submit this route. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-regular-mmvq-top1-partial-negative.md`.

2026-06-30 profile refresh: after the rowpack2 experiment was reverted and the
server rebuilt, a fresh `LLAMA_SERVER_SPEC_PROFILE=1` /
`LLAMA_MTP_DRAFT_PROFILE=1` run of the FA-on 32K/VMM record identity passed
the fixed cold suite but measured only `114.05619435553182 tok/s` because it
was diagnostic (`MAX_TOKENS=128`, profiling enabled). The profile confirms the
current bottleneck remains target/verifier graph work, not draft or sampler
bookkeeping: `target_decode_ms=38529.540`, `draft_ms=2665.342`,
`process_ubatch_ms=36833.360`, and `sampled_extract_ms=1665.262`. The sampled
IDs are already compact and bulk-read, so a smaller host-vector patch is not a
credible record lever unless it removes/overlaps the backend read/sync. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-record-refresh-specprofile.md`.

Follow-up sync timing with a default-off
`LLAMA_SPEC_VERIFY_SYNC_PROFILE=1` wrapper measured the later accept-side
`llama_synchronize(ctx)` at only `1.734 ms` total over `896` verifier calls
(`0.002 ms/call`). This rules out sampler-side sync cleanup as a meaningful
record path; if sampled-ID extraction is attacked again, the patch must remove
or overlap the backend output-read boundary itself.

2026-06-30 row-economics verifier profile: a default-off
`LLAMA_SPEC_VERIFY_ROW_ECON_PROFILE=1` counter measured the default full-bonus
MTP verifier path on the same record identity. The diagnostic strict128 run
passed the fixed cold gate (`cached_tokens=0`) and 128 canary rows, with
`118.69362600230792 tok/s` median tokens 1-100 after TTFT under profiling. The
important result is the row accounting: `921` verifier steps,
`3679` current output rows, `2893` oracle rows, and `786` rows saved
(`21.365%`) if an exact adaptive verifier could stop output rows at the first
mismatch while preserving full-match bonus rows. `541/921` steps were
full-match-with-bonus, so the bonus pipeline is valuable and simple no-bonus or
adaptive bonus skipping remains closed negative. A row-adaptive design is worth
only if it preserves that bonus behavior and removes real LM-head/output work
inside the verifier graph; otherwise continue with deeper routed-MoE or graph
boundary reductions. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-row-economics-profile.md`.

2026-06-30 FA-on 32K/VMM UBATCH screen: final-record identity lanes tested
`UBATCH_SIZE=768`, `896`, `1024` control, and `1152`. All lanes passed the
fixed cold gate with `cached_tokens=0`. `BATCH_SIZE=1152`, `UBATCH_SIZE=1152`
looked interesting in strict128 at `121.24708378127268 tok/s`, but the paired
full512 confirmation did not beat the record: candidate average
`117.36308529017367 tok/s`, paired-control average `114.3071667009025`, best
candidate `118.43353215490006`, current headline `123.67689864739785`.
Decision: valid local positive versus same-window controls, but no recipe
change and no LocalMaxxing submission. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-faon-vmm-ubatch-screen.md`.

2026-06-30 verifier row-shape / accept-prefix audit: two read-only source
audits plus a tiny `LLAMA_BATCH_DEBUG=1` diagnostic clarified the next verifier
lane. The profiler detail that shows the Q8 LM-head as `src1 ne=[2816,1,...]`
is misleading because the SYCL node profiler keys by node name and keeps the
first detail it observed. The actual MTP verifier split log shows standard
full-bonus verifier microbatches with `n_tokens=4` and `n_outputs=4`, so a
simple "coalesce LM-head output rows" patch is not a meaningful next step.
The remaining exact row-output reduction would require a new backend
accept-prefix verifier LM-head op that computes row 0 top-1, compares with the
draft token on-device, and computes later verifier/bonus rows only as needed.
Expected upside is modest (`+2` to `+6 tok/s` if implemented well), and the
risk is high because losing the current Q8 multi-column path or adding serial
kernel launches can erase the row savings. Do not reopen row-shape/config
screens without new profile evidence; either implement the guarded
accept-prefix op with parity mode or move to a separate service/prefill lane.
See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-verifier-row-shape-and-accept-prefix-audit.md`.

2026-06-30 accept-prefix parity probe: implemented the guarded parity mode
needed before a real backend accept-prefix verifier LM-head op. The
default-off `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY=1` helper reconstructs the
accepted token vector from backend sampled verifier rows and compares it to
`common_sampler_sample_and_accept_n(...)` on the existing full-bonus MTP path.
The first version was deliberately fail-fast but too narrow: it required
`n_draft == 3` and rejected valid short-tail steps (`n_draft=2`,
`spec_i_batch.size()=3`). The rebuilt helper accepts any full-bonus tail with
`n_draft > 0`, consecutive verifier rows, no null sampled IDs, and
`spec_i_batch.size() == n_draft + 1`. A full512 diagnostic
(`gemma4-q8-gpu0-acceptprefix-parity-full512-v2-20260630T043728Z`) passed the
fixed cold gate, `cached_tokens=0`, and 128/128 canary at
`117.60357286123875 tok/s` median 1-100 after TTFT, with p10
`104.05553056029459`, mean `117.26191569638787`, full512 after-TTFT median
`112.95266056446746`, wall full512 median `108.53028475372003`, and median
TTFT `178.42455202480778 ms`. This is not a record path and was not submitted:
it intentionally adds checking work and stays below the
`123.67689864739785 tok/s` record. The value is design proof: sampled verifier
rows can derive the same accept-prefix decision, including short-tail steps.
Next verifier work should implement the real backend op or a different
profile-backed verifier/MoE boundary reduction; do not spend more GPU time on
parity-mode throughput. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-accept-prefix-parity-probe.md`.

2026-06-30 FA-on 32K/VMM p_min gap screen: a final small threshold-only screen
tested `p_min=0.04625`, `0.04725`, `0.047625`, and `0.04875` under the current
selected-down VDR2 strict128 identity. All lanes passed the fixed cold gate and
canary with `cached_tokens=0`, but the best candidate was `0.047625` at
`118.41776692242152 tok/s`, below the matching-stack `0.0475` controls from
`20260629-faon-vmm-depthscreen-negative.md` (`119.79709987498046` and
`119.51944277144372`). Decision: closed negative; do not full512-confirm,
submit, or reopen isolated p_min screens without a new source mechanism. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-faon-vmm-pmin-gap-screen-negative.md`.

Post-top1 profile check: skip the dense/shared FFN gate+up+GEGLU fusion for
now. The activation-profile follow-up for the top1 experiment showed the new
LM-head route active and still hot, then routed MoE gate/up
(`MUL_MAT_ID:ffn_moe_gate_up-29`). It did **not** show a visible dense/shared
FFN gate/up or standalone GEGLU node in the hot set. The only visible BF16
target is routed MoE, and the routed
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT=1` family has already been
closed as a graph-safe loss. Do not add the dense/shared `build_ffn()` fusion
unless a future profile makes dense/shared BF16 work a measured bottleneck.

2026-06-29 routed BF16 gate/up + GEGLU direct follow-up: a direct BF16 fused
routed gate/up+GEGLU backend under `LLAMA_GEMMA4_MOE_GATEUP_GEGLU_BF16=1`
rebuilt and passed the fixed cold gate plus 256 canary rows, but lost in a
paired strict128 screen. GPU1 flag-on measured `114.46712115340162 tok/s`
against GPU0 control `115.41337538098514`; GPU3 flag-on measured
`110.82969266501019` against GPU2 control `112.42229330668238`. Full-output
and wall medians also regressed. Decision: closed negative; do not run full512
or submit. Preserve the patch and result as
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-bf16-gateup-geglu-direct-negative.md`.
If revisiting this area, do not use a direct BF16 dot kernel; instead preserve
the existing BF16 matmul route and fuse only post-GEMM GEGLU/scatter after a
profile proves that work is material.

2026-06-29 GEGLU-before-down + VDR2 selected-down follow-up: the older
`LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM=1` path was wired into the
current reordered-Q8 VDR2 selected-down kernel by adding a reordered GEGLU
quantizer and fixing the SYCL support predicate for reordered down weights. The
first candidate crashed because the backend-only op was assigned to CPU; after
the placement fix it passed strict128 quality, but did not clearly beat paired
controls (`115.164` / `113.306` tok/s versus controls `113.753` / `114.919`),
and stayed below the `123.67689864739785` full512 record. Decision: closed
negative/inconclusive; keep default-off and do not run full512 promotion as-is.
See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-geglu-vdr2-selected-down-negative.md`.

2026-06-29 EOG clip and SPEC_HEAD follow-up: two narrow verifier-side ideas
were screened after the selected-down record. `LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1`
is valid and real (`eog_trim calls=512 tokens=640` in the profiled strict128
run), but it did not beat the full512 record under the primary fresh metric:
best EOG full512 lane was `113.58569073629727 tok/s` versus the current
`123.67689864739785`. It may remain useful as a default-off terminal cleanup,
but it is not a LocalMaxxing record. The late-head bonus plus dedicated
SPEC_HEAD fused argmax branch (`LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1` +
`LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1`) lost in both strict128 lanes
(`107.87` and `107.29 tok/s`), so do not promote it as implemented. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-eogclip-and-spechead-negative.md`.

2026-06-29 prefix2 tail-head verifier follow-up: a more surgical verifier-row
shape was implemented under `LLAMA_SPEC_VERIFY_PREFIX2_TAIL_HEAD=1` plus
`LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1`. It kept only two prefix verifier rows
in the main target decode and, if both matched, ran a batched `SPEC_HEAD` pass
over saved `h_nextn` rows for the third draft token plus bonus token. The path
passed the fixed cold gate and 128/128 canary rows, but lost decisively:
controls measured `113.061` and `109.841 tok/s`, while prefix2 measured
`106.396 tok/s` and `100.897 tok/s` with profiling. The server profile showed
`prefix2_tail head_ms=1762.285 calls=649 avg=2.715 ms`; prefix rows matched on
almost every generation step, so the extra full-vocab head pass ran too often
and outweighed the verifier-row savings. Decision: closed negative; do not
full512-confirm or submit this implementation. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-prefix2-tail-head-negative.md`.

2026-06-29 fused selected-softmax into selected-down VDR2 follow-up:
`LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1` folds the selected-softmax
weight computation into the VDR2 reordered-Q8 selected-down weighted-sum kernel
for decode-small Gemma MoE rows. The path passed the fixed cold gate and
512/512 canary rows in all four strict128 lanes, and produced a small paired
win: GPU1 flag-on `114.762` versus GPU0 control `113.943`, and GPU3 flag-on
`115.554` versus GPU2 control `113.967`. This is a valid small positive in the
intended verifier-MoE boundary, but **not promoted** because the best strict128
candidate remained below the current full512 record
`123.67689864739785 tok/s`. Keep the flag default-off and preserve the patch;
the later full512 promotion screen was run and lost. Full512 results:

- control GPU0:
  `data/gemma4-q8-gpu0-fusedselsoft-full512-control-20260629T194706Z/summary.json`,
  `112.21988003325279 tok/s`;
- flag-on GPU1:
  `data/gemma4-q8-gpu1-fusedselsoft-full512-on-20260629T194706Z/summary.json`,
  `111.89648891729823 tok/s`;
- flag-on + EOG clip GPU2:
  `data/gemma4-q8-gpu2-fusedselsoft-eog-full512-on-20260629T194706Z/summary.json`,
  `111.90908727268967 tok/s`;
- control GPU3:
  `data/gemma4-q8-gpu3-fusedselsoft-full512-control-20260629T194706Z/summary.json`,
  `112.99706496186322 tok/s`.

All four were valid fresh-response runs (`cached_tokens=0`, canary 512/512,
realistic gate passed), but both candidates were below same-day controls and
the promoted record. Do not submit or retest this interaction as a record lane.
See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-down-selected-softmax-strict128.md`
and
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-selected-softmax-full512-negative.md`.

2026-06-29 adaptive bonus-row follow-up:
`LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_ROW=1` was tested with exact no-bonus
full-match handling after the current-response full-accept rate warmed up. All
four strict128 lanes were valid fresh-response runs (`cached_tokens=0`,
canary 128/128, realistic gate passed), but every adaptive lane lost to the
same-build control. Control measured `112.020984 tok/s`; adaptive rows measured
`109.555804`, `103.515232`, and `99.681293 tok/s` depending on warmup and
minimum full-accept threshold. The best adaptive row also had a much worse p10.
Conclusion: verifier row savings that remove or weaken the current bonus
pipeline are not productive. Preserve the patch/result, but do not full512
confirm or submit. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-adaptive-bonus-row-negative.md`.

2026-06-29 deferred verifier pending-`h` copy follow-up:
`LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY=1` skips the verifier-batch copy from
the final target row into `pending_h`, relying on `accept()` to copy the exact
accepted row before the next draft. This was a low-risk host-copy hypothesis
after the profile showed target decode dominating. It passed the fixed cold
strict128 gate and canary in a paired screen plus cross-over, but the result was
negative: controls measured `115.186`, `113.075`, `113.344`, and `116.208`
tok/s; flag-on lanes measured `111.144`, `118.110`, `110.300`, and `110.134`
tok/s. The single `118.110` outlier did not survive cross-over. Control
medians averaged `114.453`; flag-on medians averaged `112.422`. Do not
full512-confirm or submit. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-defer-verifier-pending-h-copy-negative.md`.

Current handoff note: see
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-selecteddown-next-lane-triage.md`
for the 2026-06-29 post-profile audit, closed-lane list, and the preserved
source patch snapshot before further edits.

2026-06-28 crack-100 reliability update: a single strict full512 frequency-floor
run at `2400,2800` hit `100.22397388514726 tok/s`, and an earlier unroll6 row
hit `101.076 tok/s`, but confirmations did not hold above 100. Four parallel
2400-floor confirmations measured only `96.052`, `93.510`, `92.856`, and
`94.440 tok/s`; an exact best-identity rerun with affinity and unroll6 measured
`97.054 tok/s`. Decision: valid high observations, not reliable records. The
GPUs were restored to the default `400,2800` range. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T1350-crack100-frequency-floor-reliability-negative.md`.

2026-06-28 end-of-day crack-100 audit: the remaining config-only lanes were
closed. Q2_K MTP draft lost decisively under strict128 (`85.779-88.903 tok/s`)
against the same-window Q4_0 control (`95.282 tok/s`). The later strict ledger
audit found every `>100 tok/s` fresh/cache0 observation had an immediate repeat
or confirmation that collapsed below the promoted `98.340` record or below the
solo `98.680` high-side observation. Existing source knobs around postnorm,
h_nextn, fused verifier argmax, raw argmax, tail-gating, no-bonus rows, and
runtime knobs are also closed in the sweep ledger. Decision: stop
configuration roulette. The next reliable `>100` attempt needs a true
source-level verifier-cost reduction, not another flag sweep. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md`.

2026-06-27 adaptive MTP update: the default-off adaptive-depth patch and MTP
`dp.n_max` generation-stop fix were tested under the strict realistic gate. All
v13/v14 rows passed quality and had `cached_tokens=0`, but the best adaptive
row was only `83.34212495239542 tok/s`, below both the old VDR4 `87.611` row
and the now-superseded VDR2 `90.983` record. Keep the
patch as a negative artifact; do not submit or promote it. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1841-realistic-adaptive-mtp-dpnmax.md`.

2026-06-27 static/VDR2 strict update: after the adaptive-depth negative, a
four-GPU strict sweep tested static `n_max=3` variants and then transferred the
older synthetic VDR2 Q8 reorder build back onto the realistic cold suite. The
static VDR4 variations stayed below record (`80.3-85.6 tok/s`), but VDR2 at
the strict `n3/n_min=2/UBATCH=1024` shape repeatedly landed near `87-89 tok/s`
and produced a `89.45543282863798 tok/s` record at `p_min=0.0475`; a later
tight p-min repeat of the same VDR2 family produced the then-current
`90.32179401019857 tok/s` record.
See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1906-realistic-static-and-vdr2.md`.
Also see
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2017-vdr2-pmin-tight-repeat.md`.

2026-06-27 tight `p_min` follow-up: a full strict v22 sweep at `p_min`
`0.04725`, `0.047375`, repeated `0.0475`, and `0.047625` did not beat the
record. Best row was `88.971548 tok/s`; the `0.0475` repeat fell to
`87.144002 tok/s`. This suggests the older `90.32179401019857 tok/s` row was a
valid high repeat, but it is now superseded by the confirmed
`90.98312252660529 tok/s` row; more tiny `p_min` sweeps are low ROI without a
new code/runtime change. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2031-vdr2-pmin-tight-negative.md`.

2026-06-27 source follow-up: reordered-Q8 grouped multi-token MoE
(`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER=1`) passed the strict
realistic gate and 32/32 canary, but regressed to
`83.90758854375754 tok/s` median tokens 1-100 after TTFT. The route profile
made duplicate-expert grouping look attractive, but for the actual `n_max=3`
verifier shape the grouped reordered path appears to add more
branch/scatter/register pressure than it saves. Preserve the patch as a
negative artifact and do not retry this exact approach without lower-level
kernel evidence. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2055-q8-reorder-grouped-negative.md`.

2026-06-27 direct VDR2 Q8 reorder follow-up: a narrower default-off
`LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1` specialization targeted the
actual active verifier shape (`ids ne=[8,2]`, `src1 ne=[2816,1,2,1]`) and
removed generic reordered-Q8 trait/addressing overhead. It passed the strict
fresh-response gate, but did not beat the record. The screen reached
`90.71249998925582 tok/s`, while the four-GPU confirmation measured
`89.78446476095618`, `88.2181491417087`, `86.62953234681859`, and
`86.36862208450489 tok/s`. Keep the patch as a default-off negative artifact.
Do not submit or include it in promoted reproduction commands. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2310-q8-reorder-direct-vdr2-negative.md`.

2026-06-28 top-8 slots Q8 reorder follow-up: a default-off
`LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_TOP8_SLOTS=1` kernel computed all eight
selected expert slots for one token/row in one workgroup to reuse the quantized
activation row. It passed the strict fresh-response gate on all four B70 lanes,
but did not beat the record. The four lanes measured `91.45707162294053`,
`88.36905349287005`, `87.57423762721632`, and `86.84604657306411 tok/s`.
Decision: negative, do not submit. Lesson: the activation reuse is outweighed
by register/private-memory pressure for the active `ids=[8,2]` verifier shape.
Small reordered-Q8 addressing variants (`pair_slots`, `direct_vdr2`,
`top8_slots`, grouped) are now exhausted unless a kernel profile points to a
new design. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0005-q8-reorder-top8slots-negative.md`.

2026-06-27 raw verifier argmax follow-up: default-off
`LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` publishes greedy sampled rows from raw
LM-head logits before Gemma's final softcap. This is exact when suppress-token
bias is absent because the final-logit softcap is monotonic. It passed the
strict realistic gate in every row tested, but the apparent
`90.61464067224665 tok/s` screen did not confirm: four same-config confirmation
lanes measured only `85.38010810396247`, `86.06270410755482`,
`88.22852366375129`, and `87.95831897318453 tok/s`. Keep the patch as a
default-off negative artifact and do not submit. Lesson: skipping post-LM-head
softcap is not enough; a material verifier win must avoid the full vocabulary
projection or reduce verifier MoE work. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2129-raw-spec-verify-argmax-negative.md`.

2026-06-27 Q8_0 target control: the alternate
`gemma-4-26B-A4B-it-Q8_0.gguf` target/verifier is a separate control lane, not
the promoted no-quality-loss `UD-Q8_K_XL` lane. It has a strong no-spec
baseline (`82.9625778781127 tok/s`), but it did not produce a reproducible
strict record. The best Q8_0 screen,
`n_max=3`/`n_min=1`/`p_min=0.0475`, reached
`91.5564081422068 tok/s`, but exact confirmations landed at
`88.94881774985208` and `89.89234269084307`; the best deeper row was
`n_max=4`/`n_min=2` at `90.27678402019421`, still below both the old
`UD-Q8_K_XL` record (`98.34046474459183`) and the current
`123.67689864739785` record. Keep Q8_0 as a compatibility/control
lane, not a promoted LocalMaxxing row. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2144-q80-target-strict-negative.md`.

2026-06-27 VDR2 confirmation and n=4 update: a four-lane strict UD-Q8_K_XL
sweep retested the current VDR2 `n3/n_min=2/p_min=0.0475/UBATCH=1024` identity
and two deeper `n_max=4` variants. The n=3 control produced a valid
`91.39281557735391 tok/s` high observation, but a four-repeat confirmation
spread measured `88.57072965699355`, `90.98312252660529`,
`89.87311437412865`, and `87.29987510414621 tok/s`; the conservative
`90.98312252660529` row was submitted and approved as `cmqwxep4a03qiqr010chjn93s`.
The n=4 variants were clear losses (`82.12005329123728` for `n_min=1`,
`85.93327599447983` for `n_min=2`), so do not continue deeper-MTP threshold
sweeps without a new acceptance/scoring mechanism. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2213-vdr2-recordconfirm-and-n4-negative.md`.

2026-06-28 strict profile update: a current-stack profile run under the fixed
realistic cold suite passed validity but measured only
`89.65814180509349 tok/s`, below the current submitted record. Its
value is diagnostic: target/verifier `process_ubatch_ms` was `88713.159`, while
draft `process_ubatch_ms` was only `6037.002`; sampler calls, hidden handoff,
and device-handoff counters were zero. The lane is target/verifier-forward
bound under the real gate. Do not spend more effort on blind draft knobs or
small reordered-Q8 addressing variants unless a new profile points there. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0013-strict-current-profile.md`.

2026-06-28 node-profile update: a heavier SYCL node-profile run on the same
strict identity passed the realistic gate (`cached_tokens=0`) but slowed to
`59.55962845637647 tok/s`, so it is diagnostic only. Its top node was the
target/verifier LM-head full-vocab projection (`MUL_MAT:node_2075`,
`891.483 ms / 646 calls = 1.380 ms/call`), followed by verifier MoE gate/up and
down `MUL_MAT_ID` nodes; the assistant MTP argmax nodes were smaller
(`~0.394 ms/call`). This reinforces the current direction: stop draft-side and
tiny reordered-Q8 sweeps unless new evidence appears; focus on reducing exact
target verifier rows, exact LM-head verification cost, or a materially new
Gemma4 verifier-MoE boundary change. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0029-strict-vdr2-nodeprofile.md`.

2026-06-28 runtime copy/allocation screen: a four-B70 strict sweep retested
the current VDR2 record identity while varying cheap SYCL/Level Zero runtime
knobs. All rows passed the realistic cold-suite gate and 32/32 canary, but
none beat the record: control `85.40977109929057 tok/s`,
`GGML_SYCL_USE_ASYNC_MEM_OP=0` `89.89151710630107`,
`GGML_SYCL_DEV2DEV_MEMCPY=1` `87.20277456169313`,
`GGML_SYCL_USE_LEVEL_ZERO_API=0` `86.32650903005273`. Decision: negative; do
not submit and do not keep retesting copy/allocation flags without a profile
showing copy/allocation pressure. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0034-strict-runtime-sycl-copy-screen.md`.

2026-06-28 strict route-cache/gate-up screen: a four-B70 sweep retested
low-cost route metadata variants under the current realistic cold-suite gate.
All rows passed validity and 32/32 canary, but none beat the submitted record:
`LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT=1`
`88.64037514681797 tok/s`,
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP=1`
`88.18334423611053`,
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE=1`
`87.44848512222445`, and singleton+device-map `85.4969891651534`.
Decision: negative; route-cache/gate-up metadata flags are closed under the
strict gate unless a future profile shows a new bottleneck. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0102-strict-routecache-gateup-negative.md`.

## Historical Diagnostic Frontier Pending Realistic Gate

Current best synthetic filled-long one-B70 diagnostic result is
`data/gemma4-q8-gpu0-q8reorder-vdr2-ub720-rms-20260627T155153Z/`:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- recipe: llama.cpp AOT BMG, draft-MTP `n=7`, `n_min=3`,
  `p_min=0.10`, backend draft sampling off,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`,
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`, f16 target/draft KV,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`,
  `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`,
  `--ctx-checkpoints 0`, `GGML_SYCL_ENABLE_VMM=0`,
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`,
  `UBATCH_SIZE=720`, `THREADS=8`, `POLL=100`, `FLASH_ATTN=off`,
  `GGML_SYCL_DISABLE_GRAPH=0`;
- validation: chat canary **1536 repeats / 6144 rows**, all benchmark rows
  `cached_tokens=0`;
- synthetic filled-long row0: **176.21623213048554 tok/s** after TTFT;
- supporting repeated-request mean: `176.40259133127742 tok/s`;
- LocalMaxxing: `cmqwkedg303jeqr013z753j62` (submitted before the realistic
  final-gate policy; classify as diagnostic until revalidated);
- note: this is the first synthetic diagnostic Gemma 26B Q8 result above
  the `>150 tok/s` target, but it is not a promoted real-world throughput claim
  until the fixed realistic prompt suite passes. The target/verifier remains
  UD-Q8_K_XL; the Q8_0 reorder flag refers to internal GGML Q8_0 MoE expert
  tensors.

The actual research target remains **>150 tok/s realistic cold-response**. The current
llama.cpp direct-unroll MTP path no longer performs one assistant
`llama_decode()` per draft token; it batches the assistant argmax-ID unroll in
one draft decode. The remaining gap is dominated by target/verifier work
(`process_ubatch`, especially Gemma4 verifier MoE plus the LM head), not by
draft precision or p-min-only threshold sweeps. Further p-min/thread/runtime
shape sweeps are useful only as cleanup; a 2x-class improvement likely requires
a structural verifier-side reduction or a different fresh-valid speculation
engine.

2026-06-27 diagnostic frontier update: isolated selected-softmax fused-weights and
fused-output-argmax screens were mostly neutral or valid losses, but the later
stacked route-cache cleanup (`LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` +
`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`) fully validated at
`103.95374341972274 tok/s`, then a same-stack full repeat reached
`103.9826628154082 tok/s`, then `UBATCH_SIZE=768` reached
`104.07050714456982 tok/s`, then the threshold repeat `n_min=3` / `p_min=0.10`
reached `104.22626983476746 tok/s` under the older filled-long diagnostic gate.
These are small pre-final-gate synthetic micro-records over `103.51547512013657`,
not material progress toward the current `>150 tok/s` realistic cold-response
target.
Audits found that the target-to-draft
`h_nextn` host handoff is real but profile-small, the direct selected-down
fusion family has already been tested in several losing variants, and the
verifier LM-head/argmax shortcut family is also exhausted. See
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260626T1244-frontier-pivot.md`.
The follow-up sorted-router screens were also valid but below record:
`LLAMA_GEMMA4_MOE_TOP_K=1` + `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1` measured
`100.177 tok/s`; adding `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1` measured
`100.505 tok/s`; the direct-F32 parallel-slot fused-down variant measured
`100.646 tok/s`. Do not continue small Gemma flag sweeps unless they are
materially new; the cleanup combo above is the only current scalar-stack win.
Per the current user priority, keep Gemma as the active lane:
the next Gemma work should be the verifier-side selected-softmax/down epilogue
boundary, graph-level multi-token assistant unroll, or exact verifier
candidate-vs-max design rather than a pivot to MiniMax. Source audit on
2026-06-26 specifically warned against naive full MoE fusion: preserve the
tuned Q8 gate/up and down matmul schedule, and only fold the tiny selected
softmax into the existing down epilogue if implementing the next source patch.

2026-06-26 route-cache CTX/GPU screen and follow-up: rechecked the current
route-cache recipe on four GPUs with CTX `2048`, `4096`, `8192`, and `16384`
at screen depth (`128/128` canary, 2 benchmark repeats). All rows had
`cached_tokens=0`. The best screen was GPU2 / CTX `8192` at
`103.89855970182825 tok/s` synthetic row0 after TTFT. Full validation on the same
GPU2/ctx8192 lane passed `1536/1536` canary and landed at
`103.51547512013657 tok/s` synthetic row0 after TTFT, enough to supersede the
`103.30108468098005` route-cache micro-record but still small enough to treat
as runtime/GPU variance cleanup rather than architectural progress. See
`../../patches/gemma4-26b-a4b-q8-b70/20260626T1914-routecache-ctx-gpu-screen.md`.

2026-06-26 route-cache cleanup follow-up: a four-way screen on the current
route-cache identity found a tiny stacked win from
`LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` plus
`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`. Full validation passed
`1536/1536` canary, all benchmark rows had `cached_tokens=0`, and row0 reached
`103.95374341972274 tok/s` after TTFT (`104.13506066488091` supporting mean).
LocalMaxxing accepted it as `cmqviful602p0qr01vp27jw5i`. This supersedes the
`103.51547512013657` route-cache row, but remains a small cleanup gain.

2026-06-26 same-stack repeat and unique-prompt check: exact current-stack full
repeat on GPU0 passed `1536/1536`, all benchmark rows had `cached_tokens=0`,
and row0 reached `103.9826628154082 tok/s` after TTFT
(`104.09604904731648` repeated-prompt support mean). LocalMaxxing accepted it
as `cmqvjupek02pgqr01d46algvg`. This is a variance-class record, not a new
mechanism. A new `BENCH_PROMPT_MODE=filled-long-unique` screen on GPU1 used
four distinct prompt hashes, passed `256/256`, all rows had `cached_tokens=0`,
and produced `100.8959686363723 tok/s` row0 / `101.16162483108214 tok/s`
fresh-eligible mean, confirming repeated-prompt means should remain
support-only unless using the unique prompt mode.

2026-06-27 UBATCH/threshold micro-record and profile: `UBATCH_SIZE=768` on
GPU3 first passed `1536` canary repeats / `6144` rows and reached
`104.07050714456982 tok/s` synthetic row0 after TTFT, LocalMaxxing
`cmqvmjvzx02qvqr01qh9jikow`. A later GPU0 full validation with the same scalar
stack plus `MTP_N_MIN=3` / `MTP_P_MIN=0.10` passed `6144/6144` canary rows and
reached `104.22626983476746 tok/s` synthetic row0, support mean
`104.17418893412489`, LocalMaxxing `cmqvv3kop0309qr013ekr8apu`. This is still
only a tiny variance-class headline, not a new mechanism. A short profiling
diagnostic on
GPU0 with the same UBATCH shape
(`data/gemma4-q8-gpu0-nodeprofile-current-ub768-20260627T011603Z/`) is not a
record comparison (`MAX_TOKENS=128`, profiling enabled) but confirms the hot
nodes: top final profile entries are `MUL_MAT_ID:ffn_moe_gate_up-0`
(`139.525 ms`), target LM head `MUL_MAT:node_2135` (`93.900 ms`), then mostly
`ffn_moe_gate_up-*` plus a few MoE down projections. Draft MTP stats for the
diagnostic were `187/235` accepted/generated draft tokens with mean accepted
length `6.50`. The next source work should reduce real verifier MoE/LM-head
work or change the fresh-valid speculation structure; do not repeat existing
GEGLU/down, broad `MUL_MAT_ID`, ngram-history, or naive high-depth MTP lanes.

2026-06-27 RMS-reuse micro-record: a default-off source patch
`LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1` reuses the unweighted `RMS(attn_out)` in
each Gemma4 MoE layer across the shared MLP, routed expert FFN input, and
router input. It passed a screen at `104.27340324045828 tok/s`, then full
validation
`data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
passed `6144/6144` canary rows and reached `104.30919255569083 tok/s` fresh
row0 (`cached_tokens=0`), support mean `103.93445004566178`. LocalMaxxing
approved it as `cmqw1tgzx0366qr01g4lkv7f1`. Treat this as a tiny row0
micro-record only: the support mean is lower than the prior run due to one
slower support row, so the structural speedup is marginal at best.

2026-06-27 Q8 MoE-ID reorder breakthrough: default-off
`LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1` makes broad
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` viable for the UD-Q8_K_XL target's
internal Q8_0 MoE expert tensors. Full validation
`data/gemma4-q8-gpu0-mulmatid-fast-q8reorder-ub768-fullconfirm-20260627T142318Z/`
passed `6144/6144` canary rows and reached `169.9489959621758 tok/s`
synthetic row0 (`cached_tokens=0`), support mean `169.5501066933547`. LocalMaxxing
approved it as `cmqwh8du403gfqr01d6ut1ddo`. Follow-up full validation at
`UBATCH_SIZE=704`
`data/gemma4-q8-gpu1-q8reorder-ub704-nmin3-pmin010-fullconfirm-20260627T143126Z/`
passed `6144/6144` canary rows and moved the pre-final-gate diagnostic high to
`170.11205232778414 tok/s` synthetic row0, support mean
`169.87578310923394`, LocalMaxxing `cmqwhkbzj03guqr01h00c8n04`. A later
`UBATCH_SIZE=720` full confirmation
`data/gemma4-q8-gpu0-q8reorder-ub720-nmin3-pmin010-fullconfirm-20260627T144855Z/`
passed `6144/6144` rows and raised the pre-final-gate diagnostic high to
`176.21623213048554 tok/s` synthetic row0, support mean `176.40259133127742`,
LocalMaxxing `cmqwkedg303jeqr013z753j62`.

2026-06-27 clean-repro negative sweep: after reconstructing a clean
`c926ad098` source tree plus the promoted record patches, the corrected
`filled-long` benchmark identity reproduced the `104 tok/s` lane but did not
produce a new record. Q8 ncols-hoist was neutral (`104.163` screen, no
promotion). Thresholds around `n_min=2/3` and `p_min=0.02-0.10` were losses
after full confirmation (`n_min=2,p_min=0.05` full: `104.200129`, `384/384`).
UBATCH/CTX/runtime screens produced only variance: `UBATCH=704` screened at
`104.778837` but fully confirmed at `104.191834`; `UR_L0_USE_IMMEDIATE_COMMANDLISTS=0`
screened at `104.386620` but fully confirmed at `102.440578`; unique-prompt
unique-prompt diagnostic checks stayed around `100-101.5 tok/s`. Do not continue isolated
`p_min`, `n_min`, UBATCH, CTX, thread, poll, VMM, graph-off, or immediate-list
sweeps unless they are attached to a new source mechanism. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1059-clean-repro-threshold-q8hoist.md`.

2026-06-27 post-record cleanup / diagnostics: a config-neighborhood screen
around the RMS-reuse record produced only shallow same-config variance
(`104.416546 tok/s` screen on the exact record identity); the intended full
rerun passed the `6144/6144` canary gate but exited before benchmarking due to
a transient harness quoting error. Treat it as canary-only. A prequant
route-row source experiment then failed in its unsafe form and measured
`104.0281678873085 tok/s` after guards, below record; the active source patch
was removed. A clean phase profile on the current stack confirmed target
`process_ubatch_ms=6479.261` versus draft `process_ubatch_ms=305.661`, with
sampled-ID extraction only `127.149 ms`. Conclusion: keep focusing on
target/verifier MoE or LM-head economics; stop spending runs on route-row
plumbing or tiny config sweeps. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0858-rmsreuse-config-neighborhood.md`,
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0939-prequant-route-rows-negative.md`,
and
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0950-currentstack-phaseprofile-clean.md`.

2026-06-27 route-profile follow-up confirmed why route-row plumbing has become
a dead end: decode-like `tok2_8` routed expert calls average `7.665` tokens and
`6.593` max rows per expert slice, and llama.cpp's SYCL backend already routes
`src1->ne[1] <= 8` Q8 slices through `mul_mat_vec_q8_0_q8_1_sycl_switch_ncols()`.
The hot path is therefore the actual Q8 MMVQ body, not the missing selection of
MMVQ. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1001-routeprofile-mmvq-confirmed.md`.
A compile-time VDR=4 screen for the Q8 MMVQ body then passed canaries but
collapsed to `44.21455725216031 tok/s` synthetic row0 after TTFT when rerun with
the correct record-lane MTP identity. Do not pursue global Q8 MMVQ VDR widening;
the next source candidate should preserve the tuned `VDR=2` dot shape and
restructure the Q8 multi-column body instead. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1021-q8-mmvq-vdr4-negative.md`.

2026-06-27 source rebuild warning: subsequent Q8 multi-column body work exposed
a reproducibility blocker. A rebuilt `q8hoist` binary with the new feature gate
disabled still measured only `40.15528197170138 tok/s` synthetic row0, and the
feature-enabled run measured `43.152077041798634 tok/s`; both are far below the
stale record binary. CMake identity matched the record build for the relevant
SYCL/AOT flags, so the working hypothesis is source-patch stack drift rather
than a q8hoist-specific loss. Stop interpreting rebuilt source screens as clean
kernel comparisons until a clean `c926ad098` worktree plus known record patches
reproduces the `104 tok/s` lane. The full dirty source diff is preserved as an
audit artifact in
`../../patches/gemma4-26b-a4b-q8-b70/20260627T1039-current-dirty-source-rebuild-mismatch.patch`;
see
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1039-source-rebuild-mismatch.md`.

2026-06-27 screen audit update: a p-min/UBATCH neighborhood sweep found three
screen-only rows above the then-current `104.07050714456982 tok/s` record. Two
promoted full validations were valid losses, and the third produced only a
small `104.22626983476746 tok/s` micro-record. This reinforces that the lane is
mostly row0/runtime variance until the direct-unroll path exposes a real
confidence score:

- `data/gemma4-q8-gpu0-ub768-pmin010-screen-20260627T031002Z/summary.json`:
  `104.90764207185568 tok/s`, 64/64 canary rows, `UBATCH_SIZE=768`,
  `MTP_N_MIN=2`, `MTP_P_MIN=0.10`. Full run
  `data/gemma4-q8-gpu0-ub768-pmin010-fullrepeat-20260627T031448Z/summary.json`
  passed `6144/6144` canary rows but landed at only
  `104.00197765543678 tok/s` synthetic row0 -> valid loss.
- `data/gemma4-q8-gpu3-ub768-nmin3-pmin0136-screen-20260627T031002Z/summary.json`:
  `104.17822408660554 tok/s`, 64/64 canary rows, `n_min=3`, `p_min=0.136`.
  Full run
  `data/gemma4-q8-gpu3-ub768-nmin3-pmin0136-fullrepeat-20260627T034150Z/summary.json`
  passed `6144/6144` canary rows but landed at only
  `103.98432370694714 tok/s` synthetic row0 -> valid loss.
- `data/gemma4-q8-gpu3-u768-nmin3-pmin010-screen-20260627T032140Z/summary.json`:
  `104.12813019085074 tok/s`, 64/64 canary rows, `n_min=3`, `p_min=0.10`.
  Full validation
  `data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z/summary.json`
  passed `6144/6144` canary rows and landed at
  `104.22626983476746 tok/s` synthetic row0 / `104.17418893412489` support mean,
  LocalMaxxing `cmqvv3kop0309qr013ekr8apu`. Valid micro-record, not a material
  step toward `>150 tok/s`.

Avoid over-reading these screens. Similar prior screens collapsed under full
validation: `UBATCH_SIZE=832` screened at `105.00621024594338` but validated at
`103.90548697450369`; GEGLU epilogue route-cache screened at `104.70795597094846`
but validated at `101.8211074778421`; `BATCH=1024/UBATCH=768` screened at
`104.63299392132738` and validated as only the current `104.07050714456982`
record.

Direct-source audit found the likely reason these threshold-only sweeps are so
weak: the promoted direct-unroll assistant path emits sampled token IDs only and
bypasses the normal `MTP_P_MIN` / `draft_logit_gap_min` checks. Treat future
`p_min` sweeps as low-value unless paired with a source patch that returns a
top1/top2 score, probability, or gap from the fast direct path.

2026-06-27 source roadmap after audit:

2026-06-27 draft-quant recheck on the current record stack tested
`Q4_K_M-MTP`, `Q5_K_M-MTP`, `Q6_K-MTP`, and `Q8_0-MTP` drafts at
`UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`. All passed the screen
canary with `cached_tokens=0`, but all were below the `104.22626983476746 tok/s`
fresh record; the best was `Q4_K_M-MTP` at `103.78730901696501 tok/s`, while
`Q8_0-MTP` fell to `100.18260696589377 tok/s`. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0700-draft-quant-current-stack-loss.md`.
Conclusion: do not spend more runs on higher-precision MTP drafts for this Q8
target lane unless a new mechanism changes the verifier economics.

1. ~~Fuse verifier router selection plus selected-weight materialization for
   Gemma4 verifier shapes (`n_expert=128`, `n_expert_used=8`, `n_tokens<=8`).
   This should replace top-k/argsort plus selected-weight gather/softmax, not
   merely fuse weights after IDs already exist. Start around
   `/home/steve/src/llama.cpp-gemma-record-stack/src/models/gemma4.cpp` router
   logits and `build_moe_ffn()` plus
   `/home/steve/src/llama.cpp-gemma-record-stack/src/llama-graph.cpp` selected
   logits/top-k/softmax construction. Candidate flag:
   `LLAMA_GEMMA4_MOE_FUSED_ROUTER_SELECTED_WEIGHTS=1`.~~
   Tested 2026-06-27 as
   `data/gemma4-q8-gpu1-routerselectedweights-screen-20260627T050319Z/`:
   canary `64/64`, synthetic row0 `101.52715106143687 tok/s`, below the
   `104.22626983476746` record. Patch snapshot:
   `../../patches/gemma4-26b-a4b-q8-b70/20260627T0503-llamacpp-gemma4-router-selected-weights-negative-current-stack.patch`.
   See
   `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0503-router-selected-weights-negative.md`.
   Conclusion: valid loss; do not continue this exact design unless a later
   profile makes router materialization hot again.
2. ~~Build a narrow shape-specific Q8 verifier gate/up bypass for the current
   route-cache shapes. The hottest profile nodes are
   `MUL_MAT_ID:ffn_moe_gate_up-*`; avoid broad `MUL_MAT_ID` rewrites already
   recorded as losses. Candidate flag:
   `LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT=1`.~~
   Screened 2026-06-27 as
   `data/gemma4-q8-gpu2-gateup-singleton-direct-screen-20260627T052517Z/`:
   canary `64/64`, cached tokens `[0]`, output hash matched the promoted
   record, but synthetic row0 was `104.12278210887227 tok/s`, just below the
   `104.22626983476746 tok/s` record. Same-GPU flag-off control was slower
   (`102.16498485841758 tok/s`) and produced a different benchmark hash, so the
   path is not an obvious loss, but it is not a record breaker. Patch snapshot:
   `../../patches/gemma4-26b-a4b-q8-b70/20260627T0525-llamacpp-gemma4-gateup-singleton-direct-current-stack.patch`.
   See
   `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0525-gateup-singleton-direct-screen.md`.
   Do not promote without a node-profile win and a fresh full validation.
3. Explore an exact verifier LM-head candidate-vs-max op. Existing fused-output
   argmax paths were slower, and a source audit confirmed that simply rewiring
   `ggml_mul_mat_argmax(model.output, cur)` is not enough. A viable variant
   must compare drafted candidate logits against the true maximum exactly,
   preserve greedy correctness, and prove lower verifier LM-head/output work
   on a strict128 profile before any full512 promotion. Candidate flag:
   `LLAMA_SPEC_VERIFY_CANDIDATE_MAX=1`.
4. Fix direct-unroll confidence gating. Current direct-unroll argmax bypasses
   `MTP_P_MIN`/logit-gap checks, so p-min-only screens mostly measure variance.
   A useful version would return top1/top2 score or gap from the assistant
   direct path and reduce verifier rows on low-confidence tails without using
   warmed/history state. Candidate flags:
   `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES=1` or
   `LLAMA_MTP_DRAFT_DIRECT_UNROLL_CONF_GATE=1`.

2026-06-27 blind direct-unroll depth screen: four fresh-valid screens on the
current record stack tested larger direct-unroll depths without changing the
verifier economics. All passed `64/64` chat canary rows with `cached_tokens=0`,
but all were large valid losses versus the `104.22626983476746 tok/s` record:
`n=8` reached `66.84787263988618 tok/s`, `n=9` reached
`71.63228403027686`, `n=10` reached `76.20014071584247`, and `n=12` reached
`82.92906186353807`. See
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0531-direct-unroll-depth-losses.md`.
Conclusion: stop blind depth expansion. Higher depths are only worth retesting
after a source change supplies real direct-path confidence scores or materially
reduces target verifier MoE/LM-head work.

2026-06-27 current-stack MTP profile diagnostic: a short `MAX_TOKENS=128`
profile on GPU0 with the record stack and `LLAMA_MTP_DRAFT_PROFILE=1` is
documented in
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0538-currentstack-mtp-profile.md`.
It is not a headline result because canaries ran first and the single benchmark
row reported `cached_tokens=[1]`. The useful profile finding is that the
assistant direct path is fully ID-only: `fast_topk_calls=82`,
`vocab_scanned=0`, `sampler_calls=0`, `stops gap=0`, `pmin=0`,
`avg_top1_p=1.000000`, and `avg_logit_gap=0.000000`. Target verifier
`process_ubatch_ms=12118.505` dominates draft `process_ubatch_ms=488.134`.
Conclusion: do not spend more time on threshold-only sweeps or blind depth.
Useful work needs either a compact direct-path confidence score or less target
verifier MoE / LM-head work. A proposed `ffn_moe_gate_up_scaled` epilogue is
dead for the current path because profiles show no such scale node; hot nodes
are plain `MUL_MAT_ID:ffn_moe_gate_up-*`.

2026-06-26 verifier profile update:

- current-stack profile control reproduced the promoted family at
  `102.3599780663357 tok/s` row 0, `cached_tokens=0`, canary `64/64`;
- target verifier/model time dominates: target `process_ubatch_ms` was
  `23728.047` of `24225.592` target ms, while draft decode was only
  `1348.637` ms;
- node-profile-detail maps the hot anonymous nodes: `node_2255` is the
  target/verifier LM head, `result_output` is the assistant/draft LM head, and
  `node_64` / `node_139` / `node_2239` are MoE down projections;
- MoE gate/up `MUL_MAT_ID` and MoE down projections remain the core verifier
  cost. Existing output-argmax, device-H handoff, broad `MUL_MAT_ID`,
  fused-down, fused-GEGLU-down, and skip-early-weight variants were already
  tested and should not be repeated unchanged;
- see
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260626T0748-nodeprofile-detail.md`
  and patch artifact
  `patches/gemma4-26b-a4b-q8-b70/20260626T0748-llamacpp-sycl-node-profile-detail.patch`.

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
  `cmqqxbkzx01cxqo01j8p97627` (`245.98 tok/s`), but does **not** supersede any
  fresh-response draft-MTP record. The current pre-final-gate diagnostic is
  `cmqvalync02lhqr01h76rnti3` (`103.30108468098005 tok/s` first measured
  request; `103.06255061691155 tok/s` repeat mean);
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
  `cmqqsecuk01azqo018ahv0i1s`. This was later superseded by CPU cleanup plus
  fast argmax (`cmqr82niq01hgqo01v42y7ue8`: `92.397 tok/s` first measured
  request, `92.767 tok/s` supporting repeat mean). `top_k=2/4/20` were losses
  in the same sweep.
- post-record VMM/ubatch follow-ups: `ctx4096 + ub512 + VMM=0 + top_k=10`
  reached `91.43 tok/s` after TTFT with `384/384` canary and much better wall
  throughput (`82.14 tok/s`, TTFT `636 ms`), but it still missed the then-current
  `91.62` decode record. `ub1024 + VMM=0`, `top_k=9 + ub512 + VMM=0`, and an
  `ub512 + VMM=0` repeat were also valid losses (`90.80-91.17 tok/s`). Keep
  this family as a latency/wall reference, not as the promoted decode lane.
- fast top-k neighborhood after promotion: `top_k=8` reached `91.23 tok/s`,
  `top_k=12` reached `90.57`, `top_k=10 + UBATCH_SIZE=512` reached `91.32`,
  and `top_k=10 + CTX_SIZE=4096 + UBATCH_SIZE=512` reached `91.28`; all passed
  `384/384`, all missed the then-current `91.62` after-TTFT record. The ubatch variants did
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
- clean vLLM/XPU `int8_per_channel_weight_only` single-replica comparison is
  now complete. It validated chat-template quality but reached only
  `34.89 tok/s` with graph enabled; `fp8_per_tensor` improved to `40.31 tok/s`
  as a lower-precision diagnostic. Neither lane is competitive with the
  current llama.cpp Q8-target pre-final-gate diagnostic (`103.983 tok/s` first
  no-cache request; `104.096 tok/s` supporting repeat mean) from the Q4_0
  draft-MTP validation plus direct-unroll/q-only assistant-input patch,
  selected-softmax/weighted-sum MoE guards, verifier backend argmax IDs,
  deferred target `h_nextn`, batch/thread/runtime tune, one-shot route cache,
  Gemma4 assistant fused output argmax, and fused selected-softmax weights.

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

Status: **active; pre-final-gate diagnostic headline was Q8-target draft-MTP `n=7` with
Q4_0 MTP draft, fast argmax, direct argmax-ID unroll, q-only assistant
attention inputs, verifier backend argmax IDs, deferred target `h_nextn`,
selected-softmax/weighted-sum MoE guards, CPU cleanup, VMM off, batch/ubatch
1024, thread/runtime tuning, and poll 100 at `103.299 tok/s` first no-cache
request after TTFT (`102.193 tok/s` supporting repeat mean). Draftless
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

Historical filled-long diagnostic MTP server shape:

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
`--ctx-checkpoints 0`, source-level fast top-k, then CPU cleanup plus fast
argmax advanced the Q8-draft record to `94.366 tok/s`; switching only the MTP
draft to Q4_0 advanced the valid Q8-target pre-final-gate diagnostic to
`95.264 tok/s`; direct argmax-ID unroll plus q-only assistant attention inputs
then advanced the current pre-final-gate Q8-target pre-final-gate diagnostic to
**`96.822 tok/s`** first no-cache request after TTFT; a follow-up shape tune
with `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, and `THREADS=8` advanced the
valid Q8-target pre-final-gate diagnostic to **`98.491 tok/s`** first
no-cache request after TTFT; enabling SYCL graph (`GGML_SYCL_DISABLE_GRAPH=0`)
then advanced the current pre-final-gate Q8-target pre-final-gate diagnostic to
**`98.617 tok/s`** first no-cache request after TTFT (`97.956 tok/s`
supporting repeat mean), 384/384 canary, LocalMaxxing
`cmqs7uyqb00lnqr01u9dtv63r`. Verifier row-argmax IDs plus deferred target
`h_nextn`, with `MTP_P_MIN=0.14`, then advanced the current pre-final-gate Q8-target
pre-final-gate diagnostic to **`101.428 tok/s`** first no-cache request after TTFT
(`100.769 tok/s` supporting repeat mean), 384/384 canary, LocalMaxxing
`cmqsd2jpn00pwqr017fq21akz`. Restoring the safer verifier sampled-row argmax
path with stricter shape assertions then advanced it to **`101.482 tok/s`**
(`101.249 tok/s` supporting repeat mean), 1536/1536 canary, LocalMaxxing
`cmqsf630x00r1qr01d1usfo2d`; adding `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`
advanced the then-current pre-final-gate diagnostic to **`101.602 tok/s`**
(`100.835 tok/s` supporting repeat mean), 1536/1536 canary, LocalMaxxing
`cmqshlz8j00s0qr01f7lr24oh`; adding selected-softmax/weighted-sum Gemma4 MoE
source guards and retuning `MTP_P_MIN=0.136` advanced the current pre-final-gate diagnostic
to **`103.299 tok/s`** (`102.193 tok/s` supporting repeat mean), 1536/1536
canary, LocalMaxxing `cmqsylo2l011nqr011yydjvne`.

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

Status: **completed as a compatibility/control lane; not the current speed
path.**

The official HF checkpoint loads and serves through vLLM/XPU, and the wrapper
now captures enough identity for future comparisons. The important operational
fix is GPU selection: use `ONEAPI_DEVICE_SELECTOR=level_zero:*` plus
`ZE_AFFINITY_MASK=$GPU_INDEX`. The earlier `level_zero:$GPU_INDEX` form works
for GPU 0 only; GPUs 1-3 saw zero XPU devices and failed before readiness.

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

Measured results on 2026-06-23:

- `int8_per_channel_weight_only`, graph off: `27.05 tok/s`, canary `128/128`.
- `int8_per_channel_weight_only`, PIECEWISE graph: `34.89 tok/s`, canary
  `128/128`; best INT8 vLLM smoke.
- `fp8_per_tensor`, PIECEWISE graph, compile sizes `[1,2]`: `40.31 tok/s`,
  canary `64/64`; useful diagnostic but lower precision than the Q8/INT8
  primary lane.
- `mxfp8`: rejected, no available MXFP8 MoE backend on this XPU stack.
- `fp8_per_block`: rejected, Gemma expert hidden dim `704` is not divisible by
  block size `128`.

Decision: keep vLLM as a reference path for future true INT8 kernels or
prequantized checkpoints, but return active optimization to llama.cpp Q8
source/kernel work. Detailed note:
`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T2032-vllm-int8-fp8-smokes.md`.

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
6. **vLLM int8-per-channel is not the current speed fallback.** The clean
   vLLM comparison passed canaries but topped out at `34.89 tok/s` for INT8
   graph and `40.31 tok/s` for lower-precision FP8 per-tensor. Keep vLLM for
   compatibility, multimodal, or future true all-linear INT8 kernels; do not
   spend the main optimization budget there now.
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
    quality but did not beat the then-current `103.299-103.301 tok/s` Q8-target/Q4_0-draft
    first-request record in a meaningful way.
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
    transfer still dominate. Pairing the same patch with `GGML_SYCL_ENABLE_VMM=0`,
    `UBATCH_SIZE=512`, and `POLL=100` improved wall-rate/TTFT in a smoke but
    still reached only `91.38 tok/s` after TTFT. Preserve the patch as a
    component, but prioritize vLLM/XPU and deeper backend/kernel work.
13. **Q8_0 is not a speed upgrade under the current MTP recipe.** The smaller
    `gemma-4-26B-A4B-it-Q8_0.gguf` passed a 128-row smoke but reached only
    `90.44 tok/s` after TTFT, below the `UD-Q8_K_XL` record. Keep
    `UD-Q8_K_XL` as the promoted llama.cpp Q8 target unless a future runtime
    change specifically favors Q8_0.
14. **Small runtime nudges around the `103.299 tok/s` record are exhausted.**
    The 2026-06-26 four-GPU recheck of exact control, `THREADS=16`,
    `THREADS=16` plus `BATCH/UBATCH=1152`, and `MTP_P_MIN=0.1355` all passed
    `384/384` canary with row0 `cached_tokens=0`, but topped out at
    `102.338 tok/s`, below the current record. Preserve
    `THREADS=8`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, and
    `MTP_P_MIN=0.136`; the next serious attempts should reduce target verifier
    `process_ubatch` cost or change the verifier architecture rather than
    repeating p-min/thread/batch micro-sweeps. See
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260626T0717-runtime-frontier-recheck.md`.
15. **Next real source work is verifier-graph compute.** A source audit on
    2026-06-26 identified router-selection materialization fusion,
    device-side MoE route compaction, small contiguous verifier attention, and
    shared dense FFN fusion as the plausible remaining lanes. Start with router
    materialization if writing a new patch; it is narrower than attention
    specialization and matches the `process_ubatch` profile. See
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260626T0830-verifier-frontier-source-audit.md`.
16. **Q6_K fused output argmax is not a record path.** Enabling the existing
    fused output argmax op for Q6_K required adding Q6_K to both execution and
    SYCL `supports_op` for `GGML_OP_MUL_MAT_ARGMAX`; without the support guard,
    the scheduler aborted before readiness with `cur_backend_id == -1`.
    After the fix, the screen passed `128/128` canary with row0
    `cached_tokens=0`, but reached only `103.019 tok/s`, below the current
    `103.299 tok/s` record. Preserve the patch as a complete negative result,
    but do not promote it unless assistant output extraction becomes hot again.
    See
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260626T0821-q6k-fused-output-argmax.md`.
17. **Grouped duplicate-expert MoE is not enough at the strict VDR2 shape.**
    The reordered-Q8 grouped multi-token MoE path passed the strict cold gate
    but lost (`83.908 tok/s` vs the `90.322 tok/s` record). Duplicate expert
    hits exist, but grouping/scatter/register pressure outweighed the saved
    reads at `n_max=3`. Future MoE work should start from a kernel profile or a
    more structural verifier change, not another blind grouped route variant.
    See
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2055-q8-reorder-grouped-negative.md`.
18. **Alternate MTP draft quantization is not a strict-gate win.** Under
    the current VDR2 strict identity (`UD-Q8_K_XL` target/verifier, `n_max=3`,
    `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`), official draft swaps to
    Q4_K_M, Q5_K_M, Q6_K, and Q8_0 all passed the fresh realistic gate but
    stayed below the then-current `98.34046474459183 tok/s` record and far below
    the current `123.67689864739785 tok/s` record. Closest rows were Q8_0 at
    `88.245438 tok/s` and Q5_K_M at `88.109559 tok/s`; Q4_K_M and Q6_K
    were lower. A later Q2_K screen also lost (`85.779-88.903 tok/s`) versus a
    same-window Q4_0 control (`95.282 tok/s`). Keep Q4_0 as the promoted default
    draft unless a future source change materially changes the draft/verifier
    cost tradeoff. See
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2322-strict-draft-quant-negative.md`.
19. **`n_min=1` is not a strict-gate improvement.** Keeping `n_max=3` but
    allowing one-token draft acceptance lost across tested thresholds:
    `p_min=0.035` -> `87.522 tok/s`, `0.0475` -> `88.188 tok/s`, and
    `0.065` -> `88.652 tok/s`. The exact control in the same batch produced a
    strict-valid `91.047632 tok/s` high observation, but an immediate four-lane
    exact repeat fell to `84.943-86.572 tok/s`; do not promote or submit the
    marginal high row. See
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2340-nmin1-negative-control-repeat.md`.
20. **Preserve the current source stack before compact-argmax work.** The
    current llama.cpp Gemma record source tree contains the accumulated VDR2
    selected-down, sampled-ID, Q8 reorder, MTP, and profiling changes that led
    to the `123.67689864739785 tok/s` valid record plus later negative screens.
    Before starting the next source lane (compact LM-head argmax / verifier
    cost reduction), snapshot the full source diff at
    `../../patches/gemma4-26b-a4b-q8-b70/20260629-current-source-stack-before-compact-argmax.patch`
    (`sha256=9db3ac4286e3842ece2eebd07060ac73a0e0c548cb15d17333406701576d52c8`).
    Future source experiments should diff against this snapshot and record both
    wins and losses before promotion.
21. **Fused-down selected-softmax precompute is a closed negative.** A
    default-off patch tried to rescue `LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1`
    by precomputing selected-softmax once per token before selected-down. It
    passed strict128 and full512 cold realistic gates, but full512 candidate
    medians (`114.99472751325114`, `119.55472070939985`) lost to same-build
    controls (`119.83691077465154`, `121.35664372753011`) and the
    `123.67689864739785` record. The active source hunk was reverted; patch
    and results are preserved in
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-down-selected-softmax-precompute-negative.md`.
22. **VDR2 selected-down rowpack=2 is not a short-record win.** A default-off
    source patch packed two output rows per selected-down VDR2 workgroup via
    `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2_ROWPACK=2`. The
    strict128 screen was mildly positive on average, but the full512
    cross-over lost the primary 1-100 token metric: rowpack=2 medians
    `119.75026683034108` and `110.62392954093656` versus same-window controls
    `120.62626200287556` and `117.70674646289913`. It improved full-output /
    wall throughput, so it can remain a service-lane idea, but reject it for
    the current headline record. The active source hunk was reverted; patch and
    results are preserved in
    `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-vdr2-selecteddown-rowpack2-negative.md`.

## Stop Conditions

- If Q8 GGUF cannot fit even at 2K with f16 KV, test Q8_0 before lowering to
  Q6.
- If `GGML_SYCL_DISABLE_OPT=0` fails any canary, stop using it until the
  upstream corruption cause is understood.
- If MTP speed wins but canaries fail at repeat depth, mark it invalid and
  preserve the logs; do not chase speed-only LocalMaxxing submissions.
- If all llama.cpp Q8 paths are valid but slow, switch to vLLM int8-per-channel
  rather than weakening quality.
