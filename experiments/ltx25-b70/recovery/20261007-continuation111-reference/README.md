#111 native continuation reference prototype

Inactive CPU-only source and anchor prototype. It does not extend110's authority,
register a Comfy node, construct a complete111 plan/runtime, admit storage or
memory, submit requests, or load a model. Historical continuation code and live
runtime sources remain unchanged.

## Source and workload

The exact source basis is `prepared-duration-full-110`, manifest
`bfa78fcf6af59acc3d63318ca97c61846b3a9b80999f6f17cb4c4d3651f2ad09`.
The current native boat graph is
`6bf2475c5b30461006993c4a2483503fc8e18474c2474ded8071112436e995bc`.
`graph.basis()` verifies the manifest, candidate plan, graph, and ten relevant
source files without importing application code. The native image-conditioning
signature and the upsampler's mask removal are additionally checked in source.

One disclosed boat scene uses seeds42/43/44 for three sequential chunks. A full
second pass uses the same seeds and scene but distinct capture names and IDs.
Chunk0 is the ordinary110 native graph with labels/authority fields rebound.
Chunks1/2 use the previous chunk's last decoded F32 image at frame48:

- StageA: image conditioning at strength1, bypassFalse, between empty video
  latent356 and AV concat377, before the8-step sampler344.
- StageB: the same image conditioning between upsampler348 and AV concat340,
  before the3-step sampler368. The native upsampler removes `noise_mask`.

Every other model/sampler/audio/upsampling/decoding input remains the exact native
basis. The accepted graph-sharded window encoder remains. Image conditioning
uses native resize/VAE encoding by definition; unchanged F32 anchor delivery
does **not** imply pixel-exact encode/decode reconstruction or seam continuity.

The source constructor returns an envelope, not a prompt body. Subsequent
envelopes have an unresolved external IMAGE edge. `ready_for_submission`,
`provider_registered`, and `runtime_admitted` remainFalse. A supplied target
runtime hash records a future external binding, not proof that such a runtime
exists or is authorized. `prototype_plan_sha256` identifies this design only;
it is not an executable campaign plan.

## Anchor binding and lifetime

`anchor.extract_anchor(path, expected_capture_sha256)` streams a predecessor
capture through SHA256 in at most1MiB blocks while retaining only frame48. It
checks the exact four F32 tensor shapes, contiguous nonoverlapping safetensors
ranges, a bounded padded header and file length, regular nonlinked/nonsymlink
ownership, and stable file identity. The anchor is exactly2,949,120 bytes,
shape`[1,384,640,3]`, little-endianF32. Finiteness uses integer exponent bits;
no conversion, clamp, normalization, media decoding or quantization occurs.
Other tensor finiteness and complete output parity are separate gates.

`bind_predecessor` binds the expected capture hash and anchor hash to runtime,
model-verification receipt, design plan, predecessor graph, prompt, seed, pass,
chunk and capture name. **Those expected identities must come from a trusted
future execution authority.** This helper cannot establish their provenance
from a caller's assertion or a filename alone. The graph constructor checks
the binding against the exact preceding module, including replay order.

`load_bytes(binding, expected_context)` reopens and revalidates the entire
predecessor every time. There is no cached fallback. Missing, replaced or changed
files are refused, including byte-identical files with a changed inode/identity.
`load_image(..., torch_module)` is an explicit future provider seam: it uses
CPU`frombuffer(float32)`, reshape and clone. The clone owns storage independently
of the file and temporary buffer; no Torch import or device operation occurs
at module import. No provider registration or fault/phase authority is supplied.

No anchor artifact writer is implemented. A future writer must reserve its
2,949,120-byte payload plus metadata before exclusive creation. The future
coordinator must retain both complete predecessor chains until all readers,
exact replay and seam review finish; path checks are not a lifetime lock.

## What remains before execution

New111 runtime/plan identity, provider registration and active-request binding,
fault/phase guards, additional VAE **encoding** memory admission, complete setup
accounting and source/storage admission are mandatory. Keep existing memory
floors and the50GiB reserve. Do not import the W2 optimized sampler chain: it
has no external second-stage anchor input, and one scene has a sequential
decode-to-anchor dependency.

Three chunks represent49+48+48=145 new video frames per chain; the replay is
repeat evidence, not another145 distinct frames. Output overlap slicing is not
implemented here. Six full captures alone are bounded by877,383,216 bytes;
that excludes anchors, setup, logs, previews and conditioning state, so it is
not storage admission or a six-request campaign.

Raw audio remains unchanged and separate. Its96,480 samples do not establish
an AV concatenation/trim rule. No audio edits or continuous-AV claim are made.
Exact replay of all four tensors for every chunk and lossless seam/motion/identity
review are both required; deterministic output can still have unacceptable seams.

## CPU controls

```bash
cd experiments/ltx25-b70/recovery/20261007-continuation111-reference
PYTHONDONTWRITEBYTECODE=1 python -m unittest test_anchor test_graph
```

16 tests passed in2.018s. The private parser seam uses tiny synthetic archives
with49 distinct one-pixel frames, signed zeros and a subnormal in frame48; public geometry remains fixed640×384 and explicitly
rejects those fixtures. Header-only tests reject historical25-frame geometry.
A five-byte read-block test places images after other tensor data and checks exact frame48 extraction across read boundaries. The tensor ownership test uses a fake CPU backend and asserts cloned shape/dtype and independent storage. No146MB fixture, real capture,
model payload, Torch/GPU import, endpoint, source packet build or live process
operation was used. Native runtime execution and visual coherence remain untested.
