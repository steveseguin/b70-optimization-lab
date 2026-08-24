# Qwen3.6 35B-A3B aggregate-throughput evidence

Status: **measured experiment; not a promoted deployment packet**

Measured: 2026-08-24

This page is the stable handoff for consumers that need the lab's current
one-B70 Qwen35MoE concurrency measurements. The machine-readable companion is
[`data/qwen36-35b-autoround-b70-concurrency-20260824.json`](../data/qwen36-35b-autoround-b70-concurrency-20260824.json).
Its `profile.concurrencySweep` uses the requested
`users` / `perUserTokS` / `aggregateTokS` row shape.

## Result

On one Intel Arc Pro B70, the Qwen3.6-35B-A3B AutoRound W4A16 target directly
measured **1,039.408 aggregate tok/s at 64 concurrent sequences** in the
complete seven-point r14 sweep. A later combined-runtime r16 treatment measured
**1,052.870 aggregate tok/s at 64 sequences** and **90.909 tok/s at one
sequence**. The latter is a separate two-point treatment and is not spliced
into the r14 concurrency curve.

The r14 profile used persistent raw-engine vLLM batching, 128 input tokens and
1,024 forced output tokens per request, greedy decoding, no prefix cache, TP1,
and two measured repeats per point. `perUserTokS` is the aggregate divided by
the number of sequences; it is labeled as derived in the JSON.

| Concurrent sequences | Aggregate decode tok/s | Per-sequence tok/s | Repeat aggregate rates | Fixed-seed matches |
| ---: | ---: | ---: | --- | ---: |
| 1 | 87.638 | 87.638 | 87.598 / 87.679 | 1/1 |
| 2 | 77.186 | 38.593 | 77.130 / 77.243 | 1/2 |
| 4 | 149.484 | 37.371 | 149.440 / 149.527 | 4/4 |
| 8 | 276.766 | 34.596 | 276.888 / 276.643 | 7/8 |
| 16 | 488.647 | 30.540 | 482.815 / 494.480 | 13/16 |
| 32 | 823.151 | 25.723 | 824.566 / 821.735 | 29/32 |
| 64 | **1,039.408** | 16.241 | 1,041.722 / 1,037.094 | 27/64 |

No row is interpolated, extrapolated, projected, or simulated.

## Interpretation boundary

- This is aggregate raw-engine throughput, not 1,039 tok/s for one user.
- The model is `abhinand/Qwen3.6-35B-A3B-int4-AutoRound` under vLLM/XPU. It is
  not the Ornith 1.5 GGUF checkpoint or the llama.cpp runtime, so it must not be
  reported as an Ornith measurement.
- The 875 tok/s objective and 1,000 tok/s stretch objective were both exceeded
  by direct measurement.
- Literal quality smoke passed (4/4 for r14; 100/100 across B1/B32/B64 for
  r16), but B64 repeat identity remains unresolved: 27/64 requests matched in
  r14 and 29/64 in r16. The result is valid speed evidence but not yet a
  validated user recipe or determinism repair.
- A consumer may show these points as experimental lab measurements. It must
  not use them to calibrate a different checkpoint, quantization, runtime, or
  hardware identity without a matched validation.

## Canonical evidence

- [Structured experiment record](../experiments/ornith-15-b70/data/2026-08-24-qwen36-35b-autoround-grouped-graph-aggregate-candidate.json)
- [Full analysis and artifact links](../experiments/ornith-15-b70/notes/2026-08-24-qwen36-grouped-w4a16-aggregate-candidate.md)
- [Machine-readable consumer bridge](../data/qwen36-35b-autoround-b70-concurrency-20260824.json)

The experiment record owns exact runtime commits, capture sizes, memory
settings, patch hashes, rate definitions, raw evidence hashes, component
stability probes, and failed-attempt boundaries.
