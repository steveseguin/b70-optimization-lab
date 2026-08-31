# Qwen3.8 repaired-MLP all-layer D50 result

D50 localized the next prefill nondeterminism source to decoder layer 3, the
first full-attention layer.

- Decoder inputs and outputs were bit-exact through layers 0, 1, and 2.
- Layer 3 received the same input in all four fresh processes, but returned
  four distinct hidden-state hashes.
- Complete 64-token responses still split into two classes (3+1), first at
  generated token index 60.
- Positions were identical, prefix caching was disabled, and every process used
  a separate cache directory.

This proves the synchronized M=512 dense-MLP repair moved the earliest observed
divergence past the first three linear-attention layers. D51 keeps that repair
active and splits layer 3 into normalization, full-attention, post-attention,
and MLP boundaries. D50 is a one-prompt synchronized causal diagnostic, not a
publishable speed or quality result.
