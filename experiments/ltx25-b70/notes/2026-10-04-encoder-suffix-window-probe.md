# Suffix-window text encoding: five times faster, mathematically the same, not byte-identical (2026-10-04)

Stand-alone probes on one idle card (0000:27:00.0, `ZE_AFFINITY_MASK=1`),
eager, no server and no launcher, on kernel 7.0.0-38. Scripts:
`scripts/probe-encoder-suffix-window.py`,
`scripts/probe-encoder-window-localiser.py`,
`scripts/probe-linear-row-coupling.py`. Data: `data/encoder-window-probe-01/`.
Background: [survey](2026-10-04-lossless-gpu-work-reduction-survey.md) (every
prompt is left-padded to 1024 tokens and only the last N real rows are used).

## 1. Speed and exactness of the window

The encoder loaded as the server loads it (same ComfyUI tree and flags). Each
prompt was encoded at 1024 tokens and at window W = the last W tokens of the
same padded sequence, with position ids 1024-W..1023 and the sliding layers'
window set to W so attention takes the same expanded-KV path. Compared: the
all-layer hidden-state stack cropped to the real tokens (everything the
pipeline consumes). Ten fixtures (30-56 real tokens) plus 30 synthetic
prompts of 3-544 tokens.

| Length | Median encode time | Byte-identical to 1024 | Largest abs difference seen |
| ---: | ---: | ---: | ---: |
| 1024 (certified) | 1.504 s | reference (repeat pass identical) | - |
| 512 | 0.854 s | 0 of 37 | 1.6e-2 |
| 256 | 0.514 s | 0 of 31 | 9.5e-3 |
| 128 | 0.362 s | 0 of 25 | 1.2e-2 |
| 64 | 0.301 s | 0 of 19 | 8.6e-3 |

Each window is deterministic (its repeat pass is identical to itself).

## 2. Where the difference comes from

Localiser, fixture 0, W = 512, first two layers, every leaf module:

- `embed_tokens`, `input_layernorm`, `q_proj`, `q_norm`, `k_proj`, `v_proj`,
  `k_norm`: output **exact** on all 512 rows.
- The attention output (input of `o_proj`) is **exact on the real-token
  rows**. So masking works as the survey argued: padded keys contribute
  exactly zero and the attention sum is unaffected by dropping them.
- `o_proj` output: real rows differ by 1.7e-5 although their inputs are
  bit-identical. From there the difference propagates (layer 24: 2.3e-3,
  layer 47: 1.3e-5 on real rows).

Isolated linear-layer test (random fp32 inputs, bf16 weights cast to fp32 as
the encoder does):

- A row's result never depends on what the other rows contain (zeros, x50,
  x5000: exact for every shape and row count).
- A row's result **does depend on the row count** of the call. Against 1024
  rows: 3840->4096 is identical at 512/256/128 and differs at 64;
  4096->3840, 3840->15360, 15360->3840 and 2048->3840 differ at every smaller
  row count (2e-4 to 3e-3 on unit-scale inputs).

So the GEMM kernel this stack selects changes its accumulation order with
the number of rows. The window is the same mathematics in a different
rounding order; relative to activations of order 10-1000 the differences are
at fp32 rounding level.

## 3. Consequence

No bucket can be byte-identical to the 1024-token references on this stack:
the certified bytes belong to the 1024-row kernels. A windowed encoder is a
**re-ordered kernel** in the sense of the lab rule "an oracle is bound to a
kernel identity" (AGENTS.md, diagnosis rule 2): it needs its own oracle,
regenerated on the windowed path, and every later optimisation is then gated
byte-for-byte against that new oracle. It is not lower precision, fewer
steps, or a cache.

Sizing if adopted: the encoder falls from about 2.0 GPU-s per clip to about
0.4 (W = 64 covers all ten fixtures; 128 covers prompts to 128 tokens), a
clip from about 5.1 to about 3.5 GPU-s, and the perfectly balanced four-card
interval from 1.26 s to about 0.87 s. It also empties most of two cards'
compute time, which the sampler can use.

What this note does not show: the windowed path under graph capture (only
eager was run), the effect on the final video (expected at rounding level;
to be measured as old-versus-new reference differences), and whether a fixed
row-tile formulation would make all buckets agree with each other.

## 4. Is the difference bigger than honest hardware variation? (added 03:50 UTC)

`scripts/probe-encoder-window-vs-hardware-noise.py`, three fixtures, real-token
rows of the all-layer hidden-state stack (values up to about 3,270, mean
magnitude about 0.74). "Unchanged on CPU" is the same padded 1024-token
encode of the unchanged model run on the host CPU instead of the GPU.

| Fixture (real tokens) | Unchanged on CPU vs GPU reference: mean / max abs diff | 64-token window vs GPU reference: mean / max abs diff |
| --- | ---: | ---: |
| 0 (56) | 3.7e-6 / 7.0e-3 | 4.5e-6 / 8.6e-3 |
| 1 (31) | 4.2e-6 / 2.7e-3 | 3.4e-6 / 2.4e-3 |
| 2 (31) | 3.7e-6 / 2.7e-3 | 2.9e-6 / 2.4e-3 |

Relative mean difference is 4-6 parts per million in both columns; cosine
similarity is 0.999999999998 or better in both. The window differs from the
GPU reference by the same amount as the unchanged encoder does when it is
simply run on a CPU, and for two of three prompts by less. On this measure
the window is inside the variation the unchanged model already shows between
two honest machines. Still to be measured: the difference in finished frames
and audio (packet 93). Linear-layer row-count scan (which row counts match a
1024-row call per shape): `data/encoder-window-probe-01/linear-row-count-scan.json`.
