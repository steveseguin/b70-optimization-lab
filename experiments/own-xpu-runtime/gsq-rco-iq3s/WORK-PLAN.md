# Continuing SC117 engine work

Owner direction, October 24: finish making the downloaded model work in our
engine, test correctness, then continuously optimize speed without quality
loss or benchmark shortcuts. Continue until the owner stops the work or a
concrete blocker requires their decision. The previous Unsloth lane remains
closed; this direction applies to the requested SC117 target.

The target authority is the two downloaded shards at revision
`eec4e10a2c29b440a2ae85591fa11569ce752963`, with the full readback hashes in
`model-identity.json`. Do not change target weights, quantization, context
contents, sampling identity, or full 16-bit KV to obtain a faster number.
Keep all target verification for MTP. Draft-only approximations are acceptable
only insofar as the exact target still verifies every emitted token and the
completed target state matches the target-only path.

1. Complete the all-source native build and actual persistent-pair lifecycle
   check. Load the real target once with the draft available, then compare
   target-only and MTP tokens/state after a complete request reset. Preserve
   failures, source changes, physical ownership and safe teardown evidence.
2. Establish a measured baseline with complete model/run identity and honest
   prefill/decode/acceptance/memory accounting. The short correctness comparison
   is not a speed record. Use full fresh prompts and no reused prompt/KV/output
   state for benchmark claims; separate model residency from prompt reuse.
3. Profile only after correctness passes, select changes with worthwhile
   expected benefit, and test exactness before promoting speed results. Keep
   failed candidates and matching controls. No hidden precision reductions,
   hand-picked easy prompts, extrapolated records, or speed claims from
   diagnostic work. Keep operating under the user's existing host constraints.

A dedicated subagent reviews progress every 30 minutes. It should challenge
unnecessary gating, repeated builds/tests, speculative scaffolding, and low-value
work; identify the next highest-value bottleneck; and check model identity,
correctness scope and benchmark fairness. It reports recommendations to the
coordinator and records concise dated feedback here in the lane. It does not
operate GPUs, alter services/settings, or authorize a shortcut. The coordinator
owns action selection, all device operations, and evidence-backed conclusions.
