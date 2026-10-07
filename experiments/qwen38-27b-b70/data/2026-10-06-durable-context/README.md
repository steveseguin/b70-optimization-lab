# Frozen durable-context pilot

Prepared 2026-10-06. **No live model trial has been run with this harness.**

- `development/`: seed 7, both writing styles, 48 batches each. The extraction
  gate uses 16 fixed batches per style, 53 events each.
- `holdout/`: seeds 101, 202 and 303, both styles, 48 batches each. Every task
  has eight current-state, eight historical-detail and eight cross-reference
  questions. These six cases are reserved for model evaluation.
- [plan.json](plan.json): eighteen trials, balanced arm order, task/file/code
  hashes and decision rules. Regenerate with the documented freeze command and
  compare bytes; changing the implementation requires a new recorded revision.
- [cpu-validation.json](cpu-validation.json): six development runs with an
  oracle-fed stub, 144/144 scripted answers, and both 16-batch extraction stubs.
  All model-quality and speed gates correctly remain false. Full local logs
  are under the artifact path recorded there; they are not model evidence.

The implementation passed 58 durable-store/pilot/campaign tests and nine
historical-export tests. The corresponding site importer passed 11 tests;
the site passed offline evidence, build, link and SEO checks. Desktop and mobile
inspection found no page overflow; wide history tables scroll within the page.
Repository checks found zero broken document links or missing manifest paths.
The global pin audit still reports the pre-existing 231 drifted pins of 318,
outside this change; those historical experiment pins were not rewritten.

The host's protected `context-planE-a1` server and Harbor trial were still active
at 23:59 UTC. No live harness, server, supervisor or queue was changed. The next
step, after that campaign releases the endpoint and the usual health checks
pass, is the development extraction gate. The runner requires matching passing
calibration records before it will send held-out requests.

See the [protocol](../../notes/2026-10-06-durable-context-prereg.md) and
[commands and limitations](../../scripts/context/durable/README.md).
