# Qwen3.8 Python-ordered INT4 prefill pad D35 preregistration

Date: 2026-08-31

Status: **preregistered before D35 model requests**

Audit correction: the production stage isolated by D31r and D32 has shape
`[71, 6144]`. D32's `1` label passed that entire tensor; it was never a true
M=1 call. The M=1 repair series D33/D33r/D34 is withdrawn.

D35 changes the diagnostic hook so every `INCXPULinearMethod` input with
`32 < M < 512` is constructed as M=512 in Python, with all real rows copied in
order and the result sliced back after the unchanged operator returns. This
avoids both the nondeterministic M=71 primitive and the custom-op-internal
padding/copy ordering. M<=32, including decode M=1, is unchanged. D32 measured
M=32 and M=512 stable across all four processes; earlier dedicated true-M=1
screens also passed.

Immediate gate: four fresh process traces on the sealed current image. The
layer-0 call-2 normalized input and full `out_proj` output must each have one
hash. Output row zero must equal D32's M=512 reference
`bbec363c094e89d23a3fa5046063f358f63b67e4dfa50cddc5417cf608c524b5`.
The 64 generated token IDs must also be identical across processes; otherwise
the next divergence is localized separately.

A pass is only a repair-candidate gate. Packaging, a packaged-image replay,
the strict varied-prompt cross-process suite, independent output/quality
attestation, and cold performance A/B remain mandatory before promotion.
