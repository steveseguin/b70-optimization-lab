# Three-stage pipeline: 4.49 -> 2.46 seconds of compute per second of video

*2026-09-16, packet48, `pipe` arm. Eight-clip throughput plus four oracle-gated
clips, all four raw outputs bytewise equal on every one.*

## Result

| | interval | per second of video | effective fps |
| --- | ---: | ---: | ---: |
| `graph-text` (serial) | 4.678 s | **4.49 s** | 5.3 |
| `pipe` (encode-ahead + decode-behind) | **2.563 s** | **2.46 s** | **9.8** |

**1.83x**, with no caching. Per clip in steady state, with the oracle running:

| clip_index | clip | text encode | sampler | decode node | exact |
| ---: | ---: | ---: | ---: | ---: | --- |
| 300 (fill) | 5.441 s | 1.707 s | 2.213 s | 1.164 s | yes |
| 301 | 2.434 s | **0.007 s** | 1.922 s | **0.002 s** | yes |
| 302 | 2.513 s | **0.002 s** | 2.023 s | **0.001 s** | yes |
| 303 | 2.455 s | **0.003 s** | 2.013 s | **0.010 s** | yes |

Both the encode and the decode have left the critical path. The sampler is now
essentially the whole clip.

## The two directions, and why neither is a cache

The stages sit on different cards -- encode on xpu:2, sampler on xpu:0 and
xpu:1, decode on xpu:3 -- and cross-device concurrency here measures ~100%
efficient.

- **Encode-ahead.** The encode does not depend on this clip's sampler output, so
  clip N+1's encode starts the moment clip N's conditioning is handed over and
  runs while clip N samples. Each clip's receipt records the wall time of *its
  own* encode: 1.63-1.73 s, even on the prompts where the node returned in
  0.002 s.
- **Decode-behind.** The decode *does* depend on this clip's sampler output, so
  it cannot run early; it runs late. Clip N's decode starts here and the prompt
  emits the clip decoded a prompt earlier. Receipts record `stage_seconds` of
  1.07-1.44 s per clip and an `emitted_index` that lags `clip_index` by exactly
  one:

| prompt | clip_index | emitted_index | its own decode took |
| ---: | ---: | ---: | ---: |
| 0 | 0 | 0 (fill) | 1.138 s |
| 1 | 1 | 0 | 1.138 s |
| 2 | 2 | 1 | 1.180 s |
| 5 | 5 | 4 | 1.441 s |

Every clip is computed by its own encode, sampled from scratch, and decoded by
its own decode. Nothing is stored between clips and no value is served twice.
The one exception is the **pipeline fill**: the first prompt has nothing decoded
a prompt ago, so it waits for its own clip and emits it without consuming it,
and the next prompt emits that same clip. That is one duplicated emission at
start-up, recorded in every receipt as `emitted_index`, and excluded from the
steady-state interval.

Video and audio are decoded and emitted together with their latents, so a
prompt's four oracle inputs always describe the same clip.

## Retired along the way

The **axis-cache decoder** is retired: it memoises mask tensors, and under the
no-caching rule it is not defended. The `pipe` arm decodes with the plain
`VAEDecode`, which costs about 0.09 s more per clip -- and that cost is hidden
by the pipeline anyway.

## Where the remaining 2.563 s sits, and the ceiling

| Stage | Device | Per clip | On the critical path? |
| --- | --- | ---: | --- |
| Text encode | xpu:2 | 1.59 s | hidden |
| Sampler | xpu:0 + xpu:1 | 1.98 s | **yes** |
| Decode (video+audio) | xpu:3 | ~1.2 s | hidden |
| Save + per-prompt overhead | - | ~0.3 s | partly |

The interval is 2.563 s against a sampler of 1.98 s, so about 0.58 s is still
not overlapped -- the save, the prompt turnaround, and contention between the
worker threads and the sampler.

**The hard ceiling is now the text encoder, not the sampler.** In steady state
one encode must complete per clip, there is one copy of the 26 GB encoder on one
card, and it takes 1.59 s. That caps throughput at 1/1.59 = 0.63 clips/s, i.e.
**15.7 fps, even with a sampler of zero**. 1.45 s of that is fp32 matmul at
20.9 TFLOP/s and cannot be reduced without lowering precision.

So 24 fps needs the encode itself under 1.042 s. The one lossless route is a
**column-parallel split across two cards**: splitting a GEMM's output columns
keeps each output element's reduction over K identical, and this lane has
already verified bit-identity for `ff.net.0.proj`, `ff.net.2` and `attn.to_q`.
At fp32 the encoder's GEMMs dominate its 30.6 ms/layer, so a two-card split
could bring the encode near 0.85 s.

Target list, in order: column-parallel the encoder (lifts the 15.7 fps ceiling),
then the sampler from 1.98 s to at most 1.042 s against its 0.74 s weight-read
floor.
