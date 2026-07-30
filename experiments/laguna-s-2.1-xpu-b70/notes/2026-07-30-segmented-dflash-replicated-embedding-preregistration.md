# Segmented DFlash plus replicated embedding

Date: 2026-07-30 America/Toronto

Status: **preregistered before implementation or device execution.**

## Evidence and hypothesis

The exact segmented-DFlash candidate measured
`119.18937096651626 tok/s` historical (`117.9974772568511` preferred
99-interval metric) in its first cold 13-prompt leg, 13/13 exact and
cache-zero:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-segmented-scored-20260730T150033Z
```

The DFlash checkpoint has no embedding of its own. vLLM assigns the target's
`VocabParallelEmbedding` module directly to the drafter. The existing
`VLLM_XPU_LAGUNA_REPLICATED_EMBEDDING=1` treatment therefore removes the
embedding all-reduce from both the target verifier and the segmented drafter,
not only from the target.

The isolated target-only replicated-embedding comparison on 2026-07-28 was
exact but inconclusive/slightly negative in single legs:

- flag off: `101.0850836787706 tok/s`;
- flag on: `100.87300155871071 tok/s`;
- difference: about `-0.21 tok/s`, well within known host noise.

That result is not evidence that the stacked treatment wins. The new
segmented candidate exposes the drafter embedding reduction as one of only 19
eager boundaries, so removing it is a materially different combination.

## Sealed treatment

Keep the exact first-leg identity unchanged except:

```text
VLLM_XPU_LAGUNA_REPLICATED_EMBEDDING=1
```

Required audited topology:

- target: 145 graph segments / 144 eager breaks on all four ranks;
- draft: 19 graph segments / 18 eager breaks on all four ranks;
- DFlash fixed-address all-reduce slots: 12 rather than 13, because the shared
  embedding no longer reduces.

The target and draft weights, BF16 KV, width 12, depth 11, official DFlash
checkpoint, FP8 W8A16 draft projections, sampling, rejection, prompts, scoring
window, and all correctness gates remain unchanged.

## Gates and stop rules

1. Offline tests must prove both 13-slot unreplicated and 12-slot replicated
   contracts, topology selection, overflow, replay accounting, and selector
   off behavior.
2. One non-scored 400-token two-prompt smoke must be q=1-prefix exact,
   cache-zero, exceed cycle 33 independently on both requests, show normal
   non-flat acceptance, and prove both topologies on all ranks.
3. Only after the smoke passes may one formal cold 13-prompt leg run.
4. Any token/text mismatch, topology drift, captured collective, worker leak,
   or idle failure rejects the combination.
5. Do not reboot, FLR, reload/unbind the driver, clear shared memory, repeat a
   failed probe, move graph capture outside the scored window, warm prompts,
   omit prompts, or select the better of repeated starts.

The first scored leg is evidence, not a confirmed median. Promotion requires
matched confirmation against the segmented candidate. This note makes no
throughput claim for the stacked treatment.

## Offline implementation

- vLLM commit: `f7f0eac0f5b547422cd59de57f2b5b4662aa0432`;
- patch:
  `patches/laguna-s-2.1-xpu-b70/0003-xpu-segment-replicated-DFlash-embedding.patch`;
- patch SHA-256:
  `52c579c204ed2bef6839407f787e1319639b498806e883cbbc22b8750a5ae634`;
- focused vLLM tests: `11 passed`;
- smoke/harness tests: `6 passed`;
- Python compilation, Ruff, Bash syntax, and whitespace checks: pass.

The source keeps the unreplicated 13-slot/20/19 contract as the default and
selects the 12-slot/19/18 contract only when replicated embedding is enabled.
The harness independently derives and records both target and draft topology
from that selector.

## First live smoke: memory failure, no score

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-segmented-replemb-smoke-20260730T151418Z
```

Both reduced topologies captured successfully, but request 0 failed after a
Level Zero `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`, followed by
`UR_RESULT_ERROR_DEVICE_LOST`. The apparent 400-token prefix failure was a
truncated response after engine death, not evidence of a token mismatch.
Available profiled KV memory was 6.99 GiB versus 7.56 GiB without replicated
weights.

Cleanup passed (`stop_status=0`, `worker_status=0`, `idle_status=0`); no reset,
probe, FLR, driver reload, shared-memory cleanup, or reboot was used. The run
has no correctness or throughput claim.

The only permitted retry changes the explicitly recorded
`gpu_memory_utilization` from 0.90 to 0.82. This is the already established
width-12 graph-memory reserve and leaves substantially more headroom for graph
allocation. It does not change weights, arithmetic, prompts, cache dtype,
sampling, or scoring. If that retry fails, this stacked route closes.
