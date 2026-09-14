# Cross-step text K/V reuse: reject unconditional caching

2026-09-14. Source audit only; no native request or runtime edit.

The saved confirmation places roughly 3.54 seconds in the two sampler nodes.
One possible reduction is caching text-attention key/value projections across
denoising steps because the raw prompt stays constant. This is not valid for
the current model without further proof.

The actual checkpoint header enables `cross_attention_adaln=true`, with 48
video and 48 audio prompt scale/shift tables. Packet10 model detection merges
the checkpoint transformer metadata into its constructor configuration.
`av_model.py` derives video/audio prompt timestep embeddings from the current
scaled timestep, then its `_apply_text_cross_attention` selects
`apply_cross_attention_adaln`. In `model.py`, that function computes
`context * (1 + scale_kv) + shift_kv` before the attention module projects keys
and values. The scale/shift includes the timestep-dependent prompt embedding.

Consequently, equal raw prompt/context does not establish equal attention
inputs across sigma values. Reusing those projections unconditionally would
skip required computation. Moving the affine transform past the linear
projection would also change floating-point operation order and needs its own
exactness proof; this audit does not authorize that rewrite.

[Evidence](../data/cross-step-text-kv-audit-01.json) pins all three source files
and the bounded checkpoint header read. The existing full checkpoint hash is
in [model verification](../data/model-verification.json). No full weight reread
was needed. No numerical failure or timing gain was measured: this is a
source-supported rejection of the unconditional cache idea, not a rejection
of every possible attention optimization.

Continue with execution overhead and the separate CPU embedding gather /
encoder residency candidate, retaining the original sampler arithmetic.
