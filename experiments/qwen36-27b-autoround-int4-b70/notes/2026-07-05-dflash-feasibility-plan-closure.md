# 2026-07-05 - DFlash feasibility plan closure

Status: **closed no-port / no-record for current Qwen27 Intel B70 lane**.

2026-07-06 update: this lane was reopened once after finding upstream vLLM PR
#40898's DFlash SWA/full-KV repair strategy. The local PR40898-style repair
fixed the catastrophic mixed-SWA plumbing symptom and produced stable
fresh-response DFlash rows, but the best repaired row was only `54.835514 tok/s`
(`k=4`, quality skipped) versus the current valid Qwen27 record
`67.51904968102535 tok/s`. DFlash remains closed for this record lane. See
`2026-07-06-dflash-swa-pr40898-repair-no-record.md`.

## Goal

The plan was to avoid blindly porting Hipfire's AMD DFlash stack, first prove
whether a DFlash draft gives materially better fresh-response acceptance on
our fixed realistic Qwen27 suite, and only then consider an Intel/vLLM/XPU
implementation.

Completion condition reached: existing strict local artifacts and the mixed-SWA
attempt already answer the feasibility gate. DFlash does **not** show strong
enough tau on this workload to justify an Intel kernel/runtime port for the
current `webhie/Qwen3.6-27B-int4-AutoRound` one-B70 record lane.

## Model and local artifacts

Draft checkpoint:

```text
z-lab/Qwen3.6-27B-DFlash
/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash
```

Local config facts:

- architecture: `DFlashDraftModel`;
- dtype: BF16;
- hidden size: `5120`;
- draft layers: `5`;
- block size: `16`;
- mask token: `248070`;
- target hidden extraction layers: `[1, 16, 31, 46, 61]`;
- real layer types: `sliding_attention, sliding_attention,
  sliding_attention, sliding_attention, full_attention`;
- sliding window: `2048`;
- model file: `model.safetensors`, about `3.3 GiB`.

The true architecture is mixed sliding/full attention. Running it correctly in
vLLM needs multi-KV-group DFlash proposer metadata, not a blind deletion of the
single-KV assertion.

## Gate 1: default local DFlash compatibility

Earlier strict runs already performed the required slow acceptance/throughput
probe on the fixed Qwen realistic suite:

- chat mode;
- 12 unique prompts;
- each prompt once as a cold response;
- `cached_tokens=0` on every request;
- no prompt/KV/context/response reuse;
- streamed token IDs used for generated tokens 1-100 after TTFT.

Results:

| Variant | Validity | Median tok/s | p10 tok/s | Mean tok/s | Median TTFT | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| DFlash k=8 cg8 | strict fresh pass | `49.993538` | `42.859013` | `51.255501` | `2043 ms` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k8-cg8-compat-realistic128-chat-tokenids-qwensuite-20260703T121501Z.json` |
| DFlash k=8 cg16 | strict fresh pass | `47.407962` | `40.832305` | `48.622954` | `2025 ms` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k8-cg16-realistic128-chat-tokenids-qwensuite-20260703T121956Z.json` |
| DFlash k=10 cg16 | strict fresh pass | `48.278664` | `41.029667` | `58.127830` | `2417 ms` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k10-cg16-realistic128-chat-tokenids-qwensuite-20260703T121956Z.json` |
| DFlash k=12 cg16 | strict fresh pass | `47.771277` | `45.434386` | `48.662202` | `2912 ms` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k12-cg16-realistic128-chat-tokenids-qwensuite-20260703T121956Z.json` |
| DFlash k=15 cg16 | invalid | n/a | n/a | n/a | n/a | `UR_RESULT_ERROR_DEVICE_LOST` before readiness |

Acceptance from raw server logs was not strong. Representative k=8/cg8
intervals:

```text
Mean acceptance length: 3.02
Per-position acceptance: 0.881, 0.524, 0.310, 0.095, 0.071, 0.048, 0.048, 0.048
Avg draft acceptance: 25.3%

Later intervals: 2.32, 2.85, 2.87, 2.88 mean acceptance length.
```

Representative k=10/cg16 intervals:

```text
Mean acceptance length: 3.07
Per-position acceptance: 0.833, 0.548, 0.357, 0.190, 0.048, 0.048, 0.048, 0, 0, 0
Avg draft acceptance: 20.7%

Later intervals: 2.51, 2.65, 2.75, 2.87, 3.57 mean acceptance length.
```

Interpretation: default/local DFlash can run valid fresh responses, but its
mean accepted tokens per target step is roughly the same class as current MTP3
(`~2.7` target-verified emitted tokens/step), not the `4.5+` tau needed to
justify a port. Throughput tops out around `50 tok/s`, well below the current
strict record `65.27648650325429 tok/s`.

## Gate 2: true mixed sliding/full DFlash architecture

The stronger question was whether the real mixed-SWA architecture changes the
answer. That was already tested with the preserved experimental patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-dflash-multikv-mixed-swa-attempt-20260704.patch
```

The patch got mixed DFlash through startup and graph capture:

```text
Initialized DFlash draft attention over KV groups [64, 65, 66, 67, 68]
Graph capturing finished in 2 secs, took 2.53 GiB
```

Strict graph run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-mixed-multikv-queryslots-k8-cg8-realistic128-chat-tokenids-qwensuite-20260704T113539Z
```

Outcome: invalid, device lost during the strict suite at accepted-count sync.
Before the crash, acceptance was extremely low:

```text
Mean acceptance length: 1.17, avg draft acceptance: 2.1%
Mean acceptance length: 1.10, avg draft acceptance: 1.3%
Mean acceptance length: 1.13, avg draft acceptance: 1.6%
```

Eager/no-async isolation:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-mixed-multikv-eager-noasync-k8-diagnostic-20260704T113817Z
```

Outcome: no immediate device loss, but noncompetitive and manually stopped:

```text
Mean acceptance length: 1.12, avg draft acceptance: 1.6%, throughput 4.6 tok/s
Mean acceptance length: 1.24, avg draft acceptance: 3.0%, throughput 8.2 tok/s
Mean acceptance length: 1.18, avg draft acceptance: 2.2%, throughput 12.8 tok/s
```

Interpretation: true mixed-SWA DFlash does not rescue the lane. It is much
worse on acceptance than the default/full-attention compatibility path, and it
is graph-unstable in the current vLLM/XPU stack.

## Hipfire relevance

Hipfire remains useful as a design reference, not a port target:

- its Qwen27 `185-218 tok/s` rows are code-prompt/RDNA/Hipfire-MQ4 evidence;
- they are not valid local fresh-response headline claims;
- its reusable ideas are target-hidden-conditioned drafting, target-owned
  LM-head, fixed hidden-state staging/rings, and exact GDN tape
  rollback/replay.

Those ideas are worth revisiting if a DFlash-like drafter proves strong on our
fixed suite. This particular `z-lab/Qwen3.6-27B-DFlash` route did not.

## Decision

Close DFlash for the current Qwen27 AutoRound INT4 B70 record lane.

Do **not** spend more time on:

- porting Hipfire kernels to Intel for this draft;
- optimizing DFlash kernels before tau is strong;
- deleting vLLM's single-KV assertion as a shortcut;
- repeating k/capture-size DFlash config sweeps;
- submitting any DFlash result to LocalMaxxing for this lane.

Reopen only if one of these materially changes:

1. a stronger/retuned Qwen3.6 27B DFlash draft appears;
2. an upstream vLLM DFlash/SWA implementation lands and a quick strict-suite
   tau probe reaches roughly `4.5+` accepted tokens/step;
3. the target changes to stock BF16 `Qwen/Qwen3.6-27B`, where draft/target
   mismatch may differ;
4. the goal becomes upstream correctness/plumbing rather than the local
   throughput record.

Next Qwen27 speed work should return to the already-scoped lanes: verifier /
LM-head row or call reduction, a materially stronger target-matched drafter on
held-out data, or a different model lane.
