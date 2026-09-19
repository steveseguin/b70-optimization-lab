# Packet 79 / server 79b findings (2026-09-19 20:46-20:52 UTC)

Boot 6572bcd2 (kernel -31, GuC 70.44.1), after the 18:04 UTC freeze killed
server 79 at the same point.

1. **Encoder shard installed and is bit-exact.** 24 layers (10.9 GB) on
   xpu:3, 24 (15.3 GB) on xpu:2, two encode workers, per-thread bookkeeping
   held. The four-tensor oracle passed on the two clips that emitted:
   boat (51000 vs baseline-01) and marble (51001 vs speed-oracle-marble).
2. **Placement is clean.** With the tolerant gate, every decoder tensor sits
   on xpu:3 (310 tensors); ComfyUI's loaded-model table: AudioVAE and
   CausalDiffusionVAE on xpu:3, LatentUpsampler and the 21-block LTXAV on
   xpu:0, the 27-block shard on xpu:1, the encoder halves on xpu:2/xpu:3.
   Server 78b's "Decoder state spans devices" was a transient during load.
3. **Preview save failed on the third clip (bird, 51002):**
   `av.error.ArgumentError: Invalid argument: 'avcodec_send_frame()'
   returned 22` from the AAC encoder inside ComfyUI's `save_to`. Two clips
   had saved fine. The pipeline latched (halt on any stage failure), so the
   arm ended after 2 distinct clips. The waveform itself was not retained.
4. Packet 80 guards the preview save: a muxer failure records the
   waveform's shape, dtype, device, NaN/inf counts and range in the decode
   receipt (`save_failures`), dumps the waveform for offline replay, and the
   clip continues; the raw-tensor oracle remains the judge of exactness.

Memory (sampler receipts, reserved GiB): xpu:0 26.6, xpu:1 26.2, xpu:2 20.9,
xpu:3 16.0.
