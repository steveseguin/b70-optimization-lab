# Model Effort Index

This page is the cross-model work queue and archive. It is meant to help the
next agent switch models without rereading every historical note.

Hardware planning note: the measuring host has four Intel B70 32 GB cards and
about 125 GiB system RAM. A second host has two ASRock B70 32 GB cards but only
about 15 GiB system RAM and is restricted to source/build/op-level work for the
current Qwen3.8 AutoRound lane. Higher-VRAM Intel hardware would make larger
future efforts, such as GLM 5.2 and DeepSeek Flash-class models, much more
realistic to validate under the same quality rules.

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

## Active / Recent Efforts

### Muse-Glimmer-30B Q8/WOQ On Four B70s

Main entries:

- [promoted result](../results/muse-glimmer-30b-q8-woq-b70/README.md)
- [standalone repro](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
- [complete source snapshots](../patches/muse-glimmer-30b-b70/README.md)
- [structured record](../data/muse-q8-woq-argmax-century-20260813.json)
- [experiment archive](../experiments/muse-glimmer-30b-b70/README.md)

Status: closed and banked 2026-08-13. The original BF16/lossless century
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

Status: active as of 2026-08-27. The target-only GGUF records remain Q4_K_M
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

Status: active target-only TP2 optimization as of 2026-08-14. The quality-cleared
endpoint best uses mndodd's pinned SYCL optimization fork plus the lab's full
exact collective, Q8 handoff, recurrent dispatch, and persistent-state-I/O
stack. It reaches **`35.964046 tok/s`** under conventional 99-interval
accounting or `36.327319 tok/s` under the historical helper. This is
`+15.918%` over the matched mndodd fork baseline (`31.025377` conventional).
All 12 cold completions are 512 tokens, cache-zero, and byte-exact against the
accepted pre-state-I/O control. Direct GDN state I/O added `+3.132%`; direct
convolution state I/O added another `+0.855%` in the final long suite, and the
recurrent RMS/gate/multiply/Q8 tail added `+0.219%` in pooled matched A/Bs.

The earlier one-card fork endpoint reached `17.955800` helper / `17.776242`
conventional, `+3.809%` over its matched control. MTP and DFlash measurements
are support lanes, not substitutes for this target-only objective. Forced SG32,
GDN workgroup packing, batched Q/K normalization with RoPE, Q8 cache hints,
asymmetric tensor split, root-barrier
elision, BMG-forced MMVQ phase ordering, and copy-engine replication did not
win. TP2 graph capture aborted or hung, and the built-in TP2 profiler reset
both compute engines; both remain prohibited. Pass 2 promoted a register-direct
Q8 handoff and direct IMRoPE-to-KV-cache write after clean rebuild and full
exact-output replay. Continue from its
[handoff](../results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md) only with a
materially new exact kernel proof; do not recycle rejected doors.

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

Status: approved at `102.971435596 tok/s` under the submitted legacy
100-event/99-interval convention and `101.941721240 tok/s` under conventional
interval accounting. It is 13/13 token-and-text exact against the canonical
q1 teacher, cache-zero on all rows, and approved by LocalMaxxing as
`cms2ccv2d00lps201rej94pjy`. The result uses exact width 12, DFlash depth 11,
an audited 146/145 Breakable PIECEWISE topology, BF16 KV, and 31 runtime
E4M3FN W8A16 DFlash projection conversions per rank.

This lane is sealed and closed; no benchmark or service is active. The
conventional 102 objective remains short by `0.058278760 tok/s`. Reopening it
requires a new preregistration, not a continuation from the superseded
94.920 row.

Poolside's quantized checkpoint officially ships calibrated FP8 KV; BF16 is a
deliberate record-lane override. The earlier B70 A/B doubled cache capacity
with FP8 but slowed short decode and changed output. Keep future official
long-context FP8 service work separate from the BF16 bitwise-exact record.

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
quality identity and is unnecessary for the requested 32K ceiling. The primary
next target is F16 c2/32K on each of four independent one-GPU processes, using
parallel screening but isolated same-card promotion. MTP and vision remain
optional later lanes.

### Qwen3.6 27B INT4 AutoRound On B70

Main entries:

- [result packet](../results/qwen36-27b-autoround-int4-b70/README.md)
- [handoff](../results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [exact 95.385 repro](../repro/qwen36-27b-autoround-int4-b70/README.md)
- [2026-08-15 independent validation](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md)
- [private source bundle and patches](../patches/qwen36-27b-autoround-int4-b70/record-20260711/README.md)
- [experiment lane](../experiments/qwen36-27b-autoround-int4-b70/README.md)

**Lane closed 2026-08-18.** The retained `95.385` record stands; nothing beat it
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
and performance validation. Current margin-free MTP5 anchor: `101.170 tok/s`
on the 25-prompt suite (`92.851` selection-12), with only 21–22/25 pairwise
repeatability. A valid target-only quality oracle now exists, but its A/B is
24/25 and the sealed-cache TP1 MTP5 control is only 2/4. This is research
evidence, not a record.

Distinct from the llama.cpp Q4_K_M target-only Qwen3.8 lane: different runtime,
quantization, and speculation class. Do not merge their rows.

Main entries:

- [lane setup and model manifest](../repro/qwen38-27b-autoround-int4-b70/README.md)
- [baseline evidence](../data/qwen38-27b-autoround-int4-baseline-20260818.json)
- [post-recovery TP1 result](../experiments/qwen38-27b-b70/notes/2026-08-20-postrecovery-marginfree-tp1-runtime-nondeterminism.md)
- [current source/host queue](../repro/qwen38-27b-autoround-int4-b70/REFERENCE-HOST-HANDOFF.md)

Status: active research. The target oracle, post-recovery TP2 repeats, and TP1
control are complete. The immediate queue is a least-intrusive same-cache TP1
trace of the structured-extraction flip at token 225. Only after runtime
determinism and target parity pass should draft-acceptance changes or a record
submission be considered.

### Gemma 4 26B A4B Q8 / INT8 On B70

Main entries:

- [handoff / production bookmark](../results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [production service recipe](../results/gemma4-26b-a4b-q8-b70/production-service.md)
- [result packet](../results/gemma4-26b-a4b-q8-b70/README.md)
- [125 tok/s strict repro](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
- [research plan](../results/gemma4-26b-a4b-q8-b70/research-plan.md)
- [reliability protocol](../results/gemma4-26b-a4b-q8-b70/reliability-protocol.md)
- [VDR2 selected-down record note](../results/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-record.md)

Status: production-servable one-B70 backend plus current frontier/reference,
with diminishing returns unless the next change is a larger
verifier/router/speculation or service-prefill design rather than another small
flag sweep.

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

Status: current model-slot production profile is c8. c10 is research-only;
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

Status: closed reference packet for now, but preserve every lesson for a future
return. No valid `>150 tok/s` path was found; best strict 4x baseline is
`93.55 tok/s`. The main carryover lesson is that graph/speculative speed paths
must pass full-scale canaries, not smoke tests.

### Qwen3.6 27B Q4_0 / FP8 Historical Lanes

Main entries:

- [FP8 vLLM/XPU result note](../results/fp8-vllm-xpu-qwen36-2026-05-04.md)
- older notes under `../notes/`

Status: the intensive Q4_0/DFlash SYCL lane closed on 2026-07-13 at a strict
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

Status: paused/closed on 2026-07-21 at a fully characterized frontier. The best
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
