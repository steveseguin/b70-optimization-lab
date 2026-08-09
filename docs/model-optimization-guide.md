# Model Optimization Guide For AI Agents

This guide is for an AI agent starting a new model optimization lane in this
repo. It describes the full path from first contact with a model to a promoted,
reproducible result, including what to try, what to avoid, where to look, and
how to keep the work useful for future agents.

Use this guide with:

- `AGENTS.md`
- `AGENT_HANDOFF.md`
- `CURRENT.md`
- `docs/model-effort-index.md`
- `docs/research-workflow-playbook.md`
- `docs/localmaxxing.md`
- the nearest existing model packet under `results/`

For a concise, evidence-linked catalog of transferable wins and important
boundaries, see [Cross-Model Patterns Worth Reusing](research-workflow-playbook.md#cross-model-patterns-worth-reusing).

## 0. Operating Principles

Do not start by changing flags or code. Start by making the lane measurable.

The strongest optimization work in this repo came from this loop:

1. Define the quality lane and benchmark identity.
2. Establish a valid baseline.
3. Create a repeatable harness.
4. Use cheap screens to reject bad ideas.
5. Use realistic cold-suite gates before promotion.
6. Record every meaningful result, including failures.
7. Promote only clean, reproducible, quality-preserving wins.

The weakest work came from:

- comparing runs with different model/runtime identity;
- treating synthetic or warmed prompts as real throughput;
- changing too many flags at once;
- losing patches and logs;
- pushing huge model artifacts or secrets;
- declaring victory from a smoke test when the bug was intermittent.

## 1. Start With The Workspace

Use the active checkout:

```bash
cd /home/steve/llm-optimizations
git status --short --branch
git log -1 --oneline
```

Expected policy:

- active workspace: `/home/steve/llm-optimizations`;
- branch: `main`;
- no stale side worktree for new experiments;
- stage explicit files only, not broad `git add -A`;
- commit focused work regularly;
- push once useful state is captured.

Before running or editing anything, read:

```text
AGENTS.md
AGENT_HANDOFF.md
CURRENT.md
docs/model-effort-index.md
docs/research-workflow-playbook.md
docs/localmaxxing.md
docs/local-ops.md
```

If the repo is dirty:

1. Identify tracked changes, staged changes, and untracked files.
2. Decide whether each untracked file is valuable evidence, transient output,
   a secret, a model artifact, or a build artifact.
3. Track valuable compact artifacts.
4. Add ignore rules for transient output, secrets, weights, and logs that are
   too large or not useful.
5. Do not delete another agent's work unless it is clearly transient and
   already captured elsewhere.

## 2. Create A Model Lane Packet

Every serious model effort should have a packet under:

```text
results/<model>-<quant>-<hardware>/
```

Start with these files:

```text
results/<model>-<quant>-<hardware>/README.md
results/<model>-<quant>-<hardware>/reproduce.md
results/<model>-<quant>-<hardware>/validity-gates.md
results/<model>-<quant>-<hardware>/runtime-plan.md
results/<model>-<quant>-<hardware>/model-options.md
results/<model>-<quant>-<hardware>/bugs-failed-paths.md
results/<model>-<quant>-<hardware>/localmaxxing-and-targets.md
```

Use `experiments/<model>-.../` for active research lanes. Use `repro/<model>-.../`
only when a result is promoted enough to deserve a standalone runnable recipe.

The packet should answer these questions:

- What exact model is being optimized?
- What quantization and quality lane are allowed?
- What hardware shape is in scope?
- What runtime is being tested?
- What is the current valid baseline?
- What is the fastest invalid or diagnostic result?
- What counts as promotion?
- What is explicitly forbidden?
- Which previous model lanes offer useful carryover ideas?
- Where are logs, patches, data, and scripts?

## 3. Lock The Quality Lane

Decide the quality promise before chasing speed.

Examples:

- "Q8/INT8-equivalent target/verifier; lower precision drafts allowed only if
  the Q8 target verifies accepted tokens."
- "FP16/BF16 baseline quality; FP8 KV is separate and must be labeled."
- "INT4 AutoRound is a side lane, not the default quality lane."

Record:

- exact model repo and revision;
- local model path;
- file size and checksum if practical;
- target quantization;
- draft model quantization, if any;
- KV cache type;
- context limit;
- whether multimodal support matters;
- whether the benchmark is text-only, vision+text, structured output, or service.

Do not silently switch quality lanes. The Gemma 26B work was almost derailed by
confusion between `UD-Q8_K_XL` and `Q8_0`. If the target quality changes,
create a labeled side lane.

## 4. Define Validity Before Benchmarking

Each model needs validity gates. At minimum, define:

- deterministic canary prompts;
- semantic task checks;
- arithmetic or structured checks where relevant;
- long-context checks if context is part of the claim;
- exact response or hash checks for repeated canary rows;
- required prompt/output lengths;
- whether streaming token timing is trusted;
- required `cached_tokens` behavior;
- how speculative decoding is verified.

For fresh-response headline throughput, use this rule:

- each prompt is sent once as a cold response;
- `cached_tokens=0` for every request;
- no prompt cache, KV reuse, context checkpoints, response reuse, warmed
  continuations, n-gram history populated from prior identical outputs, or
  service-side replay;
- speculative decoding is allowed only when accepted tokens are verified by the
  declared target model;
- primary metric is the median conventional rate across the 99 inter-token
  intervals between timestamps 1 and 100 after TTFT across a fixed realistic
  prompt suite;
- also report p10, mean, TTFT, wall-clock full-output throughput, full output
  after-TTFT throughput, hashes, runtime identity, flags, logs, and server
  artifacts.

Synthetic prompts are allowed for diagnostics. They are not headline throughput
unless they pass the same fresh-response policy and are representative of the
claimed workload.

## 5. Establish The Baseline

Before optimizing, run the simplest credible baseline.

For a llama.cpp lane:

- build or locate a known working SYCL binary;
- launch one model replica on one GPU;
- run canaries;
- run the fixed realistic suite;
- record prompt processing and decode metrics;
- record server logs and launcher identity.

For a vLLM lane:

- verify model load;
- verify graph/eager mode identity;
- record quantization, TP/PP/DP, scheduler, graph flags, max model len, memory
  utilization, fallback paths, and async scheduling;
- run canaries and the fixed realistic suite;
- preserve resolved engine config from the log.

Baseline notes should include:

- command line;
- environment variables;
- model paths and revisions;
- GPU selection;
- compile/runtime commits;
- output JSON path;
- server log path;
- whether result is valid, invalid, diagnostic, or inconclusive.

If the baseline is too slow, do not skip validity. A slow valid baseline is the
anchor that prevents false wins.

## 6. Build The Harness Before The Optimization

A good harness should:

- start the server;
- wait for readiness;
- run canaries;
- run the relevant benchmark;
- stop the server cleanly;
- write `summary.json`;
- write raw per-prompt results;
- record launcher identity;
- record server log path;
- expose GPU/port/label overrides;
- avoid relying on an existing warmed service state.

Use consistent folders:

```text
scripts/      shared reusable tools
repro/        promoted runnable recipes
data/         compact structured run outputs
notes/        chronological notes
patches/      source/config diffs
experiments/  active non-promoted research
results/      promoted or closed model packets
```

Every run label should include model, relevant mode, GPU, and timestamp.

Good label examples:

```text
gemma4-q8-gpu0-125repro-20260702T231635Z
qwen36-tp4-piecewise-forcedcomm-deepgate-20260615
minimax-m27-tp4-moefullforward-strict-20260519
```

## 7. Run Four GPUs As A Research Multiplier

On the current host, prefer one full replica per B70 when the model fits.

Use four GPUs for:

- four independent config screens;
- paired A/B comparisons;
- cross-over designs;
- control/candidate/control/candidate lanes;
- temperature or frequency checks;
- long-context ladder parallelism.

Do not use four-GPU screens alone to promote near-record wins. They are good
for rejecting bad ideas and finding promising candidates. Promotion should use a
clean solo run or a balanced same-window A/B that can survive variance.

Example lane layout:

```text
GPU0: control A
GPU1: candidate A
GPU2: candidate B
GPU3: control B
```

Then swap candidates and controls in the next wave if the result is close.

## 8. Measure Variance Early

Before chasing sub-1% wins, measure same-recipe variance.

Do:

- run the same valid recipe several times;
- run no-spec or simplified control when testing target-only kernels;
- capture temperature and frequency telemetry;
- calculate median, p10, mean, stdev, CV, and pairwise spread;
- define a promotion threshold.

Gemma 26B Q8 lesson:

- same-recipe MTP runs had `4.409%` p90 pairwise absolute run-median spread;
- no-spec calibration reduced that measure to `0.577%`;
- temperature telemetry did not explain it;
- small single-run wins were not credible without paired analysis.

For target-side changes that cannot affect speculation:

1. Run lower-variance no-spec A/B.
2. If the no-spec A/B shows a real positive, rerun the normal realistic MTP
   gate.
3. Promote only if the normal gate passes and the total result improves.

## 9. What To Try First

The best early experiments are cheap, reversible, and easy to explain.

### Runtime And Launcher Identity

Try:

- graph on/off when the runtime supports graph replay;
- piecewise graph modes;
- async scheduling on/off;
- memory utilization limits;
- batch and ubatch sizing;
- context size thresholds;
- VMM or host memory fallback;
- immediate command lists;
- copy engine toggles;
- CPU thread count and affinity;
- polling interval;
- cache/checkpoint settings only as diagnostics unless promotion forbids reuse.

Avoid:

- comparing graph-none to graph-on as if they are the same identity;
- leaving diagnostic flags enabled in record runs;
- measuring against a warmed server state.

### Quantization And Model Variants

Try:

- best available INT8/Q8 target;
- official FP8 or INT8 weight-only runtime if quality is acceptable;
- draft model quantization separately from target quantization;
- local GGUF variants only if file identity and quality lane are explicit.

Avoid:

- silently switching from Q8/INT8 to Q4 or QAT and calling it the same result;
- promoting lower precision because it is faster without a quality decision;
- mixing different checkpoints as if they are quant variants of one model.

### Single GPU Before Tensor Parallelism

If the model fits on one B70:

- optimize one-GPU decode first;
- use four copies for research throughput;
- try TP only when the model does not fit or when a multi-GPU serving shape is
  the actual target.

TP can help capacity, but PCIe collectives can erase decode gains at batch 1.
Record the negotiated generation, width, and root topology for every selected
device. Use the
[PCIe topology and local-LLM inference guide](pcie-topology-and-llm-inference.md)
before attributing a TP result to the nominal motherboard generation or slot
shape.

### Prompt Processing And Context

Try:

- FlashAttention;
- context-size fit thresholds;
- batch/ubatch ladders;
- phase-specific prefill ubatch;
- long-context prompt ladders;
- attention tile knobs;
- SWA or local-window bounds when the model architecture supports them;
- prompt-processing-only source flags, but always rerun the short-decode guard.

Keep prompt-processing wins separate from short-decode headline records unless
the same config passes both.

### KV-Cache Precision Is A Separate Lane

Do not infer KV precision from weight quantization or `torch_dtype`. Inspect the
checkpoint's KV-specific scheme, the resolved engine config, and the attention
backend actually selected.

For every BF16/FP16 versus FP8/Q8/TurboQuant comparison:

- record loaded cache scales and whether they are checkpoint-calibrated,
  runtime-calibrated, or default `1.0`;
- report actual cache tokens/card and memory reserved, not just theoretical
  bytes/element;
- separate short-decode speed, long-context decode, context capacity, and
  concurrency;
- treat a KV dtype change as a quality-lane change unless the declared quality
  suite proves equivalence;
- keep graph mode, attention backend, block size, model/draft identity, and
  prompt construction fixed;
- preserve a native-dtype control and run long-context retrieval, semantic,
  repetition, and structured-output gates.

FP8 halves the K/V payload in principle, but that does not guarantee a speedup.
At short context, quantize/dequantize work or a weaker backend can dominate.
Laguna's direct B70 screen doubled capacity but was `4.132%` slower than BF16
on its early matched-DFlash short-context lane. See the
[Laguna KV-cache decision](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-kv-cache-precision-decision.md).

### Speculation

Try:

- MTP/draft-model speculation;
- verifier-accepted multi-token paths;
- draft model quantization;
- `n_max`, `n_min`, and probability threshold sweeps;
- backend argmax IDs or top-k paths;
- reducing verifier host/device copies;
- exact row-adaptive verifier designs;
- candidate-bound proofs only if mathematically sound.

Avoid:

- n-gram/history speedups as headline fresh-response throughput when the
  history learned the repeated benchmark answer;
- accepting draft tokens without target verification;
- treating a speculation speedup as valid before canaries pass at scale;
- averaging warmed repeated prompts into fresh metrics.

### Kernel And Source Work

Look for:

- hot LM-head operations;
- MoE routing and selected-expert paths;
- selected-down weighted sums;
- expert duplicate handling;
- route cache opportunities;
- fused post-norm or residual operations;
- FlashAttention tile schedule and global/SWA shape splits;
- unnecessary host reads or per-token syncs;
- copy or allocation churn in the decode hot path;
- graph replay state hazards;
- allreduce placement for TP models.

Use profiling where possible before writing patches. If profiling is hard, add
low-risk instrumentation behind an environment flag and remove or default it off
after the experiment.

## 10. What To Look For In Logs And Code

For vLLM/XPU:

- resolved engine config;
- graph capture mode and capture size;
- fallback paths;
- async scheduling;
- memory utilization and KV capacity;
- sampler/top-k fallback flags;
- model runner state save/restore paths;
- worker logs around graph capture and runtime recapture.

For llama.cpp/SYCL:

- server launch header;
- selected devices;
- compile flags;
- graph enabled/disabled;
- FlashAttention selected paths;
- KV cache type and size;
- speculative-decoding stats;
- prompt processing timings;
- per-node or kernel profile output;
- source guard flags.

In source, search first for:

```bash
rg -n "spec|draft|argmax|sample|lm_head|MUL_MAT|Moe|MoE|expert|fattn|Flash|graph|cache|restore|sync"
```

Use `rg --files` and `rg` before slower search tools.

## 11. Diagnose Correctness Failures

Classify failures by signature:

- deterministic wrong answer;
- intermittent wrong first token;
- repeated garbage token;
- JSON shape valid but values wrong;
- color/order canary wrong;
- semantic drift;
- arithmetic mismatch;
- timeout;
- crash;
- device lost;
- OOM;
- graph capture crash;
- invalid cache reuse.

Then map signature to likely causes:

- wrong first token after prefill: prefill/decode state handoff or graph reuse;
- repeated garbage token: stale buffer, corruption, or graph input hazard;
- valid-looking wrong values: double-processing, skipped restore, or verifier
  state mismatch;
- only fails at scale: intermittent race, cache reuse, or rare prompt path;
- only fails with graph: captured state or replay ordering;
- only fails with speculation: draft/verifier mismatch or accept logic.

Do not fix before identifying state ownership. For model-state bugs, list every
buffer read by decode and every buffer saved/restored/advanced by speculation.

## 12. Promotion Checklist

Before calling a result promoted:

- model identity is exact;
- quantization and quality lane are unchanged or explicitly relabeled;
- run uses the fixed realistic prompt suite;
- prompts are unique and each prompt is run once;
- `cached_tokens=0` for every request;
- no prompt/KV/context/response reuse;
- no warmed n-gram/history acceleration;
- canaries pass at the required repeat count;
- quality gates relevant to the model pass;
- primary metric is the conventional 99-interval rate between generated-token
  timestamps 1 and 100 after TTFT, with the formula recorded;
- p10, mean, TTFT, wall throughput, and full-output throughput are recorded;
- output hashes or response artifacts are saved;
- server log path is recorded;
- launcher identity is recorded;
- diagnostic flags are absent or explicitly justified;
- result beats the matching prior record by more than noise;
- if within known variance, paired A/B or repeat confirmation exists;
- result packet and reproduction command are updated.

If any item fails, label the result as diagnostic, invalid, support-only, or
inconclusive.

## 13. LocalMaxxing Submission Rules

Submit only policy-compliant records.

Do not submit:

- synthetic-only scores;
- repeated-prompt averages;
- warmed continuation scores;
- n-gram/history-learned outputs;
- cached-prefix or checkpoint reuse;
- lower-quality quantization as a Q8/INT8 headline;
- results that fail canaries or quality gates;
- tiny single-run bumps inside the known variance band.

When submitting, include:

- model and exact quantization;
- GPU count and hardware;
- runtime and commit;
- prompt/output shape;
- primary metric and secondary metrics;
- quality/canary status;
- `cached_tokens=0` statement;
- no cache/history reuse statement;
- config flags;
- GitHub paths to result packet and repro;
- local data/log paths.

Credential handling is in `docs/localmaxxing.md`. Never print or commit the
API key.

## 14. Documentation And Artifact Hygiene

Every meaningful experiment should leave behind:

- patch or exact config delta;
- result JSON;
- server log path;
- benchmark identity;
- correctness status;
- throughput metrics;
- failure signature if any;
- interpretation;
- next action.

Use compact summaries for Git. Large logs can stay outside Git if a summary
records their path and the reason they matter.

Recommended artifact layout:

```text
data/<label>/summary.json
data/<label>/<suite>.json
experiments/<model>/sweeps/YYYYMMDD-<idea>.md
patches/<model>/<YYYYMMDD>-<idea>.patch
results/<model>/README.md
results/<model>/reproduce.md
results/<model>/bugs-failed-paths.md
```

When a result is promoted, create or update:

```text
repro/<model>-<hardware>-<headline>-<date>/README.md
repro/<model>-<hardware>-<headline>-<date>/run.sh
```

Keep failed patches unless they were superseded by a clearly linked fix. Failed
work prevents future agents from rediscovering the same dead end.

## 15. Suggested Start-To-Finish Workflow

Use this as the default operating sequence for a new model.

### Phase A: Orientation

1. Read current workspace docs.
2. Check git state.
3. Create a model lane packet.
4. Identify quality lane and model variants.
5. Identify best public/local baseline.
6. Decide runtime candidates: llama.cpp, vLLM, OpenVINO, Ollama, or other.
7. Write validity gates before benchmarking.

### Phase B: Baseline

1. Download or verify model files.
2. Build or select the runtime.
3. Launch the simplest server.
4. Run canaries.
5. Run fixed realistic suite.
6. Save summary and logs.
7. Document baseline and blockers.

### Phase C: Harness

1. Add a wrapper script for the lane.
2. Record all launcher identity fields.
3. Add GPU/port/label overrides.
4. Add canary and benchmark calls.
5. Ensure clean shutdown.
6. Add JSON summary output.

### Phase D: Coarse Search

1. Run four independent screens across GPUs.
2. Test runtime flags, batch/ubatch, graph, FA, VMM, context limits.
3. Reject obvious losses quickly.
4. Record negative results.
5. Keep quality canaries on, even in screens when cheap enough.

### Phase E: Profiling

1. Profile the current best.
2. Identify top hotspots.
3. Pick source changes tied to hotspots.
4. Add default-off flags for risky patches.
5. Build and run focused A/B.
6. For a native custom op, prove the loaded module and `torch.ops` namespace
   from the real binary; a unit test that installs a fake into the same wrong
   namespace can mask an integration defect.
7. If the op returns a tensor or mutates an argument inside a compiled model,
   exercise its FakeTensor/Meta path before model startup. File placement must
   follow the registered namespace (for example `_C` versus `_xpu_C`).
8. Treat component timing as a scope gate, not an endpoint projection. Even an
   exact micro-fusion with an apparently additive saving can regress after
   allocation, graph scheduling, and runtime interaction costs; one frozen
   endpoint remains the disposition gate.
9. Before replacing small TP collectives with replicated compute, measure both
   sides of the exchange in the same units. On Laguna's six-layer drafter,
   twelve synchronized 73,728-byte BF16 reductions cost only `1.239689 ms` per
   cycle, while evaluating all four FP8 projection shards locally added
   `4.208694 ms` before extra attention work. The communication was visibly
   latency-bound, but replication was still the wrong trade. Compute the gross
   collective time required to cover replicated work plus the endpoint margin,
   and reject locally when the measured collective budget is smaller.
4. Measure the complete removable scope before exercising a risky replacement.
   A later Laguna control timed all thirteen draft producer/all-reduce/consumer
   boundaries at only `1.183299 ms` on the slowest TP4 rank.  Because the
   preregistered integration gate required `1.4 ms`, even a zero-cost
   replacement could not pass; the candidate graph runtime was correctly left
   unexecuted.  An upper-bound control can be both safer and more decisive than
   testing the candidate first.

### Phase F: Variance Control

1. Measure same-recipe variance.
2. Use no-spec calibration for target-only patches.
3. Use same-window paired A/B for small deltas.
4. Capture temperature/frequency if variance is unexplained.
5. Refuse to promote noise.

### Phase G: Promotion

1. Run full realistic cold suite.
2. Run canaries at scale.
3. Run long-context/service guard if config touches prompt processing.
4. Repeat if the failure mode is intermittent.
5. Update result packet, repro, and indexes.
6. Submit to LocalMaxxing only if it is a true valid record.
7. Commit and push.

### Phase H: Closeout Or Next Model

1. Mark exhausted ideas.
2. Preserve patches and failures.
3. Write "what worked" and "what did not" sections.
4. Update `docs/model-effort-index.md`.
5. Ensure the workspace is clean.
6. Move to the next model from a known-good `main`.

## 16. Prompts For Another AI

### New Model Kickoff

```text
Start a new optimization lane for <model> on <hardware>. First read
AGENTS.md, CURRENT.md, docs/model-effort-index.md, docs/model-optimization-guide.md,
and the nearest existing result packet. Create a model packet under results/
with validity gates, runtime plan, model options, and an initial reproduce
file. Do not change runtime code until the model identity, quality lane, and
baseline benchmark are explicit.
```

### Artifact Audit

```text
Audit this model lane for stale claims, missing links, invalid headline
throughput, untracked useful artifacts, and oversized or secret files. Return
exact paths and whether each should be tracked, ignored, summarized, or deleted.
```

### Experiment Proposal

```text
Given the current valid baseline and failed paths, propose the next 12
experiments. Rank them by expected value. For each, state hypothesis, exact
config or patch, validation command, expected win size, expected failure
signature, and whether it needs four-GPU A/B or a solo confirmation.
```

### Negative Result Summary

```text
Turn this failed run into a reusable negative result. Include the reason we
tried it, exact identity, patch/config delta, artifacts, measured speed,
correctness status, failure signature, what class of ideas it rules out, and
what should be tried next.
```

### Promotion Review

```text
Review this candidate as if it is about to be submitted to LocalMaxxing. Check
fresh-response validity, cached_tokens, prompt uniqueness, quality lane,
quantization, speculative verification, metric definition, variance, server
logs, and reproducibility. Return blockers first.
```

## 17. Common High-Value Search Areas

For MoE models:

- selected expert routing;
- duplicate expert handling;
- selected-down fusion;
- gate/up and GEGLU paths;
- weighted-sum epilogues;
- route cache;
- router softmax;
- per-layer norm/residual fusion.

For attention-heavy models:

- FlashAttention tile shapes;
- GQA/MQA special cases;
- SWA/local-window bounds;
- global attention outliers;
- prompt-processing ubatch;
- KV cache layout;
- graph capture compatibility.

For speculation:

- draft model speed;
- accept rate;
- verifier LM-head cost;
- sampled-ID transfer;
- target hidden-state handoff;
- exact accept-prefix design;
- bonus token path;
- state rollback correctness.

For tensor parallel or multi-GPU:

- allreduce placement;
- graph-safe collectives;
- hidden-state shard boundaries;
- PCIe bandwidth and topology;
- root/device residual ordering;
- per-rank logits gather correctness.

For runtime reliability:

- driver and Level Zero errors;
- device lost;
- OOM vs fragmentation;
- graph capture skip reasons;
- runtime recapture;
- stale cache or prefix reuse;
- thermal/frequency variation.

## 18. Final Rule

The goal is not to get the largest number. The goal is to get the largest
number that is true, quality-preserving, reproducible, and useful to the next
person.
