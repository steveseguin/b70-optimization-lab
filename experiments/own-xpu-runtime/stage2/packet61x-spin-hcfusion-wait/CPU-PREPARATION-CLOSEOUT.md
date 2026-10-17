# Packet61x CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet61's exact HC fusion retain its kernel bytes while adopting
packet56x variant (a) for every covered wait? October 17, 2026, steve-b70s;
CPU preparation only. IQ3 compressed model, packet49 split32 oracle, full
16-bit KV, unchanged target and 91,392-row draft prefix.

## Outcome

Prepared and sealed for coordinator testing. Both builds pass. All 1,123
controller cases, seven wait checks, five mailbox-fault checks and 33
chain/submission checks pass. The candidate matches packet56's 96 target
fixtures and 24 tokens; the unchanged HC fixture compares 878,040 bytes.
V3 lane A and lane B plans accept the seal. Full-chain plan, shared oracle,
parent prefix windows, external output registration and submission pins pass.
No GPU, service or external submission ran. Packet61x device quality and speed
remain unmeasured.

## What worked

A minimal host rebuild replaces the mailbox, device and pending-progress wait
paths with packet56x's fixed pure-spin helper. All 71 inherited link objects
are unchanged hardlinks. The embedded 5,355,244-byte kernel bundle is directly
byte-identical to packet61. The build retains about 108 MB logically.

Storage admission passed with 4,449,245,184 bytes above the required reserve.
That is a snapshot; the coordinator must repeat admission at launch.

## What failed or remains uncertain

Packet61's hook is not a binary selection, so selection-only reuse was rejected.
The first local build finalization rejected an obsolete source hash in the
retained primitive sub-receipt; the builder now verifies packet61's final
sealed build receipt, whose complete source map passes. No parent was edited.
The system Python lacks pytest; the existing test environment ran the checks.
An initial ELF inspection snippet had an indentation error and produced no
receipt; the retained comparison script passes against both executables.

The supplied v1 screen results motivate the candidate, but neither additive
speed gains nor v3 timing are assumed. Full device correctness and fresh-chain
performance remain the coordinator's next work.

## Evidence and patches

- [Source identity](evidence/source-identity.json), [object identity](evidence/object-identity.json),
  [embedded kernel bytes](evidence/kernel-bundle-identity.json).
- [Build commands](engine-commands.json), [build receipt](build-device-receipt.json),
  [target/HC CPU fixture](integrated-fixture/receipt.json).
- [Controller](evidence/controller.json), [waits](evidence/wait.json),
  [mailbox faults](evidence/mailbox-faults.json), [tooling tests](evidence/tooling-tests.log).
- [V3 lane A](evidence/screen-v3-plan-A.json), [V3 lane B](evidence/screen-v3-plan-B.json),
  [chain plan](evidence/chain-plan.json), [queue plan](evidence/queue-plan.json).
- [Screen seal](screen-seal.json), [chain seal](build-receipt.json),
  [submission pins](submission-pins.json), [retention](RETENTION.md).

## When to revisit

The coordinator runs the documented v3 screens with matched controls, then the
full eleven-window chain under fresh admission. Only qualifying full-chain
evidence above the current record floor may proceed through submission tools.
Keep all parents sealed and preserve failed or negative device evidence.
