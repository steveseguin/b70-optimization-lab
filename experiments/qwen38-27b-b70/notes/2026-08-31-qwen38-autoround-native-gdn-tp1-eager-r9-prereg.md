# Qwen3.8 AutoRound INT4 native-GDN TP1 eager R9 preregistration

Date: 2026-08-31

Status: **preregistered before either R9 model request**

## Question

R8's compiled TP1 arms matched only 7/12, proving a rank-local defect. D1 then
proved all production INT4 GEMMs exact across fresh processes at M=1 and every
actual prefill row count. Does removing Inductor/AOT while retaining the same
native-GDN runtime make TP1 repeat exactly?

## Frozen treatment

- exact deterministic image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU 0 only, TP1, AutoRound INT4, MTP0, FP16 activation/KV;
- repaired native GDN (`fallback=0`), sync-after-native off, persistent scratch;
- eager execution; XPU Graph and prefix caching off;
- same complete fixed 12-prompt/six-class suite, each prompt once, fresh cache
  and server, complete token IDs, temperature 0, natural 512-token cap.

Run `tp1-eager-A`, then `tp1-eager-B`. Pass requires every integrity,
workload, canary, cleanup, and journal gate plus 12/12 complete token-array
equality. Preserve both rates as diagnostic measurements.

A pass localizes the defect to the compiled path but does not promote eager or
compiled speed. A failure proves a shared rank-local path is unstable and
requires further kernel/state localization before quality or MTP work.
