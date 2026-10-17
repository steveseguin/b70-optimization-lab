# Packet58d post-load lifetime repair — CPU closeout

<!-- campaign-closeout -->

## Question and identity

Why did packet58c KD fail after loading all 48 layers? October 17, 2026,
one-card Flash-Next UD-IQ3_XXS, card 0, context 4096, BF16 KV, plain decode,
zero-copy misses and 18 GB LRU cache. Arithmetic stays `iq3-p49-split32-v1`.
This packet is copied from frozen 58c; preparation is CPU only.

## Outcome

Two pinned-slab requests used process lifetime where the owner requires
transfer lifetime. `cache-table-staging` caused the observed exception;
`cache-route-readback` would fail next. Both now request transfer lifetime;
the plan and enforcement are unchanged. Errors now include label, category,
requested lifetime and planned lifetime.

The real post-load method passes on a CPU mock with 144 bank handles, three
allocations and 144 publications. Both original invalid requests still fail.
Both host and device builds pass; no device binary ran. All 59 Python tests,
K1's 24 CPU checks and request-reset checks pass. K1 keeps
the parent's exact output hash; resets compare tokens and 40 retained files.

## What worked

Tracing initialization exposed both mismatches without a device retry. The
test calls the actual `Engine::initialize_cache`. Logical allocations retain
production sizes, while the mock uses 2,457,406 backing bytes and opens no
model payloads. Seal creation and queue planning require this source-bound
gate. [Allocation audit](ALLOCATION-AUDIT.md) records the entire sequence.

## What failed or remains uncertain

58c never passed KD; small fixtures missed this full post-load setup path.
Device fit, full-model correctness and speed remain pending. The memory fence,
admission, GPUActive accounting, BF16 KV and arithmetic stay unchanged. All
existing latches remain in place. No GPU or service ran during preparation.

## Evidence and patches

- [Failure copies and pins](evidence/58c-kd/source-manifest.json),
  [cause summary](evidence/root-cause.json).
- [Native delta](evidence/native-delta.patch),
  [164-file comparison](evidence/native-identity.json).
- [Post-load gate](evidence/postload-allocation-cpu.json),
  [census](evidence/postload-census.json), [teardown](evidence/postload-teardown.json).
- [Python gates](evidence/python-cpu-gates.json), [K1 CPU](k1-cpu.json),
  [request resets](request-reset-cpu.json), [build commands](CPU-BUILD.md).
- [Frozen parent hashes](parent58c-source-manifest.json),
  [retention and restore](ARTIFACT-RETENTION.md).

## When to revisit

The coordinator reviews the retained lineage stops, then runs
K1a → K1b → KD → W2m → WS → WS128x → WS128 on card 0 with fresh output
`evidence/card0-58d-a`. Existing rules forbid cross-seal K1 reuse. See
[WINDOW.md](WINDOW.md). A further setup failure should extend the real-method
CPU gate in a new packet before another device attempt.
