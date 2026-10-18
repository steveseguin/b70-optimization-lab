# Packet97d: all identical sealed brackets, with lane-B drift

The owner's October 18 request changes only frozen-decision readiness. Every
completed bracket of the same sealed candidate and packet84 baseline is now
included, even when its output directory belongs to an earlier decision's
leave-one-out test. A must pass every bracket at +0.5% over its stronger
control. B needs one such win and cannot lose to both controls in any bracket.
Exactness and unchanged acceptance remain mandatory throughout.

The requested decision is `f1e5d7f47fc0fe54`; the matching older variant is
`d27742791d5b859d` / `without-93`. Both frozen JSON files retain their original
bytes. The two updated CPU entry points retain byte-exact historical copies in
`ops/packet97-orchestration/frozen97b/` for checking their frozen source pins.

| Lane | Decision / variant | Gain over stronger control | Signed control drift | Qualifies |
| --- | --- | ---: | ---: | --- |
| A | d277 / without-93 | +0.685643% | +0.048048% | yes |
| A | f1e5 / composite | +0.697105% | +0.064435% | yes |
| B | d277 / without-93 | +0.742682% | -0.071636% | yes |
| B | f1e5 / composite | -0.226902% | +1.046390% | no; above first control |

All four brackets are 13/13 exact and keep acceptance unchanged. None is
dropped. Both lanes pass the owner's new rule. Sources 91 and 90 satisfy the
unchanged two-qualified-source chain policy. These short diagnostic screens
are not a public performance result or a completed record chain.

Implementation and commands:
[identical-selection rule](../experiments/own-xpu-runtime/ops/packet97-orchestration/IDENTICAL-SELECTION.md).
The new tests cover selection/binary/seal identity mismatches, mixed decisions,
independently completed lanes, missing lanes, lane-A failures, lane-B loss to
both controls, quality/acceptance/boot failures, drift reporting, unchanged
chain policy, immutable historical pins, and every CPU preparation failure.

The first full CPU preparation passed its individual checks but correctly
refused final readiness when evaluator files changed during the run. A later
run also overlapped another session's packet98 proposal-helper changes. After
the source bytes settled, the final run completed at 04:47 UTC with
`ready: true` and reason `identical-selection evidence and all CPU readiness
checks passed`. The receipt contains all four brackets and their drift values.
No GPU, service, live queue, settings, sudo or other packet tree is touched by
this work. The generated packet97 chain proposals are CPU plans only.

Git synchronization: the required initial `git pull --rebase` refused because
another session had staged and unstaged changes. No shared work was stashed or
reset. `git fetch origin main` then showed zero commits on either side; the
other session subsequently committed its own work in the same checkout.

Validation: all 85 targeted packet97 tests pass, including the 33 new
packet97d cases. The completed shared-tree suite has 143 passing tests. The
concurrent session updated the older historical-pin assertion to account for
explicit preserved copies; packet97d did not edit review15 files. Logs:
`python-tests-97d.log` and `python-tests-97d-full.log` under the packet97 helper.

The concurrent packet98 session added five-view evidence readers to the shared
evaluator. Packet97d retains that integration and enforces each candidate's
loss-to-both-controls veto against its own adjacent pair; a later weak control
cannot erase an earlier loss. Its regression test passes. The four requested
v4 brackets and their conclusions are unchanged.

The final standalone `verify_ready.py` check is recorded in
`ops/packet97-orchestration/verify-ready-97d.log`. Required shared packet98
reader dependencies are retained with the evaluator, without changing their
contents, so its imports and preserved-pin checks are closed in Git.
