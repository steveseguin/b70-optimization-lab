# Ornith 1.5 35B-A3B: Q6_K output head through MMVQ

Date: 2026-08-23 EDT

Status: **closed engine-neutral — deterministic transcript matched; not shipped**

Ornith's Qwen lineage suggested one output-head transfer not covered by the
earlier ESIMD geometry screens. The accepted one-token path reads the Q6_K
`[2048,248320]` vocabulary weight with the direct-FP32 reordered ESIMD DMMV
kernel. The SYCL backend also has an incumbent reordered MMVQ path that first
quantizes the activation to Q8_1. The candidate routed only the exact
`result_output` shape through MMVQ; every prompt batch and every other tensor
retained accepted dispatch.

The candidate was default-off behind `GGML_SYCL_ORNITH_FINAL_MMVQ=1`. Its
initialization door and hit counter wrote directly to the diagnostic log, so a
silent no-op could not pass the screen. The forced 128-token candidate recorded
127 hits and each seven-repetition engine run recorded 889 (`7 × 127`) hits.

With fixed seed 42 and temperature zero, control and candidate generated the
same byte-for-byte transcript, SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
This is a deterministic token-output result, not a claim that all FP32 logits
are identical: the candidate deliberately introduces Q8_1 activation
quantization. Because it failed the performance gate, no larger logit or canary
qualification was warranted.

The matched engine screen used one B70, the accepted eleven-feature stack and
copy-offload setting, `p0/n128/d0/r7`, one final binary, and A/B/B/A ordering:

| Arm | Run averages (tok/s) | Mean |
| --- | --- | ---: |
| direct-FP32 ESIMD control | 133.714817, 133.088761 | 133.401789 |
| Q8_1 MMVQ candidate | 133.540733, 133.619933 | 133.580333 |

The measured mean difference was **+0.1338%**, with both candidates below
control A1 and above control A2. The arms crossed and the effect remained
noise-scale, so no fresh-server test was run. Direct-FP32 ESIMD remains the
accepted output-head path. No serialized timing was converted into a throughput
estimate, and no unmeasured result was extrapolated.

The incremental candidate is preserved at
`../patches/llamacpp-ornith15-final-q6k-mmvq-neutral-20260823.patch`. Raw
exactness and engine artifacts are under `../data/`. After the screen, the
source diff and all four published binaries were restored byte-for-byte to the
accepted package hashes recorded in the structured summary.
