# Model Effort Index

This page is the cross-model work queue and archive. It is meant to help the
next agent switch models without rereading every historical note.

Hardware planning note: the active Intel lab has four B70 32 GB cards. That
lets agents run four independent one-GPU screens or one TP4 service, but it
does not leave spare VRAM for very large models or simultaneous production
inference during multi-day optimization. Higher-VRAM Intel hardware would make
larger future efforts, such as GLM 5.2 and DeepSeek Flash-class models, much
more realistic to validate under the same quality rules.

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

Status: useful reference for SYCL/llama.cpp and FP8 vLLM patterns. Reopen only
with a clear record target and current validity gates.

### DeepSeek V4 Flash AutoRound

Main entry:

- [experiment packet](../experiments/deepseek-v4-flash-autoround-vllm/README.md)

Status: candidate future lane. Needs fresh validity gates before promotion.

## Cross-Model Lessons

- Lock benchmark identity before interpreting speed. Missing graph mode or a
  changed launcher can create false regressions or false wins.
- Treat fast speculative paths as invalid until canaries pass at scale. The
  Qwen36 lane had multiple 75-199 tok/s "wins" that failed quality or were
  synthetic.
- Preserve negative patches and logs. MiniMax improved because dead ends were
  visible; Qwen36 became hard when failed branches were not summarized quickly.
- Prefer model-specific result packets over giant branch merges. Curated
  packets are easier to merge and reuse than mixed experiment branches.
- Keep LocalMaxxing payloads and responses in `data/`, but keep API keys outside
  Git as documented in [localmaxxing.md](localmaxxing.md).
- For one-replica-per-GPU work, prefer four independent servers and four
  disjoint experiments before trying tensor parallelism. This is especially
  relevant to Gemma 4 26B A4B, where the goal is to avoid PCIe collectives.
- LocalMaxxing headline submissions must come from the fixed realistic
  cold-response suite. Synthetic filled-long, repeated, warmed, cached,
  n-gram/history, or continuation-learned scores can guide optimization but
  must remain diagnostic unless revalidated by that gate.
