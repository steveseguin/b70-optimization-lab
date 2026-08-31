# Qwen3.8 AutoRound INT4 native-GDN TP1 R8 preregistration

Date: 2026-08-31

Status: **preregistered before either R8 model request**

## Question

R3 showed shared TP2 nondeterminism, production INT4 operators were stable
across processes, all-reduce synchronization was negative, native GDN reached
10/12, and native-GDN synchronization regressed to 8/12. Does the same current
candidate repeat exactly with tensor parallelism removed?

## Frozen treatment

- exact deterministic image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU 0 only, TP1, AutoRound INT4, MTP0, FP16 activation/KV;
- repaired native GDN (`fallback=0`), sync-after-native off, persistent scratch;
- XPU Graph and prefix caching off; deterministic Inductor on;
- same complete fixed 12-prompt/six-class suite, each prompt once, fresh cache
  and server, complete token IDs, temperature 0, natural 512-token cap.

Run compiled `tp1-A`, then `tp1-B`. Pass requires all integrity, workload,
canary, cleanup, and journal gates plus 12/12 complete token-array equality.
Preserve both class-balanced rates. A refusal/OOM is a fit result, not a speed
cell; any mismatch is a determinism failure.

A pass localizes rather than automatically promotes: it establishes a TP1
candidate parent and evidence that TP2 remains defective. It still requires
the established full quality/baseline battery before publication or MTP work.
