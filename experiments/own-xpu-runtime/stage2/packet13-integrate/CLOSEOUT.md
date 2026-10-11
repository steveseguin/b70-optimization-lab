# Packet 13 CPU integration closeout — 2026-10-11

## Question and identity

Can the existing integrated own-rt-iq3 execute the measured round-2/3/4 choices
with bounded one-card layer streaming, ready for real-model device capture?
The separate Unsloth IQ3 quantized compressed version retains its weights,
BF16 state/KV and frozen arithmetic `iq3-p13-r234-sg32-split4-bf16-v1`.

## Outcome

CPU preparation passes: dense shape/grid dispatch, fused gate/up, routed down
and ordered epilogue are integrated. One-card selected-bank streaming and
two-card resident sequential placement share arithmetic. The complete first
prompt, eight-step fixture layout and GEMV/non-GEMV timing are wired.
[README](README.md) records the tests and [WINDOW](WINDOW.md) the next device
commands. No native executable was run, no performance result is promoted,
and the lane remains open.

## Useful mechanisms and retained evidence

Packet 4's original graph, shared nonlinear code and eager event retirement
are reused. Packet 3-prep owns all memory and copies. Packet 9 supplies the
measured dispatch and fused expert implementations; their own reference trees
are selected through one authority header. A compact slot map preserves
expert route order without transferring 512-expert banks.

[Build receipt](build-receipt.json), [CPU integration receipt](cpu-tests.json),
[memory calculation](memory-plan.json), [real-layer bytes/hash](evidence/real-layer/receipt.json)
and all sources are retained. Build scratch is regenerable and removed at the
end of this task. Earlier packet sources and receipts are unchanged by this
implementation; sibling edits are preserved.

## Failures and uncertainty

The first mock run caught a selected-weight lifetime classification error;
the owner refused it and shut down cleanly. Selected allocations now use the
owner's required weight lifetime and are explicitly released after draining.
The subsequent mock checks pass.

The 87-token real first-layer hash is recorded but has no comparable rebased
oracle yet. Device transcendental exactness, whole-model output, all eight
native steps, actual memory fit and fresh-owner repeats remain unmeasured.
The two-card resident mode is a sequential layer split, not within-layer TP;
the latter remains gated by its separate transport/arithmetic design.

## Next gate / revisit conditions

The coordinator runs the admitted card-3 streaming diagnostic and saves the
first real full-model token/state/timing evidence. Rebase the CPU oracle onto
this exact arithmetic identity, compare all states/tokens, and repeat in a
fresh process. Then qualify the resident cards-2/3 control. Use measured
non-GEMV and staging costs to choose the next optimization; no projected
throughput or synthetic exactness check replaces these gates.
