# Packet58r CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the one-card tile16 line reuse one model load for native A/B/A/B/A kernel
screens? October 18, 2026; Unsloth UD-IQ3_XXS quantized compressed version,
packet49 `iq3-p49-split32-v1` oracle, packet58j native base used by 58n/58p,
packet98c switch lineage. Proposed hardware is one B70, physical card 0,
whole-host exclusion. Five views each contain the fixed twelve prompts at
128 tokens, plain target decode and BF16 KV.

## Outcome

CPU implementation is accepted for coordinator planning. No device execution,
full-model equality, speed result or record is claimed. Route-fast,
rec-both-plus and their combination are implemented as restricted selections;
the initial proposal compares the combination against tile16. Other-fusion
is absent in this one-card engine and is refused.

## What worked

One native owner keeps its weight allocations, pinned expert handles and
immutable expert cache across five views, drains at each boundary and
recaptures only the selected kernels. The normal request reset clears model
state. Immediate token and final-length checks stop a view on any packet49
mismatch; the independent consumer checks all sixty requests.

Both compilers pass byte checks against the actual one-card controls. Native
full-size mock binding covers all four selections, both miss paths and each
selection at contexts 32 and 4096. Six miniature brackets compare retained
layer bytes against fresh controls. A wrong oracle stops before B0.
Twelve intercepted window paths and six real host-only native parser paths
retain the launch contract without opening a device. Seventy-nine Python
tests cover policy, memory, mask, drain, teardown and reporting failures.

## What failed or remains uncertain

Read-only review found and closed missing oracle-completion and reused-object
provenance pins, incomplete per-view full-context coverage, and report hashing
before clean-owner teardown. It also found inherited wrapper gaps: an 8 GB
runtime storage floor and fresh processes losing the full fault filter.
The new copy uses a 25 GB post-write floor and installs sealed fault patterns
in every window. Frozen parents remain unchanged.

The generic teardown scanner reports NOT_VERIFIED for this custom adapter;
actual integration tests provide the wiring evidence. GNU/Intel seeded-NaN
payload differences remain confined to the original NaN cases; candidates
match each compiler's unchanged control exactly. Device arithmetic equality,
repeat/fresh-process determinism and a strict 512-token final gate remain
pending. The 20–30 minute duration is a planning estimate. Nothing here
qualifies for submission or promotion.

## Evidence and patches

- [Build, dependencies and parent relinks](evidence/build.json)
- [Kernel bytes](evidence/byte-gates.json), [request resets](evidence/reset-gate.json)
- [Full-shape binding](evidence/fullshape-submit-cpu.json), [post-load allocation](evidence/postload-allocation-cpu.json)
- [Arguments](evidence/argument-gate.json), [native startup](evidence/startup-cpu.json)
- [Python policy](evidence/python-cpu-gates.json), [memory](evidence/memory-budget.json)
- [Drain fix](evidence/drain-fix.json), [teardown](evidence/teardown-integration.json)
- [Implementation and reproduction](README.md), [copy lineage](copy-manifest.json)

Generated binaries/objects are ignored and restored with the documented build
against frozen parent objects. This is an originating-host lab packet, not a
publicly reproducible package. No required raw GPU evidence exists yet.

## When to revisit

The coordinator may schedule the new proposal in a whole-host gap after fresh
fault, host-memory, storage, card and drain checks. Lane B must remain paused
through internal gaps. Every device token must match packet49; stop on the
first mismatch or fault, without retries. Retain a losing or drifting screen.
A passing screen can justify fresh-load quality/performance work; it cannot
publish or replace a qualified record. A separate source port is needed before
other-fusion becomes a supported switch.
