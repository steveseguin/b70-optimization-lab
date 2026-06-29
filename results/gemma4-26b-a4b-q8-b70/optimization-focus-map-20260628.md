# Gemma 4 26B A4B Q8 B70 Optimization Focus Map

Date: 2026-06-28, updated 2026-06-29

Scope: Gemma 4 26B A4B `UD-Q8_K_XL` target/verifier on Intel Arc Pro B70,
with one full Q8/INT8-quality replica per B70. This is a focus map for where
future work should and should not spend time. It folds together the local
Gemma sweep history and a triage of recent Grok/X.com leads.

## At A Glance

Current valid record: `121.41411987308553 tok/s` median generated-token
throughput for tokens 1-100 after TTFT on the fixed realistic cold suite,
with `cached_tokens=0` on every prompt. The record identity is llama.cpp
`c926ad098`, `UD-Q8_K_XL` target/verifier, Q4_0 MTP draft, reordered-Q8 VDR2,
`FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`,
`n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`,
`LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, and
`LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`
with LM-head DMMV/no-reorder experiment flags unset. LocalMaxxing:
`cmqztiqdn02vnoe01egox6q3f`
(`results/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-record.md`).

Main conclusion: the strict realistic lane is still target/verifier-forward
bound, not draft-bound, but the first reliable `>100` win came from verifier
MoE boundary work: a VDR2-reordered Q8 selected-down fused weighted-sum backend.
Future speed work should now reduce exact verifier rows, exact LM-head
verification cost, or additional verifier MoE boundary cost.

Practical next focus:

1. Exact verifier LM-head candidate-vs-max design, but only as a real new
   source design. The existing fused `ggml_mul_mat_argmax(model.output, cur)`
   path is already tested and is slower than the backend-argmax-ID route.
2. A new verifier-row or bonus-token design that preserves the current bonus
   pipeline while avoiding unnecessary full LM-head rows. The simple no-bonus
   row and staged split-bonus approaches passed quality but were much slower.
3. Direct-unroll confidence scores/gating only if the scoring path itself is
   cheaper than the rows it removes. The first confidence/gap screens did not
   survive full512 confirmation.
4. DFlash/XPU and DeepSpec/DSpark as research tracks only after graph/KV
   injection or draft-generation cost changes. The first local DFlash PR 22105
   Gemma4 screen converted and loaded, but runtime was far too slow on SYCL.

Avoid:

- blind MTP depth expansion;
- more tiny `p_min`, `n_min`, thread, poll, UBATCH, VMM, graph, or frequency
  floor sweeps without a new source mechanism;
- more small Q8 reorder addressing variants;
- n-gram/history throughput as a record path;
- TurboQuant for this short strict speed lane;
- treating Q8_0 target runs as equivalent to `UD-Q8_K_XL`.

## Latest Other-AI Progress Review

Recent work mostly **closed low-ROI paths** rather than finding another stable
speed jump. That is useful: it narrows the next agent's search space.

Latest confirmed state:

- `qwen36-results-main` now records the accepted 121.414 tok/s LocalMaxxing
  row and the late negative/default-off LM-head screens. Future agents should
  start from the explicit docs/results in this folder rather than assuming a
  clean tree means no pending research artifacts.
- Active record source
  `/home/steve/src/llama.cpp-gemma-record-repro-c926` is a detached worktree at
  `c926ad098` with broad dirty source changes across speculative sampling,
  Gemma4 graph/model code, and SYCL/MMVQ kernels. Do not reset or rebase it
  while an optimizer is running.
- The current promoted Gemma Q8 record is now `121.41411987308553 tok/s`
  via the VDR2 selected-down fused weighted-sum path plus FA-on 32K/VMM. The
  winning row was a baseline/control identity; the DMMV and no-reorder LM-head
  flags were unset.

Recent useful progress:

- Preserved the full current record artifact packet and reproducibility trail:
  latest pushed docs commits include `docs: close Gemma crack-100 config lanes`,
  `docs: record Gemma crack-100 reliability closure`, `docs: capture Gemma
  verifier kernel audit`, and `docs: preserve Gemma optimization artifacts`.
- Confirmed that `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1` plus
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` remains part of the strict record stack,
  now joined by `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`.
- Verified that the strict lane is still verifier/target-forward bound, not
  draft-bound. Profiles point first at target LM-head full-vocab projection,
  then verifier MoE gate/up/down `MUL_MAT_ID`.

Recent closed negatives:

- Crack-100 config roulette: `p_min`, unroll, thread counts, frequency floor,
  solo-vs-four-GPU, and context-size screens produced valid near-100 or
  occasional `100+` observations, but did not confirm reliably above the
  `98.340` record.
- Host/server cleanup: sampler-clone skip and identity `out_ids` skip passed
  strict quality screens but lost or failed confirmation against controls.
- Verifier-row scheduling: simple no-bonus row and staged MTP3 split-bonus were
  semantically valid but much slower because they disrupted the current
  verifier/bonus pipeline.
- Prefix2 tail-head verifier scheduling: keeping two prefix verifier rows in
  the main decode and running a batched `SPEC_HEAD` tail pass preserved strict
  validity, but lost (`106.4` / `100.9 tok/s` versus controls `113.1` /
  `109.8`). The added head-only pass ran on almost every generation step and
  cost `~2.7 ms/call`, so do not retest this shape as implemented.
- Device `h_nextn` handoff: safe row-view copies worked after view
  initialization, but were slower than the current host-staged path.
- DFlash PR 22105: Gemma4 DFlash BF16 draft conversion worked after a Gemma4
  vocab writer patch, but local SYCL runtime was unusably slow. Early eval was
  around `0.70-4.01 tok/s`, and DFlash draft generation was roughly
  `140 ms/call`. This is a graph/KV/draft-cost research item, not a record knob.
- Fused selected-softmax into selected-down VDR2:
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1` passed the fixed cold
  strict128 gate and 512/512 canary rows on both flag-on lanes. It was a real
  small paired win (`114.762` vs `113.943`, `115.554` vs `113.967`) but still
  below the promoted `121.41411987308553 tok/s` full512 record. The later
  full512 promotion screen was valid but lost (`111.896` flag-on, `111.909`
  flag-on + EOG clip, controls `112.220` / `112.997`). Preserve it as a
  default-off archived mechanism; do not retest this interaction as a record
  lane. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-down-selected-softmax-strict128.md`
  and
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-selected-softmax-full512-negative.md`.
- Adaptive bonus-row skipping:
  `LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_ROW=1` was tested with three thresholds
  after adding exact no-bonus full-match handling. All lanes passed the fixed
  cold strict128 gate, but the best adaptive lane was slower (`109.556 tok/s`)
  than the same-build control (`112.021 tok/s`) and had a worse p10. This
  reinforces that removing the current bonus pipeline is not the right row
  economy. Preserve the patch/result and do not promote. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-adaptive-bonus-row-negative.md`.
- Deferred verifier pending-`h` copy:
  `LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY=1` skipped the verifier-batch
  `pending_h` refresh and relied on `accept()` to copy the exact accepted row.
  It passed the fixed cold strict128 gate in a paired screen and a cross-over,
  but did not produce a stable win. Control medians averaged `114.453 tok/s`;
  flag-on medians averaged `112.422 tok/s`. The first-screen `118.110 tok/s`
  flag-on lane was an outlier, not a promotion candidate. Preserve the
  patch/result and do not full512-confirm or submit. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-defer-verifier-pending-h-copy-negative.md`.
- Candidate-threshold verifier LM-head:
  a read-only row-mapping audit confirmed that shifted `t_inp_tokens[r + 1]`
  gives the draft candidate ID for the narrow standard verifier shape. This is
  still not a good next record implementation: exact mismatch handling requires
  the true target token, so the kernel would still do full-vocab dot and
  top1/challenger work, duplicating the closed top1 epilogue/reduction family.
  Preserve as a no-go until a design removes verifier LM-head rows or proves a
  candidate win without scanning the full vocabulary. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-candidate-threshold-lmhead-no-go.md`.
- Context threshold / service split:
  this is not a short-record lane, but the long-context diagnostics now have a
  practical split. With FA off, current MTP is useful through
  `CTX_SIZE=24576`/`25600`, degraded at `26624`, and cliffed at `27648+`.
  With `FLASH_ATTN=on`, the same MTP stack becomes viable through true 32K:
  `~102.7-103.2 tok/s` after TTFT at `27648`, `28672`, and `32768` on the
  ~11K-token synthetic diagnostic, with `cached_tokens=0`. This is service
  guidance only, not a short-record or LocalMaxxing headline.
  See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-context-threshold-mtp-vs-nospec.md`.

Implication for the next AI: do not spend another session on launch-flag
sweeps or bonus-removal variants. The next credible record attempt needs a
real verifier-cost reduction that preserves the bonus path: compact exact
LM-head/max handling inside the existing decode boundary, or a verifier MoE
boundary/kernel change.

## Current Baselines And Guardrails

| Lane | Result | What it means | Source |
| --- | ---: | --- | --- |
| Strict current record | `115.847` tok/s | Current policy-compliant headline, VDR2 selected-down fused weighted-sum | `20260629-vdr2-selected-down-record.md` |
| Previous strict row | `98.340` tok/s | Superseded by VDR2 selected-down fusion | `README.md`, `research-plan.md` |
| Previous strict row | `95.825` tok/s | Superseded by bulk sampled-ID verifier cleanup | `README.md:159-160`, `research-plan.md:43-65` |
| Earlier strict VDR2 | `90.983`, `90.322`, `89.455` tok/s | Valid progression, superseded | `README.md:161-167`, `research-plan.md:84-95`, `research-plan.md:167-177` |
| No-spec control | `74.297` tok/s | Clean target-side baseline | `README.md:37-41` |
| Old synthetic MTP diagnostic | `176.216` tok/s | Mechanism discovery only, not headline | `README.md:43-54`, `research-plan.md:367-384` |
| N-gram warmed/history | `245-280` tok/s | Invalid as fresh-response headline | `README.md:68-73`, `README.md:213-215`, `README.md:265-270` |
| vLLM Gemma INT8/FP8 local smokes | `34.89` / `40.31` tok/s | Compatibility/reference only, not current speed path | `README.md:212`, `research-plan.md:1136-1138` |

Promotion gate remains strict: fixed realistic prompt suite, each prompt once,
`cached_tokens=0`, no prompt/KV/cache/history/ngram/response reuse, no context
checkpoints, same target model and quantization, and target-verified speculative
tokens only (`AGENTS.md:119-134`, `reproduce.md:3-18`).

## How To Use This File As An Agent

First decide the lane before touching code:

- Record lane: same `UD-Q8_K_XL` target/verifier, same strict cold prompt suite,
  no cache/history reuse, and same output-quality assumptions.
- Research lane: new algorithm or upstream port such as DFlash, EAGLE-3, or
  DSpark. Keep it separate from the active record source until it passes a
  strict smoke.
- Service/context lane: vLLM, TurboQuant, FP8 KV, long-context, or
  high-concurrency experiments. Do not compare these numbers to the strict
  single-session llama.cpp Q8 record.

Before coding:

1. Read `AGENTS.md`, `CURRENT.md`, `AGENT_HANDOFF.md`, this file,
   `README.md:3-35`, `research-plan.md:9-25`, and `reproduce.md:152-190`.
2. Check the active source tree status. The current source may be dirty because
   another experiment is running; do not reset or overwrite it.
3. If trying DFlash or upstream llama.cpp changes, create a separate source
   checkout or branch. Do not mix an upstream rebase into the active record
   source.
4. Write a short run note before the first long run: idea, patch path, command,
   expected win, and kill criterion.

Minimum evidence before promoting any result:

- run identity with all flags/env vars;
- `cached_tokens=0` evidence for each prompt;
- throughput median for the same token window used by the record;
- correctness/quality status and target-verification status;
- comparison to the exact current record identity, not stale `CURRENT.md`;
- profile summary if the patch is meant to reduce LM-head, MoE, draft, or
  host-copy cost;
- patch snapshot or commit SHA.

Early-stop rule: if a 128-token strict screen is below the current record by
more than normal variance and the profile does not show the intended bottleneck
moving, stop and record the negative. Do not spend a day confirming a patch
that failed its own mechanism test.

## Priority Queue For The Next Agent

| Rank | Work item | Start here | First test | Promote only if | Kill if |
| --- | --- | --- | --- | --- | --- |
| P0 | Sync stale top-level state | `CURRENT.md`, `README.md:3-35` | Documentation-only diff | `CURRENT.md` stops pointing agents at `95.824` as current Gemma state | User wants no doc churn |
| P0 | New verifier LM-head kernel design | `research-plan.md:189-199`, `research-plan.md:532-536`, `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/models/gemma4.cpp:589`, `/home/steve/src/llama.cpp-gemma-record-repro-c926/ggml/src/ggml-sycl/ggml-sycl.cpp:5585` | Kernel microbench and strict128 ID-equivalence screen | It beats both regular Q8 matmul+backend-argmax and existing `ggml_mul_mat_argmax` while returning exact target IDs | It is just candidate plumbing around the already-slower fused argmax op |
| P1 | PP and long-context measurement ladder | `README.md:80-135`, `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md:1708-1735`, `AGENT_HANDOFF.md:295-335` | Cold prompts at `128-16384` tokens plus outputs `1/16/64`, then long-output sustained windows | It produces repeatable TTFT, prefill, VRAM, and decode-window data without changing the short record recipe | It mixes cached-prefix/service numbers into the strict cold record lane |
| P1 | llama.cpp prompt-cache and slot service lane | llama.cpp server `cache_prompt`, `/slots`, `--cache-ram`, `--cache-idle-slots` docs | Stable-prefix repeated-prompt A/B with canary answer hashing | It cuts repeated-prefix TTFT without changing generated text or short cold decode | It is proposed as a LocalMaxxing fresh-prompt record path |
| P2 | KV precision ladder for context headroom | llama.cpp `-ctk/-ctv`, issue `#10378`, `README.md:80-135` | `ctk=q8_0`, then K/V combinations only after flash-attention compatibility check | It extends context or reduces long-context slowdown while passing quality canaries and rerunning the short suite | V-cache quant forces a slower flash-attention profile or changes quality |
| P2 | DeepSpec/DSpark idea mining | DeepSpec README checkpoint table and algorithm docs | Read implementation for confidence scheduling only | A small idea can be ported to current MTP confidence gating | Requires training a Gemma26 drafter before any local screen |
| P2 | Intel llm-scaler/vLLM A/B | Intel `llm-scaler` README, `README.md:212` | Same-model service smoke, not record comparison | It materially beats old local vLLM smokes or helps Qwen service lanes | It remains far below llama.cpp strict speed |
| P2 | vLLM/llm-scaler FP8 KV and chunked prefill | vLLM chunked-prefill/APC/KV-cache docs, Intel `llm-scaler` 2026.06 notes | Service-only smoke with conservative `max_num_batched_tokens` and FP8 KV quality gate | It improves PP or long-context service behavior while decode remains stable in its own lane | Intel compiler/runtime instability appears or quality canaries fail |
| P3 | Disaggregated prefill and LMCache | vLLM disaggregated prefill and LMCache examples | Two-instance exact-KV handoff smoke, possibly one B70 prefill worker and one decode worker | It preserves decode latency while isolating long prefill or repeated-prefix cost | KV transfer overhead exceeds the saved prefill time on local B70s |
| P3 | TurboQuant long-context check | vLLM TurboQuant docs/blog | Long-context capacity test only | It solves KV pressure for a separate long-context lane | It is proposed as a strict 8K speed-record knob |

## PP And Long-Context Roadmap

PP means prompt processing/prefill. Treat this as a separate optimization lane
from the current short cold decode record. The goal is to improve TTFT,
long-context viability, and sustained decode at higher context lengths without
regressing the `98.340` short-decode recipe or lowering output quality.

### Current Local Evidence

- The current promoted realistic suite is short. Its prompt-token counts are
  only `61,62,66,67,69,69,69,73,79,85,87,92`, with median TTFT about
  `180.211 ms` and `cached_tokens=0`. It is a decode stress test, not a PP
  stress test.
- A same-shape `CTX_SIZE=2048` strict full512 retest was valid but below the
  record: `97.814`, `98.117`, `96.256`, and `97.441` tok/s across the four
  B70s (`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md:1708-1735`).
- An older `ctx4096 + ub512 + VMM=0 + top_k=10` run was a useful PP/context
  reference, with `91.426441` tok/s after TTFT, `82.138882` wall tok/s, and
  `636.308 ms` TTFT, but it was not a record path
  (`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1657-vmm-ubatch-followups.md:31-58`).
- The existing target state already says to solve short/small-context decode
  first, then test 32K-context viability after Q8 fit. The Q8 target is about
  `27.6 GB`, so a 32 GB B70 leaves limited KV and fragmentation headroom
  (`results/gemma4-26b-a4b-q8-b70/README.md:80-135`).
- MiniMax service work is the best local long-context cautionary source:
  larger prefill chunks such as `1024` can trigger Intel compiler failures, a
  c1 service-managed 32K profile had prompt `32264`, output `64`,
  `63.91` output tok/s after TTFT, approximate prefill `1382.57 tok/s`, and
  TTFT `23.336s`, and the current exact full active `196608` context path is
  still CPU-paged-attention research rather than a launch-flag fix
  (`AGENT_HANDOFF.md:148-202`, `AGENT_HANDOFF.md:295-335`).

### Guardrails

- Keep the short cold record gate frozen. Any PP/context candidate must rerun
  the current short suite and report whether tokens 1-100 after TTFT still
  match or exceed the latest confirmed short-decode baseline.
- Do not compare cached-prefix, slot-restore, APC, or LMCache numbers to the
  strict cold record. Label them as service lanes.
- Do not lower target weight quality. Lower weight quants, approximate routing,
  token fusion, layer skipping, and non-exact halting belong in a separate
  quality-research lane unless they pass explicit semantic and canary gates.
- Treat KV precision as quality-affecting until proven otherwise. Test exact
  prompt canaries, long-context retrieval canaries, and response drift before
  calling FP8, Q8, Q4, or TurboQuant KV safe for a production lane.
- Avoid RoPE/YARN/native-context extension tricks in the no-quality-loss lane
  unless the model card and a local quality suite support the context range.
- Record cold and warm behavior separately. For the same prompt, store
  `cached_tokens`, TTFT, wall tok/s, after-TTFT tok/s, output length, and any
  slot or prefix-cache identity.

### Measurement Ladder To Build First

Before changing kernels or server behavior, build a reproducible ladder that
captures where PP or long-context decode actually falls over:

1. Cold prefill ladder: prompt tokens `128,512,1024,2048,4096,8192,12288,16384`,
   then `24576` and `32768` only if the model fits cleanly. Use outputs
   `1`, `16`, and `64`. Capture TTFT, wall time, generated tok/s after TTFT,
   conservative prompt tok/s lower bound, VRAM, server log, and quality canary.
2. Sustained long-decode ladder: prompt tokens `2048,4096,8192,12288,16384`,
   then `24576/32768` if available. Use outputs `512` and `1024`, and report
   token windows `1-100`, `101-200`, `401-512`, and `901-1000` when present.
3. Warm service ladder: repeat a stable system prompt or long document prefix
   with `cache_prompt`, slot save/restore, APC, or LMCache enabled. Compare
   only to its own cold service baseline.
4. Always finish with the strict short suite. A context win that silently costs
   the short 61-92-token decode lane should remain a separate service profile.

### Candidates Worth Trying

- Phase-specific batch tuning in llama.cpp: tune `-b`, `-ub`, and `-tb`
  separately for prefill and decode screens. The llama.cpp server exposes
  `-tb/--threads-batch` for prompt/batch CPU work and `-b/-ub` for logical and
  physical batch sizing. Expect regressions if VRAM or private memory pressure
  increases; local `ctx4096 + ub512 + VMM=0` evidence suggests this is worth
  measuring, not blindly pushing to `2048/4096`.
- llama.cpp prompt-cache and slot service mode: `cache_prompt=true` evaluates
  only the unseen suffix when a request shares the previous prompt prefix, and
  server slots plus `--cache-ram`/`--cache-idle-slots` can make multi-turn or
  repeated-prefix workflows much faster. The docs warn that `cache_prompt` can
  make runs nondeterministic because prompt processing and token generation use
  different batch sizes, so hash prompts, responses, and canary answers.
- vLLM automatic prefix caching: APC is a clean service candidate for repeated
  system prompts, RAG with shared document prefixes, and multi-round chats. It
  should not help fresh one-shot decode, so use it for TTFT and reuse, not for
  LocalMaxxing-style cold records.
- vLLM chunked prefill: V1 prioritizes decode requests and batches chunked
  prefills around them; smaller `max_num_batched_tokens` favors inter-token
  latency while larger values favor TTFT and throughput. On local Intel paths,
  start conservative because MiniMax notes show larger chunks can trip
  `ocloc`/IGC failures.
- KV precision ladder: for llama.cpp, try K-cache first with `-ctk q8_0` while
  leaving V at f16/bf16, then only test V-cache quant after flash-attention
  compatibility is understood. llama.cpp issue `#10378` notes that V-cache
  quantization requires flash attention, which matters because the current
  record uses `FLASH_ATTN=off`.
- Intel llm-scaler/vLLM FP8 KV: Intel's B60/B70-focused llm-scaler 2026.06
  release notes include FP8 KV cache support, and vLLM documents FP8 KV as a
  memory-footprint reduction that can improve throughput and enable longer
  contexts. This is a service/context candidate until local Gemma vLLM speed
  closes the gap with llama.cpp.
- Disaggregated prefill and LMCache: vLLM can run separate prefill and decode
  instances, and LMCache adds CPU/disk offload plus KV sharing between
  instances. On four B70s, the useful experiment is not a short record attempt;
  it is whether one prefill worker can absorb long prompts while another
  decode worker preserves decode latency.
- Long-term decode scheduler checks: if tokens `401-512` or `901-1000` slow
  down while `1-100` stays fast, inspect attention/KV bandwidth, memory
  fragmentation, and graph reuse before changing speculation. If all windows
  slow down equally at long context, KV format and attention path are more
  likely than draft parameters.

External source details for this roadmap:

- vLLM chunked prefill: large prefills can be chunked and batched with decode;
  V1 prioritizes decode, and `max_num_batched_tokens` trades ITL against TTFT
  (`https://docs.vllm.ai/en/stable/configuration/optimization/`, reviewed page
  lines 2567-2580).
- vLLM automatic prefix caching: APC reuses KV for shared prefixes and helps
  repeated long documents or multi-round conversations; it does not reduce
  decode time when generation dominates or prompts do not share prefixes
  (`https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/`,
  reviewed page lines 2510-2528).
- vLLM FP8 KV cache: quantized KV reduces memory footprint, supports longer
  context windows, and has per-tensor and per-head schemes, with per-head
  currently tied to the flash-attention calibration pathway
  (`https://docs.vllm.ai/en/latest/features/quantization/quantized_kvcache/`,
  reviewed page lines 2520-2533).
- llama.cpp server: `/completion` with `cache_prompt=true` compares the prompt
  with the previous completion and evaluates only the unseen suffix
  (`https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md`,
  reviewed page lines 207-208).
- Intel llm-scaler: the repo targets Arc Pro B60/B70 and its 2026.06 image
  notes include FP8 KV cache enablement in `intel/llm-scaler-vllm:0.14.0-b8.3.1`
  (`https://github.com/intel/llm-scaler`, reviewed page lines 252-260).
- vLLM disaggregated prefill and LMCache: vLLM describes separate prefill and
  decode instances connected by KV transfer, and LMCache documents CPU/disk
  offload, disaggregated prefill, and KV sharing
  (`https://docs.vllm.ai/en/latest/features/disagg_prefill/`, reviewed page
  lines 2545-2552;
  `https://docs.vllm.ai/en/latest/examples/disaggregated/lmcache/`, reviewed
  page lines 2529-2544).
- llama.cpp KV quantization caveat: issue `#10378` shows the runtime error
  `V cache quantization requires flash_attn`, so V-cache quantization is not
  neutral for the current flash-attention-off record profile
  (`https://github.com/ggml-org/llama.cpp/issues/10378`, reviewed page lines
  210-213).
- llama.cpp TurboQuant discussion: the March 2026 proposal reports TQ4 about
  `3.8x` compression versus FP16, but its initial path dequantizes before
  flash attention and omits QJL correction, making it a capacity experiment
  before it is a speed or quality-preserving default
  (`https://github.com/ggml-org/llama.cpp/discussions/20969`, reviewed page
  lines 651-671).

### Likely Not Worth Trying

- Prefix-cache, slot-restore, APC, or LMCache as a strict fresh-prompt record
  path. They are valuable service optimizations but violate the cold-record
  comparison if reused prefix tokens are counted as free.
- More blind `-ub`, VMM, or top-k launch sweeps without a PP/context ladder.
  Local follow-ups already found useful but non-record context variants, and
  short-decode work shows diminishing returns without a new source mechanism.
- TurboQuant as a first response to 32K Gemma. It is a capacity research tool,
  and the current llama.cpp proposal dequantizes before flash attention in the
  non-fused path. Try FP8/Q8 KV first, then TurboQuant only when the target is
  larger context rather than short decode.
- CPU KV offload as an active-context speed fix. MiniMax notes support RAM
  session cache for parked windows, but active CPU overflow is a separate
  CPU-paged-attention problem and should be measured as such.
- Lower target weight quantization or approximate context fusion if the stated
  requirement is no quality loss. Keep those in a separate lossy-performance
  research file.

## Experiment Template For New Notes

Use this compact shape in `notes/`, `experiments/`, or the Gemma result packet
so later agents can classify the attempt quickly:

```markdown
## YYYY-MM-DD short-name

Lane: record | research | service/context
Source: `/path/or/commit`
Patch: `/path/to/patch` or commit SHA
Hypothesis:
Command/env:
Run identity:
Result:
Correctness/cache status:
Profile delta:
Decision: win | loss | inconclusive | follow-up
Next action:
```

## What Worked

| Mechanism | Why it worked | Evidence |
| --- | --- | --- |
| One full replica per B70 | Avoids multi-GPU TP/collective overhead for this 1x record lane and allows four independent screens in parallel | `README.md:150-153`, `research-plan.md:3-5` |
| MTP with Q4_0 draft | Draft-MTP clearly beats no-spec under the strict gate, but only when shallow and verifier-friendly | `README.md:37-41`, `README.md:159`, `reproduce.md:152-190` |
| VDR2 reordered Q8 MoE-ID path | Made broad multi-token Q8 expert path viable and produced the strict VDR2 transfer | `README.md:159-167`, `research-plan.md:84-95`, `research-plan.md:367-384` |
| `n_max=3`, `n_min=2`, `p_min=0.0475` | Best strict realistic identity after adaptive/static/deeper sweeps | `research-plan.md:84-104`, `research-plan.md:167-177` |
| `UBATCH_SIZE=1024` strict VDR2 shape | Current strict identity; older UBATCH/threshold variance did not displace it | `README.md:159`, `reproduce.md:152-190` |
| `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` | Only useful source flag in its strict screen; lifted record to `95.824` before bulk verifier cleanup | `research-plan.md:43-56` |
| `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1` | Removes per-row verifier sampled-ID accessor overhead while preserving verifier semantics; lifted strict record to `98.340` | `research-plan.md:58-65`, `reproduce.md:167-182` |
| Direct argmax-ID MTP/q-only assistant inputs/fused assistant output path | Major synthetic diagnostic path before strict gate; still part of current recipe, but not sufficient alone | `reproduce.md:167-188`, `reproduce.md:350-384`, `README.md:247-258` |
| Selected-softmax/weighted-sum/RMS reuse/route-cache stack | Helped synthetic mechanism discovery; pieces remain in current recipe | `README.md:247-258`, `reproduce.md:372-384` |
| No cache/history and exact identity discipline | Prevented false records after n-gram and synthetic rows | `README.md:68-73`, `research-plan.md:43-56` |

## What Did Not Work

| Attempt | Result | Decision |
| --- | --- | --- |
| Adaptive MTP and `dp.n_max` generation-stop fix | Best strict adaptive row only `83.342` tok/s | Keep negative artifact, do not promote (`research-plan.md:76-82`) |
| Tiny `p_min` refinements | Best tight follow-up only `88.972`, repeat `0.0475` fell to `87.144` | Low ROI without source/runtime change (`research-plan.md:97-104`) |
| `n_max=4` strict variants | `82.120` / `85.933` tok/s | Stop deeper-MTP threshold sweeps (`research-plan.md:167-177`) |
| Blind direct-unroll depths `8/9/10/12` | `66.848` to `82.929` tok/s | Do not expand depth without direct-path confidence scores or lower verifier cost (`research-plan.md:545-555`) |
| Alternate MTP draft quants | Strict Q4_K_M/Q5_K_M/Q6_K/Q8_0 all below Q4_0; Q2_K also lost hard (`85.779-88.903` vs Q4_0 control `95.282`) | Keep Q4_0 draft (`README.md:163`, `research-plan.md:1215-1223`, `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md`) |
| Literal `Q8_0.gguf` target | Strong control but not reproducible record; best confirmations `88.949`/`89.892`, best deeper `90.277` | Control lane only, not no-quality-loss headline (`research-plan.md:154-165`) |
| Grouped reordered-Q8 MoE | Strict-valid but only `83.908`; grouping/register/scatter cost beat duplicate-read savings | Do not retry unchanged (`README.md:166`, `research-plan.md:106-115`, `research-plan.md:1208-1214`) |
| Direct VDR2 Q8 reorder specialization | Screen `90.712`, confirmations `86.369-89.784` | Negative (`research-plan.md:117-126`) |
| Top-8 slots Q8 reorder | Strict-valid lanes `86.846-91.457`; activation reuse lost to register/private memory pressure | Small Q8 addressing variants exhausted (`research-plan.md:128-139`) |
| Raw verifier argmax before softcap | Exact, but confirmation only `85.380-88.229`; full vocab projection still paid | Need to avoid/reduce LM-head, not just skip softcap (`research-plan.md:141-152`) |
| Runtime copy/allocation flags | `ASYNC_MEM_OP=0`, `DEV2DEV_MEMCPY=1`, `LEVEL_ZERO_API=0` all below record | Do not repeat without profile pressure (`research-plan.md:201-210`) |
| Route-cache/gate-up metadata flags | Singleton direct, device map, inplace, combo all below record | Closed under strict gate unless profile changes (`research-plan.md:212-222`) |
| Frequency floor / unroll6 `>100` screens | One `100.224` and one `101.076`, but confirmations dropped to `92.856-97.054` | Valid high observations, not records; restore default frequency (`research-plan.md:67-74`) |
| `h_nextn` cache guard | 128-token screen `97.442`; full512 lanes `94.633-96.815`; saved copy time only `3.495 ms` over about `4756` target tokens | Negative; stop host `h_nextn` micro-optimizations (`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T1319-hnextn-cacheguard-negative.md:1-66`, `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T1319-hnextn-cacheguard-negative.md:94-107`) |
| EAGLE3 Gemma4 speculator | Record env startup crashes because verifier direct-argmax is applied to the draft EAGLE3 context; disabling it lets graph-off run, but strict128 is only `72.651` tok/s, and graph-on request crashes with `Graph nodes cannot depend on events from outside the graph` (`OP MUL_MAT`) | Closed for near-term crack-100 work; only revisit on a dedicated graph-integration branch (`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md`) |
| vLLM INT8/FP8 Gemma smokes | `34.89` INT8 and `40.31` FP8 | Keep as reference, not current speed fallback (`README.md:212`, `research-plan.md:1108-1109`) |
| N-gram/history | Huge `255-280` warmed rows | Useful for warmed repetition workflows, invalid for fresh strict records (`README.md:68-73`, `README.md:213-215`) |

## Worth Trying Again Or Improving

These have enough signal to justify another focused branch or short screen.

### 1. New Verifier LM-Head Kernel Design

Why: strict node profile says target LM-head full-vocab projection is the top
node, about `1.380 ms/call`, followed by verifier MoE. Raw argmax/softcap
shortcuts did not help because they still pay full projection cost. The
research plan already names `LLAMA_SPEC_VERIFY_CANDIDATE_MAX=1` as a candidate
direction (`research-plan.md:189-199`, `research-plan.md:532-536`).

What the 2026-06-28 verifier-kernel audit found: the existing
`ggml_mul_mat_argmax(model.output, cur)` path already avoids materializing the
full `[vocab, n_outputs]` logits tensor and returns compact exact target IDs,
but it is slower than the current regular Q8 matmul plus backend `ggml_argmax`
path on this B70 stack. A candidate-aware wrapper that still computes the true
global max is likely to inherit that slower custom MMVQ/reduction path unless
the backend kernel itself is materially improved.

Strict-safe constraint: scoring only drafted token IDs is invalid because the
target may prefer another vocab token, and the bonus row needs the true target
greedy token. Any promoted verifier shortcut must either compute the exact
global maximum over the full `262144` vocab or prove a rigorous upper bound
under the same Q8 dot, tie, softcap, suppress-token, and LoRA semantics.

First viable shape: a kernel-level redesign of the existing fused argmax,
microbenchmarked before strict runs. A bounded source prototype would touch
`src/models/gemma4.cpp`, `src/llama-graph.{h,cpp}`, `src/llama-context.cpp`,
`common/sampling.cpp`, `ggml/include/ggml.h`, `ggml/src/ggml.c`, and the SYCL
Q8 fused matmul/argmax code in `ggml/src/ggml-sycl/ggml-sycl.cpp` /
`ggml/src/ggml-sycl/mmvq.cpp`. Do not spend a full strict batch on this unless
a microbench proves it beats the existing `MUL_MAT_ARGMAX` implementation.

### 2. DFlash In llama.cpp, Only After Runtime/KV Changes

Why: this is the biggest new external lead. The DFlash repo lists a Gemma 4
26B-A4B DFlash draft model and says Gemma4 currently needs a temporary vLLM
Gemma4 build (`https://github.com/z-lab/dflash/blob/main/README.md#L10-L21`,
`https://github.com/z-lab/dflash/blob/main/README.md#L51-L65`). llama.cpp PR
`#22105` was merged on 2026-06-28 and adds `--spec-type draft-dflash`;
the PR description says DFlash drafts an entire block in one forward pass and
shows a Qwen example command (`https://github.com/ggml-org/llama.cpp/pull/22105`,
page lines 178-188 and 223-279 in the reviewed PR page).

Why not immediate: the active local record source is still `c926ad098` and does
not expose `draft-dflash`; its `common_speculative_type_from_name_map` includes
`draft-eagle3`, `draft-mtp`, and n-gram types only
(`/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp:29-39`,
`/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp:2584-2595`).
There are only DFlash-related comments in the local source
(`/home/steve/src/llama.cpp-gemma-record-repro-c926/src/llama-context.cpp:1596-1604`).

Local update: the other AI already created a DFlash PR 22105 test checkout at
`/home/steve/src/llama.cpp-dflash-gemma4`. A small isolated
`conversion/qwen.py` patch made the Gemma4 DFlash BF16 draft convert with the
right Gemma4 vocab metadata. The converted server loaded and produced valid
early acceptance signals, but runtime was unusably slow on the current SYCL
stack: representative early eval was only `0.70-4.01 tok/s`, and DFlash
generation cost was about `140 ms` per draft generation call. See
`patches/gemma4-26b-a4b-q8-b70/20260628T2127-dflash-pr22105-gemma4-vocab-negative.md`.

Important implementation detail: a llama.cpp DFlash discussion identified KV
cache injection as the major blocker/shape issue. The workaround recomputes
accumulated target features and invalidates graph reuse; the ideal solution is
persistent DFlash K/V cache injection (`https://github.com/ggml-org/llama.cpp/discussions/24904`,
reviewed page lines 230-272). Maintainer guidance was to use a dual-mode graph:
embedding batches project/copy K/V into cache, token batches run regular decode,
with `llama_decode` after `llama_encode` for injection (same discussion,
reviewed page lines 307-313).

Recommended path if revisited: first solve or profile the DFlash
draft-generation overhead and KV/graph injection shape. Do not mix this into
the active dirty record source while an experiment is running, and do not spend
strict full512 time until a micro/profile screen shows draft generation is in
the same rough cost class as MTP rather than two orders of magnitude slower.

First test if the runtime changes: correctness canary, strict 128-token cold
gate, DFlash generation-time telemetry, accepted-length telemetry, and
target/verifier `process_ubatch_ms`. Stop immediately if draft generation is
still dominating wall time.

### 3. EAGLE-3 Gemma4 Speculator

Why: unlike DFlash, active local source already supports `draft-eagle3`
(`/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp:29-39`,
`/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp:638-647`).
Upstream llama.cpp speculative docs list `RedHatAI/gemma-4-26B-A4B-it-speculator.eagle3`
as a supported draft model (`https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md`,
reviewed page lines 255-280).

Why it might help: EAGLE-3 uses target hidden states and a small draft model.
It may have a lower draft overhead profile than the current MTP path. It still
needs target verification, so it will only matter if it changes accepted-token
shape enough to reduce verifier rows per output token.

Test: one strict 128-token screen with same target/verifier, no cache reuse,
then compare accepted length, target `process_ubatch_ms`, and draft time against
MTP. Do not spend a full day before a profile says it has a path.

### 4. DSpark / DeepSpec As A Research Source

Why: Grok's DSpark mention is at least partially real. `deepseek-ai/DeepSpec`
exists and says it is a full-stack codebase for speculative decoding data
preparation, training, and evaluation (`https://github.com/deepseek-ai/DeepSpec/blob/main/README.md#L1-L21`).
It includes released checkpoints for Eagle3, DFlash, and DSpark across Qwen3
4B/8B/14B and Gemma4 12B, and says supported algorithms are DSpark, DFlash, and
Eagle3 (`https://github.com/deepseek-ai/DeepSpec/blob/main/README.md#L53-L69`).

Why not immediate: the released checkpoint table does not list Gemma 4 26B-A4B,
only Gemma4 12B (`DeepSpec README.md#L58-L62`). Training defaults assume an
8-GPU node and the data pipeline warns of very large target cache storage
(`DeepSpec README.md#L27-L39`). This is not a quick B70 record knob.

Worth extracting: DSpark's confidence scheduling and semi-autoregressive ideas
may inform our direct-unroll confidence-gating design, even if we do not train a
new 26B drafter immediately.

### 6. Fresh Intel LLM Scaler / vLLM A/B As A Separate Serving Lane

Why: Intel's `llm-scaler` is real B60/B70-focused infrastructure. The README
lists June 2026 images, including `0.14.0-b8.3.2` for Qwen3.5/3.6 accuracy
fixes and `0.14.0-b8.3.1` for FP8 KV cache
(`https://github.com/intel/llm-scaler/blob/main/README.md#L1-L15`). Its vLLM
README says it is an Intel multi-GPU-adapted vLLM, with setup and B70 platform
components (`https://github.com/intel/llm-scaler/blob/main/vllm/README.md#L1-L27`,
`https://github.com/intel/llm-scaler/blob/main/vllm/README.md#L36-L57`).

Why not immediate: local Gemma vLLM INT8/FP8 was far behind llama.cpp
(`README.md:212`). Treat new llm-scaler images as Qwen/service A/B candidates,
not as the main Gemma Q8 record path unless a same-identity Gemma test surprises.

## Things Not Yet Tried Or Not Fully Tried

| Idea | Priority | Why |
| --- | --- | --- |
| Exact verifier LM-head kernel redesign | High but not quick | Directly targets top profile node and preserves exactness only if it beats both regular Q8 matmul+argmax and the already-slower `ggml_mul_mat_argmax` path |
| Graph-level DFlash KV injection/per-round fixed shape | Medium | Upstream discussion identifies this as needed for DFlash graph reuse |
| DeepSpec DSpark algorithm mining | Medium | Useful design ideas, but no Gemma26 checkpoint and likely training-heavy |
| Latest Intel llm-scaler image A/B on Qwen and maybe Gemma | Medium-low for Gemma, medium for Qwen | Fresh B70 platform updates may help vLLM but prior Gemma vLLM path was slow |
| TurboQuant 4bit-nc for long-context capacity | Low for strict speed, medium for long context | Useful under KV memory pressure, not for current 8K single-session speed |
| PMZFX/Hal B70 repo cross-checks | Low-medium | Good operator and upstream-patch references, but many recommendations conflict with this local Gemma identity |

## Likely Not Worth Trying, And Why

| Idea | Why not |
| --- | --- |
| More `p_min`/`n_min` micro-sweeps | Tight sweeps already underperformed; without new confidence scoring they mainly measure variance (`research-plan.md:97-104`) |
| More blind MTP depth | Strict `n_max=4` and direct-unroll 8/9/10/12 lost hard (`research-plan.md:167-177`, `research-plan.md:545-555`) |
| Direct-unroll confidence/gap tail trim | Implemented and screened via `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES=1` / `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS`; strict 128-token highs did not survive full512 and the score path adds overhead (`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md:2040-2167`) |
| EAGLE-3 Gemma4 speculator | Local Q4/Q8 drafts exist and graph-off liveness works, but graph-off was only `72.651 tok/s`; graph-on crashes at `OP MUL_MAT`. Needs a dedicated graph-integration branch before another record attempt (`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md:1783-1830`) |
| DFlash PR 22105 branch | Local BF16 DFlash GGUF exists and the converted server loads, but local SYCL runtime was far too slow: early eval was `0.70-4.01 tok/s` and DFlash generation cost was about `140 ms/call`. Treat as infrastructure research only until draft generation and KV/graph injection are redesigned (`patches/gemma4-26b-a4b-q8-b70/20260628T2127-dflash-pr22105-gemma4-vocab-negative.md`) |
| Alternate MTP drafts | Strict higher-precision drafts and the Q2_K draft all lost, and the lane is verifier-bound (`research-plan.md:1215-1223`) |
| Host `h_nextn` copy trimming | Measured copy time is tiny and full512 was below record (`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T1319-hnextn-cacheguard-negative.md:50-66`, `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T1319-hnextn-cacheguard-negative.md:94-107`) |
| Q8 reorder pair/direct/top8/grouped variants | Strict tests show register/scatter/addressing overhead dominates unless a new kernel profile says otherwise (`research-plan.md:106-139`) |
| Raw verifier argmax/softcap shortcut | Exact but still pays full LM-head projection, so it did not confirm (`research-plan.md:141-152`) |
| Candidate-only verifier scoring | Not strict-safe: another vocab token can beat the drafted ID, and the bonus row still needs the target greedy token. A valid design must compute or prove the full-vocab maximum. |
| Runtime copy/allocation/env churn | Recent runtime flags all lost and profiles do not show this as the bottleneck (`research-plan.md:201-210`) |
| Frequency floor as a record mechanism | Produced `100+` screens but not reliable confirmations (`research-plan.md:67-74`) |
| N-gram/history acceleration for LocalMaxxing | Invalid for fresh strict records, despite huge warmed numbers (`README.md:68-73`, `README.md:213-215`) |
| TurboQuant for this strict 8K speed lane | vLLM's own study recommends FP8 KV as default and says practical TurboQuant trades extra capacity for latency/throughput cost; local TurboQuant was already slower in other lanes (`https://vllm.ai/blog/2026-05-11-turboquant`, reviewed page lines 36-60) |
| Generic NVIDIA/Hopper/Blackwell FlashAttention tips | Mostly CUDA/Hopper-specific and not directly portable to B70 SYCL/Level Zero |

## Grok Notes Triage

### DFlash

Status: real and interesting, but Grok overstates immediate ease on B70.

Confirmed:

- DFlash is real: the repo describes a lightweight block diffusion draft model
  for speculative decoding (`https://github.com/z-lab/dflash/blob/main/README.md#L1-L5`).
- The DFlash repo lists a Gemma 4 26B-A4B draft
  (`https://github.com/z-lab/dflash/blob/main/README.md#L10-L21`).
- It says vLLM core DFlash support exists, but Gemma4 needs a temporary vLLM
  build/PR branch (`https://github.com/z-lab/dflash/blob/main/README.md#L51-L65`).
- llama.cpp PR `#22105` is merged on 2026-06-28 and adds
  `--spec-type draft-dflash` with an example command
  (`https://github.com/ggml-org/llama.cpp/pull/22105`, reviewed page lines
  178-188 and 269-279).

Relevant mechanism:

DFlash drafts a whole block in one forward pass. vLLM speculator docs describe
non-causal attention over verifier hidden states and mask token embeddings,
then target verification of blocks and accepting the longest valid prefix
(`https://docs.vllm.ai/projects/speculators/en/latest/user_guide/algorithms/dflash/`,
reviewed page lines 185-198).

B70/Gemma implication:

Worth trying on a clean branch, but only after accepting it as a porting task.
The active local source does not yet expose `draft-dflash`, and DFlash's KV
injection/non-causal attention path is exactly the kind of graph/metadata issue
that has hurt XPU speculation work before.

### vLLM Gemma4 DFlash

Status: real but not upstream-default for Gemma4 at the time reviewed.

Confirmed:

- PR `#41703` is specifically "Fix Gemma4 DFlash batched verification";
  it fixes rejected-token handling, masks rejected context slots, and prevents
  invalid context slots from entering draft KV cache
  (`https://github.com/vllm-project/vllm/pull/41703`, reviewed page lines
  238-243).
- The PR reports B200 benchmarks where DFlash is faster than Gemma4 MTP on
  warmed HumanEval and MT-Bench, despite MTP having slightly higher acceptance
  (`https://github.com/vllm-project/vllm/pull/41703`, reviewed page lines
  244-259).
- The manual validation command uses `google/gemma-4-26B-A4B-it` with
  `z-lab/gemma-4-26B-A4B-it-DFlash`
  (`https://github.com/vllm-project/vllm/pull/41703`, reviewed page lines
  293-310).

B70/Gemma implication:

Good CUDA/B200 evidence, not a direct B70 result. For XPU/vLLM, reuse this as a
correctness checklist for rejected-token handling, shared KV, and attention
backend behavior. Do not assume Intel vLLM can run it fast without porting
Triton kernels and metadata handling.

### DSpark / DeepSpec

Status: real source, but Grok likely overstates Gemma 26B readiness.

Confirmed:

- DeepSpec exists and includes data preparation, draft implementations, training
  code, and evaluation scripts (`https://github.com/deepseek-ai/DeepSpec/blob/main/README.md#L1-L21`).
- It includes DSpark, DFlash, and Eagle3 algorithms
  (`https://github.com/deepseek-ai/DeepSpec/blob/main/README.md#L67-L69`).
- Released checkpoints cover Qwen3 4B/8B/14B and Gemma4 12B, not Gemma 4 26B
  A4B (`https://github.com/deepseek-ai/DeepSpec/blob/main/README.md#L53-L62`).
- Training/eval assumptions are heavy: default scripts assume 8 GPUs, and the
  target cache can be very large (`https://github.com/deepseek-ai/DeepSpec/blob/main/README.md#L27-L39`).

B70/Gemma implication:

Mine DSpark for confidence scheduling and semi-autoregressive design ideas.
Do not plan an immediate Gemma26 DSpark record attempt unless a compatible
checkpoint appears.

### TurboQuant

Status: real, but mostly a context-capacity tool for this repo, not a strict
speed-lane tool.

Confirmed:

- Google's writeup says TurboQuant targets KV-cache and vector-search
  compression via random rotation and QJL residual correction
  (`https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/`,
  reviewed page lines 126-137).
- vLLM's May 2026 study says FP8 KV remains the best default; `turboquant_4bit_nc`
  may help under KV memory pressure but trades capacity for latency/throughput
  cost; lower-bit variants show meaningful accuracy drops
  (`https://vllm.ai/blog/2026-05-11-turboquant`, reviewed page lines 36-60).
- vLLM's TurboQuant docs describe Hadamard rotation plus Lloyd-Max scalar
  quantization, note QJL is omitted in that implementation, and list presets
  such as `turboquant_4bit_nc`
  (`https://docs.vllm.ai/en/latest/api/vllm/model_executor/layers/quantization/turboquant/`,
  reviewed page lines 2516-2549).

B70/Gemma implication:

Not a path to beat `98.340` on the 8K strict single-session lane. Revisit only
for long-context or high-concurrency KV pressure, and label quality separately.

### Intel Arc Pro B70 Repos

Status: useful context, not directly substitutable for this strict lane.

Confirmed:

- Intel `llm-scaler` is B60/B70-focused and has June 2026 vLLM images with FP8
  KV and Qwen3.5/3.6 fixes (`https://github.com/intel/llm-scaler/blob/main/README.md#L1-L15`).
- PMZFX B70 benchmarks provide real B70 llama.cpp/vLLM data; they report Gemma 4
  26B-A4B Q4_K_M at `52.6` tg128 on one B70, but this is Q4_K_M, not this Q8
  target lane (`https://github.com/PMZFX/intel-arc-pro-b70-benchmarks/blob/master/README.md#L19-L37`).
- PMZFX says SYCL beats Vulkan for decode and MoE architectures are a B70 sweet
  spot (`https://github.com/PMZFX/intel-arc-pro-b70-benchmarks/blob/master/README.md#L50-L59`).
- Hal9000AIML's kit is a B70 llama.cpp tuning kit with cherry-picks and runtime
  rules, but several recommendations are older or conflict with this local
  record identity, such as generic `GGML_SYCL_DISABLE_OPT=1` for MoE
  (`https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes/blob/main/README.md#L1-L27`,
  `https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes/blob/main/README.md#L94-L108`).

B70/Gemma implication:

Use these repos as sanity checks for driver/runtime/build regressions and
upstream PR mining, not as direct replacement recipes. The current local record
requires `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, VDR2 Q8 reorder, and the
specific MTP/verifier flags in `reproduce.md:159-190`.

### Generic Recent Methods From Grok

Mostly noise for the current record lane:

- FlashAttention-3/4, FlashDecoding++, Blackwell/Hopper FP8/NVFP4: valuable in
  CUDA stacks, but not directly actionable on Intel B70 SYCL without a port.
- QuickSilver dynamic halting/KV skipping/context fusion: interesting paper
  direction, but likely violates or complicates exact Q8 target semantics unless
  every shortcut is quality-gated. It is lower priority than exact verifier
  reductions.
- SSD/Saguaro, SPD, branch-parallel speculative decoding: algorithmically
  relevant, but current codebase leverage is low. Mine only if building a new
  speculation engine rather than tuning MTP.
- "Set `-b 2048/4096`, `--flash-attn auto`, expect 60-80 tok/s": misleading for
  this lane. Current record uses `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
  `FLASH_ATTN=off`, f16 KV, and strict cold-suite validation
  (`reproduce.md:159-190`).

## Source Index

Local:

- `results/gemma4-26b-a4b-q8-b70/README.md`
- `results/gemma4-26b-a4b-q8-b70/research-plan.md`
- `results/gemma4-26b-a4b-q8-b70/reproduce.md`
- `results/gemma4-26b-a4b-q8-b70/bugs-failed-paths.md`
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T1319-hnextn-cacheguard-negative.md`
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md`
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1657-vmm-ubatch-followups.md`
- `/home/steve/qwen36-results-main/AGENT_HANDOFF.md`
- `/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp`
- `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/llama-context.cpp`
- `/home/steve/llm-optimizations/suggestions/findings/qwen35-b70-options.md:399-424`
- `/home/steve/llm-optimizations/suggestions/findings/vllm-upstream-audit-2026-06-20.md:298-328`

External:

- `https://github.com/z-lab/dflash`
- `https://arxiv.org/abs/2602.06036`
- `https://github.com/ggml-org/llama.cpp/pull/22105`
- `https://github.com/ggml-org/llama.cpp/discussions/24904`
- `https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md`
- `https://github.com/ggml-org/llama.cpp/issues/10378`
- `https://github.com/ggml-org/llama.cpp/discussions/18074`
- `https://github.com/ggml-org/llama.cpp/discussions/20969`
- `https://github.com/vllm-project/vllm/pull/41703`
- `https://docs.vllm.ai/en/stable/configuration/optimization/`
- `https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/`
- `https://docs.vllm.ai/en/latest/features/quantization/quantized_kvcache/`
- `https://docs.vllm.ai/en/latest/features/disagg_prefill/`
- `https://docs.vllm.ai/en/latest/examples/disaggregated/lmcache/`
- `https://docs.vllm.ai/projects/speculators/en/latest/user_guide/algorithms/dflash/`
- `https://github.com/deepseek-ai/DeepSpec`
- `https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/`
- `https://vllm.ai/blog/2026-05-11-turboquant`
- `https://github.com/intel/llm-scaler`
- `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`
- `https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes`

## 2026-06-29 Update: Late Head-Only Bonus

Tested the exact late head-only bonus verifier path:

- patch/result ledger:
  `patches/gemma4-26b-a4b-q8-b70/20260629-late-head-bonus-experiment.md`;
- strict128 run:
  `data/gemma4-q8-gpu0-lateheadbonus-strict128-20260629T024814Z/summary.json`;
- validity: canary 128/128, realistic final gate passed, `cached_tokens=0`;
- metric: **96.91021564463527 tok/s** median tokens 1-100 after TTFT.

Do not promote. This is below both the then-current valid
`98.34046474459183 tok/s` record and the newer `121.41411987308553 tok/s`
record. The standalone one-row bonus head is probably correct but not cheap:
the extra graph/scheduler work offsets the saved verifier output row. If this
idea is revisited, it needs to be fused into the existing verifier/output path,
not launched as a separate head graph.
