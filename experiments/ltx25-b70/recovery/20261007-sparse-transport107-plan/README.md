# Sparse sampler transport107: CPU plan only

This is a proposed immutable successor to qualified packet106. It does not admit
new work on the currently loaded106 application. Runtime injection, diagnostic
budgets, proof integration, and source closure still require review.

The model workload retains all ten original fixtures, numerical graphs, seeds,
geometry, sampler/decode depths, and four-tensor comparisons from106. It uses
20 native requests,14 candidate requests,14 timed-fast requests, and nine setup
requests:57 total,50 raw captures,4GiB write allowance above a50GiB reserve.
The final action remains `verify-fast-timed`. There is no timed control block or
passive fdinfo collector. All14 timed-fast requests explicitly disable tracing;
their ten scored outputs use scope `uninstrumented-after-sparse-transport`.

The independent `diagnostic-descriptor.json` is pending a frozen injection
contract. It proposes at most one actual candidate sampler job per each of the two
registered sampler workers (at most two jobs/two workers), chosen from physical
clip IDs99907104–99907109. These are output producers4–9,
delivered by candidate requests8–13 after the four pipeline fills. Selection
must bind actual job identity to registered worker index0/1 and owning thread
identity, never submitting-request parity. Both workers must be covered or the
trace is incomplete; no extra requests or replacement jobs are permitted.
Within each selected job, each stageA/B selects its second observed
forward, not a presumed scheduler step. Missing observations cannot be replaced
with another job on that worker. Event/output caps are intentionally not invented here or
embedded in the semantic plan. Source-bound admission and verification of zero
tracing throughout the later timed block remain runtime obligations.

Plan construction pins106's manifest as predecessor and99b as the unchanged
graph constructor. Namespace `resolution-sparse-transport-20261007` uses
native indices99907000–99907019, setup capture indices99907030/99907041,
candidate99907100–99907113, and timed-fast99907200–99907213. CPU tests check
collisions against sealed101,101b,101c,102,103,104,105,106 plans and schedules;
the coordinator still checks actual runtime admission before executing.

```sh
python3 -B plan_reference.py validate --plan-file candidate-plan.json
python3 -B -m unittest -q test_plan_reference.py test_schedule.py
```

This is not a speed record, visual-quality judgment, endurance result, or
qualified transport optimization. Packet106's invalid passive diagnostic stays
invalid; it only supplied an exploratory reason to inspect transport directly.
