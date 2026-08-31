# Qwen3.8 repaired-MLP layer-3 D51 result

D51 places the next nondeterministic prefill operation inside layer 3 full
attention.

- Layer input, input normalization, and its residual were bit-identical 4/4.
- Full-attention output had four different hashes in four fresh processes.
- Post-attention normalization, residual, and repaired MLP output inherited the
  four-way split.
- Complete responses split 3+1, first at generated token index 60.

D52 therefore splits the production full-attention path into packed QKV,
Q/K normalization and RoPE, V/gate, attention, gating, and output projection.
This synchronized one-prompt diagnostic is not a speed or quality claim.
