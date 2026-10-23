# Checkpoint policy adapter host integration — closeout

<!-- campaign-closeout -->

## Question and identity

Can the actual native v2 request front, locked checkpoint store, identity bridge,
bounded Parking policy and attached-owner adapter complete an eight-turn lifecycle
without restarting the owner? Tested 2026-10-23 on `steve-b70s` using the unchanged
packet198 GNU `HOST_ONLY` binary, SHA256
`41cbb6c4ad3bf6626dfba24d3bbd9d95d76b512102e8b94c164e9d421b3c40ca`.
Geometry was synthetic context64/vocab16 with four tiny layers. No real model
shards or GPU execution were involved. A three-row synthetic identity TSV bound
fixture metadata to the exact bytes; it was not a production model identity.

## Outcome

Corrected attempt B passed **8 requests, 44 generated tokens, 5 SAVE and 3 RELEASE
controls**, one model load and clean `request-limit` stopped with exit code 0.
Restored append matched fresh tokens and checkpoint state exactly. An edited
prefix selected prefill. Normal no-save and explicit same-ID replay both released
the pending reply. The owner PID was absent at closeout. This qualifies the tiny
host integration path only, with no speed, serving or real-model adapter claim.

## What worked

The adapter serialized policy lookup, generation and disposition under one owner
mutex. SAVE acknowledgement hashes matched native locked snapshots and the exact
full visible history. Append plans were validated and consumed by the next RUN;
native restore retained its own checks. Parking used conservative pre-SAVE peak
reservations, preserved old checkpoints until replacement was visible, and
deleted stale prefixes through the native store. The same binary served both
owner and metadata tools, with explicit experimental p198 contract admission and
no native relabeling. The final RELEASE preceded clean stopped.

## What failed or remains uncertain

Attempt A failed at its first SAVE: an empty synthetic identity TSV passed mini
startup but the checkpoint writer requires three stat rows when `--identity` is
provided. Native teardown was safe, no device work occurred, and the failed
script/configuration/source closure and full small run were retained before the
fixture correction. Attempt B used a fresh output, not an automatic retry.

The same-ID phase deliberately performs a fresh RUN then calls actual Parking
directly; normal `before_request` would delete the older checkpoint for that
shorter prompt. Its explicit adapter RELEASE passed; automatic `run_turn`
RELEASE on a non-None same-ID hit is separately CPU-mock tested. Policy deletion
removed replaced checkpoints after equality was recorded; surviving tiny states
and the comparison digest maps are retained. HTTP wiring and real-model use of
the full adapter/store/policy path remain unqualified. Packet198's separate
device worker proof does not close those integration gaps.

## Evidence and patches

- [Attempt B closeout and full artifact digest inventory](../integration/receipts/checkpoint-engine-host-b-closeout.json),
  with [compact result](../integration/receipts/checkpoint-engine-host-b/run/result.json),
  [exact plan](../integration/receipts/checkpoint-engine-host-b/run/plan.json),
  native receipt, eight result/reset/input records, five SAVE receipts, surviving
  tiny checkpoint payloads and copied executable Python source closure.
- [Attempt A failure/drain receipt](../integration/receipts/checkpoint-engine-host-attempt-a-failure.json)
  and [preserved failed source/configuration/run](../integration/lineage/checkpoint-engine-host-attempt-a).
- [Probe source](../integration/checkpoint_engine_host_probe.py),
  [probe/replay scope](../integration/CHECKPOINT-ENGINE-HOST-PROBE.md), and
  [adapter API and boundaries](../integration/CHECKPOINT-ENGINE.md).
- [Independent adapter CPU review](../integration/receipts/independent-checkpoint-engine-review.json)
  and [separate packet198 device audit](../stage2/packet198-postreply-checkpoint/evidence/independent-device-result.json).

Original B outputs remain at ignored `stage2/packet198-postreply-checkpoint/build/engine-integration-b`:
177 files, 5,474,617 bytes. The compact retained closure is 124 files, 841,857 bytes;
larger census/site/progress logs stay local with sizes and SHA256 values in the
inventory. No model binary, model weights or large output bundle was copied.

## When to revisit

Proceed to a separately reviewed chat/HTTP boundary only after its request limits,
rendering/tokenizer identity, cancellation and owner-admission rules are explicit.
Any live adapter test needs trusted launch provenance, the geometry-bound SAVE
reservation, root free-space admission and the existing fault/drain coordinator.
Reuse a persistent owner; no restart chain, power/memory changes or automatic
reboot/reset is implied. A replay must use a new reviewed scratch destination;
completed attempts and frozen packet identities remain unchanged.
