# Qwen3.8 final-hidden trace D9 preregistration

Date: 2026-08-31

Status: **preregistered before D9 model requests**

## Question

The strict TP1 eager repeats first diverged at zero-based output token 60 for
`sql-debugging`. At the model execution that produces that token, are the final
normalized hidden states already different, or does divergence begin in the LM
head/sampling stage?

## Frozen diagnostic

- exact current image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- direct-and-ordinary verified local checkpoint, GPU0, TP1, FP16 runtime, MTP0,
  eager, graph off, prefix caching off;
- four fresh servers and four distinct empty cache roots;
- exact realistic-suite raw-completions prompt `sql-debugging`, seed 42,
  temperature 0, top-p 1, 64 output tokens;
- at model-forward call index 60 only, hash the complete input token IDs,
  positions, and final normalized hidden states. No earlier instrumentation
  synchronization is allowed.

If the call-60 inputs match but final hidden states differ, divergence is in the
decoder/final norm. If inputs and hidden states match but generated output
differs, divergence is after the model forward (LM head or sampling). If no
fresh-process output branch occurs, the run is negative and inconclusive. This
is diagnostic only and cannot promote a speed or quality claim.
