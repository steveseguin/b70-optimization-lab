# What a larger picture costs: decoder measured, transformer estimated (2026-10-06)

Owner's question: what would 640x360 do to the frame rate? The pipeline needs multiples of 64, so the sizes
probed are 256x256 (today), 512x320 and 640x384 (640x360 after a crop). Script
`scripts/probe-resolution-cost.py` (written by Codex), one card, eager, 12 transformer blocks, the real VAEs in
bf16, seeded random latents. Result file `data/resolution-cost/resolution-cost-01.json`.

## Decoder: measured

| Output size | Pixels vs 256x256 | Video decode, one card | vs 256x256 | Peak device memory |
| --- | ---: | ---: | ---: | ---: |
| 256x256 | 1.0x | 0.52 s | 1.0x | 2.6 GiB |
| 512x320 | 2.5x | 1.17 s | 2.26x | 3.1 GiB |
| 640x384 | 3.75x | 1.66 s | 3.2x | 3.5 GiB |

Audio decode is 0.19 s at every size. These are eager, decoder-only timings on seeded random latents.
They show decode cost growing almost in step with pixel count; they do not measure qualified whole-pipeline
throughput. The original statement here that the server replays a captured decoder was incorrect; see the
dated implementation clarification below.

## Transformer: not measurable this way

Eager block time came out at 8.1-8.6 ms per block at every token count (64 to 960), because in eager mode
the GPU work hides under Python dispatch, and the busy counter counts the context as active between kernels.
The server replays graphs, where September's measurement gave 2.74 ms per block at 64 tokens and 3.61 ms at
256. Extrapolating that slope (about 4.5 us per token per block) to 240 and 960 tokens gives roughly 1.5 times
today's sampler cost per clip for 640x384. Attention grows faster than linearly, so this may be low. A real
number needs a server run at that size (a packet variant with speed-only arms).

## What it adds up to (estimate)

Per clip at 640x384: sampler about 1.5x today's (estimate), decode about 3.2x today's (measured), text encoder
unchanged. With today's split (about 2.1 / 0.65 / 0.45 GPU-seconds), that is roughly 3.2 + 2.1 + 0.45 =
about 5.7 GPU-seconds per clip against about 3.0 now, so roughly half today's frame rate: about 13-16 fps on
this machine, around 20 fps with two more cards taking decode. The decoder becomes the biggest single cost,
so decoder cost is a plausible larger-size bottleneck. This is a historical estimate, not a demonstrated
bottleneck or throughput result; the original parenthetical claiming decoder graph capture and tiling were
already active was incorrect for the current exact-output lane.


## Implementation clarification — October 7, 2026

The measured decoder-only table above is retained. The accompanying implementation
claims “the server replays a captured decode graph” and “graph capture is already
in; tiling, bf16 already” were not supported by the qualified pipeline and must
not guide a new optimization experiment.

The qualified 99b optimized graph keeps node 423 `LTXVAEGraphGate` in
[`original` mode](/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/graphs/graph-capture-all48-pipe-samp2-tsh-rep-wlean-s1.json).
That mode leaves decoder methods unchanged
([gate source](/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/scripts/graph_vae_node.py:98)).
The pipeline uses native eager decode or an eager replica on another card
([native/replica dispatch](/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/scripts/pipeline_decode_node.py:349),
[replica implementation](/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/scripts/ltx_decode_replica.py:309)).
Sampler/text graph capture does not imply decoder graph capture.

The [packet 101 plan](../recovery/20261007-resolution-reference/candidate-plan.json)
preserves this distinction and independently checks native same-size references.
Its [native safety contract](../recovery/20261007-resolution-runtime/native-safety-contract.md)
requires refusal before OOM-to-tiled fallback; tiling is not an accepted shortcut
to exact native references. None of these statements asserts a completed 101
qualification or timing result.

Decoder graph capture has specific historical failures, including stale captured
outputs and host-backed RoPE-table copies, documented in
[the final decoder-capture investigation](vae-graph-capture-blocked-01.md#fourth-attempt-2026-09-16-the-real-cause-and-why-it-stays-blocked).
That route remains closed; it is not a ready optimization to enable. The old
13–16 fps projection also remains an estimate. Use completed, identity-bound
640×384 same-size parity and timing evidence for any new performance claim.
