# Qwen3.8 FP8 dynamic-MTP serial-GDN R35 diagnostic preregistration

Date: 2026-08-28

R34 failed exact target parity on five of twelve strict realistic prompts. A
static-MTP1 control using the R34 rebuilt active-width GDN artifact also first
diverged from the qualified MTP0 target on `risk-register` at generated token
440. R35 therefore tests one bounded mechanism only: replay each speculative
GDN convolution and recurrent verifier row through the ordinary one-token
kernels while snapshotting the selected source cache row.

This is a correctness diagnostic, not a performance campaign. It cannot
produce a publishable speed row.

## Fixed candidate

- base image:
  `neural-download/vllm-openai-xpu:qwen38-fp8-dynamic-deterministic-mtp8-r34`
  (`sha256:49780a358477b2a49fd25a5f9c317a443e86554680dabed23c789494c1e19e00`)
- candidate image:
  `neural-download/vllm-openai-xpu:qwen38-fp8-dynamic-serial-gdn-r35`
- vllm-xpu-kernels commit:
  `1e90ffa672ba02f17a909da11838a4c55b199783`
- combined kernel patch:
  `../patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch`
- patch SHA-256:
  `ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e`
- replacement `_xpu_C.abi3.so` SHA-256:
  `a190f22ccd9b2b6e638d7e0bc57e8a67946064219768d697a134786e8f6ee12d`
- GDN device library SHA-256:
  `2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355`
- required gate:
  `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`
- required runtime markers: both R35 serial convolution and recurrent markers

## Decision sequence

1. Start a fresh static-MTP1 singleton server with empty vLLM cache, graphs
   disabled, packed RMSNorm serial exact enabled, and R35 serial GDN enabled.
2. Run only the unchanged `risk-register` prompt from
   `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`, once, with
   seed 42, temperature 0, top-p 1, natural 512-token cap, token IDs returned,
   and cached prompt tokens equal to zero.
3. Pass requires all 512 generated token IDs to exactly equal the qualified
   MTP0 R15 target. Any first divergence is failure and stops this candidate.
4. Only after static MTP1 passes may the same sentinel be run under dynamic
   MTP8→MTP1. It must again match all 512 target token IDs exactly.
5. Only if both sentinels pass may a new full twelve-prompt, six-class,
   two-attempt strict campaign be separately preregistered and run.

No tolerance, text-only comparison, shortened output, selected-fixture speed,
prefix cache, repeated prompt, or target substitution is allowed.

## Result

The static-MTP1 sentinel passed 512/512 against R15 with cache zero and both
serial GDN markers firing on both TP ranks. The dynamic-MTP8 sentinel remained
non-exact: its first zero-based divergence was 127 (`8923` versus target
`4826`). The serial GDN treatment therefore repairs the rebuilt static path
but is insufficient for dynamic MTP8. The observed singleton rates are
diagnostic and are not publishable.
