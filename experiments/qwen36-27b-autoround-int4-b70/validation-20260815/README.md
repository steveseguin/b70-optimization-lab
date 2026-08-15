# Independent 2026-08-15 validation plan

This is a preregistered, contribution-style revalidation of the historical
Qwen3.6 27B AutoRound INT4 TP2 result. The historical result predates the
current conventional interval metric and repeatedly used its 12-prompt suite
during optimization. New measurements must therefore be treated as an
independent reproduction, not as a continuation selected from the old sweep.

The plan was frozen before launching the restored model or observing any new
endpoint measurement.

## Frozen identity

- target: `webhie/Qwen3.6-27B-int4-AutoRound` revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- model identities: every file in
  `repro/qwen36-27b-autoround-int4-b70/manifests/model.json` must pass;
- runtime: the detached source heads and working patches in the standalone
  repro packet;
- target compute: FP16 over the AutoRound INT4 checkpoint, with the recorded
  runtime INT8 target LM head and BF16 scales;
- candidate: intrinsic target-verified MTP3 with the recorded ReplaySSM and
  full-graph transaction configuration;
- control: the same target/runtime/graph/LM-head identity with speculative
  decoding disabled;
- hardware: two Arc Pro B70s, TP2, concurrency one;
- prompt/template: chat mode, thinking disabled, temperature zero, top-p one,
  seed one;
- output cap: 512 generated tokens; primary window: the first 100 generated
  token events after TTFT, counted as 99 inter-token intervals.

No automatic LocalMaxxing submission is part of this validation.

## Frozen suites

The generated validation suite interleaves two independently identified
groups. The generator refuses a source hash mismatch.

1. Historical selection suite:
   `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`, SHA256
   `df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`,
   12 prompts. This preserves exact comparability but is not called a holdout.
2. Later mixed-task holdout:
   `experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json`, SHA256
   `9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`,
   13 prompts. It postdates the historical Qwen record and was not used to
   choose that implementation. It covers executable code, code repair, SQL,
   concurrency, arithmetic, factual protocol behavior, TypeScript, Rust,
   shell safety, structured extraction, prose, and a long rollover task.

All 25 prompts are sent exactly once per fresh server process. Their order is
deterministically interleaved so neither group occupies an entire early or
late thermal window.

## Frozen run matrix

Each arm is a new server process. No arm is selected or discarded because of
its measured rate.

| Order | Arm | Physical GPUs | Speculation |
| ---: | --- | --- | --- |
| 1 | `nospec-01a` | `0,1` | off |
| 2 | `spec-01a` | `0,1` | recorded MTP3 |
| 3 | `nospec-23a` | `2,3` | off |
| 4 | `spec-23a` | `2,3` | recorded MTP3 |
| 5 | `spec-01b` | `0,1` | recorded MTP3 |
| 6 | `spec-23b` | `2,3` | recorded MTP3 |

Every arm runs a smoke, the 25-prompt suite, four deterministic exact cases,
repeat32 stability, and the 1K needle test. Speculative quality runs use the
matching target-only result as their baseline.

## Required validity checks

An arm is performance-valid only if all of the following hold:

- its process starts from the pinned source/model/runtime identities;
- all 25 unique requests complete without retry;
- every request reports `cached_tokens=0`;
- prefix, KV, checkpoint, response, n-gram, and history reuse are disabled;
- every row has at least 100 generated token-ID events;
- metric accounting is `99 / (timestamp[99] - timestamp[0])`;
- there is no device fault, worker crash, hidden CPU fallback, or incomplete
  teardown;
- exact, repeat32, and 1K quality checks pass.

The speculative implementation is called token-exact only if every generated
token ID on all 25 prompts matches the corresponding target-only arm on the
same GPU pair. Candidate repeats must also be token-exact within each pair.
Any mismatch remains evidence and is reported; it is not retried away.

## Reporting rule

Report every arm. For each arm report historical-selection, independent-
holdout, and combined medians, p10, mean, TTFT, full-output rate, wall rate,
completion-length distribution, and output hashes. The central candidate
estimate is the median of the four independently started candidate medians,
not the fastest run. Also report min/max/stdev and a deterministic prompt-
bootstrap interval. Target-only controls are correctness references and
performance context, not a substitute model.

Raw run directories live outside Git. Track the compact analysis, file
checksums, commands, and final classification here after completion.

