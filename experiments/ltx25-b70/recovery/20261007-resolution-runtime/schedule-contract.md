# Pinned resolution setup schedule

`schedule.py` constructs seven setup graphs using the exact qualified99b manifest
`f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`,
six explicitly SHA-pinned parent graphs and the reviewed fixed resolution plan.
It imports no model/runtime/device modules and submits no requests.

```python
envelope = build_schedule(packet=PARENT, plan_path=PLAN)
rows = envelope['schedule']['rows']
validate_schedule(envelope, packet=PARENT, plan_path=PLAN)
```

Runtime callers must explicitly supply the sealed packet's
`resolution/candidate-plan.json` as `plan_path`, rather than use the repository
convenience default. `packet` remains the pinned immutable99b parent, not the new
successor. Both inputs are verified by fixed hashes; the schedule cannot select
arbitrary unreviewed graphs. `validate_schedule` reconstructs all rows, rather
than trusting a self-updated JSON hash. CLI writes the plan to stdout only.

Frozen schedule SHA:
`9f79ee01c507d46c106f9e0037eda772a20a717a49d3de03a2aca06785517441`.

All seven setup request names begin `resolution-ref101c-20261007-`; the 25 unconsumed plan request names retain `resolution-ref-20261007-`:

| Suffix | Phase | Operation and prerequisite |
| --- | --- | --- |
| window-probe | native-setup | Original40-prompt window probe; same numerical inputs |
| prepare-native | native-setup | New singleton node490 `LTXResolutionPrepareNative(run_name)` after passed window probe |
| pin0 | optimized-setup | Pin sole sampler worker0, only after verified-reference/optimized-preparation barrier |
| capture0 | optimized-setup | One nonlean graph capture request at fresh index99901030 after pin0 |
| coverage | optimized-setup | Actual W1/two-stage coverage after sample completion and idle barrier |
| decode-probe | optimized-setup | Original ten seeded640 native-vs-replica decoder checks after coverage |
| freeze | optimized-setup | Original exact eager/replay/repeat chain and memory/residency freeze after decode probe |

Each row contains `kind`, `phase`, `name`, full `graph`, canonical `graph_sha256`
and `depends_on`. The `boundary_dependencies` mapping additionally links the
first native request to native preparation, native verification to all six native
executions, optimized preparation to native verification, first candidate request
to freeze, and timing to verified candidate evidence. These are declarative
obligations: the trusted authority/integration adapter must enforce them. A graph
name or successful ComfyUI history is not a passed setup verdict.

## The single W1 capture

The parent graph is `graph-capture-all48-pipe-samp2-tsh-win.json`, SHA
`181b2fe7e9daed17f516a38f0dd93d5b4e7d9f26b7c8673a419b0dd1fc0385bd`.
Its sampler mode stays `pipeline`, without lean memoization or decoder replica.
Sampler depth changes2→1 for W1. Decoder stays `pipeline-save`, depth1,
upstream_depth0 and receives the sampler-emitted index through its existing edge.
All graph nodes/edges and numeric sampler/decode operations remain intact.
The latent initializer becomes320×192, giving final640×384,25frames,B1. The
three geometry-aware nodes receive only the new reviewed mode/qid/output fields.
Text/seed come from the already pinned native boat graph. Run names and the two
integer clip indices are bound to the capture request.

Actual99b `ltx_pipeline.run_behind` submits index99901030 once. With no predecessor,
it returns emitted_index=-1 immediately; the worker computes both sampler stages
in the background. Actual `pipeline_decode_node`'s negative-index branch returns
placeholders before defining/submitting any decode job. Node414 therefore records
only an unscored placeholder for this request. The existing native decoder gate
and required replica probe are not bypassed: no replica is requested here.

The coordinator must wait for `pipeline-done-sample-99901030.json` with finite
success, inspect failed-job files and actual queue/worker state, preserve the
completed un-emitted sample identity and retire that tail at the explicit barrier.
It must never clear unfinished jobs, replay the capture request, or add a second
fill automatically. Coverage must show all48 routes, one worker and both geometry
signatures before the decoder probe/freeze. Exact raw candidate comparisons still
occur only later against independent native references.

## Counts and limits

The frozen main plan has25 requests; these seven setup requests produce32 total
submissions. All25 plan requests have raw capture nodes, including six placeholder
fills; the one setup capture adds another placeholder:26 capture requests total,
below the32 capture cap. Window/prepare/pin/coverage/decoder-probe/freeze do not
add raw captures. Nineteen main-plan captures are full emitted clips; these are
six native captures, three candidate emissions and ten timed emissions cycling
three fixtures. The unused six capture slots are reserve, not permission for
extra requests. Preview files, logs and pending work still consume storage and
must remain inside the separate4GiB runtime allowance and50GiB root reserve.

## CPU verification and pending integration

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_schedule.py
```

Eight controls verify exact reconstruction and ordering, unchanged numerical
inputs of five existing setup graphs, singleton native preparation, bounded
capture-only field deltas, actual pinned `run_behind` first-fill behavior, changed
source graph refusal, rehashed schedule refusal and changed plan refusal.

Native preparation implementation, strict setup verdict checks, executor
registration, quiescence/retirement, evidence gates and final runtime sealing are
separate components. This schedule remains CPU-reviewed planning evidence; it is
not a successful runtime, memory qualification or output-quality result.
