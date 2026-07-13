# DFlash strict-suite acceptance gap audit

Date: 2026-07-13

Status: read-only source, artifact, and result audit. No GPU server was run and
no llama.cpp, DFlash, or hipfire source was changed.

## Conclusion

The strict-suite acceptance gap is not explained by the local DFlash
checkpoint, tokenizer, feature-layer indexing, or draft weight quantization.
The one unresolved contract difference is important: the draft was trained at
B=16 and hipfire's daemon uses B=16, while native DFlash5 runs a six-position
block. Because draft attention is bidirectional, block width can change even
the early logits; it needs a direct B=6/B=9/B=16 acceptance-only test. The
strongest evidence against a broader runtime bug is an independent corrected vLLM
run on the same 12 no-thinking prompts: it emitted `2.7316` tokens per
speculative step, essentially the same as the native llama.cpp records at
`2.704-2.732` tokens per cycle. Different target quantization and a different
runtime reproduced the same acceptance ceiling.

Hipfire's much higher DFlash acceptance is primarily a prompt/output-
distribution result. Its high daemon rows use ChatML with a structured
thinking prefix, while its raw peak is a highly favorable code continuation.
Our promotion contract is twelve unique engineering/operational instructions
with thinking explicitly disabled. Hipfire itself records large acceptance
swings from prompt bytes, genre, and thinking mode.

Therefore the fastest credible path is:

1. close the B=16 and numerical-runtime doubts with a block-logit parity
   oracle;
2. adapt the draft on disjoint, target-owned traces matching the no-thinking
   strict distribution;
3. if a small adapter cannot meet the emitted-token gate, distill the full
   five-layer B=16 draft and pair it with the width-specialized verifier.

Additional Q4/Q8 draft sweeps, longer blocks with the current draft, or prompt
changes cannot deliver the strict `100 tok/s` objective.

## Audited identities

- upstream DFlash source: `94e4abc5e0c31b67bc1a9d30f1cc34ece28a8756`;
- hipfire source: `d44f89e7f00f807962e0eb61a1790151a514cb83`;
- protected llama.cpp source inspected read-only:
  `e3546c7948e3af463d0b401e6421d5a4c2faf565` plus the existing protected
  experiment changes;
- z-lab source revision:
  `0919688658996800f86b895034249700e9481106`;
- source artifact:
  `/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash/model.safetensors`,
  SHA-256 `e0c050b34798d32728a164d2c3f1681746ff85c11945701b0205b654e2f1fdbe`;
- native Q8 GGUF:
  `/mnt/usb-models/models/qwen36-27b-dflash-native/Qwen3.6-27B-DFlash-Q8_0.gguf`,
  SHA-256 `c37b84724fa58cc5c6b545d8b96f8617a8c3bd7f018bf608feef4d3460e0575e`;
- native Q4 GGUF:
  `/mnt/usb-models/models/qwen36-27b-dflash-gguf/Qwen3.6-27B-DFlash-Q4_K_M.gguf`,
  SHA-256 `71362369a3428a9e93436a869b1131f63e04b88efbc92dacacb18c419d8de95c`.

Hipfire is original work by Kaden Schutt and contributors. Its DFlash runtime,
attention kernel, MagnumQuant formats, and other mechanisms carry the
attribution and provenance requirements documented in
`/home/steve/src/hipfire/AGENTS.md` and `PRIOR-ART.md`. Any implementation
informed by those mechanisms must retain appropriate attribution.

## Contract comparison

### Checkpoint and architecture: matched

The local z-lab config is a five-layer DFlash draft with:

- hidden size `5120`, intermediate size `17408`;
- `32` attention heads, `8` KV heads, head dimension `128`;
- trained block size `16`, mask token `248070`;
- four sliding-attention layers followed by one full-attention layer;
- sliding window `2048`, RoPE base `10,000,000`;
- target feature IDs `[1,16,31,46,61]` over the 64 base target layers.

Both GGUF drafts have the same 58 tensor names and the same architecture. The
Q8 file has 36 Q8_0 and 22 F32 tensors; the Q4 file has 32 Q4_K, four Q6_K,
and 22 F32 tensors. All 22 F32 norm tensors in each GGUF are bit-exact after
BF16-to-F32 conversion against the local z-lab safetensors. This, the identical
topology, and the pinned revision make a different checkpoint an implausible
explanation.

Hipfire's registry describes its Qwen3.6-27B MQ4 draft as refreshed from
`z-lab@0919688`, the same source revision. Its HFQ/MQ4 representation uses
hipfire's FWHT-rotated MagnumQuant format, while our drafts use GGUF Q8_0 or
Q4_K/Q6_K. That is a quantization-format difference, not evidence of a better
checkpoint. Hipfire's lower-precision MQ4 draft achieving high acceptance on
favorable prompts also argues against Q8 draft weights causing our low strict
acceptance.

### Feature layers: semantically matched

Upstream `dflash/model.py` defines a feature ID `L` as
`hidden_states[L + 1]`. Transformers index zero as the embedding output, so
this is the post-layer output of layer `L`. For the 64-layer target, the source
checkpoint IDs are `[1,16,31,46,61]`.

Llama.cpp's extraction API exposes the *input* to layer `L`. The GGUF metadata
therefore stores `[2,17,32,47,62]`, exactly `source_id + 1`, which names the
same residual tensors. This is an intentional conversion adjustment, not an
off-by-one bug. Hipfire computes `[1,16,31,46,61]` and captures post-layer
residuals, also matching upstream semantics.

The target GGUF reports 65 blocks because it includes the extra MTP block; the
DFlash feature contract correctly refers to the 64 base target layers.

### Tokenizer and chat template: tokenizer matched, serving distribution differs

The target and both draft GGUFs have identical 248,320-token vocabularies and
identical merge tables. Their canonical hashes are:

- tokens: `5ee0f927bcaa4b9fe85c244776ae9487468e427f83e053fc81f2a186f14936a3`;
- merges: `7e299304d9ad9dc312acdbcb1f6ccf0dce1256bf1aa986d651f13814dfd27e7b`.

The embedded target and draft chat-template strings differ in developer-role
and tool-call handling, but the fixed suite sends one user message with no
tools. Their one-user rendering and generation-prompt tail are the same.
Native speculation tokenizes through the target model anyway, so the draft
template is not used to construct the request.

The load-bearing difference is thinking policy. The strict launcher uses
`--reasoning off`; llama.cpp maps that to `enable_thinking=false`, producing a
closed empty thinking block before the answer. The corrected vLLM result also
passed `{"enable_thinking": false}`. Hipfire's high daemon acceptance rows
explicitly use ChatML plus a structured thinking block; its raw code peak uses
a continuation prompt. Neither is the fixed strict contract.

Hipfire also enables a `\n{3,}` to `\n\n` prompt normalization by default and
documents `14-27%` gains on affected PEP-8 code. That changes prompt bytes and
cannot be counted as an improvement on this fixed suite.

### Block and mask construction: form matched, trained width differs

Upstream, llama.cpp, and hipfire all form a linear block as:

```text
[last accepted/target token, MASK, MASK, ...]
```

with mask ID `248070`, absolute target positions, parallel draft prediction,
and exact longest-prefix target verification. The checkpoint was trained at
B=16. Native DFlash5 evaluates B=6 (one seed plus five masks), which upstream
supports as a legal runtime override. It is not semantically invariant,
however: the non-causal/bidirectional draft can attend to every mask row, so
changing B can change the first five predictions as well as truncate the
available tail. Hipfire's daemon currently passes the trained B=16; its demo
starts at B=16 and can adapt within B=8..16. This is the clearest unmeasured
contract difference.

The corrected vLLM strict control used eight speculative tokens (B=9) and
still emitted only `2.7316` tokens/step, so moving partway toward the trained
width did not rescue acceptance. That does not prove B=16 is neutral. Measure
B=16 acceptance offline before paying its much larger native verifier cost.

The first four draft layers use the 2048-token sliding cache in GGUF. At the
short strict contexts, that window covers the entire relevant history. Hipfire
currently describes its decoder as all-full/non-causal, while llama.cpp uses
the checkpoint's interleaved sliding-cache layout. This has not created an
observed strict acceptance advantage: the corrected vLLM endpoint-mixed path
and native llama.cpp converge to the same emitted-token result.

### Quantization and KV: draft weights are not the strict gap

The favorable-code isolation is decisive for ordinary draft quantization:

- Q8 draft plus F16 draft KV: `100/106` accepted (`94.3%`), `73.47 tok/s`;
- Q4 draft plus F16 draft KV: `104/115` accepted (`90.4%`), `74.01 tok/s`.

Both quantizations can express long accepted runs. Q8 draft KV, by contrast,
collapsed to `7/470`; F16 draft KV remains mandatory. That was a real backend/
numerical failure, but it has already been isolated and is not the current
strict-suite gap.

The strongest cross-runtime control is
`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-corrected-acceptance-summary-20260709.json`:

- exact fixed 12-prompt suite, thinking disabled, cached tokens all zero;
- vLLM target `webhie/Qwen3.6-27B-int4-AutoRound`;
- source z-lab draft, eight speculative tokens;
- `1.73158` accepted drafts and `2.73158` emitted tokens per step.

The native B70 records are `2.704-2.732` emitted/cycle. Reproducing the same
ceiling with another runtime, another target quantization, and a wider block
strongly closes tokenizer, feature extraction, native mask construction, and
GGUF weight quantization as primary explanations.

## What 100 tok/s requires

For one active generation:

```text
throughput = emitted_tokens_per_cycle * 1000 / cycle_ms
```

The promoted strict evidence uses about `2.704` emitted/cycle. At unchanged
acceptance, `100 tok/s` requires a `27.04 ms` cycle. That is not reachable by
the remaining small runtime boundaries alone.

For DFlash5, the maximum is six emitted tokens (five accepted plus the target
bonus token):

| Cycle wall | Emitted/cycle needed | Accepted/cycle needed | Fraction of five proposals |
|---:|---:|---:|---:|
| `60.715 ms` current promoted accounting | `6.072` | `5.072` | impossible |
| `60.0 ms` | `6.00` | `5.00` | `100%` |
| `55.0 ms` | `5.50` | `4.50` | `90%` |
| `53.3 ms` representative hipfire cycle | `5.33` | `4.33` | `86.6%` |
| `50.0 ms` | `5.00` | `4.00` | `80%` |
| `45.0 ms` | `4.50` | `3.50` | `70%` |
| `40.0 ms` | `4.00` | `3.00` | `60%` |

With B=16 the mathematical maximum rises to 16 emitted tokens. A geometric
extrapolation from the current short-block prefix distribution projects only
about `2.95` emitted/cycle even with an infinite free block, but that model
assumes width does not alter early logits. Bidirectional B=16 inference can
invalidate that assumption. Width becomes an execution win only if a direct
B=16 test first demonstrates materially higher prefix agreement and the wider
verifier keeps the cycle economics favorable.

## Three testable interventions

### 1. Build a B=6/B=9/B=16 captured-block parity oracle before changing weights

Capture target-owned feature rows, seed/mask IDs, positions, draft logits, and
target top-1 IDs for representative strict cycles. Replay B=6, B=9, and the
trained B=16 through:

1. the source BF16 z-lab draft with upstream public non-causal attention;
2. the source draft with endpoint-mixed causal-SWA/full-noncausal attention;
3. native GGUF Q8 with F16 KV.

Compare per-row logits, top-1 IDs, and accepted-prefix length both at matching
width and for rows 1..5 across widths. The known feature
mapping is source post-layer `[1,16,31,46,61]` == llama layer-input
`[2,17,32,47,62]`; do not sweep arbitrary layer sets.

Decision gate: if B=16 materially improves source-BF16 prefix length, retain a
width-specialized lane and benchmark its complete cycle. If source BF16 beats
native Q8 by at least `0.5` emitted tokens at the same B, isolate the first
divergent layer and repair that runtime contract. If matching-width source and
native remain near `2.7`, close runtime parity and block width as acceptance
lanes. Cross-runtime aggregate evidence makes the last outcome plausible, but
this oracle is the fastest conclusive test.

### 2. Train a small target-conditioned adapter on the exact product distribution

Use the existing `scripts/train-qwen27-dflash-offline.py` infrastructure, but
do not reuse its default AutoRound trace identity as the final gate. Generate
new target-owned traces from the active Q4_0 target with:

- the exact no-thinking target template;
- broad engineering, operational, factual, and prose prompts disjoint from the
  twelve benchmark prompts;
- exact target greedy continuations and post-layer feature rows;
- B=16 blocks so all positions receive training signal.

Start with feature-fusion/position LoRA or another small draft-only scope. The
target remains untouched, so target verification preserves output quality.
Evaluate on a disjoint held-out corpus first, then quantize to Q8 and run the
untouched strict suite once.

Go/no-go gate: a candidate must move toward the joint economics, not merely
produce a statistically visible acceptance increase. At a `50 ms` cycle it
needs at least `4.0` accepted (`5.0` emitted) per cycle; at `45 ms` it needs
`3.5` accepted. A candidate stuck near three emitted/cycle cannot reach the
objective even if it is faster than the current draft.

### 3. Escalate to full five-layer B=16 on-policy distillation if the adapter misses

The evidence says the shipped draft is highly competent on code but poorly
aligned with the fixed no-thinking mixed distribution. If a small adapter does
not cross the gate, the credible acceptance lever is full draft adaptation or
retraining, not more runtime knobs.

Train on a large, prompt-cluster-disjoint corpus generated by the exact Q4_0
target, optimize expected accepted-prefix length, validate BF16 first, then Q8,
and only then consider Q4. Keep B=16 and pair the candidate with M=6/M=9/M=16
width-specialized Xe2 verification. Select width from measured emitted tokens
and cycle wall; do not assume B=16 is faster.

The endpoint gate is always:

```text
measured emitted/cycle >= measured cycle_ms / 10
```

for `100 tok/s`, with all normal cold/cached-zero and target-verification
requirements. This is substantial training work, but after the parity oracle
it is the only direct route to hipfire-like mixed-distribution acceptance.

## Invalid shortcuts to avoid

- Do not call `[2,17,32,47,62]` an off-by-one bug; it is the correct llama
  layer-input representation of the source post-layer taps.
- Do not repeat Q4-versus-Q8 draft weight sweeps as the acceptance plan. Both
  already recover long favorable-code blocks, and Q8 does not fix the strict
  suite.
- Do not re-enable Q8 draft KV. Its `7/470` failure is disqualifying until a
  separate numerical fix restores F16 acceptance parity.
- Do not silently enable thinking, normalize prompt bytes, switch to raw code
  continuation, or substitute hipfire prompts. Those can be useful routed
  product policies, but they are different benchmark identities.
- Do not promote B=9/16 merely because it matches training. First measure its
  changed early logits and accepted-prefix length offline, then require the
  complete wider cycle to satisfy the throughput equation. Wider verification
  is already much more expensive.
- Do not use DDTree or lossy CACTUS-style acceptance as a headline shortcut.
  Hipfire reports DDTree losing throughput and lossy acceptance corrupting
  prose at useful thresholds.
- Do not train on the twelve promotion prompts or variants derived from them.
  That is benchmark leakage, not general acceptance improvement.
- Do not compare hipfire's raw-code/daemon genre rows with the strict median as
  if prompt, thinking policy, target quantization, width, and runtime were held
  constant.

## Practical priority

Run intervention 1 once, then stop runtime-contract speculation unless it
finds a material source-BF16 advantage. In parallel with verifier fusion, put
acceptance effort into exact-target, no-thinking draft adaptation. The current
draft is behaving consistently across native llama.cpp and vLLM; asking the
same checkpoint to become a mixed-prose draft through kernel tuning will not
produce the missing `1.3-2.6` emitted tokens per cycle.
