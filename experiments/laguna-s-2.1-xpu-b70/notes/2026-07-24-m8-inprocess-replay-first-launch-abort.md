# Laguna M8 in-process replay: first launch abort

Date: 2026-07-24 America/Toronto

Status: **harness abort before model construction or generation**.

Sealed root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-inprocess-replay-1cabdf09f-8cf58ed0f-20260724T235650Z
```

The model-manifest content check, strict pre-idle proof, and q1 pre-idle proof
passed. The q1 driver then rejected the launcher environment:

```text
VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=None, expected '0'
```

The runner had omitted this frozen negative selector even though the driver
and analyzer correctly required it. No `LLM` was constructed, no generation
ran, and the eager and graph arms were never attempted. The post-arm worker
scan was empty and the strict post-idle proof passed.

The sealed root is an abort artifact only. It carries no timing, correctness,
or performance evidence and must not be reused.

Disposition: add the missing explicit zero selector, mechanically compare
every driver-required environment key against the runner, commit the repair,
then use a new run root. Do not retry or modify the sealed root.
