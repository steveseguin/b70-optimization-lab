# Packet21: graph capture plus the axis-cache decoder; clip 6.41 -> 4.68 s

September15, 2026, boot `831530c8`. Packet21
(`prepared-encoder-graph-capture-21`, manifest
`d515527a6f7eb1277df5f354a46522e6da1597b73fca08a91519caee70fa5498`), server
`encoder-server-graph-capture-21`, PID9039. Thirteen clips across four
interleaved arms. **All thirteen matched their original references bytewise on
all four raw outputs.**

The packet crosses two independent, separately restorable dimensions:

- the **transformer gate** (`original` | `graph` | `restored`), and
- the **video decoder**: the original `VAEDecode`, or `LTXNAAxisDecode` in
  `axis-cache` mode, the candidate already qualified in
  [na-axis-confirm-01](na-axis-confirm-01-results.md) over 18 clips.

## Effects, measured separately

| Effect | Without | With | Result |
| --- | ---: | ---: | --- |
| Graph capture, on the sampler | 3.616 s | **1.942 s** | **1.86x** |
| Axis cache, on the decoder (graph arm) | 0.611 s | **0.560 s** | **−50.7 ms** |
| Axis cache, on the decoder (control arm) | 0.632 s | **0.561 s** | **−71.4 ms** |
| Both, on the whole clip | 6.415 s | **4.682 s** | **1.37x, −1.733 s** |

Every axis-cache clip decoded faster than every non-cache clip in the same arm,
so the decoder effect is cleanly separated even at this sample size. It is
smaller inside the graph arm (−50.7 ms) than in the control arm (−71.4 ms) and
than the original 18-clip qualification (−83.2 ms median); the arms are small and
this note does not claim the difference is real.

The two changes are independent, as expected: the axis cache does not move the
sampler (1.942 s versus 1.950 s) and graph capture does not move the decoder.

## Standing position

| Stage | Original | Now | Effect |
| --- | ---: | ---: | ---: |
| Text encode (364) | 1.741 s | 1.741 s | untouched |
| Sampler (344+368) | 3.616 s | **1.942 s** | 1.86x |
| Video decode (374) | 0.632 s | **0.560 s** | 1.13x |
| **Warm clip preview** | **6.415 s** | **4.682 s** | **1.37x** |

For 1.042 s of video at 256x256, 25 frames, 24 fps, native BF16, 8+3 sampler
steps, bytewise identical to the original references on every clip.

Restoring the transformer gate returns the sampler to 4.511 s on the first
request and 3.635 s after, so the routes come back cleanly.

## What is left, and where it is

The clip is now **encode 1.741 + sampler 1.942 + decode 0.560 + 0.44 other**.

- **Text encode, 37% of the clip.** It runs all 48 Gemma layers over a `[1, 1024]`
  left-padded sequence and keeps only the valid suffix. Reducing the padding is
  the single largest remaining inefficiency, but it is **not a bitwise lever**:
  the tokenizer left-pads to `min_length=1024`, so shortening it shifts every
  valid token's absolute position. RoPE makes attention scores depend only on
  relative positions, so a constant shift is *mathematically* equivalent, but the
  per-token rotations differ in floating point and the four-tensor oracle would
  fail. It therefore needs an explicit, separately labelled quality decision per
  the plan, and is not attempted here. In continuous generation it is a
  per-scene cost that amortises to nothing anyway.
- **Sampler, 41%.** Now GPU-bound. The measured next lever is 2-way column
  parallelism: the two B70s do replay graphs with perfect concurrency
  (factor 1.999) and gathers cost 0.04 ms, but halving a block's weights only
  takes its chain from 104.3 to 66.4 ms, so the projection is
  [1.41x on the GPU portion](../data/column-parallel-feasibility-01.json), about
  −0.45 s, for a full column-wise re-shard.
- **Decode, 12%.** Still fully eager. Graph capture has not been extended to it.

Evidence: [`data/graph-capture-21-result.json`](../data/graph-capture-21-result.json)
and the per-clip summaries under [`data/graph-capture-21/`](../data/graph-capture-21/).
