# SC117 IQ3_S: October 28 results

The completed work favors depth-three speculation and demonstrates two target
GPUs plus a dedicated draft GPU, leaving a fourth card free. All experiment
owners exited cleanly. Further tests were stopped at the owner's request to
publish these results.

This is a measured research recipe, with clean-host installation and strict
benchmark certification pending. The [build and setup guide](README.md) exports
source `ba563d432dc616e11232fc90eec54338cc358b18`; it does **not** build the later
binaries below. Later source is retained at
[db016d6db](https://github.com/steveseguin/b70-optimization-lab/commit/db016d6db),
with exact build identities in the evidence. The dedicated-provider controller
still requires an expert local adapter; there is no portable one-command launcher.

## Twelve cold prompts: keep depth 3

Three target B70s plus one draft B70; cuts 0/17/33/48; 65,536-position reservation;
256-row prefill; four transport slots; F32 target activations, unchanged BF16 draft
routing and full 16-bit KV. Both arms use binary
`9599b0bfc025bfdd2d862374bced20b0c14869527cadb3542b3f71fb71842d77`.
These are short actual inputs, not 64K-token prompts. Exact inputs and flags are
in the [paired summary](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/dedicated-depth2-gate/full12-r2-paired-summary.json).

| Speculative depth | Actual outputs | Sum of request times | Decode across all first-to-last intervals |
| --- | ---: | ---: | ---: |
| 3 | 5,965 | 108.826 s | 58.568 tok/s |
| 2 | 5,965 | 124.209 s | 50.764 tok/s |

Depth 2 took **14.14% longer**, losing on all twelve tasks. This is one matched
pair, not a certified record or repeated performance band. Decode is 5,953
intervals divided by their summed duration, not the website's class-balanced
99-interval headline metric. Request times exclude loading and separate full
reset/proof barriers. Owner lifetimes were 553.225 s and 549.770 s respectively.

Both arms match all 5,965 CPU-qualified output IDs. The reference authority
combines 4,941 authenticated historical rows from ten identical complete inputs
and 1,024 newly computed CPU tokens on two inputs. It is not twelve new CPU runs
or proof for every prompt. Eleven cold barriers per arm each checked
4,091,763,958 bytes. All four owners exited zero and passive checks were clean.
[Depth 3 evidence](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/dedicated-depth2-gate/full12-depth3-r2-evidence/index.json),
[depth 2 evidence](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/dedicated-depth2-gate/full12-depth2-r2-evidence/index.json).

## Two target GPUs plus one draft: correctness gate passed

The same binary, depth 3 and 64K reservation passed A → B → A with target cuts
0/25/48. All **1,536 generated IDs** match the CPU-qualified references for two
unique prompts. Each cold-state and repeated-A proof checked **4,111,334,626
bytes**: 2,065 canonical target sources, 39 inactive banks and 73 provider sources.
All three owners exited zero; passive postflight found no holders or new faults.

Request times were 10.371 / 10.573 / 10.293 seconds; owner lifetime was 285.896 s.
This is a reset/repeat correctness gate, **not a speed benchmark**. The full
12-prompt 2+1 suite was **not run**; no matched full-suite topology speedup is
claimed. [Gate summary](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/dedicated-depth2-gate/two-plus-one-aba64k-r2-evidence/summary.json).

## Long prompt: placement trades prompt time against decode

Separate binary `339b75`, reference routing policy, three target GPUs plus draft,
262,144-position reservation, **121,854 actual input tokens and 512 outputs**,
256-row prefill and four slots:

| Target cuts | Request time | First-token wait | Decode, all 511 intervals |
| --- | ---: | ---: | ---: |
| 0/17/33/48 | 261.382 s | 250.842 s | 48.515 tok/s |
| 0/16/32/48 | 248.717 s | 236.209 s | 40.876 tok/s |

Equal 16-layer partitions used **4.85% less request time** but decode was
**15.75% slower**. One matched long-input screen; no universal promotion.
All 512 outputs, 2,065 canonical target sources, 73 draft sources and 122,364
hidden/token pairs matched. This excludes inactive banks and nonfinal head
scratch; it is not all-physical-state equality or independent CPU proof of the
long continuation. All owners exited zero with clean postflight.
[Control](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/equal16-topology-screen/control-r1-evidence/index.json),
[candidate](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/equal16-topology-screen/equal16-r1-evidence/index.json).

The recipe's [historical 2+1/128K and 3+1/262K measurements](measurements.json)
have different reservations and source policy. Do not combine those rows into
a controlled topology comparison or context-performance curve.

## Fixes and remaining ideas

The first twelve-prompt run exposed a parity-accounting error after even-size
bulk prefill: physical recurrent banks swap once per chunk, while the old check
assumed once per token. The fix tracks that offset and clears it on reset;
arithmetic and bank swaps are unchanged. The failed run, CPU regression and
successful rerun remain in the [fix evidence](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/bulk-bank-parity-fix/retention-index.json).

The [durable backlog](../../experiments/own-xpu-runtime/research/pp4-review-2026-10-28/backlog.json) retains wins, losses and untried ideas:

- Full twelve-prompt 2+1 timing against the completed 3+1 control.
- Moving only the first 3+1 partition boundary to relieve the busiest stage.
- Measuring checkpoint-copy cost before implementing smaller reversible snapshots.
- Adaptive draft depth, requiring policy-aware protocol validation.
- Sparse lookup storage for capacity/startup; the mapped version slowed requests.
- Larger expert batches and paired dense loads; the expert screen fell below its integration threshold.

No speculative idea is reported as a speed win. No training, compressed KV,
power-setting changes, host reboot or driver reset was used for this closeout.
