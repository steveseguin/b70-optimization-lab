# Qwen3.8 GDN out-projection prefill pad D35r result

D35r produced a positive conditional repair and exposed the next upstream
dependency.

- Output row zero matched the preregistered D32 M=512 reference in 4/4 fresh
  processes.
- Processes 1, 2, and 4 had identical normalized inputs and identical complete
  71-row outputs after the M=512 projection.
- Process 3 entered `out_proj` with a different normalized tensor. Its BA
  projection had already differed and, unlike D31r's observed transition, the
  difference propagated through the recurrent core and norm.
- QKVZ and the input hidden tensor remained exact in all four processes.

Therefore the Python-ordered M=512 `out_proj` treatment is deterministic for
identical production input in this test. It is not sufficient alone because
the loaded M=71 BA projection is a second causal source. D36 applies the same
model-scoped prefill treatment to BA and `out_proj` while leaving QKVZ and all
unrelated model linears unchanged.
