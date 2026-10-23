# P207 — paired GDN projections in the HOST_ONLY Engine

P207 connects a two-input projection operation to the actual Engine row banks and
prepared-command path introduced by [P206](../packet206-host-engine-chunk/README.md).
This is synthetic CPU preparation. No model, GPU kernel, service or device window
is executed by its build recipe. The fresh B designated host proof passed:
32 requests, 108 intermediate state comparisons, 13 complete checkpoint maps,
and 400 captured paired sites replacing 800 original projections. The full-shape
Q6 ABI/arithmetic proof also passed. See [host-proof.json](evidence/host-proof.json).

The earlier A attempt saved its first paired request with all 20 state blobs plus tokens.bin exactly equal
to serial. The harness then tried to read `owner/census.json` before the paired
owner had closed, so it failed before completing the remaining requests. The
single incident SIGTERM stopped that CPU owner cleanly (exit 0, safe to exit,
zero in-flight work and zero live bytes). This is an incomplete harness attempt,
not a complete P207 pass or a GPU/model fault. The failed attempt is retained. The harness keeps schedule, captured/issued, skip-count and non-alias checks
per request; only the allocation-census identity join is deferred until owner
closure, when the census exists. Its regression tests cover this ordering. Root executed one fresh B rerun after review.
The compiled runtime and arithmetic source remained unchanged between attempts.

## Concrete change

For mini GDN layers 0 and 2, the Engine executes both rows' HC attention prefixes,
then one captured qkv pair and one captured z pair. It suppresses exactly the two
original projection sites for each row. Each row's causal GDN suffix and ordinary
FFN then executes in order. QSA/PLE, final prompt, decode, same-generation resume,
canonical publication and fatal-partial-chunk behavior retain P206's paths.

Each row retains HC mixed input, HC injection, qkv and z in distinct allocations.
The same four allocations are bound into each GDN layer's fixed captured sites;
there is no layer-to-layer overlap. At production geometry their logical extent
would be 5,120 + 8 + 20,480 + 12,288 = 37,896 bytes per row. Mini uses its actual
smaller extents. Two separate 4-byte workspace handles satisfy the split1 ABI;
the operation does not write them. Weights, recurrent state and the remaining
operator/FFN/QSA scratch stay shared. Prepared Matrix inputs/outputs and every
ordinary prepared site are rebuilt against the row maps before execution.

The new [paired_projection.hpp](paired_projection.hpp) accepts only mini F32,
K16, rows20/12, variant2, or synthetic Q6_K, K2560, rows10240/6144, variant6 with
expanded_sg32 stride3380. F32 follows the pinned kopt3 variant2 lane order; Q6
follows p33's segment order, also exercised independently by
[P202](../packet202-prefill-chunk-prep/README.md). Both retain independent FP32
addition chains, the original tree32 and the final BF16 store. The weight and
Q6 scale are read once in source for two accumulators; this is not a measured
traffic or speed claim. No old P151 wrapper or pruned include tree is imported.

The production census has 35 Q6 GDN layers and one Q8 layer (layer 2). This
operation does not admit Q8, and the mini layer-2 F32 proof does not qualify the
production layer-2 projection. No production Engine or device path is enabled.

## Admission and ownership

`--p207-host-chunk2` and `--p207-host-observe` retain P206's early HOST_ONLY,
mini, pipeline-mini, resident, single-owner gates before Weights or Engine work.
Alternate draft/priority/record/MTP paths are refused. Serial computation remains
the default. New checkpoint identity is `experimental-host-paired-projections`,
contract `v1.2+p207`; restores are compared within the same new binary only.

The raw dense operation writes both outputs unconditionally, like its original
dense projections. Engine entry checks active/error before pair issue. A failure
in pair issue, suffix or publication poisons the Engine; there is no fallback or
retry. Canonical copies remain ordered and non-atomic. Host operations execute
real CPU arithmetic; Host inherits LifetimeMock/MockDevice, so event/queue
completion is simulated CPU backend evidence, not device scheduling authority.

## Reproduction and evidence

Compile only, using the repository compile-turn lock:

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 experiments/own-xpu-runtime/stage2/packet207-host-paired-projections/build_engine.py --compile-only
```

The recipe applies a source-pinned additive overlay to the frozen P198 generated
entry, preserves P206 recipe lineage in [parent-pins.json](parent-pins.json), and
links the unchanged pinned GNU HOST_ONLY objects. It records compiler dependency
hashes, source snapshots, logs and a binary digest per attempt. Builds remain
ignored. No old source is modified, and no build command executes the binary.

The designated runner uses the separately reviewed host harness for two
16-request serial/candidate owners. The final proof matches all 13 corresponding
checkpoint maps (20 state blobs plus tokens.bin), all 16 generated sequences,
all 108 chunk/single-tail endpoints, all 13 retained P206 checkpoint maps, and
six historical parent checkpoints. Append across position 31→32 is exact. Four
paired sites replace eight originals per successful chunk; 100 chunks yielded
400 paired sites and 800 skipped original projections. Trace
`paired-sites.jsonl` records real captured weight/input/output/workspace/injection
allocation IDs; a logged site is not itself an arithmetic correctness proof.

A separate explicit `--p207-pair-proof FRESH_OUTPUT` invocation exercises the
same pair Matrix admission, Device capture and issue APIs with full synthetic
Q6 qkv/z shapes. It compares every BF16 output against independently called
pinned p33 serial arithmetic. Live input/weight changes must affect the expected
outputs; caller Matrix mutation must not redirect captured bindings. Aliased,
short or wrong-layout bindings must refuse without changing outputs. The result
records both owner teardown receipts. This proof never constructs Weights or an
Engine and cannot access model files.

## Limits and next gate

The mini path still disables production prepared FP32 conversion caching and
expert cache behavior. P206 authority on fatal partial chunks is inherited;
P207's new host arithmetic and actual capture/binding gates passed separately.
Selected SYCL compilation, per-row scratch dependencies on device, production
FP32/cache policy, complete model exactness and throughput remain unqualified.
