# Qwen3.8 Flash-Next FP8 M1 MoE census A1 stop and A2 successor

Date: 2026-09-01
Status: A1 pre-execution failure preserved; A2 frozen before execution

A1 passed static identity and four-B70 discovery, then stopped on its first
`run_arm` call because one Bash `local` statement expanded `label` before the
assignment in that same statement. Strict undefined-variable handling caught
the wrapper defect. No Python component process, checkpoint weight load,
kernel invocation, timing, or output hash occurred. The partial evidence is
retained at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-config-census-a1`.

A2 changes only:

- the evidence root from suffix `a1` to `a2`;
- the local declaration into one assignment statement followed by the
  dependent `log`/`err` statement.

Every model, source, runtime, device, candidate, seed, timing, exactness, and
interpretation field remains identical to the
[A1 preregistration](2026-09-01-moe-m1-config-census-a1-prereg.md). A2 remains
a component screen only and cannot change a protected result. Its runner
SHA-256 is
`b30ebf7e12915cdcb43a76eaf097ff162c73387bcce2fbbd028ccdc62a22c0b4`.
