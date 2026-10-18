# Packet101 reseal, October 18

The original A control ran at 04:27–04:31 UTC. Planning A grid-1 then refused
because packet97's orchestrator had changed `selection.json`. That file was
an unused source-audit pin, not the selection used by packet101's runtime.
The old control, proposals, receipts and seals remain history. None of that
control's output is reused in the new bracket.

`reseal.py` projects the original verified CPU closure through an explicit
parent-input allow-list. It retains the source, object, binary and immutable
build-input pins. It drops the unused parent selection pin and copies the
hash-matched `evidence/object-identity.json` build receipt into
`lineage-inputs/packet97-object-identity.json`. The active closure has no pins
under packet97's `evidence/`, `decisions/` or `selections/`, and none for its
selection, submission pins, readiness, memory plan or orchestration seals.
Unknown parent output names are excluded by default; the migration additionally
asserts that the original selection is the only excluded existing pin.

The original receipts are retained and hashed as historical CPU evidence;
their old source maps are not live dependency maps for the new seals. Every
remaining live source hash, both binaries, fixtures and receipt gates are
verified before sealing. A changed kernel still refuses. The runtime's
selection, dispatch, memory plan, placement audit and fixture bytes are copied
unchanged from packet101's own original views. No rebuild, runtime arithmetic
change, GPU use, service, sudo or host setting change was needed.

Fresh views:

- `selections/control-reseal-20261018/`
- `selections/draft_attention-reseal-20261018/`

Fresh proposed queues (three jobs each, control / draft_attention / control):

- [A grid](../../ops/lane-queue/proposed-p101-reseal-20261018-A-grid.txt)
- [B mirror](../../ops/lane-queue/proposed-p101-reseal-20261018-B-grid.txt)

Every job name begins `packet101-reseal-20261018-`. Every output name begins
`p101-reseal-20261018-`, then the new candidate seal hash prefix, lane, index
and choice. The exact output paths are in the proposed files. No output exists
yet; no live queue was changed. Run the whole fresh A bracket, with B available
as its mirror. Records remain on A. After execution, `compare_reseal.py --lane A`
(or `--lane B`) uses only the new outputs and retains all existing quality,
acceptance and control-bracket requirements.

Validation:

- Both three-job grids pass the real queue planner against disposable queue
  directories. [Plan receipt](evidence/queue-plans-reseal-20261018.json),
  [A log](evidence/queue-plan-reseal-20261018-A.log),
  [B log](evidence/queue-plan-reseal-20261018-B.log).
- All 13 regression checks pass: existing selection/quality/comparison checks
  plus parent-output exclusion, retained build pins, changed-source refusal,
  local selection and unchanged binary checks, and fresh bracket output checks.
  [Test log](evidence/python-tests-reseal-20261018.log).
- [Reseal receipt](evidence/reseal-20261018.json) records both old and new seal
  hashes, the removed pin and the localized build receipt.

The first CPU plan rejected a sibling `selections-reseal-20261018/` directory:
the unchanged placement gate requires direct children of `selections/`.
The final views use that layout; the gate was not weakened.
[Failed plan](evidence/queue-plan-reseal-layout-rejected-A.log) and
[initial proposed payload](evidence/queue-proposal-reseal-layout-rejected-A.jsonl)
are retained. The unused initial generated seals remain locally under
`build/tmp/reseal-layout-rejected/`; they were never run or queued live.

Packet99/100 read-only audit: packet99's seven screen seals and packet100's
three screen seals do **not** pin packet97's mutable `selection.json` or
`submission-pins.json`. Both still pin
`packet97-record-bundle/evidence/object-identity.json`. That is the same class
of parent-evidence dependency, although its current hash matches all ten
seals; no parent hash mismatch was found. Their files were not edited and
their plans were not regenerated. [Per-seal audit](evidence/parent-pins-audit-20261018.json).

CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`. From this packet directory, the new preparation commands were
`reseal.py`, `queue_plan_reseal.py`, `-m unittest -v test_reseal test_packet101`
and `audit_parent_pins.py`. Sealing is intentionally creation-only; do not
rerun it over these existing views. The planning and read-only checks can be
repeated before scheduling while outputs are still fresh.

The opening `git pull --rebase` refused the unrelated dirty shared tree.
`git fetch origin main` showed local main and origin/main identical, so no
stash, branch, worktree or frozen-tree modification was needed.
