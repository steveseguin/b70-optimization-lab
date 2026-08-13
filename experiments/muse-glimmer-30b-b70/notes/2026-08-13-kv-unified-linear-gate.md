# Unified-KV linear prerequisite for DDTree

Date: 2026-08-13

Decision: **exact and cheap enough for a branch-layout prototype, but not a
strict zero-cost pass**. Nine arms (three C/A/C packets) measured a mean
`+0.048550 ms/round` overhead. Prose and JSON class means exceed the original
`+0.05 ms/round` per-class pass bound, so DDTree still needs another measured
kernel saving plus its real bookkeeping cost before it can honestly cross 100.

## Identity

Config:
`experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-kv-unified-linear-cac.json`

Candidate changed only `--no-kv-unified` to `--kv-unified`. All arms used the
retained BF16 TP4 DFlash stack: device top15, tree merge, block 512, heap scan,
allreduce last-event readiness, committed-only DFlash processing, backend
sampling, parallel meta submission, and graph disabled.

Raw JSONL:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-kv-unified-linear-cac-20260813.jsonl`

SHA-256:
`0a90b4757e69d99e22cf9b6799b06a3f772b77f1c7703bdb0c5332daa2358cd3`.

## Correctness

All nine arms emitted canonical hashes:

- prose `914f754747d0edaa`;
- code `cf2b2c4fd9e36fe5`;
- JSON `4f813a9706abc163`.

Prose and JSON proposal/acceptance counts were stable. In the first two
unified-KV candidates, code used 796 drafted / 198 accepted instead of the
controls' 811 / 197 while emitting the same canonical text. The third candidate
used 811 / 197. Per-round comparison therefore uses each arm's actual
`rounds = predicted_n - accepted`, not raw request throughput.

## Drift-interpolated result

For each packet and class:

`round_ms = 1000 * predicted_n / (gen_tok_s * (predicted_n - accepted))`

`delta = candidate - (control_before + control_after) / 2`

| Class | Packet 1 | Packet 2 | Packet 3 | Mean delta |
|---|---:|---:|---:|---:|
| prose | +0.101313 | +0.052637 | +0.046983 | +0.066978 ms |
| code | +0.025150 | +0.052705 | -0.028545 | +0.016436 ms |
| JSON | +0.081062 | +0.246434 | -0.140791 | +0.062235 ms |

The unweighted mean across all nine deltas is `+0.048550 ms/round`. Packet
class-means are `+0.069175`, `+0.117259`, and `-0.040784 ms/round`, showing the
noise level that made the initial three-arm screen insufficient.

## Implication

The retained DDTree zero-bookkeeping projection before this gate needed about
`0.155 ms/round` of independent saving to reach a 100 t/s arithmetic mean.
Adding measured unified-KV overhead raises that to about `0.204 ms/round`, plus
the actual multi-sequence tree bookkeeping and any branch-mask cost. Unified KV
is cheap enough to run the proposed 16-row branch-layout timing/correctness
probe (well below its 0.2--0.3 ms go/no-go threshold), but it is not evidence
that the integrated tree will cross 100 by itself.
