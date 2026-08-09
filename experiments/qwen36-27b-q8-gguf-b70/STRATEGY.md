# Qwen3.6 27B Q8 adaptive optimization strategy

Status: governing long-horizon strategy for this lane.

`CURRENT.md` remains the authority for live host state and immediate work. This
document owns the durable goal, constraints, research system, and decision
rules. Dated notes may propose tactics, but they can be replaced whenever new
evidence makes them obsolete.

## North star

Make the pinned Qwen3.6 27B Q8_0 model run **very fast** on one Intel Arc Pro
B70 per process while preserving the model users actually want:

- excellent prompt processing and time to first token;
- excellent decode latency and throughput;
- strong behavior from short prompts through the 32K context ceiling;
- useful single-request and concurrent serving performance;
- unchanged target identity and no hidden loss of quality;
- reliable, repeatable, maintainable operation across four independent GPUs.

The four-card host is a research accelerator and eventual four-service system.
It is not permission to mix shared-host screening rates with isolated one-card
claims.

The primary scorecard remains target-only text generation with Q8_0 weights,
the correctness-qualified F16 KV reference, and contexts no larger than 32K.
Concurrency is part of that product scorecard. Vision, MTP, and alternative KV
precision are optional separately labeled lanes; they cannot replace a weak
result on the primary identity.

## What “very fast” means

There is deliberately no single permanent score. Maintain a Pareto frontier
across these dimensions:

- prompt throughput and TTFT at short, middle, and near-32K contexts;
- decode rate over both early and sustained output windows at those contexts;
- request-wall latency, not only a favorable kernel interval;
- c1 latency and useful concurrent aggregate throughput;
- fairness, turnover, and stability under real service behavior;
- resource efficiency relative to the card's measured compute and memory
  limits.

Current numeric milestones belong in the lane README or a dated tactical note.
They should move as evidence improves. A candidate is not a general win if it
only accelerates one prompt length, one output prefix, or one synthetic row
while materially hurting another important part of the frontier.

## Non-negotiable integrity boundary

Performance work must not obtain speed by changing the question:

- keep the declared model artifact, Q8_0 weight identity, tokenizer, template,
  sampling policy, and context contract fixed for the primary lane;
- do not detect benchmark prompts, hard-code their content, reuse their
  answers, shorten required output, hide failures, or exclude slow valid rows;
- do not use prompt/KV/response reuse in a cold-response claim;
- do not lower numerical quality or use speculation without a separately
  labeled identity and target-verification evidence;
- treat shape specialization as legitimate only when it is based on general
  runtime properties and succeeds on unseen prompts and neighboring shapes;
- use the same executable behavior for performance and correctness testing;
- make source, runtime, benchmark, and result artifacts reproducible.

The project borrows the spirit of the
[MLPerf Inference fairness rules](https://github.com/mlcommons/inference_policies/blob/master/inference_rules.adoc):
no benchmark detection, no input-content optimization, consistent accuracy and
performance code, and mandatory replicability. This lane is not claiming
MLPerf conformance.

## Stable research objectives

### 1. Keep a trustworthy performance and quality map

Continuously characterize where time and bytes go across prompt processing,
decode, context growth, and concurrency. Separate model compute from runtime,
allocation, synchronization, transfer, and service overhead. Re-profile when a
meaningful source, compiler, runtime, or driver boundary changes.

Maintain both a visible development workload and a versioned held-out workload.
The held-out set should include diverse real tasks, structured output,
reasoning, code, multilingual text, adversarial repetition, request turnover,
and long-context retrieval. Changing a suite creates a new version and requires
fresh controls; it never rewrites an old result.

### 2. Improve the complete serving path

Pursue improvements wherever the current bottleneck map points. Durable
mechanism families include:

- quantized weight layout, consumption, and matrix kernels;
- Gated DeltaNet projections, recurrence, state layout, and state traffic;
- exact chunked long-prompt processing;
- full-attention and KV-cache work at longer context;
- fusion that removes launches, copies, allocations, or synchronization;
- scheduling, batching, concurrency, and request turnover;
- compiler, runtime, graph, and driver behavior;
- carefully verified speculation only when ordinary target execution is no
  longer the best opportunity.

Optimize complete boundaries and endpoints. A faster isolated kernel is an
idea-ranking result until the full model proves the gain.

### 3. Reuse progress made elsewhere

At every research-cycle boundary, review upstream and adjacent backends before
inventing a new mechanism. Watch at least llama.cpp/ggml, Intel SYCL and runtime
projects, SGLang, vLLM, FlashInfer, Flash Linear Attention, and relevant CUDA,
ROCm, Metal, and Vulkan work.

Treat reported token rates on different models or hardware as leads, not
comparisons. Extract the invariant mechanism, required layout, affected phase,
quality risk, and cheapest local discriminator. Pay attention to abandoned or
negative upstream work: integration losses often reveal more than a successful
microbenchmark.

A future 27B successor may inherit this research system and its mechanism
history, but it starts as a new model identity with fresh fit, quality, and
performance controls. Do not carry Qwen3.6 rates forward as validation.

The initial mechanism-indexed watchlist is in
[`suggestions/qwen36-27b-q8-gguf/`](../../suggestions/qwen36-27b-q8-gguf/).

### 4. Turn experiments into cumulative knowledge

Every meaningful attempt must leave behind:

- the hypothesis and why it was worth trying;
- exact source/config delta and treatment-entry evidence;
- benchmark identity and raw artifact pointers;
- correctness, performance, stability, and context outcomes;
- a decision: promoted, useful component, inconclusive, rejected, or parked;
- the reason and dependency that would justify revisiting it.

Do not silently delete negative work. Do not preserve it as an undifferentiated
pile either: summarize the mechanism-level lesson and link the detailed note or
patch.

### 5. Improve the research process itself

After meaningful wins, false wins, repeated failures, or long stalls, run a
short retrospective. Update harnesses, evidence schemas, agent prompts, and
decision rules when the process—not merely the candidate—caused wasted work.

Useful research-health indicators include complete-identity rate,
reproduction success, false-win count, unclassified failure count, duplicated
negative work avoided, and time from sourced idea to defensible decision.
They are diagnostics for the orchestrator, not new targets to game.

## Adaptive research cycle

Repeat this loop rather than following a fixed long checklist:

1. **Orient.** Verify live state, current evidence, recent upstream changes,
   unresolved failures, and the current bottleneck map.
2. **Choose.** Select a small portfolio spanning a high-confidence improvement,
   a deeper architectural opportunity, and one cheap falsification. State the
   expected mechanism and what would change the decision.
3. **Design.** Freeze identity, quality gates, workloads, metrics, evidence,
   stop conditions, and recovery boundaries before measuring.
4. **Screen.** Use the four GPUs to reject weak ideas quickly and collect broad
   functional evidence.
5. **Challenge.** Have an independent reviewer look for identity drift,
   benchmark overfitting, missing treatment evidence, and easier explanations.
6. **Validate.** Promote only through isolated, repeated, broad-context and
   held-out testing, then confirm real concurrent service behavior.
7. **Learn.** Record the outcome, update the idea queue and mechanism history,
   archive what matters, and choose the next cycle from the new evidence.

Only the current cycle should have detailed commands and task order. When it
stops matching reality, close or supersede it without changing this strategy.

## Four-GPU operating model

Use all four cards over the course of every active research cycle. Roles are
temporary and rotate with the work:

- a reference/reproduction role protects the current valid baseline;
- exploration roles test independent hypotheses;
- an integration role combines only independently validated wins;
- a quality/robustness role stresses context, turnover, and concurrency.

Parallel four-card work is ideal for functional screening, profiling,
cross-card calibration, and clearly separated candidates. Close performance
decisions still require same-card controls and isolated confirmation because
shared power, thermals, CPU, memory, and storage can create false rankings.
During an official isolated measurement, the other cards remain quiet; their
next work can be prepared offline outside that timing window.

## Subagent operating model

Subagents have standing responsibilities, not permanent unmanaged processes.
The orchestrator time-shares the available slots and keeps one owner for live
GPU/process safety.

- **External scout:** reviews upstream commits, issues, PRs, papers, releases,
  and non-Intel backends; records only sourced, mechanism-level leads.
- **Internal historian:** searches prior notes, patches, artifacts, and mistakes
  before new work; finds duplicates, prior blockers, and changed revisit
  conditions.
- **Transfer/profiling analyst:** maps external mechanisms and local ideas onto
  measured model boundaries and estimates their full-endpoint ceiling.
- **Experiment critic:** tries to falsify the hypothesis and design before GPU
  time is spent.
- **Integrity sentinel:** independently owns benchmark identity, held-out
  quality, anti-cheating review, and promotion veto.
- **Failure and operations reviewer:** classifies hangs and device failures,
  preserves evidence, and enforces the recovery ladder.
- **Curator:** keeps the idea queue, decision summaries, links, and current
  authorities coherent.

Run the scout and historian at cycle boundaries; the critic and integrity
sentinel before risky or promotable work; the curator after every decision;
and a retrospective reviewer when failures repeat or progress stalls. Before a
promotion, use a fresh independent review that did not implement the candidate.

Once this operating model has survived several cycles, distill the stable parts
into a versioned Codex optimization-research skill. The skill should contain
workflow, evidence, safety, and review patterns—not transient model scores or a
hard-coded experiment queue—and should be revised from retrospectives.

## Knowledge and workspace map

Keep one purpose per artifact:

- `CURRENT.md`: live services, protected work, and immediate next action;
- this `STRATEGY.md`: durable goal and operating system;
- lane `README.md`: current validated evidence and entry points;
- `suggestions/qwen36-27b-q8-gguf/`: sourced ideas, status, and revisit triggers;
- `notes/`: chronological decisions, including failures and supersessions;
- `patches/`: exact tested source/config deltas;
- `data/`: compact structured summaries and retained evidence;
- `results/` and `repro/`: only promoted results and reproduction packets;
- `/home/steve/identified-mistakes/`: audits of process or reasoning failures.

At cycle boundaries, audit dirty/protected worktrees, unpushed commits, broken
links, stale handoffs, volatile build paths, model/runtime checksums, result
classification, storage pressure, and whether every active idea has an owner
and next decision. Prefer repairing the index over adding another overlapping
handoff. Keep `CURRENT.md` compact enough to serve as an operational authority;
move chronology and superseded detail into dated notes and Git history.

The present branch has accumulated substantial unpublished history under a
name inherited from an older lane. Treat branch review, remote durability, and
eventual integration into an appropriately named branch as workspace-risk work,
not as an incidental side effect of a GPU experiment.

## Idea lifecycle

The living queue uses a small stable vocabulary:

- `inbox`: sourced but not yet analyzed;
- `shaped`: mechanism, relevance, risk, and discriminator understood;
- `ready`: evidence contract and prerequisites are clear;
- `active`: currently being implemented or measured;
- `parked`: potentially useful after a named dependency changes;
- `rejected`: answered negatively under a recorded scope;
- `promoted`: part of the validated frontier.

Each idea records its source, affected phase/context, claimed invariant,
expected benefit, quality and stability risks, evidence level, result links,
and explicit revisit trigger. Periodically sample old parked/rejected work, but
reopen it only when the original blocker or evidence quality has materially
changed.

## Quality and promotion authority

The integrity sentinel may reject a speed result even when every timing number
looks good. Promotion requires:

- correct, unchanged run identity and proof that the treatment executed;
- exact regression checks for mathematically equivalent changes;
- broader semantic/task evaluation for any deliberate numerical difference;
- unseen prompts and neighboring context/output shapes;
- short, middle, and near-32K coverage relevant to the affected phase;
- cold-response and real-service results clearly separated;
- clean lifecycle, turnover, fault, and teardown evidence;
- repeatability on the intended deployment topology;
- a complete, reviewable artifact packet.

Keep development and held-out evidence separate. Optimization agents may use
the development suite, but they must not tune candidate-specific behavior from
held-out contents. The integrity reviewer controls suite versions and hashes
and reports the complete result, including regressions.

## Failure and recovery policy

A stalled process is not automatically a wedged GPU. Stop new launches,
capture evidence, and allow a bounded quiet observation period before taking
recovery action. Use actual progress, device, process, and journal evidence—not
log-file size alone.

Prefer graceful workload cleanup, then targeted process termination if a
blocked runtime cannot exit. For a confirmed device/GuC wedge, use the
documented all-card xe module-reload procedure only after its safety checks.
Do not use PCI FLR on this stack. Never reboot automatically; a host reboot is
the last resort after evidence capture, less-disruptive recovery failure, and
explicit user authorization.

The host-specific commands and verification sequence live in
[`docs/local-ops.md`](../../docs/local-ops.md). Recovery actions never turn a
failed or contaminated measurement into a valid retry without a fresh run
identity.

## Strategy review

Review this charter only when the product goal, model/quality boundary,
hardware topology, or accumulated evidence shows that a durable rule is wrong.
Routine discoveries should change `CURRENT.md`, the idea queue, or a dated
tactical note—not expand this document into another brittle execution plan.
