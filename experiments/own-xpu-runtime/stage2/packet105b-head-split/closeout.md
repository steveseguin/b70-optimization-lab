# Reset repair CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

October 18: copy frozen packets105/106 and validate the request-reset suffix
repair without GPU work. Source identity is in `copy-lineage.json`; selected
views retain the unchanged model, weights, arithmetic and BF16 KV. Intended
device hardware is the four-card host's B pair, then independent A confirmation.

## Outcome

CPU repair, byte, allocation, mock and every-window startup checks pass for
the scheduled views. Proposed device jobs plan successfully on temporary
queues only. No device equality, model speed or record improvement is measured.

## What worked

Restoring the private active flag after reset permits the suffix reduction.
The negative control detects the old skip. Full-vocabulary byte checks and
all-window startup validate distinct parts of the path. Per-window receipts
are persisted immediately and bound to their exact source identities.

## What failed or remains uncertain

Inherited fixture permissions and harness loops covering an excluded view
needed local preparation fixes; they are described in the work note. Neither
was a GPU fault. CPU success cannot prove device correctness, transfer ordering,
real residency or performance. The device micro and full twelve-prompt smoke
must complete exactly before any grid. No automatic retries are configured.

## Evidence and patches

[Reset regression](evidence/reset-regression.json),
[byte identity](evidence/cpu-byte-identity.json),
[allocation gate](evidence/full-shape.json),
[transfer mock](evidence/runtime-mock.json),
[startup summary](startup97e.json), [retention](RETENTION.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet105b.md).
Generated source and individual receipts are member-hashed in the retained
archive. Model weights and original oracle captures remain local external inputs.

## When to revisit

Coordinator execution of the proposed micro and complete candidate smokes is
the next step. Only matching exact evidence admits the B grid; only an exact
improving B winner admits fresh A confirmation. Any mismatch needs a retained
device trace and a new copy, not mutation of these completed seals.
