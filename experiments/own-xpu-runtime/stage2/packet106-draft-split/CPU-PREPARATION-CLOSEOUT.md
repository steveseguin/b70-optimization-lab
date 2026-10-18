# Packet106 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can rank0 evaluate the unchanged draft prefix's last 45,056 rows only after a
verified hit, while rank1 retains the complete miss path? October 18, 2026;
Unsloth Flash-Next UD-IQ3_XXS quantized compressed version, arithmetic oracle
`iq3-p49-split32-v1`, BF16 KV, intended two-B70 24/24 target and rank1 draft.
Frozen source parent: packet105 commit `339d7017a`; implementation milestone
`e53b46b5b`. Production is the same fixed route-fast / rec-both-plus /
wide64+halfcache / HC-wide / ordered baseline across all four views.

## Outcome

CPU preparation passes. GNU and Intel match every finite proposal byte in two
fresh runs each, including lowest-global-index ties; nonfinite rows refuse.
Eight full-size allocation checks and nine layout refusals pass. All eleven
startup windows pass for all four views (44 checks). Four seals and three
temporary queue plans pass. No device or model performance result is claimed.
Packet87t's +0.7749% remains modeled.

## What worked

An explicit verified-hit flag selects the short rank1 prefix and separate
rank0 suffix. Misses retain the original full prefix. Separate target/draft
mailboxes and scratch permit composition; the target verifies every token.
Actual transfer mocks preserve private target state and check both reset
controls and per-request trace ownership. The final build is 261,302,180 bytes.

## What failed or remains uncertain

Review found that inherited request reset clears suffix active controls. The
local services restore them; transfer logs now follow the new request output.
The first seal refused an external-resolving manifest alias; a byte-identical
local snapshot resolves it without changing the gate identity. No existing
packet was edited. Runtime mock backends do not prove device event behavior,
residency, output determinism or speed. The host rendezvous may erase the
modeled saving. The full record chain and promotion gates remain unqualified.

## Evidence and patches

- [Design and frozen lineage](DESIGN.md), [copy hashes](copy-lineage.json).
- [GNU/Intel repeated byte gate](evidence/cpu-byte-identity.json),
  [native scheduling](evidence/controller.json), [real transfer mocks](evidence/runtime-mock.json).
- [Allocation and refusal gate](evidence/full-shape.json),
  [every-window receipt](startup97e.json), [compressed full commands/results](evidence/startup97e-runs.json.gz).
- [Final seal verification](evidence/final-verification.json),
  [temporary queue plans](evidence/queue-plans.json), [retained build evidence](RETENTION.md).
- [Task record](../../../../notes/2026-10-18-own-runtime-packet106.md).

Implementation and helpers remain in this packet; generated source and small
CPU evidence are round-trip verified in the retained archive. Model weights
and the shared full oracle outputs remain outside Git, as before.

## When to revisit

The coordinator first runs [the B smoke proposal](../../ops/lane-queue/proposed-p106-smoke-B.txt):
one prompt, 64 tokens, combined candidate only, with fault review and graceful
drain. A passing smoke unlocks [the B grid](../../ops/lane-queue/proposed-p106-B-grid.txt).
An exact candidate beating both controls unlocks [A confirmation](../../ops/lane-queue/proposed-p106-A-confirm.txt).
Require unchanged draft proposals and acceptance counts. Preserve all gates;
no retry loop or automatic server restoration. Further optimization follows
actual device evidence, not the projection.
