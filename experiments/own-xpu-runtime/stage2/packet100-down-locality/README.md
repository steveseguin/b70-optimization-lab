# Packet100: exact DOWN load locality

CPU preparation is complete for two candidates and production. No device
correctness or speed is claimed. **The real-route microbenchmark is blocked:**
packet77/86 retained route hashes, but their raw route vectors were not found.

- `down-interleave` changes workgroup order across expert slots.
- `down-tile16` transposes the same packed code/scale bytes within 16-row tiles.
- Arithmetic remains `iq3-p49-split32-v1`, including every FP32 chain/tree,
  BF16 boundary, route and status write. Weight size is unchanged.

The copied packet97 engine retains its composition dimensions. Seventeen
startup views include both maximal packet97 corners and all six independent
packet99 gate/up variants crossed with both DOWN candidates. These are
compatibility checks, not proposed combined performance arms. Packet99 gate/up
sources are copied and pinned; their separate campaign is not reopened here.

## Passed CPU gates

GNU and Intel each ran production and both candidates twice. Each run compares
36 complete output/status cases, 62,208 raw FP32 chains, 1,944 trees, all 65,536
half-scale patterns and 167,961,600 byte-permutation checks. Fixture cases cover
2560x640 and short rows, 8/10 selected slots, offsets/tails, invalid and duplicate
routes with distinct activations, NaN/Inf and zero/subnormal activations.
Full-size startup runs all 17 views on both ranks through the actual Arena,
post-load capture and draft setup, mocking only payload/backend. All 68 short
or misaligned allocation tests and 14 unsupported-mode tests refuse; five bad
selection cases refuse. Fifteen Python tests, closed-environment worker imports
and both real lane admission predicates pass. Three seals and five temporary
queue plans pass. The build is about 151 MB; the smallest composition margin
is 630,519,094 bytes under the unchanged arena limit.

Offline linked BMG assembly uses 128 GRFs and 79 static load lines in all three
kernels. Static instruction counts are 2981 / 3016 / 2984 for production /
interleave / tile16. No scratch load/store or spill code is present. These are
compiler observations, not device performance, cache counters or occupancy.

## Next device boundary

`route_inputs.py --raw-root <retained-raw-tree>` accepts only route files whose
bytes match all packet77/86 inventory hashes. It requires all 12 fixed prompts
and both ranks/layers, deduplicating only identical vectors. The retained
inventories describe final per-layer states, not a full per-token trace.
The prepared native micro uses full 512-expert banks and those routes, synthetic
weight/activation values, exact output checks, and 40 alternating pairs per
candidate per route vector. A separate 512 MiB device scrub precedes every timed
arm; no host cache is touched. It times the actual shipped operation bodies.
This remains an operator diagnostic, never a model benchmark.

The run wrapper refuses missing route bytes before opening any GPU. Every
candidate must take <=85% of production kernel time overall, in both ordering
halves and on every route stratum. Only then may its own B bracket run, followed
by the exact same improving winner's A bracket. The shared pinned v4 wrapper
runs its 64-token oracle smoke and full fixed suite; all 13 exact checks and
unchanged per-prompt acceptance remain required. Records run on A in a later
qualified bundle. This packet explicitly refuses record/K2-merge/submission
helpers; no record chain is registered.

New proposals, never enqueued:

- `ops/lane-queue/proposed-p100-micro-B.txt`
- `ops/lane-queue/proposed-p100-down-interleave-{B-grid,A-confirm}.txt`
- `ops/lane-queue/proposed-p100-down-tile16-{B-grid,A-confirm}.txt`

Paths above are relative to `experiments/own-xpu-runtime/`. Plans use the
packet90 `--direction B-grid` pattern and separate single-candidate brackets.

[Task note](../../../../notes/2026-10-18-own-runtime-packet100.md),
[preregistration](PREREGISTRATION.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md),
[final verification](evidence/final-verification.json),
[route inventory](evidence/route-inputs.json), [retention](RETENTION.md).

All CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, an 8 GiB address-space ceiling and packet94's compiler-turn lock.
Supported preparation entry points are `build_engine.py`, `cpu_gate.py`,
`full_shape.py`, `inspect_registers.py`, `build_microbench.py`, `python_gate.py`,
`seal.py`, `queue_plan.py`, and `final_check.py`. Other inherited helpers are
source context, not a claim that the packet97 record chain is qualified here.
