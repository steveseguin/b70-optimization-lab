# Independent CPU integration review

Reviewed the root-owned integration against the actual phase authority, native
adapter, setup schedule, output gates, request client and immutable99b source
APIs. No ComfyUI/Torch/model/device imports, endpoint requests, runtime build or
materialization were performed. Runtime/device APIs in controls are explicit CPU
stubs; the actual authority, graph schedule, setup validators, reference-state
validator, executor guard and client phase parser are exercised.

## Result

All16 focused controls pass:

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_integration.py
```

The latest run completed in0.374seconds. This review finds no remaining blocker
within the tested integration scope. It does not establish live startup,
allocator headroom, XPU graph behavior, tensor parity or throughput.

## Findings resolved by the source owner

1. Actual sample completion markers have identity under `session_observation`,
   not a top-level server SHA. Capture retirement now checks that binding, the
   real stage/index, reference receipt and finite completion. A CPU control uses
   this actual marker schema.
2. Dependency checking copied the planned list before appending boundary
   dependencies, avoiding accidental mutation of the registered schedule.
3. The preview writer owns a separate queue. Pipeline-idle alone was insufficient
   for a barrier. Runtime observation now includes pending previews/failures;
   authority quiescence refuses them before tail retirement or phase advance.
4. The status observation now includes reference and candidate receipt hashes,
   satisfying the actual client's optimized/timing admission schema. The control
   exercises the route's atomic file replacement and actual client parser in all
   three executing phases.
5. Memory admission now requires pin completion before sampler capture, and
   coverage plus capture-tail retirement before the decoder probe. An early
   admission cannot precede those allocations and later be reused. The negative
   control uses a poison CPU device stub to prove refusal precedes device calls.

## Covered boundaries

- Exactly32 pinned main/setup requests registered, initially native phase only.
- Native before-observation requires no active request or queued/running work;
  its timestamp and queue fields satisfy the native reference gate's schema.
- Actual executor wrapper brackets native requests with adapter before/after
  calls; failed postchecks preserve failed history, call cleanup and latch halt.
- A negative freeze UI verdict cannot become accepted merely because a Comfy
  prompt succeeded. Candidate/timing request admission checks actual frozen state.
- Native preparation receives the complete source map plus the unchanged
  baseline runtime-files dictionary in its actual expected API shape.
- Unfinished jobs and pending previews cannot be retired as completed tails.
- Native verification cannot start without all six executions; optimized phase
  cannot start without the verified native action.
- Four-card memory readings and unchanged owner fingerprints are required by
  optimized admission; the receipt explicitly disclaims proven peak bounds.
- HTTP action exceptions leave the action-busy flag cleared while retaining the
  permanent failure receipt. Status snapshots bind phase, plan and runtime.
- The4GiB write allowance and50GiB reserve refuse an insufficient filesystem.

The exact native/candidate proof reconstruction and complete byte comparisons
are covered by their separate gate controls. These integration controls do not
fabricate successful reference tensors. Actual setup/runtime results remain
required before any qualification or performance claim.

## Reviewed hashes

These bind the files read at review close; subsequent edits require targeted
review of their effect, not reinterpretation of this historical receipt.

| File | SHA256 |
| --- | --- |
| integration.py | `2c870c803c547949c4ca6af62dd7f0188fb7fe3246e515ebafd4988e2db56c71` |
| session.py | `48f51eedd8d45e6809fbd2794161ab7cb3f7bcac0a8efc16cd06136ffddd49c4` |
| executor_guard.py | `1a2ec2ec7a08321c0cacd9625952658df04e07b861a0091a98ebc688c3fb947d` |
| runtime_observer.py | `475ede8de04d5cd45fc3bc0e550d6c7f4d9d00da1bd129095d6736c8fd6ff0b8` |
| native_adapter.py | `ffc4c74f5ff4e956e223073a2199fa22e2ac1bbdc67bef13d6dc7cc65ad5c8a2` |
| native_safety.py | `e5e5eb42d520d20651a7e57bbb4588a566c72f598d316a371424c3b89f6552f5` |
| setup_gates.py | `35e076721822439ad2528ecd5610b1ab3b758fe35e68ff5660e42d848f865465` |
| schedule.py | `5b0e6c52aef229cd458129ee5a3c74c7535efe789fa550b1ac859c9853de34ca` |
| reference_gate.py | `804ecee7f3a31511efbc45b8a5b86e927601f3089846c314293b835fcb0fed4a` |
| candidate_gate.py | `2f797eb0a55092ba7ecfce16e858ef3131612ad22108ffe114f43650479c182c` |
| request_client.py | `777619fec8ba72aaba5955f42c5a35068402e0e2b7bb01b7da16308514b2d4c0` |
| test_integration.py | `249a90ddd0c10186a59bf5d5ce21fe6100538adfc6052ddb187056fbf84fc1ef` |
