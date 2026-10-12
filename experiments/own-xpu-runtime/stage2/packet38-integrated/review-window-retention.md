# Independent offline window-retention review

Source review passed after concrete fixes in `retain_window.py`. It now checks
recorded run/rank receipt hashes, finished ownership and exactly one clean
teardown owner per rank before deleting anything. Pair identity must match;
both target inventories must have their recorded raw bytes, and MTP windows
must retain all five rank-1 draft-cache files. Tokens, guesses, hit/miss events,
fixtures and final states must match across controllers. Recorded oracle token
and fixture bindings are checked again. Symlinks are rejected before resolution.

Suite retention requires its finished summary/request receipts, clean rank
ownership, verified state archives and both runtime inventories, and every
recorded retained fixture byte/hash. K0/K1/K2/W0p/KD cannot be removed through
either entry point. The comparison receipt is written atomically before
archival; it reports an incomplete retention until every verified archive is
recorded. An archive failure retains a false/incomplete receipt and does not
claim successful cleanup. If an earlier archive already completed, that archive
remains linked while the unprocessed tree stays on disk.

Thirteen packet-local synthetic CPU checks passed in
`window-retention-gates.json`, including successful pair/suite retention and
refusal of failed windows, changed receipts, retained owners, missing target or
draft state, identity/token differences, prerequisites, symlinks, corrupted suite
fixtures and archive failure. These tests use synthetic small evidence and start
no rank or device process. The helper and tests do not establish a device-window
pass or a speed result. WINDOW.md's sequencing and commands required no change.

An additional field audit used the archived outputs of the actual host-backend
window dry-run (`scratch-resume-final-models-1791786100271674302.jsonl.gz`). All
six controller pairs have matching reconstructed signatures, clean ownership,
one valid teardown owner per rank, 206 raw target-state file hashes and 32 mini
fixtures; W2m/W2mc include all five required draft-cache files. Both WS/WSs
contain three completed miniature requests, matching summary/receipt data and
valid archived state-retention/runtime-inventory fields. These are observed
host-run fields, not fabricated schema examples.

That archive contains run trees directly and has no outer `window.json` records.
The remaining wrapper fields were checked against `window.py`: it supplies the
required pair identity, exact oracle bindings and receipt hashes. Mini suites
intentionally omit real `oracle_check` and contain four layers per fixture step;
real suite mode supplies the checked oracle result and 48-layer fixtures. The
helper's real-window requirements therefore remain intact. No legitimate
coordinator field mismatch was found. No archived scratch was restored or
deleted, and no rank was started for this audit.

Final source refresh: independently reread the suite timing-metadata and Intel
CPU export identity deltas. Timing changes affect receipt metadata only; the
state-retention path and exact emitted output remain unchanged. Offline window
retention imports `retained_state_binding`, which is unchanged; compiler checks
are confined to CPU `export_run`. All 13 lightweight retention tests were rerun
on these final sources and passed. No rank or device process was launched.
