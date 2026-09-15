# Packet13: text encoder made fully resident; exact, and speed-neutral

September14, 2026. Packet13 (`prepared-encoder-host-residency-13`, manifest
`174e80b56ce16d712f1315832463baa0f86657c5568d587719f421925ea7a29f`) changes
exactly one thing from packet12: the launcher's `--reserve-vram` goes from 6 GiB
to 2 GiB. Every `source/` and `graphs/` byte is inherited unchanged, and the new
checker proves it by requiring all 1,343 packet12 files to reappear with their
recorded digests.

## What it fixed

Packet12's text encoder never loaded fully. With a 6 GiB reserve, a 32,657 MB
card offered 24,586 MB for ~25,100 MB of Gemma weights, so 457.51 MB stayed on
CPU and were re-copied through blocking pageable transfers every forward. The
offloaded share **grew every request** (457.51 -> 510.00 -> 555.00 -> 600.00 MB).
Under packet13 the encoder reports `loaded completely; 28682.00 MB usable,
24999.98 MB loaded, full load: True`, with no offload and no growth.

## What it did not do

| Measure | Packet12 (n=4) | Packet13 (n=5) | Effect |
| --- | ---: | ---: | ---: |
| Warm preview | 6.363 s | 6.489 s | +0.126 s |
| Text encode (364) | 1.800 s | 1.778 s | −0.022 s |
| Sampler (344+368) | 3.572 s | 3.627 s | +0.055 s |
| Video decode (374) | 0.606 s | 0.649 s | +0.043 s |

All five warm clips matched their original references **bytewise on all four raw
outputs**, so the residency change is output-identical as predicted. It is not a
speed win. These are separate processes, not interleaved arms, and this lane has
already measured 4.38% drift between bracketing controls, so the +2% preview
difference is not established as a regression either. **Decision: exact,
mechanism-correct, speed-neutral; not promoted as a speed result.** Keep it as
the base for later work because the growing offload is gone.

## The correction this forces

The [dispatch-bound diagnosis](dispatch-bound-diagnosis-01.md) predicted a ~1.4 s
win here, reading 78.9% py-spy occupancy at `cast_to`'s blocking copy as
removable overhead. **That reading was wrong**, in exactly the way that note's
own limitation paragraph and the earlier small-state screen both warned about: a
synchronous copy parks the thread while the GPU drains earlier queued work, so
its stack occupancy is GPU wait, not dispatch cost. Two independent candidates
have now failed the same way. The rule this lane should apply: **py-spy occupancy
at a synchronous copy or any blocking call is not a latency estimate, and must
never be converted into one without an A/B that removes the call.**

## What the resident encoder actually spends its time on

Re-profiling packet13 (one clip, 6.402 s preview, still bytewise exact) moves the
occupancy somewhere much more informative:

| Leaf | Share of encode |
| --- | ---: |
| `scaled_dot_product_attention (ops.py:61)` | **71.3%** |
| `encode_token_weights (sd1_clip.py:73)` | 8.8% |
| `cast_bias_weight (ops.py:432)` | 4.7% |
| `forward (gemma4.py:643)` | 4.1% |

The placement receipt records the cause: `input_ids` is **`[1, 1024]`**. The
encoder runs all 48 Gemma layers over a 1024-token padded sequence and then keeps
only the valid suffix (`out[:, :, -sum(attention_mask):]`). Attention over the
padding is roughly 1.27 s of the 1.78 s. Cropping it is **not** obviously exact:
the padding is on the left, so cropping moves every valid token's position and
changes RoPE, and a shorter softmax row can change reduction order. Any such
candidate needs its own bitwise gate, and this is deliberately not attempted here.

More importantly, text encoding is a **per-scene** cost, not a per-frame one. The
north star is continuous generation, where a fixed prompt is encoded once and
amortizes toward zero. The per-frame path is sampler 3.63 s plus decode 0.65 s
= 4.28 s for 1.042 s of video. That is where the remaining work belongs.

## Also observed, for the decode stage

In the same profile the video decode stage spends ~39.5% of its samples in
`_group_mask (eager/na.py:74-77)`, rebuilding neighborhood-attention geometry per
call. That is the cost the already-qualified [axis cache](na-axis-confirm-01-results.md)
removes: 18 confirmation clips, all bytewise exact, decoder effect −83.2 ms
median. It is not active in the control arm. It remains a real, proven, small win
available for later inclusion.

Evidence: [`data/host-residency-13-result.json`](../data/host-residency-13-result.json),
per-run summaries and the profile under [`data/host-residency-13/`](../data/host-residency-13/).
Negative tests for the new packet gate: [`scripts/test-host-residency-packet-negative.py`](../scripts/test-host-residency-packet-negative.py).
