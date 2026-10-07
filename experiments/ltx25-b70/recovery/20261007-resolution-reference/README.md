# Same-size native reference candidate (CPU plan only)

Status: **not runtime-ready, not GPU-qualified, no model requests**. Parent
source is qualified packet99b, manifest
`f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
All work is confined to this folder. Existing source, sealed packets, speed-only
admission and oracle guards remain unchanged. See the
[design note](../../notes/2026-10-07-resolution-reference-design.md).

`plan_reference.py` reads only the small pinned manifest, three graph JSONs and
the accepted fixture JSON. It imports no Torch/Comfy, loads no model, contacts no
endpoint, and builds no runtime. `plan` emits a deterministic JSON plan to
stdout. `validate` checks both its hash and exact reconstruction from the pinned
inputs, so editing a plan and supplying its own replacement hash cannot qualify
it. Duplicate JSON keys, nonfinite JSON and symlinked input paths refuse.

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-reference/plan_reference.py plan
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-reference/plan_reference.py validate \
  --plan-file /home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261007-resolution-reference/candidate-plan.json
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-reference/test_plan_reference.py
```

`candidate-plan.json` is the reviewed graph/sequence proposal; it is deliberately
not an executable runtime or a live campaign. `cpu-validation.json` binds the
planner, controls and generated plan. No captured tensors or GPU results exist
for this candidate. Twelve offline controls pass, including execution of the
actual pinned `run_ahead` function body with CPU job stubs.

## Pinned workload and comparison

The first three original fixtures (boat seed42, marble17, bird123) are selected
by their existing order, with their exact text and accepted window64, not by
results of a new size test. Same native BF16 model, original8+3 sigmas, B1,
23/25 two-card transformer,25 frames,24 playback FPS. Stage1 is320×192 and
native upsampling produces640×384. The accepted graph-sharded/window encoder
is preserved; the native reference is **not entirely eager end to end**.

The native reference graph derives from `host-embedding-control.json`:
`SamplerCustomAdvanced`344/368, native upsampler348, video decode374 and audio
decode358 stay unchanged. It omits transformer graph gates, lean sampler,
decode replicas and save-behind. Its encoding branch is taken from the pinned
accepted optimized graph, with365 wired directly to364;421 is removed because
its single-encode accounting is incompatible with that branch. Native capture414
retains all four tensors. Optional lossy preview nodes75/370 are omitted from
reference creation; raw images remain available for a later reviewed rendering.

Six serial requests establish three native references and three independent
repeats. Every request has its own name/index/graph hash. The optimized graph
is the pinned99b W1/shared-pool/replica-xpu2 path at the new size. It requires
six submissions to emit the three candidate-check clips, then a separate
13-submission phase to emit ten timed clips cycling the same three fixtures.
Three fills in each phase are explicit. Candidate references are mapped by the
**emitted** fixture rather than the current request's fixture. Sixteen exact
comparisons are planned:3repeat +3candidate-check +10timed, all over images,
video latent,audio latent,waveform. Timed labels do not imply it is safe to run.

The proposed clip range99900000–99900212 is below the inherited100000000
ceiling, with unique names and disjoint phases. **Coordinator collision checking
and reservation remain pending**; this is not proof that another historical or
planned arm has not used that range. Native repeat equality must bind separate
successful request IDs and timestamps, same source/model/runtime, no cached
node outputs and exact shapes/dtypes/bytes. Reference outputs cannot come from
the optimized candidate. Existing256×256 w93c references remain separate.

## Minimum runtime/source changes for parent review

These are required work, not changes implemented by this folder:

1. **Geometry admission and truthful labels.** Add a narrowly identified
   `comparison_mode="same-size-native-v1"` and `qualification_id` to a new
   geometry helper and affected text/sampler/decode node interfaces. The ID
   hashes the pinned source-graph/fixture/shape/configuration basis in this
   plan. It identifies the declared workload; it does not attest success or
   replace a completed reference receipt. Require the matching sealed plan,
   fixed640×384 B1/23–25 configuration and phase authorization before execution.
   Keep old `speed_only` and reference guards intact for every other mode.
   Existing nodes deliberately reject the proposed new fields today.
2. **Reference lifecycle before sampler capture.** Same-server window probe
   first, then six serial native executions. Native text keeps encoderdepth2:
   actual `ltx_pipeline.run_ahead` submits and collects the same current index
   and text tag, then considers future queue-known work. It does not return
   the prior clip; depth0 is rejected by the existing function. With serial
   submissions and an empty prompt queue, require `started_ahead=[]`, no pending
   encode jobs and `speculation_miss=false`, alongside matching clip index,
   text/seed and conditioning receipts. Twelve CPU controls include execution
   of that actual function body and depth0 refusal. Verify three repeat comparisons
   before installing sampler graph routes. Require actual absence of optimized
   sampler/lean/decode state in reference phase, rather than relying only on
   graph node names. Do not switch an already-frozen optimized server back to
   native reference mode. Reference and candidate both keep qualified99b RoPE.
3. **Complete source closure.** Seal both canonical/custom-node copies of any
   changed module, update manifest/extension/startup pins and graph contracts,
   and record the explicit transition from99b. Keep dependency and Torch pins.
   Current99b launch admits only256×256; a separate reviewed launch contract
   must admit the new geometry, same-size decode probes and scaled chain checks.
4. **CPU reference gate and live client.** Hash and re-read each capture, verify
   request/submission/history identity, unique noncached executions, bound
   graph/fixture/seed/window and all four finite tensors. Compare native repeats
   before freezing an exclusive new reference receipt; refuse overwrite or
   candidate-as-reference. Add explicit candidate-reference mapping to a new
   throughput client instead of weakening old `--no-oracle` assertions. Only
   passed same-size references enable candidate checks and then timing.
5. **Phase transitions and safety.** Existing pipelines can retain in-flight
   tail jobs after the final emitted output. Define and test complete
   sample/decode/save quiescence and fresh-phase index/queue behavior before
   the next phase; a list of request graphs alone does not provide this.
   Retain fault halt, single owned server, no automatic retry/restart, graceful
   stop, actual memory floors, disk admission and postflight. Runtime faults
   stop further requests, including after failed reference comparison.

The qualification ID is fixed by the plan's basis and included in graph hashes;
it is not the envelope `plan_sha256` (which also covers those graphs), avoiding
a circular hash. A sealed runtime must bind the whole envelope and its own
identity separately; accepting an arbitrary client-supplied ID is insufficient.

## Unknown budgets and claim boundaries

Native eager transformer transients at240/960 tokens, encoder-graph coexistence,
subsequent sampler capture, shared pools, native and replica VAE room remain
unmeasured on this workload. Storage admission must cover raw captures plus
setup/capture outputs, pending-tail outputs, previews and compilation caches.
The19 planned retained emitted/reference captures alone contain about1.320GiB
of four-tensor F32 payload; this is **not** a total disk allowance or an enforced bound.
The proposed total cap is32 captures (2.224GiB four-tensor payload), including
setup and pending tails, inside a4GiB total admitted write allowance; the
remaining space must cover headers/previews/logs/cache and cannot be assumed
sufficient without accounting. These caps are not enforced by this CPU plan.
Keep the50GiB disk reserve and2GiB device floor, and obtain current host/device
admission from the independent memory review. The provisional pre-native
physical-free thresholds are6GiB each on sampler cards0/1,2GiB on encodercard2
and7GiB on nativeVAEcard3, after required weights/encoder graphs/VAEs are
resident, with no sampler routes/replica and no owner eviction. These include
unmeasured transient allowances, not a proven full48-block bound. Historical packet98 estimates
are not current admission.

A pass would cover the three fixtures on the pinned same-size native-sampling
workload. It would not establish equality with256×256 pixels, general image
quality, all ten historical fixtures, sustained reliability or coherent longer
video. Ten emitted clips are a preliminary timing sample; report generated
frames/s separately from playback FPS and request latency. Visual review of
selected full-resolution samples remains distinct from exactness.
