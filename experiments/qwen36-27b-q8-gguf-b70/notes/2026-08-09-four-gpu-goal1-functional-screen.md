# Four-GPU Goal-1 functional screen

Date: 2026-08-09

## Outcome

The first full-512 four-card wave passed its intended functional evidence class.
Four independent one-B70 processes simultaneously exercised the 4K, 17K,
near-32K, and fixed realistic workloads. All four child packets and the outer
packet sealed cleanly.

This is deliberately a `parallel-functional-screen`, not a promotable
performance result. The rates below identify the starting bottlenecks and
prove the new measurement path works under four-card load. Isolated c1 and c2
packets remain required for performance claims.

Raw evidence:

- run directory:
  `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-four-gpu-functional-20260809T161652.861663620Z`;
- outer completion SHA-256: `2479df4606...0addce5`;
- outer artifact-manifest SHA-256: `153db86cec...c90e21e`;
- tracked structured summary:
  [`data/goal1-four-gpu-functional-summary-20260809.json`](../data/goal1-four-gpu-functional-summary-20260809.json).

Independent review verified all 314 outer manifest entries, all 71 entries in
each child manifest, and all 172 cross-lane validation checks.

## Identity and topology

- pinned target-only Qwen3.6 27B Q8_0 model, SHA `f93f517f...fb14ce`;
- archived llama.cpp runtime, SHA `1a093f09...a7d7`;
- one process and one 32,768-token F16-KV slot per card;
- DNN0, OPT1, graph off, VMM on, no speculation or prompt cache;
- `65/65` layers offloaded;
- GPU0/1/2/3 at BDFs `23:00.0`, `27:00.0`, `43:00.0`, and
  `47:00.0`;
- loaded residency `28,372 MiB` per card, returning to `43 MiB` per card.

## Diagnostic scorecard

`D100` is `99 / (t100 - t1)`. `D512` is the strategy's sustained-decode
metric, `511 / (t512 - t1)`. PP is the runtime-reported prompt-evaluation
rate; service PP uses the client-observed first-token boundary.

| Lane | Rows | Median prompt tokens | PP tok/s | Service PP | TTFT s | D100 | D512 | Request-wall tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4K | 2 | 4,343 | 156.971 | 156.909 | 27.690 | 15.056 | 15.057 | 8.309 |
| 17K | 2 | 17,222.5 | 156.622 | 156.574 | 109.996 | 13.873 | 13.824 | 3.484 |
| near-32K | 2 | 31,843.5 | 155.889 | 155.845 | 204.328 | 12.639 | 12.635 | 2.092 |
| realistic | 12 | 68.5 | 88.293 | 88.191 | 0.767 | 15.528 | 15.446 | 15.124 |

Every number above was independently recomputed from raw timestamps with zero
delta from the retained summaries. The realistic PP row is dominated by
fixed request overhead and is not comparable with the strategy's 4K PP target.

Against the primary targets, the diagnostic 4K row still needs about `+91%`
PP and `+33%` sustained decode, while near-32K needs about `+60%` PP and `+43%`
sustained decode. TTFT needs reductions of about `46%` and `36%`, respectively.
These are large, honest gaps; the existing runtime is a baseline, not the goal.

## Correctness and safety

- `18/18` rows completed a 512-token deterministic replay with cache reuse
  zero, no truncation, a limit stop, and valid token-1, token-100, and
  token-512 timing endpoints.
- All streamed text matched the complete replay and every required alignment,
  stop, slot, prompt-calibration, and PP-consistency gate passed.
- Each lane's post-workload 128-token canary matched the sealed external
  DNN-off oracle exactly. The 12 realistic rows also matched that oracle's
  first 128 tokens and rendered prompts.
- The six long-context main rows are new `BASELINE_CAPTURE_READY` outputs, not
  external-golden comparisons. Do not call them external-oracle exact.
- No server or device fault was retained, no process needed SIGKILL, no
  survivor or listener remained, and all cards returned to idle.

One transport detail is intentional and important. The `technical-guide` row
reported only 510 individually timed SSE token IDs; incomplete UTF-8 handling
suppressed events corresponding to replay positions 89 and 161. Its final text
still matched the uniquely aligned 512-token replay, and positions 1, 100, and
512 all had timestamps, so both decode metrics remain well-defined. A generated
token count must not be conflated with the number of SSE messages.

The functional evidence class pins and hashes the model FD initially and proves
its file identity remained unchanged, but does not pay for a final 26.6-GiB
rehash. The official isolated class does require that final rehash.

## Decision and next action

The four-process measurement foundation is operational. Do not tune against
these simultaneous rates or sum them as a four-GPU scaling result: each context
band ran on a different card, and the rows named `c2-*` were still sequential
slot-0 requests in one-slot processes.

Next, establish official isolated c1 baselines at 4K and near-32K, then run the
fresh-server two-slot c2 gate. Those packets determine whether the first
optimization cycle should prioritize prompt processing, single-request decode,
or the existing multi-column Q8 path under real simultaneous occupancy.
