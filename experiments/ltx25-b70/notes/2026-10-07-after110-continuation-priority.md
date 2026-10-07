# After110: establish a coherent continuation reference

Source-only recommendation while110 is running; no110 success, speed gain or new quality qualification is assumed. If110 fails, bank and resolve that result first. If its ten-fixture49-frame exact gate passes, the highest-value next step is a bounded native continuation reference at the same640×384,49-frame geometry. Do not automatically increase duration/resolution or reopen copy, graph-chaining, QKV, worker or layout sweeps.

The north star includes coherent continuous video, deterministic replay and more than24 unique generated frames/s. Independent clips, even longer exact clips, leave the first two requirements untested. Existing CPU anchor/delivery/coordinator work is useful but inactive, tied to the old256²/25-frame graph, and cannot be relabeled as a qualified current runtime. A three-chunk reference exposes this missing capability directly. It may be slower than independent clips; that is a measured baseline for subsequent optimization, not a speed improvement claim.

## Smallest useful design

Prepare a separately sealed native graph for one disclosed scene, three ordered seeds and three sequential chunks; replay the complete chain once from the same initial seed. Chunk0 remains the ordinary same-shape text-to-video calculation. Chunks1/2 each consume the preceding chunk's last decoded F32 frame, with no preview conversion, clamp or quantization. Use the native image-conditioning node at strength1 before **both** samplers. Preserve BF16,8+3 steps and named20/28 placement. This changes the workload to image-conditioned continuation; it must not replace the independent-clip exact oracle or silently become an adopted quality mode.

Six complete captures would have a conservative raw-file bound of877,383,216 bytes using the existing146,230,536-byte full-file bound, before setup, conditioning state, previews, logs and replay metadata. This is a design estimate, not storage admission or a proposed six-request campaign. Account for every actual setup/capture in the future plan, retain the50GiB reserve and existing memory floors, and prewrite-bound new anchor artifacts. One640×384 RGB F32 frame is2,949,120 bytes. Preserve both complete short chains until exact replay and seam review finish; do not retire predecessors while anything can read them.

Do not initially port continuation into the W2 pipeline. Its internal `_sample_chain` performs upsample→AV concat→second sampler with no external second-stage anchor input. Moreover, the next chunk cannot be sampled until the previous chunk's decoder produces the anchor. Two workers can serve independent scenes, but their present independent-clip overlap does not establish faster generation of one coherent scene. Start with explicit sequential native execution; qualify any later masked graph capture, pipeline ownership or scheduling change against that new reference.

## Specific source changes and acceptance gates

The old graph builder binds a historical graph/source set and25-frame256² shapes; anchor I/O fixes frame24 and786,432 bytes, and the provider reshapes to256². Rebind all of these, the delivery reader and coordinator to a single immutable49-frame current-source contract. For this reference, the anchor is frame48, shape[1,384,640,3]. Bind predecessor full-capture hash, anchor bytes/hash, graph, model/runtime, prompt, seed, stage conditioning strength and replay order. Preserve exclusive ownership, finite/F32/shape validation and fault-halt behavior; reject changed/missing predecessors instead of substituting cached anchors.

The successful109 source confirms that `LTXVImgToVideoInplace.execute` clones the latent, optionally resizes the image, VAE-encodes it, writes a prefix and masks it. Its `nodes_lt.py` hash differs from the older continuation note, so that note's source pins cannot be reused. The unchanged upsampler still removes `noise_mask` at line62. Re-anchor after that upsampler; a stage-A-only patch is insufficient. The reference includes native resize/VAE encoding by definition: unchanged float delivery does not make the anchor's encode/decode reconstruction pixel-exact.

Before a live reference, close CPU graph/source/anchor/capture-budget tests and a fresh memory admission for the additional VAE **encoding** path.109's decoder headroom and110's text-to-video qualification cannot prove conditioning-encode workspace safety. Keep the existing native guard; do not import a captured optimized chain simply because tensor dimensions match. A new plan/runtime contract is necessary; no extension or hot mutation of110's consumed authority.

Then require exact repeat equality of all four complete tensors for all three chunks, exact predecessor linkage, and no faults/nonfinite outputs/memory-floor or retention violations. Separate this deterministic-reference gate from seam/motion/identity quality: one anchored frame may preserve appearance poorly or reset motion. Review the two boundaries in lossless samples and preserve failures. Deterministic flicker is still a failed coherence result. A tiny scene pilot is not broad visual acceptance, endurance or permission to adopt a quality tradeoff; prompt changes and multiple motion classes come only after this reference works.

## Honest timing and audio limits

Count49 frames from chunk0, then48 new frames per subsequent chunk:145 delivered unique frames across the three-chunk chain. A49-frame continuation request does not deliver49 new frames. Record submit→complete decoded chunk latency and anchor-ready→next-chunk-ready separately, with anchor/conditioning work included; no p95 or sustained claim from two boundaries. Report initial buffering and physical playback separately from sink acknowledgements. Do not reuse independent W2 throughput as a single-scene streaming rate.

Keep raw audio unchanged and separate initially. The current49-frame waveform has96,480 samples at48kHz (2.01s);49/24 seconds is98,000 samples, while48 new frames span96,000 samples. Neither difference supplies an authorized trim rule. Do not silently concatenate, crossfade, resample or drop audio to call the result coherent AV. A first video-continuation reference may leave audio alignment explicitly unresolved; resolving the AV timeline is its own quality gate before a continuous-AV claim.

No concrete compute kernel change is justified by the present bounded evidence. The prior sparse trace closed the small transfer/static-fill opportunity and did not identify an exact kernel substitution. Existing completed110 stage/service receipts can later rank sampler versus decoder cost without another broad trace campaign, but compute-heavy spans alone do not identify a safe faster implementation. Build the missing reference first rather than nominate speculative fusion. This advances the continuous-video goal while preserving the established independent-clip performance lane.

## Reviewed input identities

These are source/metadata hashes only; no model or tensor payload was read. Successful109 sealed source is used as the concrete numerical predecessor, not as evidence that110 passed.

- `PLAN.md`: `554e91ddfd731c6994af905ebf741a231ca4ea96089c293dcd7c3b43f02d6e95`
- `notes/continuation-source-boundary.md`: `1b0d87361457c1add16c3e7d8b6aabdef59b28accbbffe7301e58e8e9e6b0fbb`
- `notes/2026-10-07-follow-up-levers.md`: `7d64bc3b0c3916cb6a92a82075daca4d960880b73b081bedf3d15a170ea290ac`
- `notes/2026-10-07-next-useful-workload.md`: `ae07a1890479dc2821eaefba688f369f42c923673a6bb0b89fc2d46565053825`
- `notes/2026-10-07-duration109-resource-audit.md`: `9233a641283f3caff31b26bb130dbd0f84cab8228475085c3e1e81fcfaa8b707`
- `scripts/build-continuation-graph.py`: `22911dcda8ecad5f88b11d04521e777215ee9b96bfd7c3bcb1eb29f2e3dbe33d`
- `scripts/continuation_anchor_io.py`: `91ab1f40655bda9e3f0b39cf8b71784579bdb98a76b8ffcce4e9902388294c21`
- `scripts/continuation_anchor_node.py`: `a0c6282ec2fe92d15cc6c4310b8b59a4a380669e73b83254eb214f8f7e80ad7f`
- `scripts/continuation_stream_state.py`: `d4d2b26755f85b3bce79bbb3144d2ae68714a42027f24cd450741817300f5873`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-pilot-109/source/comfy_extras/nodes_lt.py`: `09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-pilot-109/source/comfy_extras/nodes_lt_upsampler.py`: `c9f225e4c54f19f31452016fd4e546119d69e9dec37b60a9dc4ddf133848a892`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-pilot-109/source/scripts/pipeline_sampler_node.py`: `3dcaa3186c4230fce65536e5a6b3737a3979eced12f33e84576529b06cb03701`
