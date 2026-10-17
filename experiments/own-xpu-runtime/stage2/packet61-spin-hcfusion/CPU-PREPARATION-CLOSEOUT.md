# Packet61 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Combine packet56w's 250 µs controller/device spin and rank-0 queue property
with packet60's exact three-kernel HC fusion for the quantized compressed
Unsloth UD-IQ3_XXS Flash-Next lane. Preparation on steve-b70s, October 17,
2026; planned cards 0+1, split23/25, draft rank1, 4096 context, BF16 KV,
packet49 split32 oracle. This closeout ends CPU preparation only.

## Outcome

Accepted for coordinator screening and full-chain execution. Both builds,
878,040 compared HC bytes, 96 target fixtures, 24 tokens, 1,123 controller
cases, five mailbox fault cases and 31 wrapper/submission tests pass.
Both screen versions accept the seal; chain plan, prefix/oracle identities and
storage pass. There is no packet61 device speed or exactness measurement.

## What worked

Exact packet60 kernel source and compiled HC object reuse keeps its order and
math intact. Recompiling the combined main and packet56w device wait carries
both independent changes. Hash-bound hardlinks keep the build under 400 MB.
The chain and submission tooling retain all existing evidence gates and add
explicit HC identity checks alongside prefix/spin provenance.

## What failed or remains uncertain

Initial CPU build attempts exposed a missing copied `.inc` include and a
collision between inherited object basenames. Both were fixed locally; object
links now include a source-path digest. The first integrated fixture compile
mixed two checked-header trees and reported duplicate definitions. Its
fixture-data include now uses the combined engine's checked tree. No device
was contacted by any failed attempt. System Python lacked pytest; tests ran
with the existing vllm-xpu environment's `python3 -B`.

Packet56x was unsealed when integration began; its optional wait replacement
is deferred through the documented hook. Screen v3's generic interface accepts
packet61, but the coordinator must wait for that wrapper's own qualification.
Combined GPU speed, cold-prompt exactness and full-chain quality remain pending.

## Evidence and patches

[Source identity](evidence/source-identity.json),
[CPU fixture receipt](integrated-fixture/receipt.json),
[controller cases](evidence/controller.json),
[mailbox faults](evidence/mailbox-faults.json),
[chain tests](evidence/chain-tests.log),
[screen v1 plan](evidence/screen-v1-plan.json),
[screen v3 plan](evidence/screen-v3-plan.json),
[chain plan](evidence/chain-plan.json),
[screen seal](screen-seal.json), [chain seal](build-receipt.json),
[retention](RETENTION.md).

## When to revisit

Run the coordinator's matched screen, then the full chain against the unchanged
packet49 oracle. A record requires measured performance above the current
shared floor and all chain quality gates. A later wait variant needs its own
sealed configuration and comparison; do not change this tested candidate.
