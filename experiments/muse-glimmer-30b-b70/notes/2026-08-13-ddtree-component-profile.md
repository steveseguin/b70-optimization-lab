# Functional DDTree component profile: verifier remains dominant

Date: 2026-08-13

## Result

The functional budget-15 DDTree path was temporarily reinstated behind its
default-off guard and instrumented with synchronized component timing. At 128
completed tree rounds, the cumulative means were:

| component | ms/round |
|---|---:|
| target decode plus 16 sampled-row reads | 47.993 |
| committed DFlash process, device complete | 2.337 |
| unified-KV prefix forks | 0.219 |
| selected-leaf KV promote/keep/truncate | 0.284 |
| tree build, batch, walk, free, and post accounting | 0.047 |
| complete profiled tree transaction | **50.882** |

The transaction timer begins after DFlash proposals already exist. The
independent speculation profiler measured the preceding draft phase at
**6.78 ms/round**, so the relevant cycle is about **57.66 ms**, consistent
with the earlier integrated 55--58 ms request-derived rounds. This resolves
the optimistic accounting error: DDTree did not unexpectedly spend several
milliseconds in CPU tree bookkeeping. The target verifier/sample path itself
still occupies about 48 ms, and the DFlash proposal pass remains another
roughly 6.8 ms.

The report covered all 65 prose rounds, all 49 code rounds, and the first 14
JSON rounds. It averaged 4.984 outputs per round. Even on that favorable
prefix, 100 tok/s permits only 49.84 ms per round; the profiled transaction
alone exceeds that before adding DFlash proposal generation. On the actual
full functional run, mean emitted tokens per round were lower and the required
saving was roughly 8 ms/round.

The synchronized diagnostic is not a throughput comparator. Its output also
changed the prose identity, so it is component evidence only, not a quality or
speed result.

## Evidence

- source profiler: `370e85b4a`;
- config:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-ddtree-component-profile256.json`;
- JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-ddtree-component-profile256-20260813.jsonl`,
  SHA-256 `b5f4e2961b718c79fd163dbace8f8d61670bf2eb604a6298a0e907c2ed43a4a2`;
- server log:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dflash-ddtree-component-profile256-20260813-ddtree-components.log`,
  SHA-256 `33b6ada13a135a3cf0f4d3b90df474f91e67c2a5f2970c50d123e78722df76fd`.

## Decision

Close the functional DDTree implementation again after preserving this
profile. Further DDTree bookkeeping work cannot close the gap. Kernel work
must first remove several milliseconds from the TP4 target verifier and/or the
proposal pass before tree integration is reconsidered.
