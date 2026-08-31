# Qwen3.8 AutoRound INT4 native-GDN TP2 R6 preregistration

Date: 2026-08-30

Status: **preregistered before either R6 model request**

## Question

The current deterministic-parent wrapper forces
`VLLM_XPU_GDN_NATIVE_FALLBACK=1`, routing every ordinary MTP0 prefill/decode
through the PyTorch/FLA fallback. R3 showed shared eager/compiled
nondeterminism, production INT4 GEMMs were stable across eight processes, and
R5 proved that draining after all-reduce is insufficient. Does engaging the
repaired native XPU GDN path (`fallback=0`, persistent scratch retained) make
two fresh compiled servers repeat exactly while recovering speed?

## Frozen treatment

- exact current deterministic image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- two local B70s (0,1), TP2, AutoRound INT4, MTP0, FP16 activation/KV;
- XPU Graph and prefix caching off; deterministic Inductor on;
- INT4 determinism pad, deterministic FP16 GDN B/A prefill, explicit
  collective `Work.wait()`, and persistent GDN scratch unchanged;
- only treatment: `VLLM_XPU_GDN_NATIVE_FALLBACK=0` instead of `1`;
- same complete fixed 12-prompt/six-class suite, each prompt once, zero cache,
  complete token IDs, temperature 0, natural 512-token cap.

Run fresh compiled `native-A`, then `native-B`, each with a new compile/evidence
root and every existing integrity/workload/canary/journal gate. Pass requires
12/12 complete token-array equality. A backend refusal or any mismatch is a
negative.

Even a pass is a candidate-parent result, not automatic promotion: preserve
the measured speed, then require a separate quality/control attestation before
authorizing MTP or publishing a headline.
