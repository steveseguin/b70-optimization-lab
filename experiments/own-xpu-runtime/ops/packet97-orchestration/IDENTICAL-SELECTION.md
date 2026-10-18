# Packet97d: identical sealed selection evidence

Only `orchestrate.py --decision <frozen decision>` uses this rule. A fresh
source selection keeps the existing composite/leave-one-out policy.

The evaluator enumerates every completed composite and leave-one-out bracket
on each lane across the saved decisions. It pools only the same candidate and
baseline selections, selection hashes, binaries, seals, dispatch, memory plan,
placement, profile and timing. The existing loader rechecks the full sealed
identity, twelve cold requests plus incident64, timestamps, current boot,
non-overlapping controls, oracle outputs, isolation and acceptance counts.

- A: every matching bracket must be exact, keep acceptance unchanged, and
  exceed its stronger control by at least 0.5%.
- B: at least one matching bracket must clear that bar. A candidate below both
  its controls vetoes readiness. Invalid quality or changed acceptance also
  vetoes readiness; a drifting non-win is retained in the report.
- Every matching bracket appears in `ready.json`, including failures, together
  with signed control drift: `100 * (control2 / control1 - 1)`. Failed quality
  receipts retain timestamp-derived diagnostic rates when available.
- The chain still needs two qualified sources, or at least 1.5% on both lanes.
  For that comparison, use the minimum qualifying bracket ratio per lane.
  These are short diagnostic screens, not new public performance records.

The decision's JSON is never rewritten. The replaced CPU entry points are
preserved byte for byte in `frozen97b/`. Historical pins for those two files
alone resolve to their preserved copies, and must match the frozen hashes.
Every other source, receipt, binary and seal pin is checked at its original
path. The prepared chain separately pins the frozen decision, preserved tools
and current evaluator. This is an explicit policy revision, not a reseal of
historical performance evidence.

CPU preparation still runs composition queue planning, resealing, dry run,
seal verification, input verification, storage admission and chain queue
planning. The readiness verifier repeats evidence evaluation and checks all
preparation bindings before `ready=true` is written. `verify_ready.py` dispatches
to the same verifier for this rule. No evaluator launches device work.

Run from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet97-orchestration/orchestrate.py --decision experiments/own-xpu-runtime/ops/packet97-orchestration/decisions/f1e5d7f47fc0fe54.json </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet97-orchestration/verify_ready.py </dev/null
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest -q -p no:cacheprovider experiments/own-xpu-runtime/ops/packet97-orchestration/test_orchestrate.py experiments/own-xpu-runtime/ops/packet97-orchestration/test_composite.py experiments/own-xpu-runtime/ops/packet97-orchestration/test_decision_readiness.py </dev/null
```

The targeted suite has 85 passing tests. After the concurrent packet98
updates, the full orchestration suite has 143 passing tests, including the
historical-pin compatibility checks. Review15 changes were made by the
concurrent session; packet97d preserves them. See `python-tests-97d.log` and
`python-tests-97d-full.log`.
