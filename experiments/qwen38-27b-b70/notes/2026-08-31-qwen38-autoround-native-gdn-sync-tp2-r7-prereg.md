# Qwen3.8 AutoRound INT4 native-GDN synchronization TP2 R7 preregistration

Date: 2026-08-31

Status: **preregistered before either R7 model request**

## Question

R6's repaired native-GDN route was faster and more repeatable than the shared
fallback route, but two fresh servers still matched only 10/12 prompts. Does a
device completion boundary immediately after every ordinary native XPU GDN
call eliminate the remaining cross-process divergence?

## Frozen treatment

- exact deterministic image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- two local B70s (0,1), TP2, AutoRound INT4, MTP0, FP16 activation/KV;
- native GDN enabled (`VLLM_XPU_GDN_NATIVE_FALLBACK=0`), persistent scratch;
- XPU Graph and prefix caching off; deterministic Inductor on;
- only treatment relative to R6:
  `VLLM_XPU_GDN_SYNC_AFTER_NATIVE=1`;
- same complete fixed 12-prompt/six-class suite, each prompt once, fresh cache
  and server, complete token IDs, temperature 0, natural 512-token cap.

Run fresh compiled `gdn-sync-A`, then `gdn-sync-B`. Pass requires every
existing integrity/workload/canary/journal gate plus 12/12 complete token-array
equality. A refusal, mismatch, or fault is negative. Preserve both strict rates
to measure synchronization cost.

Even a pass establishes only a candidate deterministic MTP0 parent. It still
requires a separate quality/control attestation before MTP or headline use.
