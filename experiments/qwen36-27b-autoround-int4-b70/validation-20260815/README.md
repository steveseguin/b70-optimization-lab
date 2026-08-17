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

## Inductor-partition recovery matrix

The later source audit localized the recurring token-68 failure to the compiled
speculative target forward. A raw-forward diagnostic restored the target token
but measured only `22.218 tok/s`. Enabling current Inductor graph partitioning,
while explicitly disabling the irrelevant MLA-only fusion pass, restored the
same canary under compiled PIECEWISE execution at `84.224 tok/s`. That canary
advanced to the same preregistered six-arm matrix through
[`run-partition-matrix.sh`](run-partition-matrix.sh).

The complete matrix root is
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/partition-validation-20260815T230000Z`.
All six fresh arms exited zero, used the frozen 25-prompt suite, reported zero
cached tokens on every row, passed the realistic and objective quality gates,
and shut down cleanly. Its compact result is
[`../../../results/qwen36-27b-autoround-int4-b70/partition-validation-20260815.json`](../../../results/qwen36-27b-autoround-int4-b70/partition-validation-20260815.json).

The strict verdict is still **fail**:

- candidate arm medians were `99.610`, `99.962`, `100.003`, and `99.635`
  tok/s;
- the preregistered central estimate was **`99.798 tok/s`**, with arm range
  `99.610`–`100.003` and prompt-bootstrap 95% interval
  `96.897`–`103.226`;
- the historical-selection subset was `97.491 tok/s`, while the later holdout
  subset was `103.226 tok/s`;
- every candidate differed from its matching target-only control on 11 or 12
  of 25 complete outputs;
- candidate repeats differed on 2/25 prompts for pair 0–1 and 1/25 for pair
  2–3; the two target controls differed on 1/25 prompts;
- ten candidate divergence points were stable across pairs and starts. The
  original `holdout--concurrency-review` mismatch moved from token 68 to token
  381, showing a material correctness improvement rather than a complete fix.

The single `100.003 tok/s` arm is not a record: it misses target parity,
repeat parity, and the central/robust speed gate. No LocalMaxxing submission is
permitted from this result. The next source step is to port the missing upstream
Qwen/Xe2 safety fixes before any further performance tuning, then re-run a
focused mismatch oracle before paying for another full matrix.

## Complete-runtime upstream safety canary

Three current upstream Qwen/Xe2 correctness fixes were ported onto the retained
kernel source as focused commits: the SLM refill WAR fences, the ratio-three
virtual-head bounds guard, and the convolution-tail bounds guards. Both runtime
components were rebuilt and installed. The complete direct guard passed the
logical-TP4 tail case and actual-TP2 8K/32K cases bit-exactly; see
`upstream-safety-guard-complete-20260815T230500Z` under the raw benchmark root.

The fresh endpoint canary then ran the four historically divergent prompts at
512 tokens with a cold target process followed by a cold speculative process.
Both arms were operationally valid and every request reported zero cached
tokens. The speculative median was `103.80488189787577 tok/s`, while the target
control was `47.94709618021187 tok/s`, under the conventional 99-interval
metric. This is not a record because strict parity failed on all four prompts:

| Prompt | First differing generated token |
| --- | ---: |
| arithmetic reasoning | 6 |
| concurrency review | 68 |
| structured extraction | 246 |
| long rollover repository audit | 391 |

Those are the same known divergence points, proving that the upstream safety
fixes are required but do not repair the packed recurrent arithmetic. The
fail-closed harness stopped before its repeat pair. Raw root:
`upstream-safety-canary-complete-20260815T230700Z`; root manifest SHA256
`c73d3ce4286deb018aaa7736403b42f174260fb7c6e9c8a8deab3b6a8cdb982c`.
The compact tracked result is
[`../../../data/qwen36-27b-autoround-int4-upstream-safety-canary-complete-20260815.json`](../../../data/qwen36-27b-autoround-int4-upstream-safety-canary-complete-20260815.json).

The next default-off proof replaces only the packed multi-row recurrent kernel
with four ordered calls to the ordinary one-token GDN recurrence inside the
same persistent custom op. Packed convolution, exact state-column publication,
MTP scheduling, and Inductor partitioning stay unchanged. It must first make
the direct Qwen-shaped operator guard byte-exact with FP16 activations and the
server's FP32 SSM cache, then pass this same four-prompt cold canary before any
larger performance matrix.

## Native-recurrence oracle correction

The first implementation of that proof passed its direct operator guard but
failed the cold endpoint canary. The direct guard compared the packed verifier
against repeated calls to the native SYCL one-token GDN kernel. The established
target-only server does not use that kernel by default: with
`VLLM_XPU_GDN_NATIVE_FALLBACK` unset, decode and prefill use vLLM's Triton GDN
fallback. The test therefore proved exactness against the wrong arithmetic
oracle.

The endpoint result remains useful negative evidence. Both fresh arms exited
zero, used the same frozen four-prompt suite, reported `cached_tokens=0` on
every request, and performed real MTP speculation. The target median was
`47.43721486441161 tok/s`; the native-recurrence speculative median was
`84.51110693756173 tok/s`. Strict target parity failed:

| Prompt | First differing generated token |
| --- | ---: |
| structured extraction | 5 |
| arithmetic reasoning | 6 |
| concurrency review | 7 |
| long rollover repository audit | 7 |

The harness stopped before repeats. Raw root:
`exact-recurrent-safety-canary-20260816T002046Z`; root manifest SHA256
`756b3a5d8201a34b5596faf1b04b7b303a83309216ff425710fe043dfeeb97d1`.
The direct native-operator guard is retained separately at
`exact-recurrent-direct-guard-20260816T001600Z` with manifest SHA256
`82f6586adab486c58204957e4c97884d4f88696ad313a5a7136ee56907d171d8`;
it is a native-kernel equivalence result, not an established-target result.

The next bounded gate uses one coherent arithmetic identity on both sides:
disable the Triton fallback explicitly for both the no-spec target and the
serial native-recurrence candidate, then compare their outputs as a separately
named native-SYCL-GDN target identity. A passing canary would still require a
separate frozen objective-quality gate. If that identity fails, the remaining
compiled-verifier arithmetic must be isolated before performance tuning.

That coherent native/native canary also failed. The branch marker appeared on
both ranks, the stronger direct guard covered accepted counts 1 through 4
bit-exactly, and both endpoint arms were fresh and cache-zero. The native-SYCL
no-spec control measured `49.741060605989944 tok/s`; the serial
native-recurrence candidate measured `85.3897431000287 tok/s`. The first
differences were unchanged from the backend-mismatched run: structured token
5, arithmetic token 6, and concurrency/long-rollover token 7. The failure is
therefore outside the repaired GDN recurrence and accepted-state selection.

Raw root:
`native-target-exact-recurrent-safety-canary-20260816T005300Z`; root manifest
SHA256 `29f2453278eed918c31eee80ea731eb17f5e0fe59cfeb68cf965af0d0f1de3cc`.
This was a four-prompt parity canary with `run_quality=0`, not a quality gate.
The preregistered first-pair stop correctly omitted repeats. The next
diagnostic bypasses only the compiled speculative target forward while
retaining the same native-SYCL GDN state path.

That raw-forward diagnostic also failed. It retained the native-SYCL GDN
target identity, exact-recurrence implementation flag, real MTP3 scheduler,
and fixed four-row verifier, but set
`VLLM_XPU_SKIP_COMPILED_SPEC_DECODE=1`. Both ranks emitted the exact-recurrence
branch marker. All four requests were fresh and reported `cached_tokens=0`.
The preferred 99-interval diagnostic median was `23.13707545916408 tok/s`;
this deliberately raw
rate is not promotion evidence. Its first differences against the matching
native-SYCL no-spec control remained structured token 5, arithmetic token 6,
and concurrency/long-rollover token 7.

Raw root:
`native-target-exact-recurrent-raw-spec-20260816T010700Z`; post-teardown
manifest SHA256
`4262fab9e2f150679595293558b9f3bb8f6c309bb363fa89c444f157e4fc9d2d`.
The compact result is
[`../../../data/qwen36-27b-autoround-int4-native-target-raw-verifier-negative-20260816.json`](../../../data/qwen36-27b-autoround-int4-native-target-raw-verifier-negative-20260816.json).
This falsifies the compiled speculative wrapper as the primary cause. The
remaining diagnostic boundary is the semantic identity of a four-row INT4
verifier versus a one-row target and the transaction surrounding those rows.
The next control must compare normal speculation with a zero-accept,
fixed-width-four target trajectory under the same native/exact runtime. A
passing fixed-width control would define a separately named target identity
and would still require an objective quality gate; it would not make the
historical one-row target byte-exact retroactively.

That fixed-width-four control also failed. It used the same model, TP2,
native-SYCL GDN, repaired recurrent implementation, compilation identity,
runtime hashes, and frozen four-prompt suite as the normal speculative arm.
The only semantic change was synthetic acceptance rates `[0, 0, 0]`. Runtime
metrics confirmed `0` accepted tokens and zero acceptance at all three draft
positions; every emitted token was target-owned row zero. All requests were
fresh and cache-zero, both ranks emitted the exact-recurrence marker, and the
process exited cleanly. The preferred 99-interval median was
`32.262676165863056 tok/s`, diagnostic only.

Normal speculation nevertheless first differed from the repeated row-zero
trajectory at concurrency token 3, long-rollover token 4, structured token 5,
and arithmetic token 7. The zero-accept trajectory also differed from native
one-row no-spec execution at tokens 3, 4, 6, and 7 respectively. A subsequent
packet trace showed that the first normal speculative packet was target-exact,
so this control does not prove a width-dependent target identity. Instead, the
zero-accept drift after successive rejection transitions implicates cross-call
state rollback or promotion.

Raw root: `native-fixedwidth-zero-control-20260816T012100Z`; final manifest
SHA256
`630f09d7f8bef05e048cd1913e951760c7d419190fd035ad0e67180e6c886b5a`.
The compact
tracked result is
[`../../../data/qwen36-27b-autoround-int4-fixedwidth-zero-control-negative-20260816.json`](../../../data/qwen36-27b-autoround-int4-fixedwidth-zero-control-negative-20260816.json).
The next bounded diagnostic traces the first two verifier packets and layer
boundaries. It must distinguish an already-wrong target row logit from an
acceptance/emission error before any scheduler, KV, or performance change.

That packet trace localized the normal speculative failure before sampling.
For `holdout--concurrency-review`, the first real packet entered with accepted
count 1 and target argmax rows `[369, 264, 11088]`. They exactly matched the
native no-spec continuation; all three drafts were accepted and target bonus
`4098` was emitted. The next packet correctly recorded accepted count 4,
selected source column 3, and positions `[78, 79, 80, 81]`. Its target argmax
rows were `[5757, 3377, 13]`, while native no-spec required
`[5757, 3377, 25]`. The sampler emitted the target rows it received, so row 2
was already wrong after the full-accept-plus-bonus transition.

Raw root: `native-exact-packet-trace-20260816T013000Z`; final manifest SHA256
`b5136d8614a8ff68a3e4c4e2f2cb58cab192a8197a883137028b696107d04276`.
The trace is
diagnostic and its timing is not promotion evidence. The compact result is
[`../../../data/qwen36-27b-autoround-int4-native-exact-packet-trace-20260816.json`](../../../data/qwen36-27b-autoround-int4-native-exact-packet-trace-20260816.json).
The next exact gate is a literal two-call in-place native operator test: call 1
must full-accept into source column 3, then call 2 must reuse the same state
table and persistent scratch and match four ordered one-token native calls
byte-for-byte. The earlier accepted-column guard seeded each restart from its
oracle and did not cover this cross-call lifecycle.

That literal two-call guard passed at zero tolerance. It reused the same state
table and production persistent scratch, full-accepted call 1 into source
column 3, and then ran call 2. Both calls' core and z outputs, every published
convolution prefix, and every FP32 SSM prefix were byte-exact against eight
ordered one-token native calls. All maximum absolute differences were zero.
Raw root: `exact-recurrent-two-call-guard-20260816T014000Z`; manifest SHA256
`e587f72c1b2812d9d8c7cb121cec7da4cc8cfefd819bac0df05a5c6b677057bf`.
This moves the next bisection outside the isolated GDN core lifecycle. The
smallest existing semantic screen is progressive serial speculative
FlashAttention, which evaluates the four verifier rows through ordered
one-row attention calls while leaving MTP scheduling and GDN state unchanged.

That progressive FlashAttention bisection also failed. It ran the frozen
`holdout--concurrency-review` prompt once with a fresh compile/cache root,
`cached_tokens=0`, real MTP acceptance, native target arithmetic, exact serial
GDN recurrence, and `VLLM_XPU_FA_SERIAL_SPEC_MODE=progressive`. Both ranks hit
the exact-recurrence marker and the process exited cleanly. The output still
first differed from the native no-spec target at generated token 7: the
candidate target row produced token `13` where native no-spec required token
`25`. The preferred 99-interval rate was only `75.43835444622417 tok/s`, so
the mode is also a performance loss.

Raw root: `native-exact-fa-progressive-20260816T014000Z`. The compact result is
[`../../../data/qwen36-27b-autoround-int4-fa-progressive-negative-20260816.json`](../../../data/qwen36-27b-autoround-int4-fa-progressive-negative-20260816.json).
The 35-file final manifest SHA256 is
`2f842a640b5e5b10a4287b109616876f2c31f264f91519add713d8297fe5cbce`.
All 128 output token IDs are also identical to the standard compiled exact-spec
arm, making the negative independent of a near-miss textual comparison.
This falsifies packed full-attention execution as a sufficient cause of the
early divergence. The next bounded diagnostic traces layers 0--3 and the Qwen
GDN projection/core/output boundaries on the first two verifier packets to
identify the first unequal activation before changing scheduler or KV state
transactions.

## 2026-08-17 bounded input-dependency closeout

The later state-copy, exact-recurrence, and metadata repairs produced a stable
four-prompt target identity. A narrowed dependency from the current XPU queue
tail into the layer-0 GDN `in_proj_qkvz` oneDNN W4A16 call then passed a warmed
four-prompt screen: **4/4 complete token arrays exact** and
`110.67515578910192 tok/s` by the preferred 99-interval accounting. The raw
root is `int4-input-dependency-layer0-four-spec-a-20260817T014146Z`; its final
manifest SHA256 is
`988ff654c1a3d0ddf7efd4a6331cfe955ceafdd914d82c90314896b8e2cd36a4`.

This is not a promotion. The normal 25-prompt candidate remains 17/25 exact at
`96.51945586661562 tok/s`, and the final dependency source has no matched
25-prompt target/candidate repeats. Raw broad and rebuilt scoped dependency
controls also contradict one another. Experimentation stopped with the runtime
left unchanged pending operator discussion. See the
[closeout note](../../../notes/2026-08-17-qwen36-int4-input-dependency-closeout.md),
[structured controls](../../../data/qwen36-27b-autoround-int4-input-dependency-controls-20260817.json),
and [source packet](../../../patches/qwen36-27b-autoround-int4-b70/int4-input-dependency-20260817/README.md).
