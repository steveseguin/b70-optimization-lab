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
obligations. Current-source strict terminal-EOS qualification passed 472 checks,
including 460 physical-state comparisons and 12 corruption controls. Remaining
CPU qualification and the final seal are still in progress.

## What worked

Retention selects host exports while target decisions remain with rank1.
Draft buffers and publication storage are private. A speculative miss stops
rank0 at the next compute-launch boundary, drains submitted work, restores its
checkpoint and recomputes the confirmed token. Speed receipts require a
same-boot exactness companion covering their prompts and identity.

Current completed CPU evidence includes 408 strict terminal miniature checks,
64 strict terminal sampled real-model checks, 1,109 actual native/Python
controller cases, and the refreshed GNU/Intel/ASAN mini gates. The strict proof
binds 480 owner archives and covers both controllers. Nonterminal cancellation
and its 204-case inventory audit, eight long-retention comparisons over twelve
requests, and 28 draft publication/failure cases now pass on current builds.
GNU and Intel Python-controller qualification each passes five modes, totaling
40 exact tokens and 1,920 fixtures per compiler. The refreshed cheap campaign
records 23 receipts, including 29 structural checks and 43 rejected mutations;
eight rollback-audit tests pass separately. Independent cancellation/retention
and suite-prefix reviews are signed. [CPU-RESULTS.md](CPU-RESULTS.md) preserves
these scopes without adding overlapping audits as extra model executions.
These are correctness checks, not device speed measurements.

The inherited real CPU suite now passes all three 64-token requests: 192 exact
tokens and 1,152 fixtures, native MTP on Intel host ranks. It covers three of
twelve prompts; full response generation does not imply complete prompt-set
coverage. Its scratch is archived and removed. Four selected-dispatch capture
prompts match fresh GNU/Intel references, and the pipeline draft-agreement join
passes for both compilers.

The one-prompt 128-token tail-fixture gate remains pending. The final native
real-controller campaign has passed four modes while MTP is active. Wrapper
and admission refresh, build/evidence validation and seal remain pending.
Earlier receipts do not substitute for their required current evidence.

## What failed or remains uncertain

Full-state comparisons exposed uninitialized standalone scratch; initialization
now clears it outside timed requests. Partial cancellation required retaining
the tail of every submitted kernel, including multi-pass operations. Inherited
structural assertions were updated to check the new bank-ownership rules, with
negative mutation checks retained. The seal audit also exposed an omitted
nested helper binary; its inventory check and regression test were corrected.

The original terminal-EOS path left abandoned physical bytes and token/cache
metadata unrestored. The replacement preserves a private pre-speculation image
and restores it on every rollback, including terminal abandonment. No reduced
state exception is assumed; [EOS-STATE-SCOPE.md](EOS-STATE-SCOPE.md) records the
finding and correction. The current-source strict proof now passes exhaustive
miniature boundaries and sampled full-weight real boundaries at positions 7
and 8 on the original seven-token prefix. This diagnostic is not a full-prompt
oracle or speed measurement. Device overlap, KD device parity, cancellation
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

Complete the remaining current-source CPU qualification, seal, then run the
admitted coordinator-only device windows.
Changed arithmetic, kernel choices, compiler, protocol, lifetime, retention,
input identity or metric definitions require the corresponding gates again.
[INTEGRATE.md](INTEGRATE.md) records the next rank0-draft/rebalance and packet39
fusion work. [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) preserves closed approaches.
This packet does not declare the optimization lane finished.
