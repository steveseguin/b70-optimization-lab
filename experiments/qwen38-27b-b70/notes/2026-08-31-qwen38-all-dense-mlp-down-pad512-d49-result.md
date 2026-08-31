# Qwen3.8 all dense MLP down M=512 D49 result

D49 proves the model-wide dense-MLP repair engages and is exact, but it does
not yet make the complete model deterministic.

- The first repaired MLP input and complete M=512 down output were identical
  across four fresh processes; the trace JSON matched 4/4.
- Complete 64-token responses produced two SHA-256 values: one in three
  processes and one in the fourth.
- The first token difference remained generated token index 60.
- Every request was fresh (`cached_tokens=0`) and valid. This was a one-prompt
  causal diagnostic, not a publishable performance or quality suite.

The repair reduced a four-way layer-0 MLP boundary to one exact value and is
retained as a diagnostic dependency. D50 keeps it active while hashing all 64
decoder-layer boundaries at prefill call 2 to locate the next source. Nothing
is packaged or promoted yet.
