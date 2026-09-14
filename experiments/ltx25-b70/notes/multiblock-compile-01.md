# Multi-block compilation candidate

The cache-limit failure below is preserved. Its private-entry successor now
passes the actual CPU10-graph test; [successor and inactive packet](multiblock-private-entry-02.md).

September 14, 2026. Inactive successor to the exact but slower block24 compiler.
The paired native timing result was a loss (+99.797 ms median preview versus
adjacent restored controls); no speed improvement is inferred from exactness.

The candidate expands clone-local compilation to a bounded selected block set,
with one aggregate native-pre_run lifecycle guard and independent graph receipts
for every selected block. Node selections are single24, boundary4 (0/20/21/47),
and all48. Candidates remain available after switching back to restored dispatch.
Original registered model weights, arithmetic kwargs, stage schedule and route
transfers are unchanged. Native activation/RMS compiler boundaries remain pinned.
No Dynamo cache limits, precision settings or host settings are changed.

The aggregate guard reuses one full registry walk. Each native pre_run checks
all selected block state; each subsequent route validation checks its current
block state and all registered routing/bindings. Existing late-mutation, hooks,
current-executing-patcher and ownership rejection remain. Independent source
review found no blocker for this static model contract.

The CPU lifecycle test passed54 checks using actual ModelPatcher.pre_run and a
compiler dispatch spy. It covered restored-candidate reuse, original parameter
ownership, all four boundary selections, invalid/duplicate selections, graph
path collisions, selected late hooks, unselected registration mutation and
rejection before compiled dispatch. Instrumentation observed one complete
registry walk per lifecycle validation, state scans only for the current block
on dispatch and all selected blocks at pre_run. This is mechanism evidence,
not a speed measurement or numerical compilation result.

The node's12 stdlib graph-receipt checks pass. They establish receipt contract
behavior only, not native execution or a full state-machine qualification.

Evidence: [CPU progress](../data/multiblock-cpu-01/summary.json),
[lifecycle receipt](../data/multiblock-cpu-01/lifecycle.json),
[node contract receipt](../data/multiblock-node-contract-stdlib-01.json),
[adapter delta](../patches/ltx-multiblock-compile-01.patch).
Full retained CPU evidence lives under
/mnt/fast-ai/bench-results/ltx25-baseline-20260913/multiblock-lifecycle-cpu-01.

Actual bound CPU compilation, native GPU stages/full clips and paired speed
remain pending. The persistent PID17769 still runs unchanged packet05, idle on
restored dispatch. No application reload or GPU request was made for this source
and CPU lifecycle work. The next packet will permit bounded selections in one
application session; a necessary controlled application reload is already within
the user's authorization, with no repeated approval pause.

A cache-limit caveat is preserved: the three native selections would require
106 stage graphs, but being below accumulated_recompile_limit256 does not prove
that recompile_limit8 permits them. Backend closures alone do not demonstrate
separate frame identity budgets. Require actual per-block graph coverage and
halt on the first compiler/quality failure; never accept eager fallback or
blindly raise limits. Boundary4 after single24 tests cumulative10 graphs early.

## Actual CPU compilation: cache-limit failure

The composed five-block test (0/20/21/24/47) ran both first-stage seeds exactly,
then failed while compiling the second stage. Eight graph receipts were emitted;
the ninth graph hit recompile_limit8 with BACKEND_MATCH failure between the
per-block backend callables. fullgraph=True raised a hard error; no fallback
or complete second-stage qualification was accepted. This is a failed scaling
candidate, not a numerical mismatch or native GPU fault. See the retained
[capture receipt](../data/multiblock-cpu-01/capture.json) and complete external
multiblock-capture-cpu-01 directory. The source/test identities and exact command
are recorded in the progress JSON. No retry of these unchanged sources is useful.

Next candidate: give each clone-local compiler entry its own Python code object
while calling the unchanged original module. Preserve the v1 source and test
failure. Keep compiler limits unchanged; qualify the distinct-frame hypothesis
on the same composed10-graph test before preparing a native runtime.
