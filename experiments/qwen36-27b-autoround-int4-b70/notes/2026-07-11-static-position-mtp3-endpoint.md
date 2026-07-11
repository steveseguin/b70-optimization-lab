# Qwen27 static position-FC MTP3 endpoint

Date: 2026-07-11

Status: **graph-safe runtime implemented; transferred MTP5 checkpoint is a
strict fresh throughput no-win; MTP3-specific training in progress**. Nothing
in this note is a promoted record or LocalMaxxing submission.

## Why this was reopened

The five-position `allfc-allsteps-lr2e5` checkpoint improved accepted drafts
on all 12 fixed-suite prompt clusters at MTP3 (`+0.123182` drafts/start, paired
cluster CI approximately `[+0.085109,+0.158797]`). The prior runtime could not
test that gain without either freezing FC0 in every compiled draft depth or
running the drafter eager. The current record is `93.036242 tok/s` at roughly
`2.746954` visible tokens per verifier step; unchanged step cost requires
about `+0.205609` visible tokens/step to reach 100 tok/s.

## Runtime implementation

Focused patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-static-position-mtp-runtime-20260711.patch
```

The implementation creates three statically bound MTP forward modules. Each
module calls the same loaded Qwen MTP weights with a literal draft depth 0, 1,
or 2, but owns a separate vLLM compiler backend, AOT artifact, and graph cache.
The proposer routes first and serial draft forwards through those modules and
warms/captures all three before runtime capture is disabled. The normal shared
FC checkpoint path does not instantiate the wrappers.

The initial guarded-recompile design was rejected by a real endpoint:

- attempt 1 failed only in a hashable warning argument and was fixed;
- attempt 2 compiled depth 0, then failed at depth 1 with
  `VllmBackend can only be called once`;
- the first static-wrapper attempt reached serving, but the cache audit found
  all inherited forwards sharing one AOT hash and reusing FC0; it was stopped
  before a benchmark;
- distinct literal forward code objects produced three unique model hashes
  and three unique deployed AOT artifacts:
  `86079b898f6b79795cb473687d020a437305bac64c5900ced5157a59d03ea04b`
  (position 0),
  `024cd441d6870bebe547c95bb0837ddc9413f85be1fb08c9bf0cbddf017b5556`
  (position 1), and
  `4822497b66ab24ce0b9a0446039d62a9fd99c068bdee8a372da67a1836748e9f`
  (position 2).

The endpoint then loaded all five BF16 FC tensors, enabled three static entry
points, compiled three distinct `eagle_head_position_{0,1,2}` backends, and
completed target PIECEWISE/FULL graph capture. This closes the runtime graph
identity problem for MTP3.

## Strict endpoint result

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-tp2-fp16-positionfc-static3-unique-probe-20260711-20260711T221647Z
```

The fixed realistic 12-prompt suite ran each prompt once cold with
`cached_tokens=0`, target-verified MTP3, unchanged AutoRound target weights,
and the current graph-safe FlashAttention record topology:

| metric | position-FC endpoint | current record |
|---|---:|---:|
| median tokens 1-100 after TTFT | `89.285778` | `93.036242` |
| mean | `90.172277` | `92.773145` |
| p10 | `82.790027` | `82.845516` |
| full after-TTFT median | `87.371166` | `91.219731` |
| TTFT median | `737.331 ms` | `742.232 ms` |

This is a valid fresh-response **no-win** (`-4.03%` headline median). The full
quality tail was intentionally stopped after the strict speed failure; no
quality or production claim is made for this checkpoint. The run remains
valuable because it proves the static dispatch and endpoint topology while
showing that the transferred MTP5 FC gain does not cover its extra graph/runtime
cost.

## Next experiment

`run-position-fc-mtp3-training-4gpu.sh` trains four MTP3-specific candidates
at learning rates `1e-5`, `2e-5`, `3e-5`, and `5e-5` on the disjoint v6 chat
trajectory corpus, one per B70. It then evaluates each on the untouched fixed
realistic-suite continuation corpus. These are acceptance diagnostics, not
throughput results. Do not run another endpoint unless a candidate exceeds the
predeclared `+0.205609` drafts/start gate with broad per-family support; a
candidate that passes still needs strict cold throughput, full quality, and a
pair-swapped variance gate before promotion.

The first matrix launch used an accidental `65,536`-start default and was
stopped around 1,600 of 16,384 optimizer steps, before any checkpoint export.
The launcher default was corrected to the prior transferred experiment's
`16,384`-start budget (4,096 optimizer steps); the interrupted directory is
diagnostic-only and must not be treated as a completed candidate:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-position-fc/mtp3-4gpu-20260711T222200Z
```
