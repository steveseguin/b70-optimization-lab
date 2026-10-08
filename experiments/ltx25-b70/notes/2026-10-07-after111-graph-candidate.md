# Conditional next candidate after native continuation111

Source-only recommendation, written while111 is in window setup. **111 has not
passed.** No optimized runtime is authorized by this note. If native conditioning
or exact replay fails, bank and resolve that result before this candidate.

The smallest worthwhile optimization is existing per-block graph replay on the
same serial prompt-thread chain, with lean memoization initially disabled.
Preserve both explicit native image-conditioning nodes. Stage B remains after
upsampling and before AV concatenation and the second sampler. Moving the chain
into `pipeline_sampler_node._sample_chain` would lose that hook unless changed;
its independent-worker run-behind scheduling offers no demonstrated advantage to
one scene whose next anchor depends on the previous decoded chunk.

Use `graph_capture_node.LTXGraphCaptureGate` with all48 blocks and `chain=1`,
preserving named20/28 placement, BF16,8+3 steps, native decoder and serial chunk
ordering. This targets repeated eager transformer work without changing native
I2V arithmetic or assembling a new sampler. The native conditioning, mask
construction, noise preparation and sampler remain outside the per-block graph.
Whether their resulting block inputs replay exactly is a qualification question,
not established by the independent-clip result.

## Mask-sensitive capture identity

`model_base.LTXAV.process_timestep` applies video/audio denoise masks to timesteps
and patchifies the result. `ltx_graph_capture.Group.key_for` describes video/audio
activation inputs, all admitted keyword inputs, numerical transformer options and
pinned infrastructure. Its keyword set includes video/audio timesteps, attention
masks and positional/timestep conditioning. `describe`, `walk` and `mirror`
handle nested tensor-bearing objects, including compressed timestep/mask objects;
`slot_for` creates owned static destinations and fills their current tensor data.

Signatures bind input structure, tensor layout/type/device and scalar values;
they do not hash every tensor's current numerical contents into a new graph key.
Those contents must instead be copied into the correct static input buffers for
each forward. Noise seeds are upstream sampler inputs, not a separately signed
per-block noise channel: their effects arrive through the actual video/audio
activations. Preserve request seed/latent/mask provenance and whole-output checks.
Neither identical output geometry nor existing unmasked captures proves masked
compatibility. Qualify ordinary and anchored A/B paths explicitly; do not assume
the previous two-signature census. Retain the current eight-signature hard ceiling
and reject new signatures after freeze. Coverage binds actual thread/card owners
and every route. Existing block replay/eager equality and non-inert-input checks
remain required; no chaining or layout sweep is proposed.

## Admission and result gates

111 native safety, integration and proofs intentionally require zero sampler
routes. Do not weaken those checks or relabel graph execution as native. A
successor needs a separate candidate safety contract accepting only the exact
pinned48-route inventory on the intended thread and20/28 owners. Keep full
residency, native conditioning A/B source and ownership checks,8/8/2/9 GiB
preconditioning allowances,2 GiB post floors and persistent fault latches.
Additional graph/static allocations must fit without evicting models or lowering
floors. Capture admission is separate from successful native encoding admission.

Compare all four complete tensors for every candidate chunk to its corresponding
native reference, consuming each candidate chain's own verified predecessor
anchor. Replay the candidate chain exactly. Preserve both conditioning nodes and
mask metadata through stage B; reject any missing hook, mismatched owner/signature,
nonfinite tensor, byte mismatch, resource refusal or fault. Timing includes
conditioning, native decoding and anchor handoff. Three chunks deliver145 unique
frames (49+48+48); report initial buffering and boundary latency, not independent
W2 throughput. No endurance, semantic continuity, resolved audio alignment or
public speed claim follows from this bounded comparison.

Lean's clip-scoped connector memo is a later separable option. Its
`begin_clip`/`set_stage`/`end_clip` lifetime must span the explicit native nodes;
combining that change with first masked graph qualification would complicate
attribution. This note recommends one lever only.

## Reviewed source identity

All paths below are relative to the immutable packet
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-native-111`.
The two contextual notes read were `notes/continuation-source-boundary.md` and
`notes/2026-10-07-after110-continuation-priority.md`; their old shape/source claims
are historical, not current admission.

| Path | SHA256 |
| --- | --- |
| manifest.json | 65adf13fca14f92047960ed939c507cd7e28a08b41940decd089189c86c41363 |
| source/scripts/ltx_graph_capture.py | fc691e4ff4fdbeba0724a8946dbb58dbf3b4cbd9ccdaf325c307f2d86981d7e5 |
| source/scripts/graph_capture_node.py | 775456c2d20b692dbe17d37819fb0364fdedf44681eae5b54b39ffc692a677c3 |
| source/scripts/ltx_lean_conditioning.py | 6740d6665c7dea622fc859287cf075bc01a5e521a7154e6138afaf6afbad7d99 |
| source/scripts/pipeline_sampler_node.py | 3dcaa3186c4230fce65536e5a6b3737a3979eced12f33e84576529b06cb03701 |
| source/comfy/model_base.py | a1a1a7bb89a199710f996bf0bdf549d3e42484fe4dd91aa0a6361bb30c990508 |

No runtime/code changes, tests, GPU calls, process actions or commits accompanied
this source review. Root retains all operational ownership.
