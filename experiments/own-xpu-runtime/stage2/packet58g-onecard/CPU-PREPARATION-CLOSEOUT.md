# Packet58g CPU repair closeout

<!-- campaign-closeout -->

## Question and identity

October 18, 2026. Why did frozen 58f refuse p28 after loading 48 layers?
One B70, card 0, resident target-only UD-IQ3_XXS, zero-copy misses, 18 GB cache,
4096-position BF16 KV, unchanged `iq3-p49-split32-v1` oracle.

## Outcome

The layer-2 gate/up uses IQ3_S and separate checks. The real one-card loader
stores its 512 pointers in 8,192 bytes; the direct p28 submit expects 512 × 640 ×
1,100 = 360,448,000 packed bytes. The up table has the same latent mismatch.
Alignment and device ownership pass. New explicit table resolution preserves
the same lanes, reduction order and output rounding.

## What worked

The full-size mock reserves nonoverlapping real virtual extents and runs real
initialization, cache publication and command preparation. The old call refuses;
the repaired call validates all 1,486 sites at both context extents. K1 tests the
new actual p28 path against the previous direct p39 oracle and retains its exact
output hash across host/device/mixed/streamed fixtures. Refusal tests exercise
the real window entry and real temporary leases/drain files. Timing command and
native receipt checks pin lane-A cores and nice 0.

## Failures and uncertainty

The old post-load test stopped at cache setup and never called prepare_commands.
Miniature model buffers do not satisfy production native shape contracts: the
full-size submit executable links the native validation mirrors separately;
miniature reset tests keep their original host executable. Neither CPU test
establishes actual device access, full-model exactness or speed. Those remain
coordinator gates. The device build is compiled only, never executed here.

## Retained evidence

[Root cause](evidence/fullshape-root-cause.json), [original parent pins](parent58f-source-manifest.json),
[real arena census](evidence/fullshape-census.json), [old refusal](evidence/fullshape-58f-refusal.txt),
[full-shape result](evidence/fullshape-submit-cpu.json), [K1 bytes](k1-cpu.json),
[Python tests](evidence/python-cpu-gates.json), [build steps](CPU-BUILD.md).
Frozen parents, screen and ops are untouched. Only own temporary fixture scratch is removed.

## Revisit conditions

Run the fresh K1a → K1b → KD → W2m → WS → WS128x → WS128 chain. Any new startup
refusal must be reproduced through these actual full-size CPU paths first.
A valid software refusal releases coordination but never advances the queue.
