# Native continuation111 plan — CPU preparation only

This fixed plan has eight requests: the accepted window probe and native
preparation, then three native chunks and a complete independent replay.
Each pass uses seeds 42, 43 and 44 at 49 frames, 640×384, unchanged BF16 model
weights and 8+3 sampler steps. Chunk 0 is ordinary native generation. Chunks
1 and 2 condition both stages on frame 48 of their own pass's verified predecessor.
The two chains retain all six full captures; neither audio assembly nor seam
quality is qualified by this plan. A chain has 147 raw frames and 145 unique
video-frame positions after accounting for the two shared boundary frames.

All eight rows are in `plan.requests`, in execution order. Setup rows have
`phase=native-setup`; native rows use `native-reference` or `native-repeat`.
All rows use the existing `native_reference` authority phase. Every request
requires the immediately previous request's durable proof. The first conditioned
chunk establishes an additional barrier before any later conditioned chunk.
There are no optimized phases, retries, concurrent submissions or hidden fills.

The numerical contract determines the qualification ID before graphs are built.
The plan SHA covers the complete plan after graph construction. Provider
bindings must explicitly use that actual plan SHA and the future sealed111
runtime identity, never the inactive prototype's design SHA or source110's
runtime identity. Graphs stay immutable: `LTXContinuationAnchor111` takes only
`run_name`; trusted active-request authority resolves verified predecessor
metadata and bytes. Neither future node class is registered by this module.

Future `LTXContinuationCondition111` must reject a graph IMAGE that is not the
guard-owned anchor object and invoke
`guard.run_stage(stage, request_id=run_name, vae=vae, latent=latent,
native_call=exact_native_execute)`, with uppercase `A` then `B`. Trusted runtime
integration must call `begin_request` and `finish_request` around each of the
four conditioned rows; chunk 0 makes no conditioning-stage calls. The guard's
inspection callbacks and exact native method identities still require binding
to the actual sealed runtime sources. The guard supplies the bound image and
unchanged strength 1.0 / bypass False arguments; the wrapper must preserve the
original native result. Required runtime checks preserve default F32, CPU
intermediate latents and BF16 VAE weights / F32 output. Fresh physical free
memory floors are 8/8/2/9 GiB before each conditioning stage and 2 GiB after.
The accepted graph-sharded text encoder stays in place; no alternate/tiled VAE
fallback, optimized sampler capture routes or decoder replicas are admitted.

The capture contract permits exactly six full files at 146,230,536 bytes each,
877,383,216 bytes total. The 4 GiB runtime allowance is **provisional** pending
exact cache and other-output bounds plus fresh storage admission. The plan
preserves a 50 GiB reserve and budgets 384 MiB for a future source build. It does
not admit encoder workspace, build a runtime, submit requests or establish
quality, performance, A/V, adoption or endurance claims.

`plan.py` checks the pinned inactive prototype and sealed110 source basis.
`validate()` reconstructs the exact plan, including source pins, rather than
accepting a rehashed mutation. `candidate-plan.json` is its generated envelope.
`python plan.py --output NEW_PATH` writes exclusively and fsyncs the file and
parent directory. It will not replace an existing artifact.

Validation: `PYTHONDONTWRITEBYTECODE=1 python -m unittest test_plan` — 12 CPU
tests passed in 0.520 seconds. Tests cover source and graph identity,
both conditioning stages, own-pass predecessor/replay linkage, barriers,
storage bounds, rehashed drift, and absence of fabricated validated anchors.
No Torch, real tensor captures, model loads or runtime endpoints are used.
