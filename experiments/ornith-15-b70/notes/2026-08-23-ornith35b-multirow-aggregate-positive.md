# Ornith 1.5 35B: measured aggregate curve and multi-row fusion candidate

Date: 2026-08-23

## Result

The accepted twelve-feature Ornith stack does not scale close to linearly with
concurrent decode sequences. A direct `llama-batched-bench` sweep measured
`162.504 tok/s` aggregate at 16 sequences and `216.513 tok/s` at 32. The
external planning estimate of roughly `857 tok/s` at 16 sequences is therefore
not suitable as evidence for this machine or recipe.

A default-off SYCL candidate generalizing two exact one-row fusions to 2--32
rows improved every matched multi-row point. A focused C/B/B/C confirmation at
four sequences measured `120.694 -> 123.356 tok/s` aggregate, **+2.21%**. The
one-sequence point was neutral. This is a research-positive optional patch for
multi-user workloads; it is not part of the package's single-user launch.

## Measurement scope

This is a raw llama.cpp engine continuous-batching test with independent
prompts and interleaved decode. It is not an HTTP request-concurrency test and
does not include network, JSON, queueing, or server scheduler overhead.

The command shape was:

```bash
llama-batched-bench \
  -m Ornith-1.5-35B-Q4_K_M.gguf \
  -ngl all -fa on -c 65536 -npp 1024 -ntg 256 \
  -npl 1,2,4,8,16,32
```

It used one Intel Arc Pro B70, the pinned llama.cpp revision and accepted
twelve-feature patch, graph off, F16 KV, copy offload disabled, and the exact
runtime doors in the package. `speed_tg` is aggregate generated tokens divided
by decode time. Per-user rate below is arithmetic aggregate/users, not a
latency percentile.

## Accepted-stack baseline curve

| concurrent sequences | aggregate tok/s | arithmetic per-user tok/s |
| ---: | ---: | ---: |
| 1 | 98.025 | 98.025 |
| 2 | 102.672 | 51.336 |
| 4 | 118.883 | 29.721 |
| 8 | 146.283 | 18.285 |
| 16 | 162.504 | 10.156 |
| 32 | 216.513 | 6.766 |

These are measured points only. No missing concurrency, queueing latency, or
HTTP throughput is interpolated or extrapolated from them.

## Why the single-user optimizations stopped helping

The accepted fusions are deliberately guarded to one decode row. Activation
counters showed their MoE add-reduction and residual/RMS paths firing at
`npl=1` and recording zero hits above one sequence. The backend therefore fell
back to the stock multi-row graph exactly where aggregate throughput matters.

The candidate patch:

- assigns an independent workgroup to each of 1--32 rows;
- generalizes the ordered eight-expert FP32 add reduction;
- generalizes residual/RMS and routed-plus-shared/residual/RMS paths;
- retains the original FP32 materialization and reduction boundaries;
- rejects unsupported shapes and remains default off behind
  `GGML_SYCL_FUSED_ORNITH_MULTIROW=1`.

Patch: `../patches/llamacpp-ornith15-multirow-aggregate-fusions-candidate-20260823.patch`
(SHA-256 `61135a790d749b66ca6fd63a045a5b675ec7c2e868d913e8234adff7cabbbe6e`).

## Correctness gate

Fresh HTTP-server responses were not a usable byte-exact gate: the unmodified
control itself changed three of four response hashes across fresh concurrent
runs. That pre-existing scheduler/slot variability is preserved in the raw
artifacts and is not attributed to this candidate.

The decisive gate used `llama-batched` with four fixed sequence IDs, unified
KV, a fixed prompt and seed, greedy temperature zero, and 276 generated tokens.
Control and candidate stdout were byte-identical (`cmp=0`), both SHA-256:

`1b50819cab9e15ac7e5219f05e8f76878686ded24b3a99ebde6616dad4b621f1`

The candidate recorded 2,800 multi-row MoE-reduction hits and 5,600 multi-row
residual/RMS hits in that test.

## Conservative paired sweep

An initial ascending candidate sweep showed large gains but also exposed a
strong process-order/warmup effect. Those deltas are retained as diagnostics
and are not used as the claim. A same-binary, descending candidate/control
pair gives the conservative comparison:

| sequences | control tok/s | candidate tok/s | delta |
| ---: | ---: | ---: | ---: |
| 1 | 100.771 | 100.810 | +0.04% |
| 2 | 92.030 | 95.246 | +3.49% |
| 4 | 119.350 | 121.930 | +2.16% |
| 8 | 145.830 | 147.897 | +1.42% |
| 16 | 165.292 | 166.580 | +0.78% |
| 32 | 219.308 | 220.459 | +0.52% |

## Four-sequence confirmation

Four fresh processes were run C/B/B/C, each with three identical four-sequence
shapes. The first cold shape in each process was excluded before comparison.

| arm | two warm decode rows (tok/s) | warm mean |
| --- | --- | ---: |
| control 1 | 121.194, 121.328 | 121.261 |
| candidate 1 | 123.403, 123.372 | 123.387 |
| candidate 2 | 123.296, 123.352 | 123.324 |
| control 2 | 119.976, 120.276 | 120.126 |

Pooled controls: `120.693573 tok/s`. Pooled candidates: `123.355557 tok/s`.
Confirmed improvement: **+2.2056%**. Both candidate arms exceeded both control
arms.

## Disposition

Keep the patch as an optional, evidence-backed concurrency candidate. Do not
replace the accepted single-user patch or advertise an HTTP users/sec result.
The next aggregate optimization should extend another high-frequency
single-row Ornith fusion to multi-row, with the same deterministic gate and
matched C/B/B/C measurement discipline.

## Full shared-gate chain follow-up

That next fusion was tested. It measured +1.235% alone, but only +0.276% when
stacked on this generic patch, with overlapping warm-sample ranges. It is not
promoted; this generic +2.21% patch remains the recommendation. See
`2026-08-23-ornith35b-shared-gate-residual-rms-multirow.md` for the direct
measurements and archived research patches.
