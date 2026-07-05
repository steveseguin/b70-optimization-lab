# 2026-07-05: Hipfire DFlash Audit For Intel B70 Qwen27

## Goal

The user asked whether Hipfire's open-source Qwen3.6 27B DFlash path, which
reports roughly `185-218 tok/s` on AMD 7900 XTX code prompts, can be reused or
ported to Intel B70 to push our strict Qwen27 result beyond the current
`65.276 tok/s` record.

This note separates what Hipfire actually proves from what is valid for our
benchmark policy, then maps the reusable ideas into an Intel/vLLM prototype
path.

## Current Local Baseline To Beat

Current strict fresh-response record for this lane:

- model/runtime label: `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8
  LM-head (BF16 scales)`;
- hardware: one Intel Arc Pro B70, TP1, vLLM/XPU;
- speculation: target-verified `qwen3_next_mtp`, `num_speculative_tokens=3`,
  `max_cudagraph_capture_size=8`;
- primary metric: fixed Qwen realistic suite, each prompt once, chat mode,
  `cached_tokens=0`, generated-token throughput for tokens 1-100 after TTFT;
- current headline: `65.27648650325429 tok/s`, p10 `59.6085`, mean `65.0769`;
- LocalMaxxing: `cmr5iu3gk00bfq901nidgcana`.

Important: the GGUF Q4 lane is not this result. The local Qwen3.6 27B GGUF Q4
lane is about `30.68 tok/s` strict fresh; the `65 tok/s` result is the vLLM
AutoRound + runtime INT8 LM-head lane.

## Hipfire Source Snapshot

Local reference checkout:

```text
/home/steve/src/hipfire
commit d44f89e7f00f807962e0eb61a1790151a514cb83
```

Primary upstream references:

- source: https://github.com/Kaden-Schutt/hipfire
- Hipfire Qwen3.6 27B model card:
  https://huggingface.co/schuttdev/hipfire-qwen3.6-27b
- model-card revision observed via HF API:
  `f9b326a657f14cbc400e384ff84a4b9b4b726ba2`
- relevant files reported by HF API:
  `qwen3.6-27b.mq4`, `qwen36-27b-dflash-mq4.hfq`,
  `qwen36-27b-dflash-mq3.hfq`
- DFlash upstream draft: https://huggingface.co/z-lab/Qwen3.6-27B-DFlash

## What Hipfire Claims, And What It Does Not Claim For Us

Hipfire's own docs say the non-spec Qwen3.5 27B MQ4 autoregressive lane is about
`47 tok/s` on a 7900 XTX, and that DFlash lifts code prompts substantially:

- Qwen3.5 27B code HumanEval/53: AR `44.1`, DFlash `196.0`, peak `218.6`,
  speedup `4.45x`, tau `9.82`;
- Qwen3.6 27B code HumanEval/53: AR `44.2`, DFlash `185.5`, speedup `4.19x`,
  tau `9.25`;
- Qwen3.5 27B prose Rome: AR `44.0`, DFlash `49.6`, speedup `1.13x`,
  tau `1.67`;
- Qwen3.5 27B instruct sky-color: AR `44.6`, DFlash `44.7`, speedup `1.00x`,
  tau `1.39`.

The Hipfire README/model card also describes the Qwen3.6 27B draft as a paired
DFlash sidecar converted from `z-lab/Qwen3.6-27B-DFlash`, with `block_size=16`,
`mask_token_id=248070`, and target hidden extraction layers
`[1, 16, 31, 46, 61]` for the 62-layer Qwen3.6 target. The paired Hipfire draft
is about `0.92 GB`.

Interpretation for our policy:

- Hipfire is legitimate source evidence that a stronger, target-matched
  block-diffusion drafter can make Qwen27 code prompts much faster.
- Hipfire's `185-218 tok/s` rows are not our LocalMaxxing headline result:
  they are AMD RDNA, Hipfire MQ4/HFQ runtime, code prompt fixtures, and not our
  fixed realistic fresh-response suite.
- The genre table is the warning label. DFlash can be huge on code, close to
  flat on instruct/prose, and sometimes net-negative on other prompts. We must
  measure tau/acceptance on the fixed realistic suite before assuming this can
  beat `65.276 tok/s` as a general fresh-response result.
- Warm GPU/JIT/DPM state is acceptable for steady-state silicon comparison, but
  prompt/output continuation history is not. Any submitted number still needs
  one cold request per prompt, `cached_tokens=0`, no prefix/KV/context/response
  reuse, no warmed repeated continuation, and target-verified speculation.

## Implementation Findings From Hipfire

### DFlash draft architecture

File: `/home/steve/src/hipfire/crates/hipfire-runtime/src/dflash.rs`

Key facts:

- lines 5-14: DFlash draft forward is Rust+HIP and the draft has no vocab head;
  it emits hidden rows and the caller applies the target `lm_head`.
- lines 16-27: the draft is a Qwen3-style decoder conditioned on selected target
  hidden states; the current source comment says five full-attention layers and
  cumulative target hidden context.
- lines 51-66 and 82-130: `DflashConfig` is loaded from HFQ metadata with
  `block_size`, `mask_token_id`, `target_layer_ids`, and target-layer count.
- lines 193-205: HFQ matrix weights support F16/F32 plus MQ4/MQ6/MQ3 group-256
  formats.

For Intel, the reusable concept is not the HIP kernels. It is the contract:
capture selected target hidden states, run a small paired block drafter, apply
the target LM-head to the draft hidden rows, and verify with the target model.

### Verification and acceptance

File: `/home/steve/src/hipfire/crates/hipfire-arch-qwen35/src/speculative.rs`

Key facts:

- lines 223-348: Hipfire batches the target LM-head over verify rows, supports
  Q8/HFQ4/MQ4/MQ3/HFQ6/MQ6 output weights, and for greedy verification runs GPU
  batched argmax before downloading only token IDs.
- lines 2356-2460: verify runs the target over the candidate block, with graph
  capture eligibility over fixed-size verify batches. The graph reads current
  bytes from fixed device buffers.
- lines 3549-3591: before verify, Hipfire snapshots DeltaNet state, then target
  verification advances state over the whole speculative block.
- lines 3755-3790: greedy acceptance is the longest prefix where the draft
  token matches the target argmax; the bonus token comes from the target.
- lines 3971-4022: after verify, Hipfire restores the pre-verify DeltaNet state
  and advances only the accepted prefix. If a `GdnTape` was captured, it replays
  GDN recurrence for `accept_len + 1`; otherwise it reruns a batched target
  prefill over the accepted prefix.

This is the most important lesson for our Qwen/GDN work: Hipfire treats
rollback/replay as a first-class exact state transition, not as an incidental
copy after a captured decode replay.

### GDN tape

File: `/home/steve/src/hipfire/crates/hipfire-arch-qwen35/src/speculative.rs`

Key facts:

- `GdnTape` captures pre-conv1d qkv plus post-sigmoid alpha/beta for each
  linear-attention layer and verify position.
- replay runs conv1d + Q/K norm + repeat-interleave + GDN recurrence for the
  accepted prefix so both S-state and conv state land on the committed
  trajectory.

This directly explains why our Qwen35B graph+ReplaySSM path was fragile: graph
capture plus eager restore can race or double-process unless the state transition
is explicitly part of the verified/committed pipeline.

### Hidden-state ring and graph safety

File: `/home/steve/src/hipfire/crates/hipfire-arch-qwen35/src/speculative.rs`

Key facts:

- `HiddenStateRingBuffer` uses fixed staging buffers for graph-captured verify
  writes and then commits staging to the ring outside capture.
- `commit_staging_to_ring` synchronizes the active stream before copying from
  staging into the logical ring so replayed graphs do not bake in a dynamic head
  offset.

This is a concrete design pattern for our Intel prototype: captured target
verify should write hidden rows into fixed staging buffers; dynamic logical ring
updates should happen outside capture with explicit ordering.

### Draft conversion and format

File: `/home/steve/src/hipfire/crates/hipfire-quantize/src/bin/dflash_convert.rs`

Key facts:

- `dflash_convert` converts a Hugging Face DFlash draft safetensors directory
  into Hipfire HFQ with `arch_id=20` and a top-level `dflash` metadata block.
- It has `--mq4`/`--mq3` paths for MagnumQuant group-256 formats.
- This is useful as a metadata/format reference, but HFQ/MQ kernels are not
  directly usable by vLLM/XPU.

## Subagent Cross-Check

Subagent `019f2ffd-328f-7852-a0c9-3ac407f61b0c` independently mapped the same
DFlash stack and modified no files. Its useful additions:

- service-level loop is `generate_spec` in
  `/home/steve/src/hipfire/crates/hipfire-runtime/examples/daemon.rs`;
- the generic reusable contract lives in
  `/home/steve/src/hipfire/crates/hipfire-runtime/src/spec.rs`;
- `Speculator`/`SpecTarget`, prompt-cache/resume policy, acceptance logic,
  DFlash metadata, target-hidden ring/checkpoint strategy, DeltaNet snapshot,
  and GDN tape semantics are conceptually reusable;
- AMD/HIP buffer and kernel pieces are a rewrite on Intel: `rdna_compute::Gpu`,
  HIP streams/events/graphs, all `.hip` kernels, MQ/HFQ/Q8 GEMM dispatch,
  draft attention, target attention, GDN/conv kernels, top-k/softmax/argmax,
  KV write/compact, and graph capture paths.

## Reusable Ideas For Intel B70

High value:

1. **Target-matched block drafter.** The core opportunity is a better drafter,
   not more MTP3 config sweeps. Our current MTP3 trace emits about `2.7`
   tokens/verify step; Hipfire code prompts show that a target-conditioned
   block drafter can emit many more tokens per expensive target verify step.
2. **Target-owned LM-head.** The draft has no separate vocab head. It emits
   hidden rows, and the target LM-head maps them to draft tokens. That keeps
   final quality target-verified and avoids a second incompatible vocab head.
3. **Batched verifier hidden capture.** Run the target over the whole candidate
   block, capture selected target hidden rows, and feed accepted rows to the
   next draft cycle.
4. **Exact recurrent-state rollback/replay.** For Qwen3.6 hybrid DeltaNet/GDN,
   a correct fast path likely needs a GDN tape or equivalent accepted-prefix
   replay, not a loose eager copy around captured decode.
5. **Fixed-buffer graph discipline.** Captured verify should read/write stable
   buffers; dynamic ring positions and state commits happen outside the graph
   with explicit ordering.
6. **Benchmark hygiene.** Hipfire's prompt-md5 and resident reset discipline is
   useful. We should keep our stricter fresh-suite/cache-zero rules layered on
   top.

Not directly portable:

- HIP/RDNA kernels, graph APIs, WMMA/dp4a paths, MQ/HFQ byte layouts, and
  Hipfire's Rust runtime cannot be used directly on Intel Level Zero/SYCL.
- Hipfire MQ4 target weights are a different quantization/runtime from our
  AutoRound W4A16 + runtime INT8 LM-head result.
- Hipfire DFlash results depend heavily on prompt genre. They are not a generic
  chat throughput guarantee.
- The existing local vLLM DFlash implementation already failed to run the real
  mixed sliding/full DFlash architecture because the proposer assumes one draft
  KV-cache group. That must be fixed or bypassed.

## Intel Prototype Plan

### Phase A: Feasibility and acceptance before kernel work

Purpose: decide whether the Qwen3.6 27B DFlash draft actually has enough
acceptance on our fixed realistic suite to justify an Intel port.

Steps:

1. Obtain metadata for `qwen36-27b-dflash-mq4.hfq` and/or the upstream
   `z-lab/Qwen3.6-27B-DFlash` draft without treating Hipfire benchmark numbers
   as local claims.
2. Determine whether the upstream safetensors draft can be loaded by PyTorch or
   vLLM with its real mixed sliding/full attention. Do not use the local
   all-sliding workaround as evidence; it already collapsed to `20.63 tok/s`.
3. Build an offline acceptance probe on a tiny subset of the fixed Qwen suite:
   run target prefill/verify and draft generation in a slow but exact path if
   necessary, then report tau/accepted tokens by prompt.
4. Completion gate: if realistic-suite tau is not clearly above the current
   MTP3 `~2.7` tokens/step, close the lane as "code-prompt-specific no-win for
   our target suite" before touching Intel kernels.

### Phase B: vLLM/XPU prototype, not a standalone engine

Purpose: reuse our current vLLM/XPU model loader, strict harness, and
LocalMaxxing validation path.

Required pieces:

1. Make vLLM's DFlash/EAGLE proposer metadata support mixed draft KV groups
   (`sliding_attention` plus `full_attention`) instead of assuming one
   `kv_cache_gid`.
2. Capture selected target hidden states during target prefill/verify into
   fixed staging/ring buffers.
3. Run the DFlash draft forward on XPU. The first prototype can be PyTorch/XPU
   and slow if it proves acceptance; only then replace hot pieces with kernels.
4. Apply the target LM-head to draft hidden rows. For our current runtime this
   should use the same INT8 LM-head path where exact; fallback to dense logits
   when penalties/logprobs/sampling require it.
5. Verify candidate blocks with the target model in one batched pass.
6. Implement exact GDN/DeltaNet accepted-prefix state replay or a graph-safe
   equivalent. This is mandatory for correctness under graph capture.
7. Gate the entire path behind default-off env flags until it passes strict
   fresh validation.

### Phase C: Performance work only after acceptance is real

Likely hot spots after a correctness prototype:

1. Draft forward over `block_size=16` with mixed SWA/full attention.
2. Target verifier forward over the block.
3. Target LM-head for draft rows and verifier rows.
4. GDN tape/replay overhead.
5. Dynamic hidden-ring scatter/commit.

Do not spend time porting Hipfire's MQ/HFQ kernels unless Phase A/B prove that
tau is high on the fixed realistic suite. If tau is high, then a SYCL/XPU draft
forward and a graph-safe verifier are credible work; if tau is low, the port is
not worth it for our headline benchmark.

## Strict Validation Rules For This Lane

Diagnostic exploration may use code prompts, HumanEval-style fixtures, and
synthetic prompts to understand tau.

Promotion/submission requires:

- fixed Qwen realistic prompt suite;
- each prompt once as a cold first response;
- `cached_tokens=0` for every request;
- no prompt/KV/cache/history reuse, no response reuse, no n-gram/history
  acceleration;
- target model and quantization unchanged from the declared row;
- speculative decoding allowed only when every committed token is verified by
  the declared target;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT;
- report p10, mean, TTFT, wall-clock tok/s, full-output tok/s, prompt/output
  hashes, model identity, runtime commit, env vars, flags, logs, and support
  artifacts;
- if the delta is inside the known `~1-1.5%` practical variance band for this
  Qwen27 recipe, run paired/same-window repeats across multiple B70s before
  claiming a win.

## Decision And Next Step

The AMD Hipfire result is real enough to justify a targeted acceptance/prototype
lane, but it is not a simple "port the code" task and not a LocalMaxxing claim.

Recommended next step:

1. Download or inspect the upstream DFlash draft metadata and weights only as
   needed.
2. Build a small, slow, exact acceptance probe for the fixed realistic suite.
3. If tau is strong, implement mixed-KV-group DFlash proposer support in vLLM
   and a graph-safe target hidden ring/state replay path.
4. If tau is weak, close the lane and return to other stronger-drafter or
   verifier-cost work.

Definition of completion for this Hipfire lane:

- **Win path:** a vLLM/XPU DFlash-style Qwen27 path beats `65.276 tok/s` on the
  strict fresh suite, passes quality and variance checks, is documented,
  committed, pushed, and submitted to LocalMaxxing.
- **Feasibility-closed path:** realistic-suite tau is too low or the upstream
  draft cannot be used without a large training/conversion effort; record the
  blocker and preserve any probes.
- **Engineering-blocked path:** tau is strong but mixed-KV-group proposer or
  GDN replay support requires a larger backend project; preserve a design with
  clear file targets and correctness gates.
