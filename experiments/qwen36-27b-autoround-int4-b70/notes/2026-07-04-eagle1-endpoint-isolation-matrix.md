# 2026-07-04 - EAGLE1 Endpoint Isolation Matrix: Closed Negative

## Classification

Diagnostic only. Do not submit to LocalMaxxing and do not use as a headline
throughput result.

This note closes the current local EAGLE1 endpoint attempt for
`webhie/Qwen3.6-27B-int4-AutoRound` on one B70. The current valid record remains
the webhie BF16-scale runtime INT8-LM-head MTP3/cg8 row at
`65.27648650325429 tok/s` with strict fresh-response gating.

## Why This Was Run

The first larger local EAGLE1 attempt trained cleanly and looked promising
offline:

- corpus:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-4gpu-trainheldout-20260704T075504Z`;
- best draft:
  `draft-e6-r3-lr3e5-tok01`;
- offline held-out acceptance: mean accepted tokens `2.1015625`, with step-1
  acceptance `0.8506`, step-2 conditional `0.8519`, and step-3 conditional
  `0.7264`.

Endpoint serving did not match that offline signal: the fixed Qwen realistic
suite produced repeated-token corruption and only about `21.74 tok/s` over
measurable rows. The isolation matrix tested whether this was caused by the
current promoted GDN state flags, XPU graph capture, or speculative depth.

## Runner Changes

Added:

- `scripts/run-qwen27-eagle1-isolation-matrix.sh`

This launches four independent one-GPU diagnostic variants against
`experiments/qwen36-27b-autoround-int4-b70/calibration-suite-v1.json`:

1. `eagle1-currentstate-graph-k3`;
2. `eagle1-defaultstate-graph-k3`;
3. `eagle1-currentstate-eager-k3`;
4. `eagle1-currentstate-graph-k1`.

The runner is explicitly diagnostic:

- uses the calibration suite, not the final promotion suite;
- keeps `cached_tokens=0` checks through the shared candidate harness;
- writes raw logs and verifier traces under `/mnt/fast-ai`;
- records `VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE` for sampler-side evidence.

Also fixed a shared harness bug in
`scripts/run-qwen36-27b-autoround-vllm-candidate.sh`: the default
`BENCH_REQUEST_EXTRA_JSON` fallback was brace-expanded by bash and produced
invalid JSON (`Extra data`). The default is now assigned as a literal string and
preflight-validated with `json.loads()` before model load.

## Raw Artifacts

Failed harness artifact, before the JSON quoting fix:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle1-endpoint-isolation-20260704T094037Z`

Useful isolation run:

- raw root:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle1-endpoint-isolation-20260704T094450Z`;
- external summary:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle1-endpoint-isolation-20260704T094450Z/summary.json`;
- in-repo summary copy:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle1-endpoint-isolation-20260704T094450Z-summary.json`.

The matrix was manually stopped after the useful evidence was collected because
`eagle1-currentstate-graph-k3` stalled without a complete JSON. Ports were
released afterward.

## Results

Complete variants:

| Variant | Graph | State flags | k | Gate | Median tok/s | Main failure |
| --- | --- | --- | --- | --- | ---: | --- |
| `eagle1-currentstate-eager-k3` | off | current promote-source pair | 3 | fail | `19.8276` | repeated outputs, short rows |
| `eagle1-defaultstate-graph-k3` | on | default GDN state | 3 | fail | `20.6978` | repeated outputs, short rows |
| `eagle1-currentstate-graph-k1` | on | current promote-source pair | 1 | fail | `22.4105` | still corrupt / too slow |

Incomplete variant:

| Variant | Graph | State flags | k | Status |
| --- | --- | --- | --- | --- |
| `eagle1-currentstate-graph-k3` | on | current promote-source pair | 3 | no JSON before manual cutoff |

Verifier-trace summary:

- `currentstate-eager-k3`: accepted-token histogram
  `{0:1299, 1:198, 2:33, 3:298}`, with `384` repeated target-argmax rows;
- `defaultstate-graph-k3`: accepted-token histogram
  `{0:1284, 1:215, 2:27, 3:298}`, with `368` repeated target-argmax rows;
- `currentstate-graph-k1`: accepted-token histogram `{0:1425, 1:765}`, with
  `0` repeated target-argmax rows, but quality still failed and throughput was
  far below the record.

Examples included repeated `Cooperativa`, repeated `four`, repeated punctuation
or newline target argmax rows, and short outputs where the calibration prompt
ended after only a few streamed token IDs.

## Interpretation

This endpoint attempt is not near the promoted MTP3/cg8 record and is not a
candidate for further endpoint config sweeping.

The obvious controls did not rescue it:

- default GDN state did not fix repeated-token corruption;
- graph off / eager did not fix repeated-token corruption;
- k1 reduced some repeated-target-argmax trace signatures but still failed
  quality and was slow;
- current-state graph k3 stalled and therefore has no usable result.

The best explanation is a combination of corpus/eval mismatch and EAGLE
integration fragility rather than a single simple state flag. The existing
training data was too narrow and completion-like, with repeated filler patterns
and insufficient chat-style held-out diversity, so the offline acceptance number
was optimistic and did not predict endpoint quality.

## Next Action

Do not repeat this exact EAGLE endpoint attempt.

If EAGLE is revisited, do the setup work first:

1. build a corpus v2 from diverse non-final chat prompts, not repeated filler
   completions;
2. preserve prompt IDs, family labels, and holdout membership through hidden
   dump, dataset build, training, offline eval, and endpoint traces;
3. add offline diagnostics for repeated-token risk, family/OOD acceptance, and
   first-token behavior;
4. require a held-out endpoint calibration pass before touching the final
   realistic suite;
5. only then run strict final promotion gates.

The next practical Qwen27 work should remain one of:

- fewer LM-head calls/rows per verifier step;
- a materially different oneDNN/XPU-integrated top-ID or candidate-score
  primitive;
- better target-verified accepted tokens per expensive verifier step;
- a proper EAGLE corpus/eval v2, not another endpoint config sweep.
