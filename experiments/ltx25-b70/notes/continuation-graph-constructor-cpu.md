# Inactive continuation graph constructor — 2026-09-14

Implemented [build-continuation-graph.py](../scripts/build-continuation-graph.py)
and [13 passing CPU structural tests](../data/continuation-graph-cpu-02.json).
The [test log](../data/continuation-graph-cpu-02.log) and receipt bind the exact
builder/test bytes. No Torch/Comfy runtime imports, GPU requests, process scans,
model reads, deployment, or changes to current runtime packets were performed.
This implements the first graph-construction step of the existing
[continuation source boundary](continuation-source-boundary.md) and [plan](../PLAN.md).

The first chunk uses the selected `speed-resident-split-api.json`, SHA256
`fa3868afb3d81056a776d256e68ed5e239cb501bd8b254af7ff2d33339d742d7`.
Its two dual CFG guiders retain video/audio CFG1. The initial
[12-test attempt](../data/continuation-graph-cpu-01.json) used the related
BasicGuider graph; review caught this unrelated baseline change. Attempt02
corrects the base and adds source-AST validation of every declared output
list, including native SaveVideo's VIDEO passthrough. The
[preserved attempt delta](../patches/continuation-graph-cpu-01-to-02.patch)
can be reversed to recover the initial builder/tests; both recovered source
hashes were checked against the initial receipt before saving this patch.
Only explicit prompt/seed and safe output names can change. Native BF16,
128x128 first stage, 256x256 second stage, 25 frames, 24 fps, the 8+3 schedules,
untiled VAE decode and raw tensor capture remain the reference settings.
The custom resident component node remains an integration dependency; this
constructor does not attest any running extension or model identity.

Each subsequent chunk adds precisely these native nodes and rewires the video
input of the corresponding AV concat. The same external IMAGE edge feeds both.

| New node | Native class | `vae` | `image` | `latent` | `strength` | `bypass` |
| --- | --- | --- | --- | --- | --- | --- |
| `continuation_anchor_stage1` | `LTXVImgToVideoInplace` | `[420,2]` | caller-supplied IMAGE edge | `[356,0]` | 1.0 | false |
| `continuation_anchor_stage2` | `LTXVImgToVideoInplace` | `[420,2]` | same IMAGE edge | `[348,0]` | 1.0 | false |

In serialized graphs, node IDs are strings. The exact native input types are
VAE, IMAGE, LATENT, FLOAT and BOOLEAN; output0 is LATENT. The CPU test checks
these names/types and the execute signature by parsing pinned source as AST,
without importing it. It verifies the six pinned Comfy source hashes and every
declared output list from native and local custom-node source AST. The anchor
and upsampler hashes match the earlier source-boundary note. Stage1's native resize/VAE encode uses the
128x128 latent resolution; stage2 reencodes the original 256x256 float anchor
after the upsampler has removed the first-stage mask. This defines a new
continuation workload, not equivalence to unconditioned T2V or a guarantee
that the VAE reproduces the anchor pixels exactly.

The builder writes an **inactive module envelope**, not an API submission.
For subsequent chunks it declares an external output edge whose provider is
explicitly unimplemented. It requires a predecessor-frame hash and declares
one `[1,256,256,3]` float32 RGB frame, predecessor frame24, and SHA256 of
contiguous little-endian float32 sample bytes. Hash/payload verification is
pending: a future float-anchor provider must validate the captured payload,
finiteness, shape, dtype and hash before supplying that edge. Preview/media
decoding, clipping and quantization cannot supply this input. No fake
`LoadFloatAnchor` node is inserted or assumed available.

The structural validator checks every node/input, required and extra fields,
scalar types/enums, all internal edge sources, output indices and edge types,
cycles, provider/node collisions, and precisely two external anchor uses.
Its schemas intentionally cover only this fixed graph and do not replace the
future server's own schema validation. Tests additionally prove the exact
two-node/two-edge continuation delta, unchanged sampler/audio paths, and
exclusive CLI file creation. Test hashes are explicitly synthetic contracts,
not image payloads or inference evidence.

Run construction with the standard library only:

```bash
python3 experiments/ltx25-b70/scripts/build-continuation-graph.py \
  --chunk-index 0 --run-name continuation-first \
  --output /tmp/ltx-continuation-first-module.json

python3 experiments/ltx25-b70/scripts/test-continuation-graph.py
```

For a subsequent module, pass `--chunk-index 1`, a new `--run-name`,
`--anchor-node` and optional `--anchor-output`, plus the real predecessor
`--anchor-sha256`. Python callers can use
`build_chunk(index, run_name, seed, prompt, anchor_edge, anchor_sha256)`.
No command here submits a graph. CLI output creation fails if the destination
already exists, preserving prior evidence.

Delivery accounting is25 frames for chunk0 and24 new frames for each subsequent
chunk, reserving frame0 as its boundary. The graph still captures all25 raw
frames; delivery slicing is explicitly unimplemented. At24fps each subsequent
chunk contributes one second of new video, but no generation time is measured.
Raw audio still flows directly from native decode into capture and preview.
It is not trimmed, resampled, crossfaded, or concatenated; the existing48,480
samples/48kHz versus video-duration mismatch leaves stream timing unresolved.

Remaining work is concrete: implement and bind the float-anchor provider and
delivery state; validate the completed graph against a recovered runtime;
establish a short chain with exact replay; review visual seams and subject
persistence; and define a separately qualified audio timeline. The host fault
continues to block GPU qualification. These CPU tests make no inference
correctness, temporal coherence, lossless export, or speed claim.
