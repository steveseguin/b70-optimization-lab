# Existing draft integration: CPU review and qualification scope

The proposed two-stage sequential reference and four-stage live proposal run
can qualify target-state parity and draft-state parity across scheduling and
placement. They do not independently establish parity with the old native
controller: both use the new committed-hidden transport. No GPU work was
performed for this review; no draft training is involved.

## Pair semantics checked against the existing provider

The final target layer's raw `streams` buffer is captured after the layer's
`ffn.combine`, before final head operations. For this model it contains four
2560-element F32 streams (40,960 bytes), not the 2560-element mixed/head-normalized
vector. `DraftRuntime.compute` performs the existing F32-to-BF16 conversion once.
At target input position p, `(raw_hidden_p, confirmed_token_p+1)` advances the
canonical draft to position p+1 and proposes token p+2. The native provider and
controller both enforce contiguous canonical advancement.

Prompt bootstrap supplies every true pair p=0 through P-2 in order. The draft
head flag is `p+2 >= P`: it is distinct from the target handoff's head flag,
which states whether that target row emitted a token. For EOS or the generation
cap, omit the final unused pair, consistently with the legacy controller. The
new driver checks the completed pair count against the target frontier.

Historical `draft-rows.jsonl` files retain position, confirmed token, guess and
head mask but no raw hidden input. The available old service captures do not
contain an appropriate sealed complete draft state. Old reset-state dumps or
consecutive one-step hits are not substitutes for this proof.

There is a useful narrower legacy control for the exact 87-token
incident-retrospective prompt: the retained depth-probe trace contains canonical
confirmed positions 86 through 117, confirmed tokens and first draft guesses.
Every selected probe records byte-verified restoration. These 32 rows agree with
the separately retained native controller result, whose `draft_rows.position`
is the proposed token position (confirmed position plus one).
[Extracted legacy prefix](live-draft-legacy-prefix.json) pins both sources and
the prompt and retains these expected live event rows. Matching them would add
independent legacy proposal evidence; it still cannot prove identical hidden
inputs or full legacy draft state.

## Lifecycle and deadlock review

The controller copies both committed header and raw hidden into owned Python
bytes as it consumes the final-stage COMMIT reply. It binds them to that exact
position, token, row ticket and commit sequence, so reuse of the shared slot
does not silently replace a queued pair.

A queued pair blocks only new stage0 ROW commands. COMMIT/ABORT resolution and
other stages remain schedulable; op23 runs only after stage0 has neither busy
nor pending target work. This avoids the cycle where the draft waits for a
checkpoint while target verification waits for the draft. The synchronous
op23 exchange temporarily pauses controller dispatch, while already submitted
downstream work can finish; it is bounded and checks the host guard. A missing
or late proposal leaves the known-target path available.

The draft provider is allocated before `StageCheckpoint` pins its mutable
inventory. Checkpoint save/restore includes its device allocations and the two
explicit pinned allocations. No draft compute executes while a target snapshot
is active, so restoring a rejected target row cannot roll back newer canonical
draft host state. EOS/cap drains rejected descendants before final dumps.

## Required qualification evidence

1. Run identical prompt, generated tokens, model/draft weights, arithmetic,
   context capacity and head masks. PP2 sets `use_proposals=false` but still
   executes every canonical true-pair draft step; PP4 enables existing depth-one
   proposals. Keep actual build and topology identities in provenance.
2. Compare every target canonical buffer/layout against the retained target-only
   baseline, including sealed wavefront quiescence and byte-verified restores.
3. Compare ordered per-pair position, confirmed token, head mask, raw-hidden
   SHA256 and resulting draft proposal. Hash the input tuple sequence separately
   from outputs; a matching final state cannot excuse a differing input sequence.
4. Compare the new `ownrt.draft-state.v1` sealed dumps with
   `engine/tools/compare_draft_state.py`: every device allocation, scratch byte,
   pinned publication/half-staging byte, layout and host field is included.
   Bind the sealed I32 draft position to the host and manifest position. Require
   no disabled provider, async operation, reverse pointer or queued depth probe.

CPU tests cover 2/4/6-stage socket scheduling, fragmented replies, proposal
misses, EOS/cap and prompt bootstrap; the draft-state comparator's negative
controls cover payload tampering, changed scratch/pinned bytes, missing layouts,
wrong shapes, stale device position, pending host state and mismatched pair
sequence. These CPU checks do not certify GPU execution or throughput.
