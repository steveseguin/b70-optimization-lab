# Independent 2026-08-15 validation plan

This is a preregistered, contribution-style revalidation of the historical
Qwen3.6 27B AutoRound INT4 TP2 result. The historical result predates the
current conventional interval metric and repeatedly used its 12-prompt suite
during optimization. New measurements must therefore be treated as an
independent reproduction, not as a continuation selected from the old sweep.

The plan was frozen before launching the restored model or observing any new
endpoint measurement.

### Preflight amendment

The first attempted matrix root,
`independent-validation-20260815T145530Z`, stopped before creating any
benchmark rows. The generic runner appended two stray braces to an explicitly
set request-extra JSON value, so the benchmark parser exited before its first
request. That preflight also established that the candidate-only fixed width-4
full graph is not a valid one-row no-spec schedule: it produced corrupt target
text. No speed was observed.

Before restarting the matrix, the JSON default was made syntactically safe and
the no-spec controls were changed to the already quality-validated ordinary
PIECEWISE target graph (capture size 8). They retain the same target checkpoint,
FP16 target compute, runtime INT8 LM head, oneCCL, sampling, and hardware. The
speculative candidate remains unchanged. The failed preflight is preserved
outside Git with its logs and checksums.

A second attempted root, `independent-validation-20260815T150457Z`, completed
the first no-spec arm but stopped before the first speculative benchmark. The
new validator had incorrectly set `STAGE=/home/steve/src/vllm-xpu-kernels`,
overriding the promoted wrapper's graph-safe FlashAttention package. FULL graph
capture then failed, as expected, on oneAPI work-group scratch memory. No
speculative score was produced. The validator now separately hash-pins the
ordinary XPU runtime and the graph-safe FlashAttention extension/device library.
This was a validation-harness error, not a failed performance arm, and its raw
root remains preserved rather than retried in place. Its postmortem manifest
has SHA256
`17bfe4fc65d7fd52e70e25c548b93722e362b6b8d8f4c9636232b9ee97ce1288`.

## Frozen identity

- target: `webhie/Qwen3.6-27B-int4-AutoRound` revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- model identities: every file in
  `repro/qwen36-27b-autoround-int4-b70/manifests/model.json` must pass;
- runtime: the detached source heads and working patches in the standalone
  repro packet;
- target compute: FP16 over the AutoRound INT4 checkpoint, with the recorded
  runtime INT8 target LM head and BF16 scales; the candidate uses its recorded
  fixed width-4 full graph, while target-only controls use the validated
  one-row PIECEWISE graph with capture size 8;
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

The generated suite file has SHA256
`292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c`;
all six arms used that exact byte-identical file.

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

## Independent result

The completed root is
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/independent-validation-20260815T152141Z`.
Its relative-file manifest is `SHA256SUMS` with SHA256
`9ecdc491634200f65cd0b827ec9f55cab485daf5d4b2e592826c9ff26f546b70`.
All six arm manifests and the root manifest passed verification after server
teardown. A Git-resident evidence copy is at
[`evidence/independent-validation-20260815T152141Z/`](evidence/independent-validation-20260815T152141Z/).
Its local manifest has SHA256
`55640e9e724590b23f7a63d71c4c4b388cf9a75ae70a8cef4c4f5670d0747100`.
A compact machine-readable verdict is in
[`../../../results/qwen36-27b-autoround-int4-b70/independent-validation-20260815.json`](../../../results/qwen36-27b-autoround-int4-b70/independent-validation-20260815.json).

The preregistered strict verdict is **fail**, for output identity—not for
startup, cache policy, objective quality, or throughput collection:

- all six fresh arms exited zero, passed smoke and the 25-prompt cache-zero
  gate, and passed the narrow exact cases, repeat32 canary, legacy quality
  baseline check, and 1K retrieval;
- both target-only controls were token-exact on all 25 prompts across the two
  physical GPU pairs;
- every speculative arm differed from its matching target-only control on all
  25 realistic prompts;
- the two speculative restarts on GPUs 0–1 differed on 19/25 prompts, and the
  two restarts on GPUs 2–3 differed on 21/25;
- no device loss, worker crash, benchmark retry, prompt/KV/history/response
  reuse, or nonzero cached-token count was observed.

The legacy quality baseline check above covers its small deterministic case
set; it is not the same as token-by-token parity over the 25 realistic prompts.
The latter is the stronger check and is the reason the final verdict fails.

Current conventional 99-interval throughput:

| Arm | Mode | GPUs | Old 12-prompt median | Later 13-prompt median | Combined median |
| --- | --- | --- | ---: | ---: | ---: |
| `nospec-01a` | target only | 0,1 | 48.153 | 47.827 | 47.868 |
| `spec-01a` | MTP3 | 0,1 | 94.728 | 103.925 | 98.771 |
| `nospec-23a` | target only | 2,3 | 48.013 | 47.986 | 48.006 |
| `spec-23a` | MTP3 | 2,3 | 94.650 | 104.288 | 101.078 |
| `spec-01b` | MTP3 | 0,1 | 95.962 | 104.546 | 98.353 |
| `spec-23b` | MTP3 | 2,3 | 94.531 | 104.388 | 98.761 |

The reporting-rule central estimate is the median of the four speculative arm
medians:

- historical selection prompts: **94.689 tok/s** (arm range 94.531–95.962;
  prompt-bootstrap 95% interval 88.555–100.715);
- later holdout prompts: **104.338 tok/s** (103.925–104.546; interval
  98.707–110.902);
- all 25 prompts: **98.766 tok/s** (98.353–101.078; interval
  92.969–104.754).

This independently reproduces the old result's speed on its original prompt
family under corrected accounting, and shows a real roughly 2x uplift over the
matching target-only controls. It does **not** validate a robust `>100 tok/s`
claim, token-exact speculative decoding, or fresh-start output determinism.
Do not submit a new LocalMaxxing record from this matrix. The retained July
record remains historical evidence under its original metric and quality bar;
the independent matrix is the stronger present-day classification.

## Preregistered persistent-scratch recovery matrix

The follow-up candidate replaces the non-exact ReplaySSM transaction with the
exact native packed GDN path and fixes its PIECEWISE graph replay lifetime by
holding the custom op's temporary tensors at stable process-lifetime addresses.
The one-prompt gate passed 128/128 target-token parity and all 35 aligned
verifier rounds at XPU-kernel commit
`534bd9ccca74e0b076067a212271f896bb137d2a` and extension SHA256
`e9715e02bc7a475f2f8922caa288fa542df6acf24736662aecd37fd6a21cb8a7`.

Before observing any 25-prompt candidate result, the follow-up matrix is frozen
to the same six-arm order, same two physical GPU pairs, same immutable suite,
same target-only controls, same cold/cache-zero rules, same exact/repeat32/1K
quality checks, and same 99-interval metric as the independent matrix above.
Only the speculative transaction changes:

- `VLLM_XPU_GDN_REPLAYSSM_SPEC=0`;
- `VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1`;
- `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`;
- ordinary PIECEWISE capture at fixed verifier width four;
- DDTree/full-graph GDN capture remains disabled.

Run with `run-fixed-scratch-matrix.sh`. The strict correctness gate remains all
25 outputs token-exact to the matching target-only arm and exact across both
fresh candidate starts on each GPU pair. Performance is reported regardless of
outcome. The optimization goal is a combined central median above 100 tok/s,
but no result may be promoted or submitted unless the correctness gate passes.

### Persistent-scratch result

The frozen six-arm matrix completed at
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/fixed-scratch-validation-20260815T194000Z`.
All six fresh processes exited zero, all 25 cold requests per arm were valid,
all cache counts were zero, and all objective quality gates passed. The
persistent allocation fixed the captured-address lifetime failure and made the
candidate much more repeatable, but the strict result is still **fail**:

- candidate arm medians were `98.686`, `98.593`, `99.051`, and `98.523`
  tok/s;
- the preregistered combined median of those four medians was **98.639 tok/s**
  (range `98.523`–`99.051`);
- the old 12-prompt selection subset was `98.429`, while the independent
  13-prompt holdout was `104.153` tok/s;
- GPU-pair 0–1 repeated exactly on 25/25 prompts, and pair 2–3 differed on
  1/25 prompts;
- nevertheless, each candidate arm differed from its matching target-only
  control on 10 or 11 of 25 realistic outputs.

Several first differences recur at the same generated-token positions on both
GPU pairs (notably 68, 77, 402, and 497). That pattern is consistent with a
stable arithmetic/state-transition difference in the packed multi-row GDN
kernel, rather than the repaired scratch-address replay bug. The target-only
controls also differed across physical pairs on 11/25 long outputs, so
cross-pair equality is not used as a substitute for same-pair target parity.

The compact result is
[`../../../results/qwen36-27b-autoround-int4-b70/fixed-scratch-validation-20260815.json`](../../../results/qwen36-27b-autoround-int4-b70/fixed-scratch-validation-20260815.json).
The raw `analysis.json`, report, arm exit codes, environment, and complete
relative-file manifest have SHA256 values recorded there. No LocalMaxxing
submission is permitted from this result.

The next preregistered diagnostic uses only
[`../correctness-recovery-20260815/recurring-divergence-suite.json`](../correctness-recovery-20260815/recurring-divergence-suite.json),
whose first mismatch was token 68 in every candidate arm. Fresh target-only,
packed eager, repaired serial, and packed PIECEWISE/persistent-scratch runs will
use the same 128-token prompt and verifier trace. If eager and PIECEWISE agree
with one another but differ from target and serial at the same verifier row,
the remaining fault is packed recurrent arithmetic. If only PIECEWISE differs,
graph replay still has an unresolved state/lifetime edge. These are diagnostic
runs; their endpoint rates are not promotion evidence.
