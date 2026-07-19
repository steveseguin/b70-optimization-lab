# K160 EAGLE-3 / DEAGLE draft design and execution plan

Date: **2026-07-19**  
Status: **design only; no model load, GPU work, training, source integration, or
promotion has been performed**

## Decision

Build a small, dense, recursively autoregressive draft head that consumes three
broadly spaced K160 target features. The first implementation proposes a linear
chain of seven tokens. It replaces only the DSpark proposal producer and reuses
the existing fixed transaction: seven draft IDs become the seven speculative
rows, the unchanged K160 target evaluates the current token plus those IDs as
one exact **M=8** sequential verifier call, and the existing target-owned
rejection/bonus/commit path decides what is emitted.

This is EAGLE-3-style in the important sense: direct multi-step token training
uses a fusion of low-, middle-, and high-level target features rather than only
the top target feature. It also carries a small feature-consistency regularizer
for K160 bring-up. That regularizer is deliberately secondary: published
EAGLE-3 removed feature prediction as the primary objective. DEAGLE-style
confidence-adaptive depth is a later policy experiment, not part of the first
fixed-M7 candidate.

The first candidate is intended to answer one question cheaply: does recursive
conditioning raise deep conditional agreement above the roughly 70% ceiling of
the current DSpark/Markov draft? It is not reasonable to promise 160 or 230
tok/s from the first head. With current cycle economics, a plausible first lift
to 45-55% overall draft-token acceptance corresponds to about 4.15-4.85 emitted
tokens/cycle before added draft cost, roughly a 100-125 tok/s opportunity. A
160 tok/s result needs about 6.2 emitted tokens/cycle at today's cycle cost.
Fixed M=8 cannot reach 230 tok/s at today's cycle cost even at perfect
acceptance; that milestone also requires a cheaper target cycle and/or a wider
verifier.

## Evidence and implementation seam

The design is pinned to the following target and record geometry:

- K160 target revision:
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- target: 43 layers, hidden size 4096, four MHC streams, three hash layers,
  vocabulary 129,280, and only one native next-token-prediction layer;
- current qualified record: 80.820052 tok/s on four B70s;
- current proposal/verification width: DSpark7 draft, exact M=8 K160 target
  verification;
- current diagnostic: 35.8149% draft-token acceptance, 3.507 emitted
  tokens/cycle on the combined DEV workload; public-continuity subset 30.2453%
  and 3.1172 emitted tokens/cycle;
- current marginal acceptance: 78.23%, 60.18%, 43.02%, 28.55%, 19.08%,
  13.19%, 8.45% at positions 1-7;
- current prose result: 28.72% draft-token acceptance and 3.010 emitted
  tokens/cycle.

Relevant implementation facts:

- `vllm/models/deepseek_v4/xpu/model.py` already marks the target as
  `SupportsEagle3`, stores configured auxiliary layer boundaries, reconstructs
  each selected post-MHC state with `hc_post`, reduces its four streams with
  `mean(dim=1)`, and returns auxiliary states beside target output.
- `vllm/models/deepseek_v4/xpu/dspark.py` fuses target states with
  `main_proj`/`main_norm`, prepares draft context KV, implements the draft model
  hooks, shares the target embedding/LM head, and maps full-vocabulary draft
  IDs identically to target IDs.
- The current draft pack selects zero-based target layers `[40, 41, 42]`; the
  runner converts these to post-layer boundaries `(41, 42, 43)`.
- The DSpark speculator produces seven IDs in a tensor shaped `[request, 7]`.
  Its proposal backbone runs all query slots in parallel; only a rank-256
  Markov logit bias sees the previously proposed token.
- The exact M=8 verifier and commit path are already proven on genuine
  sequential rows. The new drafter must not alter them.

Source anchors in the active development tree at design time:

- `xpu/model.py:1638-1732` -- EAGLE interface and auxiliary-state storage;
- `xpu/model.py:1813-1911` -- post-MHC tap capture and return;
- `xpu/dspark.py:62-160` -- DSpark feature fusion and three-stage draft;
- `xpu/dspark.py:203-239` -- parallel draft backbone output;
- `xpu/dspark.py:293-373` -- proposal-facing hooks and target ID mapping;
- `gpu/spec_decode/dspark/speculator.py:3-23` -- current parallel/Markov design;
- `gpu/spec_decode/dspark/speculator.py:586-811` -- seven-step Markov sampling;
- `gpu/spec_decode/dspark/speculator.py:813-841` -- proposal transaction;
- `gpu/spec_decode/eagle/eagle3_utils.py:35-58` -- auxiliary-layer semantics.

These are design references, not authorization to change those files in this
task.

## 1. Architecture

### 1.1 Target feature taps

Use post-layer boundaries **`[4, 22, 43]`** for the first K160 head:

- boundary 4: after zero-based target layer 3, the first ordinary layer after
  the three hash layers;
- boundary 22: a middle representation after zero-based layer 21;
- boundary 43: after the final target layer.

At each boundary, use exactly the target representation already exposed by the
V4 EAGLE seam:

```text
f_l(t) = mean_stream(hc_post(layer_l_state(t)))  in BF16[4096]
```

Do not silently substitute pre-MHC tensors, the flattened 4x4096 residual, or
the final normalized LM-head input. Training capture and inference must use the
same boundary definition and reduction.

`[4, 22, 43]` is a K160-specific engineering choice, not a proven optimum. It
keeps the EAGLE-3 low/mid/high principle while putting the low feature after the
special three-layer hash stack. The tiny pilot should capture a small superset
and compare these two alternatives offline before the full corpus is fixed:

- canonical-like boundaries `[2, 21, 40]`;
- late-heavy DSpark control `(41, 42, 43)`.

The ablation changes only the fusion input. Do not spend a frozen pack on tap
selection.

### 1.2 Minimal head

Recommended first head:

```text
three target features:       3 x 4096
per-feature RMSNorm:         frozen-shape, trainable scale
feature fusion:              Linear(12288, 2048), no bias
token path:                  frozen target embedding 4096
token projection:            Linear(4096, 2048), no bias
token/feature input fusion:  Linear(4096, 2048), no bias
recursive decoder:           1 dense causal transformer layer
draft width:                 2048
attention:                   16 query heads, 4 KV heads, head_dim 128
MLP:                         SwiGLU, intermediate 5504 initially
context:                     own causal KV, sliding window 128 initially
feature output adapter:      Linear(2048, 4096), no bias
output normalization:        RMSNorm
token head for pilot:        frozen/shared target LM head
```

At every step, concatenate the 2048-wide projected previous-token embedding
with the 2048-wide feature/recursive state, then apply the explicit
`Linear(4096, 2048)` input-fusion projection before the decoder layer. The
first step uses the fused target feature. Later steps use the projected
proposed-token embedding plus the recursively updated draft state. The layer is
dense: copying K160's MoE into the drafter would defeat the latency and memory
purpose.

The trainable pilot is approximately 100-130M parameters, depending on the
precise attention implementation. The frozen target embedding and LM head are
aliases, not another target copy. A production reduced-vocabulary head is a
separate latency optimization after the acceptance hypothesis passes:

- build a 48K or 64K vocabulary from training-only token counts;
- freeze the mapping before any frozen evaluation pack is materialized;
- require target-greedy vocabulary coverage >=99.5% overall and >=99.0% on
  disjoint prose DEV;
- fall back to full vocabulary if coverage fails;
- reduced vocabulary may lower acceptance but cannot alter correctness because
  every proposed ID is still target-verified.

The pilot deliberately uses the full target vocabulary and shared head to
avoid confounding the early depth result with vocabulary coverage. The full
head may be too expensive for the final 3 ms draft budget.

### 1.3 Seven-token autoregression

For a cycle ending at committed target position `t`:

1. Fuse K160 features `[f4(t), f22(t), f43(t)]` into draft state `z0`.
2. Combine `z0` with the embedding of the current committed token and run the
   one-layer head to obtain `q1`; greedily propose `d1 = argmax(q1)`.
3. Feed the embedding of `d1`, the cached draft KV, and the updated latent into
   the same shared layer to obtain `d2`.
4. Repeat recursively through `d7`.
5. Return exactly `[d1..d7]`; do not accept or emit any token in the drafter.

All seven positions share weights. For the first correctness implementation,
the draft KV is cycle-local scratch: create it from the committed prefix,
discard the entire seven-step scratch state after verification, and retain no
rejected suffix state. The target-owned rejection or all-accept bonus token is
committed only by the verifier; it enters the next target call, whose freshly
returned auxiliary features anchor the next draft cycle. This is simpler and
safer than partial draft-cache rollback. A later persistent-cache optimization
must prove token-for-token and state-transition equivalence against this
discard-and-refresh reference. The first implementation may run seven explicit
calls. The performance candidate should unroll those fixed calls into a
captured device transaction, but graphing is not allowed to change arithmetic
or state transitions.

This recursive latent/token update is the essential difference from the
current Markov path. Today, later slots receive a low-rank logit bias from the
previous token; they do not recompute a rich hidden representation conditioned
on the entire proposed prefix.

### 1.4 DSpark M-step and exact M=8 integration boundary

Reuse the existing DSpark transaction downstream of proposal production:

```text
K160 target feature return
        |
new EAGLE proposal producer -> draft_ids[1, 7]
        |
existing fixed-M7 target-input builder
        |
unchanged K160 forward on [current + seven drafts], width M=8
        |
existing target-owned greedy prefix comparison / rejection / bonus
        |
existing commit and counters
```

The new head must adapt to the existing proposal interface; the verifier must
not adapt to the head. In particular:

- target input width remains exactly eight;
- target token order and positions remain strictly consecutive;
- the unchanged K160 target computes all eight verification rows;
- accepted prefix length is derived only from target outputs;
- rejection emits the target token at the first mismatch;
- an all-accepted block emits the exact target bonus token;
- draft confidence and feature similarity are telemetry/policy inputs only;
- no draft-only acceptance is permitted.

## 2. DFlash, native MTP, DSpark, and EAGLE assessment

### What K160 already has

K160 declares one native MTP layer. Repeating that layer was tested and is
closed: the third proposal accepted only 0-3.2% and the endpoint fell to about
46.25 tok/s.

The attached official DSpark draft is substantially stronger and is already
DFlash-like:

- it consumes three target features;
- it projects one shared feature representation into every draft layer's
  context KV;
- it has three trained decoder stages;
- it predicts the seven-position block in one parallel backbone pass;
- it adds left-to-right dependence with a rank-256 Markov head.

This parallelism is why it can be fast. It is not, however, the same as a
recursively conditioned EAGLE state. Every slot begins from the same projected
target context, and only the small Markov correction sees the sampled prefix.
The diagnostic's strong P1 and compounding deep decay are consistent with that
conditioning bottleneck.

### Why EAGLE might win

A correct earlier token changes the complete hidden/KV state used for every
later proposal. That mechanism directly targets the observed failure: later
conditional acceptance, particularly prose, rather than P1 alone. Multi-level
features also give the draft access to more than the late-layer trio used by
the present pack.

Expected first full-corpus range, stated as a hypothesis:

- P1: 76-82%, ideally unchanged from DSpark;
- average conditional P2-P7: 78-88%;
- overall draft-token acceptance: 45-55%;
- emitted tokens/cycle: 4.15-4.85;
- prose emitted tokens/cycle: at least 3.6.

These numbers would validate the family but would not prove 160 tok/s.

### Why it might lose

- Seven serial dense draft calls can cost more than DSpark's single parallel
  backbone call plus Markov sampling.
- The existing post-MHC `mean(dim=1)` feature may discard information that a
  four-stream K160 draft needs.
- A 2048-wide dense layer may be too weak to follow a 180B MoE teacher for
  seven positions.
- The shared full-vocabulary target head may violate the 3 ms cycle budget;
  a reduced head may then lower prose coverage.
- EAGLE-3 literature results on other architectures do not establish the same
  result for hash-pruned K160 on B70.

DFlash/DSpark remains a valid alternative. If recursive EAGLE raises
acceptance but fails latency, the next design should transfer its training
signal into P-EAGLE/parallel EAGLE or a DFlash/DFlare-style per-layer feature
fusion, rather than making the head wider without an endpoint budget.

DEAGLE is useful later for confidence-based dynamic depth/tree allocation. The
first implementation stays a fixed linear chain because the production
verifier is exactly M=8 and fixed geometry is already optimized and proven.

Primary external references:

- EAGLE-3: <https://arxiv.org/abs/2503.01840>
- DFlash: <https://arxiv.org/abs/2602.06036>
- DEAGLE: <https://openreview.net/forum?id=eZRPb52ccA>

## 3. Training data

### 3.1 Data-generation principle

Train on greedy trajectories generated by the exact K160 teacher and replay
those trajectories teacher-forced to capture features efficiently. Do not use
arbitrary corpus continuations as labels: the labels should be tokens K160
itself would produce and therefore tokens the greedy exact verifier would
accept.

Every sample shard should contain:

```text
schema_version
target_revision, tokenizer_revision, source_id, source_revision
prompt_hash, trajectory_hash, generation_seed/settings
input_ids / target-generated continuation ids
position_ids, document boundaries, assistant/loss mask
feature_boundary_ids = [4, 22, 43]
features_bf16[token, 3, 4096]
target_final_hidden_bf16[token, 4096]
next_target_token_id[token]
EOS/reset markers
per-shard SHA-256 and row count
```

For anchor position `t`, draft label `j` is the teacher token `y[t+j]`, and
the optional feature target is the K160 final hidden state that predicts that
token, `h_target[t+j-1]`. Retain anchors only when all required shifted rows
remain inside the same generated continuation and before EOS. Near EOS, train
the valid prefix with an explicit per-position mask; never cross a document,
request, assistant turn, or reset boundary to manufacture seven labels.

Do not store full 129K logits in the default corpus. Hard next-token targets
match the greedy production objective and keep storage tractable. A small
calibration subset may retain top-128 teacher logits for loss ablation, but it
must use only training/DEV sources.

### 3.2 Prompt mixture

Use a source allowlist with stable revisions and licenses. Recommended token
mixture after K160 generation:

| Category | Share | Required coverage |
| --- | ---: | --- |
| prose | **45%** | dialogue, exposition, editing, summarization, long-form continuation, multilingual prose, style transfer |
| code | 15% | generation, repair, explanation, tests, multiple languages |
| math/reasoning | 15% | arithmetic, word problems, symbolic reasoning, concise and long solutions |
| extraction/tools | 15% | JSON, schema adherence, tables, entity extraction, tool-call-like outputs |
| low-locality | 10% | copying, reordering, transformations, nonrepetitive long-context retrieval |

Prose is intentionally the plurality because it is both the largest observed
DEV category and the weakest current category. Deduplicate by normalized prompt
and document hash before teacher generation. Hold out 10% of every source and
category as non-frozen DEV; split at document/source-group level, not row level.

### 3.3 Volume and storage

Three stages:

| Stage | Target-generated tokens | Approx. anchors | Purpose |
| --- | ---: | ---: | --- |
| tap/format smoke | 100K-250K | 80K-220K eligible | tensor alignment, tap choice, overfit proof |
| smallest signal milestone | 0.5M-1M | 0.4M-0.9M eligible | decide whether deep conditional acceptance moves |
| full candidate | 10M-20M | 9M-19M eligible | train a reviewable endpoint candidate |

Three BF16 features plus one BF16 final teacher state cost 32 KiB/token before
container overhead: about 32 GB per 1M tokens and 320-640 GB for 10-20M. Shard
at 2-8 GB, use memory-mappable safetensors or an equivalently checksummed
format, and test per-vector INT8+scale compression on the smoke set. Promote
compressed capture only if its trained/offline acceptance matches BF16 within
0.5 percentage point overall and at every position.

### 3.4 Frozen-pack isolation

The frozen evaluator packs are not training data, DEV data, vocabulary data,
or router data.

- Do not open, read, hash, list individual contents, or pass Pack A/B paths to
  data generation.
- Explicitly exclude the public 12-prompt continuity suite and
  `data/dspark7-draft-acceptance-dev-suite-v1.json` from training by path and
  source namespace. They remain diagnostics.
- Freeze training source IDs/revisions, all prompt/document hashes, split
  hashes, target generation settings, tap IDs, vocabulary mapping, weights,
  code, and policy before Pack A is materialized.
- Any candidate change after that spends Pack A. Pack B is materialized only
  after A and runs the unchanged candidate in reversed launch order.

This is stronger than trying to compare against unseen pack text: the packs
must not be consulted at all.

## 4. Training recipe

### 4.1 Objective

Roll the shared head out for all seven positions during training. In the first
offline implementation, teacher-force the exact K160 previous token at every
position. This matches the quantity that matters for exact speculative
decoding: the probability of draft position `j` being correct conditional on
all earlier draft tokens matching K160. Once an earlier token is wrong, later
tokens in that cycle cannot be accepted, so training them against target states
captured from a different prefix would be invalid rather than useful exposure
to the inference distribution.

For draft position `j`:

```text
L_j = w_j * (
        CE(draft_logits_j, K160_greedy_token_j)
        + 0.10 * SmoothL1(RMS(P_out(z_j)), stopgrad(RMS(h_target_j)))
        + 0.05 * (1 - cosine(P_out(z_j), stopgrad(h_target_j)))
      )
```

Starting position weights, normalized to keep their mean at one:

```text
raw w = [1.00, 1.00, 1.10, 1.25, 1.40, 1.60, 1.80]
```

The later weighting reflects the diagnosed P3-P7 failure, but P1 retains full
weight. Do not use a later-heavy schedule that drops P1 below the current
76.36% public-continuity baseline. Run one feature-loss ablation on the small
DEV set: EAGLE-3's direct-token-only objective is the control, and the feature
regularizer survives only if it improves conditional depth or convergence.

Validate each checkpoint two ways: teacher-forced per-position accuracy exposes
the conditional depth directly, while a full greedy seven-token rollout gives
the actual marginal acceptance and emitted-tokens/cycle estimate. An optional
later on-policy training branch is valid only if K160 features and targets are
recaptured for the changed prefix, or if every loss after the first draft
divergence is masked. Never pair the original teacher-prefix hidden states or
next-token labels with a draft-generated divergent prefix.

Loss masks cover target-generated assistant/continuation tokens only. Prompt,
padding, cross-document, and post-EOS positions are masked.

### 4.2 Optimizer and steps

Starting configuration:

```text
dtype:                  BF16 forward/backward; FP32 optimizer state
optimizer:              AdamW
betas:                  (0.9, 0.95)
epsilon:                1e-8
learning rate:          2e-4 pilot; 1e-4 full run
weight decay:           0.05 (no decay on norm/scales)
schedule:               cosine decay to 10% of peak
warmup:                 3% of optimizer updates
gradient clipping:      global norm 1.0
packed sequence:        1024 initially, then 2048
anchors/update:          8K initially
supervised positions:    up to 56K/update (7 shifted labels per anchor)
checkpoint:             every 250 updates plus best non-frozen DEV checkpoint
```

Pilot: 500-1,500 optimizer updates, stopping early once the tiny corpus is
clearly learned. Full candidate: target about three passes over 9M-19M eligible
anchors. At 8K anchors/update, this is roughly 3,375-7,125 updates, 27M-57M
anchor exposures, and at most 189M-399M supervised draft-position exposures.
Validate every 250 updates. Select by a preregistered score combining overall
conditional P2-P7, prose emitted tokens/cycle, and P1 preservation, not
training loss alone.

### 4.3 Compute and time

The dense head fits comfortably on a 32 GB B70 without the target loaded. The
safe sequence is:

1. TP4 K160 target generation and feature capture;
2. stop and unload K160 completely;
3. verify all four allocators are free;
4. load only the verified frozen target embedding and LM-head tensors (or their
   tensor-parallel shards) by exact checkpoint tensor name and hash;
5. four-card data-parallel head training.

Do not co-reside head training with the 96 GiB K160 target. No transformer,
attention, MoE, or expert target weights belong in the training process. The
training checkpoint excludes the frozen embedding/head tensors and pins their
source hashes; at runtime the draft pack aliases the already loaded live K160
tensors after the same hash checks.

Conservative estimates, to be replaced by the first measured 100-step smoke:

- 0.5M-1M token milestone: 3-8 hours teacher generation/capture plus 1-3 hours
  head training; allow one working day including validation and XPU fixes;
- 10M-20M token corpus at the 43.8 tok/s single-session target control would
  take about 2.6-5.3 days for generation alone;
- batched generation plus teacher-forced feature replay may reduce full data
  production to roughly 12-36 hours, but that is an estimate, not a measured
  B70 result;
- full head-only training: approximately 4-12 hours if PyTorch XPU BF16/DDP
  kernels behave normally; data I/O may dominate.

The official/open Speculators training path is CUDA-first. If the 100-step XPU
smoke fails correctness, unsupported backward kernels, or scaling, export the
already captured BF16/INT8 shards and train the head on 2-4 H100/A100-class
GPUs. Target feature generation must still use the exact K160 teacher. Do not
spend days porting training kernels before the small acceptance hypothesis is
tested.

## 5. Loading, integration, and exactness gates

### 5.1 Draft pack and guard

Package the trained head separately from K160. Required manifest fields:

```text
format/schema version
method = dspark_eagle3_k160 (provisional name)
default_enabled = false
target and tokenizer path-independent revisions/hashes
vLLM/XPU/oneCCL commits used for capture and integration
tap boundary IDs and exact feature reduction
eagle_aux_hidden_state_layer_ids = [4, 22, 43]
head architecture, dtype, vocabulary maps, weight hashes
training source/split manifest hashes
M=7 proposal / M=8 target verification declaration
policy/confidence hash and allowed inputs
offline metric report hash
```

Enable only through an explicit experimental method/config selector. No
environment flag may silently replace ordinary DSpark. Fail closed on target
revision, tokenizer, hidden size, tap count, vocabulary map, verifier width,
or head hash mismatch. These are post-layer boundary IDs in the target's
EAGLE-aux interface. They correspond to zero-based target layers `[3, 21, 42]`;
they must never be interpreted as DSpark's zero-based layer IDs. The loader
must resolve both representations, verify the returned boundary tags are
exactly `[4, 22, 43]`, and refuse an untagged or ambiguous feature tuple.

### 5.2 Gate order

1. **Offline format gate:** captured feature boundaries, shapes, positions,
   target IDs, EOS, and shard hashes agree with a tiny independent replay.
2. **Offline predictor gate:** disjoint non-frozen DEV metrics meet the
   thresholds in section 6 before integration.
3. **Proposal interface gate:** exactly seven deterministic target-vocabulary
   IDs are produced; no stale rows across changing inputs.
4. **Target provenance gate:** every accepted ID has an explicit matching K160
   verifier row in the same cycle.
5. **Greedy equivalence gate:** speculative output token IDs equal same-build
   target-only greedy IDs 100%; no text-only comparison.
6. **State gate:** rejection rollback, all-accept bonus, early EOS,
   cancellation, reset, alternating context, prompt boundaries, and repeated
   request lifecycle pass.
7. **Four-card replay gate:** at least 128 ordered changing captures, including
   positions 28 and 58, pass on every rank; no stale sentinel, hang, deadlock,
   timeout, worker restart, or rank disagreement.
8. **Cycle-cost gate:** measure draft, policy, verify, and commit separately on
   the same workload. Acceptance without complete-cycle improvement is a
   rejection.
9. **Frozen contract gate:** run the freeze-before-reveal protocol exactly as
   written, only after the candidate manifest is immutable.

Hard contract requirements include `cached_tokens=0`, unique random request
IDs, disabled prefix/history/n-gram/response reuse, target logprobs at at least
64 positions, two packs, reversed Pack B launch order, and two complete
leak-free repetitions. Each pack contains exactly 48 short normal requests
(12 code, 10 math, 20 mixed, 6 tools) spanning prompt-token buckets 32-128,
129-512, and 513-900 and output-token buckets 8-48, 96-192, and 256-512, plus
16 nonrepetitive long-context requests at 2048/4096 context. Labels must not be
sent to the server, and request order is randomized only after the candidate
is frozen. Router inputs, if added later, are limited to the contract's allowed
pre-target inputs. Prompt ID/hash, category labels, saved outputs, future
target state, and manual per-request routes are forbidden.

Required trace fields are `request_id`, `cycle`, `context_length`,
`generated_position`, `proposed_depth`, `accepted_prefix_length`,
`emitted_tokens`, `rejection_or_bonus`, `policy_mode_and_pre_target_inputs`,
`draft_policy_verify_commit_time_ms`, `target_cycles`, and `verifier_width`.
Store them per cycle without exposing evaluator labels to the endpoint.

## 6. Evaluation protocol and thresholds

### 6.1 Metrics

For cycle count `D` and accepted-through-position counts `A1..A7`, report:

```text
marginal_i       = Ai / D
conditional_1    = A1 / D
conditional_i    = Ai / A(i-1), i > 1
draft acceptance = sum(Ai) / (7D)
emitted/cycle    = 1 + sum(Ai) / D
```

Also report per-category and overall target cycles, run-length histogram,
draft/policy/verify/commit milliseconds, TTFT, generated tokens 1-100 tok/s,
full-512 tok/s, wall tok/s, output/prompt hashes, and exact identity.

### 6.2 Before frozen reveal

Use only preregistered non-frozen DEV sets. The public continuity suite remains
a continuity screen, never a promotion headline.

Smallest-milestone signal gate:

- P1 >=76%;
- mean conditional P2-P7 >=75%;
- at least four of P2-P7 individually above 72%;
- overall draft-token acceptance >=40%;
- no target-token alignment or rollout mismatch.

Full offline integration gate:

- P1 no worse than 76.36%;
- average conditional P3-P7 >=78%, with no position below 72%;
- overall draft-token acceptance >=45%;
- emitted tokens/cycle >=4.15 overall;
- prose emitted tokens/cycle >=3.60;
- a lower-quality tap/head cannot be selected for latency before it passes
  these acceptance gates.

Four-card development gate:

- all exactness/state gates pass;
- draft plus policy <=3.0 ms/cycle;
- emitted tokens/cycle >=2.2 overall and >=2.0 mixed (contract floor), while
  this project additionally requires >=4.15 overall to justify the head;
- continuity/DEV median >84.861 tok/s (5% over 80.820052) before spending a
  frozen pack;
- engineering target >=90 tok/s with positive paired improvement.

### 6.3 Freeze-before-reveal promotion

Freeze the candidate manifest before Pack A materialization. Run paired
same-build controls:

- target-only, no speculation;
- current target-verified MTP1;
- fixed EAGLE candidate.

Pack B is materialized after Pack A and runs the unchanged candidate in reverse
launch order. Promotion requires every hard correctness/cache gate plus:

- >=5% improvement over same-build MTP1 for pack wall time;
- >=5% improvement over same-build MTP1 median decode throughput;
- >=3% mixed-workload improvement;
- paired-bootstrap 95% lower bound above zero;
- no category or long-context p10 regression greater than 5%;
- two independent packs and two complete repetitions without state leak;
- candidate median above the 80.820052 record, with >84.861 tok/s the
  preregistered meaningful-record threshold.

### 6.4 160/230 economics

Using the public diagnostic's 3.117 emitted tokens/cycle and the 80.65 tok/s
same-recipe confirmation gives an approximate complete cycle of 38.6 ms. At
that cost:

- 100 tok/s needs about 3.86 emitted tokens/cycle;
- 160 tok/s needs about 6.18 emitted tokens/cycle, or about 74% mean marginal
  acceptance across seven drafts;
- if P1 is 82%, reaching 6.18 emitted/cycle requires roughly 96-97%
  conditional survival at each later position;
- perfect M=8 acceptance caps throughput near 207 tok/s;
- 230 tok/s needs <=34.8 ms even with perfect eight-token emission, or a wider
  verifier; at a more plausible 6.2 emitted/cycle it needs about 27.0 ms.

Therefore EAGLE is a credible route to materially higher acceptance and the
100+ region. A 160 result requires an exceptional head plus cycle-cost parity.
A 230 result is a joint target-verifier/draft-width program, not an acceptance
claim for this fixed-M8 head.

## 7. Risks and smallest first milestone

### Smallest decisive milestone

Do this before building production loaders or XPU kernels:

1. Capture 100K-250K tokens with a superset of the three proposed tap sets on
   training-only prompts, with at least 50% prose.
2. Validate feature/target alignment and freeze a tiny train/DEV split.
3. Train the `[4,22,43]`, width-2048, one-layer, shared-full-head pilot for
   500-1,500 updates; run the two tap alternatives only long enough for a fair
   early curve.
4. Roll out seven tokens entirely offline on disjoint K160 DEV traces.
5. Continue only if mean conditional P2-P7 exceeds 75% (clearly above the
   approximately 70% present ceiling), P1 remains >=76%, and overall acceptance
   reaches 40%.
6. Expand to 0.5M-1M tokens and require the 45%/4.15 emitted-cycle integration
   gate before any runtime integration.

This milestone tests the architectural hypothesis with no verifier or endpoint
changes. Failure is cheap and informative.

### Risk register

| Risk | Early test | Response |
| --- | --- | --- |
| Mean-pooled MHC features lose critical state | tiny tap/reduction ablation | test learned four-stream compression only if mean pooling misses the signal |
| Recursive quality improves but seven calls exceed 3 ms | isolated fixed-M7 head timing after offline gate | distill to reduced vocab, capture fixed transaction, or pivot to P-EAGLE/DFlash |
| Width 2048 is too weak | train/DEV scaling curve | try width 3072 only after the latency envelope is measured |
| Later weighting damages P1 | per-position validation every checkpoint | cap/anneal deep weights; P1 gate is hard |
| Prose remains weak | 45% prose mix and prose-only DEV | add diverse prose sources, not prompt-specific routing |
| Reduced vocabulary drops rare prose tokens | training-only coverage audit | use 64K or full vocabulary |
| Feature shards dominate disk/I/O | BF16 vs vector-INT8 pilot | use checksummed vector quantization only within 0.5 pp acceptance |
| XPU training stack is immature | 100-step BF16/DDP smoke | train head off-host; preserve K160-generated features |
| Draft KV rollback/capture state is stale | ordered rejection/EOS/reset tests | fail closed to current DSpark or target-only |
| K160 teacher is an experimental hash-pruned artifact | pin revision and label all results | do not generalize the head to official/full V4 without retraining |
| Offline acceptance does not translate to endpoint | complete-cycle measurement | reject on net tok/s even if acceptance rises |

## Execution checklist once GPUs are free

1. Verify live-state authority, source commits, no other GPU work, endpoint
   state, and allocator state.
2. Freeze the non-frozen source allowlist and exclude public DEV/continuity
   assets. Do not access held-out packs.
3. Implement a default-off capture-only path for exact boundary features; test
   16 tokens before bulk generation.
4. Generate the 100K-250K smoke corpus with exact K160 identity and checksums.
5. Stop/unload K160; verify all four cards are free.
6. Run a 100-step XPU training compatibility smoke; offload head training if
   correctness or kernel support fails.
7. Train/evaluate the smallest milestone and apply the hard no-go thresholds.
8. Only after it passes, generate 0.5M-1M tokens, retrain, and apply the 45%
   acceptance/4.15 emitted-cycle gate.
9. Only after that, implement the guarded proposal adapter and run exactness,
   rollback, four-card, and <=3 ms cycle gates.
10. Freeze the complete candidate manifest before any Pack A reveal. Run Pack
    A and unchanged reverse-order Pack B exactly under the contract.

No LocalMaxxing submission is authorized by this plan. A result is promotable
only after the frozen contract and same-build controls pass.
