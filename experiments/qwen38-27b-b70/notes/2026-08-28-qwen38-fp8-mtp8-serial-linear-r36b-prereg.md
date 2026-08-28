# Qwen3.8 FP8 MTP8 packed-linear R36b eager-routing diagnostic

Date: 2026-08-28

R36 failed preflight because its compiled graph never reached the Python
nine-row packed-FP8 marker. Its output is not evidence about the treatment.
R36b changes only target execution to `--enforce-eager`, so the exact runtime
row count reaches the same already-built R36 branch. This is a routing and
correctness discriminator, not a speed candidate.

Use the R36 image and treatment settings unchanged, a new empty runtime cache,
and the same dynamic MTP8→MTP1 schedule, but set `ENFORCE_EAGER=1`. Require the
R36 packed-FP8 marker and both R35 serial-GDN markers on both ranks. Then run
the unchanged one-prompt, 512-token, cache-zero `risk-register` sentinel.

Pass requires all 512 token IDs to exactly equal qualified MTP0 R15. Missing
markers or any divergence is failure. No speed from this eager diagnostic may
be promoted, and a pass authorizes only a separate implementation capable of
preserving the treatment under compiled execution.
