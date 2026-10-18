# Packet97 CPU orchestration

## Packet98b: v5 intent planning and five-view readiness

The composite CLI defaults to `--wrapper v5`; `--wrapper v4` retains separate
loads. `v5_jobs.py --sources` prepares packets92/94/100/101. Every v5 intent is
control/candidate/control/candidate/control, with exact selection hashes and
records on lane A. **The requested current intents are blocked:** frozen v5
only switches route/recurrence in its registered packet91 lineage. Half-cache,
weightcache, and tile16 change load layout; other requested switches also lack
qualified native support. The queue planner refuses these proposals. Do not
enqueue them as runnable jobs or replace their selections with packet91's.

The packet97d evaluator also reads qualifying v5 receipts. Both candidates must
beat the maximum of all three controls; the slower candidate determines the
ratio. All thirteen checks, acceptance, identical-selection/binary/seal rules,
both lanes, the chain policy and all CPU readiness checks remain mandatory.
The shared lifetime never counts as two fresh processes. Different v4/v5 native
identities cannot be pooled. See the
[packet98b note](../../../../notes/2026-10-18-own-runtime-packet98b.md)
for exact refusals, proposed paths and CPU validation.

## Review 15: record-lane loss veto for new decisions

Use `review15/orchestrate_review15.py` for new decisions. It rereads every source
through its frozen loader and chooser, including lane-A confirmations of lane-B grid
winners. A completed lane-A result excludes that source choice if it is inexact
or is not strictly faster than both same-lane controls. A tie also loses.
The latest completed matching A bracket governs; pending A evidence does not
erase a completed result or hold up other sources. Packet93's head-transpose
therefore cannot qualify from its B win after its A loss.

The decision retains the exclusion reason, comparison rows, source and receipt
hashes. All inspected source windows (including absent/incomplete windows) are
checked again before a new decision is frozen. If any changes during collection,
the helper refuses that decision and requires a fresh read.

To record a new CPU-only decision without changing proposals, `ready.json`,
`screens-current.json`, the live queues or runtime preparation:

```sh
nice -n 19 ionice -c3 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/packet97-orchestration/review15/orchestrate_review15.py \
  --decision-only </dev/null
```

For later proposal/preparation work use the same new entry without
`--decision-only`. `--snapshot-only`, baseline pins, closures and frozen-decision
evaluation remain available. The matching `review15/verify_ready_review15.py` and
`review15/device-entry-review15.sh` carry the exclusion evidence into the existing
readiness gate. They do not launch a GPU during CPU preparation.

The old decisions `d27742791d5b859d` and `f1e5d7f47fc0fe54` and every original
Python tool they pin retain their original bytes. Their queued screen jobs
still use the original validator. The review15 subdirectory also preserves the
old tool inventory. The separate review-15 entry is necessary because editing
those pinned tools would invalidate the already-frozen jobs.
An old decision is evaluated as its original selection; it is never rewritten
to apply a later source result. New composition decisions use review 15.

## Historical review 14 / packet97b

A source qualifies for composition after **one** completed first-lane grid:
13/13 exact in every screen, unchanged per-prompt acceptance, and a candidate
faster than **both** same-lane controls. The adapter uses the frozen source's
loader and chooser, with its identity, oracle, seal and cold-request checks.
Packet93 retains its micro gate. Either grid direction can qualify; the first
completed qualifying direction supplies the choice. The second lane is not
required for a source. Invalid finished evidence is still rejected.

An unfinished window without a finish timestamp or failure markers is
**pending**, not failed. A stop reason, retained child, reporting failure,
completed invalid receipt, missing finished artifact, changed acceptance or
identity mismatch remains a failure. Packet91's old A rejection combined
unfinished and failed windows in one error. At the initial packet97b recheck,
the closing control was still unfinished; its completed grid now qualifies
route-fast plus rec-both-plus. The task note records the earlier snapshot too.

Use the CPU prefix for every command below:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet97-orchestration/orchestrate.py </dev/null
```

This collects current source evidence and freezes the qualified set in
`decisions/<hash>.json`. Pending sources are deferred. It writes
`../lane-queue/proposed-p97-composite-A.txt` and `proposed-p97-composite-B.txt`,
then plans all six jobs using temporary queue copies. The live queues are never
changed. The coordinator schedules the jobs. Each job binds the decision hash,
source receipts, tools and existing sealed view, with fresh decision-specific
output paths. No binary or view rebuild is needed.

The baseline remains packet84's selection. Packet91's qualifying route and
recurrence are candidate choices, so its gains are tested as part of the whole
composite. Each lane runs **control / composite / control**. The composite must
be 13/13 exact everywhere, keep acceptance counts unchanged and beat both
controls on **both** lanes. Standalone or micro gains are never added together.

`--snapshot-only` writes evidence and false record readiness without generating
jobs. `composition_ready` means sources qualify for a composition screen;
`ready` still means the full chain's CPU preparation passed. Missing composite
receipts cannot make `ready` true.

After scheduling, use `orchestrate.py --decision <saved-decision.json>` with the
same CPU prefix to evaluate **that exact decision**, even if more sources have
qualified meanwhile. Without `--decision`, a new qualified set creates a new
decision and output paths. A frozen decision cannot take new pins or closures.

If either lane's composite gain is below +0.5%, or below the best selected
single-source gain, the helper emits leave-one-out proposals and leaves record
readiness false. Gains use the stronger same-lane control. The comparison is
conservative: the smaller composite lane gain must reach the best source gain;
absolute speeds are never compared across lanes. Equality at either threshold
does not trigger fallback. A losing but exact composite also triggers fallback.

To prepare leave-one-out files independently:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet97-orchestration/composite_jobs.py --decision <saved-decision.json> --leave-one-out </dev/null
```

This writes `proposed-p97-leave-one-out-{A,B}.txt`. Each retained source gets its
own baseline / leave-one-out / baseline bracket on each lane. Removing packet91
removes its winning arm together; removing E1 retains E3, and vice versa. Every
variant is one of the already sealed 128 compositions. The generator only
plans. The coordinator measures and reviews these views before choosing a new
candidate.

`--pin key=baseline` and `--closed packet=reason` remain available for a new
decision. Pins only revert registered dimensions. A pending closure needs
explicit baseline pins for every affected dimension; failed evidence cannot be
closed. Partly reverting packet91 removes its whole qualified arm, avoiding an
unqualified subset. Pinning `experts=wide64` removes both E1 and E3.

The record requirements remain: two winning composite lanes, the existing
1.5%-on-both-lanes or two-selected-source rule, then the full unchanged sealed
chain, CPU rehearsal, input/storage checks and `verify_ready.py` before device
work. These short screens are diagnostic and never a record by themselves.

Tests:

```sh
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest -q -p no:cacheprovider experiments/own-xpu-runtime/ops/packet97-orchestration </dev/null
```

## Packet97e: same decision, fresh directory

The failed `device-cards01-a` remains history. Prepare a new directory without
changing the selected composition or its screen seals:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet97-orchestration/decision_readiness.py \
  --decision experiments/own-xpu-runtime/ops/packet97-orchestration/decisions/f1e5d7f47fc0fe54.json \
  --chain-output device-cards01-b </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet97-orchestration/verify_ready.py </dev/null
```

Use the exact `chain_command` in the resulting `ready.json`; preparation never
runs it. The command binds the new output and uses a separate systemd unit.
A later explicitly requested attempt can use `device-cards01-c`. An occupied
output or any selection change is refused. The original no-reselection guard
is unchanged.

The chain entry requires the new 128-composition, eleven-window CPU startup
receipt and installs the bounded KD reference repair. Target binaries and
selection seals are unchanged. For later evidence preparation use the packet's
`submission97e.py`; for the shared submission CLI use `submission_cli97e.py`.
These retain strict target identities and validate KD's explicitly bound draft
reference identity. Neither preparation nor this repair authorizes submission.
See the [repair note](../../../../notes/2026-10-18-own-runtime-packet97.md#packet97e--kd-host-reference-repair-and-a-fresh-chain-directory).
