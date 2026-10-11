# Packet 4 integration — closeout

<!-- campaign-closeout -->

## Question and identity

Can the existing IQ3 loader, ordered decode graph and resource owner form a
single runnable CLI? October 11 CPU-only preparation on steve-b70s, the admitted
Unsloth UD-IQ3_XXS three shards, packet2 tree32 GEMVs and BF16 state. No GPU run.

## Outcome

Integration and compile-only SYCL target are present. Synthetic end-to-end
identity passes; the real first-layer exactness gate fails at 2,293/10,240 BF16
values. No real-model quality, device fit, speed or full answer is qualified.

## What worked

Census-driven ownership, bounded reads/copies, on-device routing kernel lowering,
GGUF GDN head layout, and clean teardown are wired. Mini-model Python parity,
receipt checks and event retirement tests pass. All 1,224 tensors are covered.

## What failed or remains uncertain

The initial real-layer CPU attempt reached 36 tokens then safely refused more
work at the 4,096-event smoke ledger bound. Completed-event retirement fixes
that integration limit without removing the bound or freeing busy work. The
complete 87-token first layer still differs from the independent BLAS oracle.
Known reduction/library differences are hypotheses for localization, not a
quality waiver. Native compound kernels and one-/two-card memory fit are unrun.

## Evidence and patches

[Sources and limits](README.md), [build](build-receipt.json), [CPU tests](cpu-tests.json),
[retained actual/oracle bytes and comparison](evidence/real-layer/comparison.json),
[initial safe refusal](evidence/event-ledger-refusal.json). All implementation
changes are tracked; build scratch is regenerable using `build.py` and removed.
The sibling's complete oracle run remains in its lane, not copied wholesale.

## When to revisit

Localize the real-layer arithmetic mismatch at operator boundaries, retaining
both arithmetic identities and exact gates. The coordinator may use the first
card-3 layer window for diagnostics; full one-token and eight-token stages must
wait for exact first-layer and fresh-process passes. No optimization lane is
finished by this packet closeout.
