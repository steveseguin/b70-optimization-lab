# Packet202: exact two-row prefill preparation

## Question and identity

Can two known prompt positions share projection work and submission overhead
while reproducing the unchanged packet198 single-token arithmetic and state?
This is a CPU source/design assessment after the closed packet201 serving run.
The initial assessment changed no runtime source and performed no native work.
The later synthetic CPU implementation is explicitly described separately; no
model payload or device/endpoint/service/queue action was performed. This
directory grants no operational admission.

The [packet201 observations](../../integration/streaming_v1/P201-PREFILL-OBSERVATIONS.md)
measure fresh370 prefill at 10.790s of 15.404s native request time (70.0%). Its
369 non-final positions issue 409,590 kernels and 2,214 host waits: 1,110 kernels
and six waits per position. The 7.208s summed host-wait interval includes queued
computation; it is not independently removable overhead. Halving the prefill
phase would save 5.395s as a sensitivity calculation, not a candidate forecast.
First-position 23.594s initialization/paging remains a separate attribution task.

## Decision

The first implementation now proves a **causal two-row GDN branch core** with
synthetic HOST_ONLY fixtures; see [implementation and results](IMPLEMENTATION.md).
The broader layer executor remains future work. Start with layer0 GDN and its current production Q6_K projections, not a
generic GEMM, whole-runtime rewrite, or a chunk4 implementation. The additive files are `chunk_plan.hpp`, `layer0_host_probe.cpp`,
`tests/test_chunk_plan.py`, and a production-binding manifest. The executable is
a synthetic CPU fixture, not a runtime owner or device binary; no new launcher,
profile or operational window is introduced.

A useful chunk must run layer-major: both rows reach the end of layer L before
layer L+1 consumes them. Merely enqueueing two entire ordinary token plans
preserves their weight rereads, 1,110-kernel/token count and host lookup/caching
barriers. Conversely, a two-row linear primitive alone leaves most causal state,
control binding and buffer lifetime work unresolved.

## Interfaces and required ordering

Proposed `ChunkPlan(start_position, known_tokens, count=2, mode=nonfinal_prefill)`
records immutable per-row token/position/lookup inputs, each operation's read and
write set, persistent-state aliases, and explicit dependencies. A remainder of
one uses the original M=1 path. The last prompt token always remains the existing
`step(token, fixture_step=1)` that computes the first output; subsequent decode,
stop-token behavior, front protocol and postreply SAVE/RELEASE remain unchanged.
Chunk4 stays out until chunk2 earns complete parity and a measured saving.

For an eventual full executor, the non-final span is `[start, input.size()-1)`.
Fresh start is zero. Append starts at restored.position, including the saved
pending token: the recorded 370-token append starts at342 and steps28 tokens,
including the final argmax-producing step. Same-generation resume remains on
its existing decode loop. Never advance twice or skip the pending token.

| Concern | Concrete decision / first-patch boundary |
| --- | --- |
| Row controls | Each row has immutable `position=start+i`, token and row-local temporary bindings. Preserve original active/error guards and sticky failure; a failed chunk is poisoned, never an automatic M=1 retry. The planner must distinguish speculative intermediate writes from a committed sequence boundary. |
| Dense math | Current plan.tsv layer0 qkv is grid14/Q6_K, K2560→10240; z is K2560→6144, both `p33.dense.segment`. Reuse the original per-lane multiply/add sequence, split tree, SG32 order and BF16 store. The older production-pair kernel supports Q6_K/K2560 but must match the actual current variant/fusion/flags before adoption. The old study's generic “Q8 first” is not this site's identity. |
| GDN and convolution | One shared layer0 history/state, never independent sibling state images. Compute row0 convolution and recurrence, including BF16 state store, before row1 reads that state. HC/gating/normalization retain original intermediate rounding. No associative scan or FP32 state held across rows. |
| QSA later | Row i must prepare/append/pool/select/attend with its own position and only prior/current KV. Finish row0 selection/attention before row1 changes shared pool state in the first conservative executor. Preserve completed four-token pools, selected-ID order/ties and split32 implementation12; a triangular mask alone is insufficient. |
| PLE later | Prepare each lookup from the exact preceding token history in order, including sentinel handling. Row-local embedding/PLE values must survive until consumed; PLE dilation3 convolution has its own sequential persistent history. Host and device token-history updates must agree. |
| MoE later | Keep route slots, probabilities, expert arithmetic and mixture ordering per row. Start with two original expert calls; no route sorting/coalescing or exceptional-IQ3 pair assumption. Dense sharing is not a promise of expert weight reuse. |
| Commit | Preserve a coherent chunk-end sequence position, final streams and token history only after all its layers succeed. Layer-major execution cannot expose the same globally complete intermediate sequence state as token-major execution; interrupts/errors before completion must retain a failed owner, not publish a checkpoint. A design using local row controls must not prematurely mutate the shared position read by unrelated layers. |

The first HOST_ONLY harness should take synthetic quantized weights, two explicit
layer inputs and one initial GDN state; run the current serial dispatch twice
and the proposed layer schedule; compare each projection, convolution history,
recurrent output/state and final row streams byte-for-byte. Test real production
binding geometry separately from a tiny numerical fixture, with no model load.
A generic reference interpreter alone does not prove the active device branch.

## Workspace and host/device decisions

The current engine binds one global `streams` buffer and captures concrete
allocation pointers in `issue_sites`. Its global `controls/scores/probabilities`,
FP32 input-cache tags and prepared argument blocks are not safe to reuse for
simultaneously live rows without a binding/lifetime audit. New per-row prepared
sites must be captured through the existing prepared submission abstraction;
never directly submit uncaptured kernels or capture references to temporary
argument objects.

Allocate one additional activation row and per-row live outputs/scratch, with
weights and all persistent layer states shared. Reuse ephemeral workspace across
layers. For orientation only, an extra BF16 streams row is20,480B, embedding
5,120B, qkv20,480B and z12,288B; these are **not a complete allocation bound**.
The existing large interpreter scratch must not simply be duplicated. Derive the
actual peak from typed read/write sets, overlapping lifetimes, selected split
scratch and guards; reject missing/ambiguous writers and allocation aliasing.
Retain the existing device/host/storage floors until a separately reviewed
complete ledger justifies admission.

`prepare_token()` currently decodes host lookup rows and calls `put/upload`,
which drains and waits while reusing a staging slab. An eventual chunk path must
stage the two known embedding/PLE payloads into distinct immutable slots before
submission, then retain those slots through completion. It cannot overwrite the
same slab while DMA/compute still references it. Position admission currently
reprepares QSA at multiples of32; the first version should split chunks at those
boundaries rather than silently use a different capacity reduction envelope.

The cache is the other integration blocker. Current overlap maintenance observes
48 layers' routes after each complete token, revokes victims/publishes pointers
only at drained boundaries, and may fill asynchronously. Layer-major scheduling
cannot finish token0's full-model route history before token1's lower layers.
Use a **new explicit chunk cache cadence**: quiesce/resolve old maintenance at
entry, freeze one valid pointer table and victim ownership for the whole chunk,
collect every row/layer route before scratch reuse, drain, then observe routes in
recorded row order and plan future maintenance. No fill may overwrite a visible
victim during the chunk. Exact host/device weight bytes must remain equivalent.
This changes cache scheduling, so a future comparison needs a row-serial
same-chunk-cache control to isolate projection/scheduling gains; it must not
claim the original cache history stayed identical. Keep cache integration outside
the initial one-layer CPU patch, which models it as an immutable input contract.

## Existing work and dead ends

The current `prepare_commands` and `step` already omit final norm/logits/argmax
for ordinary prefill positions. Removing that work again is not an opportunity.
They still read back sticky error and stale/unused next_token each token, copy
48 route buffers and drain, in addition to lookup uploads. Removing those
boundaries requires the dependency and ownership work above, not deleting waits.

[Packet165's batched-prefill study](../packet165-warm-prefill/BATCHED-PREFILL.md)
already identifies pair-dense and recurrent building blocks. Reuse it and
[packet151 production_rows.hpp](../packet151-sibling-cost/production_rows.hpp)
as mechanism evidence, not finished causal scheduling. The discarded-sibling
campaign remains closed: its extra independent row cost9.21ms device time in the
half model. This does not price useful known-prompt work, and does not justify
reopening sibling speculation. [Packet49b](../packet49b-gemv/DO-NOT-REPEAT.md)
and [packet68b](../packet68b-batched-rows/DO-NOT-REPEAT.md) explicitly distinguish
operator M=2 support from complete integrated correctness. Preserve their sealed
identities; never substitute arbitrary GEMM or oneDNN reduction order.

## Evidence, authority and next gate

[Source review receipt](source-review.json) pins the exact main/plan/dispatch,
prior studies and measurement receipt used here, and verifies the current main
against the packet198 source-overlay seal. The independent [authority map](AUTHORITY.md) and
[65-input authority inventory](authority-inputs.json) are complete in this
directory; their source review agrees with this first-patch scope.

Existing p181 CPU oracle outputs/logit hashes and p198/p201 complete checkpoint
hashes constrain later end-to-end tests, but do not supply missing prompt-internal
layer activations. The first patch must therefore create a **differential** CPU
fixture against the actual unchanged serial operator path. Cover two distinct
rows, equal/permuted rows, aliases/extent refusal, inactive/sticky-error behavior,
rounding-sensitive values, odd tails, capacity31/32/33 and append342/343 in the
planner. Verify no final/head/sampler operation in non-final chunks and no
checkpoint publication before completion.

After that proof, add QSA/PLE layer coverage and extend the same schedule through
all48 layers with all-state comparisons before considering device compilation.
Any later device test needs a new source/binary identity, real selected-kernel
byte gates, matched fresh prompts and separately reported first-use behavior.
Keep the real370/394 fresh prompts; append reuse is a separate control. This
proposal predicts neither a speedup nor a safe device-ready implementation.
