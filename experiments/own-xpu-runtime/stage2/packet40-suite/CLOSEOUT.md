# Packet40 suite preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can suite timing exclude fixture copies, measure 64/128 output caps, and reduce
draft/cancellation overhead without changing target tokens or state? This is the
quantized compressed Unsloth UD-IQ3_XXS lane, arithmetic `iq3-p17-detmath-v2`,
with full BF16 target state. Packet40 copies amended packet38 as recorded in
[parent-copy.json](parent-copy.json). Changes cover retention, native asynchronous
draft publication, per-launch cancellation and suite metrics. Preparation runs
on CPU only on steve-b70s; no device has run. The exact build identity and its
qualification status belong in [build-receipt.json](build-receipt.json).

## Outcome

CPU qualification remains in progress. Copied packet38 passing receipts are
historical inputs, not packet40 qualification. No packet40 speed is claimed.
The final gate inventory is authoritative only after a fresh successful seal;
[qualification-checklist.json](qualification-checklist.json) maps inherited
obligations. The strict terminal-EOS state requirement remains unresolved and
blocks sealing independently of the remaining CPU checks.

## What worked

Retention selects host exports while target decisions remain with rank1.
Draft buffers and publication storage are private. A speculative miss stops
rank0 at the next compute-launch boundary, drains submitted work, restores its
checkpoint and recomputes the confirmed token. Speed receipts require a
same-boot exactness companion covering their prompts and identity.

Current completed CPU evidence includes all miniature cancellation boundaries,
four sampled real-model boundaries, full nonterminal state inventories,
retention independence, native/Python controller equivalence and every-window
CPU wrapper rehearsals. [CPU-RESULTS.md](CPU-RESULTS.md) records the precise
counts and scope. These are correctness checks, not device speed measurements.

## What failed or remains uncertain

Full-state comparisons exposed uninitialized standalone scratch; initialization
now clears it outside timed requests. Partial cancellation required retaining
the tail of every submitted kernel, including multi-pass operations. Inherited
structural assertions were updated to check the new bank-ownership rules, with
negative mutation checks retained. The seal audit also exposed an omitted
nested helper binary; its inventory check and regression test were corrected.

At terminal EOS, abandoned speculative work can leave different unused physical
bytes even though committed state and emitted tokens agree. No owner exception
has been assumed; [EOS-STATE-SCOPE.md](EOS-STATE-SCOPE.md) describes the exact
limit and pending decision. Device overlap, KD device parity, cancellation
savings and boot-bound exactness/speed pairs remain unmeasured. A 128-token cap
can provide the 100-event rate but cannot satisfy the repository's 512-token
publication gate or promotion-attestation requirement. The historical 28.49
reference also differs in arithmetic, runtime, context and finite-rate population;
[the independent metric review](review-metrics-second-independent.md) records
those limits.

## Evidence and patches

The implementation is retained in this packet, with [ROLLBACK.md](ROLLBACK.md)
and [DRAFT-ORDERING.md](DRAFT-ORDERING.md) explaining state/event ownership.
[CPU-RESULTS.md](CPU-RESULTS.md), current gate receipts and compressed evidence
retain successful and failed attempts. [ARTIFACTS.md](ARTIFACTS.md) explains
retention and restoration. Large unchanged parent evidence stays at its immutable
parent path, mapped by [inherited-evidence-links.json](inherited-evidence-links.json).
[CPU-REPRO.md](CPU-REPRO.md) records reproduction commands, and
[WINDOW.md](WINDOW.md) contains the prepared coordinator windows.

## When to revisit

Resolve the terminal-EOS physical-state requirement, finish current CPU
qualification and seal, then run the admitted coordinator-only device windows.
Changed arithmetic, kernel choices, compiler, protocol, lifetime, retention,
input identity or metric definitions require the corresponding gates again.
[INTEGRATE.md](INTEGRATE.md) records the next rank0-draft/rebalance and packet39
fusion work. [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) preserves closed approaches.
This packet does not declare the optimization lane finished.
