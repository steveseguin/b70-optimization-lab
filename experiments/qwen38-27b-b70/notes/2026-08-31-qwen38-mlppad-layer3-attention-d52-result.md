# Qwen3.8 repaired-MLP layer-3 attention D52 result

D52 found two unstable M=71 INT4 projections in the first full-attention
layer.

- Input, input norm, residual, V, and gate were bit-identical 4/4.
- Packed QKV produced four hashes; Q produced four and K two.
- Those Q/K differences produced two raw/gated-attention hashes.
- The attention output projection produced four hashes from those two inputs.
- Complete responses remained split 3+1 at generated token index 60.

Thus the attention kernel is downstream of unstable QKV arithmetic, while the
output projection is a second arithmetic source. D53 pads both full-attention
projection roles plus the already-proven dense-MLP down role to M=512 during
medium-width prefill, retains the GDN projection repair, and retraces every
decoder layer. D52 is a synchronized one-prompt diagnostic, not a speed or
quality result.
