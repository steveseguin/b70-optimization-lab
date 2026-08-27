# Gemma 4 26B A4B Q8 on Intel B70

Status: **bookmarked production/research frontier with a realistic final gate
required for any new claim.** Start with
[`HANDOFF.md`](HANDOFF.md) for the current production launcher, resume
checklist, and next-work assessment. Use
[`production-service.md`](production-service.md) for the persistent backend
recipe.

The same fixed cold suite now has a **`122.16035656735696 tok/s`** primary
headline: median within each input class, then median across the six class
medians, using the conventional 99 inter-token intervals. Its secondary
all-prompt median is `123.72736943965285 tok/s`; the historical
`124.97714084813418 tok/s` 100-event value remains a compatibility field, not
the current headline. Evidence:
`data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.
It uses llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
`GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
`UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
`LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
LM-head experiment flags unset,
`cached_tokens=0` on every suite prompt, and
`realistic_final_gate.passed=true` under the historical workload gate; new
external promotion additionally requires the hash-bound quality attestation.

Quantization guardrail: the promoted no-quality-loss lane is the literal
`gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` target/verifier. Older file labels such
as `q8target-q40draft` mean "Q8-quality target plus Q4_0 MTP draft"; they do
**not** mean the target was switched to `gemma-4-26B-A4B-it-Q8_0.gguf`.
Literal `Q8_0.gguf` target runs are controls only unless the user explicitly
accepts that quantization change.

Current repeat / confirmation status: the VDR2 selected-down fused weighted-sum
path is the current policy-compliant LocalMaxxing submission:
`cmr1u77na01k2ld01kalwzs1e`. The current row uses
`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` on the same FA-on 32K/VMM
selected-down baseline/control identity. It measured p10
`103.83610041293263`, mean `122.47435471668817`, median full512 after-TTFT
`114.87107033590866`, median wall full512 `108.58112847853889`, and median
TTFT `178.6938319564797 ms`. Same exact reproduction batch support lanes were
`121.59076340768573`, `119.26425148518223`, and `113.63257982764395`. Treat
this as the current valid high with high variance, and keep repeat
confirmations separate from promotion claims. A same-GPU thermal sweep on
2026-07-01 did not find temperature to be the main driver: exact GPU0 repeats
spanned `114.520-120.202 tok/s` with active core max `77-78 C`, memory max
`86-90 C`, near-max frequency, and no thermal-throttle samples. See
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md).
The prior same-family
`123.67689864739785 tok/s` LocalMaxxing row `cmr01nnet000mld01x2tt6qds`,
the prior `121.41411987308553 tok/s` row `cmqztiqdn02vnoe01egox6q3f`,
the `119.94842631460949 tok/s` confirmation, and
the prior selected-down LocalMaxxing rows
`cmqzq5zu402troe01t774uyox`, `cmqyrpox4021dqk01co5o4fcw`, and
`cmqyo0jyt08ippk01vhiobdnm` are superseded by the current repeat.
The prior LocalMaxxing row `cmqxchyra03xmqr01b963gmi1` at
`98.34046474459183 tok/s`, prior `cmqx3687103v4qr01ace1ft3m` at
`95.82453787677183 tok/s`, earlier VDR2 submissions, and prior VDR4 submission
`cmqwnl2ag03lgqr01ch5bxknq` are superseded.
The earlier `86.47445652599384 tok/s` `p_min=0.075` observation did not repeat.

Current record details and patch links:
[`20260629-vdr2-selected-down-record.md`](20260629-vdr2-selected-down-record.md).
Use the paired A/B reliability protocol for any proposed micro-change near the
current record; single-run medians are too noisy to establish a `+1-4%` win.
See
[`reliability-protocol.md`](reliability-protocol.md)
and the analyzer
[`../../scripts/analyze-gemma-realistic-ab.py`](../../scripts/analyze-gemma-realistic-ab.py).

Recent non-promoted source follow-ups after the final-postnorm record:
attention post-norm residual fusion lost on the short metric, and per-layer
embedding post-norm residual fusion was only a small/inconclusive strict128
hint (`116.812` flag-on average versus `115.809` controls, best flag-on
`119.963`, still below `123.677`). Both flags remain default-off and are not
LocalMaxxing submission candidates for the current short-decode record. An
accept-prefix parity probe then validated the sampled-row invariant for a
future backend verifier LM-head op: `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY=1`
passed the fixed cold gate, `cached_tokens=0`, and 128/128 canary at
`117.604 tok/s`, but it intentionally adds checking work and is diagnostic
only. See the latest sweep notes under
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/).
The subsequent accept-prefix top1-epilogue verifier path is also closed:
`LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE=1` plus
`LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` preserved exact verification and
passed the fixed cold gate, but four-lane A/B candidates averaged only
`105.080 tok/s` versus controls at `116.498 tok/s` (`-9.80%`). Do not reopen
row-by-row accept-prefix variants; future verifier work needs a non-serial
backend row-adaptive design or a genuine candidate-bound certificate. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-acceptprefix-top1-epilogue-negative.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-acceptprefix-top1-epilogue-negative.md).

Latest short-decode profiler refresh:
`gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z` passed the fixed cold
gate (`cached_tokens=0`, `16/16` canary rows), but it is diagnostic only
because `GGML_SYCL_NODE_PROFILE=1` disables SYCL graph execution and the run
used `MAX_TOKENS=128`. Do not submit its speed. The useful result is the
hotspot ordering: target/verifier full-vocab LM-head (`MUL_MAT:node_1715`) is
rank 1, three MTP draft argmax LM-head nodes
(`mtp_direct_argmax_unroll_token_0/1/2`) are each large, and host
bookkeeping/sync remains negligible. Follow-up source audit found the backend
already supports multi-column `MUL_MAT_ARGMAX`, but these draft heads are
autoregressive and cannot be naively batched because each sampled token feeds
the next draft step. Future draft work needs a new single-node `q6_K` argmax
kernel design or a different draft algorithm. The bounded current-record screen
of `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16` on the draft path is closed
no-win: all eight full512 lanes passed with `cached_tokens=0`, but paired
median-ratio CI was `-2.594% / +0.001% / +4.021%` and no candidate beat the
`124.977 tok/s` record. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-recordstack-nodeprofile-hotspots.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-recordstack-nodeprofile-hotspots.md),
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-argmaxtile16-draft-q6k-no-win.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-argmaxtile16-draft-q6k-no-win.md).

Current service/prefill candidate: keep the promoted short-decode reproduction
on `UBATCH_SIZE=1024`, but use the default-off SYCL FlashAttention tile patch
with `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` for long-context service lanes. The
patched Gemma full-attention DV512/GQA8 selector improved the cold near-32K
case (`30400` actual prompt tokens, exact JSON validation, `cached_tokens=0`)
from `702.605` to `947.589` mean prefill tok/s in a GPU crossover, with
identical output hashes. A broader three-case service gate passed at `16213`,
`22730`, and `30400` actual prompt tokens; median prefill was `1039.603 tok/s`
for UB2048, `1075.983` for UB2304, and `1066.029` for UB2560. UB2048 remains
the balanced service default; UB2304 is the best pure-prefill setting seen so
far. Fixed cold short-suite guards passed with `cached_tokens=0`, but did not
beat the `123.67689864739785` short record, so no LocalMaxxing submission was
made. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md).
Follow-up KV-max mask pre-scan testing showed the existing scan should stay
enabled: disabling it with `GGML_SYCL_FATTN_KV_MAX_SCAN_MIN_Q=-1` passed exact
validation but regressed the `30400` actual-token prefill from `955.2365` to
`862.9161 tok/s`. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md).
Follow-up `ncols1` forcing inside the GQA8 tile path is also closed negative:
the current implicit `ncols1=2` path measured `953.0630` and `950.5813`
prefill tok/s on paired controls, while forced `ncols1=1` fell to `821.6392`
and forced `ncols1=4` fell to `856.8965`. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.md).
The follow-up compile-time retune of the winning GQA8 FP16 tile from
`nbatch_fa=64` to `128` is also closed negative/noise: four valid cold lanes
averaged `951.5273 tok/s` prefill (`953.3767`, `944.6846`, `955.1166`,
`952.9311`), which is indistinguishable from the same-case controls
(`950.5813-955.2365`). Keep the existing
`GGML_SYCL_FATTN_TILE_CONFIG_CASE(576, 512, 16, 256, 2, 64, 64)` setting.
Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md).
A phase-specific prompt/decode ubatch source patch was then screened. The v1
context-only patch is closed negative: `BATCH_SIZE=2048`,
`UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048` passed validation but hit
KV retry churn and fell to `880.2510 tok/s` prefill. The v2 patch also sizes
SWA/ISWA memory by `max(n_ubatch, n_ubatch_prefill)`, removing retries. It is
valid and useful as a service-lane candidate (`2048/1024 + prefill2048`:
`956.7217 tok/s` prefill, `112.9063 tok/s` long-context decode, short guard
`120.8849 tok/s`), but it does not beat the current `124.97714084813418`
short-decode record and is not a LocalMaxxing submission. `prefill2304` and
`prefill2560` were valid but not better balanced in the paired screen. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md).
The next SYCL FlashAttention idea, mask-derived `KV_min` left-bound skipping,
is only a preserved partial result: it improved validated long-context prefill
by about `+4.7%` to `+6.1%`, but the fixed short-decode guard showed a
`~1-2%` regression risk. The patch was archived and the active source reverted;
do not enable it in promoted service or LocalMaxxing headline recipes. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-sycl-fattn-kv-min-left-bound-partial.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-sycl-fattn-kv-min-left-bound-partial.md).

Post-cleanup service confirmation on 2026-07-02 revalidated the promoted
host-derived SWA left-bound service recipe in the single active workspace:
`BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`,
`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
`LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`, and
`LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`. The long-context A/B plus
cross-over passed exact JSON validation and `cached_tokens=0`, improving median
prefill by **+6.927%** while long-context decode was flat/slightly positive.
The paired full512 short-decode guard also passed and showed no regression
signal (`+0.223%` on the 1-100 metric, within normal MTP variance). Treat this
as the current validated service/prefill recipe, not a LocalMaxxing short-decode
headline. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-postclean-baseline-swalb-service-confirm.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-postclean-baseline-swalb-service-confirm.md).

The latest structural global-FlashAttention service micro-win is the
default-off KQ register/broadcast path:
`GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`. It was first validated on the
`DKQ=512`, `DV=512` tile path, then extended to the profiled `DKQ=576`,
`DV=512`, `ncols=16` global GQA shape. The DKQ576 extension passed a balanced
four-wave long-context A/B + crossover with exact JSON validation and
`cached_tokens=0` on all 48 rows, improving approximate prefill by `+0.722%`
mean / `+0.813%` median and TTFT by `-0.765%`, positive by GPU and by case.
The candidate short-decode smoke guard also passed four lanes at
`MAX_TOKENS=256`, `CANARY_REPEATS=8`, `cached_tokens=0`. A full512 short-decode
follow-up later passed all gates but did not promote the flag for the short
headline: controls `117.584/124.161/115.228/116.737`, candidates
`116.760/117.590/124.444/115.657`, paired median-ratio CI
`-2.666% / -0.040% / +3.119%`, decision `no_win`. This remains
service/prefill only, not a LocalMaxxing headline decode result.
Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-kq-reg-bcast-dkq576-service-win.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-kq-reg-bcast-dkq576-service-win.md).

The bounded follow-up one-pass scheduler gate for that same profiled global
GQA8 service shape is closed no-win. The default-off source flag
`GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1` forced `parallel_blocks=1` only for
the hot global shape, excluding SWA/decode paths. It passed a one-case exact
JSON smoke and a four-wave service A/B + crossover on top of the KQ
register/broadcast service stack with all 48 rows exact-valid and
`cached_tokens=0`, but moved prefill only `+0.102%` mean / `+0.260%` median.
The patch was reverted and the active binary rebuilt to the baseline
`libggml-sycl.so.0.15.2` hash
`61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`. Do not
carry this flag or retest broad `PARALLEL_BLOCKS=1` as-is. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-hotglobalpb1-service-no-win.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-hotglobalpb1-service-no-win.md).

Current service-context ladder baseline: the validated service stack
(`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`, SWA left-bound min-Q `2048`, KQ
register/broadcast, phase prefill ubatch `2048`, `BATCH_SIZE=2048`,
`UBATCH_SIZE=1024`, `CTX_SIZE=32768`, FA/VMM on) passed the full cold
long-context suite across all four B70s, from 512 through 24K target prompt
tokens. All 32 long-context rows were exact-valid with `cached_tokens=0`, and
all 64 canary rows passed. Average lane median prefill was `1192.965 tok/s`;
average lane median long-context decode was `131.786 tok/s`. At the longest
`32571` actual-token case, prefill stayed about `991-1006 tok/s` and decode
about `114-115 tok/s`. This is a service/prompt-processing reference only, not
a short-decode LocalMaxxing headline. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-current-service-context-ladder.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-current-service-context-ladder.md).

Follow-up no-KQ-local-memory elision for the same KQ register/broadcast path is
closed negative/noise. The candidate added
`GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_NO_KQ_LSM=1`, built successfully, and
passed a 48-row exact long-context A/B + crossover with `cached_tokens=0`, but
measured only `-0.034%` mean / `+0.067%` median prefill delta with mixed
wave/GPU behavior. It was reverted and should not be promoted. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-no-kq-lsm-negative.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-no-kq-lsm-negative.md).

Follow-up pre-softmax barrier skipping for the same KQ register/broadcast path
is also closed negative/noise. The candidate added
`GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_SKIP_PRESOFTMAX_BARRIER=1`, built
successfully, and passed a 48-row exact long-context A/B + crossover with
`cached_tokens=0`, but measured only `+0.031%` mean / `+0.169%` median prefill
delta with alternating negative/positive waves. It was reverted and should not
be promoted. Evidence:
[`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-skipbarrier-negative.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-skipbarrier-negative.md).

The earlier UBATCH-only service work remains useful background: UB2048 was the
best unpatched long-prefill candidate, and the profile that followed correctly
pointed at `FLASH_ATTN_EXT` / KV-cache attention rather than verifier LM-head
or MoE selected-down kernels. Do not reopen generic UBATCH roulette without new
profile evidence.

The valid no-spec control is `74.29709476830473 tok/s` median:
`data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`.
Use it as the clean target-side baseline for new work; draft-MTP now has a
clear median advantage on the fixed suite, while the no-spec row still provides
the simplest quality/control reference.

The previous diagnostic synthetic filled-long result was llama.cpp draft-MTP
`n=7`, UD-Q8_K_XL target/verifier with Q4_0 MTP draft only, the prior
route-cache/fused-output/fused-selected-softmax/RMS-reuse stack plus
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
`LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`, `UBATCH_SIZE=720`, `MTP_N_MIN=3`,
`MTP_P_MIN=0.10`, and reordered Q8_0 MMVQ compile knob
`GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2` on GPU0 at `176.21623213048554 tok/s`
after TTFT on synthetic row0 / `176.40259133127742` support mean. Under the
2026-06-27 policy this is **diagnostic only** and must not be promoted or
submitted as real-world throughput. The same applies to earlier `100+` and
`170+` rows whose original labels said `fresh`: without the fixed cold suite,
they are pre-final-gate diagnostics only.

The older `92.397 tok/s` result from `2026-06-23T222838Z` was also
`UD-Q8_K_XL`, not `Q8_0`; it used the pre-final-gate filled-long diagnostic
shape and is therefore not directly comparable to the current fixed
realistic-suite `124.977 tok/s` record.

The 2026-07-02 repro documentation pass reran the current 125 wrapper exactly
(`CTX_SIZE=32768`, FA on, VMM on, Q4_0 draft verified by Q8 target) and passed
the strict gate at `120.92334534956485 tok/s`, with `cached_tokens=0` on all
12 prompts and `512/512` canary rows. This is valid support for the recipe, not
a new high. Evidence:
`../../data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`.

Current copy-ready reproduction recipe:
[`../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/`](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md).

Prior superseded reproduction recipe:
[`../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/`](../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md).
Use that folder for the older 95 tok/s Gemma 26B settings. The current
176.216 tok/s diagnostic result is documented in this result ledger, the active
Gemma sweep notes, and the LocalMaxxing submission ledger as diagnostic only.

Draftless `ngram-mod` later reached `245-280 tok/s`, but only after repeated
benchmark requests made the same continuation predictable from generated
history. Those rows are useful warmed/history-accelerated artifacts, not valid
fresh-response headline throughput. The submitted ngram LocalMaxxing rows are
marked retraction-needed in this repo; API deletion was attempted on 2026-06-23
and returned 404 because LocalMaxxing exposes no benchmark delete endpoint.

This lane replaces the closed Qwen3.6 35B TP4 effort. The target architecture is
different on purpose: run **one complete Gemma 4 26B A4B replica per B70** and
avoid tensor-parallel PCIe overhead. The host has four B70s, so the research
workflow should normally run four independent single-GPU attempts in parallel.

## Target

- Model family: Gemma 4 26B A4B instruction tuned.
- Primary quality target: no lower than INT8-equivalent weights. Do **not** use
  INT4 AutoRound as the default lane.
- Primary runtime target: single-session decode rate on short/small-context
  prompts first, then 32K-context viability after the Q8 fit is proven.
- Preferred first artifact:
  `unsloth/gemma-4-26B-A4B-it-GGUF`,
  `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` (27.6 GB).
- First runtime lane: llama.cpp SYCL/Level Zero, one process per GPU.
- Secondary runtime lane: vLLM/XPU with `google/gemma-4-26B-A4B-it` and
  `--quantization int8_per_channel_weight_only`, one process per GPU.
- Nice-to-have after text baseline: image input / multimodal smoke.

## Why This Shape

The model is MoE with about 25.2B total parameters and about 3.8B active
parameters, so a full Q8 GGUF copy should fit on a 32 GB B70 with limited KV
headroom. Running four replicas avoids the Qwen-style TP4 PCIe/collective cost
and lets four experiments run at once.

This is also the capacity boundary that makes Gemma 26B a good B70 target: it
barely fits with Q8-quality weights and leaves enough room for useful decode
work. Larger open-weight models will need either heavier compromises or
higher-VRAM Intel hardware before this same no-quality-loss workflow can be
applied cleanly. Crescent Island-class `160-480 GB` XPU devices would be the
right kind of lab target for those next lanes.

External references:

- Unsloth GGUF repo and Q8 file list:
  <https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/tree/main>
- Unsloth model card and llama.cpp / vLLM / Ollama entry points:
  <https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF>
- vLLM Gemma 4 recipe, including 26B A4B single-GPU and int8-per-channel notes:
  <https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html>
- vLLM Gemma 4 MoE DP issue recommending separate DP=1 instances:
  <https://github.com/vllm-project/vllm/issues/38999>
- LocalMaxxing Gemma 4 26B A4B leaderboard:
  <https://www.localmaxxing.com/en/models/google/gemma-4-26B-A4B-it>
  (useful for targets, but current top public rows include lower-precision
  modes such as MXFP4/Q4 and are not direct Q8-quality comparisons).

## Current Local State

- Four B70s are visible as Level Zero devices `level_zero:0..3`.
- llama.cpp upstream was cloned to `/home/steve/src/llama.cpp` and built with
  SYCL/Level Zero at commit `dec5ca557`; server binaries are under
  `/home/steve/src/llama.cpp/build-sycl-b70/bin/`.
- A separate latest-runtime worktree is available at
  `/home/steve/src/llama.cpp-latest-gemma`, built at `c926ad098` with AOT BMG
  output under
  `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31/bin/`.
  Use `--ctx-checkpoints 0` for record attempts on this runtime; the upstream
  default checkpointing hurts this benchmark's TTFT.
- The current local Gemma record source worktree snapshot is preserved as
  [`../../patches/gemma4-26b-a4b-q8-b70/20260629-current-llamacpp-gemma-record-worktree.md`](../../patches/gemma4-26b-a4b-q8-b70/20260629-current-llamacpp-gemma-record-worktree.md)
  plus the adjacent `.patch`. This cumulative patch is the recovery artifact
  for `/home/steve/src/llama.cpp-gemma-record-repro-c926` at upstream
  `c926ad098`; it includes promoted code paths and default-off failed
  experiments, so consult the per-experiment notes before enabling flags.
- There is enough disk for the Q8 GGUF; `/mnt/fast-ai` had about 353 GB free at
  lane start.
- The Q8 GGUF is downloaded and byte-verified at
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
  (`27,636,230,944` bytes). Metadata sidecar:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf.metadata.json`.
- Alternate Q8_0 GGUF is also downloaded for later comparison at
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-Q8_0.gguf`
  (`26,859,859,744` bytes). Do not promote it until it beats the Q8_K_XL
  frontier under the same canary and filled-long benchmark shape.
- The local editable `/home/steve/src/vllm` tree was used only for a controlled
  official-HF Gemma comparison after recording vLLM version/source identity.
  It is not competitive with llama.cpp Q8 today; see the vLLM row below.

## First Milestones

1. Build upstream llama.cpp with SYCL/Level Zero.
2. Download the Q8 GGUF to
   `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/`.
3. Launch one `llama-server` replica on a single B70 at `CTX_SIZE=8192` and
   establish a valid text-only baseline before attempting 32K.
4. Launch four replicas on ports `18260..18263` and run four independent
   experiments/benchmarks in parallel.
5. Compare against a vLLM/XPU int8-per-channel single-GPU baseline only after
   llama.cpp has a stable text baseline.

## Result Table

| Date | Runtime | GPU Layout | Precision | Context | Status | Output tok/s | Evidence |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| 2026-07-01 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path + bulk sampled-ID verifier host read + VDR2 selected-down fused weighted-sum + final post-norm residual fusion + FA-on 32K/VMM | 1 replica on B70 GPU0; exact full512 reproduction batch across four GPUs | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 32K | **current strict realistic-suite record**: exact promoted recipe rerun after LM-head subgroup experiment, fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, LM-head subgroup unset, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`, target-verifier accepted MTP tokens; LocalMaxxing `cmr1u77na01k2ld01kalwzs1e`; valid but high variance, with same-batch support `121.591`, `119.264`, `113.633` | **124.977 median 1-100 after TTFT** / 114.871 full512 after TTFT / 108.581 wall full512 | [summary](../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-finalpostnorm-faon-vmm-ctx32768-full512-124tok-20260701.submit.log), [reproduction note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-reproduction-check.md) |
| 2026-06-30 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path + bulk sampled-ID verifier host read + VDR2 selected-down fused weighted-sum + final post-norm residual fusion + FA-on 32K/VMM | 1 replica on B70 GPU0; paired full512 finalpost/control A/B across four GPUs | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 32K | prior strict realistic-suite record, superseded by the 2026-07-01 exact reproduction: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`, target-verifier accepted MTP tokens; LocalMaxxing `cmr01nnet000mld01x2tt6qds`; valid but high variance, with second finalpost `116.551` and controls `117.873` / `114.709` | **123.677 median 1-100 after TTFT** / 110.683 full512 after TTFT / 106.441 wall full512 | [summary](../../data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-finalpostnorm-faon-vmm-ctx32768-full512-123tok-20260630.submit.log), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-final-postnorm-fusion-screen.md) |
| 2026-06-29 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path + bulk sampled-ID verifier host read + VDR2 selected-down fused weighted-sum + FA-on 32K/VMM | 1 replica on B70 GPU3; same-family four-GPU baseline confirmation batch | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 32K | prior strict realistic-suite record, superseded by final post-norm fusion: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, target-verifier accepted MTP tokens; LM-head experiment flags unset; LocalMaxxing `cmqztiqdn02vnoe01egox6q3f`; supporting same-family confirmation high `119.948` plus lower variance rows `113.572`, `114.088`, `111.988` | **121.414 median 1-100 after TTFT** / 110.391 full512 after TTFT / 105.881 wall full512 | [summary](../../data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-faon-vmm-ctx32768-full512-121tok-20260629.submit.log), [record note](20260629-vdr2-selected-down-record.md) |
| 2026-06-29 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path + bulk sampled-ID verifier host read + VDR2 selected-down fused weighted-sum + FA-on 32K/VMM | 1 replica on B70 GPU3; same-identity four-GPU confirmation batch | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 32K | prior strict realistic-suite record, superseded by the later same-family `121.414` baseline row: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, target-verifier accepted MTP tokens; LocalMaxxing `cmqzq5zu402troe01t774uyox`; confirmations measured `116.458`, `117.415`, `115.089`, `117.457` | **117.915 median 1-100 after TTFT** / 110.958 full512 after TTFT / 106.807 wall full512 | [summary](../../data/gemma4-q8-gpu3-faon-vmm-ctx32768-full512-20260629T211437Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-faon-vmm-ctx32768-full512-20260629.submit.log), [record note](20260629-vdr2-selected-down-record.md) |
| 2026-06-29 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path + bulk sampled-ID verifier host read + VDR2 selected-down fused weighted-sum | 1 replica on B70 GPU1; same-recipe repeat beside BF16-direct retest controls | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | prior strict realistic-suite record, superseded by the FA-on 32K/VMM row: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, target-verifier accepted MTP tokens; LocalMaxxing `cmqyrpox4021dqk01co5o4fcw`; BF16-direct lanes did not beat controls | **115.847 median 1-100 after TTFT** / 104.661 full512 after TTFT / 100.640 wall full512 | [summary](../../data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-repeat-20260629.submit.log), [record note](20260629-vdr2-selected-down-record.md) |
| 2026-06-29 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path + bulk sampled-ID verifier host read + VDR2 selected-down fused weighted-sum | 1 replica on B70 GPU1; four parallel one-B70 confirmations | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | initial selected-down strict realistic-suite record, superseded by the same-recipe `115.847` repeat: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, target-verifier accepted MTP tokens; LocalMaxxing `cmqyo0jyt08ippk01vhiobdnm`; full512 confirmation lanes measured `113.471`, `115.728`, `113.815`, `114.811` | **115.728 median 1-100 after TTFT** / 104.602 full512 after TTFT / 100.228 wall full512 | [summary](../../data/gemma4-q8-gpu1-vdr2-selecteddown-reordervdr2-full512-20260629B/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-20260629.submit.log), [record note](20260629-vdr2-selected-down-record.md) |
| 2026-06-28 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path + bulk sampled-ID verifier host read | 1 replica on B70 GPU1; four parallel one-B70 confirmations | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | prior strict realistic-suite record, superseded by the VDR2 selected-down row: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, target-verifier accepted MTP tokens; LocalMaxxing `cmqxchyra03xmqr01b963gmi1`; full512 confirmation lanes measured `96.015`, `98.340`, `95.903`, `94.941` | **98.340 median 1-100 after TTFT** / 91.174 full512 after TTFT / 87.737 wall full512 | [summary](../../data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-bulksampled-full512-20260628.submit.log), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md) |
| 2026-06-28 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + F16 p021 small-ncols path | 1 replica on B70 GPU1; four parallel one-B70 confirmations | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | prior strict realistic-suite record, superseded by the bulk sampled-ID row: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, target-verifier accepted MTP tokens; LocalMaxxing `cmqx3687103v4qr01ace1ft3m`; full512 confirmation lanes measured `95.817`, `95.825`, `93.422`, `95.566` | **95.825 median 1-100 after TTFT** / 91.142 full512 after TTFT / 88.262 wall full512 | [summary](../../data/gemma4-q8-gpu1-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-smallncols-full512-20260628.submit.log), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0047-strict-f16p021-smallncols-record.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | prior strict realistic-suite record, superseded by the 2026-06-28 F16 p021 small-ncols row: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, target-verifier accepted MTP tokens; LocalMaxxing `cmqwxep4a03qiqr010chjn93s`; submitted from a conservative four-repeat confirmation batch, with a same-identity `91.393 tok/s` high observation kept as support rather than headline | **90.983 median 1-100 after TTFT** / 85.919 full512 after TTFT / 82.897 wall full512 | [summary](../../data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-recordconfirm-20260627T221722.submit.log), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2213-vdr2-recordconfirm-and-n4-negative.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 | 4 parallel one-B70 replicas | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | **valid strict acceptance-shape loss**: `n_min=1` variants were tested because they could have accepted useful verified one-token drafts; all passed the fixed cold gate but lost. Exact control in the batch produced a marginal valid high observation (`91.048`), but an immediate exact-repeat batch fell to `84.943-86.572`, so it is not promoted. | `n_min=1` best **88.652 median 1-100**; control high **91.048**, not confirmed | [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2340-nmin1-negative-control-repeat.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 | 4 parallel one-B70 replicas | UD-Q8_K_XL GGUF target + alternate official MTP draft quants, f16 KV | 8K | **valid strict draft-quant losses**: Q4_K_M, Q5_K_M, Q6_K, and Q8_0 draft swaps all preserved strict validity but stayed below the Q4_0-draft record. Keep Q4_0 as the default draft unless a future source change changes the cost tradeoff. | best alternate draft **88.245 median 1-100** (Q8_0 draft) | [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2322-strict-draft-quant-negative.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | prior strict realistic-suite record, superseded by the row above: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, target-verifier accepted MTP tokens; LocalMaxxing `cmqwt1zk803ozqr01hctqss2z` | **90.322 median 1-100 after TTFT** / 86.217 full512 after TTFT / 83.212 wall full512 | [summary](../../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v21-20260627.submit.log), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2017-vdr2-pmin-tight-repeat.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 | 1 replica on B70 | Q8_0 GGUF target controls, mostly Q4_0 MTP draft, f16 KV | 8K | **valid strict control, not promoted**: literal `gemma-4-26B-A4B-it-Q8_0.gguf` target tested because it is smaller and has fast Q8_0 kernels. Best screen `91.556` did not confirm (`88.949`, `89.892` exact repeats); best deeper row `90.277` stayed below the `UD-Q8_K_XL` record. Do not submit under the no-quality-loss lane. | **90.277 best repeated/depth control** / 91.556 unconfirmed high repeat | [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2144-q80-target-strict-negative.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 + grouped reordered-Q8 MoE experiment | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | **valid strict realistic-suite loss**: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse; source flag `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER=1`; duplicate-expert grouping lost to branch/scatter/register overhead; do not submit | **83.908 median 1-100 after TTFT** / 82.008 full512 after TTFT / 79.093 wall full512 | [summary](../../data/gemma4-q8-gpu0-strict-vdr2-grouped-reorder-n3-p00475-ub1024-screen-20260627T205542Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2055-q8-reorder-grouped-negative.md), [patch note](../../patches/gemma4-26b-a4b-q8-b70/20260627T2055-q8-reorder-grouped-multitoken-negative.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + Q8 MoE-ID reorder VDR2 | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | prior strict realistic-suite record, superseded by the row above: fixed realistic cold suite, each prompt once, `cached_tokens=0` every row, no cache/history/ngram reuse, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, target-verifier accepted MTP tokens; LocalMaxxing `cmqwqzayr03o8qr01j6lgx93n` | **89.455 median 1-100 after TTFT** / 84.452 full512 after TTFT / 80.625 wall full512 | [summary](../../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-ub1024-v19-20260627T191931Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627.submit.log), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1906-realistic-static-and-vdr2.md) |
| 2026-06-23 | llama.cpp SYCL setup | 1 replica / B70 | UD-Q8_K_XL GGUF | 8K first, 32K target | model download | n/a | [lane start note](../../notes/2026-06-23-gemma4-26b-a4b-q8-b70-lane-start.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF, f16 KV | 8K | **valid baseline**: chat canary 128/128; reasoning off | **26.10 after TTFT** / 24.24 wall | [summary](../../data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T052850Z-valid-baseline-reasoning-off.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF, f16 KV | 8K | **current natural-stop best**: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `--parallel 1 --cache-ram 0`, chat canary 384/384; reasoning off | **42.15 after TTFT** / 36.41 wall | [summary](../../data/gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0900-parallel-cache-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF, f16 KV | 8K | sustained-decode best before MTP: same config, `BENCH_PROMPT_MODE=long`, 384/384 canary; actual shape is about 75 input / 512 output tokens | **42.72 after TTFT** / 41.35 wall | [summary](../../data/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0930-long-output-benchmark.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | MTP `n=4`: `--spec-type draft-mtp --spec-draft-n-max 4`, 384/384 canary; actual shape 75 input / 512 output tokens | **44.50 after TTFT** / 43.03 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1125-mtp-draft-smoke-and-deep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | MTP `n=3`: `--spec-type draft-mtp --spec-draft-n-max 3`, 384/384 canary; actual shape 75 input / 512 output tokens | **46.36 after TTFT** / 44.75 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n3-long-deep-20260623T0328/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0328-mtp-near-optimum-deep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | repeated MTP `n=3`, 384/384 canary; actual shape 75 input / 512 output tokens | **47.63 after TTFT** / 45.93 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n3-repeat-long-deep-20260623T0337/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0337-mtp-n3-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | AOT `bmg-g31`, MTP `n=3`, 384/384 canary; actual shape 75 input / 512 output tokens | **47.92 after TTFT** / 46.18 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n3-aot-bmg-long-deep-20260623T0345/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0345-mtp-n3-aot-and-runtime.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | repeated AOT `bmg-g31`, MTP `n=3`, 384/384 canary; actual shape 75 input / 512 output tokens | **48.35 after TTFT** / 46.60 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0353-mtp-aot-n-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=3`, 384/384 canary; actual shape 588 input / 512 output tokens | **68.19 after TTFT** / 63.43 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n3-aot-filled-long-deep-20260623T085322Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0853-filled-long-mtp-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=3` + `--spec-draft-p-split 0.20`, 384/384 canary; actual shape 588 input / 512 output tokens | **68.51 after TTFT** / 63.67 wall | [summary](../../data/gemma4-q8-gpu2-mtp-n3-aot-psplit020-filled-long-deep-20260623T085844Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0853-filled-long-mtp-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=4`, 384/384 canary; actual shape 588 input / 512 output tokens | **74.39 after TTFT** / 68.80 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n4-aot-filled-long-deep-20260623T085822Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0853-filled-long-mtp-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=4` + `--spec-draft-p-split 0.20`, 384/384 canary; actual shape 588 input / 512 output tokens | **74.50 after TTFT** / 68.90 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n4-aot-psplit020-filled-long-deep-20260623T090712Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0907-filled-long-n4-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=5`, 384/384 canary; actual shape 588 input / 512 output tokens | **78.64 after TTFT** / 72.25 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n5-aot-filled-long-deep-20260623T091227Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0912-filled-long-deeper-n-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=6`, `n-min=2`, `p-min=0.15`, 384/384 canary; actual shape 588 input / 512 output tokens | **83.52 after TTFT** / 76.57 wall | [summary](../../data/gemma4-q8-gpu2-mtp-n6-aot-nmin2-pmin015-filled-long-deep-20260623T091227Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0912-filled-long-deeper-n-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.15`, 384/384 canary; actual shape 588 input / 512 output tokens | **87.88 after TTFT** / 80.25 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin015-filled-long-deep-20260623T091939Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0919-filled-long-n7-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.10`, 384/384 canary; actual shape 588 input / 512 output tokens | **88.35 after TTFT** / 80.55 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-filled-long-deep-20260623T092524Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0925-n7-pmin-and-psplit-sweeps.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.10`, `--no-spec-draft-backend-sampling`, 384/384 canary; actual shape 588 input / 512 output tokens | **90.24 after TTFT** / 82.24 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-filled-long-deep-20260623T093619Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0936-n7-backend-sampling-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.10`, `--no-spec-draft-backend-sampling`, `--spec-draft-threads 32`, 384/384 canary; actual shape 588 input / 512 output tokens | **90.42 after TTFT** / 82.34 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-20260623T094131Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0941-n7-nobs-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.12`, `--no-spec-draft-backend-sampling`, `--spec-draft-threads 32`, `--spec-draft-threads-batch 32`, 384/384 canary; actual shape 588 input / 512 output tokens | **91.05 after TTFT** / 82.97 wall | [summary](../../data/gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1018-dtb32-pmin-interaction.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous pre-final-gate filled-long diagnostic best: latest runtime, MTP `n=7`, `n-min=2`, `p-min=0.12`, `--no-spec-draft-backend-sampling`, `--spec-draft-threads 32`, `--spec-draft-threads-batch 32`, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens | **91.16 after TTFT** / 71.06 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1130-latest-runtime-c926ad098.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + fast top-k patch | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | prior pre-final-gate filled-long diagnostic best: prior `n=7/n-min=2/p-min=0.12` recipe plus `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`, backend sampling off, 384/384 canary; actual shape 588 input / 512 output tokens, first request `91.25 tok/s`, `cached_tokens=0` | **91.62 after TTFT** / 71.29 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1504-fast-topk.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + CPU cleanup | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | CPU hot-path cleanup on top of fast-top-k stack, `n=7/n-min=2/p-min=0.12`, backend sampling off, 384/384 canary; actual shape 588 input / 512 output tokens, first request `91.88 tok/s`, `cached_tokens=0` | **91.90 after TTFT** / 71.49 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-cpucleanup-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T221705Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T2217-mtp-cpu-cleanup.md) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + fast argmax + CPU cleanup + VMM/ubatch/poll | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, `n=7/n-min=2/p-min=0.12`, backend sampling off, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens, first measured row `94.366 tok/s`, repeated-request mean `92.559`, `cached_tokens=0` | **94.366 first synthetic** / 92.559 supporting mean / 80.51 first-row wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-full-fresh-20260624T032733Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T0235-mtp-fused-unroll-feasibility.md) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + fast argmax + CPU cleanup + VMM/ubatch/poll | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: target/verifier remains Q8; only the draft is Q4_0. `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, `n=7/n-min=2/p-min=0.12`, backend sampling off, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens, first measured row `95.264 tok/s`, repeated-request mean `95.386`, `cached_tokens=0` | **95.264 first synthetic** / 95.386 supporting mean / 81.29 first-row wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-draftq40-full-20260624T081218Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T0235-mtp-fused-unroll-feasibility.md) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + direct-unroll7 q-only assistant inputs | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: target/verifier remains Q8; only the draft is Q4_0. Adds `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`, `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`, and `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1` to the prior n7 fast-argmax recipe. `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, backend sampling off, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens, first measured row `96.822 tok/s`, repeated rows are support only, `cached_tokens=0` | **96.822 first synthetic** / 97.226 supporting mean / 82.46 first-row wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-full-20260624T1432Z/summary.json), [QAT/Q8 side-lane note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T1045-qat-side-lane.md) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights + RMS reuse + Q8 MoE-ID reorder + VDR=2 | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | **diagnostic synthetic filled-long best, pending realistic gate**: prior route-cache/fused-output/fused-selected-softmax/RMS-reuse recipe plus `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`, `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`, and reordered Q8_0 MMVQ compile knob `GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2`. Direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, selected-softmax and weighted-sum Gemma4 MoE source guards, `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=720`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled, backend sampling off, `--ctx-checkpoints 0`, 1536 repeats / 6144 canary rows passed; actual shape 588 input / 512 output tokens, first measured synthetic row `176.216 tok/s`, repeated rows are support only, `cached_tokens=0` | **176.216 diagnostic row0** / 176.403 support mean / 139.32 row0 wall | [summary](../../data/gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1553-q8-reorder-vdr2-record.md), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627.submit.log) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights + RMS reuse + Q8 MoE-ID reorder | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: same Q8 MoE-ID reorder recipe as current, but default reordered Q8_0 MMVQ VDR=4. `UBATCH_SIZE=720`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`, 1536 repeats / 6144 canary rows passed; actual shape 588 input / 512 output tokens, first measured row `171.108 tok/s`, repeated rows are support only, `cached_tokens=0` | **171.108 first synthetic** / 170.129 supporting mean / 135.67 first-row wall | [queue](../../data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub720-nmin3-pmin010-fresh-20260627.queue.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub720-nmin3-pmin010-fresh-20260627.submit.log) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights + RMS reuse + Q8 MoE-ID reorder | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: same Q8 MoE-ID reorder recipe with `UBATCH_SIZE=704`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`; 1536 repeats / 6144 canary rows passed; actual shape 588 input / 512 output tokens, first measured row `170.112 tok/s`, repeated rows are support only, `cached_tokens=0` | **170.112 first synthetic** / 169.876 supporting mean / 134.90 first-row wall | [queue](../../data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub704-nmin3-pmin010-fresh-20260627.queue.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub704-nmin3-pmin010-fresh-20260627.submit.log) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights + RMS reuse + Q8 MoE-ID reorder | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: same Q8 MoE-ID reorder recipe with `UBATCH_SIZE=768`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`; 1536 repeats / 6144 canary rows passed; actual shape 588 input / 512 output tokens, first measured row `169.949 tok/s`, repeated rows are support only, `cached_tokens=0` | **169.949 first synthetic** / 169.550 supporting mean / 135.18 first-row wall | [queue](../../data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub768-nmin3-pmin010-fresh-20260627.queue.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub768-nmin3-pmin010-fresh-20260627.submit.log) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights + RMS reuse | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best, tiny row0 micro-record: same route-cache/fused-output recipe as the previous row, with `UBATCH_SIZE=768`, `MTP_N_MIN=3`, and `MTP_P_MIN=0.10`, plus `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`. Direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536 repeats / 6144 canary rows passed; actual shape 588 input / 512 output tokens, first measured row `104.309 tok/s`, repeated rows are support only, `cached_tokens=0`; support mean was lower (`103.934`) due to one slower support row, so the gain is row0-only | **104.309 first synthetic** / 103.934 supporting mean / 90.85 first-row wall | [summary](../../data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-rmsreuse-ub768-nmin3-pmin010-fresh-20260627.submit.log) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best, variance-class micro-record: same route-cache/fused-output recipe as the previous row, with `UBATCH_SIZE=768`, `MTP_N_MIN=3`, and `MTP_P_MIN=0.10`. Direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536 repeats / 6144 canary rows passed; actual shape 588 input / 512 output tokens, first measured row `104.226 tok/s`, repeated rows are support only, `cached_tokens=0`; support mean also improved to `104.174`, but the gain remains small | **104.226 first synthetic** / 104.174 supporting mean / 90.74 first-row wall | [summary](../../data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-nmin3-pmin010-fresh-20260627.submit.log) |
| 2026-06-27 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: same route-cache/fused-output recipe as the previous row, with runtime shape changed to `UBATCH_SIZE=768`. Direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, `MTP_P_MIN=0.136`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=768`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536 repeats / 6144 canary rows passed; actual shape 588 input / 512 output tokens, first measured row `104.071 tok/s`, repeated rows are support only, `cached_tokens=0`; support mean is lower than the previous record | **104.071 first synthetic** / 103.589 supporting mean / 90.49 first-row wall | [summary](../../data/gemma4-q8-gpu3-b1024u768-fullrepeat-20260626T235649Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-fresh-20260627.submit.log) |
| 2026-06-26 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best, variance-class micro-record: exact same route-cache/fused-output recipe as the previous row, repeated on GPU0. Direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, `MTP_P_MIN=0.136`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536/1536 canary; actual shape 588 input / 512 output tokens, first measured row `103.983 tok/s`, repeated rows are support only, `cached_tokens=0`; same mechanism as `103.954` | **103.983 first synthetic** / 104.096 supporting mean / 90.48 first-row wall | [summary](../../data/gemma4-q8-gpu0-currentrecord-control-fullrepeat-20260626T230510Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-repeat-fresh-20260626.submit.log) |
| 2026-06-26 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + route cache + fused assistant output argmax + fused selected-softmax weights | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded same-stack micro-record: same route-cache recipe as the previous row plus `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` and `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`. Direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, `MTP_P_MIN=0.136`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536/1536 canary; actual shape 588 input / 512 output tokens, first measured row `103.954 tok/s`, repeated rows are support only, `cached_tokens=0`; small improvement over prior route-cache row | **103.954 first synthetic** / 104.135 supporting mean / 90.69 first-row wall | [summary](../../data/gemma4-q8-gpu2-routecache-mtpfusedoutargmax-selfusedweights-full-20260626T222525Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-fresh-20260626.submit.log) |
| 2026-06-26 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + selected-softmax + weighted-sum MoE guards + one-shot `MUL_MAT_ID` route cache | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded route-cache micro-record: same route-cache recipe as the previous row, validated after a four-GPU CTX screen. Direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, `MTP_P_MIN=0.136`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536/1536 canary; actual shape 588 input / 512 output tokens, first measured row `103.515 tok/s`, repeated rows are support only, `cached_tokens=0`; small improvement over prior route-cache row | **103.515 first synthetic** / 103.193 supporting mean / 90.22 first-row wall | [summary](../../data/gemma4-q8-gpu2-routecache-ctx8192-full-20260626T191746Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-ctx8192-gpu2-pmin0136-fresh-20260626.submit.log) |
| 2026-06-26 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + selected-softmax + weighted-sum MoE guards + one-shot `MUL_MAT_ID` route cache | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded route-cache micro-record: direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, `MTP_P_MIN=0.136`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536/1536 canary; actual shape 588 input / 512 output tokens, first measured row `103.301 tok/s`, repeated rows are support only, `cached_tokens=0`; improvement over prior record was only `+0.001884 tok/s` | **103.301 first synthetic** / 103.063 supporting mean / 89.98 first-row wall | [summary](../../data/gemma4-q8-gpu0-mulmatid-routecache-full-20260626T184617Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626.submit.log) |
| 2026-06-25 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + selected-softmax + weighted-sum MoE guards | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: direct-unroll7 q-only recipe plus verifier backend argmax IDs, deferred target `h_nextn`, `MTP_P_MIN=0.136`, selected-softmax and weighted-sum Gemma4 MoE source guards (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`), `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536/1536 canary; actual shape 588 input / 512 output tokens, first measured row `103.299 tok/s`, repeated rows are support only, `cached_tokens=0` | **103.299 first synthetic** / 102.193 supporting mean / 89.85 first-row wall | [summary](../../data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z/summary.json), [repeat](../../data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-repeat-20260625T032710Z/summary.json), [LocalMaxxing response](../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-selectedsoftmax-weightedsum-pmin0136-fresh-20260625.submit.log) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + safer verifier row-argmax IDs + deferred target `h_nextn` + immediate command lists | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: direct-unroll7 q-only recipe plus stricter verifier row-argmax shape assertions, deferred target `h_nextn`, `MTP_P_MIN=0.14`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536/1536 canary; actual shape 588 input / 512 output tokens, first measured row `101.602 tok/s`, repeated rows are support only, `cached_tokens=0` | **101.602 first synthetic** / 100.835 supporting mean / 88.51 first-row wall | [summary](../../data/gemma4-q8-gpu1-rowargmax-safer-immediatecl1-full-20260624T193222Z/summary.json), [row-argmax/defer-h follow-up note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T1733-rowargmax-deferh-followups.md) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + safer verifier row-argmax IDs + deferred target `h_nextn` | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: direct-unroll7 q-only recipe plus stricter verifier row-argmax shape assertions, deferred target `h_nextn`, `MTP_P_MIN=0.14`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 1536/1536 canary; actual shape 588 input / 512 output tokens, first measured row `101.482 tok/s`, repeated rows are support only, `cached_tokens=0` | **101.482 first synthetic** / 101.249 supporting mean / 88.58 first-row wall | [summary](../../data/gemma4-q8-gpu0-rowargmax-safer-pmin014-full-20260624T183044Z/summary.json), [row-argmax/defer-h follow-up note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T1733-rowargmax-deferh-followups.md) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + verifier row-argmax IDs + deferred target `h_nextn` | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: direct-unroll7 q-only recipe plus verifier row-argmax IDs, deferred target `h_nextn`, `MTP_P_MIN=0.14`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens, first measured row `101.428 tok/s`, repeated rows are support only, `cached_tokens=0` | **101.428 first synthetic** / 100.769 supporting mean / 88.37 first-row wall | [summary](../../data/gemma4-q8-gpu0-rowargmax-deferh-pmin014-full-20260624T173546Z/summary.json), [row-argmax/defer-h follow-up note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T1733-rowargmax-deferh-followups.md) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + direct-unroll7 q-only assistant inputs + batch/thread tune + SYCL graph enabled | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: same Q8-target/Q4_0-draft direct-unroll7 q-only recipe as above, with `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled (`GGML_SYCL_DISABLE_GRAPH=0`), backend sampling off, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens, first measured row `98.617 tok/s`, repeated rows are support only, `cached_tokens=0` | **98.617 first synthetic** / 97.956 supporting mean / 86.26 first-row wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-syclgraph0-full-20260624T144749Z/summary.json), [batch/thread follow-up note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T1351-q8-batch-thread-followups.md) |
| 2026-06-24 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + direct-unroll7 q-only assistant inputs + batch/thread tune | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF target + Q4_0 MTP draft GGUF, f16 KV | 8K | superseded pre-final-gate filled-long diagnostic best: same Q8-target/Q4_0-draft direct-unroll7 q-only recipe as above, with `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, VMM off, backend sampling off, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens, first measured row `98.491 tok/s`, repeated rows are support only, `cached_tokens=0` | **98.491 first synthetic** / 97.886 supporting mean / 86.19 first-row wall | [summary](../../data/gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-b1024u1024-th8-full-20260624T135701Z/summary.json), [batch/thread follow-up note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T1351-q8-batch-thread-followups.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + fast argmax + CPU cleanup + VMM/ubatch/poll | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | superseded conservative pre-final-gate filled-long diagnostic result: same scalar recipe before clean full confirmation; actual shape 588 input / 512 output tokens, first request `92.397 tok/s`, repeated-request mean `92.767`, `cached_tokens=0` | **92.397 first synthetic** / 92.767 supporting mean / 83.29 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T2221-cpucleanup-vmm-fastargmax.md) |
| 2026-06-23 | vLLM `0.20.2rc1.dev13+g9557d9108` XPU online quant | 1 replica on B70 GPU1/GPU2 | official HF Gemma 4 26B A4B, `int8_per_channel_weight_only` and FP8 diagnostics | 8K | compatibility comparison: INT8 graph passed 128/128 at `34.89 tok/s`; FP8 per-tensor passed 64/64 at `40.31 tok/s`; selector fix required `ONEAPI_DEVICE_SELECTOR=level_zero:*` + `ZE_AFFINITY_MASK` | **34.89 INT8** / **40.31 FP8 diagnostic** | [vLLM sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T2032-vllm-int8-fp8-smokes.md), [best INT8 summary](../../data/gemma4-vllm-int8pc-gpu1-piecewise-selectorfix-smoke-20260623T204041Z/summary.json), [best FP8 summary](../../data/gemma4-vllm-fp8tensor-gpu2-compile12-piecewise-smoke-20260623T205416Z/summary.json) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draftless ngram-mod AOT BMG | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF, f16 KV | 8K | warmed/history artifact: `ngram-mod match=20 min=32 max=64`, `--ctx-checkpoints 0`, 384/384 canary; repeated 588+512 output became predictable after prior identical generations. Submitted before fresh/warmed rule clarification; retraction-needed. | **255.04 warmed/history** / 137.00 wall | [summary](../../data/gemma4-q8-gpu0-ngram-mod-20-32-64-ctxcp0-filled-long-deep-20260623T1750/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1735-ngram-spec-sweep.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draftless ngram-mod AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF, f16 KV | 4K | warmed/history artifact: same `ngram-mod match=20 min=32 max=64`, `--ctx-checkpoints 0`, `UBATCH_SIZE=512`, `POLL=50`, 384/384 canary; not a fresh-response or 32K-context claim. Submitted before rule clarification; retraction-needed. | **280.04 warmed/history** / 206.50 wall | [summary](../../data/gemma4-q8-gpu3-ngram-mod-20-32-64-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1815/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1735-ngram-spec-sweep.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draftless ngram-mod AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF, f16 KV | 4K | warmed/history artifact: same `ngram-mod match=20 min=32 max=64`, `--ctx-checkpoints 0`, `UBATCH_SIZE=512`, `POLL=100`, 384/384 canary; repeated 588+512 output became predictable from n-gram history. Submitted before rule clarification; retraction-needed. | **280.64 warmed/history** / 206.24 wall | [summary](../../data/gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1735-ngram-spec-sweep.md) |

The first valid result is intentionally labeled as a baseline, not an optimized
result. It proves that the Q8 GGUF fits and serves correctly at 8K on one B70,
but the decode rate is far below the public LocalMaxxing Gemma 4 family context
and should be treated as the control for four-at-a-time optimization sweeps.

`GGML_SYCL_DISABLE_OPT=0` is the largest speed lever so far despite an upstream
B70/Gemma corruption report for that flag. The promoted
`FLASH_ATTN=off --parallel 1 --cache-ram 0` variant passed a promotion-depth
deterministic chat gate (`96` repeats x `4` cases = `384/384`) before being
promoted. Treat any further optimized-SYCL variants as risky until they pass the
same or stronger gate.

The 42.72 tok/s no-spec sustained-decode row uses the same valid runtime
identity as the 42.15 natural-stop row, but a different benchmark prompt shape.
The model is forced to generate the full 512-token budget, so wall throughput
rises because TTFT is amortized over more output tokens.

The `long` prompt mode is a short 75-token prompt that forces 512 output tokens.
The newer `filled-long` mode was the historical diagnostic search shape for
this lane because it produces a near-p512/o512 request in practice: 588 prompt
tokens and 512 output tokens. On that shape, the previous conservative
pre-final-gate draft-MTP recipe reached **104.071 tok/s** on the first measured
synthetic row after TTFT, with a supporting repeated-request mean of
**103.589 tok/s** and `cached_tokens=0` on all rows. A later threshold repeat
on the same scalar stack reached **104.226 tok/s** first synthetic /
**104.174 tok/s** supporting mean with `MTP_N_MIN=3`, `MTP_P_MIN=0.10`, and
`UBATCH_SIZE=768`. A follow-up `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1` diagnostic
row reached **104.309 tok/s** first synthetic / **103.934 tok/s** supporting
mean, approved as `cmqw1tgzx0366qr01g4lkv7f1`, but it is superseded within the
diagnostic lane by later Q8 MoE-ID reorder rows up to **176.216 tok/s**. These
diagnostic rows use the source-level fast-argmax/CPU-cleanup stack plus
selected-softmax and weighted-sum Gemma4 MoE guards, `GGML_SYCL_ENABLE_VMM=0`,
`BATCH_SIZE=1024`, `UBATCH_SIZE=768`,
`THREADS=8`, `POLL=100`, `GGML_SYCL_DISABLE_GRAPH=0`, direct greedy
sampled-token IDs, direct-unroll7,
`LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`, verifier backend argmax IDs, deferred
target `h_nextn`, and the default-off
`LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1` one-shot route cache, plus Gemma4
assistant fused output argmax, fused selected-softmax weights, and
`LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`. The
target/verifier
remains `UD-Q8_K_XL`; only the MTP draft model is Q4_0. The run was approved
on LocalMaxxing as `cmqw1tgzx0366qr01g4lkv7f1` before the fixed realistic-suite
gate was adopted. It is now diagnostic/pre-final-gate unless revalidated on the
realistic suite. The previous
`104.22626983476746 tok/s` row remains useful as the same-family baseline;
the latest improvement is still a tiny row0 micro-record, not a material
optimization breakthrough. Draftless
`ngram-mod` speculation later produced **280.64 tok/s** after TTFT with
`match=20, min=32, max=64`, `CTX_SIZE=4096`, `UBATCH_SIZE=512`, and
`POLL=100`, but that is warmed/history throughput: the repeated benchmark
output became predictable from prior generated continuation history. It is
valid Q8 verification of a warmed continuation, not fresh-response no-cache
decode. Do not use the submitted ngram LocalMaxxing rows as headline records.
Under the current policy, the valid strict cold-suite high and representative
family are the fixed realistic-suite rows at the top of this file, not any
single synthetic row0 or repeated-row mean.
The after-TTFT decode metric is the promoted comparison metric. The wall/total
metric in repeated filled-long runs is warmed by the benchmark's repeated prompt
shape and can include substantial prompt-cache reuse after the first repeat; do
not compare it to a cold unique-prompt total-throughput benchmark without
labeling the difference.
Keep natural-stop, short-prompt
sustained-decode, and filled-long sustained-decode records separate when
comparing future runs, and keep MTP runs separate from no-spec runs unless
prompt/output shape and canary depth match.

## Linked Files

- [Reproduction commands](reproduce.md)
- [Validity gates](validity-gates.md)
- [Runtime plan](runtime-plan.md)
- [Research plan and experiment queue](research-plan.md)
- [Model and runtime options](model-options.md)
- [LocalMaxxing targets and submission packet](localmaxxing-and-targets.md)
- [Current 125 tok/s reproduction recipe](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
- [Prior 95 tok/s reproduction recipe](../../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md)
- [Bugs and failed paths](bugs-failed-paths.md)
- [Active experiment folder](../../experiments/gemma4-26b-a4b-q8-b70/README.md)
