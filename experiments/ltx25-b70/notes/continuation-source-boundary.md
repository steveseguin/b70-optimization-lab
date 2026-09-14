# Continuation boundary in the frozen two-stage graph

Status: source audit only; no continuation graph has been qualified or run.
The independent text-to-video baseline and its timing target remain unchanged.
This audit supports stage 3 of the [plan](../PLAN.md) while speed work proceeds.

## Finding that changes the implementation

`LTXVImgToVideoInplace` clones a video latent, encodes the supplied image at the
latent's spatial resolution, writes the encoded prefix and sets its noise mask
to `1 - strength`. At strength 1, the prefix is masked from denoising. Native
AV concat/separate nodes carry this video mask through the joint latent.

However, `LTXVLatentUpsampler.execute` explicitly removes `noise_mask` from its
return value. Adding an anchor only before the first sampler would therefore
leave the second sampler without that protection. Any two-stage continuation
reference must explicitly define its second-stage anchoring. Simply connecting
the existing upsampler does not preserve the first-stage mask.

One candidate reference is to condition on the previous clip's last full-float
decoded frame before both samplers, using the native image-conditioning node at
each stage's existing resolution. This must be evaluated as a new continuation
workload: VAE encoding and decoding do not guarantee that the displayed anchor
pixels exactly reproduce their input, nor that one frame preserves motion or
subject identity over a long sequence. Stronger multi-frame guidance may be
needed after reviewing the first bounded reference. No seam-quality result is
claimed from these source paths.

## Reference requirements before implementation

- Transfer the anchor directly as its captured float tensor. Do not round-trip
  through an 8-bit preview, JPEG, or MP4. A 256x256 RGB float32 frame is 786,432
  bytes, so the initial one-frame state can remain bounded without retaining
  every clip on disk. Model-native resize/VAE conditioning is part of the new
  reference, not a lossless media transformation.
- Retain the current BF16 model, 8+3 sampling schedule, 256x256 final output,
  25 generated frames and 24 fps. Record the two explicit conditioning nodes
  and their strength as workload changes, not baseline-exact speed gains.
- For a one-frame boundary, treat only frames 1 through 24 of each subsequent
  25-frame result as newly delivered video. Frame 0 is a boundary anchor and
  cannot count toward generated throughput. This gives 24 new frames per
  continuation request; under one second per request remains the target.
- Bind each chunk to its predecessor's anchor hash, ordered prompt and seed
  schedule, source/model identity and continuation policy. Establish an exact
  replay of a short chain before making any speed or coherence claim. Include
  prompt changes in a later reference rather than assuming unchanged-prompt
  behavior extends to them.
- Retain at most the current continuation state and bounded playback/review
  buffers. Prune completed verified outputs under the existing policy. On
  failure, stop new requests and preserve the failed boundary and its inputs.
- Define audio timing separately before calling the stream coherent. Existing
  [captures](../data/speed-resident/resident-split-03/capture-summary.json) have
  48,480 waveform samples at 48 kHz, while 25 video frames at
  24 fps span 1.0417 seconds. Blind concatenation or an assumed one-frame audio
  trim does not establish alignment. Preserve raw audio exactly for comparison;
  any resampling, crossfade or timing policy would need its own reference and
  cannot be presented as unchanged sample output.

First acceptance is a short chain reviewed for seams, scene persistence and
audio alignment, with exact replay of all generated outputs. That is separate
from the original three-fixture oracle and does not replace the under-one-second
full-clip performance gate. Deployment waits for its own reviewed graph and
runtime identity; this note changes no pending encoder packet or loaded server.

## Source identity

Frozen ComfyUI commit: `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`.

| Source | SHA256 |
| --- | --- |
| `comfy_extras/nodes_lt.py` | `01575b886e9abacd08c7ce39e7bde9ef7c7cc8f17063d726e2bf4a320a512d95` |
| `comfy_extras/nodes_lt_upsampler.py` | `c9f225e4c54f19f31452016fd4e546119d69e9dec37b60a9dc4ddf133848a892` |

Reviewed functions are `LTXVImgToVideoInplace.execute`,
`LTXVConcatAVLatent.execute`, `LTXVSeparateAVLatent.execute` and
`LTXVLatentUpsampler.execute`. The original
[selected graph](../data/speed-resident-split-api.json) supplies the current
sampler/upsampler ordering. No tensor payload was loaded for this audit.
