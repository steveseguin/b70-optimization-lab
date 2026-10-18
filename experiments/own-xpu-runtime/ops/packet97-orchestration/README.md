# Packet97 CPU orchestration — review 14 / packet97b

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
