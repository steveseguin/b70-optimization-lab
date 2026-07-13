# Target M=6 GPU-resident greedy verification boundary

Date: 2026-07-13

## Decision

For the fixed greedy realistic suite, the target-side DFlash verifier should
return six exact **policy-adjusted** token IDs, not six full vocabulary rows. Those
six IDs are a complete sufficient statistic for the existing greedy acceptance
rule:

```text
target input rows:  [seed, draft0, draft1, draft2, draft3, draft4]
target picks:       [pick0, pick1, pick2, pick3, pick4, bonus5]

accept draft[i] while pick[i] == draft[i]
first mismatch i: emit draft[0:i], then pick[i]
all five match:    emit draft[0:5], then bonus5
```

The first safe implementation should classify the exact active bias policy,
append an all-six-row device argmax to the existing target
LM head, copy only `I32[6]` to the host, and run the same prefix/bonus and
sampler-state updates there. This removes the current
`6 * 248320 * sizeof(float) = 5,959,680` byte full-logit D2H and the creation of
1,489,920 host candidate records per cycle. It deliberately leaves the full
GPU logit tensor in place for the first parity step.

After that boundary proves exact, generalize the already validated Xe2 Q6_K
fused top-1 path from DFlash draft rows 1..5 to target rows 0..5. That second
step removes the full `[248320, 6]` GPU logit materialization as well. Do not
merge acceptance/state mutation into the first kernel change; six IDs are a
small, auditable interface and make rollback parity easy to prove.

### Correction: the current strict identity is raw greedy

The Qwen server startup logs identify five EOG tokens and precompute an
infinite negative bias for each:

| Token | ID |
|---|---:|
| `<|endoftext|>` | 248044 |
| `<|im_end|>` | 248046 |
| `<|fim_pad|>` | 248063 |
| `<|repo_name|>` | 248064 |
| `<|file_sep|>` | 248065 |

For example,
`/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/q6top1-jit-gpu2-port19446-20260713.log:146-150`
records the token IDs and lines 460-464 record the `-inf` biases. The source
constructs this model-specific EOG list in `common/common.cpp:1274-1286`;
request evaluation can add it to the active bias set in
`tools/server/server-schema.cpp:451-460`. Arbitrary request `logit_bias` values
are parsed separately at `tools/server/server-schema.cpp:410-449`, and the CPU
sampler applies them before the remaining chain in
`src/llama-sampler.cpp:3442-3473`.

Those startup entries are only `logit_bias_eog` metadata. They become active
sampler biases when a request explicitly sets `ignore_eos`; the unchanged
strict realistic payload does not do so and its effective `logit_bias` vector
is empty. The current strict identity is therefore raw greedy, not masked
greedy. The previous version of this note incorrectly inferred active request
semantics from startup precomputation.

The implementation has two separately keyed exact modes:

- empty active `logit_bias` -> raw argmax;
- exactly the five unique EOG IDs above, each with `-inf` bias -> masked
  argmax for explicit `ignore_eos`.

Any different, duplicate, finite, or request-specific bias fails closed to
ordinary logits and CPU sampling. Eligibility must always inspect the active
request sampler parameters, never the existence of the startup EOG list.

This is a necessary cycle reduction, not by itself the 100 tok/s solution. The
serialized target trace attributes about 3.303 ms to the target vocabulary
head. Even deleting it completely would not close the full gap. The value is
that this is a measured, reusable boundary on the critical M=6 verifier and it
removes work that grows with vocabulary size.

## Source identities reviewed

- protected llama.cpp: `e3546c7948e3af463d0b401e6421d5a4c2faf565` plus the
  guarded dirty experiment stack present on 2026-07-13;
- hipfire: `d44f89e7f00f807962e0eb61a1790151a514cb83`;
- no protected llama.cpp source was changed for this design audit.

## Current llama.cpp target dataflow

### Width-six graph and raw-logit extraction

`tools/server/server-context.cpp:447-480` builds the target verifier batch.
When five draft tokens are present, it marks all six tokens as outputs and
records six `spec_i_batch` indices. Qwen's target graph then performs final
RMSNorm and the shared output projection in `src/models/qwen35.cpp:209-227`:

```text
result_norm [5120, 6]
  -> build_lora_mm(output.weight, ..., output_s)
  -> result_output / t_logits [248320, 6] F32
```

`src/llama-context.cpp:1920-1935` says raw logits are required whenever an
output sequence has no backend sampler. The target server sampler is CPU-side
by default (`common/common.h:292`; `common/arg.cpp:2055-2061`), so
`src/llama-context.cpp:2183-2195` asynchronously copies all six FP32 rows to
the context's host logit storage.

Enabling generic backend sampling is not a substitute. In
`src/llama-graph.cpp:3469-3496`, `seq_to_logit_row[seq_id]` keeps only one row
per sequence. All six verifier outputs belong to the same sequence, so that
interface cannot return six per-position picks without a DFlash-specific
multi-row result.

### Host sampling and acceptance

For each verifier row, `common/sampling.cpp:130-159` expands the raw row into
one `llama_token_data` record per vocabulary token. `common_sampler_sample()`
then synchronizes the context, applies reasoning/grammar/sampler transforms,
and returns the selected ID (`common/sampling.cpp:540-621`).

`common_sampler_sample_and_accept_n()` at `common/sampling.cpp:624-651` is the
exact acceptance rule. It samples rows 0 through 4 in order, calls
`common_sampler_accept()` for each selected target ID, stops at the first draft
mismatch, and samples row 5 only after all five drafts match. The returned
vector therefore always contains:

- zero or more target-verified draft tokens; and
- one replacement token at the first mismatch, or one row-5 bonus token after
  full acceptance.

The caller in `tools/server/server-context.cpp:3795-3864` clones sampler state
before verification, computes rollback from the returned vector size, restores
the speculative checkpoint and cloned sampler when required, and otherwise
passes only `accepted.size() - 1` to `common_speculative_accept()`.

The subsequent commit path at `tools/server/server-context.cpp:3870-3926` is
important and must not be simplified accidentally:

- it removes all five proposed draft tokens from the prompt;
- it reinserts only `ids[0..end-1]`, the accepted draft prefix;
- it sets `slot.sampled = ids.back()`, the replacement or bonus;
- it trims target and draft memory to the accepted-prefix boundary; and
- it emits every ID, including the replacement/bonus.

The final replacement/bonus is the seed for the next target decode. It is not
already inserted into `slot.prompt.tokens` at this point. This is why the state
contract is `accepted draft count` plus `next token`, not simply “number of
emitted tokens.”

## hipfire comparison

hipfire already uses this boundary for greedy DFlash.
`crates/hipfire-arch-qwen35/src/speculative.rs:2264-2275` defines verifier
output as `argmax_per_pos`, with full logits populated only when a sampled path
needs distributions. In its batched vocabulary-head path,
`speculative.rs:2654-2698` keeps logits on the GPU, runs batched argmax, and
downloads only `4 * B` bytes for greedy operation. Full logits are downloaded
only for sampling or host-side repeat-penalty/ngram processing.

`speculative.rs:3758-3792` sends those picks to the shared
`accept_greedy_prefix()` helper. Its implementation in
`crates/hipfire-runtime/src/spec.rs:78-137` accepts the longest matching draft
prefix and appends `target_pick[accepted]` as the replacement or bonus. This is
the same information boundary as llama.cpp's current greedy path.

The transferable idea is not Rust or HIP-specific: keep target distributions
resident and return compact decisions. hipfire also shows the correct fallback
rule: requests with temperature sampling, repeat penalties, or n-gram blocking
continue to use the distribution path unless those transforms themselves move
to the GPU.

hipfire's plain greedy argmax maps directly to the unchanged strict request's
empty active bias policy. Explicit `ignore_eos` still requires applying the
five immutable EOG bans before compact IDs are produced. The transferable
boundary is “exact target picks on device,” with the active request policy
included in the graph key.

## Exact compact contract

### Stage-one device result

Use a distinct target result, not the existing draft result:

```cpp
struct dflash_verify_top1_result {
    int32_t ids[6]; // policy-adjusted picks, row 0..5 in target output-row order
};
```

The minimum host-visible output for the first implementation is 24 bytes.
Keeping all six IDs is preferable to immediately returning an acceptance
count: it permits direct row-by-row comparison against the ordinary path and
keeps all sampler and rollback mutation in existing host code.

The existing `t_dflash_top1` contract is deliberately different. The draft
graph in `src/models/dflash.cpp:262-286` excludes row 0 and returns only rows
1..5 as `I32[5]`; the current Xe2 matcher and kernel in
`ggml/src/ggml-sycl/ggml-sycl.cpp:6809-6906` and
`ggml/src/ggml-sycl/mmvq.cpp:22-212` likewise hard-code five rows. Reusing that
name or five-element storage for the target would create an off-by-one bonus
hazard. Add a separate `t_dflash_verify_top1`/six-ID context result.

### Host acceptance helper

Add a compact equivalent of `common_sampler_sample_and_accept_n()` whose input
is `target_ids[6]` plus `draft[5]`. It should:

1. append `target_ids[i]` and call `common_sampler_accept(..., true)` for each
   matching row;
2. on the first mismatch, append and accept `target_ids[i]`, then stop;
3. if all drafts match, append and accept `target_ids[5]`;
4. return the same vector shape as the existing function.

Calling `common_sampler_accept()` remains mandatory even under the fixed-mask
greedy guard. It advances the sampler chain and `prev` ring
(`common/sampling.cpp:444-465`), preserving future behavior and leaving the
existing clone/checkpoint rollback path valid.

### Later minimum result

Only after six-ID parity is established may device-side prefix comparison
reduce the D2H result to:

```cpp
struct dflash_greedy_decision {
    uint32_t accepted; // 0..5, excludes replacement/bonus
    int32_t  next;     // mismatch replacement or full-accept bonus
};
```

The host already owns the five draft IDs and can reconstruct
`draft[0:accepted] + next`. This eight-byte boundary is only useful once draft
IDs also remain in a fixed device buffer; uploading five host IDs merely to
save 16 D2H bytes has no value. It is a later persistent-cycle cleanup, not the
first integration target.

## Numerical semantics that must remain exact

“Greedy” alone is not a sufficient guard. For the strict server identity, the
compact path is valid only when the selected target ID is exactly the raw
output-projection maximum. The separate explicit-`ignore_eos` identity selects
the maximum after the immutable five-ID `-inf` mask is applied.

The fixed suite requests `temperature=0` and `top_p=1` in
`scripts/bench-openai-realistic-suite.py:31-49`. With the current default
parameters, repetition/frequency/presence and DRY penalties are identities,
XTC is disabled, typical-p is disabled, top-n-sigma is disabled, and top-k and
min-p retain the maximum allowed token. The temperature implementation
(`src/llama-sampler.cpp:265-281`) scans in token-ID order with strict `>`;
therefore equal maxima select the lowest token ID.

Implement one explicit predicate, for example
`common_sampler_is_fixed_masked_argmax_exact()`, and require all of the
following:

- native DFlash, one active sequence, five drafts, six target output rows;
- `temp <= 0`, dynamic temperature disabled, mirostat disabled, and no adaptive
  or infill sampler;
- no grammar/tool schema or reasoning-budget transform;
- the effective active logit-bias set is either empty (raw mode) or exactly the
  canonical immutable `-inf` mask `{248044, 248046, 248063, 248064, 248065}`
  (explicit-`ignore_eos` mode), with no finite, duplicate, dynamic, or
  request-specific bias;
- identity repetition/frequency/presence and DRY penalties;
- XTC disabled, typical-p disabled, top-n-sigma disabled, `top_p == 1`;
- only maximum-preserving top-k/min-p stages before temperature;
- `n_probs == 0` and no OpenAI logprobs/probability payload request;
- no LoRA adapter or unhandled `output_s` transform on the output projection.

The last condition may be relaxed only by placing the exact `output_s` and
LoRA operations before the device mask and argmax. The matcher must inspect
the actual graph, not assume `build_lora_mm()` is a bare Q6_K multiply.

On any failed condition, missing compact tensor, wrong shape/type, graph mode
incompatibility, unsupported weight layout, or backend dispatch failure, use
the existing full-logit path. A mask mismatch is also a hard fallback, even if
none of the five fixed IDs happened to win in a sample run. The fast path must
never silently change a sampled, penalized, grammar-constrained, dynamically
biased, or logprob-returning request into the fixed-mask greedy policy.

For the fused Xe2 kernel, exactness means:

- the same final-normalized FP32 activation rows consumed by production;
- the same Q8 activation quantization and Q6_K decode/scale semantics;
- the same effective output scaling and adapter behavior;
- exclusion of all five immutable banned IDs before local or final top-1
  reduction;
- deterministic reduction; and
- lowest-token-ID selection among allowed tokens for exactly equal top logits.

Full logits need not be bit-identical if the six selected IDs are identical,
but promotion requires zero ID mismatches. Record top-1/top-2 margins and
fused/reference top-1 deltas in the fixture comparator so a numerically fragile
pass is visible rather than hidden.

## Staged implementation

### Stage 0: prove the compact boundary with the ordinary target head

1. Add a target-only cparam and graph-result pointer, distinct from
   `dflash_top1_ids`, in `src/llama-cparams.h`, `src/llama-graph.h`, and the
   graph-key comparison. Key raw and exact-five-EOG-mask modes separately so a
   graph captured for one policy cannot replay for another.
2. In `src/models/qwen35.cpp`, only for an eligible six-row DFlash verifier,
   append `ggml_argmax` over all six final output rows in raw mode. In the
   separately keyed explicit-`ignore_eos` mode, first apply the five sparse
   `-inf` bans. Expose `I32[6]` and leave the ordinary output projection
   unchanged.
3. Add six-ID async-copy/read storage in `src/llama-context.{h,cpp}`. When the
   compact target result exists, skip the raw-logit copy at
   `src/llama-context.cpp:2183-2195`.
4. Add the compact host helper beside
   `common_sampler_sample_and_accept_n()` and select it in
   `tools/server/server-context.cpp:3807-3814` only after the request-level
   exact-policy predicate passes.
5. Preserve the current sampler clone, rollback calculation,
   `common_speculative_accept(accepted.size()-1)`, prompt insertion, memory
   trimming, and `slot.sampled` handling unchanged.

This stage removes full-vocabulary D2H and host candidate materialization. It
does not yet remove `[248320,6]` GPU logit writes.

### Stage 1: fuse the target Q6_K head to six top-1 IDs

1. Capture real **target** M=6 `result_norm` activations and the six production
   policy-adjusted IDs. Retain raw and masked reference top-1 IDs so the
   explicit-`ignore_eos` fixture can prove the mask is actually exercised. The existing fixture is from the
   DFlash draft decoder and only validates useful rows 1..5; it is not
   sufficient for target row 0 or the row-5 full-accept bonus contract.
2. Generalize the existing Q6_K Xe2 packed-weight kernel from five useful
   draft rows to all six target rows. The GGUF is predominantly Q4_0, but its
   `output.weight` is Q6_K. Raw mode admits all IDs. The masked mode excludes
   the five banned output IDs before each local maximum is admitted to the
   reduction.
3. Match the exact target graph ending in the keyed five-ID mask and all-six-row
   argmax. Reject other masks, consumers, output transforms, adapters, shapes,
   devices, and layouts.
4. Write only `I32[6]`; do not allocate or write the full logit tensor on the
   matched execution path. Preserve ordinary graph fallback.
5. Reuse the expanded Q6_K output-head pack already created at model load. Do
   not repack the 1.36 GB mirror for each test. Record the device-memory cost
   of coexistence with the ordinary output weight while required fallback
   remains available.

### Stage 2: integrate, measure, and keep only a real cycle win

Run same-build, same-GPU A/B/A/B crossovers with the strict 12-prompt cold
suite. Record compact dispatch/fallback counts, target-verifier time, DFlash
draft time, acceptance per position, emitted tokens per cycle, output hashes,
and full run identity. The compact path must not change acceptance merely
because draft and target happened to emit the same final text.

### Stage 3: optional device-side accept decision

After Stage 2, keep draft IDs and target IDs in fixed device buffers, compare
the five pairs on-device, and copy `{accepted, next}`. Preserve host-side
`common_sampler_accept()` and the existing context rollback/commit sequence.
This is justified only if profiling still shows a measurable host boundary;
24-byte D2H alone is not a target.

## Go/no-go gates

Correctness is unconditional:

- zero mismatches across all six rows of captured target fixtures;
- zero differences in per-cycle proposed, accepted, replacement/bonus, and
  emitted token arrays across the full strict suite;
- identical output token hashes and stop behavior;
- explicit forced tests for mismatch positions 0, 1, 4, and full acceptance;
- synthetic rows where each banned ID is raw top-1 and the masked reference
  must select the next allowed ID, including lowest-ID tie cases;
- a test that reordered fixed entries canonicalize to the same graph identity;
- fallback-path tests for a missing/wrong/ambiguous-duplicate fixed mask, any
  request-originated or additional finite/`-inf` bias, temperature sampling, penalties,
  grammar/tools, logprobs, wrong width, and non-Q6_K target output weights.

The decisive fused-boundary microbenchmark gate is:

- B70 AOT, real target M=6 activations, warm persistent pack;
- median of at least 100 iterations after 20 warmups;
- include activation quantization, output-head work, top-1 reduction, and the
  24-byte result read in both measured boundaries;
- apply the same canonical five-ID mask in candidate and reference;
- fused six-row boundary `<= 2.75 ms` **and** at least `1.20x` faster than the
  exact production full-logit-plus-mask-plus-argmax comparator.

At the measured 3.303 ms target vocabulary head, this requires at least about
0.55 ms of isolated saving rather than a launch-count-only result. If it misses
either latency threshold, preserve the experiment and stop kernel tuning unless
profiling identifies a specific fix.

Stage 0 has a separate integration gate because it is the semantic scaffold:
the compact post-head path must save at least 0.50 ms per DFlash cycle in the
measured `target decode complete -> accepted vector ready` interval, with exact
parity. If it does not, do not promote Stage 0 alone; proceed only as a fixture
and correctness harness for the fused Stage 1 boundary.

Finally, keep the fused implementation only if the strict AOT crossover gains
at least 1.5% median throughput without a p10 regression or acceptance change.
Anything smaller is useful infrastructure, not progress toward 100 tok/s.
