# 2026-07-12 Phase 0 Implementation

## Identity

- llama.cpp: `e3546c7948e3af463d0b401e6421d5a4c2faf565`, dirty private tree;
- build: Release, NDEBUG, SYCL, `GGML_SYCL_GRAPH=ON`, AOT `bmg-g31`;
- target: `Qwen3.6-27B-Q4_0.gguf`, SHA256
  `20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a`;
- draft: `Qwen3.6-27B-DFlash-Q4_K_M.gguf`, SHA256
  `71362369a3428a9e93436a869b1131f63e04b88efbc92dacacb18c419d8de95c`;
- hardware: four Intel Arc Pro B70 devices; tests below used one physical B70
  at a time through `ZE_AFFINITY_MASK`;
- target KV for current Phase 0 rows: `q8_0` K and V.

## MMVQ Dispatch Correctness

A dedicated backend regression creates one Q4_0 weight tensor, executes an
M=1 warm operation to bootstrap the reordered representation, and then checks
M=1 through M=17 against the CPU reference.

Results on physical GPU0:

- `GGML_SYCL_ENABLE_OPT=1`: 17/17 passed;
- `GGML_SYCL_ENABLE_OPT=0`: 17/17 passed;
- total: 34/34 direct cases passed.

Raw logs:

- `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/phase0/mmvq/q4_0-reorder-n1-17-opt1.log`;
- `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/phase0/mmvq/q4_0-reorder-n1-17-opt0.log`.

This validates the rows 9-17 dispatch extension in both the reordered fast
path and the optimization-disabled control. It does not replace full-model
quality or state validation.

## Graph Evidence Before Concat Gate Repair

An instrumented graph-on one-token target run proved the prior state:

```text
requested=1
compatibility_rejected=1
recorded=0
replayed=0
reason=CONCAT
```

Raw evidence:
`/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/phase0/gpu1-graph-evidence-preconcat-v.stderr.log`.

Source inspection showed that the recurrent model uses dimension-0 concat.
The SYCL implementation already submits dimension-0/1/2 and non-contiguous
concat as kernels; only contiguous dimension-3 concat performs blocking
`memcpy(...).wait()`. The compatibility gate was narrowed to reject only that
blocking case.

The post-change graph entered recording and submitted an executable graph for
all eight measured forwards, but update failed on every forward after the
first and recreated the executable graph:

```text
requested=8
compatibility_rejected=0
recorded=8
created=1
updated=0
recreated=7
replayed=8
```

This is not persistent replay. The graph-on diagnostic measured only
`8.09 tok/s`, so graph requesting remains off by default. The next graph task
is fixed-address/signature reuse that can submit an existing executable graph
without recording and recreating it each token.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/phase0/gpu1-graph-evidence-postconcat.stderr.log`.

## Implemented Harness Work

- current `GGML_SYCL_ENABLE_*` launcher controls and durable graph counters;
- fixed no-spec, MTP3, and DFlash 5/8/15 launcher profiles;
- strict sequential baseline runner:
  `scripts/run-qwen27-tp1-phase0-baselines.sh`;
- persistent four-worker foundation and checked model/golden manifests under
  `experiments/qwen27-dflash-sycl-b70/harness/`.

No result in this note is promoted yet.

## DFlash Executor Identity Correction

The first strict DFlash5 attempt incorrectly selected llama.cpp's distinct
`draft-dflash` executor for the external DFlash GGUF. It passed the cold-suite
mechanical gate but accepted almost no tokens and measured `13.74 tok/s`.
This is preserved as a misconfigured negative result, not a DFlash quality or
speed conclusion. The July 12 working diagnostics used the external GGUF as a
`draft-simple` model. Fixed DFlash profiles now select that executor, and the
strict DFlash5 rerun reached only `11.51 tok/s` median on the mixed realistic
suite, despite passing the cold and cached-zero gate. This valid executor is
also a decisive mixed-workload loss. DFlash8/15 mixed-suite runs were stopped
under the plan's kill rules. Preserve long-block DFlash only for code-targeted
screens and future adaptive routing.

## Strict Realistic Baselines

All rows below used graph off, Q4_0 target weights, Q8_0 K/V, 12 unique cold
prompts, `cache_prompt=false`, `--cache-ram 0`, context checkpoints off, and
`cached_tokens=0` throughout.

| Profile | Median tok/s | p10 tok/s | Mean tok/s | Gate |
|---|---:|---:|---:|---|
| no-spec | 25.783 | 25.773 | 25.771 | pass |
| MTP3 | 47.244 | 41.858 | 46.420 | pass |
| DFlash5 `draft-simple` | 11.505 | 11.292 | 11.498 | pass, speed loss |

Structured results are under `data/qwen27-dflash-sycl-b70-phase0/`.

## Four-Card Independent TP1 Calibration

The persistent harness then ran four simultaneous MTP3 TP1 replicas. This is
cross-card calibration, not TP4 and not a new promoted result.

| Physical GPU | Median tok/s | p10 tok/s | Mean tok/s | Gate |
|---|---:|---:|---:|---|
| 0 | 49.708 | 42.338 | 46.932 | pass |
| 1 | 48.296 | 41.896 | 46.394 | pass |
| 2 | 48.205 | 41.164 | 46.354 | pass |
| 3 | 47.976 | 41.954 | 46.912 | pass |

All four rows had `cached_tokens=0`. The result directory is
`data/qwen27-tp1-fourway-calibration/20260712T151554Z/`. GPU0 was about 3.6%
faster than GPU3 by median, so paired candidates must use swapped physical-card
assignments as required by the controlling plan.
