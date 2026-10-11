# Model Effort Index

This page indexes measured outcomes, research packets, and remaining gaps so a
new reader can switch models without rereading every historical note.
Navigation reviewed **2026-10-10**. [CURRENT.md](../CURRENT.md) alone owns active
work, host admission and protected paths. A completed campaign or rejected lever
does not mean a model lane is finished; dated entries below describe recorded
evidence, not a running service or an instruction to launch one.

The lab has a four-B70 host with about 128 GiB host RAM and a two-B70 host
with 15 GiB. Treat their topology and memory limits as different experimental
identities; use [AGENTS.md](../AGENTS.md#host-facts) for host details.

## Lane Entry Points And Evidence Status

This inventory separates the maintained entry points from the older campaign
summaries below. The linked packets own exact numbers and qualification limits.

| Lane | Start here | Evidence status |
| --- | --- | --- |
| Own Intel Xe runtimes | [objective](own-xpu-runtime-objective.md), [packets](../experiments/own-xpu-runtime/README.md) | CPU preparation; native execution is a separate admission gate |
| LTX 2.5 | [145-frame recipe](../repro/ltx25-continuation-stream-b70-145f-20261010/README.md) | Lab replay; early-window timing is separate from sustained delivery and later packets |
| MiniMax-H3 | [result](../results/minimax-h3-b70/README.md), [recipe](../repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) | Owner-selected fitted denoiser; exact scheduling result against its own reference; rebuild gaps remain |
| Qwen3.8 Flash-Next FP8 | [result](../results/qwen38-flash-next-fp8-b70/README.md), [reopen work](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/README.md) | September record retained; October fault/loading investigation is separate |
| Qwen3.8 27B FP8 | [one-card recipe](../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md), [two-card recipe](../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) | Official FP8 identity; context and many-user profiles have separate evidence |
| Qwen3.5 4B / 9B | [4B handoff](../experiments/qwen35-4b-b70/HANDOFF.md), [9B W4A16 recipe](../repro/qwen35-9b-w4a16-b70/README.md), [9B FP8 recipe](../repro/qwen35-9b-fp8-b70/README.md) | Qualified single-request profiles; concurrency, runtime revisions and FP8 remain separately scoped |
| Qwen3.6 family | [family map](qwen36-research-map.md) | Q8 TP2 record, one-card Q8, INT4/MTP, Q4, FP8 and 35B evidence are distinct |
| Qwen3.8 27B GGUF / AutoRound INT4 | [model board](../README.md#qwen38-27b-model-board), [INT4 recipe](../repro/qwen38-27b-autoround-int4-b70/README.md) | August discovery notes below are historical; use maintained recipes for later qualification |
| Muse-Glimmer 30B | [result](../results/muse-glimmer-30b-q8-woq-b70/README.md) | Retained Q8/WOQ campaign result; not a BF16/lossless claim |
| Laguna S 2.1 | [result](../results/laguna-s-2.1-int4-b70/README.md), [125 tok/s recipe](../repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md) | Qualified BF16-KV record; July 26 recipe is an earlier milestone |
| Gemma 4 26B A4B | [result](../results/gemma4-26b-a4b-q8-b70/README.md), [reconstruction](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) | Historical cold-suite result and separate service/prefill work; source reconstruction is not binary-exact replay |
| Gemma 4 12B | [experiment](../experiments/gemma4-12b-int4-autoround-vllm/README.md) | Retained c8 service experiment; c10 research and c12+ failures remain separate |
| MiniMax M2.7 | [recipe](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md) | Historical deployment/optimization baseline; no resident-service claim |
| DeepSeek V4 Flash K160 | [result](../results/deepseek-v4-flash-k160-b70/README.md) | Retained experimental pruned-artifact frontier; not official true REAP |

For packaged models beyond these detailed campaign summaries, use the
[package directory](../packages/README.md); for first-pass baselines use the
[performance index](../results/scoreboard.md). A package entry does not confer
clean-host certification.

## How To Add A Model Effort

For the full optimization lifecycle, read
[`model-optimization-guide.md`](model-optimization-guide.md) before creating a
new lane.

Create or update the smallest set of files that makes the lane understandable:

1. `results/<model>-<hardware>/README.md` for promoted or closed-out outcomes.
2. `results/<model>-<hardware>/validity-gates.md` for what counts as a record.
3. `results/<model>-<hardware>/reproduce.md` for the best known commands.
4. `results/<model>-<hardware>/bugs-failed-paths.md` for invalid fast lanes and
   failure signatures.
5. `notes/YYYY-MM-DD-<model>-...md` for chronological experiment notes.
6. `patches/<model>-...patch` for source or config deltas worth preserving.
7. `data/<model>-...json` for compact structured result evidence.

Do not move old files just to make the tree look tidy. Add indexes and links
unless a file is clearly misplaced and no one is likely to reference the old
path.

<a id="active--recent-efforts"></a>

## Recorded Efforts And Remaining Gaps

### Qwen3.8 Flash-Next FP8, four B70s — campaign closed September 13

The September A340–A394 campaign has a retained qualified result and separately
scoped depth measurements in the [result packet](../results/qwen38-flash-next-fp8-b70/README.md)
and [recipe](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md).
Its [September closeout](../results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md)
is historical: October [reopen work](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/README.md)
examines loading and exit faults and does not supersede that performance record.
Check CURRENT before using any prepared command.

### Qwen3.5 4B And 9B On One Or Two B70s

Main entries:

- [9B W4A16 recipe](../repro/qwen35-9b-w4a16-b70/README.md) and
  [container packet](../packages/qwen35-9b-w4a16-b70/README.md)
- [9B FP8 recipe](../repro/qwen35-9b-fp8-b70/README.md) and
  [container packet](../packages/qwen35-9b-fp8-b70/README.md)
- [4B W4A16 recipe](../repro/qwen35-4b-w4a16-b70/README.md) and
  [container packet](../packages/qwen35-4b-w4a16-b70/README.md)
- [experiment archive](../experiments/qwen35-9b-b70/) and
  [4B archive](../experiments/qwen35-4b-b70/)

The September 7–13 campaigns produced several different operating profiles.
Use the recipes above for the qualified R294b single-user shortlist records,
R304 replay, two-card results, and context ladders. The
[4B shortlist evidence](../experiments/qwen35-4b-b70/data/qwen35-4b-w4a16-20260912-slu67k-strict-result.json)
and [9B shortlist evidence](../experiments/qwen35-9b-b70/data/qwen35-9b-w4a16-20260912-slu67k-strict-result.json)
retain two fresh MTP3 servers and all four G1/G2/G3 comparisons at 12/12;
these one-card, class-balanced cold-suite records do not qualify arbitrary
concurrent serving.

The useful conclusions, in their final measured scope:

- **Single-operator fixes did not remove the concurrent identity gap.** The
  early serial-norm/row-wise-allreduce trend was not established; the powered
  fragile-prompt comparison was 23 versus 24 divergent requests. Later
  [TP1 norm](../experiments/qwen35-9b-b70/notes/2026-09-09-the-norm-is-not-the-mechanism.md)
  and [capture-ceiling](../experiments/qwen35-9b-b70/notes/2026-09-09-capture-fallback-is-not-the-mechanism.md)
  tests also failed to remove it. Their old “try this next” paragraphs are
  chronology, not the present queue.
- **Admission and workload matter.** The [4B handoff](../experiments/qwen35-4b-b70/HANDOFF.md)
  records repeated exact MTP0 ladders with 5 ms staggered admission, including
  two-card runs. The [9B R293 result](../experiments/qwen35-9b-b70/notes/2026-09-11-r293-on-the-9b.md)
  independently measured its staggered c64 profile at 1280/1280 exact. These
  bounded suites do not establish exactness for arbitrary arrivals, prompts or
  speculation. The [classification retrospective](../experiments/qwen35-4b-b70/notes/2026-09-09-divergence-classification-retrospective.md)
  corrects the mistaken interpretation of ordinary tie forks as inserted tokens.
- **The FP16 projection chunk was a throughput cost.** R293's verified
  class-consistent padding/splitting improved the measured many-user profiles
  on [4B](../experiments/qwen35-4b-b70/notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md)
  and [9B](../experiments/qwen35-9b-b70/notes/2026-09-11-r293-on-the-9b.md).
  Its single-user cost means it is a separate profile, not the shortlist
  record default. Older c16 scaling limits belong to their original runtime.
- **R308 repaired a separate request-lifecycle defect.** Accepted-state metadata
  is retained across pause/removal/re-add. The [final qualification](../experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md)
  passed both models' 60/60 MTP0 boundary checks, 52/52 on each fresh MTP3
  server, and all strict comparisons 12/12. Scope is TP1, one active request,
  fixed depth 3, capacities 256 for boundaries and 1024 for strict tests.
  Concurrent speculation, TP2, dynamic depth, forced preemption and a new 32K
  R308 profile remain unqualified. R308's timings are supporting measurements,
  not a new speed headline.

Remaining work is scoped by those gaps and CURRENT's host admission: independent
clean-host replay, further qualification of request scheduling, and separately
registered FP8 arithmetic work. The
[FP8 row-invariance specification](../experiments/qwen35-9b-b70/notes/2026-09-07-per-channel-fp8-row-invariance-specification.md)
is a proposal, not a demonstrated fix. Preserve the
[4B FP8 repeat failures](../experiments/qwen35-4b-b70/notes/2026-09-07-qwen35-4b-fp8-not-repeat-exact.md)
as a separate model/runtime result. No Qwen3.5 lane is declared finished here.

### Muse-Glimmer-30B Q8/WOQ On Four B70s

Main entries:

- [promoted result](../results/muse-glimmer-30b-q8-woq-b70/README.md)
- [standalone repro](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
- [complete source snapshots](../patches/muse-glimmer-30b-b70/README.md)
- [structured record](../data/muse-q8-woq-argmax-century-20260813.json)
- [experiment archive](../experiments/muse-glimmer-30b-b70/README.md)

Campaign result retained from 2026-08-13. The original BF16/lossless century
objective was not reached. The operator-approved no-training UD-Q8_K_XL
successor measured two independent canonical means of `100.088` and `100.649
tok/s`; the frozen 15-prompt conventional first-100 median was `161.900 tok/s`
with p10 `108.574` and 15/15 cache-zero. It is target-verified but not BF16,
lossless, universally token-exact, or uniformly above 100. LocalMaxxing
approved it as
[`cmss8515c00n0ms01n3begqgg`](https://www.localmaxxing.com/en/runs/cmss8515c00n0ms01n3begqgg).
Reopen only with a new objective/preregistration.

### Qwen3.6 Family Navigation

Use the [Qwen3.6 family research map](qwen36-research-map.md) before selecting a
Qwen lane. It keeps the current 27B Q8 TP2 record, one-card Q8 baseline,
AutoRound INT4/MTP records, Q4/DFlash and intrinsic-MTP work, native FP8, and
35B Quark archive separate while providing one read order. These identities
must not be merged into a family-level speed claim.

### Qwen3.8 27B On Two ASRock B70s

Main entries:

- [Qwen3.8 model board](../README.md#qwen38-27b-model-board)
- [Q8_0 quality-conservative TP2 reproduction](../repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
- [Q4_K_M target-only TP2 reproduction](../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K_M fusion patch](../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [target-only optimization ledger](../experiments/qwen38-27b-b70/notes/2026-08-15-target-only-pass2.md)
- [c2 cache-row fusion result](../experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md)
- [distributed greedy argmax result](../experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md)
- [archived contributed GPTQ INT4/MTP route](../community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md)
- [AutoRound INT4/MTP3 lane and replay gates](../repro/qwen38-27b-autoround-int4-b70/README.md)

Historical snapshot, 2026-08-27: The target-only GGUF records remain Q4_K_M
TP2 at `49.717503 tok/s` conventional (`50.219700` historical helper) and Q8_0
TP2 at `36.772932 tok/s`. The official FP8 route has moved beyond its original
`21.708532 tok/s` graph baseline: the block-W8A16 overlay directly measures
`31.489587 tok/s` at an exact 32K prompt and target-only/MTP0 reaches
`1,112.570323 tok/s` aggregate at c128 under its scoped short-context gate.
The dynamic-MTP single-user headline is pending: `58.391033` used a 128-token
cap and `146.814418` used a selected high-acceptance fixture, so both are
diagnostic only. MTP9
and the subsequent latch/c2 threshold treatments are retained as measured
negatives; no diagnostic treatment is spliced into the package headline.

The strict-greedy distributed-argmax candidate was token-for-token exact
across a position-balanced 48-request replay, but it moved the primary metric
by `-0.057%` and worsened TTFT by `+8.311%`. It is preserved as a closed
mechanism result, not enabled in the reproduction package. The replay also
clarified that the earlier accepted Q8 speed capture was reasoning-enabled,
whereas the current service launcher and quality oracle use reasoning off.

The separate contributed one-card GPTQ INT4 vLLM route is locally B70-tested at 8K.
Native FP16 KV reached `34.160467 tok/s` target-only and `87.605425` MTP4,
faster than the corresponding FP8-KV rows. MTP matched its target and the
loaded draft parameters were verified FP16, but the GPTQ target failed a
deterministic code-result canary passed by Q8/Q4. It remains an experimental
performance lane, not the no-quality-loss deployment. The 131K boundary patch,
power, exact contributor prompt, and broad quality claims remain open.
The exact public model, container, runtime flags, copied benchmark assets, two
patches, safe launcher, reported payload, source hashes, and audit caveats are
captured in the linked packet.

The separate `devan-carlin/Qwen3.8-27B-int4-AutoRound` lane now has an honest
margin-free MTP5 working anchor at `101.170 tok/s` across all 25 prompts and
`92.851 tok/s` on selection-12. It is not promoted: three pairwise comparisons
agree on only 21–22/25 prompts. A fresh target-only A/B now agrees on 24/25;
post-recovery TP2 MTP5 remains 21/25, and a sealed-cache TP1 pair agrees on
only 2/4. The published `101.922`/`100.497` rows used an output-changing margin
and are withdrawal-recommended.

### Qwen3.6 27B Q8_0 Target-Only On Two ASRock B70s

Main entries:

- [promoted lab result](../results/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [standalone reproduction](../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [complete lab source patch](../patches/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [validated community/fork packet](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md)
- [status and provenance boundary](../community/mndodd-qwen36-27b-llamacpp-sycl/STATUS.md)
- [initial compatibility patch](../community/mndodd-qwen36-27b-llamacpp-sycl/patches/0001-asrock-lab-lowram-dnnless-tp2.patch)
- [model board](../README.md#qwen36-27b-model-board)

The retained **2026-08-15 target-only TP2 record** is **36.604128 tok/s**
conventional (99 intervals); its historical compatibility value is
36.973866. The [structured summary](../data/qwen36-q8-tp2-asrock-b70-20260814/summary.json)
and [result packet](../results/qwen36-27b-q8-tp2-asrock-b70/README.md) own the
full metrics and progression. Scope: Q8_0 target, F16 KV, equal two-card split,
12 unique cold prompts with 512-token outputs, 12/12 complete hashes exact to
the accepted control, all cache counts zero; no MTP or DFlash. The recipe is
lab replay, not clean-host certification.

Pass 1 promoted no gain. Pass 2 and the August 15 two-chain DP4A change advanced
the record; older 35.699225 / 35.964046 / 36.347290 summaries are intermediate
milestones. Contributor mndodd's source base and matched baseline remain
credited in the packet. For the next materially new exact critical-path idea,
read the [handoff](../results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md) and retain
its rejected-kernel and fault boundaries. Do not repeat the unsafe TP2 profiler
or root-both remote-write prototype.

### Laguna S 2.1 INT4 On Four B70s

Main entries:

- [record resume](../experiments/laguna-s-2.1-xpu-b70/RESUME.md)
- [record note](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md)
- [campaign transfer ledger](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md)
- [KV-cache precision decision](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-kv-cache-precision-decision.md)
- [source snapshots](../patches/laguna-s-2.1-xpu-b70/README.md)
- [qualified result packet](../results/laguna-s-2.1-int4-b70/README.md)
- [standalone repro](../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md)
- [metric correction](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md)

The [qualified result packet](../results/laguna-s-2.1-int4-b70/README.md)
and [July 31 reproduction](../repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md)
own the later 125.461973 conventional record. The July 26 102.971436 legacy /
101.941721 conventional result linked above is an earlier milestone, not the
latest record or an unmet current target. Both preserve their exact source,
metric and quality identities; campaign closeouts do not declare the lane
finished or identify a live service.

The record uses BF16 KV and target-verified DFlash. Poolside's checkpoint also
ships calibrated FP8 KV, but the earlier B70 A/B changed outputs and slowed
short decode despite higher capacity. Keep that research separately labeled;
it does not replace the BF16 exact-output record.

### Qwen3.6 27B Q8_0 GGUF On One B70

Main entry:

- [adaptive strategy](../experiments/qwen36-27b-q8-gguf-b70/STRATEGY.md)
- [experiment lane](../experiments/qwen36-27b-q8-gguf-b70/README.md)

Status: validated baseline lane as of 2026-08-08. The exact target-only
Unsloth Q8_0 artifact is pinned and verified on USB for a text-only, target-only,
one-B70 baseline with a 32K ceiling. DNN-off passed 12/12 exact at `15.550257
tok/s` median and the full 32K F16-KV retrieval ladder at `28,372 MiB` loaded;
no full-512 throughput result is promoted yet. The historically recorded Q8_0 family result of `15.275 tok/s`
at p512/n128 is only a trend anchor because its raw evidence, revision, and
binary were not retained. F16 KV is validated; Q8 KV is a separate fallback
quality identity and was unnecessary for that 32K ceiling. Subsequent c2/32K
and MTP experiments have their own outcomes in the
[lane README](../experiments/qwen36-27b-q8-gguf-b70/README.md); the original
baseline's proposed next steps do not replace those results.

### Qwen3.6 27B INT4 AutoRound On B70

Main entries:

- [result packet](../results/qwen36-27b-autoround-int4-b70/README.md)
- [handoff](../results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [exact 95.385 repro](../repro/qwen36-27b-autoround-int4-b70/README.md)
- [2026-08-15 independent validation](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md)
- [private source bundle and patches](../patches/qwen36-27b-autoround-int4-b70/record-20260711/README.md)
- [experiment lane](../experiments/qwen36-27b-autoround-int4-b70/README.md)

**August campaign closed 2026-08-18.** The retained `95.385` record stands; nothing beat it
like-for-like. Closing evidence:

- [determinism/speed closeout](../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md)
- [closeout source packet](../patches/qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/README.md)
- [determinism reproduction](../repro/qwen36-27b-autoround-int4-b70-determinism-20260818/README.md)

Succeeded by the Qwen3.8 27B INT4 AutoRound lane below.

### Qwen3.8 27B INT4 AutoRound On B70

Opened 2026-08-18. `devan-carlin/Qwen3.8-27B-int4-AutoRound`, vLLM/XPU TP2 with
native MTP speculative decoding. Its tensor architecture is compatible with the
Qwen3.6 INT4 lane, so the pinned source stack runs without a model-specific
code change. The new weights still require independent quality, determinism,
and performance validation. The August 18 margin-free MTP5 anchor was: `101.170 tok/s`
on the 25-prompt suite (`92.851` selection-12), with only 21–22/25 pairwise
repeatability. At that point a valid target-only quality oracle existed, but its A/B is
24/25 and the sealed-cache TP1 MTP5 control is only 2/4. This is research
evidence, not a record.

Distinct from the llama.cpp Q4_K_M target-only Qwen3.8 lane: different runtime,
quantization, and speculation class. Do not merge their rows.

Main entries:

- [lane setup and model manifest](../repro/qwen38-27b-autoround-int4-b70/README.md)
- [baseline evidence](../data/qwen38-27b-autoround-int4-baseline-20260818.json)
- [post-recovery TP1 result](../experiments/qwen38-27b-b70/notes/2026-08-20-postrecovery-marginfree-tp1-runtime-nondeterminism.md)
- [current source/host queue](../repro/qwen38-27b-autoround-int4-b70/REFERENCE-HOST-HANDOFF.md)

This is the August discovery history. The token-225 trace proposal is
superseded as a navigation entry by the maintained
[INT4 recipe](../repro/qwen38-27b-autoround-int4-b70/README.md) and
[performance index](../results/scoreboard.md), which include later qualified
profiles. Keep the August failures and their exact source identities for
localization; do not treat this old queue as current launch instructions.

### Gemma 4 26B A4B Q8 / INT8 On B70

Main entries:

- [handoff / production bookmark](../results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [production service recipe](../results/gemma4-26b-a4b-q8-b70/production-service.md)
- [result packet](../results/gemma4-26b-a4b-q8-b70/README.md)
- [125 tok/s strict repro](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
- [research plan](../results/gemma4-26b-a4b-q8-b70/research-plan.md)
- [reliability protocol](../results/gemma4-26b-a4b-q8-b70/reliability-protocol.md)
- [VDR2 selected-down record note](../results/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-record.md)

Recorded result and service/prefill research, not a live-service assertion.
Use the linked research plan and reliability protocol to select a new
verifier, router, speculation or prefill hypothesis without repeating the
rejected small flag sweeps.

Best strict fresh-response result:

- llama.cpp `c926ad098`, one B70, UD-Q8_K_XL target/verifier, Q4_0 MTP draft
  verified by the Q8 target;
- fixed realistic cold prompt suite, `cached_tokens=0`, no cache/history reuse;
- reordered-Q8 VDR2, F16 p021 small-ncols, bulk sampled-ID verifier host read,
  VDR2 selected-down fused weighted-sum, final post-norm residual fusion,
  FA-on 32K/VMM;
- `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT, p10 `103.83610041293263`, mean
  `122.47435471668817`;
- LocalMaxxing `cmr1u77na01k2ld01kalwzs1e`.

Important caveats:

- same-recipe repeatability is noisy: `2.324%` run-median CV and `4.409%` p90
  pairwise absolute run-median delta; do not promote `+1-4%` single-run spikes;
- use paired same-window A/B analysis with
  `scripts/analyze-gemma-realistic-ab.py` for close changes;
- older filled-long `104+` / `176+ tok/s` rows are diagnostic/pre-final-gate
  only;
- draftless `ngram-mod` `245-280 tok/s` rows are warmed/history artifacts, not
  real fresh-response records.

Service/prefill status: UB2048 is the validated long-context candidate for the
service lane. It passed fixed JSON-retrieval gates through `22730` actual
prompt tokens and the corrected `30400` actual-token boundary case with
`cached_tokens=0`, exact outputs, and no paired short-suite decode regression.
It did not beat the short-decode record, so keep UB1024 for short-record
reproduction.

Recent exhausted neighborhoods include adaptive MTP depth caps, tight `p_min`
repeats, grouped reordered-Q8 duplicate-expert MoE, direct VDR2, top-8
reordered-Q8 slot blocking, Q4_K_M/Q5_K_M/Q6_K/Q8_0 draft swaps, fused verifier
argmax, rowpack, non-direct top-k confidence gating, regular-Q8 top1
epilogue/partial reductions, direct BF16 routed gate/up+GEGLU, attention
post-norm fusion, and per-layer post-norm fusion.

### Gemma 4 12B IT INT4 AutoRound

Main entry:

- [experiment packet](../experiments/gemma4-12b-int4-autoround-vllm/README.md)

Recorded service experiment: c8 was the accepted profile. c10 is research-only;
c12+ hit boundary failures.

### MiniMax M2.7 INT4 AutoRound

Main entries:

- [fresh Ubuntu 24 deployable repro](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md)
- [older strict speed repro](../repro/minimax-m27-b70-89tps-20260520/README.md)

Status: strong candidate to revisit when Gemma work stalls or when a
cross-model collective/graph-boundary idea appears. Strict speed lane is
`89.314195` output tok/s / `119.085594` total at p512/n1536; deployable 32K
endpoint baseline is about `83-84` output tok/s.

Future speed work should target hidden-state collective and graph-boundary
fusion, especially MoE-output allreduce plus epilogue or attention `o_proj`
allreduce plus residual/RMSNorm. Do not spend much time on generic env flag
sweeps.

### Qwen3.6 35B A3B Quark W8A8 INT8

Main entries:

- [result packet](../results/qwen36-35b-quark-int8-b70/README.md)
- [research map](qwen36-research-map.md)

Status: retained campaign reference; preserve every lesson for future work. No valid `>150 tok/s` path was found; best strict 4x baseline is
`93.55 tok/s`. The main carryover lesson is that graph/speculative speed paths
must pass full-scale canaries, not smoke tests.

### Qwen3.6 27B Q4_0 / FP8 Historical Lanes

Main entries:

- [FP8 vLLM/XPU result note](../results/fp8-vllm-xpu-qwen36-2026-05-04.md)
- older notes under `../notes/`

Status: the intensive Q4_0/DFlash SYCL campaign closed on 2026-07-13 at a strict
one-B70 record of `47.818818 tok/s`; the `100/200 tok/s` single-session goals
were not reached. Read the
[closure and transfer note](../notes/2026-07-13-qwen27-dflash-sycl-closure.md)
before using its kernel, speculation, graph, or packing artifacts. Reopen only
with one of the concrete scope changes listed there, not another flag sweep.
The separate UD-Q4_K_XL intrinsic-MTP lane's best valid p-min row is `31.480
tok/s`; its [result packet](../results/qwen36-27b-mtp-gguf-q4-b70/README.md)
retains the older LocalMaxxing MTP3 reference. The community native-FP8 TP2
Docker recipe was independently exercised at `30.171 tok/s` median decode on
a different prompt-length benchmark; keep it non-comparable to fixed-suite
rows and start from its [STATUS](../community/dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md).

### DeepSeek V4 Flash REAP/XPU On B70

Main entry:

- [closed result packet](../results/deepseek-v4-flash-k160-b70/README.md)
- [standalone 80.820 tok/s repro](../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md)
- [experiment packet](../experiments/deepseek-v4-flash-reap-xpu-b70/README.md)
- [controlling investment-gated plan](../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md)
- [historical lane handoff](../experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md)
- [frontier closeout](../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md)

Campaign frontier recorded on 2026-07-21. The best
verified one-session result is the experimental uniform-K160 target with
target-verified DSpark7: `80.820052 tok/s` strict high and `78.287226 tok/s`
three-suite median-of-medians on four B70s, with 36/36 cache-zero realistic
rows and 24/24 exact canaries. LocalMaxxing approved
`cmrquta9905w3lg013m5vxoqx`; no later verified endpoint exceeded it. Reopen
only for the closeout's 10-20M-token EAGLE/hybrid training condition or a new
device-execution mechanism. The public checkpoint remains hash-pruned with
unavailable calibration and must not be described as official true REAP.

Historical rejected fit/support evidence for the oversized Intel AutoRound
artifact remains at
[the original AutoRound experiment packet](../experiments/deepseek-v4-flash-autoround-vllm/README.md).

## Cross-Model Lessons

For evidence-linked strategies and their transfer boundaries, start with
[Cross-Model Patterns Worth Reusing](research-workflow-playbook.md#cross-model-patterns-worth-reusing).

- Lock benchmark identity before interpreting speed. Missing graph mode or a
  changed launcher can create false regressions or false wins.
- Treat fast speculative paths as invalid until canaries pass at scale. The
  Qwen36 lane had multiple 75-199 tok/s "wins" that failed quality or were
  synthetic.
- Preserve negative patches and logs. MiniMax improved because dead ends were
  visible; Qwen36 became hard when failed experiments were not summarized
  quickly.
- Prefer model-specific result packets over large mixed history dumps. Curated
  packets are easier to review and reuse than monolithic experiment ledgers.
- Keep LocalMaxxing payloads and responses in `data/`, but keep API keys outside
  Git as documented in [localmaxxing.md](localmaxxing.md).
- For one-replica-per-GPU work, prefer four independent servers and four
  disjoint experiments before trying tensor parallelism. This is especially
  relevant to Gemma 4 26B A4B, where the goal is to avoid PCIe collectives.
- LocalMaxxing headline submissions must come from the fixed realistic
  cold-response suite. Synthetic filled-long, repeated, warmed, cached,
  n-gram/history, or continuation-learned scores can guide optimization but
  must remain diagnostic unless revalidated by that gate.
- Treat weight, activation, router, draft, and KV precision as separate identity
  fields. A lower-byte KV cache is a capacity candidate until its actual
  attention path, long-context speed, and separately labeled quality gates pass.
- Require runtime execution proof for experimental selectors, assert graph and
  collective work counts, and never infer device health from a probe that did
  not prove it entered.
