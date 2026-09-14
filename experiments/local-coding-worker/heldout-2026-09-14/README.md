# Two held-out worker issues

Both issues reproduce on clean ML Bottleneck commit
`8df1372c4f20fc8ae0bf4e35e1b75084327b17fc`.
The source repository remains clean. Baseline checks ran against a plain
`git archive` snapshot in `snapshot/workspace`; no model, GPU, network, or
Docker operation was used. Task prompts describe behavior and constraints,
without prescribing implementation changes.

## Context-sweep latency at batch sizes above one

Task: `../../../worker/tasks/ml-context-sweep-batch-latency.json`.
Acceptance: `../../../worker/acceptance/ml_context_sweep_latency.mjs`.

For the same 2048-input / 128-output Qwen3.8 27B request on one RTX 4090,
batch 4, the public `predict()` API reports first-token latency of 4.646 s;
the context sweep reports 1.1614 s. Both report the same prefill throughput.
At batch 1 the two APIs agree. This violates the existing per-request latency
versus aggregate-throughput accounting documented in `docs/sdk.md` and used
by `predict()`. Scope is the derived context-sweep latency and regression
coverage, preserving existing prediction and calibration values.

The acceptance check covers batch 1, 2 and 4, all returned context points,
public SDK agreement, unchanged prefill/decode predictions, and unchanged
caller input. It rebuilds the SDK inside the editable snapshot, using only
Node's standard library. The baseline exits 1 with the registered error marker.

## Incomplete duplicate depth flags

Task: `../../../worker/tasks/ml-incomplete-depth-flag.json`.
Acceptance: `../../../worker/acceptance/ml_incomplete_depth_flag.mjs`.

`llama-bench -d 512 --n-depth` is currently recorded as an unambiguous depth
of 512 even though the final depth flag has no value. Short, long, and
equals-form variants have the same failure. The existing parser and tests
already require ambiguous or malformed depth specifications to remain
unresolved, making this a missing edge case in that established contract.
Scope is parser behavior and focused regressions; historical benchmark data
and calibration remain untouched.

The acceptance check covers five incomplete duplicate variants, existing
sweep/duplicate/combined-test rejection, valid zero and positive depths,
quoted values and executable paths, and an unrelated-command control.
The baseline exits 1 with the registered error marker.

## Evidence

`evidence/` retains each command, exact source and acceptance identities,
exit status, expected failure marker, stdout, stderr, and their hashes.
`evidence/original-repository-check.json` records the final clean-source check.
`snapshot.json` binds the source archive and original tree.

These tasks are held out from the original five worker issues. No candidate
fixes or model runs have been performed for them.
