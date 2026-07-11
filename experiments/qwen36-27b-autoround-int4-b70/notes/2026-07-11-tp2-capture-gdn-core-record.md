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

The `100 tok/s` objective is not complete. Next work should:

1. profile this 33-piece winner to quantify the new target step cost;
2. test a graph-capturable full-attention backend only if it preserves exact
   output and can enable fewer than 33 boundaries without losing kernel speed;
3. otherwise pursue verified accepted-depth/branch regeneration, because the
   remaining proposer and sampler costs cannot independently provide the
   required gain;
4. keep target model, quantization, fresh-response policy, and quality gates
   unchanged.
