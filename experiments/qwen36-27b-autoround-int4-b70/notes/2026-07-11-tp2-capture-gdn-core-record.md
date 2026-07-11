# Qwen27 TP2 captured-GDN target graph record

Date: 2026-07-11

Status: **promoted**. Conservative strict fresh-response result
`87.02911429766677 tok/s`; diagnostic isolated high `87.81573759082826 tok/s`.

## Baseline lock and current timing

The exact promoted public-oneCCL/draft-graph recipe was first reproduced
without instrumentation at `82.819760 tok/s`, effectively identical to the
prior conservative `82.893718 tok/s` record. A synchronized profile of the
fixed MTP3 decode bucket measured approximately:

| Region | Mean ms/step | Share of visible timed step |
| --- | ---: | ---: |
| target verifier forward | `25.305` | `79.6%` |
| complete draft | `4.529` | `14.2%` |
| postprocess | `1.392` | `4.4%` |
| sample | `0.575` | `1.8%` |
| total | `31.802` | `100%` |

A narrower draft profile showed that all three draft model forwards total only
about `1.7 ms/step`, three greedy draft LM-head/sample calls total about
`2.1 ms/step`, and draft metadata/bookkeeping is below `1 ms/step`. The target
verifier, not the proposer or sampler, remains the primary cost.

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-draftgraph-stageprofile-timing-20260711T165051Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-draftgraph-draftprofile-timing-20260711T165543Z.json`;
- control summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-draftgraph-stageprofile-control-20260711T1640Z-candidate-summary-20260711T165051Z.json`.

## Graph census and implementation

The prior target generated graph executed `129` compiled pieces over 64 model
layers. It contained 48 GDN layers, 16 full-attention layers, and 256
functional all-reduce/wait occurrences in the generated graph text.

`VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=1` removes
`vllm::gdn_attention_core_xpu` from the PIECEWISE split list. The GDN op stays
inside the surrounding compiled/captured segment, while full FlashAttention
remains an external split boundary. The generated target graph then has only
`33` piece calls. The model still executes all 48 GDN layers; this changes
graph boundaries, not model math, quantization, target verification, or
speculation depth.

Focused source artifact:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-capture-gdn-core-piecewise-20260711.patch`.

## Rejected outer full graph

An isolated `FULL_AND_PIECEWISE` startup compiled successfully but failed while
capturing target FlashAttention:

```text
RuntimeError: The sycl_ext_oneapi_work_group_scratch_memory feature is not yet
available for use with the SYCL Graph extension.
```

This is a concrete Intel SYCL/FlashAttention command-graph blocker, not an OOM
or oneCCL failure. A separate discarded attempt was invalid because it used
`VISIBLE_DEVICES`, which the Qwen wrapper does not consume; concurrent jobs
must set `GPU_INDEX`/`ZE_AFFINITY_MASK` and logical
`ONEAPI_DEVICE_SELECTOR=level_zero:0,1`.

A follow-up replaced FlashAttention with `TRITON_ATTN`. That backend allowed
`FULL_AND_PIECEWISE` to compile, capture, serve, and pass the strict
cold/cached-zero mechanics, but throughput fell to `77.852324 tok/s` (p10
`69.365550`, mean `77.770986`) with quality intentionally skipped. The slower
attention kernel costs more than the outer full graph saves. Preserve this as
a backend no-win; do not trade the current FlashAttention pieces for Triton
only to obtain a single outer graph.

Artifact:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-triton-fullandpiecewise-20260711T1732Z-candidate-summary-20260711T173126Z.json`.

## Strict result and quality

Promoted full-gate run:

- median tokens 1-100 after TTFT: **`87.029114 tok/s`**;
- p10: `79.941979 tok/s`;
- mean: `87.913957 tok/s`;
- full-output after-TTFT median: `85.262032 tok/s`;
- full wall-clock median: `75.779717 tok/s`;
- TTFT median: `732.142 ms`;
- strict suite: 12 unique realistic prompts, each once, all
  `cached_tokens=0`;
- quality: exact OK/copy/arithmetic/JSON cases passed, repeat128 passed,
  baseline outputs matched, and the 1K needle passed.

The independent quality-skipped isolated row reached `87.815738 tok/s`. Use
the lower full-quality `87.029114` value as the conservative headline. It is
`4.99%` above the prior conservative `82.893718` record.

Primary artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-draftgraph-capturegdn-quality-20260711T1712Z-realistic128-chat-tokenids-qwensuite-20260711T170815Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-draftgraph-capturegdn-quality-20260711T1712Z-repeat128-ctx1024-20260711T170815Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-draftgraph-capturegdn-quality-20260711T1712Z-candidate-summary-20260711T170815Z.json`.

## Four-GPU variance crossover

The durable crossover harness runs candidate and control simultaneously on two
TP2 pairs, then swaps the physical pairs:

| Window | Candidate | Control | Paired delta |
| --- | ---: | ---: | ---: |
| candidate GPUs 0-1, control GPUs 2-3 | `85.496559` | `84.113689` | `+1.64%` |
| candidate GPUs 2-3, control GPUs 0-1 | `84.338605` | `83.124809` | `+1.46%` |

Average candidate median was `84.917582`; average control median was
`83.619249`, a same-direction `+1.5527%`. Shared four-GPU load compresses the
isolated gain, but the candidate wins both physical-pair assignments. Combined
with two stable isolated candidate rows, exact baseline reproduction, and the
complete quality gate, this supports promotion with the lower `87.029` result.

Crossover artifact:

- `diagnostics/qwen27-tp2-capturegdn-crossover-20260711.json`;
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/tp2-capturegdn-crossover-20260711T1718Z/summary.json`;
- harness:
  `scripts/run-tp2-capturegdn-crossover-4gpu.sh`.

## Reproduce

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0,1 PORT=19444 QUALITY_REPEAT_RUNS=128 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-capturegdn-candidate.sh
```

The wrapper inherits the checksum-gated pinned public oneCCL runtime, exact
ReplaySSM MTP3 state handling, target INT8 LM-head, draft INT4 LM-head, and
compiled draft all-gather fix from the prior promoted recipe.

## Next frontier

The `100 tok/s` objective is not complete. Follow-up work on the exact record
identity produced these additional boundaries:

- an isolated synchronized stage profile measured broad rank-0 regions at
  `30.31 ms` target forward (excluding its single maximum), `4.19 ms` draft,
  `2.62 ms` preprocessing, `1.35 ms` postprocessing, and `0.50 ms` sampling.
  These regions are not additive endpoint attribution: once GDN is captured,
  a synchronization around target forward also drains work submitted by an
  earlier asynchronous region. Use the endpoint plus accepted-token count for
  step economics, not those broad synchronized totals. Compact artifact:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-capturegdn-stageprofile-isolated-timing-20260711T173558Z.json`.
- the strict top-k64 trace still averages `2.746954` accepted visible tokens
  per verifier step. At the `87.029` endpoint this implies about `31.56 ms` per
  step and requires about `3.156` visible tokens per step to reach `100 tok/s`
  without reducing step time. The optimistic legal-tree envelope is retained
  in `qwen27-capturegdn-strict-topk64-branch-envelope-20260711.{json,md}`.
- corrected intrinsic-MTP fixed trees are mechanically valid but currently
  lose economically. TP1 binary depth-2 used seven target rows, accepted only
  about `2.62-2.72` visible tokens per step (no better than the MTP3 chain),
  and measured `58.89 tok/s`; binary depth-3 reached roughly `3.2-3.3` tokens
  per step but only `54.42 tok/s`. Do not confuse these with the older invalid
  sibling-as-chain screens.
- a fresh TP2 MTP3 control reproduced `87.287 tok/s`. A paired MTP4 attempt
  first exposed an MTP3-specific hardcoded ReplaySSM ring length; the wrapper
  now derives the minimum `2 * (k + 1)` and the kernel rounds it to a power of
  two. MTP4 then served but corrupted/terminated most responses; only two
  prompts reached 100 generated tokens and their partial median was about
  `55.55 tok/s`. This is invalid correctness evidence and closes MTP4 on the
  current ReplaySSM path, not a throughput claim.
- target W4A8 was screened using the existing oneDNN
  `int4_gemm_w4a8` primitive, including per-token activation quantization and
  BF16 output conversion. Across the six real projection shapes, projected
  target projection time regressed from about `22.39` to `28.87 ms/step` and
  introduced material activation error. Do not integrate W4A8 here.

The remaining useful work is a material target-body reduction or a stronger
target-verified drafter that transfers to the strict prompt distribution.
Small oneCCL algorithm changes, naive compact LM-head kernels, fixed trees,
FC-only MTP adaptation, and W4A8 are now closed. Keep the target model,
quantization identity, fresh-response policy, and quality gates unchanged.

## FP16 target compute promotion

The same captured-GDN TP2 recipe was then run with `--dtype float16`. This
keeps the AutoRound INT4 weights unchanged and changes target activation/
compute dtype from BF16 to FP16. A six-shape projection microbenchmark
projected only a `22.31 -> 21.67 ms` target projection reduction, but the full
endpoint improved materially, showing that non-projection target kernels also
benefit.

Two four-GPU pair-swapped windows measured:

| Window | FP16 | BF16 | FP16 gain |
| --- | ---: | ---: | ---: |
| FP16 GPUs 2-3, BF16 GPUs 0-1 | `92.637225` | `86.504722` | `+7.09%` |
| FP16 GPUs 0-1, BF16 GPUs 2-3 | `91.714405` | `86.766262` | `+5.70%` |

The lower FP16 row is promoted. It passed all 12 unique prompts once cold,
`cached_tokens=0` throughout, exact cases, repeat128, complete baseline output
parity, and the 1K needle. Headline metrics are median `91.714405`, p10
`81.735821`, mean `90.916872`, full after-TTFT median `87.667759`, wall median
`76.670155`, and TTFT median `743.355 ms`.

Reproduce with:

```bash
GPU_INDEX=0,1 PORT=19446 QUALITY_REPEAT_RUNS=128 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-capturegdn-fp16-candidate.sh
```

Authoritative packet:
`results/qwen36-27b-autoround-int4-b70/tp2-fp16-capture-gdn-20260711.json`.
LocalMaxxing approved the conservative row as `cmrgojixq005rmj0141e9fjj2`.
